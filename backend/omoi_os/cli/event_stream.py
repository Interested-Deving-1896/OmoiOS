"""CLI event stream for OmoiOS orchestration.

Usage:
    python -m omoi_os.cli.event_stream                    # All events
    python -m omoi_os.cli.event_stream --filter TASK_*    # Task events only
    python -m omoi_os.cli.event_stream --filter agent.*   # Agent events only
    python -m omoi_os.cli.event_stream --json             # Raw JSON output
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from typing import Optional

import fnmatch

# Event type → emoji mapping for rich display
EVENT_ICONS = {
    "TASK_CREATED": "🔄",
    "TASK_ASSIGNED": "📋",
    "TASK_STARTED": "▶️ ",
    "TASK_COMPLETED": "✅",
    "TASK_FAILED": "❌",
    "TASK_VALIDATION_FAILED": "⚠️ ",
    "TASK_VALIDATION_PASSED": "✔️ ",
    "SANDBOX_SPAWNED": "🚀",
    "SANDBOX_agent.completed": "✅",
    "SANDBOX_agent.failed": "❌",
    "SANDBOX_agent.error": "💥",
    "TICKET_CREATED": "🎫",
    "orchestrator.dry_run.decision": "🔮",
    "agent.tool_use": "🤖",
    "coordination.join": "🔀",
}

# ANSI color codes
COLORS = {
    "reset": "\033[0m",
    "dim": "\033[2m",
    "bold": "\033[1m",
    "red": "\033[31m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "blue": "\033[34m",
    "magenta": "\033[35m",
    "cyan": "\033[36m",
}

EVENT_COLORS = {
    "TASK_CREATED": "cyan",
    "TASK_ASSIGNED": "blue",
    "TASK_STARTED": "green",
    "TASK_COMPLETED": "green",
    "TASK_FAILED": "red",
    "TASK_VALIDATION_FAILED": "yellow",
    "SANDBOX_SPAWNED": "magenta",
    "orchestrator.dry_run.decision": "magenta",
}


def format_timestamp(ts: Optional[str] = None) -> str:
    """Format timestamp for display. If None, use current time."""
    if ts:
        try:
            dt = datetime.fromisoformat(ts)
            return dt.strftime("%H:%M:%S")
        except (ValueError, TypeError):
            pass
    return datetime.now().strftime("%H:%M:%S")


def format_event_rich(event_data: dict) -> str:
    """Format an event for rich terminal display."""
    event_type = event_data.get("event_type", "unknown")
    entity_type = event_data.get("entity_type", "")
    entity_id = event_data.get("entity_id", "")
    payload = event_data.get("payload", {})

    icon = EVENT_ICONS.get(event_type, "📌")
    color_name = EVENT_COLORS.get(event_type, "reset")
    color = COLORS.get(color_name, "")
    reset = COLORS["reset"]
    dim = COLORS["dim"]

    ts = format_timestamp(payload.get("timestamp"))

    # Format entity reference
    entity_ref = f"{entity_type}/{entity_id[:8]}" if entity_id else entity_type

    # Build detail string from payload
    details = ""
    if event_type == "orchestrator.dry_run.decision":
        selected = payload.get("selected_task", {})
        if selected:
            details = f"task={selected.get('task_id', '')[:8]} type={selected.get('task_type', '')}"
    elif "description" in payload:
        desc = payload["description"]
        if len(desc) > 60:
            desc = desc[:57] + "..."
        details = f'"{desc}"'
    elif "error_message" in payload:
        details = f'error="{payload["error_message"][:50]}"'

    return f"{dim}[{ts}]{reset} {icon} {color}{event_type:<30}{reset} {entity_ref:<20} {details}"


def format_event_json(event_data: dict) -> str:
    """Format an event as compact JSON (one line)."""
    return json.dumps(event_data, default=str)


def matches_filter(event_type: str, filter_pattern: str) -> bool:
    """Check if an event type matches a filter pattern (supports wildcards)."""
    # Convert wildcard patterns: TASK_* → TASK_*, agent.* → agent.*
    return fnmatch.fnmatch(event_type, filter_pattern)


class EventStreamCLI:
    """CLI tool for streaming OmoiOS events from Redis."""

    def __init__(
        self,
        redis_url: Optional[str] = None,
        filter_pattern: Optional[str] = None,
        json_mode: bool = False,
        entity_filter: Optional[str] = None,
    ):
        self.filter_pattern = filter_pattern
        self.json_mode = json_mode
        self.entity_filter = entity_filter
        self.event_count = 0
        self._redis_url = redis_url

    def _get_redis_url(self) -> str:
        """Get Redis URL from settings or environment."""
        if self._redis_url:
            return self._redis_url
        try:
            from omoi_os.config import get_app_settings

            return get_app_settings().redis.url
        except Exception:
            import os

            return os.getenv("REDIS_URL", "redis://localhost:16379")

    def _should_display(self, event_data: dict) -> bool:
        """Check if event passes all filters."""
        event_type = event_data.get("event_type", "")

        # Check event type filter
        if self.filter_pattern and not matches_filter(event_type, self.filter_pattern):
            return False

        # Check entity filter (task ID, spec ID, etc.)
        if self.entity_filter:
            entity_id = event_data.get("entity_id", "")
            payload = event_data.get("payload", {})
            spec_id = payload.get("spec_id", "")
            if self.entity_filter not in (entity_id, spec_id):
                return False

        return True

    def handle_event(self, event_data: dict) -> Optional[str]:
        """Process a single event. Returns formatted string or None if filtered out."""
        if not self._should_display(event_data):
            return None

        self.event_count += 1

        if self.json_mode:
            return format_event_json(event_data)
        else:
            return format_event_rich(event_data)

    def run(self) -> None:
        """Start streaming events from Redis. Blocks until interrupted."""
        import redis as redis_lib

        redis_url = self._get_redis_url()

        try:
            # Use short timeout for initial connection check
            client = redis_lib.from_url(
                redis_url,
                decode_responses=True,
                socket_timeout=5.0,
                socket_connect_timeout=5.0,
            )
            client.ping()
        except (
            redis_lib.exceptions.ConnectionError,
            redis_lib.exceptions.TimeoutError,
        ) as e:
            print(f"❌ Cannot connect to Redis at {redis_url}: {e}", file=sys.stderr)
            print(
                "   Make sure Redis is running (just dev-all or docker-compose up redis)",
                file=sys.stderr,
            )
            sys.exit(1)

        # Re-create client without socket_timeout for long-lived pub/sub listener
        # socket_timeout causes TimeoutError during listen() when no events arrive
        client = redis_lib.from_url(
            redis_url,
            decode_responses=True,
            socket_timeout=None,
            socket_connect_timeout=5.0,
        )

        pubsub = client.pubsub()

        # Subscribe to all event channels via pattern
        pubsub.psubscribe("events.*")

        # Print banner
        if not self.json_mode:
            print(f"\n{'=' * 60}")
            print("  OmoiOS Event Stream")
            print(f"  Connected to: {redis_url}")
            if self.filter_pattern:
                print(f"  Filter: {self.filter_pattern}")
            if self.entity_filter:
                print(f"  Entity: {self.entity_filter}")
            print("  Press Ctrl+C to stop")
            print(f"{'=' * 60}\n")

        try:
            for message in pubsub.listen():
                if message["type"] == "pmessage":
                    try:
                        event_data = json.loads(message["data"])
                        output = self.handle_event(event_data)
                        if output:
                            print(output, flush=True)
                    except (json.JSONDecodeError, KeyError):
                        pass  # Skip malformed messages
        except KeyboardInterrupt:
            if not self.json_mode:
                print(f"\n\nStream ended. {self.event_count} events received.")
        finally:
            pubsub.close()
            client.close()


def main():
    parser = argparse.ArgumentParser(
        description="Stream OmoiOS orchestration events from Redis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m omoi_os.cli.event_stream                     # All events
  python -m omoi_os.cli.event_stream --filter "TASK_*"   # Task events only
  python -m omoi_os.cli.event_stream --filter "agent.*"  # Agent events
  python -m omoi_os.cli.event_stream --json              # JSON output (pipe to jq)
  python -m omoi_os.cli.event_stream --entity abc123     # Filter by entity ID
        """,
    )
    parser.add_argument(
        "--filter",
        "-f",
        dest="filter_pattern",
        help="Filter events by type pattern (supports wildcards: TASK_*, agent.*)",
    )
    parser.add_argument(
        "--json",
        "-j",
        dest="json_mode",
        action="store_true",
        help="Output raw JSON (one event per line, suitable for piping to jq)",
    )
    parser.add_argument(
        "--entity",
        "-e",
        dest="entity_filter",
        help="Filter events by entity ID or spec ID",
    )
    parser.add_argument(
        "--redis-url",
        help="Redis URL (default: from config or redis://localhost:16379)",
    )

    args = parser.parse_args()

    cli = EventStreamCLI(
        redis_url=args.redis_url,
        filter_pattern=args.filter_pattern,
        json_mode=args.json_mode,
        entity_filter=args.entity_filter,
    )
    cli.run()


if __name__ == "__main__":
    main()
