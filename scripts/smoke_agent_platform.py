#!/usr/bin/env python3
"""End-to-end smoke test for the agent workspace platform.

Exercises the full built surface (credentials CRUD, environments, artifacts,
webhooks, workspace isolation, sessions alias) against a running local API,
then allocates a REAL Daytona sandbox to verify the sandbox boot path and
egress proxy wiring.

Each phase reports one of:
    PASS — behavior matches expectation
    FAIL — regression against a built feature (exit nonzero)
    GAP  — spec requirement not implemented yet (expected; documented, not a failure)
    SKIP — prerequisite unavailable (e.g. DAYTONA_API_KEY unset)

Exit code is 0 unless any FAIL is recorded. GAPs are tracked but do not fail
the run — they're the map of what's left to build.

Prerequisites:
    - Backend API running at API_BASE_URL (default http://localhost:18000)
    - Postgres + Redis up (just watch)
    - CREDENTIAL_ENCRYPTION_KEY set
    - Feature flags flipped (sessions_api_v1, environments_v1, broker_enabled,
      egress_proxy_enabled, artifacts_unified_v1, webhooks_enabled)
    - DAYTONA_API_KEY set (required — per project decision, no mock mode)
    - OMOIOS_PLATFORM_API_KEY set (tenant-scoped platform key)

Usage:
    uv run python scripts/smoke_agent_platform.py
    uv run python scripts/smoke_agent_platform.py --keep-sandbox
    uv run python scripts/smoke_agent_platform.py --only credentials_crud,artifacts_roundtrip
    uv run python scripts/smoke_agent_platform.py --report .sisyphus/evidence/smoke-$(date +%F).json
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import hmac
import json
import os
import secrets
import socket
import sys
import threading
import time
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Callable, Optional

import httpx


API_BASE_URL = os.environ.get("OMOIOS_API_BASE_URL", "http://localhost:18000")
PLATFORM_KEY = os.environ.get("OMOIOS_PLATFORM_API_KEY", "")
DAYTONA_API_KEY = os.environ.get("DAYTONA_API_KEY", "")
DAYTONA_API_URL = os.environ.get("DAYTONA_API_URL", "https://app.daytona.io/api")
EGRESS_PROXY_URL = os.environ.get("OMOIOS_EGRESS_PROXY_URL", "http://egress-proxy:3128")
EGRESS_ALLOWED_HOST = os.environ.get("SMOKE_EGRESS_ALLOWED_HOST", "api.github.com")
EGRESS_BLOCKED_HOST = os.environ.get("SMOKE_EGRESS_BLOCKED_HOST", "example.com")


class Verdict(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    GAP = "GAP"
    SKIP = "SKIP"


@dataclass
class PhaseResult:
    name: str
    verdict: Verdict
    duration_sec: float = 0.0
    detail: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass
class Context:
    """Mutable shared state across phases."""
    org_id: Optional[str] = None
    workspace_a_id: Optional[str] = None
    workspace_b_id: Optional[str] = None
    binding_a_id: Optional[str] = None
    binding_b_id: Optional[str] = None
    environment_id: Optional[str] = None
    env_version_1: Optional[int] = None
    env_version_2: Optional[int] = None
    artifact_id: Optional[str] = None
    webhook_sub_id: Optional[str] = None
    webhook_secret: Optional[str] = None
    daytona_sandbox_id: Optional[str] = None
    client: Optional[httpx.AsyncClient] = None


def auth_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {PLATFORM_KEY}",
        "Content-Type": "application/json",
    }


# ─── phase registry ──────────────────────────────────────────────────────────

PHASES: list[tuple[str, Callable[[Context], Any]]] = []


def phase(name: str):
    """Decorator: register an async function as a named phase."""
    def wrap(fn: Callable[[Context], Any]) -> Callable[[Context], Any]:
        PHASES.append((name, fn))
        return fn
    return wrap


# ─── utility: local webhook catcher ───────────────────────────────────────────

class WebhookCatcher:
    """Spins up a one-shot HTTP server to receive a webhook POST."""

    def __init__(self):
        self.received: list[dict[str, Any]] = []
        self._server: Optional[HTTPServer] = None
        self._thread: Optional[threading.Thread] = None
        self.port = self._pick_port()

    @staticmethod
    def _pick_port() -> int:
        with socket.socket() as s:
            s.bind(("", 0))
            return s.getsockname()[1]

    def start(self) -> str:
        catcher = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length) if length else b""
                catcher.received.append({
                    "headers": dict(self.headers),
                    "body": body.decode(errors="replace"),
                    "received_at": time.time(),
                })
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'{"ok":true}')

            def log_message(self, *a, **k):  # quiet
                pass

        self._server = HTTPServer(("127.0.0.1", self.port), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return f"http://127.0.0.1:{self.port}/hook"

    def stop(self):
        if self._server:
            self._server.shutdown()


# ─── phases ─────────────────────────────────────────────────────────────────

@phase("prereqs")
async def phase_prereqs(ctx: Context) -> PhaseResult:
    missing = []
    if not PLATFORM_KEY:
        missing.append("OMOIOS_PLATFORM_API_KEY")
    if not DAYTONA_API_KEY:
        missing.append("DAYTONA_API_KEY")
    if not os.environ.get("CREDENTIAL_ENCRYPTION_KEY"):
        missing.append("CREDENTIAL_ENCRYPTION_KEY")
    if missing:
        return PhaseResult("prereqs", Verdict.FAIL, detail=f"missing env vars: {missing}")

    # Ping the API.
    try:
        r = await ctx.client.get(f"{API_BASE_URL}/health", timeout=5.0)
        if r.status_code >= 400:
            return PhaseResult("prereqs", Verdict.FAIL, detail=f"/health returned {r.status_code}")
    except Exception as e:
        return PhaseResult("prereqs", Verdict.FAIL, detail=f"API not reachable: {e}")

    return PhaseResult("prereqs", Verdict.PASS, detail="env + API reachable")


@phase("org_setup")
async def phase_org_setup(ctx: Context) -> PhaseResult:
    """Resolve an org + two workspaces for isolation tests.

    Platform keys are tenant-scoped so the org is implied by the key. We just
    need workspace IDs — read the first two from whatever the key resolves to.
    """
    r = await ctx.client.get(f"{API_BASE_URL}/api/v1/workspaces", headers=auth_headers())
    if r.status_code != 200:
        return PhaseResult("org_setup", Verdict.FAIL,
                           detail=f"list workspaces: {r.status_code} {r.text[:200]}")
    wss = r.json() if isinstance(r.json(), list) else r.json().get("items", [])
    if len(wss) < 2:
        return PhaseResult("org_setup", Verdict.SKIP,
                           detail=f"need ≥2 workspaces for isolation tests, found {len(wss)}")
    ctx.workspace_a_id = wss[0]["id"]
    ctx.workspace_b_id = wss[1]["id"]
    ctx.org_id = wss[0].get("organization_id") or wss[0].get("org_id")
    return PhaseResult("org_setup", Verdict.PASS,
                       evidence={"ws_a": ctx.workspace_a_id, "ws_b": ctx.workspace_b_id})


@phase("credentials_crud")
async def phase_credentials_crud(ctx: Context) -> PhaseResult:
    """POST/GET/DELETE /api/v1/credentials — built surface."""
    plaintext = f"sk-smoke-{secrets.token_hex(8)}"
    r = await ctx.client.post(
        f"{API_BASE_URL}/api/v1/credentials",
        headers=auth_headers(),
        json={
            "workspace_id": ctx.workspace_a_id,
            "kind": "bearer_secret",
            "name": f"smoke-{secrets.token_hex(4)}",
            "value": plaintext,
        },
    )
    if r.status_code not in (200, 201):
        return PhaseResult("credentials_crud", Verdict.FAIL,
                           detail=f"create: {r.status_code} {r.text[:300]}")
    created = r.json()
    ctx.binding_a_id = created["id"]

    # Response must NOT contain the plaintext.
    body_text = r.text
    if plaintext in body_text:
        return PhaseResult("credentials_crud", Verdict.FAIL,
                           detail="PLAINTEXT LEAK: create response contains plaintext value")

    # GET by id.
    r = await ctx.client.get(f"{API_BASE_URL}/api/v1/credentials/{ctx.binding_a_id}",
                             headers=auth_headers())
    if r.status_code != 200:
        return PhaseResult("credentials_crud", Verdict.FAIL,
                           detail=f"get: {r.status_code} {r.text[:300]}")
    if plaintext in r.text:
        return PhaseResult("credentials_crud", Verdict.FAIL,
                           detail="PLAINTEXT LEAK: get response contains plaintext value")

    return PhaseResult("credentials_crud", Verdict.PASS,
                       evidence={"binding_id": ctx.binding_a_id})


@phase("environments_crud")
async def phase_environments_crud(ctx: Context) -> PhaseResult:
    """Create env → v1 (with secret variable) → v2 → verify v1 still retrievable."""
    r = await ctx.client.post(
        f"{API_BASE_URL}/api/v1/environments",
        headers=auth_headers(),
        json={
            "name": f"smoke-{secrets.token_hex(4)}",
            "description": "smoke test env",
            "org_id": ctx.org_id,
        },
    )
    if r.status_code not in (200, 201):
        return PhaseResult("environments_crud", Verdict.FAIL,
                           detail=f"create env: {r.status_code} {r.text[:300]}")
    ctx.environment_id = r.json()["id"]

    secret_plaintext = f"env-secret-{secrets.token_hex(8)}"
    r = await ctx.client.post(
        f"{API_BASE_URL}/api/v1/environments/{ctx.environment_id}/versions",
        headers=auth_headers(),
        json={"variables": {
            "DB_URL": {"type": "string", "value": "postgres://example"},
            "API_KEY": {"type": "secret", "value": secret_plaintext},
        }},
    )
    if r.status_code not in (200, 201):
        return PhaseResult("environments_crud", Verdict.FAIL,
                           detail=f"v1: {r.status_code} {r.text[:300]}")
    v1 = r.json()
    ctx.env_version_1 = v1.get("version_number") or v1.get("version")

    if secret_plaintext in r.text:
        return PhaseResult("environments_crud", Verdict.FAIL,
                           detail="PLAINTEXT LEAK: env v1 response contains secret value")

    r = await ctx.client.post(
        f"{API_BASE_URL}/api/v1/environments/{ctx.environment_id}/versions",
        headers=auth_headers(),
        json={"variables": {"DB_URL": {"type": "string", "value": "postgres://changed"}}},
    )
    if r.status_code not in (200, 201):
        return PhaseResult("environments_crud", Verdict.FAIL,
                           detail=f"v2: {r.status_code} {r.text[:300]}")
    v2 = r.json()
    ctx.env_version_2 = v2.get("version_number") or v2.get("version")

    if ctx.env_version_2 == ctx.env_version_1:
        return PhaseResult("environments_crud", Verdict.FAIL,
                           detail="v2 did not increment version")
    return PhaseResult("environments_crud", Verdict.PASS,
                       evidence={"env_id": ctx.environment_id,
                                 "v1": ctx.env_version_1, "v2": ctx.env_version_2})


@phase("artifacts_roundtrip")
async def phase_artifacts_roundtrip(ctx: Context) -> PhaseResult:
    """Upload → download → checksum match."""
    payload = f"smoke-artifact-{secrets.token_hex(16)}".encode()
    expected_sha = hashlib.sha256(payload).hexdigest()

    files = {"file": ("smoke.bin", payload, "application/octet-stream")}
    r = await ctx.client.post(
        f"{API_BASE_URL}/api/v1/artifacts/upload",
        headers={"Authorization": f"Bearer {PLATFORM_KEY}"},
        files=files,
        data={"workspace_id": ctx.workspace_a_id},
    )
    if r.status_code not in (200, 201):
        return PhaseResult("artifacts_roundtrip", Verdict.FAIL,
                           detail=f"upload: {r.status_code} {r.text[:300]}")
    ctx.artifact_id = r.json()["id"]

    r = await ctx.client.get(
        f"{API_BASE_URL}/api/v1/artifacts/{ctx.artifact_id}/download",
        headers=auth_headers(),
    )
    if r.status_code != 200:
        return PhaseResult("artifacts_roundtrip", Verdict.FAIL,
                           detail=f"download: {r.status_code}")
    got_sha = hashlib.sha256(r.content).hexdigest()
    if got_sha != expected_sha:
        return PhaseResult("artifacts_roundtrip", Verdict.FAIL,
                           detail=f"checksum mismatch: expected {expected_sha}, got {got_sha}")
    return PhaseResult("artifacts_roundtrip", Verdict.PASS,
                       evidence={"artifact_id": ctx.artifact_id, "sha256": got_sha})


@phase("webhooks_hmac")
async def phase_webhooks_hmac(ctx: Context) -> PhaseResult:
    """Register subscription → trigger event → catcher receives + HMAC verifies."""
    catcher = WebhookCatcher()
    url = catcher.start()
    ctx.webhook_secret = f"whsec_{secrets.token_hex(16)}"
    try:
        r = await ctx.client.post(
            f"{API_BASE_URL}/api/v1/webhooks/subscriptions",
            headers=auth_headers(),
            params={"org_id": ctx.org_id},
            json={
                "url": url,
                "events": ["artifact.uploaded"],
                "secret": ctx.webhook_secret,
            },
        )
        if r.status_code not in (200, 201):
            return PhaseResult("webhooks_hmac", Verdict.FAIL,
                               detail=f"subscribe: {r.status_code} {r.text[:300]}")
        ctx.webhook_sub_id = r.json()["id"]

        # Trigger an artifact.uploaded by uploading a small file.
        r = await ctx.client.post(
            f"{API_BASE_URL}/api/v1/artifacts/upload",
            headers={"Authorization": f"Bearer {PLATFORM_KEY}"},
            files={"file": ("hook.txt", b"hello", "text/plain")},
            data={"workspace_id": ctx.workspace_a_id},
        )
        if r.status_code not in (200, 201):
            return PhaseResult("webhooks_hmac", Verdict.FAIL,
                               detail=f"trigger upload: {r.status_code}")

        # Poll up to 10s for a delivery.
        deadline = time.time() + 10
        while time.time() < deadline and not catcher.received:
            await asyncio.sleep(0.3)

        if not catcher.received:
            return PhaseResult("webhooks_hmac", Verdict.FAIL,
                               detail="no webhook received within 10s")

        delivery = catcher.received[0]
        sig_header = delivery["headers"].get("X-Signature") or delivery["headers"].get("X-Hub-Signature-256") or ""
        if not sig_header:
            return PhaseResult("webhooks_hmac", Verdict.FAIL,
                               detail=f"no signature header; got headers={list(delivery['headers'])}")

        # Signature format varies — try common shapes:
        #   "t=<ts>,v1=<hmac>"  (Stripe-style)
        #   "sha256=<hmac>"     (GitHub-style)
        body_bytes = delivery["body"].encode()
        ok = False
        if "v1=" in sig_header and "t=" in sig_header:
            parts = dict(p.split("=", 1) for p in sig_header.split(","))
            signed = f"{parts['t']}.{delivery['body']}".encode()
            expected = hmac.new(ctx.webhook_secret.encode(), signed, hashlib.sha256).hexdigest()
            ok = hmac.compare_digest(expected, parts.get("v1", ""))
        elif sig_header.startswith("sha256="):
            expected = hmac.new(ctx.webhook_secret.encode(), body_bytes, hashlib.sha256).hexdigest()
            ok = hmac.compare_digest(expected, sig_header.split("=", 1)[1])
        else:
            expected = hmac.new(ctx.webhook_secret.encode(), body_bytes, hashlib.sha256).hexdigest()
            ok = hmac.compare_digest(expected, sig_header)

        if not ok:
            return PhaseResult("webhooks_hmac", Verdict.FAIL,
                               detail=f"HMAC signature mismatch; header={sig_header[:60]}")
        return PhaseResult("webhooks_hmac", Verdict.PASS,
                           evidence={"sub_id": ctx.webhook_sub_id,
                                     "signature_header": sig_header[:120]})
    finally:
        catcher.stop()


@phase("workspace_isolation")
async def phase_workspace_isolation(ctx: Context) -> PhaseResult:
    """Create a binding in B; assert the binding in A cannot be retrieved via B's scope."""
    # Create a binding in workspace B for contrast.
    r = await ctx.client.post(
        f"{API_BASE_URL}/api/v1/credentials",
        headers=auth_headers(),
        json={
            "workspace_id": ctx.workspace_b_id,
            "kind": "bearer_secret",
            "name": f"iso-{secrets.token_hex(4)}",
            "value": f"sk-iso-{secrets.token_hex(8)}",
        },
    )
    if r.status_code not in (200, 201):
        return PhaseResult("workspace_isolation", Verdict.FAIL,
                           detail=f"create in B: {r.status_code} {r.text[:300]}")
    ctx.binding_b_id = r.json()["id"]

    # Listing workspace A should NOT include B's binding.
    r = await ctx.client.get(
        f"{API_BASE_URL}/api/v1/credentials?workspace_id={ctx.workspace_a_id}",
        headers=auth_headers(),
    )
    if r.status_code != 200:
        return PhaseResult("workspace_isolation", Verdict.FAIL,
                           detail=f"list A: {r.status_code}")
    ids = {b["id"] for b in (r.json() if isinstance(r.json(), list) else r.json().get("items", []))}
    if ctx.binding_b_id in ids:
        return PhaseResult("workspace_isolation", Verdict.FAIL,
                           detail="ISOLATION BREACH: ws A's listing included ws B's binding")
    return PhaseResult("workspace_isolation", Verdict.PASS,
                       evidence={"binding_a_in_a": ctx.binding_a_id in ids,
                                 "binding_b_leaked_to_a": False})


