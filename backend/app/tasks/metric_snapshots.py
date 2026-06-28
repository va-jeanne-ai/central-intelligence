"""Metric snapshot Celery task.

Periodically captures every registered outcome metric into ``metric_snapshots``,
building the timeseries the data-intelligence engine analyzes. Thin wrapper over
``app.analytics.snapshots.compute_snapshots`` (the real logic, sync + testable).
"""

import logging
from datetime import datetime, timezone
from uuid import uuid4

from celery.exceptions import MaxRetriesExceededError

from app.analytics.recommend import generate_recommendations
from app.analytics.snapshots import compute_snapshots
from app.tasks.celery_app import celery_app
from app.tasks.db import make_sync_session

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=300)
def capture_metric_snapshots(self) -> dict:
    """Compute + upsert today's snapshot for every registered metric × window.

    Idempotent per day (the unique constraint upserts), so safe to run repeatedly —
    a later run with more data simply refreshes the day's value.
    """
    task_id = self.request.id or uuid4().hex
    logger.info("capture_metric_snapshots started — task_id=%s", task_id)

    try:
        db = make_sync_session()
        try:
            result = compute_snapshots(db)
            # Recompute recommendations from the fresh snapshots so the two stay in sync.
            recs = generate_recommendations(db)
        finally:
            db.close()

        logger.info(
            "capture_metric_snapshots: wrote %d rows across %d metrics, %d active "
            "recommendation(s) — task_id=%s",
            result["rows_written"],
            result["metrics"],
            recs["active"],
            task_id,
        )
        return {
            "task_id": task_id,
            "status": "completed",
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "active_recommendations": recs["active"],
            **result,
        }

    except Exception as exc:
        logger.exception("capture_metric_snapshots failed — task_id=%s error=%s", task_id, exc)
        try:
            raise self.retry(exc=exc)
        except MaxRetriesExceededError:
            return {
                "task_id": task_id,
                "status": "failed",
                "error": str(exc),
            }
