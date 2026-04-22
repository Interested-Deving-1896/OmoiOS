"""CLI tool for inspecting task context.

Usage:
    python -m omoi_os.cli.inspect_context <task_id>
    python -m omoi_os.cli.inspect_context <task_id> --json
    python -m omoi_os.cli.inspect_context <task_id> --base64
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import sys
from typing import Optional

from omoi_os.config import get_app_settings
from omoi_os.services.database import DatabaseService
from omoi_os.services.task_context_builder import TaskContextBuilder


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser for the CLI."""
    parser = argparse.ArgumentParser(
        prog="omoi-inspect-context",
        description="Inspect the task context that would be sent to an agent",
    )
    parser.add_argument(
        "task_id",
        help="The ID of the task to inspect",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON (equivalent to --format json)",
    )
    parser.add_argument(
        "--base64",
        action="store_true",
        help="Output as base64 (equivalent to --format base64)",
    )
    parser.add_argument(
        "--format",
        type=str,
        choices=["markdown", "json", "base64"],
        default="markdown",
        help="Output format (default: markdown)",
    )
    return parser


async def inspect_task(task_id: str, format: str) -> str:
    """Inspect task context and return the formatted output.

    Args:
        task_id: The ID of the task to inspect
        format: Output format (markdown, json, or base64)

    Returns:
        Formatted context string

    Raises:
        ValueError: If task not found
        ConnectionError: If database is not available
    """
    # Get database connection string from settings
    settings = get_app_settings()

    # Create database service
    db = DatabaseService(connection_string=settings.database.url)

    try:
        # Create context builder
        context_builder = TaskContextBuilder(db=db)

        # Build context
        full_context = await context_builder.build_context(task_id)

        # Format output based on requested format
        if format == "markdown":
            return full_context.to_markdown()
        elif format == "json":
            return json.dumps(full_context.to_dict(), indent=2)
        elif format == "base64":
            task_data = full_context.to_dict()
            task_data["_markdown_context"] = full_context.to_markdown()
            task_data_json = json.dumps(task_data)
            encoded = base64.b64encode(task_data_json.encode()).decode()
            return encoded
        else:
            raise ValueError(f"Invalid format: {format}")

    except Exception as e:
        # Re-raise with better error message
        if "connection" in str(e).lower() or "could not connect" in str(e).lower():
            raise ConnectionError(
                "Database connection failed. Is PostgreSQL running on port 15432?"
            ) from e
        raise


async def main_async(args: Optional[list[str]] = None) -> int:
    """Async main entry point."""
    parser = create_parser()
    parsed = parser.parse_args(args)

    # Determine format from flags or --format option
    if parsed.json:
        output_format = "json"
    elif parsed.base64:
        output_format = "base64"
    else:
        output_format = parsed.format

    task_id = parsed.task_id

    try:
        output = await inspect_task(task_id, output_format)
        print(output)
        return 0
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except ConnectionError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        return 3


def main(args: Optional[list[str]] = None) -> int:
    """Main entry point."""
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    sys.exit(main())