@phase("sessions_alias")
async def phase_sessions_alias(ctx: Context) -> PhaseResult:
    """GET /api/v1/sessions returns same data as /api/v1/tasks + X-Deprecated header."""
    r_tasks = await ctx.client.get(f"{API_BASE_URL}/api/v1/tasks", headers=auth_headers())
    r_sess = await ctx.client.get(f"{API_BASE_URL}/api/v1/sessions", headers=auth_headers())

    if r_sess.status_code != 200:
        return PhaseResult("sessions_alias", Verdict.FAIL,
                           detail=f"/sessions: {r_sess.status_code}")
    if "X-Deprecated" not in r_sess.headers and "x-deprecated" not in r_sess.headers:
        return PhaseResult("sessions_alias", Verdict.FAIL,
                           detail="missing X-Deprecated header on /sessions")
    if r_tasks.status_code == 200 and r_tasks.text != r_sess.text:
        return PhaseResult("sessions_alias", Verdict.FAIL,
                           detail="/sessions body differs from /tasks")
    return PhaseResult("sessions_alias", Verdict.PASS,
                       evidence={"deprecation_header": r_sess.headers.get("X-Deprecated")
                                                      or r_sess.headers.get("x-deprecated")})


@phase("daytona_allocation")
async def phase_daytona_allocation(ctx: Context) -> PhaseResult:
    """Spin up a real Daytona sandbox and run a command inside it.

    Baseline: proves Daytona creds + image work. Required before egress tests.
    """
    try:
        from daytona import Daytona, DaytonaConfig, CreateSandboxFromSnapshotParams
    except ImportError as e:
        return PhaseResult("daytona_allocation", Verdict.SKIP,
                           detail=f"daytona SDK not importable: {e}")

    cfg = DaytonaConfig(api_key=DAYTONA_API_KEY, api_url=DAYTONA_API_URL, target="us")
    d = Daytona(cfg)
    try:
        snapshot = os.environ.get("OMOIOS_SMOKE_SANDBOX_SNAPSHOT", "omoios-omo-vnc")
        params = CreateSandboxFromSnapshotParams(
            snapshot=snapshot,
            labels={"source": "omoios-smoke-test", "run_id": uuid.uuid4().hex},
            env_vars={"SMOKE_TEST": "1"},
        )
        sb = d.create(params)
        ctx.daytona_sandbox_id = getattr(sb, "id", None) or getattr(sb, "sandbox_id", None)
    except Exception as e:
        return PhaseResult("daytona_allocation", Verdict.FAIL,
                           detail=f"sandbox create failed: {e}")

    try:
        result = sb.process.exec("echo hello-from-daytona && curl -s -o /dev/null -w '%{http_code}' https://api.github.com")
        out = getattr(result, "result", "") or getattr(result, "stdout", "")
        if "hello-from-daytona" not in str(out):
            return PhaseResult("daytona_allocation", Verdict.FAIL,
                               detail=f"exec echo failed; stdout={str(out)[:200]}")
        return PhaseResult("daytona_allocation", Verdict.PASS,
                           evidence={"sandbox_id": ctx.daytona_sandbox_id,
                                     "exec_output": str(out)[:300]})
    except Exception as e:
        return PhaseResult("daytona_allocation", Verdict.FAIL,
                           detail=f"exec failed: {e}")


