"""Tests for branch strategy preview."""

import json
import dataclasses
from omoi_os.services.branch_preview import (
    BranchPreview,
    ConflictPrediction,
    MergePreview,
    BranchStrategyPreview,
)
from omoi_os.services.branch_strategy_preview import BranchStrategyPreviewService


class TestBranchPreview:
    def test_creation(self):
        bp = BranchPreview(
            branch_name="feature/123-auth",
            source_branch="main",
            would_collide=False,
            ticket_type="feature",
            naming_rule="feature/{ticket_id}-{slug}",
        )
        assert bp.branch_name == "feature/123-auth"
        assert not bp.would_collide

    def test_collision(self):
        bp = BranchPreview(
            branch_name="feature/123-auth",
            source_branch="main",
            would_collide=True,
            ticket_type="feature",
            naming_rule="feature/{ticket_id}-{slug}",
        )
        assert bp.would_collide


class TestConflictPrediction:
    def test_no_conflict(self):
        cp = ConflictPrediction(
            branch_name="feature/1-auth", would_conflict=False, conflict_count=0
        )
        assert not cp.would_conflict
        assert cp.conflict_files == []

    def test_with_conflicts(self):
        cp = ConflictPrediction(
            branch_name="feature/1-auth",
            would_conflict=True,
            conflict_count=2,
            conflict_files=["src/auth.py", "src/routes.py"],
        )
        assert cp.conflict_count == 2


class TestMergePreview:
    def test_successful_merge(self):
        mp = MergePreview(
            merge_order=["t1", "t2"],
            conflict_predictions={},
            total_predicted_conflicts=0,
            would_succeed=True,
            requires_manual_review=False,
            recommendation="proceed",
        )
        assert mp.would_succeed
        assert mp.recommendation == "proceed"


class TestBranchStrategyPreviewService:
    def test_preview_branch_creation_feature(self):
        svc = BranchStrategyPreviewService()
        bp = svc.preview_branch_creation(
            ticket_id="123",
            ticket_title="Add user authentication",
            ticket_type="feature",
        )
        assert bp.branch_name == "feature/123-add-user-authentication"
        assert bp.source_branch == "main"
        assert not bp.would_collide

    def test_preview_branch_creation_bug(self):
        svc = BranchStrategyPreviewService()
        bp = svc.preview_branch_creation(
            ticket_id="456",
            ticket_title="Fix login redirect",
            ticket_type="bug",
        )
        assert bp.branch_name.startswith("fix/")

    def test_preview_branch_creation_hotfix(self):
        svc = BranchStrategyPreviewService()
        bp = svc.preview_branch_creation(
            ticket_id="789",
            ticket_title="Critical auth bypass",
            ticket_type="bug",
            priority="critical",
        )
        assert bp.branch_name.startswith("hotfix/")

    def test_preview_branch_collision(self):
        svc = BranchStrategyPreviewService()
        bp = svc.preview_branch_creation(
            ticket_id="123",
            ticket_title="Add auth",
            existing_branches=["feature/123-add-auth"],
        )
        assert bp.would_collide

    def test_preview_merge_strategy(self):
        svc = BranchStrategyPreviewService()
        mp = svc.preview_merge_strategy(
            {
                "t1": "feature/t1-auth",
                "t2": "feature/t2-tests",
            }
        )
        assert len(mp.merge_order) == 2
        assert mp.would_succeed

    def test_preview_full_strategy(self):
        svc = BranchStrategyPreviewService()
        tasks = [
            {"id": "t1", "title": "Auth middleware", "type": "feature"},
            {"id": "t2", "title": "Auth tests", "type": "test"},
        ]
        preview = svc.preview_full_strategy(spec_id="spec-1", tasks=tasks)
        assert preview.spec_id == "spec-1"
        assert len(preview.branches) == 2
        assert preview.merge_preview is not None

    def test_preview_single_task_no_merge(self):
        svc = BranchStrategyPreviewService()
        tasks = [{"id": "t1", "title": "Solo task", "type": "feature"}]
        preview = svc.preview_full_strategy(spec_id="spec-1", tasks=tasks)
        assert preview.merge_preview is None

    def test_serializable(self):
        svc = BranchStrategyPreviewService()
        tasks = [
            {"id": "t1", "title": "Auth", "type": "feature"},
            {"id": "t2", "title": "Tests", "type": "test"},
        ]
        preview = svc.preview_full_strategy(spec_id="spec-1", tasks=tasks)
        result = dataclasses.asdict(preview)
        # Should be JSON serializable
        json.dumps(result)


class TestBranchPreviewCLI:
    def test_format_preview(self):
        from omoi_os.cli.branch_preview import format_preview

        preview = BranchStrategyPreview(
            spec_id="test-spec",
            branches=[
                BranchPreview(
                    branch_name="feature/t1-auth",
                    source_branch="main",
                    would_collide=False,
                    ticket_type="feature",
                    naming_rule="feature/{ticket_id}-{slug}",
                )
            ],
        )
        output = format_preview(preview)
        assert "test-spec" in output
        assert "feature/t1-auth" in output
