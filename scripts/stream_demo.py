"""End-to-end streaming demo: API health → session bootstrap → live TUI.

One command from clean state to an interactive Textual TUI streaming the
full opencode event vocabulary (message.part.delta, session.idle,
permission.asked, file.edited, lsp.client.diagnostics, pty.*, …) into
your terminal.

What it does:

    step 0  hit GET /health on OMOIOS_API_BASE_URL  (must already be up)
    step 1  whoami — verify the API key authenticates
    step 2  workspace find-or-create (poof-life)
    step 3  fireworks credential find-or-create
    step 4  environment find-or-create (poof-kimi)
    step 5  bind env_version alias (fireworks-ai)
    step 6  session.create — fresh chat session
    step 7  exec `omoios sessions connect <SID>` — TUI takes over

Steps 0–6 reuse the existing `scripts/poof/*` probes so resource state
is shared with `just poof-*`. Step 7 hands off to the SDK CLI, which
opens the SSE + WebSocket channels and renders the new event taxonomy.

Usage:

    just stream-demo                        # one-shot, fresh session
    OMOIOS_API_BASE_URL=https://… \\
    OMOIOS_PLATFORM_API_KEY=plat_… \\
        python scripts/stream_demo.py       # explicit env override

Pre-flight failure modes:

    - API down on :18000           → asks the user to start uvicorn
    - missing API key / org id     → points at backend/.env.local
    - probe step fails             → prints PASS/FAIL line + exits non-zero

The script never starts uvicorn itself — that's a foreground process
the user owns (per project memory; uvicorn already runs in the poof
tmux session on most dev machines).
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Awaitable, Callable, Optional

import httpx

REPO = Path(__file__).resolve().parent.parent
for path in (REPO, REPO / "sdk" / "python", REPO / "backend"):
    p = str(path)
    if p not in sys.path:
        sys.path.insert(0, p)

from scripts.poof import (  # noqa: E402
    api_health,
    auth_whoami,
    credential_find_or_create,
    env_version_bind_alias,
    environment_find_or_create,
    session_create,
    workspace_find_or_create,
)
from scripts.poof._client import build_client  # noqa: E402
from scripts.poof._common import (  # noqa: E402
    StepResult,
    load_merged_state,
    print_step,
    save_probe_state,
)


ProbeRun = Callable[[object, dict], Awaitable[StepResult]]


# (step_number, label, probe_module_name, run_fn, needs_client)
_BOOTSTRAP_PROBES: list[tuple[int, str, str, ProbeRun, bool]] = [
    (0, "pre-flight", api_health.PROBE_NAME, api_health.run, False),
    (1, "whoami", auth_whoami.PROBE_NAME, auth_whoami.run, True),
    (
        2,
        "workspace",
        workspace_find_or_create.PROBE_NAME,
        workspace_find_or_create.run,
        True,
    ),
    (
        3,
        "credential",
        credential_find_or_create.PROBE_NAME,
        credential_find_or_create.run,
        True,
    ),
    (
        4,
        "environment",
        environment_find_or_create.PROBE_NAME,
        environment_find_or_create.run,
        True,
    ),
    (
        5,
        "env_version",
        env_version_bind_alias.PROBE_NAME,
        env_version_bind_alias.run,
        True,
    ),
    (6, "session", session_create.PROBE_NAME, session_create.run, True),
]


def _print_banner() -> None:
    print("  ▸ stream-demo: bootstrapping a session, then launching the TUI…")


# ─── credential auto-bootstrap ───────────────────────────────────────────────


_STREAM_DEMO_USER_EMAIL = "streamdemo@local.dev"
# Local-only demo password used to register the stream-demo user against
# a developer's own running uvicorn on :18000. Never reaches production.
_STREAM_DEMO_USER_PASSWORD = "StreamDemo123!ABC"  # pragma: allowlist secret
_STREAM_DEMO_USER_NAME = "Stream Demo"
_STREAM_DEMO_ORG_NAME = "Stream Demo"
_STREAM_DEMO_ORG_SLUG = "stream-demo"
_STREAM_DEMO_KEY_NAME = "stream-demo"
_STREAM_DEMO_CREDS_PATH = REPO / ".sisyphus" / "stream-demo-creds.json"


def _api_base_url() -> str:
    return (os.environ.get("OMOIOS_API_BASE_URL") or "http://localhost:18000").rstrip(
        "/"
    )


def _platform_key_works(key: str) -> bool:
    """Cheap probe: GET /auth/me with the candidate key returns 200?"""
    if not key:
        return False
    try:
        r = httpx.get(
            f"{_api_base_url()}/api/v1/auth/me",
            headers={"Authorization": f"Bearer {key}"},
            timeout=5.0,
        )
    except httpx.HTTPError:
        return False
    if r.status_code == 500 and "shutting down" in r.text.lower():
        # The API itself is up but its Postgres dependency is unavailable.
        # Treat this as a probe failure — the user needs to fix their DB
        # before any of the probes will pass.
        raise RuntimeError(
            "postgres is rejecting connections (API returned 500 with "
            "'database system is shutting down'). Fix: "
            "`brew services restart postgresql@16` or check the postmaster "
            "log at /opt/homebrew/var/log/postgresql@16.log"
        )
    return r.status_code == 200


def _try_login(http: httpx.Client) -> Optional[str]:
    """Return a JWT for the stream-demo user, or None."""
    r = http.post(
        f"{_api_base_url()}/api/v1/auth/login",
        json={
            "email": _STREAM_DEMO_USER_EMAIL,
            "password": _STREAM_DEMO_USER_PASSWORD,
        },
    )
    if r.status_code != 200:
        return None
    return r.json().get("access_token")


def _ensure_user(http: httpx.Client) -> str:
    """Find-or-create the stream-demo user; return a fresh JWT."""
    jwt = _try_login(http)
    if jwt:
        return jwt
    r = http.post(
        f"{_api_base_url()}/api/v1/auth/register",
        json={
            "email": _STREAM_DEMO_USER_EMAIL,
            "password": _STREAM_DEMO_USER_PASSWORD,
            "display_name": _STREAM_DEMO_USER_NAME,
        },
    )
    # 200/201 = created; 409/400 = already exists; either way try login next.
    jwt = _try_login(http)
    if not jwt:
        raise RuntimeError(
            f"could not log in as {_STREAM_DEMO_USER_EMAIL} after register "
            f"(register={r.status_code}: {r.text[:200]})"
        )
    return jwt


def _ensure_org(http: httpx.Client, jwt: str) -> str:
    """Find-or-create the stream-demo org; return its UUID."""
    r = http.get(
        f"{_api_base_url()}/api/v1/organizations",
        headers={"Authorization": f"Bearer {jwt}"},
    )
    r.raise_for_status()
    for org in r.json() or []:
        if org.get("slug") == _STREAM_DEMO_ORG_SLUG:
            return org["id"]
    create = http.post(
        f"{_api_base_url()}/api/v1/organizations",
        headers={"Authorization": f"Bearer {jwt}"},
        json={"name": _STREAM_DEMO_ORG_NAME, "slug": _STREAM_DEMO_ORG_SLUG},
    )
    create.raise_for_status()
    return create.json()["id"]


def _mint_api_key(http: httpx.Client, jwt: str, org_id: str) -> str:
    """Mint a fresh platform API key. Always create a new one — old keys
    can't be re-read since they're hashed at rest."""
    r = http.post(
        f"{_api_base_url()}/api/v1/auth/api-keys",
        headers={"Authorization": f"Bearer {jwt}"},
        json={
            "name": f"{_STREAM_DEMO_KEY_NAME}-{int(time.time())}",
            "scopes": [],
            "organization_id": org_id,
        },
    )
    r.raise_for_status()
    return r.json()["key"]


def _save_creds(*, api_key: str, org_id: str, jwt: str) -> None:
    """Persist creds so re-runs reuse them instead of minting new keys."""
    _STREAM_DEMO_CREDS_PATH.parent.mkdir(parents=True, exist_ok=True)
    _STREAM_DEMO_CREDS_PATH.write_text(
        json.dumps(
            {
                "api_key": api_key,
                "org_id": org_id,
                "jwt": jwt,
                "minted_at": int(time.time()),
            },
            indent=2,
        )
    )


def _load_cached_creds() -> Optional[dict]:
    if not _STREAM_DEMO_CREDS_PATH.exists():
        return None
    try:
        return json.loads(_STREAM_DEMO_CREDS_PATH.read_text())
    except json.JSONDecodeError:
        return None


def _ensure_local_credentials() -> None:
    """Make sure OMOIOS_PLATFORM_API_KEY + OMOIOS_TEST_ORG_ID are set
    AND that the key actually works against the running API.

    Fast path: env already has a working key → no-op.
    Cached path: re-use creds from .sisyphus/stream-demo-creds.json
        if the key still authenticates.
    Slow path: register/login the stream-demo user, find-or-create the
        org, mint a fresh key, persist + export.

    Side effect: poof's lru_cache around get_settings is reset so the
    new env values get picked up by the probe chain.
    """
    base = _api_base_url()
    print(f"  · ensuring credentials for {base}")

    cur_key = os.environ.get("OMOIOS_PLATFORM_API_KEY", "")
    cur_org = os.environ.get("OMOIOS_TEST_ORG_ID", "")
    if cur_key and cur_org and _platform_key_works(cur_key):
        print(f"    ✓ env key works   ({cur_key[:18]}…)")
        return

    cached = _load_cached_creds()
    if cached:
        cached_key = cached.get("api_key", "")
        cached_org = cached.get("org_id", "")
        if cached_key and cached_org and _platform_key_works(cached_key):
            os.environ["OMOIOS_PLATFORM_API_KEY"] = cached_key
            os.environ["OMOIOS_TEST_ORG_ID"] = cached_org
            # Refresh the user JWT — access tokens expire after 15 min
            # and the WS handler requires a *user* token (not the API key).
            with httpx.Client(timeout=10.0) as http:
                fresh_jwt = _try_login(http)
            if fresh_jwt:
                cached["jwt"] = fresh_jwt
                _save_creds(api_key=cached_key, org_id=cached_org, jwt=fresh_jwt)
            print(f"    ✓ cached key works  ({cached_key[:18]}…)")
            _reset_poof_settings_cache()
            return

    print("    · minting fresh credentials…")
    with httpx.Client(timeout=15.0) as http:
        jwt = _ensure_user(http)
        org_id = _ensure_org(http, jwt)
        api_key = _mint_api_key(http, jwt, org_id)
    os.environ["OMOIOS_PLATFORM_API_KEY"] = api_key
    os.environ["OMOIOS_TEST_ORG_ID"] = org_id
    _save_creds(api_key=api_key, org_id=org_id, jwt=jwt)
    print(f"    ✓ minted key    ({api_key[:18]}…)")
    print(f"    ✓ org_id        {org_id}")
    print(f"    ▸ persisted to  {_STREAM_DEMO_CREDS_PATH.relative_to(REPO)}")
    _reset_poof_settings_cache()


def _reset_poof_settings_cache() -> None:
    """Drop the cached PoofSettings so probes pick up the new env."""
    try:
        from scripts.poof._settings import reset_settings_cache

        reset_settings_cache()
    except Exception:  # noqa: BLE001
        pass


def _print_handoff(session_id: str) -> None:
    print()
    print(f"  ✓ session ready: {session_id}")
    print("  ▸ launching omoios sessions connect — Ctrl+C / Ctrl+Q to exit")
    print()


async def _bootstrap_session() -> Optional[str]:
    """Run probes 0-6 and return the freshly-minted session_id, or None.

    Side-effect: per-probe state is cached under .sisyphus/poof-state/
    so subsequent `just poof-*` runs re-use the same workspace/env.
    """
    state = load_merged_state([p[2] for p in _BOOTSTRAP_PROBES])

    # Step 0 (health) doesn't need the SDK client.
    pre = _BOOTSTRAP_PROBES[0]
    pre_result = await pre[3](None, state)
    print_step(pre[0], pre[1], pre_result)
    if pre_result.status != "PASS":
        return None

    async with build_client() as client:
        for step_num, label, _probe_name, run_fn, _needs_client in _BOOTSTRAP_PROBES[
            1:
        ]:
            result = await run_fn(client, state)
            print_step(step_num, label, result)
            if result.status != "PASS":
                return None

    sid = state.get("session_id")
    if not isinstance(sid, str) or not sid:
        return None
    save_probe_state("stream_demo", {"session_id": sid})
    return sid


def _launch_tui(session_id: str) -> int:
    """Hand off to `omoios sessions connect <SID>`.

    Uses ``os.execvp`` so the TUI inherits our terminal directly (no
    nested Python → subprocess buffering). The poof env (OMOIOS_API_BASE_URL,
    OMOIOS_PLATFORM_API_KEY) already lives in the process env after
    `_load_env_file` was called via `get_settings`.

    Also exports OMOIOS_USER_JWT from the cached credentials so the
    multiplayer WebSocket (`/api/v1/sessions/<id>/ws`) can authenticate.
    Without it the server returns close code 4401 ("Authentication
    required") right after handshake and the TUI sees REMOTE_CLOSING
    on every send.

    Three launch paths, tried in order:

      1. ``omoios`` console script on $PATH — the happy path when the
         SDK is installed in the active venv.
      2. ``python -m omoios.cli`` — falls back to a module run when the
         binary isn't on $PATH but the package is importable.
      3. error — neither found; the user needs to install the SDK.
    """
    import shutil

    # Pull the user JWT out of the cached creds so the TUI's per-session
    # WebSocket can authenticate. The platform API key is enough for HTTP
    # routes but the WS handler verifies a USER access token specifically.
    cached = _load_cached_creds() or {}
    jwt = cached.get("jwt")
    if isinstance(jwt, str) and jwt:
        os.environ["OMOIOS_USER_JWT"] = jwt

    omoios_bin = shutil.which("omoios")
    if omoios_bin:
        cmd = [omoios_bin, "sessions", "connect", session_id]
    else:
        try:
            import omoios.cli  # noqa: F401
        except ImportError:
            print(
                "  ✗ omoios SDK not available — install with:\n"
                "    uv pip install --editable sdk/python\n"
                "    or run via:  uv run --with-editable sdk/python "
                "omoios sessions connect " + session_id,
                file=sys.stderr,
            )
            return 127
        cmd = [sys.executable, "-m", "omoios.cli", "sessions", "connect", session_id]

    _print_handoff(session_id)
    try:
        os.execvp(cmd[0], cmd)
    except FileNotFoundError as exc:
        print(f"  ✗ {cmd[0]} not on PATH: {exc}", file=sys.stderr)
        return 127


async def _run(launch_tui: bool) -> int:
    _print_banner()
    try:
        _ensure_local_credentials()
    except Exception as exc:  # noqa: BLE001
        print(
            f"\n  ✗ credential bootstrap failed: {type(exc).__name__}: {exc}\n"
            "    is the API up on :18000? `tmux attach -t poof` (window 0)",
            file=sys.stderr,
        )
        return 1
    sid = await _bootstrap_session()
    if sid is None:
        print(
            "\n  ✗ bootstrap failed — see PASS/FAIL above.\n"
            "    common fixes:\n"
            "      • API down on :18000  → tmux attach -t poof  (window 0)\n"
            "      • missing creds        → check backend/.env.local\n"
            "      • stale state          → just stream-demo-fresh",
            file=sys.stderr,
        )
        return 1
    if not launch_tui:
        print(f"\n  ✓ session bootstrapped (--no-tui): {sid}")
        return 0
    return _launch_tui(sid)  # never returns on success — execvp replaces us


def main() -> int:
    # Tiny manual flag parser — argparse pulls in I/O latency we don't need.
    launch_tui = "--no-tui" not in sys.argv[1:]
    try:
        return asyncio.run(_run(launch_tui=launch_tui))
    except KeyboardInterrupt:
        print("\n  · interrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
