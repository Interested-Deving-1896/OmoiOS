#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
from collections import defaultdict
from pathlib import Path
import tomllib

SOURCE_EXTENSIONS = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".rs", ".go", ".java", ".kt", ".kts",
    ".swift", ".c", ".cc", ".cpp", ".h", ".hpp", ".cs", ".rb", ".php", ".scala",
    ".sql", ".sh", ".json", ".yaml", ".yml", ".toml", ".ini", ".proto", ".graphql",
    ".md", ".mdx",
}

ALWAYS_KEEP_FILENAMES = {
    "README", "README.md", "ARCHITECTURE.md", "UI.md", "AGENTS.md", "CLAUDE.md",
    "package.json", "pnpm-lock.yaml", "yarn.lock", "package-lock.json", "bun.lock",
    "pyproject.toml", "uv.lock", "poetry.lock", "requirements.txt", "requirements-dev.txt",
    "Cargo.toml", "Cargo.lock", "go.mod", "go.sum", "docker-compose.yml", "docker-compose.yaml",
}

EXCLUDED_DIR_NAMES = {
    ".git", ".hg", ".svn", "node_modules", ".venv", "venv", "__pycache__", "dist", "build",
    "target", ".next", ".turbo", ".cache", "coverage", ".litho", "litho.docs", "tmp", "temp",
}

IMPORTANT_PATH_PREFIXES = (
    ".github/workflows/",
    "migrations/",
    "alembic/",
    "schema/",
    "schemas/",
    "infra/",
    "infrastructure/",
    "config/",
    "configs/",
    "docs/architecture/",
    "docs/design/",
    "docs/adr/",
)


def resolve_repo_path(repo_path: str | Path) -> Path:
    return Path(repo_path).expanduser().resolve()


def run_cmd(command: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=str(cwd) if cwd else None, text=True, capture_output=True, check=False)


def git_tracked_files(repo_path: Path) -> list[Path]:
    result = run_cmd(["git", "ls-files"], cwd=repo_path)
    if result.returncode != 0:
        return []
    return [repo_path / line for line in result.stdout.splitlines() if line.strip()]


def latest_git_commit_timestamp(repo_path: Path) -> float | None:
    result = run_cmd(["git", "log", "-1", "--format=%ct"], cwd=repo_path)
    if result.returncode != 0:
        return None
    value = result.stdout.strip()
    return float(value) if value else None


def is_source_like(path: Path) -> bool:
    if path.name in ALWAYS_KEEP_FILENAMES:
        return True
    return path.suffix.lower() in SOURCE_EXTENSIONS


def iter_repo_files(repo_path: Path) -> list[Path]:
    tracked = git_tracked_files(repo_path)
    if tracked:
        return [p for p in tracked if p.is_file()]

    files: list[Path] = []
    for root, dirs, filenames in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in EXCLUDED_DIR_NAMES]
        root_path = Path(root)
        for filename in filenames:
            files.append(root_path / filename)
    return files


def detect_global_config_path(explicit_path: str | None = None) -> Path | None:
    if explicit_path:
        candidate = Path(explicit_path).expanduser().resolve()
        return candidate if candidate.exists() else None

    env_candidate = os.environ.get("LITHO_GLOBAL_CONFIG") or os.environ.get("LITHO_CONFIG")
    if env_candidate:
        candidate = Path(env_candidate).expanduser().resolve()
        if candidate.exists():
            return candidate

    shell_files = [
        Path.home() / ".zshrc",
        Path.home() / ".zprofile",
        Path.home() / ".zshenv",
        Path.home() / ".bashrc",
        Path.home() / ".bash_profile",
    ]
    alias_pattern = re.compile(r"(?:alias\s+)?deepwiki-rs\s*=\s*['\"](?P<value>.+?)['\"]")
    config_pattern = re.compile(r"(?:--config|-c)\s+(?P<path>(?:\S+|['\"].+?['\"]))")

    interactive_alias = run_cmd(["zsh", "-ic", "alias deepwiki-rs 2>/dev/null || true"])
    interactive_value = interactive_alias.stdout.strip()
    if interactive_value:
        match = alias_pattern.search(interactive_value)
        if match:
            alias_value = match.group("value")
            config_match = config_pattern.search(alias_value)
            if config_match:
                raw_path = config_match.group("path").strip("'\"")
                candidate = Path(raw_path).expanduser().resolve()
                if candidate.exists():
                    return candidate

    for shell_file in shell_files:
        if not shell_file.exists():
            continue
        try:
            content = shell_file.read_text()
        except OSError:
            continue
        for match in alias_pattern.finditer(content):
            alias_value = match.group("value")
            config_match = config_pattern.search(alias_value)
            if not config_match:
                continue
            raw_path = config_match.group("path").strip("'\"")
            candidate = Path(raw_path).expanduser().resolve()
            if candidate.exists():
                return candidate

    common_candidates = [Path.home() / "litho.toml", Path.home() / ".litho.toml"]
    for candidate in common_candidates:
        if candidate.exists():
            return candidate.resolve()

    return None


