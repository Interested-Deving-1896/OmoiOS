#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 1 ]; then
  echo "Usage: bash scripts/uv_run.sh <pep723-script> [args...]" >&2
  exit 1
fi

SCRIPT_PATH="$1"
shift

if uv run "$SCRIPT_PATH" "$@"; then
  exit 0
fi

STATUS=$?

if [ -n "${VIRTUAL_ENV:-}" ] || [ -e ".venv/bin/python3" ]; then
  echo "uv run failed; retrying with system python fallback..." >&2
  exec uv run --python "$(which python3)" "$SCRIPT_PATH" "$@"
fi

exit "$STATUS"
