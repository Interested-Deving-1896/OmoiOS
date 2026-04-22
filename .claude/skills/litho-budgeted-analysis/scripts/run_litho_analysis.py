#!/usr/bin/env python3

# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///

from __future__ import annotations

import argparse
import datetime as dt
import json
import shlex
import subprocess
from pathlib import Path

from _litho_common import (
    create_filtered_copy,
    detect_global_config_path,
    estimate_runtime_minutes,
    print_json,
    profile_repo,
    resolve_repo_path,
    should_use_filtered_copy,
)
from generate_litho_config import render_litho_config
from _litho_common import load_toml


def iso_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def write_status(status_path: Path, payload: dict) -> None:
    status_path.parent.mkdir(parents=True, exist_ok=True)
    status_path.write_text(json.dumps(payload, indent=2, sort_keys=True))


def build_observability_paths(repo_path: Path) -> tuple[Path, Path]:
    run_dir = repo_path / ".litho"
    return run_dir / "run.log", run_dir / "run-status.json"


def build_command(repo_path: Path, config_path: Path, profile: dict) -> str:
    flags = []
    freshness = profile["cache"]["freshness"]
    if freshness in {"fresh", "fresh-ish"} and profile["repo_class"] in {"medium", "large", "very-large"}:
        flags.append("--skip-preprocessing")
    return f"command deepwiki-rs --config {shlex.quote(str(config_path))} -p {shlex.quote(str(repo_path))} {' '.join(flags)}".strip()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Litho with repo-size and cache-aware heuristics")
    parser.add_argument("--repo-path", default=".", help="Path to the repository")
    parser.add_argument("--global-config", default=None, help="Optional explicit path to the global litho.toml")
    parser.add_argument("--time-budget-minutes", type=int, default=15, help="Target time budget")
    parser.add_argument("--dry-run", action="store_true", help="Print plan without executing")
    parser.add_argument("--detach", action="store_true", help="Start Litho in the background and return immediately")
    parser.add_argument("--config-name", default="litho.local.toml", help="Repo-local config filename")
    args = parser.parse_args()

    repo_path = resolve_repo_path(args.repo_path)
    global_config_path = detect_global_config_path(args.global_config)
    profile = profile_repo(repo_path, global_config_path)
    global_config = load_toml(global_config_path)

    working_repo = repo_path
    filtered_copy = None
    if should_use_filtered_copy(profile, args.time_budget_minutes):
        filtered_destination = repo_path / ".litho" / "filtered-repo"
        filtered_copy = create_filtered_copy(repo_path, filtered_destination)
        working_repo = Path(filtered_copy["destination"])
        profile = profile_repo(working_repo, global_config_path)

    config_path = working_repo / args.config_name
    config_path.write_text(render_litho_config(working_repo, global_config, profile))
    command = build_command(working_repo, config_path, profile)
    log_path, status_path = build_observability_paths(repo_path)
    plan = {
        "repo_path": str(repo_path),
        "working_repo": str(working_repo),
        "global_config_path": str(global_config_path) if global_config_path else None,
        "config_path": str(config_path),
        "repo_class": profile["repo_class"],
        "cache_freshness": profile["cache"]["freshness"],
        "estimated_runtime_minutes": estimate_runtime_minutes(profile["repo_class"], profile["cache"]["freshness"], filtered=bool(filtered_copy)),
        "used_filtered_copy": bool(filtered_copy),
        "filtered_copy": filtered_copy,
        "log_path": str(log_path),
        "status_path": str(status_path),
        "command": command,
    }

    if args.dry_run:
        print_json(plan)
        return

    initial_status = {
        **plan,
        "phase": "starting",
        "started_at": iso_now(),
        "last_output_at": None,
        "pid": None,
        "exit_code": None,
    }
    write_status(status_path, initial_status)

    print_json(plan)
    print(f"Started Litho plan. Log: {log_path}")
    print(f"Status: {status_path}")

    log_path.parent.mkdir(parents=True, exist_ok=True)

    if args.detach:
        with log_path.open("a", encoding="utf-8") as log_file:
            log_file.write(f"[{iso_now()}] Starting detached Litho run\n")
            log_file.write(f"[{iso_now()}] Command: {command}\n")
            log_file.flush()
            process = subprocess.Popen(
                ["zsh", "-ic", command],
                stdout=log_file,
                stderr=subprocess.STDOUT,
                text=True,
                start_new_session=True,
            )

        detached_status = {
            **initial_status,
            "phase": "running-detached",
            "pid": process.pid,
        }
        write_status(status_path, detached_status)
        return

    with log_path.open("a", encoding="utf-8") as log_file:
        log_file.write(f"[{iso_now()}] Starting Litho run\n")
        log_file.write(f"[{iso_now()}] Command: {command}\n")
        log_file.flush()

        process = subprocess.Popen(
            ["zsh", "-ic", command],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        running_status = {
            **initial_status,
            "phase": "running",
            "pid": process.pid,
        }
        write_status(status_path, running_status)

        assert process.stdout is not None
        for line in process.stdout:
            log_file.write(line)
            log_file.flush()
            print(line, end="")
            running_status["last_output_at"] = iso_now()
            write_status(status_path, running_status)

        exit_code = process.wait()
        completed_status = {
            **running_status,
            "phase": "completed" if exit_code == 0 else "failed",
            "finished_at": iso_now(),
            "exit_code": exit_code,
        }
        write_status(status_path, completed_status)
        raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
