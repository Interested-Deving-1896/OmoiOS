"""Tail a single OmoiOS session's envelope stream in the terminal.

Primary transport is the per-session WebSocket
(`/api/v1/sessions/{id}/ws`); falls back to SSE
(`/api/v1/sessions/{id}/events`) when the WS handshake fails twice in a
row, or when invoked with `--sse`.

Renders three lanes (filterable via `--show`):

- **chat**       — what the user reads as a conversation
- **lifecycle**  — agent health, errors, handoffs
- **system**     — sandbox, guardian, memory, coordination, spec, ticket

Streaming events are coalesced in place using carriage returns:

- `agent.text_delta`         → buffered per turn_id
- `agent.thinking_delta`     → buffered per turn_id (separate stream)
- `agent.tool_input_delta`   → buffered per tool_call_id (drafting tool args)
- `agent.tool_result_delta`  → buffered per tool_call_id (long stdout)
- `agent.plan_delta`         → applied to the live plan view

Usage:
    python -m omoi_os.cli.session_tail <SESSION_ID>
    python -m omoi_os.cli.session_tail <SESSION_ID> --sse
    python -m omoi_os.cli.session_tail <SESSION_ID> --raw
    python -m omoi_os.cli.session_tail <SESSION_ID> --since 42
    python -m omoi_os.cli.session_tail <SESSION_ID> --types 'agent.*'
    python -m omoi_os.cli.session_tail <SESSION_ID> --show chat,lifecycle
    python -m omoi_os.cli.session_tail <SESSION_ID> --base-url http://localhost:18000
"""

from __future__ import annotations

import argparse
import asyncio
import fnmatch
import json
import os
import random
import signal
import sys
from typing import Any, Optional
from urllib.parse import urlencode, urlparse, urlunparse

from omoi_os.cli.event_format import (
    COLORS,
    LANE_CHAT,
    LANE_LIFECYCLE,
    LANE_SYSTEM,
    color_for,
    format_event_json,
    format_timestamp,
    icon_for,
    lane_for,
)


DEFAULT_BASE_URL = os.environ.get("OMOIOS_API_URL", "http://localhost:18000")
ALL_LANES = (LANE_CHAT, LANE_LIFECYCLE, LANE_SYSTEM)


# ---------------------------------------------------------------------------
# Offline demo stream — exercises every renderer path without API/Redis
# ---------------------------------------------------------------------------


