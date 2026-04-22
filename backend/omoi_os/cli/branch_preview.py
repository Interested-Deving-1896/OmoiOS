"""CLI tool for previewing branch strategy.

Usage:
    python -m omoi_os.cli.branch_preview <spec_id>
    python -m omoi_os.cli.branch_preview --tasks '{"t1":"Auth middleware","t2":"Auth tests"}'
"""

from __future__ import annotations
import argparse
import json
import dataclasses
from omoi_os.services.branch_strategy_preview import BranchStrategyPreviewService
from omoi_os.services.branch_preview import BranchStrategyPreview


def format_preview(preview: BranchStrategyPreview) -> str:
    """Format branch strategy preview for terminal display."""
    lines = [f"\nBranch Strategy Preview (spec: {preview.spec_id})", "=" * 50, ""]

    lines.append("Branches:")
    for bp in preview.branches:
        collision = " ⚠️  COLLISION" if bp.would_collide else ""
        lines.append(f"  {bp.branch_name}{collision}")
        lines.append(f"    ← {bp.source_branch} (rule: {bp.naming_rule})")

    if preview.merge_preview:
        mp = preview.merge_preview
        lines.append("\nConvergence Merge:")
        lines.append(f"  merge order: {mp.merge_order}")
        lines.append(f"  predicted conflicts: {mp.total_predicted_conflicts}")
        status = "✅" if mp.would_succeed else "⚠️"
        lines.append(f"  recommendation: {mp.recommendation} {status}")

    lines.append(f"\nOverall: {preview.overall_recommendation}")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Preview branch strategy")
    parser.add_argument(
        "spec_id",
        nargs="?",
        default="preview",
        help="Spec ID to preview (default: 'preview')",
    )
    parser.add_argument(
        "--tasks", type=str, default=None, help="JSON dict of task_id:title pairs"
    )
    parser.add_argument(
        "--json", action="store_true", dest="json_output", help="Output as JSON"
    )

    args = parser.parse_args()
    service = BranchStrategyPreviewService()

    if args.tasks:
        task_dict = json.loads(args.tasks)
        tasks = [
            {"id": tid, "title": title, "type": "feature"}
            for tid, title in task_dict.items()
        ]
    else:
        tasks = [
            {"id": f"task-{i}", "title": f"Sample Task {i}", "type": "feature"}
            for i in range(1, 4)
        ]

    preview = service.preview_full_strategy(spec_id=args.spec_id, tasks=tasks)

    if args.json_output:
        print(json.dumps(dataclasses.asdict(preview), indent=2))
    else:
        print(format_preview(preview))


if __name__ == "__main__":
    main()
