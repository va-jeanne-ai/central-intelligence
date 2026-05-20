"""
Funnel Stats Celery task — Operator OPS-SF1.

Scheduled task that pulls and updates funnel conversion metrics and
persists them to the funnel_stats table.

Uses a synchronous SQLAlchemy session because Celery runs outside
FastAPI's async event loop.

Sprint 3b / OPS-SF1 — Funnel Stats Updater
"""

import logging
from datetime import datetime, timezone
from uuid import uuid4

from celery.exceptions import MaxRetriesExceededError
from sqlalchemy import func, select

from app.models.marketing import FunnelEvent, FunnelStats
from app.tasks.celery_app import celery_app
from app.tasks.db import make_sync_session

logger = logging.getLogger(__name__)


# OPS-SF1: Scheduled Celery task for funnel conversion metrics
@celery_app.task(bind=True, max_retries=3, default_retry_delay=300)
def update_funnel_stats(self) -> dict:
    """Scheduled Celery task that pulls and updates funnel conversion metrics.

    Sprint 3b / OPS-SF1 — Funnel Stats Updater
    Runs on a schedule (configured in Celery beat schedule).

    In production this task will:
    1. Query the funnel_events table for recent activity
    2. Aggregate conversion rates per funnel stage
    3. Upsert records into the funnel_stats table
    4. Trigger downstream alerts for stages below conversion threshold

    Returns
    -------
    dict
        Summary of the update operation including task ID, status, and
        the number of funnels checked.
    """
    task_id = self.request.id or uuid4().hex

    logger.info("update_funnel_stats started — task_id=%s", task_id)

    try:
        db = make_sync_session()
        try:
            now = datetime.now(timezone.utc)
            period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            period_end = now

            # Aggregate funnel_events grouped by funnel_id and stage
            rows = db.execute(
                select(
                    FunnelEvent.funnel_id,
                    FunnelEvent.stage,
                    func.count().label("cnt"),
                ).group_by(FunnelEvent.funnel_id, FunnelEvent.stage)
            ).all()

            checked = 0
            for row in rows:
                existing = db.execute(
                    select(FunnelStats).where(
                        FunnelStats.funnel_id == row.funnel_id,
                        FunnelStats.stage == row.stage,
                        FunnelStats.period_start == period_start,
                    )
                ).scalar_one_or_none()

                if existing:
                    existing.event_count = row.cnt
                    existing.period_end = period_end
                else:
                    stat = FunnelStats(
                        funnel_id=row.funnel_id,
                        stage=row.stage,
                        event_count=row.cnt,
                        period_start=period_start,
                        period_end=period_end,
                    )
                    db.add(stat)
                checked += 1

            db.commit()
        finally:
            db.close()

        return {
            "task_id": task_id,
            "status": "completed",
            "message": f"Funnel stats updated for {checked} funnel/stage combinations",
            "funnels_checked": checked,
            "updated_at": now.isoformat(),
        }

    except Exception as exc:
        logger.exception(
            "update_funnel_stats failed — task_id=%s error=%s", task_id, exc
        )
        try:
            raise self.retry(exc=exc)
        except MaxRetriesExceededError:
            logger.error(
                "Max retries exceeded for update_funnel_stats task_id=%s", task_id
            )
            raise
