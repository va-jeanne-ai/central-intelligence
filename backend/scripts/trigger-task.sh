#!/usr/bin/env bash
# Manually trigger one scheduled task — useful for verifying without waiting for cron.
# Usage: ./scripts/trigger-task.sh <task-shortname>
# Shortnames: funnel | social | email | ads | comments
set -euo pipefail
cd "$(dirname "$0")/.."

case "${1:-}" in
  funnel)   TASK=app.tasks.funnel_stats.update_funnel_stats ;;
  social)   TASK=app.tasks.social_stats.update_social_stats ;;
  email)    TASK=app.tasks.email_stats.update_email_stats ;;
  ads)      TASK=app.tasks.ads_stats.update_ads_stats ;;
  comments) TASK=app.tasks.comments_collector.collect_social_comments ;;
  *)
    echo "usage: $0 <funnel|social|email|ads|comments>" >&2
    exit 1
    ;;
esac

PYTHONPATH=. ./.venv/bin/python -c "
from app.tasks.celery_app import celery_app
# Enqueue (worker must be running to consume; .delay() returns immediately)
result = celery_app.send_task('${TASK}')
print(f'Enqueued: ${TASK}')
print(f'Task ID:  {result.id}')
print('Watch the worker terminal for output, then re-query the DB.')
"
