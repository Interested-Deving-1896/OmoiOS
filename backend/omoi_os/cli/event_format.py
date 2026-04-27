"""Shared ANSI formatting + lane routing for terminal event consumers.

Used by both the legacy Redis pubsub tail (`event_stream.py`) and the
spec-shaped per-session tail (`session_tail.py`).

Three lanes are defined so a TUI can show only the noise it cares about:

- **chat**       — what the user reads as a conversation
- **lifecycle**  — agent health, errors, handoffs (dim/sidebar)
- **system**     — sandbox, guardian, memory, coordination, spec, ticket

Anything not classified falls into `system` (fail-safe).
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Optional


# ---- Lane assignment ------------------------------------------------------

LANE_CHAT = "chat"
LANE_LIFECYCLE = "lifecycle"
LANE_SYSTEM = "system"

EVENT_LANES: dict[str, str] = {
    # ---- chat lane ----
    "session.created": LANE_CHAT,
    "session.started": LANE_CHAT,
    "session.completed": LANE_CHAT,
    "session.succeeded": LANE_CHAT,
    "session.failed": LANE_CHAT,
    "session.cancelled": LANE_CHAT,
    "session.message": LANE_CHAT,
    "agent.user_message": LANE_CHAT,
    "agent.assistant_message": LANE_CHAT,
    "agent.system_message": LANE_CHAT,
    "agent.thinking": LANE_CHAT,
    "agent.thinking_delta": LANE_CHAT,
    "agent.text_output": LANE_CHAT,
    "agent.text_delta": LANE_CHAT,
    "agent.tool_use": LANE_CHAT,
    "agent.tool_input_delta": LANE_CHAT,
    "agent.tool_result": LANE_CHAT,
    "agent.tool_result_delta": LANE_CHAT,
    "agent.tool_completed": LANE_CHAT,
    "agent.user_tool_result": LANE_CHAT,
    "agent.command_started": LANE_CHAT,
    "agent.command_completed": LANE_CHAT,
    "agent.file_written": LANE_CHAT,
    "agent.file_edited": LANE_CHAT,
    "agent.skill_invoked": LANE_CHAT,
    "agent.skill_completed": LANE_CHAT,
    "agent.subagent_invoked": LANE_CHAT,
    "agent.subagent_completed": LANE_CHAT,
    "agent.plan_created": LANE_CHAT,
    "agent.plan_updated": LANE_CHAT,
    "agent.plan_delta": LANE_CHAT,
    "agent.turn_complete": LANE_CHAT,
    "agent.response": LANE_CHAT,
    "agent.message": LANE_CHAT,
    "agent.message.sent": LANE_CHAT,
    # ---- lifecycle lane ----
    "agent.started": LANE_LIFECYCLE,
    "agent.shutdown": LANE_LIFECYCLE,
    "agent.heartbeat": LANE_LIFECYCLE,
    "agent.waiting": LANE_LIFECYCLE,
    "agent.processing": LANE_LIFECYCLE,
    "agent.interrupted": LANE_LIFECYCLE,
    "agent.error": LANE_LIFECYCLE,
    "agent.stream_error": LANE_LIFECYCLE,
    "agent.failed": LANE_LIFECYCLE,
    "agent.completed": LANE_LIFECYCLE,
    "agent.result": LANE_LIFECYCLE,
    "agent.message_injected": LANE_LIFECYCLE,
    "agent.capability.updated": LANE_LIFECYCLE,
    "agent.handoff.requested": LANE_LIFECYCLE,
    "agent.handoff.accepted": LANE_LIFECYCLE,
    "agent.handoff.declined": LANE_LIFECYCLE,
    "agent.collab.started": LANE_LIFECYCLE,
    "agent.collab.ended": LANE_LIFECYCLE,
    "agent.validation_feedback": LANE_LIFECYCLE,
    "agent.log": LANE_LIFECYCLE,
    "agent.event": LANE_LIFECYCLE,
}

# Prefix-based fallbacks for lane assignment (longest prefix wins).
_PREFIX_LANES: list[tuple[str, str]] = [
    ("sandbox.", LANE_SYSTEM),
    ("guardian.", LANE_SYSTEM),
    ("memory.", LANE_SYSTEM),
    ("coordination.", LANE_SYSTEM),
    ("orchestrator.", LANE_SYSTEM),
    ("spec.", LANE_SYSTEM),
    ("ticket.", LANE_SYSTEM),
    ("task.", LANE_SYSTEM),
    ("iteration.", LANE_SYSTEM),
    ("continuous.", LANE_SYSTEM),
    ("agent.", LANE_LIFECYCLE),  # any unknown agent.* defaults to lifecycle
    ("session.", LANE_CHAT),
]


def lane_for(event_type: str) -> str:
    if event_type in EVENT_LANES:
        return EVENT_LANES[event_type]
    for prefix, lane in _PREFIX_LANES:
        if event_type.startswith(prefix):
            return lane
    return LANE_SYSTEM


# ---- Icons ----------------------------------------------------------------

EVENT_ICONS: dict[str, str] = {
    # --- session lifecycle ---
    "session.created": "🟢",
    "session.started": "🟢",
    "session.completed": "✅",
    "session.succeeded": "✅",
    "session.failed": "❌",
    "session.cancelled": "🚫",
    "session.message": "💬",
    # --- conversation core ---
    "agent.user_message": "👤",
    "agent.assistant_message": "🤖",
    "agent.system_message": "⚙️ ",
    "agent.thinking": "💭",
    "agent.thinking_delta": "",  # body-only redraw
    "agent.text_output": "💬",
    "agent.text_delta": "",  # body-only redraw
    "agent.response": "💬",
    "agent.message": "💬",
    "agent.message.sent": "📤",
    "agent.turn_complete": "🏁",
    # --- tools ---
    "agent.tool_use": "🔧",
    "agent.tool_input_delta": "",  # body-only redraw
    "agent.tool_result": "↳",
    "agent.tool_result_delta": "",  # body-only redraw
    "agent.tool_completed": "↳",
    "agent.user_tool_result": "↳",
    "agent.command_started": "$",
    "agent.command_completed": "↳",
    "agent.file_written": "📝",
    "agent.file_edited": "✏️ ",
    "agent.skill_invoked": "🪄",
    "agent.skill_completed": "✨",
    "agent.subagent_invoked": "🧬",
    "agent.subagent_completed": "🧬",
    "agent.plan_created": "🗺️ ",
    "agent.plan_updated": "🗺️ ",
    "agent.plan_delta": "",
    # --- lifecycle ---
    "agent.started": "▶️ ",
    "agent.shutdown": "⏹️ ",
    "agent.heartbeat": "·",
    "agent.waiting": "⏳",
    "agent.processing": "⚙️ ",
    "agent.interrupted": "⏸️ ",
    "agent.error": "💥",
    "agent.stream_error": "💥",
    "agent.failed": "❌",
    "agent.completed": "✅",
    "agent.result": "📦",
    "agent.message_injected": "💉",
    "agent.capability.updated": "🛠️ ",
    "agent.handoff.requested": "🤝",
    "agent.handoff.accepted": "🤝",
    "agent.handoff.declined": "🙅",
    "agent.collab.started": "👥",
    "agent.collab.ended": "👥",
    "agent.validation_feedback": "🧪",
    "agent.log": "📋",
    "agent.event": "📌",
    # --- sandbox / guardian / memory ---
    "sandbox.spawned": "🚀",
    "sandbox.terminated": "🛑",
    "sandbox.failed": "💥",
    "guardian.steering.intervention": "🦮",
    "memory.context.suggested": "🧠",
    "memory.pattern.learned": "🧠",
    "memory.stored": "🧠",
    # --- coordination ---
    "coordination.join.created": "🔀",
    "coordination.split.created": "🪓",
    "coordination.merge.completed": "🔗",
    "coordination.sync.created": "🔄",
    "coordination.sync.ready": "🔄",
    "coordination.synthesis.completed": "✨",
    "coordination.synthesis.failed": "💥",
    # --- orchestrator / spec / ticket / task (legacy + spec lane) ---
    "orchestrator.dry_run.decision": "🔮",
    "spec.execution_started": "▶️ ",
    "spec.execution_completed": "✅",
    "spec.execution_failed": "❌",
    "spec.phase_started": "🎬",
    "spec.phase_completed": "🎬",
    "spec.phase_failed": "💥",
    "spec.phase_retry": "🔁",
    "spec.progress": "📈",
    "spec.eval_result": "🧪",
    "spec.artifact_created": "📦",
    "spec.requirements_generated": "📜",
    "spec.design_generated": "📐",
    "spec.tasks_generated": "🗂️ ",
    "spec.sync_started": "🔄",
    "spec.sync_completed": "🔄",
    "spec.tasks_queued": "📥",
    "spec.ticket_created": "🎫",
    "spec.ticket_updated": "🎫",
    "spec.task_created": "🆕",
    "spec.task_updated": "✏️ ",
    "ticket.blocked": "🚧",
    "ticket.unblocked": "✅",
    "ticket.phase_transitioned": "🔀",
    "ticket.status_transitioned": "🔁",
    "task.status.changed": "🔁",
    # --- legacy SystemEvent (event_stream.py firehose) ---
    "TASK_CREATED": "🔄",
    "TASK_ASSIGNED": "📋",
    "TASK_STARTED": "▶️ ",
    "TASK_COMPLETED": "✅",
    "TASK_FAILED": "❌",
    "TASK_VALIDATION_FAILED": "⚠️ ",
    "TASK_VALIDATION_PASSED": "✔️ ",
    "SANDBOX_SPAWNED": "🚀",
    "TICKET_CREATED": "🎫",
    "coordination.join": "🔀",
}


# ---- Colors ---------------------------------------------------------------

COLORS: dict[str, str] = {
    "reset": "\033[0m",
    "dim": "\033[2m",
    "bold": "\033[1m",
    "red": "\033[31m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "blue": "\033[34m",
    "magenta": "\033[35m",
    "cyan": "\033[36m",
    "white": "\033[37m",
    "bright_red": "\033[91m",
    "bright_green": "\033[92m",
    "bright_yellow": "\033[93m",
    "bright_blue": "\033[94m",
    "bright_magenta": "\033[95m",
    "bright_cyan": "\033[96m",
}

EVENT_COLORS: dict[str, str] = {
    # success / completion → green
    "session.created": "green",
    "session.started": "green",
    "session.completed": "green",
    "session.succeeded": "bright_green",
    "agent.completed": "green",
    "agent.turn_complete": "green",
    "agent.skill_completed": "bright_green",
    "agent.subagent_completed": "bright_green",
    "agent.command_completed": "dim",
    "agent.tool_completed": "dim",
    "spec.execution_completed": "green",
    "spec.phase_completed": "green",
    "ticket.unblocked": "green",
    # failure → red
    "session.failed": "red",
    "session.cancelled": "yellow",
    "agent.error": "red",
    "agent.stream_error": "red",
    "agent.failed": "red",
    "sandbox.failed": "red",
    "spec.execution_failed": "red",
    "spec.phase_failed": "red",
    "coordination.synthesis.failed": "red",
    # tools → cyan family
    "agent.tool_use": "cyan",
    "agent.tool_input_delta": "dim",
    "agent.tool_result": "dim",
    "agent.tool_result_delta": "dim",
    "agent.command_started": "cyan",
    "agent.file_written": "cyan",
    "agent.file_edited": "cyan",
    # skills + subagents → magenta (stand out)
    "agent.skill_invoked": "magenta",
    "agent.subagent_invoked": "bright_magenta",
    # plans → yellow (operator-facing, distinct from chat content)
    "agent.plan_created": "bright_yellow",
    "agent.plan_updated": "yellow",
    "agent.plan_delta": "dim",
    # thinking → dim
    "agent.thinking": "dim",
    "agent.thinking_delta": "dim",
    # roles
    "agent.user_message": "bright_blue",
    "agent.assistant_message": "bright_cyan",
    "agent.system_message": "dim",
    # lifecycle
    "agent.started": "blue",
    "agent.shutdown": "dim",
    "agent.heartbeat": "dim",
    "agent.waiting": "dim",
    "agent.processing": "blue",
    "agent.interrupted": "yellow",
    "agent.message_injected": "yellow",
    "agent.handoff.requested": "yellow",
    "agent.handoff.accepted": "green",
    "agent.handoff.declined": "red",
    "agent.collab.started": "blue",
    "agent.collab.ended": "dim",
    "agent.validation_feedback": "yellow",
    # system lane
    "sandbox.spawned": "magenta",
    "sandbox.terminated": "dim",
    "guardian.steering.intervention": "bright_yellow",
    "memory.context.suggested": "blue",
    "memory.pattern.learned": "blue",
    "memory.stored": "dim",
    "coordination.join.created": "magenta",
    "coordination.split.created": "yellow",
    "coordination.merge.completed": "green",
    "coordination.synthesis.completed": "bright_green",
    "orchestrator.dry_run.decision": "magenta",
    "spec.phase_started": "blue",
    "spec.execution_started": "blue",
    "spec.requirements_generated": "cyan",
    "spec.design_generated": "cyan",
    "spec.tasks_generated": "cyan",
    "ticket.blocked": "red",
    # legacy
    "TASK_CREATED": "cyan",
    "TASK_ASSIGNED": "blue",
    "TASK_STARTED": "green",
    "TASK_COMPLETED": "green",
    "TASK_FAILED": "red",
    "TASK_VALIDATION_FAILED": "yellow",
    "SANDBOX_SPAWNED": "magenta",
}


def color_for(event_type: str) -> str:
    name = EVENT_COLORS.get(event_type)
    if name is None:
        # Lane-based default color for unknown events.
        lane = lane_for(event_type)
        name = {
            LANE_CHAT: "reset",
            LANE_LIFECYCLE: "dim",
            LANE_SYSTEM: "blue",
        }.get(lane, "reset")
    return COLORS.get(name, "")


def icon_for(event_type: str) -> str:
    return EVENT_ICONS.get(event_type, "📌")


# ---- Timestamp + legacy formatters ---------------------------------------


def format_timestamp(ts: Optional[str] = None) -> str:
    """Format an ISO timestamp as local-tz HH:MM:SS, falling back to now()."""
    if ts:
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            if dt.tzinfo is not None:
                dt = dt.astimezone()
            return dt.strftime("%H:%M:%S")
        except (ValueError, TypeError):
            pass
    return datetime.now().strftime("%H:%M:%S")


def format_event_rich(event_data: dict[str, Any]) -> str:
    """Format a legacy SystemEvent payload (event_stream.py shape)."""
    event_type = event_data.get("event_type", "unknown")
    entity_type = event_data.get("entity_type", "")
    entity_id = event_data.get("entity_id", "")
    payload = event_data.get("payload", {}) or {}

    icon = icon_for(event_type)
    color = color_for(event_type)
    reset = COLORS["reset"]
    dim = COLORS["dim"]

    ts = format_timestamp(payload.get("timestamp"))
    entity_ref = f"{entity_type}/{entity_id[:8]}" if entity_id else entity_type

    details = ""
    if event_type == "orchestrator.dry_run.decision":
        selected = payload.get("selected_task", {}) or {}
        if selected:
            details = (
                f"task={selected.get('task_id', '')[:8]} "
                f"type={selected.get('task_type', '')}"
            )
    elif "description" in payload:
        desc = payload["description"]
        if len(desc) > 60:
            desc = desc[:57] + "..."
        details = f'"{desc}"'
    elif "error_message" in payload:
        details = f'error="{payload["error_message"][:50]}"'

    return f"{dim}[{ts}]{reset} {icon} {color}{event_type:<30}{reset} {entity_ref:<20} {details}"


def format_event_json(event_data: dict[str, Any]) -> str:
    return json.dumps(event_data, default=str)