async def _demo_stream(rate: float):  # type: ignore[no-untyped-def]
    """Yield scripted envelopes with realistic timing — no network needed.

    Drives every code path: assistant_message, thinking_delta, plan_created,
    plan_updated, text_delta, tool_input_delta, tool_use, tool_result_delta,
    tool_result, skill_invoked, subagent_invoked, sandbox.spawned,
    guardian.steering.intervention, session.completed.
    """
    import uuid as _uuid
    from datetime import datetime as _dt
    from datetime import timezone as _tz

    seq = 0
    turn_id = f"turn_{_uuid.uuid4().hex[:6]}"
    plan_id = f"plan_{_uuid.uuid4().hex[:6]}"
    tool_call_id = f"tc_{_uuid.uuid4().hex[:6]}"

    def env(event_type: str, data: dict[str, Any]) -> dict[str, Any]:
        nonlocal seq
        seq += 1
        return {
            "id": _uuid.uuid4().hex,
            "seq": seq,
            "type": event_type,
            "session_id": "demo",
            "actor": "agent",
            "timestamp": _dt.now(_tz.utc).isoformat(),
            "data": data,
        }

    yield env("session.created", {"reason": "offline demo"})
    await asyncio.sleep(rate * 4)

    yield env(
        "agent.assistant_message",
        {
            "turn_id": turn_id,
            "turn": 1,
            "model": "claude-sonnet-4-6",
            "stop_reason": None,
            "block_count": 4,
        },
    )
    await asyncio.sleep(rate * 2)

    # Streaming thinking
    for i, w in enumerate("Let me list the repo, then look at the backend.".split(" ")):
        yield env(
            "agent.thinking_delta",
            {
                "turn_id": turn_id,
                "index": i,
                "text": (w if i == 0 else " " + w),
            },
        )
        await asyncio.sleep(rate)
    await asyncio.sleep(rate * 3)

    # Plan
    yield env(
        "agent.plan_created",
        {
            "turn_id": turn_id,
            "plan_id": plan_id,
            "title": "Explore repo",
            "steps": [
                {"id": "s1", "text": "List top-level dirs", "status": "pending"},
                {"id": "s2", "text": "Skim backend/", "status": "pending"},
                {"id": "s3", "text": "Report findings", "status": "pending"},
            ],
        },
    )
    await asyncio.sleep(rate * 4)
    yield env(
        "agent.plan_updated",
        {
            "plan_id": plan_id,
            "step_id": "s1",
            "status": "in_progress",
        },
    )
    await asyncio.sleep(rate * 2)

    # Streaming text reply
    reply = "I'll start by listing the repo to see what we're working with."
    for i, tok in enumerate(reply.split(" ")):
        yield env(
            "agent.text_delta",
            {
                "turn_id": turn_id,
                "index": i,
                "text": (tok if i == 0 else " " + tok),
            },
        )
        await asyncio.sleep(rate)
    await asyncio.sleep(rate * 2)

    # Streaming tool input JSON
    for piece in ['{"command":', ' "ls', ' -la"', "}"]:
        yield env(
            "agent.tool_input_delta",
            {
                "turn_id": turn_id,
                "tool_call_id": tool_call_id,
                "partial_json": piece,
            },
        )
        await asyncio.sleep(rate * 2)
    await asyncio.sleep(rate * 2)

    yield env(
        "agent.tool_use",
        {
            "turn_id": turn_id,
            "tool_call_id": tool_call_id,
            "name": "Bash",
            "input": {"command": "ls -la"},
        },
    )
    await asyncio.sleep(rate * 3)

    # Streaming tool result
    for c in ["CLAUDE.md\n", "backend\n", "frontend\n", "scripts\n", "subsystems\n"]:
        yield env(
            "agent.tool_result_delta",
            {
                "tool_call_id": tool_call_id,
                "chunk": c,
                "eof": False,
            },
        )
        await asyncio.sleep(rate * 2)
    yield env(
        "agent.tool_result",
        {
            "tool_call_id": tool_call_id,
            "ok": True,
            "output": "CLAUDE.md\nbackend\nfrontend\nscripts\nsubsystems",
            "duration_ms": 412,
        },
    )
    await asyncio.sleep(rate * 3)

    yield env(
        "agent.plan_updated",
        {
            "plan_id": plan_id,
            "step_id": "s1",
            "status": "completed",
        },
    )
    yield env(
        "agent.plan_updated",
        {
            "plan_id": plan_id,
            "step_id": "s2",
            "status": "in_progress",
        },
    )
    await asyncio.sleep(rate * 2)

    # Skill invocation
    yield env(
        "agent.skill_invoked",
        {
            "turn_id": turn_id,
            "tool": "Skill",
            "skill_name": "naming-conventions",
            "input": {"args": "verify backend service names"},
        },
    )
    await asyncio.sleep(rate * 4)
    yield env(
        "agent.skill_completed",
        {
            "skill_name": "naming-conventions",
            "ok": True,
            "duration_ms": 220,
        },
    )
    await asyncio.sleep(rate * 2)

    # Subagent
    yield env(
        "agent.subagent_invoked",
        {
            "turn_id": turn_id,
            "tool": "Task",
            "subagent_type": "Explore",
            "subagent_description": "Map backend/omoi_os/services structure",
            "subagent_prompt": "List the modules under services/.",
        },
    )
    await asyncio.sleep(rate * 4)
    yield env(
        "agent.subagent_completed",
        {
            "subagent_type": "Explore",
            "ok": True,
            "duration_ms": 1840,
        },
    )
    await asyncio.sleep(rate * 2)

    # System lane noise (will only render if --show includes system)
    yield env("sandbox.spawned", {"sandbox_id": "sb_demo01", "provider": "modal"})
    await asyncio.sleep(rate * 2)
    yield env(
        "guardian.steering.intervention",
        {
            "guidance": "Consider re-running the test suite after the rename.",
        },
    )
    await asyncio.sleep(rate * 2)

    # Lifecycle noise (only renders if --show includes lifecycle)
    yield env("agent.heartbeat", {"agent_id": "ag_demo"})
    await asyncio.sleep(rate)

    # Final follow-up text
    follow = "Three top-level directories. Backend has 12 services. Done."
    for i, tok in enumerate(follow.split(" ")):
        yield env(
            "agent.text_delta",
            {
                "turn_id": turn_id,
                "index": 100 + i,
                "text": (tok if i == 0 else " " + tok),
            },
        )
        await asyncio.sleep(rate)
    await asyncio.sleep(rate * 2)

    yield env(
        "agent.plan_updated",
        {
            "plan_id": plan_id,
            "step_id": "s2",
            "status": "completed",
        },
    )
    yield env(
        "agent.plan_updated",
        {
            "plan_id": plan_id,
            "step_id": "s3",
            "status": "completed",
            "note": "summary delivered",
        },
    )
    yield env("agent.turn_complete", {"turn_id": turn_id})
    await asyncio.sleep(rate * 2)
    yield env("session.completed", {"reason": "demo done"})


