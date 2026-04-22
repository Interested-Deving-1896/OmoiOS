#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 1 ]; then
  echo "Usage: bash scripts/run_local_litho.sh <repo-path> [time-budget-minutes] [--detach]" >&2
  exit 1
fi

REPO_PATH="$1"
TIME_BUDGET="${2:-15}"
DETACH_FLAG="${3:-}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

CMD=(bash "$SCRIPT_DIR/uv_run.sh" "$SCRIPT_DIR/run_litho_analysis.py" --repo-path "$REPO_PATH" --time-budget-minutes "$TIME_BUDGET")

if [ "$DETACH_FLAG" = "--detach" ]; then
  CMD+=(--detach)
fi

exec "${CMD[@]}"
