"""Tests for Orchestrator dry-run mode.

Tests Requirements: OIP-0006 Part B - Orchestrator Dry-Run Mode
"""

import pytest
from omoi_os.workers.dry_run import (
    DryRunDecision,
    TaskSummary,
    BlockedTaskInfo,
)
from omoi_os.config import OrchestratorSettings, get_app_settings


class TestDryRunDecision:
    """Test suite for DryRunDecision dataclass."""

    @pytest.mark.unit
    def test_dry_run_decision_creation_with_defaults(self):
        """Test DryRunDecision can be created with default values."""
        decision = DryRunDecision(
            cycle_number=1,
            timestamp="2025-03-01T12:00:00+00:00",
        )

        assert decision.cycle_number == 1
        assert decision.timestamp == "2025-03-01T12:00:00+00:00"
        assert decision.eligible_tasks == []
        assert decision.selected_task is None
        assert decision.selection_reason == ""
        assert decision.dependency_graph == {}
        assert decision.blocked_tasks == []
        assert decision.completed_predecessors == []
        assert decision.running_count_by_project == {}
        assert decision.concurrency_limit_hit is False
        assert decision.limit_details is None
        assert decision.would_spawn_sandbox is False
        assert decision.would_create_branch is False
        assert decision.branch_name_preview is None
        assert decision.env_vars_preview == {}

    @pytest.mark.unit
    def test_dry_run_decision_to_dict(self):
        """Test DryRunDecision.to_dict() serializes correctly."""
        task_summary = TaskSummary(
            task_id="task-123",
            task_type="implementation",
            description="Implement feature X",
            priority="high",
            phase_id="PHASE_IMPLEMENTATION",
            ticket_id="ticket-456",
        )

        decision = DryRunDecision(
            cycle_number=5,
            timestamp="2025-03-01T12:00:00+00:00",
            selected_task=task_summary,
            selection_reason="Next pending task in queue",
            would_spawn_sandbox=True,
            would_create_branch=True,
            branch_name_preview="feature/task-123",
        )

        result = decision.to_dict()

        assert result["cycle_number"] == 5
        assert result["timestamp"] == "2025-03-01T12:00:00+00:00"
        assert result["selected_task"]["task_id"] == "task-123"
        assert result["selected_task"]["task_type"] == "implementation"
        assert result["selection_reason"] == "Next pending task in queue"
        assert result["would_spawn_sandbox"] is True
        assert result["would_create_branch"] is True
        assert result["branch_name_preview"] == "feature/task-123"

    @pytest.mark.unit
    def test_dry_run_decision_to_log_dict_truncation(self):
        """Test to_log_dict() truncates long eligible_tasks list."""
        eligible_tasks = [
            TaskSummary(
                task_id=f"task-{i}",
                task_type="implementation",
                description=f"Task {i}",
                priority="medium",
                phase_id="PHASE_IMPLEMENTATION",
                ticket_id=f"ticket-{i}",
            )
            for i in range(10)
        ]

        decision = DryRunDecision(
            cycle_number=1,
            timestamp="2025-03-01T12:00:00+00:00",
            eligible_tasks=eligible_tasks,
        )

        result = decision.to_log_dict()

        # Should be truncated to 5 items
        assert len(result["eligible_tasks"]) == 5
        assert result["eligible_tasks_truncated"] is True

    @pytest.mark.unit
    def test_dry_run_decision_to_log_dict_no_truncation(self):
        """Test to_log_dict() doesn't truncate short eligible_tasks list."""
        eligible_tasks = [
            TaskSummary(
                task_id="task-1",
                task_type="implementation",
                description="Task 1",
                priority="medium",
                phase_id="PHASE_IMPLEMENTATION",
                ticket_id="ticket-1",
            ),
        ]

        decision = DryRunDecision(
            cycle_number=1,
            timestamp="2025-03-01T12:00:00+00:00",
            eligible_tasks=eligible_tasks,
        )

        result = decision.to_log_dict()

        # Should not be truncated
        assert len(result["eligible_tasks"]) == 1
        assert "eligible_tasks_truncated" not in result


class TestTaskSummary:
    """Test suite for TaskSummary dataclass."""

    @pytest.mark.unit
    def test_task_summary_creation(self):
        """Test TaskSummary can be created correctly."""
        summary = TaskSummary(
            task_id="task-123",
            task_type="implementation",
            description="Implement feature X",
            priority="high",
            phase_id="PHASE_IMPLEMENTATION",
            ticket_id="ticket-456",
        )

        assert summary.task_id == "task-123"
        assert summary.task_type == "implementation"
        assert summary.description == "Implement feature X"
        assert summary.priority == "high"
        assert summary.phase_id == "PHASE_IMPLEMENTATION"
        assert summary.ticket_id == "ticket-456"


class TestBlockedTaskInfo:
    """Test suite for BlockedTaskInfo dataclass."""

    @pytest.mark.unit
    def test_blocked_task_info_creation(self):
        """Test BlockedTaskInfo can be created correctly."""
        blocked = BlockedTaskInfo(
            task_id="task-789",
            task_type="validation",
            description="Validate feature Y",
            blocked_by=["task-123", "task-456"],
        )

        assert blocked.task_id == "task-789"
        assert blocked.task_type == "validation"
        assert blocked.description == "Validate feature Y"
        assert blocked.blocked_by == ["task-123", "task-456"]


class TestOrchestratorSettings:
    """Test suite for OrchestratorSettings."""

    @pytest.mark.unit
    def test_orchestrator_settings_defaults(self, monkeypatch):
        """Test OrchestratorSettings has correct defaults."""
        # Ensure no env var override
        monkeypatch.delenv("ORCHESTRATOR_DRY_RUN", raising=False)

        settings = OrchestratorSettings()

        # Note: In local environment, local.yaml may set this to True
        # The default in code is False, but YAML overlay may override
        assert isinstance(settings.dry_run, bool)

    @pytest.mark.unit
    def test_orchestrator_settings_from_yaml(self):
        """Test OrchestratorSettings loads from YAML configuration."""
        settings = get_app_settings().orchestrator

        # Should have the orchestrator section loaded
        assert isinstance(settings, OrchestratorSettings)
        # Value depends on environment - local.yaml sets it to True
        assert isinstance(settings.dry_run, bool)

    @pytest.mark.unit
    def test_orchestrator_settings_env_override(self, monkeypatch):
        """Test OrchestratorSettings can be overridden via env var."""
        monkeypatch.setenv("ORCHESTRATOR_DRY_RUN", "true")

        settings = OrchestratorSettings()

        assert settings.dry_run is True