def _matches(event_type: str, patterns: list[str]) -> bool:
    if not patterns:
        return True
    return any(fnmatch.fnmatch(event_type, p) for p in patterns)


def _truncate(s: str, n: int) -> str:
    return s if len(s) <= n else s[: n - 3] + "..."


# ---------------------------------------------------------------------------
# Streaming buffers
# ---------------------------------------------------------------------------


class StreamRenderer:
    """Coalesces multiple in-flight delta streams into in-place redraws.

    Streams are keyed by `(kind, key)` tuples — e.g. ("text", turn_id) or
    ("thinking", turn_id) or ("tool_input", tool_call_id). At most one
    stream is "live" at a time; switching streams flushes the previous one
    with a newline.
    """

    def __init__(self) -> None:
        self._buffers: dict[tuple[str, str], str] = {}
        self._live: Optional[tuple[str, str]] = None

    def _flush_live(self) -> None:
        if self._live is not None:
            sys.stdout.write("\n")
            sys.stdout.flush()
            # Once the line is committed to scroll-back, drop its buffer so
            # a future delta with the same key starts a fresh line. This
            # matches user expectation: "the previous message is done".
            self._buffers.pop(self._live, None)
        self._live = None

    def _redraw(
        self, kind: str, key: str, body: str, prefix_label: str, color: str
    ) -> None:
        slot = (kind, key)
        if self._live is not None and self._live != slot:
            self._flush_live()
        self._buffers[slot] = body
        ts = format_timestamp(None)
        dim = COLORS["dim"]
        reset = COLORS["reset"]
        line = f"{dim}[{ts}]{reset} {color}{prefix_label}{reset} {body}"
        sys.stdout.write("\r\033[K" + line)
        sys.stdout.flush()
        self._live = slot

    # --- public stream APIs ---

    def append_text(self, turn_id: str, text: str) -> None:
        slot = ("text", turn_id)
        prev = self._buffers.get(slot, "")
        self._redraw("text", turn_id, prev + text, "💬", COLORS["reset"])

    def append_thinking(self, turn_id: str, text: str) -> None:
        slot = ("thinking", turn_id)
        prev = self._buffers.get(slot, "")
        merged = prev + text
        # Italic-ish: dim color carries through the body so it visually
        # separates from regular text_delta output.
        self._redraw(
            "thinking",
            turn_id,
            COLORS["dim"] + merged + COLORS["reset"],
            "💭",
            COLORS["dim"],
        )
        self._buffers[slot] = merged

    def append_tool_input(self, tool_call_id: str, partial_json: str) -> None:
        slot = ("tool_input", tool_call_id)
        prev = self._buffers.get(slot, "")
        merged = prev + partial_json
        # Truncate display so very long JSON doesn't wrap nightmares.
        body = _truncate(merged, 160)
        self._redraw(
            "tool_input",
            tool_call_id,
            body,
            f"🔧 (drafting {tool_call_id[-6:]})",
            COLORS["cyan"],
        )
        self._buffers[slot] = merged

    def append_tool_result(self, tool_call_id: str, chunk: str, eof: bool) -> None:
        slot = ("tool_result", tool_call_id)
        prev = self._buffers.get(slot, "")
        merged = prev + chunk
        # For result streams, only show the tail (last line) — the line
        # itself can be huge.
        last = merged.splitlines()[-1] if merged else ""
        body = _truncate(last, 160)
        self._redraw(
            "tool_result",
            tool_call_id,
            body,
            f"↳ ({tool_call_id[-6:]})",
            COLORS["dim"],
        )
        self._buffers[slot] = merged
        if eof:
            self._flush_live()
            self._buffers.pop(slot, None)

    def flush_for_other_event(self) -> None:
        self._flush_live()


