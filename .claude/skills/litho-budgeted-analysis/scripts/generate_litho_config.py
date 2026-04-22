#!/usr/bin/env python3

# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///

from __future__ import annotations

import argparse
from pathlib import Path

from _litho_common import (
    detect_global_config_path,
    generate_repo_settings,
    load_toml,
    print_json,
    profile_repo,
    resolve_repo_path,
)


def render_litho_config(repo_path: Path, global_config: dict, profile: dict) -> str:
    settings = generate_repo_settings(profile)
    llm = dict(global_config.get("llm", {}))
    llm["max_parallels"] = settings["max_parallels"]
    llm["tool_concurrency"] = settings["tool_concurrency"]
    llm["timeout_seconds"] = settings["timeout_seconds"]

    cache = dict(global_config.get("cache", {}))
    cache.setdefault("enabled", True)
    cache.setdefault("cache_dir", ".litho/cache")
    cache.setdefault("expire_hours", 8760)

    top_level = {
        "project_path": ".",
        "output_path": "./litho.docs",
        "target_language": global_config.get("target_language", "en"),
        "analyze_dependencies": global_config.get("analyze_dependencies", True),
        "identify_components": global_config.get("identify_components", True),
        "core_component_percentage": global_config.get("core_component_percentage", 40.0),
        "git_tracked_only": global_config.get("git_tracked_only", True),
        "internal_path": global_config.get("internal_path", ".litho"),
        "max_turns": global_config.get("max_turns", 100),
        "max_depth": settings["max_depth"],
        "max_file_size": settings["max_file_size"],
        "include_tests": False,
        "include_hidden": False,
    }

    excluded_extensions = global_config.get(
        "excluded_extensions",
        ["jpg", "jpeg", "png", "gif", "bmp", "ico", "mp3", "mp4", "avi", "pdf", "zip", "tar", "exe", "dll", "so", "archive"],
    )
    included_extensions = global_config.get("included_extensions", [])

    lines: list[str] = []
    for key, value in top_level.items():
        if isinstance(value, bool):
            lines.append(f"{key} = {'true' if value else 'false'}")
        elif isinstance(value, (int, float)):
            lines.append(f"{key} = {value}")
        else:
            lines.append(f'{key} = "{str(value)}"')
    lines.append("")
    lines.append("excluded_dirs = [")
    for value in [
        ".litho", "litho.docs", "target", "node_modules", ".git", "build", "dist", "venv",
        ".venv", "__pycache__", "coverage", ".next", ".turbo", "tmp", "temp",
    ]:
        lines.append(f'  "{value}",')
    lines.append("]")
    lines.append("")
    lines.append("excluded_extensions = [")
    for value in excluded_extensions:
        lines.append(f'  "{value}",')
    lines.append("]")
    lines.append("")
    lines.append("included_extensions = [")
    for value in included_extensions:
        lines.append(f'  "{value}",')
    lines.append("]")
    lines.append("")
    lines.append("excluded_files = [")
    for value in [
        "*.log", "*.tmp", "*.cache", "pnpm-lock.yaml", "package-lock.json", "yarn.lock", "bun.lock",
        "Cargo.lock", ".env",
    ]:
        lines.append(f'  "{value}",')
    lines.append("]")

    if llm:
        lines.append("")
        lines.append("[llm]")
        for key in [
            "provider", "api_key", "api_base_url", "internal_path", "model_efficient", "model_powerful",
            "max_tokens", "temperature", "retry_attempts", "retry_delay_ms", "disable_preset_tools",
            "max_parallels", "tool_concurrency", "timeout_seconds",
        ]:
            if key not in llm:
                continue
            value = llm[key]
            if isinstance(value, bool):
                lines.append(f"{key} = {'true' if value else 'false'}")
            elif isinstance(value, (int, float)):
                lines.append(f"{key} = {value}")
            else:
                lines.append(f'{key} = "{str(value)}"')

    lines.append("")
    lines.append("[cache]")
    for key in ["enabled", "cache_dir", "expire_hours"]:
        value = cache[key]
        if isinstance(value, bool):
            lines.append(f"{key} = {'true' if value else 'false'}")
        elif isinstance(value, (int, float)):
            lines.append(f"{key} = {value}")
        else:
            lines.append(f'{key} = "{str(value)}"')

    lines.append("")
    lines.append("[boundary_analysis]")
    lines.append(f"max_boundary_insights = {settings['max_boundary_insights']}")
    lines.append(f"code_insights_limit = {settings['code_insights_limit']}")
    lines.append(f"include_source_code = {'true' if settings['include_source_code'] else 'false'}")
    lines.append(f"only_directories_when_files_more_than = {settings['only_dirs_threshold']}")

    lines.append("")
    lines.append("[knowledge.local_docs]")
    lines.append("enabled = true")
    lines.append('cache_dir = ".litho/cache/knowledge/local_docs"')
    lines.append("watch_for_changes = true")

    lines.append("")
    lines.append("[knowledge.local_docs.default_chunking]")
    lines.append("enabled = true")
    lines.append(f"max_chunk_size = {settings['chunk_size']}")
    lines.append(f"chunk_overlap = {settings['chunk_overlap']}")
    lines.append(f'strategy = "{settings["chunk_strategy"]}"')
    lines.append(f"min_size_for_chunking = {settings['chunk_min_size']}")

    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a repo-local Litho config")
    parser.add_argument("--repo-path", default=".", help="Path to the repository")
    parser.add_argument("--global-config", default=None, help="Optional explicit path to the global litho.toml")
    parser.add_argument("--output", default="litho.local.toml", help="Output filename inside the repo")
    parser.add_argument("--dry-run", action="store_true", help="Print config instead of writing it")
    args = parser.parse_args()

    repo_path = resolve_repo_path(args.repo_path)
    global_config_path = detect_global_config_path(args.global_config)
    global_config = load_toml(global_config_path)
    profile = profile_repo(repo_path, global_config_path)
    content = render_litho_config(repo_path, global_config, profile)

    if args.dry_run:
        print(content)
        return

    output_path = repo_path / args.output
    output_path.write_text(content)
    print_json(
        {
            "repo_path": str(repo_path),
            "global_config_path": str(global_config_path) if global_config_path else None,
            "output_path": str(output_path),
            "repo_class": profile["repo_class"],
        }
    )


if __name__ == "__main__":
    main()
