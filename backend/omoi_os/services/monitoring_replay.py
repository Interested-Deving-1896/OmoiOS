"""Monitoring replay service for testing Guardian and Conductor without live agents.

Feeds recorded agent sessions to Guardian and Conductor so you can see their
scoring and intervention decisions without running live agents.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from omoi_os.logging import get_logger

logger = get_logger(__name__)


@dataclass
class AgentSessionSnapshot:
    """A recorded snapshot of agent state for monitoring replay."""

    agent_id: str
    task_id: str
    sandbox_id: str
    phase: str
    started_at: str
    events: list[dict] = field(default_factory=list)
    tool_calls: list[dict] = field(default_factory=list)
    current_output: str = ""
    task_description: str = ""
    elapsed_seconds: int = 0
    status: str = "running"  # "running" | "completed" | "failed"


@dataclass
class GuardianReplayResult:
    """Result of replaying a session through Guardian analysis."""

    session_file: str
    agent_id: str
    trajectory_score: float
    alignment_score: float
    would_intervene: bool
    intervention_type: Optional[str] = None
    intervention_recommendation: Optional[str] = None
    details: dict = field(default_factory=dict)


@dataclass
class ConductorReplayResult:
    """Result of replaying sessions through Conductor analysis."""

    sessions_analyzed: int
    coherence_score: float
    duplicates_detected: list[dict] = field(default_factory=list)
    coordination_issues: list[str] = field(default_factory=list)
    recommended_actions: list[str] = field(default_factory=list)


class MonitoringReplayService:
    """Feeds recorded agent sessions to Guardian and Conductor.

    Since Guardian and Conductor have complex dependencies (DatabaseService,
    LLMService, etc.), this replay service operates in standalone mode —
    it loads snapshots, analyzes them structurally, and produces results
    that mirror what Guardian/Conductor would output.

    For full Guardian/Conductor integration, use the real MonitoringLoop
    with replay_mode enabled.
    """

    def __init__(self, replay_dir: str = ".monitoring-recordings"):
        self._replay_dir = Path(replay_dir)

    def _load_snapshot(self, session_file: str) -> AgentSessionSnapshot:
        """Load an agent session snapshot from a JSON file."""
        path = Path(session_file)
        if not path.is_absolute() and not path.exists():
            path = self._replay_dir / path
        with open(path) as f:
            data = json.load(f)

        return AgentSessionSnapshot(
            **{
                k: v
                for k, v in data.items()
                if k in AgentSessionSnapshot.__dataclass_fields__
            }
        )

    def list_recordings(self) -> list[str]:
        """List all available recording files."""
        if not self._replay_dir.exists():
            return []
        recordings = []
        for p in sorted(self._replay_dir.rglob("*.json")):
            recordings.append(str(p.relative_to(self._replay_dir)))
        return recordings

    def replay_guardian(self, session_file: str) -> GuardianReplayResult:
        """Run structural Guardian analysis against a recorded session.

        Analyzes:
        - Event count vs elapsed time (activity rate)
        - Tool call patterns
        - Status progression
        - Output length as proxy for progress
        """
        snapshot = self._load_snapshot(session_file)

        # Structural trajectory analysis
        event_count = len(snapshot.events)
        tool_count = len(snapshot.tool_calls)
        elapsed = max(snapshot.elapsed_seconds, 1)

        # Activity rate: events per minute
        activity_rate = (event_count / elapsed) * 60

        # Alignment heuristic based on activity and output
        has_output = len(snapshot.current_output) > 0
        has_events = event_count > 0
        is_completed = snapshot.status == "completed"

        if is_completed:
            alignment = 0.95
        elif has_output and has_events:
            alignment = min(0.85, 0.5 + (activity_rate * 0.05))
        elif has_events:
            alignment = min(0.7, 0.3 + (activity_rate * 0.05))
        else:
            alignment = 0.2

        trajectory_score = alignment * 0.8 + (0.2 if has_output else 0.0)
        would_intervene = alignment < 0.6

        intervention_type = None
        intervention_rec = None
        if would_intervene:
            if not has_events:
                intervention_type = "restart"
                intervention_rec = "Agent appears stuck — no events recorded"
            elif not has_output:
                intervention_type = "redirect"
                intervention_rec = "Agent has events but no output — may be looping"
            else:
                intervention_type = "refocus"
                intervention_rec = "Low alignment score — agent may be drifting"

        return GuardianReplayResult(
            session_file=session_file,
            agent_id=snapshot.agent_id,
            trajectory_score=round(trajectory_score, 2),
            alignment_score=round(alignment, 2),
            would_intervene=would_intervene,
            intervention_type=intervention_type,
            intervention_recommendation=intervention_rec,
            details={
                "event_count": event_count,
                "tool_calls": tool_count,
                "elapsed_seconds": elapsed,
                "activity_rate_per_min": round(activity_rate, 1),
                "status": snapshot.status,
            },
        )

    def replay_conductor(self, session_files: list[str]) -> ConductorReplayResult:
        """Run structural Conductor analysis across multiple sessions.

        Analyzes:
        - Cross-agent task description overlap
        - File edit overlap detection via tool calls
        - Overall system coherence
        """
        snapshots = [self._load_snapshot(f) for f in session_files]

        if not snapshots:
            return ConductorReplayResult(
                sessions_analyzed=0,
                coherence_score=1.0,
            )

        # Detect duplicates by comparing task descriptions
        duplicates = []
        descriptions = {s.agent_id: s.task_description for s in snapshots}
        agent_ids = list(descriptions.keys())

        for i in range(len(agent_ids)):
            for j in range(i + 1, len(agent_ids)):
                a1, a2 = agent_ids[i], agent_ids[j]
                d1, d2 = descriptions[a1].lower(), descriptions[a2].lower()
                # Simple word overlap check
                words1 = set(d1.split())
                words2 = set(d2.split())
                if words1 and words2:
                    overlap = len(words1 & words2) / max(len(words1 | words2), 1)
                    if overlap > 0.5:
                        duplicates.append(
                            {
                                "agent1": a1,
                                "agent2": a2,
                                "overlap_score": round(overlap, 2),
                                "description1": descriptions[a1][:100],
                                "description2": descriptions[a2][:100],
                            }
                        )

        # Detect file edit overlaps via tool calls
        coordination_issues = []
        agent_files: dict[str, set[str]] = {}
        for s in snapshots:
            files = set()
            for tc in s.tool_calls:
                if isinstance(tc, dict):
                    f = tc.get("file") or tc.get("path") or ""
                    if f:
                        files.add(f)
            agent_files[s.agent_id] = files

        for i in range(len(agent_ids)):
            for j in range(i + 1, len(agent_ids)):
                a1, a2 = agent_ids[i], agent_ids[j]
                shared = agent_files.get(a1, set()) & agent_files.get(a2, set())
                if shared:
                    coordination_issues.append(
                        f"{a1} and {a2} both editing: {', '.join(sorted(shared)[:3])}"
                    )

        # Coherence score
        n = len(snapshots)
        dup_penalty = len(duplicates) * 0.1
        issue_penalty = len(coordination_issues) * 0.05
        coherence = max(0.0, min(1.0, 1.0 - dup_penalty - issue_penalty))

        actions = []
        for dup in duplicates:
            actions.append(
                f"Review potential duplicate work: {dup['agent1']} ↔ {dup['agent2']}"
            )
        for issue in coordination_issues:
            actions.append(f"Coordinate: {issue}")

        return ConductorReplayResult(
            sessions_analyzed=n,
            coherence_score=round(coherence, 2),
            duplicates_detected=duplicates,
            coordination_issues=coordination_issues,
            recommended_actions=actions,
        )


class AgentSessionRecorder:
    """Records agent session snapshots to disk for later replay."""

    def __init__(self, recording_dir: str = ".monitoring-recordings"):
        self._recording_dir = Path(recording_dir) / "agent-sessions"
        self._recording_dir.mkdir(parents=True, exist_ok=True)
        self._active_sessions: dict[str, AgentSessionSnapshot] = {}

    def start_session(
        self,
        agent_id: str,
        task_id: str,
        sandbox_id: str,
        phase: str,
        task_description: str,
    ) -> None:
        """Start recording a new agent session."""
        from omoi_os.utils.datetime import utc_now

        self._active_sessions[agent_id] = AgentSessionSnapshot(
            agent_id=agent_id,
            task_id=task_id,
            sandbox_id=sandbox_id,
            phase=phase,
            started_at=utc_now().isoformat(),
            task_description=task_description,
        )

    def record_event(self, agent_id: str, event: dict) -> None:
        """Record an event for an active session."""
        if agent_id in self._active_sessions:
            self._active_sessions[agent_id].events.append(event)

    def record_tool_call(self, agent_id: str, tool_call: dict) -> None:
        """Record a tool call for an active session."""
        if agent_id in self._active_sessions:
            self._active_sessions[agent_id].tool_calls.append(tool_call)

    def update_output(self, agent_id: str, output: str) -> None:
        """Update the current output for an active session."""
        if agent_id in self._active_sessions:
            self._active_sessions[agent_id].current_output = output

    def end_session(self, agent_id: str, status: str = "completed") -> Optional[str]:
        """End a session and save to disk. Returns the file path."""
        if agent_id not in self._active_sessions:
            return None

        session = self._active_sessions.pop(agent_id)
        session.status = status

        # Calculate elapsed (approximate)
        session.elapsed_seconds = max(1, len(session.events) * 2)

        filename = f"{agent_id}-{session.task_id[:8]}.json"
        filepath = self._recording_dir / filename

        import dataclasses

        with open(filepath, "w") as f:
            json.dump(dataclasses.asdict(session), f, indent=2)

        return str(filepath)

    def list_active(self) -> list[str]:
        """List active session agent IDs."""
        return list(self._active_sessions.keys())
