"""
Social Stats Celery task — Operator OPS-SS1.

Scheduled task that pulls and updates social media metrics and persists them
to the social_stats table.

Instagram and Facebook are LIVE: when an ``integrations`` row (provider=
'instagram' / 'facebook', status='connected') has valid credentials, the task
pulls real metrics from the Meta Graph API and stamps the integration's sync
status + a sync_log row. When a platform isn't connected (or the pull fails)
it is SKIPPED — we never overwrite real data with seed values.

linkedin / tiktok are still STUBBED with seed values (no live connector yet)
so the /marketing/social dashboard stays populated. Wire each the same way
when its connector lands.

Uses a synchronous SQLAlchemy session because Celery runs outside FastAPI's
async event loop.

Sprint 3a / OPS-SS1 — Social Stats Updater
Instagram + Facebook integrations: Meta Graph API (manual-token connectors)
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
from app.services import facebook_client, instagram_client
from app.services.facebook_credentials import load_facebook_credentials
from app.services.instagram_credentials import load_instagram_credentials
from app.tasks.celery_app import celery_app
from app.tasks.db import make_sync_session

logger = logging.getLogger(__name__)

# Platforms without a live connector yet — keep dashboards populated. Remove a
# platform from here once it has a real integration (as Instagram + Facebook do).
_SEED_DATA = {
    "linkedin": {"followers": 5100, "posts_count": 32, "engagement_rate": 4.1, "reach": 18000, "impressions": 42000},
    "tiktok": {"followers": 3200, "posts_count": 23, "engagement_rate": 6.5, "reach": 95000, "impressions": 310000},
}

# Platforms with a live Meta Graph connector. Each entry: how to load creds
# from the integration row + how to fetch its stats. Both return an object
# with followers/posts_count/engagement_rate/reach/impressions.
_LIVE_PLATFORMS = {
    "instagram": (load_instagram_credentials, instagram_client.fetch_instagram_stats),
    "facebook": (load_facebook_credentials, facebook_client.fetch_facebook_stats),
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


def _sync_live_platform(
    db, platform: str, period_start: datetime, period_end: datetime
) -> str:
    """Pull live metrics for one Meta-connected platform and upsert them.

    Driven by ``_LIVE_PLATFORMS[platform]`` = (creds_loader, fetch_fn). Returns
    one of: 'synced' (live data written), 'skipped' (not connected), or 'error'
    (connected but the pull failed). Stamps the integration row's sync status
    and writes a sync_log entry. Never raises — a problem with one platform
    must not abort the whole task.
    """
    load_creds, fetch_stats = _LIVE_PLATFORMS[platform]

    row = db.execute(
        select(Integration).where(Integration.provider == platform)
    ).scalar_one_or_none()

    if row is None or row.status != "connected":
        logger.info(
            "[social-sync] %s: not connected (row=%s, status=%s) — skipping",
            platform, "yes" if row else "none", getattr(row, "status", None),
        )
        return "skipped"

    creds = load_creds(row)
    if creds is None:
        logger.warning(
            "[social-sync] %s: connected but credentials unusable "
            "(decrypt/parse failed or missing token/id) — skipping", platform,
        )
        row.last_sync_status = "error"
        row.last_sync_error = "Credentials missing or unparseable"
        return "error"

    access_token, account_id = creds
    # Mask the token in logs — show only length + last 4 chars.
    masked = f"…{access_token[-4:]} (len {len(access_token)})" if access_token else "(empty)"
    logger.info(
        "[social-sync] %s: creds OK — account_id=%s token=%s; calling Graph API…",
        platform, account_id, masked,
    )
    try:
        stats = fetch_stats(access_token, account_id)
        metrics = {
            "followers": stats.followers,
            "posts_count": stats.posts_count,
            "engagement_rate": stats.engagement_rate,
            "reach": stats.reach,
            "impressions": stats.impressions,
        }
        logger.info("[social-sync] %s: fetched live metrics → %s", platform, metrics)
        _upsert_platform_stats(db, platform, metrics, period_start, period_end)
        row.last_synced_at = period_end
        row.last_sync_status = "success"
        row.last_sync_error = None
        db.add(
            SyncLog(
                id=uuid.uuid4(),
                operation=f"{platform}_social_stats_sync",
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
            "[social-sync] %s: SYNCED + upserted for period %s → %s "
            "(followers=%s posts=%s impressions=%s)",
            platform, period_start.date(), period_end.date(),
            stats.followers, stats.posts_count, stats.impressions,
        )
        return "synced"
    except Exception as exc:  # noqa: BLE001 — isolate one platform's failure
        logger.exception("[social-sync] %s: live fetch FAILED — %s", platform, exc)
        row.last_sync_status = "error"
        row.last_sync_error = str(exc)[:500]
        db.add(
            SyncLog(
                id=uuid.uuid4(),
                operation=f"{platform}_social_stats_sync",
                status="error",
                details={"error": str(exc)[:500]},
            )
        )
        return "error"


# OPS-SS1: Scheduled Celery task for social media metrics
@celery_app.task(bind=True, max_retries=3, default_retry_delay=300)
def update_social_stats(self) -> dict:
    """Pull + upsert social media metrics.

    Instagram + Facebook are pulled live from the Meta Graph API when
    connected; the remaining platforms use seed values until they get their
    own connectors.

    Sprint 3a / OPS-SS1 — Social Stats Updater
    Runs on a schedule (configured in Celery beat schedule).

    Returns
    -------
    dict
        Summary including task ID, status, platforms touched, and each live
        platform's sync result ('synced' | 'skipped' | 'error').
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
            live_results: dict[str, str] = {}

            # Live Meta platforms. 'skipped'/'error' both leave any existing
            # row untouched (no fake-data overwrite).
            for platform in _LIVE_PLATFORMS:
                result = _sync_live_platform(db, platform, period_start, period_end)
                live_results[platform] = result
                if result == "synced":
                    checked += 1

            # Remaining platforms — seed values until their connectors land.
            for platform in _PLATFORMS:
                if platform in _LIVE_PLATFORMS:
                    continue
                seed = _SEED_DATA.get(platform, {})
                _upsert_platform_stats(db, platform, seed, period_start, period_end)
                checked += 1

            logger.info(
                "[social-sync] summary — live=%s seeded=%s",
                live_results,
                [p for p in _PLATFORMS if p not in _LIVE_PLATFORMS],
            )
            db.commit()
        finally:
            db.close()

        return {
            "task_id": task_id,
            "status": "completed",
            "message": f"Social stats updated for {checked} platform(s)",
            "profiles_checked": checked,
            **live_results,
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
