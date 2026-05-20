#!/usr/bin/env bash
# Start the Celery worker. Run in its own terminal.
# Worker and beat MUST be separate processes — see ../app/tasks/celery_app.py beat_schedule.
set -euo pipefail
cd "$(dirname "$0")/.."
exec ./.venv/bin/celery -A app.tasks.celery_app worker --loglevel=info