# ---------------------------------------------------------------------------
# Plan tracker
# ---------------------------------------------------------------------------


class PlanTracker:
    """Tracks the latest plan + step states per plan_id and renders them."""

    STATUS_GLYPH = {
        "pending": "○",
        "in_progress": "◐",
        "completed": "●",
        "skipped": "⊘",
        "failed": "✗",
    }
    STATUS_COLOR = {
        "pending": "dim",
        "in_progress": "yellow",
        "completed": "green",
        "skipped": "dim",
        "failed": "red",
    }

    def __init__(self) -> None:
        # plan_id → {"title": str, "steps": [{"id","text","status"}]}
        self._plans: dict[str, dict[str, Any]] = {}

    def upsert(self, plan_id: str, title: str, steps: list[dict[str, Any]]) -> str:
        steps_norm = [
            {
                "id": s.get("id") or f"s{i}",
                "text": s.get("text") or "",
                "status": s.get("status") or "pending",
            }
            for i, s in enumerate(steps or [])
        ]
        self._plans[plan_id] = {"title": title or "", "steps": steps_norm}
        return self._render_plan(plan_id, header="🗺️  plan")

    def update_step(
        self, plan_id: str, step_id: str, status: str, note: Optional[str]
    ) -> Optional[str]:
        plan = self._plans.get(plan_id)
        if not plan:
            return None
        for s in plan["steps"]:
            if s["id"] == step_id:
                s["status"] = status
                if note:
                    s["note"] = note
                break
        return self._render_plan(plan_id, header=f"🗺️  plan ({step_id} → {status})")

    def append_step(self, plan_id: str, step_id: str, text: str) -> Optional[str]:
        plan = self._plans.setdefault(plan_id, {"title": "", "steps": []})
        for s in plan["steps"]:
            if s["id"] == step_id:
                s["text"] += text
                return self._render_plan(plan_id, header="🗺️  plan (streaming)")
        plan["steps"].append({"id": step_id, "text": text, "status": "pending"})
        return self._render_plan(plan_id, header="🗺️  plan (streaming)")

    def _render_plan(self, plan_id: str, header: str) -> str:
        plan = self._plans[plan_id]
        reset = COLORS["reset"]
        dim = COLORS["dim"]
        ts = format_timestamp(None)
        lines = [
            f"{dim}[{ts}]{reset} {header}{(': ' + plan['title']) if plan['title'] else ''}"
        ]
        for s in plan["steps"]:
            status = s["status"]
            glyph = self.STATUS_GLYPH.get(status, "·")
            cname = self.STATUS_COLOR.get(status, "reset")
            color = COLORS.get(cname, "")
            text = s["text"]
            if status == "completed":
                text = f"{COLORS['dim']}{text}{reset}"
            note = f"  {dim}— {s.get('note')}{reset}" if s.get("note") else ""
            lines.append(f"   {color}{glyph}{reset} {text}{note}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Per-event renderers
# ---------------------------------------------------------------------------


def _format_other_event(env: dict[str, Any]) -> Optional[str]:
    """Render a non-streaming, non-plan envelope as one line. None to skip."""
    event_type = env.get("type") or env.get("event_type") or "unknown"

    ts = format_timestamp(env.get("timestamp"))
    icon = icon_for(event_type)
    color = color_for(event_type)
    reset = COLORS["reset"]
    dim = COLORS["dim"]

    data = env.get("data") or {}
    detail = ""

    if event_type == "agent.tool_use":
        name = data.get("name") or data.get("tool", "?")
        inp = data.get("input") or {}
        if isinstance(inp, dict) and "command" in inp:
            detail = f"{name}  $ {inp['command']}"
        else:
            preview = json.dumps(inp, default=str)
            detail = f"{name}  {_truncate(preview, 100)}"
    elif event_type in (
        "agent.tool_result",
        "agent.tool_completed",
        "agent.user_tool_result",
    ):
        ok = data.get("ok", True)
        dur = data.get("duration_ms")
        out = data.get("output") or data.get("result") or ""
        if isinstance(out, (dict, list)):
            out = json.dumps(out, default=str)
        first = out.splitlines()[0] if out else ""
        status = "ok" if ok else "fail"
        dur_s = f" ({dur}ms)" if dur is not None else ""
        detail = f"{status}{dur_s}  {_truncate(first, 100)}"
    elif event_type == "agent.command_started":
        detail = f"$ {data.get('command', '')}"
    elif event_type == "agent.command_completed":
        rc = data.get("exit_code", data.get("returncode"))
        detail = f"exit={rc}  {_truncate(data.get('stdout_tail', ''), 80)}"
    elif event_type in ("agent.file_written", "agent.file_edited"):
        detail = data.get("path", "")
    elif event_type == "agent.skill_invoked":
        detail = f"{data.get('skill_name', '?')}  {_truncate(json.dumps(data.get('input') or {}, default=str), 80)}"
    elif event_type == "agent.skill_completed":
        detail = f"{data.get('skill_name', '?')}  ok={data.get('ok', True)}"
    elif event_type == "agent.subagent_invoked":
        st = data.get("subagent_type") or "?"
        desc = data.get("subagent_description") or ""
        detail = f"{st}  {_truncate(desc, 80)}"
    elif event_type == "agent.subagent_completed":
        detail = f"{data.get('subagent_type', '?')}  ok={data.get('ok', True)}"
    elif event_type == "agent.assistant_message":
        detail = (
            f"turn={data.get('turn', '?')} model={data.get('model', '?')} "
            f"stop={data.get('stop_reason', '?')} blocks={data.get('block_count', '?')}"
        )
    elif event_type == "agent.user_message":
        detail = _truncate(data.get("text", "") or data.get("content", ""), 200)
    elif event_type == "agent.thinking":
        detail = _truncate(data.get("content") or data.get("text") or "thinking…", 200)
    elif event_type == "session.message":
        detail = _truncate(data.get("text", ""), 200)
    elif event_type in (
        "session.failed",
        "agent.error",
        "agent.stream_error",
        "agent.failed",
    ):
        detail = _truncate(str(data.get("error") or data.get("message") or ""), 200)
    elif event_type == "agent.handoff.requested":
        detail = f"to={data.get('to_agent', '?')}  reason={_truncate(data.get('reason', ''), 80)}"
    elif event_type == "guardian.steering.intervention":
        detail = _truncate(data.get("guidance") or data.get("reason", ""), 160)
    elif event_type == "sandbox.spawned":
        detail = (
            f"id={data.get('sandbox_id', '?')}  provider={data.get('provider', '?')}"
        )
    elif event_type == "memory.context.suggested":
        detail = _truncate(data.get("summary", ""), 160)
    elif event_type == "orchestrator.dry_run.decision":
        sel = data.get("selected_task") or {}
        detail = f"task={sel.get('task_id', '')[:8]} type={sel.get('task_type', '')}"
    elif event_type.startswith("spec."):
        if "phase" in data:
            detail = f"phase={data['phase']}"
        elif "title" in data:
            detail = _truncate(data["title"], 120)
        elif data:
            detail = _truncate(json.dumps(data, default=str), 120)
    elif event_type.startswith("ticket."):
        detail = f"ticket={data.get('ticket_id', '?')[:8]} {data.get('to_status') or data.get('to_phase') or ''}"
    elif data:
        detail = _truncate(json.dumps(data, default=str), 100)

    seq = env.get("seq")
    seq_s = f"{dim}#{seq}{reset} " if seq is not None else ""
    icon_s = f"{icon} " if icon else ""
    return f"{dim}[{ts}]{reset} {seq_s}{icon_s}{color}{event_type}{reset}  {detail}".rstrip()


# ---------------------------------------------------------------------------
# Main tail
# ---------------------------------------------------------------------------


class SessionTail:
    def __init__(
        self,
        session_id: str,
        base_url: str,
        token: Optional[str],
        force_sse: bool,
        raw: bool,
        since: Optional[int],
        type_filters: list[str],
        lanes: set[str],
    ) -> None:
        self.session_id = session_id
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.force_sse = force_sse
        self.raw = raw
        self.since = since
        self.type_filters = type_filters
        self.lanes = lanes
        self.streams = StreamRenderer()
        self.plans = PlanTracker()
        self.last_seq: Optional[int] = since
        self.ws_failures = 0
        self._stop = asyncio.Event()

    # ----- discovery -----

    async def _discover_urls(self) -> dict[str, str]:
        try:
            import httpx
        except ImportError as e:  # pragma: no cover
            raise SystemExit(f"httpx required: {e}")

        url = f"{self.base_url}/api/v1/sessions/{self.session_id}"
        headers = {}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.get(url, headers=headers)
                if r.status_code == 200:
                    body = r.json()
                    return {
                        "websocket": body.get("websocket") or self._fallback_ws_url(),
                        "events_sse": body.get("events_sse")
                        or self._fallback_sse_url(),
                    }
        except Exception as e:
            print(
                f"{COLORS['dim']}discovery failed ({e}); using convention{COLORS['reset']}",
                file=sys.stderr,
            )
        return {
            "websocket": self._fallback_ws_url(),
            "events_sse": self._fallback_sse_url(),
        }

    def _fallback_ws_url(self) -> str:
        p = urlparse(self.base_url)
        scheme = "wss" if p.scheme == "https" else "ws"
        return urlunparse(
            (scheme, p.netloc, f"/api/v1/sessions/{self.session_id}/ws", "", "", "")
        )

    def _fallback_sse_url(self) -> str:
        return f"{self.base_url}/api/v1/sessions/{self.session_id}/events"

    # ----- output -----

    def _render_envelope(self, env: dict[str, Any]) -> None:
        event_type = env.get("type") or env.get("event_type") or ""
        if not _matches(event_type, self.type_filters):
            return
        if lane_for(event_type) not in self.lanes:
            return

        seq = env.get("seq")
        if isinstance(seq, int):
            self.last_seq = seq

        if self.raw:
            self.streams.flush_for_other_event()
            print(format_event_json(env), flush=True)
            return

        data = env.get("data") or {}

        # ---- streaming events: redraw in place ----
        if event_type == "agent.text_delta":
            self.streams.append_text(
                data.get("turn_id", "default"), data.get("text", "")
            )
            return
        if event_type == "agent.thinking_delta":
            self.streams.append_thinking(
                data.get("turn_id", "default"), data.get("text", "")
            )
            return
        if event_type == "agent.tool_input_delta":
            self.streams.append_tool_input(
                data.get("tool_call_id", "default"),
                data.get("partial_json", ""),
            )
            return
        if event_type == "agent.tool_result_delta":
            self.streams.append_tool_result(
                data.get("tool_call_id", "default"),
                data.get("chunk", ""),
                bool(data.get("eof", False)),
            )
            return

        # Any non-stream event flushes the live delta line first.
        self.streams.flush_for_other_event()

        # ---- plan events ----
        if event_type == "agent.plan_created":
            line = self.plans.upsert(
                plan_id=data.get("plan_id", "default"),
                title=data.get("title", ""),
                steps=data.get("steps", []),
            )
            print(line, flush=True)
            return
        if event_type == "agent.plan_updated":
            line = self.plans.update_step(
                plan_id=data.get("plan_id", "default"),
                step_id=data.get("step_id", ""),
                status=data.get("status", "pending"),
                note=data.get("note"),
            )
            if line:
                print(line, flush=True)
            return
        if event_type == "agent.plan_delta":
            op = data.get("op", "append_step")
            if op == "append_step":
                line = self.plans.append_step(
                    plan_id=data.get("plan_id", "default"),
                    step_id=data.get("step_id", ""),
                    text=data.get("text", ""),
                )
                if line:
                    print(line, flush=True)
            elif op == "append_text":
                line = self.plans.append_step(
                    plan_id=data.get("plan_id", "default"),
                    step_id=data.get("step_id", ""),
                    text=data.get("text", ""),
                )
                if line:
                    print(line, flush=True)
            return

        line = _format_other_event(env)
        if line:
            print(line, flush=True)

    # ----- transports -----

    async def run_demo(self, rate: float = 0.05) -> None:
        if not self.raw:
            bar = "=" * 60
            print(f"\n{bar}\n  OmoiOS session tail — OFFLINE DEMO")
            print(f"  lanes: {', '.join(sorted(self.lanes))}")
            print(f"  Ctrl+C to stop\n{bar}\n", flush=True)
        async for envelope in _demo_stream(rate):
            if self._stop.is_set():
                break
            self._render_envelope(envelope)

    async def run(self) -> None:
        urls = await self._discover_urls()
        self._banner(urls)

        backoff = 1.0
        while not self._stop.is_set():
            use_sse = self.force_sse or self.ws_failures >= 2
            try:
                if use_sse:
                    await self._run_sse(urls["events_sse"])
                else:
                    await self._run_ws(urls["websocket"])
                backoff = 1.0
            except asyncio.CancelledError:
                raise
            except Exception as e:
                if not use_sse:
                    self.ws_failures += 1
                msg = f"{COLORS['yellow']}[reconnect]{COLORS['reset']} {e}"
                self.streams.flush_for_other_event()
                print(msg, file=sys.stderr, flush=True)
                await asyncio.sleep(min(backoff, 8.0) + random.random() * 0.5)
                backoff = min(backoff * 2, 8.0)

    def _banner(self, urls: dict[str, str]) -> None:
        if self.raw:
            return
        bar = "=" * 60
        print(f"\n{bar}\n  OmoiOS session tail — {self.session_id}")
        print(f"  WS:  {urls['websocket']}")
        print(f"  SSE: {urls['events_sse']}")
        print(f"  lanes: {', '.join(sorted(self.lanes))}")
        if self.type_filters:
            print(f"  filter: {', '.join(self.type_filters)}")
        if self.since is not None:
            print(f"  since: seq>{self.since}")
        print(f"  Ctrl+C to stop\n{bar}\n", flush=True)

    async def _run_ws(self, url: str) -> None:
        try:
            import websockets
        except ImportError as e:  # pragma: no cover
            raise SystemExit(f"websockets required: {e}")

        params = {}
        if self.token:
            params["token"] = self.token
        if self.last_seq is not None:
            params["since_seq"] = str(self.last_seq)
        full_url = url + (f"?{urlencode(params)}" if params else "")

        async with websockets.connect(full_url, ping_interval=20) as ws:
            self.ws_failures = 0
            async for raw in ws:
                if isinstance(raw, bytes):
                    raw = raw.decode("utf-8", errors="replace")
                try:
                    frame = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                env = frame.get("envelope") if isinstance(frame, dict) else None
                if env is None:
                    env = frame
                self._render_envelope(env)

    async def _run_sse(self, url: str) -> None:
        try:
            import httpx
            from httpx_sse import aconnect_sse
        except ImportError as e:  # pragma: no cover
            raise SystemExit(f"httpx + httpx-sse required: {e}")

        params: dict[str, Any] = {}
        if self.last_seq is not None:
            params["since_seq"] = self.last_seq
        headers = {}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(None, connect=10.0)
        ) as client:
            async with aconnect_sse(
                client, "GET", url, params=params, headers=headers
            ) as event_source:
                async for sse_event in event_source.aiter_sse():
                    if not sse_event.data:
                        continue
                    try:
                        env = json.loads(sse_event.data)
                    except json.JSONDecodeError:
                        continue
                    self._render_envelope(env)

    def request_stop(self) -> None:
        self._stop.set()