@phase("egress_proxy_wiring")
async def phase_egress_proxy_wiring(ctx: Context) -> PhaseResult:
    """Verify that the Daytona spawner injects HTTPS_PROXY env vars.

    Known gap today: daytona_spawner.py does not set HTTPS_PROXY/NO_PROXY.
    The egress-proxy binary exists but is not wired into the sandbox path.
    Reports GAP until daytona_spawner is patched to inject proxy env vars.
    """
    if not ctx.daytona_sandbox_id:
        return PhaseResult("egress_proxy_wiring", Verdict.SKIP,
                           detail="no sandbox allocated")
    try:
        from daytona import Daytona, DaytonaConfig
        cfg = DaytonaConfig(api_key=DAYTONA_API_KEY, api_url=DAYTONA_API_URL, target="us")
        d = Daytona(cfg)
        sb = d.get(ctx.daytona_sandbox_id)
        result = sb.process.exec("env | grep -E '^(HTTPS_PROXY|HTTP_PROXY|NO_PROXY)=' || echo NOT_SET")
        out = str(getattr(result, "result", "") or getattr(result, "stdout", ""))
        if "NOT_SET" in out:
            return PhaseResult(
                "egress_proxy_wiring", Verdict.GAP,
                detail="HTTPS_PROXY/NO_PROXY not injected into sandbox env — "
                       "daytona_spawner.py needs to set these. Proxy binary exists "
                       "standalone but is not in the sandbox data path.",
                evidence={"env_check": out[:400]})
        return PhaseResult("egress_proxy_wiring", Verdict.PASS,
                           evidence={"proxy_env": out[:400]})
    except Exception as e:
        return PhaseResult("egress_proxy_wiring", Verdict.FAIL,
                           detail=f"env inspect failed: {e}")


