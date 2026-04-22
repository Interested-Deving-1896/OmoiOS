"""Branch strategy preview dataclasses for dry-run branch/merge analysis."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class BranchPreview:
    """Preview of a branch that would be created."""

    branch_name: str
    source_branch: str
    would_collide: bool
    ticket_type: str
    naming_rule: str


@dataclass
class ConflictPrediction:
    """Prediction of merge conflicts for a branch."""

    branch_name: str
    would_conflict: bool
    conflict_count: int
    conflict_files: list[str] = field(default_factory=list)


@dataclass
class MergePreview:
    """Preview of a convergence merge operation."""

    merge_order: list[str]
    conflict_predictions: dict[str, ConflictPrediction]
    total_predicted_conflicts: int
    would_succeed: bool
    requires_manual_review: bool
    recommendation: str  # "proceed" | "review" | "abort"


@dataclass
class BranchStrategyPreview:
    """Full branch strategy preview for a spec."""

    spec_id: str
    branches: list[BranchPreview]
    merge_preview: Optional[MergePreview] = None
    overall_recommendation: str = "proceed"
