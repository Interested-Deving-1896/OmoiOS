"""Dev environment bootstrap and health checking.

Usage:
    python -m omoi_os.cli.bootstrap check     # Check all dependencies
    python -m omoi_os.cli.bootstrap health     # Live health dashboard
"""

from __future__ import annotations

import argparse
import asyncio
import os
import socket
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class DependencyCheck:
    """Represents the status of a single dependency check."""

    name: str
    status: str  # "ok" | "missing" | "wrong_version" | "not_configured"
    required: bool  # True = hard dependency, False = optional
    details: str  # Human-readable explanation
    fix_command: str  # Command to fix the issue
    category: str  # "runtime" | "database" | "service" | "config"


@dataclass
class BootstrapReport:
    """Complete bootstrap check report."""

    checks: list[DependencyCheck] = field(default_factory=list)

    @property
    def all_required_ok(self) -> bool:
        """Check if all required dependencies are satisfied."""
        return all(
            c.status == "ok" or not c.required
            for c in self.checks
            if c.category != "config"  # Config warnings don't block
        )

    @property
    def has_warnings(self) -> bool:
        """Check if there are any warnings (optional deps missing)."""
        return any(c.status != "ok" and not c.required for c in self.checks)

    def get_by_category(self, category: str) -> list[DependencyCheck]:
        """Get all checks for a specific category."""
        return [c for c in self.checks if c.category == category]


