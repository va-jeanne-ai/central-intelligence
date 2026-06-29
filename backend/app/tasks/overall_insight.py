"""Overall Insight Celery task.

Once a day, generate the company-level health assessment — the narrative that compounds
on the previous day's (see ``app.analytics.overall_insight``). Thin wrapper over the sync
``generate_overall_insight`` (the real logic, testable).

COST NOTE: unlike the other scheduled tasks (pure DB work), this one makes ONE paid
Claude call per run when a real key is configured. When ``mock_mode`` is on (or no key),
``generate_overall_insight`` falls back to a free mock — so enabling the beat entry below
is safe to wire before you're ready to spend: it only costs once ``mock_mode=False``.

Runs after ``capture_metric_snapshots`` so the assessment reflects the day's fresh
snapshots, trends, and recommendations. Idempotent per day (upsert on ``insight_date``).
"""

import logging
from datetime import datetime, timezone
from uuid import uuid4

from celery.exceptions import MaxRetriesExceededError

from app.analytics.overall_insight import generate_overall_insight
from app.tasks.celery_app import celery_app
from app.tasks.db import make_sync_session

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=2, default_retry_delay=600)
def capture_overall_insight(self) -> dict:
    """Generate (or refresh) today's overall insight.

    Genesis is automatic: ``generate_overall_insight`` synthesizes from scratch when no
    prior assessment exists, and compounds on the previous day otherwise. Idempotent per
    day — re-running upserts the same row.

    ``max_retries`` is low (2) on purpose: a paid LLM call shouldn't be retried hard.
    """
    task_id = self.request.id or uuid4().hex
    logger.info("capture_overall_insight started — task_id=%s", task_id)

    try:
        db = make_sync_session()
        try:
            result = generate_overall_insight(db)
        finally:
            db.close()

        logger.info(
            "capture_overall_insight: %s assessment for %s (verdict=%s, model=%s) — task_id=%s",
            "genesis" if result["previous_date"] is None else "daily",
            result["insight_date"],
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
        logger.exception("capture_overall_insight failed — task_id=%s error=%s", task_id, exc)
        try:
            raise self.retry(exc=exc)
        except MaxRetriesExceededError:
            return {
                "task_id": task_id,
                "status": "failed",
                "error": str(exc),
            }
