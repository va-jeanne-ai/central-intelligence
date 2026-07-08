"""Weekly Digest Celery task.

Once a week (Mondays, after the daily overall-insight run), synthesize the last 7
days of the statistical engine's output into ONE weekly narrative — see
``app.analytics.weekly_digest`` for the real logic (the reusable, testable part).

COST NOTE: same discipline as ``capture_overall_insight`` — this makes at most ONE
paid Claude call per run when a real key is configured (mock_mode falls back free).
Unlike the daily task, this one also no-ops entirely (no LLM call, nothing written)
when there's no evidence at all for the week — see ``generate_weekly_digest``.

Runs after ``capture_overall_insight`` so the digest can read Monday's own fresh daily
assessment as part of the week. Idempotent per week (upsert on (insight_date, period)
where insight_date is the Monday the week starts from).
"""

import logging
from datetime import datetime, timezone
from uuid import uuid4

from celery.exceptions import MaxRetriesExceededError

from app.analytics.weekly_digest import generate_weekly_digest
from app.tasks.celery_app import celery_app
from app.tasks.db import make_sync_session

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=2, default_retry_delay=600)
def capture_weekly_digest(self) -> dict:
    """Generate (or refresh) this week's digest.

    No-ops gracefully (no LLM call) when there is no data for the week at all —
    ``generate_weekly_digest`` returns None in that case. Idempotent per week —
    re-running the same week upserts the same row.

    ``max_retries`` is low (2) on purpose: a paid LLM call shouldn't be retried hard.
    """
    task_id = self.request.id or uuid4().hex
    logger.info("capture_weekly_digest started — task_id=%s", task_id)

    try:
        db = make_sync_session()
        try:
            result = generate_weekly_digest(db)
        finally:
            db.close()

        if result is None:
            logger.info("capture_weekly_digest: no evidence for this week — no-op — task_id=%s", task_id)
            return {
                "task_id": task_id,
                "status": "skipped",
                "reason": "no data for the week",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }

        logger.info(
            "capture_weekly_digest: %s digest for week %s..%s (verdict=%s, model=%s) — task_id=%s",
            "genesis" if result["previous_week_start"] is None else "weekly",
            result["week_start"],
            result["week_end"],
            result["health_verdict"],
            result["model"],
            task_id,
        )
        return {
            "task_id": task_id,
            "status": "completed",
            "updated_at": datetime.now(timezone.utc).isoformat(),
            **result,
        }

    except Exception as exc:
        logger.exception("capture_weekly_digest failed — task_id=%s error=%s", task_id, exc)
        try:
            raise self.retry(exc=exc)
        except MaxRetriesExceededError:
            return {
                "task_id": task_id,
                "status": "failed",
                "error": str(exc),
            }