class BootstrapChecker:
    """Checks development environment dependencies."""

    def __init__(self):
        self.report = BootstrapReport()

    async def check_all(self) -> BootstrapReport:
        """Run all dependency checks and return the report."""
        self.report = BootstrapReport()

        # Runtime checks
        await self._check_python()
        await self._check_node()
        await self._check_docker()
        await self._check_uv()

        # Database checks
        await self._check_postgres()
        await self._check_redis()

        # Configuration checks
        await self._check_env_file()
        await self._check_llm_key()
        await self._check_github_token()
        await self._check_claude_key()
        await self._check_daytona_key()

        # Python environment checks
        await self._check_python_deps()
        await self._check_migrations()

        return self.report

    async def _run_command(
        self,
        *cmd: str,
        timeout: float = 5.0,
        capture_stderr: bool = False,
    ) -> tuple[int, str, str]:
        """Run a command asynchronously and return (returncode, stdout, stderr)."""
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE if capture_stderr else None,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            return (
                proc.returncode or 0,
                stdout.decode().strip() if stdout else "",
                stderr.decode().strip() if stderr else "",
            )
        except asyncio.TimeoutError:
            return 1, "", "Command timed out"
        except FileNotFoundError:
            return 127, "", f"Command not found: {cmd[0]}"
        except Exception as e:
            return 1, "", str(e)

    async def _check_python(self) -> None:
        """Check Python version (3.12+ required)."""
        version_info = sys.version_info
        version_str = f"{version_info.major}.{version_info.minor}.{version_info.micro}"

        if version_info >= (3, 12):
            self.report.checks.append(
                DependencyCheck(
                    name="Python",
                    status="ok",
                    required=True,
                    details=f"{version_str}",
                    fix_command="",
                    category="runtime",
                )
            )
        else:
            self.report.checks.append(
                DependencyCheck(
                    name="Python",
                    status="wrong_version",
                    required=True,
                    details=f"{version_str} (3.12+ required)",
                    fix_command="Install Python 3.12 or later (e.g., 'brew install python@3.12')",
                    category="runtime",
                )
            )

    async def _check_node(self) -> None:
        """Check Node.js installation and version."""
        returncode, stdout, stderr = await self._run_command("node", "--version")

        if returncode == 0 and stdout.startswith("v"):
            version = stdout[1:]  # Remove 'v' prefix
            major_version = int(version.split(".")[0])

            if major_version >= 20:
                self.report.checks.append(
                    DependencyCheck(
                        name="Node.js",
                        status="ok",
                        required=True,
                        details=version,
                        fix_command="",
                        category="runtime",
                    )
                )
            else:
                self.report.checks.append(
                    DependencyCheck(
                        name="Node.js",
                        status="wrong_version",
                        required=True,
                        details=f"{version} (20+ recommended)",
                        fix_command="Install Node.js 20+ (e.g., 'brew install node@20')",
                        category="runtime",
                    )
                )
        else:
            self.report.checks.append(
                DependencyCheck(
                    name="Node.js",
                    status="missing",
                    required=True,
                    details="Not installed",
                    fix_command="Install Node.js (e.g., 'brew install node')",
                    category="runtime",
                )
            )

    async def _check_docker(self) -> None:
        """Check Docker installation."""
        returncode, stdout, _ = await self._run_command("docker", "--version")

        if returncode == 0:
            # Parse version from "Docker version 24.0.7, build ..."
            parts = stdout.split()
            version = parts[2].rstrip(",") if len(parts) >= 3 else "installed"

            self.report.checks.append(
                DependencyCheck(
                    name="Docker",
                    status="ok",
                    required=True,
                    details=version,
                    fix_command="",
                    category="runtime",
                )
            )
        else:
            self.report.checks.append(
                DependencyCheck(
                    name="Docker",
                    status="missing",
                    required=True,
                    details="Not installed",
                    fix_command="Install Docker Desktop (https://www.docker.com/products/docker-desktop)",
                    category="runtime",
                )
            )

    async def _check_uv(self) -> None:
        """Check uv (Python package manager) installation."""
        returncode, stdout, _ = await self._run_command("uv", "--version")

        if returncode == 0:
            version = stdout.strip()
            self.report.checks.append(
                DependencyCheck(
                    name="uv",
                    status="ok",
                    required=True,
                    details=version,
                    fix_command="",
                    category="runtime",
                )
            )
        else:
            self.report.checks.append(
                DependencyCheck(
                    name="uv",
                    status="missing",
                    required=True,
                    details="Not installed",
                    fix_command="Install uv (e.g., 'curl -LsSf https://astral.sh/uv/install.sh | sh')",
                    category="runtime",
                )
            )

    async def _check_postgres(self) -> None:
        """Check PostgreSQL connectivity on port 15432."""
        # First try pg_isready
        returncode, stdout, _ = await self._run_command(
            "pg_isready", "-h", "localhost", "-p", "15432", timeout=3.0
        )

        if returncode == 0:
            self.report.checks.append(
                DependencyCheck(
                    name="PostgreSQL",
                    status="ok",
                    required=True,
                    details="Running on :15432",
                    fix_command="",
                    category="database",
                )
            )
            return

        # Fallback: check if port is listening
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2.0)
            result = sock.connect_ex(("localhost", 15432))
            sock.close()

            if result == 0:
                self.report.checks.append(
                    DependencyCheck(
                        name="PostgreSQL",
                        status="ok",
                        required=True,
                        details="Port :15432 is listening",
                        fix_command="",
                        category="database",
                    )
                )
            else:
                self.report.checks.append(
                    DependencyCheck(
                        name="PostgreSQL",
                        status="missing",
                        required=True,
                        details="Not running on :15432",
                        fix_command="Start PostgreSQL: 'just docker-up' or 'docker-compose up -d postgres'",
                        category="database",
                    )
                )
        except Exception as e:
            self.report.checks.append(
                DependencyCheck(
                    name="PostgreSQL",
                    status="missing",
                    required=True,
                    details=f"Connection failed: {e}",
                    fix_command="Start PostgreSQL: 'just docker-up' or 'docker-compose up -d postgres'",
                    category="database",
                )
            )

    async def _check_redis(self) -> None:
        """Check Redis connectivity on port 16379."""
        # Try redis-cli first
        returncode, stdout, _ = await self._run_command(
            "redis-cli", "-p", "16379", "ping", timeout=3.0
        )

        if returncode == 0 and "PONG" in stdout.upper():
            self.report.checks.append(
                DependencyCheck(
                    name="Redis",
                    status="ok",
                    required=True,
                    details="Running on :16379",
                    fix_command="",
                    category="database",
                )
            )
            return

        # Fallback: check if port is listening
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2.0)
            result = sock.connect_ex(("localhost", 16379))
            sock.close()

            if result == 0:
                self.report.checks.append(
                    DependencyCheck(
                        name="Redis",
                        status="ok",
                        required=True,
                        details="Port :16379 is listening",
                        fix_command="",
                        category="database",
                    )
                )
            else:
                self.report.checks.append(
                    DependencyCheck(
                        name="Redis",
                        status="missing",
                        required=True,
                        details="Not running on :16379",
                        fix_command="Start Redis: 'just docker-up' or 'docker-compose up -d redis'",
                        category="database",
                    )
                )
        except Exception as e:
            self.report.checks.append(
                DependencyCheck(
                    name="Redis",
                    status="missing",
                    required=True,
                    details=f"Connection failed: {e}",
                    fix_command="Start Redis: 'just docker-up' or 'docker-compose up -d redis'",
                    category="database",
                )
            )

    async def _check_env_file(self) -> None:
        """Check if .env or .env.local exists."""
        env_exists = Path(".env").exists()
        env_local_exists = Path(".env.local").exists()

        if env_local_exists:
            self.report.checks.append(
                DependencyCheck(
                    name=".env file",
                    status="ok",
                    required=False,
                    details="Found .env.local",
                    fix_command="",
                    category="config",
                )
            )
        elif env_exists:
            self.report.checks.append(
                DependencyCheck(
                    name=".env file",
                    status="ok",
                    required=False,
                    details="Found .env (create .env.local for overrides)",
                    fix_command="",
                    category="config",
                )
            )
        else:
            self.report.checks.append(
                DependencyCheck(
                    name=".env file",
                    status="not_configured",
                    required=False,
                    details="No .env or .env.local found",
                    fix_command="cp .env.example .env.local  # Then edit with your settings",
                    category="config",
                )
            )

    async def _check_llm_key(self) -> None:
        """Check LLM API key configuration."""
        # Try to load settings safely (without failing if config is missing)
        llm_mode = "live"  # Default assumption
        try:
            from omoi_os.config import get_app_settings

            settings = get_app_settings()
            llm_mode = getattr(settings.llm, "mode", "live")
        except Exception:
            # If we can't load settings, assume live mode and check env vars
            pass

        # If mode is null or replay, key not needed
        if llm_mode in ("null", "replay"):
            self.report.checks.append(
                DependencyCheck(
                    name="LLM API Key",
                    status="ok",
                    required=False,
                    details=f"Mode: {llm_mode} (key not needed)",
                    fix_command="",
                    category="config",
                )
            )
            return

        # Check for API keys
        has_fireworks = bool(os.getenv("FIREWORKS_API_KEY"))
        has_llm_key = bool(os.getenv("LLM_API_KEY"))

        if has_fireworks or has_llm_key:
            key_source = "FIREWORKS_API_KEY" if has_fireworks else "LLM_API_KEY"
            self.report.checks.append(
                DependencyCheck(
                    name="LLM API Key",
                    status="ok",
                    required=False,
                    details=f"Found {key_source}",
                    fix_command="",
                    category="config",
                )
            )
        else:
            self.report.checks.append(
                DependencyCheck(
                    name="LLM API Key",
                    status="not_configured",
                    required=False,
                    details="Not set (set llm.mode: 'null' in config/local.yaml to bypass)",
                    fix_command="Set FIREWORKS_API_KEY or LLM_API_KEY in .env.local",
                    category="config",
                )
            )

    async def _check_github_token(self) -> None:
        """Check GitHub token configuration."""
        # Check if git provider is local (no token needed)
        git_provider = "github"  # Default
        try:
            from omoi_os.config import get_app_settings

            settings = get_app_settings()
            # Note: integrations section might not exist yet, use safe access
            git_provider = getattr(settings, "git", {}).get("provider", "github")
        except Exception:
            pass

        if git_provider == "local":
            self.report.checks.append(
                DependencyCheck(
                    name="GitHub Token",
                    status="ok",
                    required=False,
                    details="Git provider is local (token not needed)",
                    fix_command="",
                    category="config",
                )
            )
            return

        # Check for GitHub token
        has_token = bool(os.getenv("GITHUB_TOKEN"))

        if has_token:
            self.report.checks.append(
                DependencyCheck(
                    name="GitHub Token",
                    status="ok",
                    required=False,
                    details="Found GITHUB_TOKEN",
                    fix_command="",
                    category="config",
                )
            )
        else:
            self.report.checks.append(
                DependencyCheck(
                    name="GitHub Token",
                    status="not_configured",
                    required=False,
                    details="Not set (set git.provider: 'local' in config to bypass)",
                    fix_command="Set GITHUB_TOKEN in .env.local or set git.provider: 'local' in config",
                    category="config",
                )
            )

    async def _check_claude_key(self) -> None:
        """Check Claude/Anthropic API key configuration."""
        has_anthropic = bool(os.getenv("ANTHROPIC_API_KEY"))
        has_oauth = bool(os.getenv("CLAUDE_CODE_OAUTH_TOKEN"))

        if has_oauth:
            self.report.checks.append(
                DependencyCheck(
                    name="Claude API Key",
                    status="ok",
                    required=False,
                    details="Found CLAUDE_CODE_OAUTH_TOKEN",
                    fix_command="",
                    category="config",
                )
            )
        elif has_anthropic:
            self.report.checks.append(
                DependencyCheck(
                    name="Claude API Key",
                    status="ok",
                    required=False,
                    details="Found ANTHROPIC_API_KEY",
                    fix_command="",
                    category="config",
                )
            )
        else:
            self.report.checks.append(
                DependencyCheck(
                    name="Claude API Key",
                    status="not_configured",
                    required=False,
                    details="Not set (needed for Claude Agent SDK)",
                    fix_command="Set CLAUDE_CODE_OAUTH_TOKEN (preferred) or ANTHROPIC_API_KEY in .env.local",
                    category="config",
                )
            )

    async def _check_daytona_key(self) -> None:
        """Check Daytona API key configuration."""
        # Check if sandbox provider is local (no key needed)
        sandbox_provider = "daytona"  # Default
        try:
            from omoi_os.config import get_app_settings

            settings = get_app_settings()
            sandbox_provider = getattr(settings, "sandbox", {}).get(
                "provider", "daytona"
            )
        except Exception:
            pass

        if sandbox_provider == "local":
            self.report.checks.append(
                DependencyCheck(
                    name="Daytona API Key",
                    status="ok",
                    required=False,
                    details="Sandbox provider is local (key not needed)",
                    fix_command="",
                    category="config",
                )
            )
            return

        # Check for Daytona token
        has_token = bool(os.getenv("DAYTONA_API_KEY"))

        if has_token:
            self.report.checks.append(
                DependencyCheck(
                    name="Daytona API Key",
                    status="ok",
                    required=False,
                    details="Found DAYTONA_API_KEY",
                    fix_command="",
                    category="config",
                )
            )
        else:
            self.report.checks.append(
                DependencyCheck(
                    name="Daytona API Key",
                    status="not_configured",
                    required=False,
                    details="Not set (set sandbox.provider: 'local' in config to bypass)",
                    fix_command="Set DAYTONA_API_KEY in .env.local or set sandbox.provider: 'local' in config",
                    category="config",
                )
            )

    async def _check_python_deps(self) -> None:
        """Check if Python dependencies are installed."""
        # Try importing omoi_os
        try:
            import omoi_os  # noqa: F401

            self.report.checks.append(
                DependencyCheck(
                    name="Dependencies",
                    status="ok",
                    required=True,
                    details="All installed",
                    fix_command="",
                    category="runtime",
                )
            )
        except ImportError as e:
            self.report.checks.append(
                DependencyCheck(
                    name="Dependencies",
                    status="missing",
                    required=True,
                    details=f"Import failed: {e}",
                    fix_command="Run 'uv sync --active' to install dependencies",
                    category="runtime",
                )
            )

    async def _check_migrations(self) -> None:
        """Check database migration status."""
        # Check if alembic can get current head
        returncode, stdout, stderr = await self._run_command(
            "uv", "run", "--active", "alembic", "heads", capture_stderr=True
        )

        if returncode == 0:
            self.report.checks.append(
                DependencyCheck(
                    name="Migrations",
                    status="ok",
                    required=True,
                    details="Alembic configured",
                    fix_command="",
                    category="database",
                )
            )
        else:
            error_msg = stderr or stdout or "Unknown error"
            self.report.checks.append(
                DependencyCheck(
                    name="Migrations",
                    status="not_configured",
                    required=False,
                    details=f"Check failed: {error_msg[:50]}",
                    fix_command="Ensure PostgreSQL is running, then run 'just db-migrate'",
                    category="database",
                )
            )