def load_toml(path: Path | None) -> dict:
    if not path or not path.exists() or tomllib is None:
        return {}
    try:
        with path.open("rb") as fh:
            return tomllib.load(fh)
    except Exception:
        return {}


def cache_state(repo_path: Path) -> dict:
    cache_dir = repo_path / ".litho" / "cache"
    exists = cache_dir.exists()
    file_count = 0
    newest_mtime = None
    if exists:
        for file_path in cache_dir.rglob("*"):
            if file_path.is_file():
                file_count += 1
                mtime = file_path.stat().st_mtime
                newest_mtime = max(newest_mtime or mtime, mtime)

    head_ts = latest_git_commit_timestamp(repo_path)
    freshness = "missing"
    if exists and file_count > 0:
        if head_ts is not None and newest_mtime is not None:
            freshness = "fresh" if newest_mtime >= head_ts else "stale"
        elif newest_mtime and (time.time() - newest_mtime) <= 86400:
            freshness = "fresh-ish"
        else:
            freshness = "stale"

    return {
        "cache_dir": str(cache_dir),
        "exists": exists,
        "file_count": file_count,
        "newest_mtime": newest_mtime,
        "git_head_timestamp": head_ts,
        "freshness": freshness,
    }


def classify_repo(source_like_files: int, source_like_bytes: int) -> str:
    mb = source_like_bytes / (1024 * 1024)
    if source_like_files <= 500 and mb <= 50:
        return "small"
    if source_like_files <= 2000 and mb <= 200:
        return "medium"
    if source_like_files <= 8000 and mb <= 750:
        return "large"
    return "very-large"


def estimate_runtime_minutes(repo_class: str, cache_freshness: str, filtered: bool = False) -> float:
    base = {
        "small": 5.0,
        "medium": 11.0,
        "large": 20.0,
        "very-large": 35.0,
    }[repo_class]
    if cache_freshness == "fresh":
        base *= 0.65
    elif cache_freshness == "fresh-ish":
        base *= 0.8
    if filtered:
        base *= 0.55
    return round(base, 1)


def profile_repo(repo_path: Path, global_config_path: Path | None) -> dict:
    files = iter_repo_files(repo_path)
    tracked_files = len(files)
    total_bytes = 0
    source_like_files = 0
    source_like_bytes = 0
    directory_bytes: dict[str, int] = defaultdict(int)
    directory_counts: dict[str, int] = defaultdict(int)

    for file_path in files:
        try:
            size = file_path.stat().st_size
        except OSError:
            continue
        total_bytes += size
        rel = file_path.relative_to(repo_path)
        top_dir = rel.parts[0] if len(rel.parts) > 1 else "."
        directory_bytes[top_dir] += size
        directory_counts[top_dir] += 1
        if is_source_like(file_path):
            source_like_files += 1
            source_like_bytes += size

    top_directories = sorted(
        (
            {
                "path": name,
                "bytes": bytes_count,
                "files": directory_counts[name],
            }
            for name, bytes_count in directory_bytes.items()
        ),
        key=lambda item: item["bytes"],
        reverse=True,
    )[:10]

    repo_class = classify_repo(source_like_files, source_like_bytes)
    cache = cache_state(repo_path)
    return {
        "repo_path": str(repo_path),
        "global_config_path": str(global_config_path) if global_config_path else None,
        "tracked_files": tracked_files,
        "total_bytes": total_bytes,
        "source_like_files": source_like_files,
        "source_like_bytes": source_like_bytes,
        "top_directories": top_directories,
        "repo_class": repo_class,
        "cache": cache,
        "estimated_runtime_minutes": estimate_runtime_minutes(repo_class, cache["freshness"], filtered=False),
        "estimated_filtered_runtime_minutes": estimate_runtime_minutes(repo_class, cache["freshness"], filtered=True),
    }


