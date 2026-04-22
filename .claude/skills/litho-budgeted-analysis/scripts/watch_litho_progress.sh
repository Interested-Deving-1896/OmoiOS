#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 1 ]; then
  echo "Usage: bash scripts/watch_litho_progress.sh <repo-path>" >&2
  exit 1
fi

REPO_PATH="$1"
STATUS_FILE="$REPO_PATH/.litho/run-status.json"
LOG_FILE="$REPO_PATH/.litho/run.log"

while true; do
  clear || true
  echo "=== Litho Status ==="
  if [ -f "$STATUS_FILE" ]; then
    python3 - <<'PY' "$STATUS_FILE"
import json, sys
from pathlib import Path
path = Path(sys.argv[1])
data = json.loads(path.read_text())
for key in ["phase", "pid", "started_at", "last_output_at", "finished_at", "exit_code", "repo_class", "cache_freshness"]:
    print(f"{key}: {data.get(key)}")
print(f"log_path: {data.get('log_path')}")
print(f"command: {data.get('command')}")
PY
  else
    echo "No status file yet: $STATUS_FILE"
  fi

  echo
  echo "=== Log Tail ==="
  if [ -f "$LOG_FILE" ]; then
    tail -n 40 "$LOG_FILE"
  else
    echo "No log file yet: $LOG_FILE"
  fi
  sleep 2
done
