"""Tests for the opencode event taxonomy.

Covers:
* extract_session_id digs the sid out of every nest location opencode uses
* should_forward routes session-scoped events by sid match
* should_forward forwards workspace events from our sandbox unconditionally
* should_forward drops global/transport events
* is_high_volume picks the events that should be marked transient
"""

from __future__ import annotations

import pytest

from omoi_os.services.opencode_events import (
    GLOBAL_EVENTS,
    HIGH_VOLUME_EVENTS,
    SESSION_SCOPED_EVENTS,
    WORKSPACE_SCOPED_EVENTS,
    extract_session_id,
    is_high_volume,
    should_forward,
)


SID = "ses_abc123"
OTHER = "ses_xyz789"


# ─── extract_session_id ──────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "evt,expected",
    [
        ({"type": "session.idle", "properties": {"sessionID": SID}}, SID),
        (
            {"type": "session.created", "properties": {"info": {"id": SID}}},
            SID,
        ),
        (
            {
                "type": "message.part.updated",
                "properties": {"part": {"sessionID": SID}},
            },
            SID,
        ),
        (
            {
                "type": "message.updated",
                "properties": {"info": {"sessionID": SID}},
            },
            SID,
        ),
        (
            {
                "type": "permission.asked",
                "properties": {"permission": {"sessionID": SID}},
            },
            SID,
        ),
        (
            {"type": "permission.replied", "properties": {"sessionID": SID}},
            SID,
        ),
        ({"type": "command.executed", "properties": {"sessionID": SID}}, SID),
        # No sid anywhere
        ({"type": "file.edited", "properties": {"file": "/etc/hosts"}}, None),
        ({"type": "server.heartbeat", "properties": {}}, None),
        # Malformed
        (None, None),
        ({"type": "x"}, None),
        ({"type": "x", "properties": "not-a-dict"}, None),
    ],
)
def test_extract_session_id(evt, expected):
    assert extract_session_id(evt) == expected


# ─── should_forward (session-scoped) ─────────────────────────────────────────


def test_session_scoped_forwards_when_sid_matches():
    evt = {"type": "session.idle", "properties": {"sessionID": SID}}
    assert should_forward(evt, SID) is True


def test_session_scoped_dropped_when_sid_differs():
    evt = {"type": "session.idle", "properties": {"sessionID": OTHER}}
    assert should_forward(evt, SID) is False


def test_message_part_delta_forwards_via_part_sid():
    evt = {
        "type": "message.part.delta",
        "properties": {"part": {"sessionID": SID, "type": "text"}},
    }
    assert should_forward(evt, SID) is True


def test_permission_asked_forwards_via_nested_permission_sid():
    evt = {
        "type": "permission.asked",
        "properties": {"permission": {"sessionID": SID, "id": "perm_1"}},
    }
    assert should_forward(evt, SID) is True


def test_session_created_forwards_via_info_id():
    evt = {"type": "session.created", "properties": {"info": {"id": SID}}}
    assert should_forward(evt, SID) is True


def test_session_error_with_optional_sid_missing_drops():
    # session.error has optional sid; without one, we cannot route → drop
    evt = {"type": "session.error", "properties": {"error": {"name": "X"}}}
    assert should_forward(evt, SID) is False


# ─── should_forward (workspace-scoped) ───────────────────────────────────────


def test_file_edited_forwards_unconditionally():
    evt = {"type": "file.edited", "properties": {"file": "/repo/main.py"}}
    assert should_forward(evt, SID) is True


def test_lsp_diagnostics_forwards_unconditionally():
    evt = {
        "type": "lsp.client.diagnostics",
        "properties": {"serverID": "pyright", "path": "/repo/x.py"},
    }
    assert should_forward(evt, SID) is True


def test_pty_event_forwards_unconditionally():
    evt = {
        "type": "pty.created",
        "properties": {"info": {"id": "pty_1", "command": "ls"}},
    }
    assert should_forward(evt, SID) is True


# ─── should_forward (global) ─────────────────────────────────────────────────


def test_server_heartbeat_dropped():
    evt = {"type": "server.heartbeat", "properties": {}}
    assert should_forward(evt, SID) is False


def test_installation_event_dropped():
    evt = {"type": "installation.update-available", "properties": {"version": "1.15"}}
    assert should_forward(evt, SID) is False


def test_tui_event_dropped():
    evt = {"type": "tui.command.execute", "properties": {"command": "edit"}}
    assert should_forward(evt, SID) is False


# ─── unknown types ───────────────────────────────────────────────────────────


def test_unknown_type_with_our_sid_forwards():
    """Future-proofing: if opencode adds a new type that carries our sid,
    forward it rather than silently dropping."""
    evt = {"type": "feature.we.dont.know.about", "properties": {"sessionID": SID}}
    assert should_forward(evt, SID) is True


def test_unknown_type_without_sid_drops():
    evt = {"type": "feature.we.dont.know.about", "properties": {}}
    assert should_forward(evt, SID) is False


def test_malformed_event_drops():
    assert should_forward({}, SID) is False
    assert should_forward({"properties": {}}, SID) is False
    assert should_forward({"type": 42, "properties": {}}, SID) is False


# ─── high-volume marking ─────────────────────────────────────────────────────


def test_message_part_delta_is_high_volume():
    assert is_high_volume("message.part.delta") is True


def test_session_status_is_high_volume():
    """Status flips busy↔idle several times per turn — transient."""
    assert is_high_volume("session.status") is True


def test_lsp_diagnostics_is_high_volume():
    assert is_high_volume("lsp.client.diagnostics") is True


def test_pty_updated_is_high_volume():
    assert is_high_volume("pty.updated") is True


def test_session_idle_is_not_high_volume():
    """idle is the terminal signal for a turn — must persist for replay."""
    assert is_high_volume("session.idle") is False


def test_message_updated_is_not_high_volume():
    """The cumulative snapshot is the source of truth for replay."""
    assert is_high_volume("message.updated") is False


def test_unknown_type_is_not_high_volume():
    assert is_high_volume("foo.bar") is False


# ─── taxonomy disjoint sets ──────────────────────────────────────────────────


def test_taxonomy_partitions_are_disjoint():
    """A type cannot be both session-scoped and workspace-scoped, etc."""
    assert SESSION_SCOPED_EVENTS.isdisjoint(WORKSPACE_SCOPED_EVENTS)
    assert SESSION_SCOPED_EVENTS.isdisjoint(GLOBAL_EVENTS)
    assert WORKSPACE_SCOPED_EVENTS.isdisjoint(GLOBAL_EVENTS)


def test_high_volume_subset_of_known_types():
    """Every high-volume type is one we recognise (session or workspace)."""
    known = SESSION_SCOPED_EVENTS | WORKSPACE_SCOPED_EVENTS
    assert HIGH_VOLUME_EVENTS.issubset(known)