@phase("egress_allow_deny")
async def phase_egress_allow_deny(ctx: Context) -> PhaseResult:
    """With HTTPS_PROXY set, an allowed host succeeds and a blocked one returns 451.

    Will SKIP if the proxy isn't wired (prior phase reported GAP).
    """
    if not ctx.daytona_sandbox_id:
        return PhaseResult("egress_allow_deny", Verdict.SKIP, detail="no sandbox")

    try:
        from daytona import Daytona, DaytonaConfig
        cfg = DaytonaConfig(api_key=DAYTONA_API_KEY, api_url=DAYTONA_API_URL, target="us")
        d = Daytona(cfg)
        sb = d.get(ctx.daytona_sandbox_id)

        # Probe: is HTTPS_PROXY set? If not, skip — nothing to verify.
        probe = sb.process.exec("echo $HTTPS_PROXY")
        proxy_val = str(getattr(probe, "result", "") or getattr(probe, "stdout", "")).strip()
        if not proxy_val:
            return PhaseResult(
                "egress_allow_deny", Verdict.SKIP,
                detail="HTTPS_PROXY unset in sandbox; cannot verify allow/deny behavior")

        allowed = sb.process.exec(
            f"curl -s -o /dev/null -w '%{{http_code}}' https://{EGRESS_ALLOWED_HOST}"
        )
        blocked = sb.process.exec(
            f"curl -s -o /dev/null -w '%{{http_code}}' https://{EGRESS_BLOCKED_HOST}"
        )
        a_code = str(getattr(allowed, "result", "") or getattr(allowed, "stdout", "")).strip()
        b_code = str(getattr(blocked, "result", "") or getattr(blocked, "stdout", "")).strip()

        a_ok = a_code.startswith("2") or a_code.startswith("3")
        b_blocked = b_code == "451" or b_code == "000"  # 000 = connection closed
        if a_ok and b_blocked:
            return PhaseResult("egress_allow_deny", Verdict.PASS,
                               evidence={"allowed_host_code": a_code, "blocked_host_code": b_code})
        return PhaseResult("egress_allow_deny", Verdict.FAIL,
                           detail=f"allow={a_code} (expect 2xx/3xx), deny={b_code} (expect 451/000)",
                           evidence={"proxy": proxy_val})
    except Exception as e:
        return PhaseResult("egress_allow_deny", Verdict.FAIL, detail=f"exec failed: {e}")


