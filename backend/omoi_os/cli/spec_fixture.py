"""CLI for running spec pipeline in fixture mode.

Usage:
    python -m omoi_os.cli.spec_fixture run-all
    python -m omoi_os.cli.spec_fixture run-phase explore
    python -m omoi_os.cli.spec_fixture validate
    python -m omoi_os.cli.spec_fixture list
"""

import argparse
import asyncio
import sys

from omoi_os.services.fixture_phase_runner import FixturePhaseRunner, PhaseResult


def _get_fixture_dir() -> str:
    """Get fixture directory from settings."""
    try:
        from omoi_os.config import get_app_settings

        return get_app_settings().spec.fixture_dir
    except Exception:
        return "subsystems/spec-sandbox/.claude/skills/spec-driven-dev/references"


def _format_result(result: PhaseResult) -> str:
    """Format a phase result for terminal display."""
    icon = "✅" if result.passed else "❌"
    line = f"  {icon} Phase: {result.phase:<15} score={result.score:.2f}"
    if result.issues:
        line += f"  issues={len(result.issues)}"
    if result.error:
        line += f"  error: {result.error}"
    return line


async def cmd_run_all(args):
    runner = FixturePhaseRunner(fixture_dir=args.fixture_dir)
    result = await runner.run_full_pipeline()

    print("\nSpec Pipeline Fixture Run")
    print(f"{'=' * 50}")
    for r in result.results:
        print(_format_result(r))

    print(f"\n{'=' * 50}")
    if result.all_passed:
        print(f"✅ All {len(result.phases_passed)} phases passed")
    else:
        print(f"❌ {len(result.phases_passed)}/{len(result.phases_run)} phases passed")

    return 0 if result.all_passed else 1


async def cmd_run_phase(args):
    runner = FixturePhaseRunner(fixture_dir=args.fixture_dir)
    result = await runner.run_phase(args.phase)
    print(_format_result(result))
    if result.issues:
        for issue in result.issues:
            print(f"    ⚠️  {issue}")
    return 0 if result.passed else 1


async def cmd_list(args):
    runner = FixturePhaseRunner(fixture_dir=args.fixture_dir)
    fixtures = runner.list_available_fixtures()
    print(f"\nAvailable fixtures in {args.fixture_dir}:")
    for f in fixtures:
        print(f"  • {f}")
    if not fixtures:
        print("  (none found)")
    return 0


async def cmd_validate(args):
    """Validate all fixtures have expected structure."""
    runner = FixturePhaseRunner(fixture_dir=args.fixture_dir)
    fixtures = runner.list_available_fixtures()
    all_ok = True

    print(f"\nValidating fixtures in {args.fixture_dir}:")
    for phase in fixtures:
        result = await runner.run_phase(phase)
        print(_format_result(result))
        if not result.passed:
            all_ok = False

    return 0 if all_ok else 1


def main():
    parser = argparse.ArgumentParser(description="Run spec pipeline in fixture mode")
    parser.add_argument(
        "--fixture-dir",
        default=_get_fixture_dir(),
        help="Directory containing fixture JSON files",
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    subparsers.add_parser("run-all", help="Run all phases against fixtures")

    run_phase = subparsers.add_parser("run-phase", help="Run a single phase")
    run_phase.add_argument(
        "phase", choices=["explore", "requirements", "design", "tasks"]
    )

    subparsers.add_parser("list", help="List available fixtures")
    subparsers.add_parser("validate", help="Validate all fixtures")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    commands = {
        "run-all": cmd_run_all,
        "run-phase": cmd_run_phase,
        "list": cmd_list,
        "validate": cmd_validate,
    }

    exit_code = asyncio.run(commands[args.command](args))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
