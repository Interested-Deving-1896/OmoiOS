"""CLI tool for replaying monitoring sessions.

Usage:
    python -m omoi_os.cli.monitoring_replay guardian <session_file>
    python -m omoi_os.cli.monitoring_replay conductor <session_dir>
    python -m omoi_os.cli.monitoring_replay list [--dir=.monitoring-recordings]
"""

from __future__ import annotations

import argparse
import json
import sys
import dataclasses
from pathlib import Path

from omoi_os.services.monitoring_replay import MonitoringReplayService


def cmd_guardian(args, service: MonitoringReplayService):
    """Replay Guardian analysis on a recorded session."""
    result = service.replay_guardian(args.session_file)

    if args.json_output:
        print(json.dumps(dataclasses.asdict(result), indent=2))
        return

    print(f"\nGuardian Replay: {result.agent_id}")
    print("=" * 40)
    print(f"  Trajectory Score: {result.trajectory_score}")
    print(f"  Alignment: {result.alignment_score}")
    print(f"  Would Intervene: {'Yes' if result.would_intervene else 'No'}")
    if result.intervention_type:
        print(f"  Intervention: {result.intervention_type}")
        print(f"  Recommendation: {result.intervention_recommendation}")
    details = result.details
    print(f"  Events: {details.get('event_count', 0)}")
    print(f"  Tool Calls: {details.get('tool_calls', 0)}")
    print(f"  Elapsed: {details.get('elapsed_seconds', 0)}s")
    print(f"  Activity Rate: {details.get('activity_rate_per_min', 0)}/min")


def cmd_conductor(args, service: MonitoringReplayService):
    """Replay Conductor analysis across sessions."""
    session_dir = Path(args.session_dir)
    if session_dir.is_file():
        files = [str(session_dir)]
    elif session_dir.is_dir():
        files = [str(p) for p in sorted(session_dir.glob("*.json"))]
    else:
        print(f"Error: {session_dir} is not a file or directory", file=sys.stderr)
        sys.exit(1)

    if not files:
        print("No session files found", file=sys.stderr)
        sys.exit(1)

    result = service.replay_conductor(files)

    if args.json_output:
        print(json.dumps(dataclasses.asdict(result), indent=2))
        return

    print(f"\nConductor Replay: {result.sessions_analyzed} sessions")
    print("=" * 40)
    print(f"  Coherence Score: {result.coherence_score}")
    if result.duplicates_detected:
        print(f"  Duplicates: {len(result.duplicates_detected)}")
        for dup in result.duplicates_detected:
            print(
                f"    {dup['agent1']} ↔ {dup['agent2']} (overlap: {dup['overlap_score']})"
            )
    if result.coordination_issues:
        print(f"  Coordination Issues: {len(result.coordination_issues)}")
        for issue in result.coordination_issues:
            print(f"    - {issue}")
    if result.recommended_actions:
        print("  Recommended Actions:")
        for action in result.recommended_actions:
            print(f"    - {action}")


def cmd_list(args, service: MonitoringReplayService):
    """List available recordings."""
    recordings = service.list_recordings()
    if not recordings:
        print("No recordings found.")
        return
    print(f"\nAvailable recordings ({len(recordings)}):")
    for r in recordings:
        print(f"  {r}")


def main():
    parser = argparse.ArgumentParser(description="Monitoring replay tool")
    parser.add_argument(
        "--dir", default=".monitoring-recordings", help="Recording directory"
    )
    parser.add_argument(
        "--json", action="store_true", dest="json_output", help="Output as JSON"
    )

    subparsers = parser.add_subparsers(dest="command")

    guard_parser = subparsers.add_parser("guardian", help="Replay Guardian analysis")
    guard_parser.add_argument("session_file", help="Path to session JSON file")

    cond_parser = subparsers.add_parser("conductor", help="Replay Conductor analysis")
    cond_parser.add_argument("session_dir", help="Path to session file or directory")

    subparsers.add_parser("list", help="List available recordings")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    service = MonitoringReplayService(replay_dir=args.dir)

    if args.command == "guardian":
        cmd_guardian(args, service)
    elif args.command == "conductor":
        cmd_conductor(args, service)
    elif args.command == "list":
        cmd_list(args, service)


if __name__ == "__main__":
    main()