def generate_repo_settings(profile: dict) -> dict:
    repo_class = profile["repo_class"]
    settings = {
        "small": {
            "max_file_size": 512 * 1024,
            "max_depth": 10,
            "max_boundary_insights": 15,
            "code_insights_limit": 25,
            "include_source_code": True,
            "only_dirs_threshold": 100,
            "max_parallels": 3,
            "tool_concurrency": 4,
            "timeout_seconds": 300,
            "chunk_size": 8000,
            "chunk_overlap": 200,
            "chunk_strategy": "semantic",
            "chunk_min_size": 10000,
        },
        "medium": {
            "max_file_size": 384 * 1024,
            "max_depth": 10,
            "max_boundary_insights": 15,
            "code_insights_limit": 25,
            "include_source_code": False,
            "only_dirs_threshold": 100,
            "max_parallels": 4,
            "tool_concurrency": 4,
            "timeout_seconds": 300,
            "chunk_size": 8000,
            "chunk_overlap": 200,
            "chunk_strategy": "semantic",
            "chunk_min_size": 10000,
        },
        "large": {
            "max_file_size": 256 * 1024,
            "max_depth": 8,
            "max_boundary_insights": 10,
            "code_insights_limit": 20,
            "include_source_code": False,
            "only_dirs_threshold": 50,
            "max_parallels": 5,
            "tool_concurrency": 4,
            "timeout_seconds": 420,
            "chunk_size": 6000,
            "chunk_overlap": 150,
            "chunk_strategy": "semantic",
            "chunk_min_size": 8000,
        },
        "very-large": {
            "max_file_size": 128 * 1024,
            "max_depth": 6,
            "max_boundary_insights": 8,
            "code_insights_limit": 15,
            "include_source_code": False,
            "only_dirs_threshold": 25,
            "max_parallels": 5,
            "tool_concurrency": 3,
            "timeout_seconds": 600,
            "chunk_size": 4000,
            "chunk_overlap": 100,
            "chunk_strategy": "paragraph",
            "chunk_min_size": 5000,
        },
    }[repo_class]
    return settings


def should_use_filtered_copy(profile: dict, time_budget_minutes: int) -> bool:
    if profile["repo_class"] == "very-large":
        return True
    return profile["estimated_runtime_minutes"] > (time_budget_minutes * 1.25)


def keep_in_filtered_copy(rel_path: Path) -> bool:
    path_str = rel_path.as_posix()
    if rel_path.name in ALWAYS_KEEP_FILENAMES:
        return True
    if any(path_str.startswith(prefix) for prefix in IMPORTANT_PATH_PREFIXES):
        return True
    if any(part in EXCLUDED_DIR_NAMES for part in rel_path.parts[:-1]):
        return False
    return rel_path.suffix.lower() in SOURCE_EXTENSIONS


def create_filtered_copy(repo_path: Path, destination: Path) -> dict:
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True, exist_ok=True)
    copied = 0
    bytes_copied = 0
    files = iter_repo_files(repo_path)
    for file_path in files:
        rel = file_path.relative_to(repo_path)
        if not keep_in_filtered_copy(rel):
            continue
        target = destination / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(file_path, target)
        copied += 1
        try:
            bytes_copied += target.stat().st_size
        except OSError:
            pass
    return {
        "destination": str(destination),
        "copied_files": copied,
        "copied_bytes": bytes_copied,
    }


def print_json(data: dict) -> None:
    print(json.dumps(data, indent=2, sort_keys=True))
