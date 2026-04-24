"""Tests for event stream CLI — formatting and filtering only (no Redis needed)."""

from __future__ import annotations


from omoi_os.cli.event_stream import (
    EVENT_ICONS,
    EventStreamCLI,
    format_event_json,
    format_event_rich,
    format_timestamp,
    matches_filter,
)


class TestFormatTimestamp:
    def test_with_valid_iso_timestamp(self):
        result = format_timestamp("2026-03-01T14:23:01")
        assert result == "14:23:01"

    def test_with_none_returns_current_time(self):
        result = format_timestamp(None)
        assert len(result) == 8  # HH:MM:SS

    def test_with_invalid_string_returns_current_time(self):
        result = format_timestamp("not-a-date")
        assert len(result) == 8


class TestMatchesFilter:
    def test_exact_match(self):
        assert matches_filter("TASK_CREATED", "TASK_CREATED") is True

    def test_wildcard_match(self):
        assert matches_filter("TASK_CREATED", "TASK_*") is True
        assert matches_filter("TASK_COMPLETED", "TASK_*") is True

    def test_wildcard_no_match(self):
        assert matches_filter("SANDBOX_SPAWNED", "TASK_*") is False

    def test_dot_wildcard(self):
        assert matches_filter("agent.tool_use", "agent.*") is True
        assert matches_filter("agent.started", "agent.*") is True

    def test_no_match(self):
        assert matches_filter("TASK_CREATED", "SANDBOX_*") is False


class TestFormatEventRich:
    def test_task_created_event(self):
        event = {
            "event_type": "TASK_CREATED",
            "entity_type": "task",
            "entity_id": "abc12345-6789",
            "payload": {"description": "Implement auth"},
        }
        result = format_event_rich(event)
        assert "TASK_CREATED" in result
        assert "task/abc12345" in result
        assert '"Implement auth"' in result

    def test_dry_run_decision_event(self):
        event = {
            "event_type": "orchestrator.dry_run.decision",
            "entity_type": "orchestrator",
            "entity_id": "dry-run",
            "payload": {
                "selected_task": {
                    "task_id": "xyz98765-4321",
                    "task_type": "implement_feature",
                },
            },
        }
        result = format_event_rich(event)
        assert "dry_run.decision" in result
        assert "xyz98765" in result

    def test_unknown_event_type_gets_default_icon(self):
        event = {
            "event_type": "CUSTOM_EVENT",
            "entity_type": "custom",
            "entity_id": "id-123",
            "payload": {},
        }
        result = format_event_rich(event)
        assert "CUSTOM_EVENT" in result

    def test_long_description_truncated(self):
        event = {
            "event_type": "TASK_CREATED",
            "entity_type": "task",
            "entity_id": "abc123",
            "payload": {"description": "A" * 100},
        }
        result = format_event_rich(event)
        assert "..." in result


class TestFormatEventJson:
    def test_returns_valid_json(self):
        import json

        event = {
            "event_type": "TASK_CREATED",
            "entity_type": "task",
            "entity_id": "123",
            "payload": {},
        }
        result = format_event_json(event)
        parsed = json.loads(result)
        assert parsed["event_type"] == "TASK_CREATED"


class TestEventStreamCLI:
    def test_handle_event_no_filter(self):
        cli = EventStreamCLI()
        event = {
            "event_type": "TASK_CREATED",
            "entity_type": "task",
            "entity_id": "123",
            "payload": {},
        }
        result = cli.handle_event(event)
        assert result is not None
        assert "TASK_CREATED" in result

    def test_handle_event_filter_match(self):
        cli = EventStreamCLI(filter_pattern="TASK_*")
        event = {
            "event_type": "TASK_CREATED",
            "entity_type": "task",
            "entity_id": "123",
            "payload": {},
        }
        result = cli.handle_event(event)
        assert result is not None

    def test_handle_event_filter_no_match(self):
        cli = EventStreamCLI(filter_pattern="SANDBOX_*")
        event = {
            "event_type": "TASK_CREATED",
            "entity_type": "task",
            "entity_id": "123",
            "payload": {},
        }
        result = cli.handle_event(event)
        assert result is None

    def test_handle_event_json_mode(self):
        import json

        cli = EventStreamCLI(json_mode=True)
        event = {
            "event_type": "TASK_CREATED",
            "entity_type": "task",
            "entity_id": "123",
            "payload": {},
        }
        result = cli.handle_event(event)
        parsed = json.loads(result)
        assert parsed["event_type"] == "TASK_CREATED"

    def test_entity_filter_match(self):
        cli = EventStreamCLI(entity_filter="abc123")
        event = {
            "event_type": "TASK_CREATED",
            "entity_type": "task",
            "entity_id": "abc123",
            "payload": {},
        }
        result = cli.handle_event(event)
        assert result is not None

    def test_entity_filter_no_match(self):
        cli = EventStreamCLI(entity_filter="abc123")
        event = {
            "event_type": "TASK_CREATED",
            "entity_type": "task",
            "entity_id": "xyz789",
            "payload": {},
        }
        result = cli.handle_event(event)
        assert result is None

    def test_entity_filter_spec_id_in_payload(self):
        cli = EventStreamCLI(entity_filter="spec-123")
        event = {
            "event_type": "TASK_CREATED",
            "entity_type": "task",
            "entity_id": "task-456",
            "payload": {"spec_id": "spec-123"},
        }
        result = cli.handle_event(event)
        assert result is not None

    def test_event_count_increments(self):
        cli = EventStreamCLI()
        event = {
            "event_type": "TASK_CREATED",
            "entity_type": "task",
            "entity_id": "123",
            "payload": {},
        }
        cli.handle_event(event)
        cli.handle_event(event)
        assert cli.event_count == 2

    def test_event_icons_complete(self):
        """All key event types have icons."""
        assert "TASK_CREATED" in EVENT_ICONS
        assert "TASK_COMPLETED" in EVENT_ICONS
        assert "TASK_FAILED" in EVENT_ICONS
        assert "orchestrator.dry_run.decision" in EVENT_ICONS
