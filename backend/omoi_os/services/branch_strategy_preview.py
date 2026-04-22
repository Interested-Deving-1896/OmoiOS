"""Branch strategy preview service for local development.

Provides dry-run branch and merge previews without requiring
GitHub API or Daytona sandbox connections.
"""

from __future__ import annotations
import re
from typing import Optional
from omoi_os.services.branch_preview import (
    BranchPreview,
    ConflictPrediction,
    MergePreview,
    BranchStrategyPreview,
)
from omoi_os.logging import get_logger

logger = get_logger(__name__)

# Copy of TYPE_PREFIX_MAP from branch_workflow.py
TYPE_PREFIX_MAP = {
    "feature": "feature",
    "bug": "fix",
    "refactor": "refactor",
    "docs": "docs",
    "test": "test",
    "chore": "chore",
}


class BranchStrategyPreviewService:
    """Preview branch strategy without hitting GitHub or Daytona."""

    def __init__(self, max_conflicts_auto_resolve: int = 10):
        self._max_conflicts = max_conflicts_auto_resolve

    def preview_branch_creation(
        self,
        ticket_id: str,
        ticket_title: str,
        ticket_type: str = "feature",
        priority: Optional[str] = None,
        source_branch: str = "main",
        existing_branches: Optional[list[str]] = None,
    ) -> BranchPreview:
        """Preview what branch would be created for a ticket."""
        existing_branches = existing_branches or []

        # Determine prefix
        if ticket_type == "bug" and priority == "critical":
            prefix = "hotfix"
        else:
            prefix = TYPE_PREFIX_MAP.get(ticket_type, "feature")

        # Generate slug
        slug = re.sub(r"[^a-zA-Z0-9\s-]", "", ticket_title.lower())
        slug = re.sub(r"\s+", "-", slug.strip())
        slug = slug[:25].rstrip("-")

        branch_name = f"{prefix}/{ticket_id}-{slug}"
        would_collide = branch_name in existing_branches

        return BranchPreview(
            branch_name=branch_name,
            source_branch=source_branch,
            would_collide=would_collide,
            ticket_type=ticket_type,
            naming_rule=f"{prefix}/{{ticket_id}}-{{slug}}",
        )

    def preview_merge_strategy(
        self,
        task_branches: dict[str, str],  # task_id -> branch_name
    ) -> MergePreview:
        """Preview merge strategy for multiple task branches.

        Since we can't run git merge-tree without a real repo, this
        generates a structural preview based on branch names and order.
        """
        # Sort by branch name for deterministic ordering
        merge_order = sorted(task_branches.keys())

        predictions = {}
        for task_id in merge_order:
            branch_name = task_branches[task_id]
            predictions[task_id] = ConflictPrediction(
                branch_name=branch_name,
                would_conflict=False,  # Can't predict without repo
                conflict_count=0,
                conflict_files=[],
            )

        return MergePreview(
            merge_order=merge_order,
            conflict_predictions=predictions,
            total_predicted_conflicts=0,
            would_succeed=True,
            requires_manual_review=False,
            recommendation="proceed",
        )

    def preview_full_strategy(
        self,
        spec_id: str,
        tasks: list[dict],  # List of task dicts with id, title, type, priority
        source_branch: str = "main",
    ) -> BranchStrategyPreview:
        """Generate full branch strategy preview for a spec."""
        branches = []
        task_branches = {}

        for task in tasks:
            bp = self.preview_branch_creation(
                ticket_id=task.get("id", "unknown"),
                ticket_title=task.get("title", task.get("description", "untitled")),
                ticket_type=task.get("type", "feature"),
                priority=task.get("priority"),
                source_branch=source_branch,
            )
            branches.append(bp)
            task_branches[task.get("id", "unknown")] = bp.branch_name

        merge_preview = None
        if len(task_branches) > 1:
            merge_preview = self.preview_merge_strategy(task_branches)

        return BranchStrategyPreview(
            spec_id=spec_id,
            branches=branches,
            merge_preview=merge_preview,
            overall_recommendation="proceed",
        )