@phase("opencode_auth_json")
async def phase_opencode_auth_json(ctx: Context) -> PhaseResult:
    """Spec §14: OmO reads ~/.local/share/opencode/auth.json for provider creds.

    Required shape (mode 0600):
        { "<provider>": { "type": "api"|"oauth", "key"|"access": "..." }, ... }

    GitHub Copilot OAuth *requires* this file — env vars cannot substitute.
    Today: bootstrap does not write this file. Broker does not mint short-lived
    OAuth tokens. This is the OmO-specific credential gap.
    """
    if not ctx.daytona_sandbox_id:
        return PhaseResult("opencode_auth_json", Verdict.SKIP, detail="no sandbox")
    try:
        from daytona import Daytona, DaytonaConfig
        cfg = DaytonaConfig(api_key=DAYTONA_API_KEY, api_url=DAYTONA_API_URL, target="us")
        sb = Daytona(cfg).get(ctx.daytona_sandbox_id)

        # Try both root and non-root home locations.
        probe = sb.process.exec(
            "for f in /root/.local/share/opencode/auth.json "
            "$HOME/.local/share/opencode/auth.json; do "
            "  if [ -f \"$f\" ]; then "
            "    echo FOUND:$f:$(stat -c '%a' \"$f\"):$(cat \"$f\" | head -c 500); "
            "    exit 0; "
            "  fi; "
            "done; echo MISSING"
        )
        out = str(getattr(probe, "result", "") or getattr(probe, "stdout", "")).strip()

        if out.startswith("MISSING"):
            return PhaseResult(
                "opencode_auth_json", Verdict.GAP,
                detail="auth.json not written at sandbox boot. "
                       "Need: bootstrap script that calls /broker/creds/<alias> for each "
                       "declared alias and writes the result as auth.json (mode 0600). "
                       "Required for GitHub Copilot OAuth; recommended for all providers.")

        # Parse "FOUND:<path>:<mode>:<first 500 bytes of content>"
        parts = out.split(":", 3)
        path, mode, preview = parts[1], parts[2], parts[3] if len(parts) > 3 else ""
        try:
            parsed = json.loads(preview)
        except json.JSONDecodeError:
            return PhaseResult("opencode_auth_json", Verdict.FAIL,
                               detail=f"auth.json not valid JSON: {preview[:200]}")
        if mode != "600":
            return PhaseResult("opencode_auth_json", Verdict.FAIL,
                               detail=f"auth.json permissions {mode}, expected 600",
                               evidence={"path": path, "providers": list(parsed.keys())})
        if not isinstance(parsed, dict) or not parsed:
            return PhaseResult("opencode_auth_json", Verdict.FAIL,
                               detail="auth.json is empty or not an object")
        # Validate shape: every entry needs a "type" field.
        bad = [k for k, v in parsed.items()
               if not isinstance(v, dict) or "type" not in v]
        if bad:
            return PhaseResult("opencode_auth_json", Verdict.FAIL,
                               detail=f"auth.json entries missing 'type' field: {bad}")
        return PhaseResult("opencode_auth_json", Verdict.PASS,
                           evidence={"path": path, "mode": mode,
                                     "providers": sorted(parsed.keys())})
    except Exception as e:
        return PhaseResult("opencode_auth_json", Verdict.FAIL, detail=f"exec failed: {e}")


