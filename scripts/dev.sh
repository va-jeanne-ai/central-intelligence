#!/usr/bin/env bash
# Bring up the three local dev processes that Central Intelligence needs:
#   - FastAPI backend (uvicorn) on :8000
#   - Celery worker  (background tasks)
#   - Celery beat    (scheduler — triggers embed-queue-drain, gmail/drive sync, etc.)
#
# All three run in the same terminal with multiplexed output. Each line is
# prefixed with the process name so you can tell who's saying what.
# Ctrl+C stops all three cleanly.
#
# Beat being absent is the #1 stall this stack hits. This script removes
# the manual "did I start beat?" check that has bitten us repeatedly.
set -euo pipefail

cd "$(dirname "$0")/.."          # repo root
cd backend

if [[ ! -d .venv ]]; then
  echo "ERROR: backend/.venv missing — run python -m venv .venv && pip install -r requirements.txt first."
  exit 1
fi

# Trap propagates SIGINT so all child processes die when the user hits Ctrl+C.
pids=()
cleanup() {
  echo
  echo ">>> stopping dev processes..."
  for pid in "${pids[@]}"; do
    kill "$pid" 2>/dev/null || true
  done
  wait 2>/dev/null || true
  exit 0
}
trap cleanup INT TERM

run_prefixed() {
  local name=$1
  shift
  # Prefix every line of stdout/stderr with [name] so multiplexed output is readable.
  "$@" 2>&1 | sed "s/^/[$name] /" &
  pids+=($!)
}

echo ">>> backend dev stack starting (Ctrl+C to stop all)"

run_prefixed "backend" .venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
run_prefixed "worker"  env PYTHONPATH=. .venv/bin/celery -A app.tasks.celery_app worker --loglevel=info
run_prefixed "beat"    env PYTHONPATH=. .venv/bin/celery -A app.tasks.celery_app beat   --loglevel=info

wait