def _status_icon(check: DependencyCheck) -> str:
    """Get the appropriate status icon for a check."""
    if check.status == "ok":
        return "✅"
    elif check.status in ("missing", "wrong_version"):
        return "❌" if check.required else "⚠️"
    else:  # not_configured
        return "⚠️"


def display_report(report: BootstrapReport) -> None:
    """Display the bootstrap report in a formatted way."""
    print()
    print("OmoiOS Dev Environment Check")
    print("═══════════════════════════════════════════════════════════")
    print()

    categories = [
        ("runtime", "Runtime"),
        ("database", "Database"),
        ("config", "Configuration"),
    ]

    for cat_key, cat_name in categories:
        checks = report.get_by_category(cat_key)
        if not checks:
            continue

        print(f"{cat_name}")
        for check in checks:
            icon = _status_icon(check)
            name_colored = check.name.ljust(15)
            print(f"  {icon} {name_colored} {check.details}")
        print()

    print("═══════════════════════════════════════════════════════════")

    if report.all_required_ok:
        print("Status: Ready for local development")
    else:
        print("Status: Missing required dependencies")
        print()
        print("Fix commands:")
        for check in report.checks:
            if check.status != "ok" and check.required and check.fix_command:
                print(f"  • {check.name}: {check.fix_command}")

    if report.has_warnings:
        print()
        print("Optional dependencies (warnings):")
        for check in report.checks:
            if check.status != "ok" and not check.required and check.fix_command:
                print(f"  • {check.name}: {check.fix_command}")

    print()


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser for the CLI."""
    parser = argparse.ArgumentParser(
        prog="omoi-bootstrap",
        description="OmoiOS development environment bootstrap and health checking",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # check command
    check_parser = subparsers.add_parser(
        "check", help="Check all dependencies and configuration"
    )
    check_parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON",
    )

    # health command (alias for check, can be extended later)
    health_parser = subparsers.add_parser(
        "health", help="Show live health dashboard (same as check)"
    )
    health_parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON",
    )

    return parser


async def main_async(args: Optional[list[str]] = None) -> int:
    """Async main entry point."""
    parser = create_parser()
    parsed = parser.parse_args(args)

    if not parsed.command:
        parser.print_help()
        return 1

    checker = BootstrapChecker()
    report = await checker.check_all()

    if getattr(parsed, "json", False):
        import json

        # Convert to dict for JSON serialization
        result = {
            "checks": [
                {
                    "name": c.name,
                    "status": c.status,
                    "required": c.required,
                    "details": c.details,
                    "fix_command": c.fix_command,
                    "category": c.category,
                }
                for c in report.checks
            ],
            "all_required_ok": report.all_required_ok,
            "has_warnings": report.has_warnings,
        }
        print(json.dumps(result, indent=2))
    else:
        display_report(report)

    return 0 if report.all_required_ok else 1


def main(args: Optional[list[str]] = None) -> int:
    """Main entry point."""
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    sys.exit(main())