@phase("opencode_config")
async def phase_opencode_config(ctx: Context) -> PhaseResult:
    """Spec §14: OmO reads opencode.json for provider/model surface.

    Expected at ~/.config/opencode/opencode.json with `provider` block defining
    each provider (npm package + `{env:VAR}` substitutions). Optional layered
    override: `oh-my-openagent.jsonc` for agent/category routing.

    Today: not written at sandbox boot. Bootstrap needs to render this from
    the environment version's provider definitions.
    """
    if not ctx.daytona_sandbox_id:
        return PhaseResult("opencode_config", Verdict.SKIP, detail="no sandbox")
    try:
        from daytona import Daytona, DaytonaConfig
        cfg = DaytonaConfig(api_key=DAYTONA_API_KEY, api_url=DAYTONA_API_URL, target="us")
        sb = Daytona(cfg).get(ctx.daytona_sandbox_id)

        probe = sb.process.exec(
            "for f in /root/.config/opencode/opencode.json "
            "$HOME/.config/opencode/opencode.json "
            "/root/.config/opencode/oh-my-openagent.jsonc "
            "$HOME/.config/opencode/oh-my-openagent.jsonc; do "
            "  if [ -f \"$f\" ]; then echo \"FOUND:$f\"; fi; "
            "done; echo DONE"
        )
        out = str(getattr(probe, "result", "") or getattr(probe, "stdout", "")).strip()
        found = [line.split(":", 1)[1] for line in out.splitlines()
                 if line.startswith("FOUND:")]
        if not found:
            return PhaseResult(
                "opencode_config", Verdict.GAP,
                detail="opencode.json / oh-my-openagent.jsonc not present. "
                       "Bootstrap must render these from env.credentials + env.tools so "
                       "OmO knows which providers + models + fallback chains to use. "
                       "Without these, OmO has no provider surface and cannot route tasks.")
        return PhaseResult("opencode_config", Verdict.PASS,
                           evidence={"files": found})
    except Exception as e:
        return PhaseResult("opencode_config", Verdict.FAIL, detail=f"exec failed: {e}")


