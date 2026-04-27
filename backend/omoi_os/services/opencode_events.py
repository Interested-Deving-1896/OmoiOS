"""Canonical taxonomy of opencode bus events.

opencode emits a global SSE feed at ``GET /event`` covering every domain
the server knows about: chat messages, sessions, permissions, file edits,
LSP diagnostics, ptys, project state, the lot. Most clients want a
filtered subset — typically "everything that pertains to my session".

This module is the single source of truth for:

* the full vocabulary of event types we recognise,
* whether each type is *session-scoped* (carries a sessionID we can
  match) or *workspace-scoped* (no sessionID but emitted from the same
  sandbox we own),
* a ``should_forward`` predicate the modal/daytona agents use to decide
  whether to push an event to the SSE consumer,
* a ``is_high_volume`` predicate so the envelope can mark the event as
  ``transient`` (no DB row) and bound table volume.

Reference: opencode-1.14.x bus event registry. Verified against the
schema dumped by the deepwiki-resolved zod definitions in
``packages/opencode/src/{session,permission,question,command,...}``.
"""

from __future__ import annotations

from typing import Any, Optional


# ─── event vocabulary ────────────────────────────────────────────────────────


# Events whose ``properties`` always carries a ``sessionID`` (top-level or
# nested under ``info``/``part``/``permission``). Anything in this set is
# routed by session id.
SESSION_SCOPED_EVENTS: frozenset[str] = frozenset(
    {
        # Message lifecycle
        "message.part.delta",
        "message.part.updated",
        "message.part.removed",
        "message.updated",
        "message.removed",
        # Session lifecycle
        "session.created",
        "session.updated",
        "session.deleted",
        "session.idle",
        "session.compacted",
        "session.diff",
        "session.error",
        "session.status",
        # Permission flow (HITL approval before tool execution)
        "permission.asked",
        "permission.replied",
        "permission.updated",
        # Structured-question flow (agent asks user, user replies)
        "question.asked",
        "question.replied",
        "question.rejected",
        # Slash-command execution (still scoped to one session)
        "command.executed",
    }
)


# Events emitted from the workspace/sandbox without a sessionID. Each
# OmoiOS session owns its own sandbox 1:1, so anything emitted from THIS
# sandbox IS for our session — we forward these too.
WORKSPACE_SCOPED_EVENTS: frozenset[str] = frozenset(
    {
        "file.edited",
        "file.watcher.updated",
        "lsp.client.diagnostics",
        "lsp.updated",
        "pty.created",
        "pty.updated",
        "pty.exited",
        "pty.deleted",
        "project.updated",
    }
)


# Events scoped to the opencode binary or the SSE transport itself —
# noisy, not actionable for chat clients, never forward.
GLOBAL_EVENTS: frozenset[str] = frozenset(
    {
        "server.connected",
        "server.heartbeat",
        "server.instance.disposed",
        "global.disposed",
        "installation.updated",
        "installation.update-available",
        "tui.prompt.append",
        "tui.command.execute",
    }
)


# Events that fire many times per turn (token-level deltas, status
# flips, watcher pings). The envelope marks these ``transient`` so we
# publish to Redis but skip the DB row.
HIGH_VOLUME_EVENTS: frozenset[str] = frozenset(
    {
        "message.part.delta",
        "session.status",
        "file.watcher.updated",
        "pty.updated",
        "lsp.client.diagnostics",
    }
)


# ─── matchers ────────────────────────────────────────────────────────────────


def extract_session_id(evt: Any) -> Optional[str]:
    """Pull the opencode sessionID out of an event payload.

    Different event types nest the sid in different places (top-level
    ``sessionID``, ``info.id`` for session lifecycle, ``info.sessionID``
    for messages, ``part.sessionID`` for message-parts, ``permission.sessionID``
    for permission events). We check all the spots and return the first
    hit.

    Returns ``None`` for workspace/global events that have no sessionID.
    """
    if not isinstance(evt, dict):
        return None
    props = evt.get("properties")
    if not isinstance(props, dict):
        return None

    sid = props.get("sessionID")
    if isinstance(sid, str):
        return sid

    part = props.get("part")
    if isinstance(part, dict):
        sid = part.get("sessionID")
        if isinstance(sid, str):
            return sid

    info = props.get("info")
    if isinstance(info, dict):
        sid = info.get("sessionID")
        if isinstance(sid, str):
            return sid
        # session.{created,updated,deleted}: info IS the Session, info.id == sid
        sid = info.get("id")
        if isinstance(sid, str):
            return sid

    permission = props.get("permission")
    if isinstance(permission, dict):
        sid = permission.get("sessionID")
        if isinstance(sid, str):
            return sid

    return None


def should_forward(evt: Any, opencode_session_id: str) -> bool:
    """Should this event flow through to the SSE consumer for our session?

    Rules:
      * session-scoped event with our sid → forward
      * session-scoped event with a different sid → drop
      * workspace-scoped event (no sid) → forward (this sandbox is ours)
      * global event → drop
      * unknown event type with our sid → forward (be liberal in what
        we accept; future opencode versions will add types we don't
        know about yet)
      * unknown event type with no sid → drop (could be anything)
    """
    if not isinstance(evt, dict):
        return False
    et = evt.get("type")
    if not isinstance(et, str):
        return False

    if et in GLOBAL_EVENTS:
        return False

    extracted_sid = extract_session_id(evt)

    if et in SESSION_SCOPED_EVENTS:
        return extracted_sid == opencode_session_id

    if et in WORKSPACE_SCOPED_EVENTS:
        # Each OmoiOS session owns its sandbox 1:1, so every workspace
        # event from THIS opencode instance is for our session. We
        # don't try to extract_session_id — pty/lsp/file payloads have
        # their own ``info.id`` that means something else (a pty id,
        # a server id) and would confuse the matcher.
        return True

    # Unknown type — forward if it claims our sid.
    return extracted_sid == opencode_session_id


def is_high_volume(event_type: str) -> bool:
    """Whether the envelope should mark this event ``transient`` (skip DB)."""
    return event_type in HIGH_VOLUME_EVENTS
