#!/usr/bin/env python3

# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///

from __future__ import annotations

import argparse

from _litho_common import detect_global_config_path, print_json, profile_repo, resolve_repo_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Profile a repo for budgeted Litho analysis")
    parser.add_argument("--repo-path", default=".", help="Path to the repository")
    parser.add_argument("--global-config", default=None, help="Optional explicit path to the global litho.toml")
    args = parser.parse_args()

    repo_path = resolve_repo_path(args.repo_path)
    global_config_path = detect_global_config_path(args.global_config)
    print_json(profile_repo(repo_path, global_config_path))


if __name__ == "__main__":
    main()