@phase("spec_broker_flow")
async def phase_spec_broker_flow(ctx: Context) -> PhaseResult:
    """Spec §04: sandbox presents sess_tok_... to GET /broker/creds/{alias}.

    Known gap: this endpoint and session-token mechanism are not implemented.
    """
    # Try the spec-compliant endpoint.
    r = await ctx.client.get(
        f"{API_BASE_URL}/broker/creds/anthropic",
        headers={"Authorization": f"Bearer sess_tok_{secrets.token_hex(16)}"},
    )
    if r.status_code == 404:
        return PhaseResult(
            "spec_broker_flow", Verdict.GAP,
            detail="GET /broker/creds/{alias} not implemented. "
                   "Need: (1) sess_tok_... issuance on session create, "
                   "(2) /broker/creds/{alias} endpoint that verifies session token "
                   "and dispatches by env.credentials[alias].kind, "
                   "(3) environment.credentials alias map (currently only env.variables)",
            evidence={"http_code": r.status_code})
    if r.status_code in (401, 403):
        # Endpoint exists but rejected our fake token — partial progress.
        return PhaseResult(
            "spec_broker_flow", Verdict.GAP,
            detail=f"broker endpoint exists (status {r.status_code}) but session-token "
                   "issuance needs to be wired into session create",
            evidence={"http_code": r.status_code, "body": r.text[:300]})
    if r.status_code < 400:
        return PhaseResult("spec_broker_flow", Verdict.PASS,
                           evidence={"body": r.text[:300]})
    return PhaseResult("spec_broker_flow", Verdict.FAIL,
                       detail=f"unexpected status {r.status_code}: {r.text[:200]}")


@phase("spec_event_envelope")
async def phase_spec_event_envelope(ctx: Context) -> PhaseResult:
    """Spec §03: events carry {id, seq, type, session_id, actor, timestamp, data}.

    Known gap: no seq/actor columns on the events table.
    """
    r = await ctx.client.get(f"{API_BASE_URL}/api/v1/tasks?limit=1", headers=auth_headers())
    if r.status_code != 200:
        return PhaseResult("spec_event_envelope", Verdict.SKIP,
                           detail="could not list tasks for event probe")
    tasks = r.json() if isinstance(r.json(), list) else r.json().get("items", [])
    if not tasks:
        return PhaseResult("spec_event_envelope", Verdict.SKIP, detail="no tasks to inspect")
    task_id = tasks[0]["id"]
    r = await ctx.client.get(f"{API_BASE_URL}/api/v1/events?task_id={task_id}&limit=5",
                             headers=auth_headers())
    if r.status_code != 200:
        return PhaseResult("spec_event_envelope", Verdict.GAP,
                           detail=f"events endpoint returned {r.status_code}; "
                                  "spec §03 event envelope not standardized")
    events = r.json() if isinstance(r.json(), list) else r.json().get("items", [])
    if not events:
        return PhaseResult("spec_event_envelope", Verdict.SKIP, detail="no events on task")
    sample = events[0]
    required = {"id", "seq", "type", "actor", "timestamp", "data"}
    missing = required - set(sample.keys())
    if missing:
        return PhaseResult(
            "spec_event_envelope", Verdict.GAP,
            detail=f"event missing spec §03 envelope fields: {sorted(missing)}. "
                   "Need alembic migration adding seq + actor columns, plus "
                   "envelope wrapper at emit time (plan-08 PR-1).",
            evidence={"sample_keys": sorted(sample.keys())})
    return PhaseResult("spec_event_envelope", Verdict.PASS,
                       evidence={"sample_keys": sorted(sample.keys())})


