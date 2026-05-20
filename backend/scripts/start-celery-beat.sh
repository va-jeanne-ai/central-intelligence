#!/usr/bin/env bash
# Start the Celery beat scheduler. Run in its own terminal, alongside the worker.
# Beat reads the schedule from app.tasks.celery_app.beat_schedule and enqueues
# tasks at the configured cron times. The worker (started separately) consumes them.
#
# Default scheduler stores last-run state in `celerybeat-schedule` (sqlite-shelve)
# in the current working directory. Safe for local dev. For prod, swap to redbeat.
set -euo pipefail
cd "$(dirname "$0")/.."
exec ./.venv/bin/celery -A app.tasks.celery_app beat --loglevel=info
