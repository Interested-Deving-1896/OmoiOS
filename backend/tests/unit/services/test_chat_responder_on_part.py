"""Tests for chat_responder._make_on_part.

Verifies the on_part callback bridges opencode events into the session
envelope correctly:

* every incoming opencode event becomes one envelope.emit() call
* the type is namespaced (``session.`` prepended unless already prefixed)
* high-volume types (deltas, status flips, watcher pings) are marked
  ``transient`` so they bypass the DB
* low-volume types (idle, message.updated, permission.asked) are NOT
  transient and do persist

These tests use a fake DB + bus so they don't need Postgres/Redis.
"""

from __future__ import annotations

import contextlib
from typing import Any

import pytest


# ─── stubs ───────────────────────────────────────────────────────────────────


class _FakeSession:
    def __init__(self):
        self.committed = False

    def commit(self):
        self.committed = True


class _FakeDB:
    def __init__(self):
        self._session = _FakeSession()

    @contextlib.contextmanager
    def get_session(self):
        yield self._session


class _RecordingEnvelope:
    """Captures every emit() call for assertions."""

    instances: list["_RecordingEnvelope"] = []

    def __init__(self, sess, bus):
        self.sess = sess
        self.bus = bus
        self.calls: list[dict[str, Any]] = []
        _RecordingEnvelope.instances.append(self)

    def emit(self, **kwargs):
        self.calls.append(kwargs)


@pytest.fixture(autouse=True)
def _reset_recorder():
    _RecordingEnvelope.instances.clear()
    yield
    _RecordingEnvelope.instances.clear()


@pytest.fixture
def patched_envelope(monkeypatch):
    """Patch SessionEventEnvelope inside chat_responder + a no-op event bus."""
    from omoi_os.services import chat_responder

    monkeypatch.setattr(chat_responder, "SessionEventEnvelope", _RecordingEnvelope)
    monkeypatch.setattr(chat_responder, "get_event_bus", lambda: None)
    return _RecordingEnvelope


# ─── tests ───────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_on_part_namespaces_unprefixed_types(patched_envelope):
    from omoi_os.services.chat_responder import _make_on_part

    cb = _make_on_part(session_id="ses_omoios_1", db=_FakeDB())
    await cb("message.part.delta", {"part": {"text": "hi"}})

    assert len(patched_envelope.instances) == 1
    call = patched_envelope.instances[0].calls[0]
    assert call["event_type"] == "session.message.part.delta"
    assert call["session_id"] == "ses_omoios_1"


@pytest.mark.asyncio
async def test_on_part_passes_through_session_prefixed_types(patched_envelope):
    from omoi_os.services.chat_responder import _make_on_part

    cb = _make_on_part(session_id="ses_x", db=_FakeDB())
    await cb("session.idle", {"sessionID": "ses_inner"})

    call = patched_envelope.instances[0].calls[0]
    assert call["event_type"] == "session.idle"


def _all_calls(recorder: _RecordingEnvelope) -> list[dict[str, Any]]:
    """Aggregate emit() calls across every envelope instance the test made."""
    return [c for inst in recorder.instances for c in inst.calls]


@pytest.mark.asyncio
async def test_on_part_marks_high_volume_transient(patched_envelope):
    from omoi_os.services.chat_responder import _make_on_part

    cb = _make_on_part(session_id="ses_x", db=_FakeDB())
    await cb("message.part.delta", {"part": {"text": "tok"}})
    await cb("session.status", {"sessionID": "ses_x", "status": "busy"})
    await cb("pty.updated", {"info": {"id": "pty_1"}})
    await cb("lsp.client.diagnostics", {"serverID": "pyright", "path": "/x"})
    await cb("file.watcher.updated", {"path": "/x"})

    calls = _all_calls(patched_envelope)
    assert all(c["transient"] is True for c in calls), calls


@pytest.mark.asyncio
async def test_on_part_does_not_force_low_volume_transient(patched_envelope):
    from omoi_os.services.chat_responder import _make_on_part

    cb = _make_on_part(session_id="ses_x", db=_FakeDB())
    await cb("session.idle", {"sessionID": "ses_x"})
    await cb("message.updated", {"part": {"text": "hi"}})
    await cb("permission.asked", {"permission": {"id": "p1"}})
    await cb("session.error", {"sessionID": "ses_x", "error": {"name": "X"}})
    await cb("file.edited", {"file": "/repo/x.py"})

    calls = _all_calls(patched_envelope)
    # transient is None (let envelope's own .delta autodetect handle it)
    assert all(c["transient"] is None for c in calls), calls


@pytest.mark.asyncio
async def test_on_part_swallows_envelope_failures(patched_envelope, monkeypatch):
    """A failing envelope must NOT abort the streaming turn."""
    from omoi_os.services import chat_responder

    class _BoomEnvelope(_RecordingEnvelope):
        def emit(self, **kwargs):
            raise RuntimeError("DB unreachable")

    monkeypatch.setattr(chat_responder, "SessionEventEnvelope", _BoomEnvelope)

    cb = chat_responder._make_on_part(session_id="ses_x", db=_FakeDB())
    # Must not raise
    await cb("message.part.delta", {"part": {"text": "tok"}})


@pytest.mark.asyncio
async def test_on_part_forwards_full_event_vocabulary(patched_envelope):
    """Smoke: every type the taxonomy advertises gets through to emit()."""
    from omoi_os.services.chat_responder import _make_on_part
    from omoi_os.services.opencode_events import (
        SESSION_SCOPED_EVENTS,
        WORKSPACE_SCOPED_EVENTS,
    )

    cb = _make_on_part(session_id="ses_x", db=_FakeDB())
    for et in SESSION_SCOPED_EVENTS | WORKSPACE_SCOPED_EVENTS:
        await cb(et, {"sessionID": "ses_x"})

    # Each call instantiates a fresh envelope; aggregate across them.
    seen = {c["event_type"] for inst in patched_envelope.instances for c in inst.calls}
    expected = {
        f"session.{et}" if not et.startswith("session.") else et
        for et in SESSION_SCOPED_EVENTS | WORKSPACE_SCOPED_EVENTS
    }
    assert seen == expected