# ─── cleanup ─────────────────────────────────────────────────────────────────

async def cleanup(ctx: Context, keep_sandbox: bool) -> list[str]:
    notes: list[str] = []

    async def _delete(path: str, label: str):
        if not ctx.client:
            return
        try:
            r = await ctx.client.delete(f"{API_BASE_URL}{path}", headers=auth_headers())
            notes.append(f"{label}: {r.status_code}")
        except Exception as e:
            notes.append(f"{label}: {e}")

    if ctx.binding_a_id:
        await _delete(f"/api/v1/credentials/{ctx.binding_a_id}", "del binding_a")
    if ctx.binding_b_id:
        await _delete(f"/api/v1/credentials/{ctx.binding_b_id}", "del binding_b")
    if ctx.webhook_sub_id:
        await _delete(f"/api/v1/webhooks/{ctx.webhook_sub_id}", "del webhook_sub")
    if ctx.artifact_id:
        await _delete(f"/api/v1/artifacts/{ctx.artifact_id}", "del artifact")

    if ctx.daytona_sandbox_id and not keep_sandbox:
        try:
            from daytona import Daytona, DaytonaConfig
            cfg = DaytonaConfig(api_key=DAYTONA_API_KEY, api_url=DAYTONA_API_URL, target="us")
            sb = Daytona(cfg).get(ctx.daytona_sandbox_id)
            sb.delete()
            notes.append(f"sandbox {ctx.daytona_sandbox_id}: deleted")
        except Exception as e:
            notes.append(f"sandbox cleanup: {e}")

    return notes


# ─── runner ──────────────────────────────────────────────────────────────────

async def run(selected: Optional[set[str]], keep_sandbox: bool,
              report_path: Optional[Path]) -> int:
    results: list[PhaseResult] = []
    ctx = Context()
    ctx.client = httpx.AsyncClient(timeout=30.0)

    try:
        for name, fn in PHASES:
            if selected is not None and name not in selected:
                continue
            print(f"  ▸ {name} ...", end=" ", flush=True)
            t0 = time.time()
            try:
                result = await fn(ctx)
            except Exception as e:
                result = PhaseResult(name, Verdict.FAIL, detail=f"exception: {e!r}")
            result.duration_sec = round(time.time() - t0, 2)
            results.append(result)
            marker = {"PASS": "✔", "FAIL": "✖", "GAP": "◇", "SKIP": "—"}[result.verdict.value]
            print(f"{marker} {result.verdict.value} ({result.duration_sec}s) {result.detail[:100]}")

        cleanup_notes = await cleanup(ctx, keep_sandbox)
    finally:
        await ctx.client.aclose()

    # Summary.
    by_verdict = {v.value: sum(1 for r in results if r.verdict == v) for v in Verdict}
    print()
    print(f"  PASS {by_verdict['PASS']}  FAIL {by_verdict['FAIL']}  "
          f"GAP {by_verdict['GAP']}  SKIP {by_verdict['SKIP']}")
    if cleanup_notes:
        print(f"  cleanup: {'; '.join(cleanup_notes)}")

    # Report.
    if report_path:
        report = {
            "api_base_url": API_BASE_URL,
            "run_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "summary": by_verdict,
            "phases": [asdict(r) for r in results],
            "cleanup": cleanup_notes,
        }
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2, default=str))
        print(f"  report: {report_path}")

    return 1 if by_verdict["FAIL"] else 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--only", help="comma-separated phase names to run")
    p.add_argument("--keep-sandbox", action="store_true",
                   help="do not delete the Daytona sandbox on exit")
    p.add_argument("--report", type=Path,
                   default=Path(".sisyphus/evidence/smoke-agent-platform.json"),
                   help="JSON report path")
    args = p.parse_args()

    selected = set(args.only.split(",")) if args.only else None
    if selected:
        known = {n for n, _ in PHASES}
        bad = selected - known
        if bad:
            print(f"unknown phases: {bad}; known: {known}", file=sys.stderr)
            return 2
    return asyncio.run(run(selected, args.keep_sandbox, args.report))


if __name__ == "__main__":
    sys.exit(main())