def _parse_lanes(spec: str) -> set[str]:
    if not spec or spec == "all":
        return set(ALL_LANES)
    out: set[str] = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if part not in ALL_LANES:
            raise SystemExit(
                f"unknown lane: {part!r} (valid: {', '.join(ALL_LANES)}, all)"
            )
        out.add(part)
    return out or set(ALL_LANES)


def _parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Tail an OmoiOS session's envelope stream in the terminal.",
    )
    p.add_argument(
        "session_id",
        nargs="?",
        default=None,
        help="Target session id (tasks.id) — omit when using --demo",
    )
    p.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help=f"API base URL (default: {DEFAULT_BASE_URL})",
    )
    p.add_argument(
        "--token",
        default=os.environ.get("OMOIOS_API_TOKEN"),
        help="Bearer/JWT token (default: $OMOIOS_API_TOKEN)",
    )
    p.add_argument(
        "--sse",
        dest="force_sse",
        action="store_true",
        help="Force SSE transport (default: WS with SSE fallback)",
    )
    p.add_argument(
        "--raw",
        action="store_true",
        help="One JSON envelope per line (suitable for jq)",
    )
    p.add_argument(
        "--since", type=int, default=None, help="Resume from envelope seq > N"
    )
    p.add_argument(
        "--types", default="", help="Comma-separated event-type globs (e.g. 'agent.*')"
    )
    p.add_argument(
        "--show",
        default="chat",
        help="Lanes to render: chat,lifecycle,system or 'all' (default: chat)",
    )
    p.add_argument(
        "--demo",
        action="store_true",
        help="Run an offline scripted demo (no API/Redis needed)",
    )
    p.add_argument(
        "--demo-rate",
        type=float,
        default=0.05,
        help="Per-token delay in demo mode (default 0.05s)",
    )
    return p.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> None:
    args = _parse_args(argv)
    if not args.demo and not args.session_id:
        raise SystemExit("session_id is required (or pass --demo)")

    type_filters = [t.strip() for t in args.types.split(",") if t.strip()]
    if os.environ.get("OMOIOS_TRANSPORT") == "sse":
        args.force_sse = True
    lanes = _parse_lanes(args.show)

    tail = SessionTail(
        session_id=args.session_id or "demo",
        base_url=args.base_url,
        token=args.token,
        force_sse=args.force_sse,
        raw=args.raw,
        since=args.since,
        type_filters=type_filters,
        lanes=lanes,
    )

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, tail.request_stop)
        except NotImplementedError:  # pragma: no cover (Windows)
            pass
    try:
        if args.demo:
            loop.run_until_complete(tail.run_demo(rate=args.demo_rate))
        else:
            loop.run_until_complete(tail.run())
    except KeyboardInterrupt:
        pass
    finally:
        tail.streams.flush_for_other_event()
        loop.close()


if __name__ == "__main__":
    main()
