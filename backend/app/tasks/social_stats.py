"""
Social Stats Celery task — Operator OPS-SS1.

Scheduled task that pulls and updates social media metrics and persists them
to the social_stats table.

Instagram is LIVE: when an ``integrations`` row (provider='instagram',
status='connected') has valid credentials, the task pulls real metrics from
the Meta Graph API and stamps the integration's sync status + a sync_log row.
When Instagram isn't connected (or the pull fails) it is SKIPPED — we never
overwrite real data with seed values.

facebook / linkedin / tiktok are still STUBBED with seed values (no live
connector yet) so the /marketing/social dashboard stays populated. Wire each
the same way Instagram is wired when its connector lands.

Uses a synchronous SQLAlchemy session because Celery runs outside FastAPI's
async event loop.

Sprint 3a / OPS-SS1 — Social Stats Updater
Instagram integration: Meta Graph API (manual-token connector)
"""

import logging
import uuid
from datetime import datetime, timezone
from uuid import uuid4

from celery.exceptions import MaxRetriesExceededError
from sqlalchemy import select

from app.models.audit import SyncLog
from app.models.integration import Integration
from app.models.marketing import SocialStats
from app.services import instagram_client
from app.services.instagram_credentials import load_instagram_credentials
from app.tasks.celery_app import celery_app
from app.tasks.db import make_sync_session

logger = logging.getLogger(__name__)

# Platforms without a live connector yet — keep dashboards populated. Remove a
# platform from here once it has a real integration (as Instagram does below).
_SEED_DATA = {
    "facebook": {"followers": 8320, "posts_count": 54, "engagement_rate": 1.8, "reach": 22000, "impressions": 67000},
    "linkedin": {"followers": 5100, "posts_count": 32, "engagement_rate": 4.1, "reach": 18000, "impressions": 42000},
    "tiktok": {"followers": 3200, "posts_count": 23, "engagement_rate": 6.5, "reach": 95000, "impressions": 310000},
}

_PLATFORMS = ["instagram", "facebook", "linkedin", "tiktok"]


def _upsert_platform_stats(
    db, platform: str, metrics: dict, period_start: datetime, period_end: datetime
) -> None:
    """Upsert one platform's metrics into social_stats for the current period."""
    existing = db.execute(
        select(SocialStats).where(
            SocialStats.platform == platform,
            SocialStats.period_start == period_start,
            SocialStats.deleted_at.is_(None),
        )
    ).scalar_one_or_none()

    if existing:
        for key, value in metrics.items():
            if hasattr(existing, key):
                setattr(existing, key, value)
        existing.period_end = period_end
    else:
        db.add(
            SocialStats(
                platform=platform,
                period_start=period_start,
                period_end=period_end,
                **metrics,
            )
        )


def _sync_instagram(db, period_start: datetime, period_end: datetime) -> str:
    """Pull live Instagram metrics and upsert them.

    Returns one of: 'synced' (live data written), 'skipped' (not connected),
    or 'error' (connected but the pull failed). Stamps the integration row's
    sync status and writes a sync_log entry. Never raises — a problem with
    one platform must not abort the whole task.
    """
    row = db.execute(
        select(Integration).where(Integration.provider == "instagram")
    ).scalar_one_or_none()

    if row is None or row.status != "connected":
        logger.info("Instagram not connected — skipping live sync")
        return "skipped"

    creds = load_instagram_credentials(row)
    if creds is None:
        logger.warning("Instagram connected but credentials unusable — skipping")
        row.last_sync_status = "error"
        row.last_sync_error = "Credentials missing or unparseable"
        return "error"

    access_token, ig_user_id = creds
    now = period_end
    try:
        stats = instagram_client.fetch_instagram_stats(access_token, ig_user_id)
        metrics = {
            "followers": stats.followers,
            "posts_count": stats.posts_count,
            "engagement_rate": stats.engagement_rate,
            "reach": stats.reach,
            "impressions": stats.impressions,
        }
        _upsert_platform_stats(db, "instagram", metrics, period_start, period_end)
        row.last_synced_at = now
        row.last_sync_status = "success"
        row.last_sync_error = None
        db.add(
            SyncLog(
                id=uuid.uuid4(),
                operation="instagram_social_stats_sync",
                status="success",
                details={
                    "followers": stats.followers,
                    "posts_count": stats.posts_count,
                    "reach": stats.reach,
                    "impressions": stats.impressions,
                },
            )
        )
        logger.info(
            "Instagram synced — followers=%s posts=%s reach=%s",
            stats.followers, stats.posts_count, stats.reach,
        )
        return "synced"
    except Exception as exc:  # noqa: BLE001 — isolate IG failure from the task
        logger.exception("Instagram live sync failed: %s", exc)
        row.last_sync_status = "error"
        row.last_sync_error = str(exc)[:500]
        db.add(
            SyncLog(
                id=uuid.uuid4(),
                operation="instagram_social_stats_sync",
                status="error",
                details={"error": str(exc)[:500]},
            )
        )
        return "error"


# OPS-SS1: Scheduled Celery task for social media metrics
@celery_app.task(bind=True, max_retries=3, default_retry_delay=300)
def update_social_stats(self) -> dict:
    """Pull + upsert social media metrics.

    Instagram is pulled live from the Meta Graph API when connected; the other
    platforms use seed values until they get their own connectors.

    Sprint 3a / OPS-SS1 — Social Stats Updater
    Runs on a schedule (configured in Celery beat schedule).

    Returns
    -------
    dict
        Summary including task ID, status, platforms touched, and the
        Instagram sync result ('synced' | 'skipped' | 'error').
    """
    task_id = self.request.id or uuid4().hex

    logger.info("update_social_stats started — task_id=%s", task_id)

    try:
        db = make_sync_session()
        try:
            now = datetime.now(timezone.utc)
            period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            period_end = now
            checked = 0

            # Instagram — live. 'skipped'/'error' both mean we leave any
            # existing instagram row untouched (no fake data overwrite).
            ig_result = _sync_instagram(db, period_start, period_end)
            if ig_result == "synced":
                checked += 1

            # Remaining platforms — seed values until their connectors land.
            for platform in _PLATFORMS:
                if platform == "instagram":
                    continue
                seed = _SEED_DATA.get(platform, {})
                _upsert_platform_stats(db, platform, seed, period_start, period_end)
                checked += 1

            db.commit()
        finally:
            db.close()

        return {
            "task_id": task_id,
            "status": "completed",
            "message": f"Social stats updated for {checked} platform(s)",
            "profiles_checked": checked,
            "instagram": ig_result,
            "updated_at": now.isoformat(),
        }

    except Exception as exc:
        logger.exception(
            "update_social_stats failed — task_id=%s error=%s", task_id, exc
        )
        try:
            raise self.retry(exc=exc)
        except MaxRetriesExceededError:
            logger.error(
                "Max retries exceeded for update_social_stats task_id=%s", task_id
            )
            raise
