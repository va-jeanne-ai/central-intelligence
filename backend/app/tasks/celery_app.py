"""
Celery application instance for Central Intelligence background tasks.

The broker and result backend are both driven by the Redis URL from
``app.config.settings``.  All task modules are listed in ``include``
so that Celery discovers them automatically when a worker starts.

Sprint 2 / CI-CORE-01 / T01-1
"""

from celery.schedules import crontab

from celery import Celery

from app.config import settings

celery_app = Celery(
    "centralintelligence",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "app.tasks.transcriber",
        "app.tasks.call_analyzer",
        "app.tasks.icp",
        "app.tasks.email_stats",
        "app.tasks.social_stats",
        "app.tasks.comments_collector",
        "app.tasks.funnel_stats",
        "app.tasks.ads_stats",
        "app.tasks.offer_generator",
        "app.tasks.ghl_sync",
        "app.tasks.ghl_push",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
)

# Beat schedule — staggered intervals (UTC) so tasks don't all fire simultaneously.
# Each task is safe re-running: upsert semantics, no double-inserts, no wipe of seeded data
# (the 5 stats updaters key on current-month period_start, which differs from seed periods).
celery_app.conf.beat_schedule = {
    "funnel-stats-hourly": {
        "task": "app.tasks.funnel_stats.update_funnel_stats",
        "schedule": crontab(minute=5),  # every hour at :05 — cheap aggregation over funnel_events
    },
    "social-stats-every-6h": {
        "task": "app.tasks.social_stats.update_social_stats",
        "schedule": crontab(minute=10, hour="*/6"),  # 00:10, 06:10, 12:10, 18:10 UTC
    },
    "email-stats-every-6h": {
        "task": "app.tasks.email_stats.update_email_stats",
        "schedule": crontab(minute=15, hour="*/6"),  # 00:15, 06:15, 12:15, 18:15 UTC
    },
    "ads-stats-every-6h": {
        "task": "app.tasks.ads_stats.update_ads_stats",
        "schedule": crontab(minute=20, hour="*/6"),  # 00:20, 06:20, 12:20, 18:20 UTC
    },
    "comments-collector-every-4h": {
        "task": "app.tasks.comments_collector.collect_social_comments",
        "schedule": crontab(minute=25, hour="*/4"),  # 00:25, 04:25, ... 20:25 UTC
    },
    "ghl-contacts-sync-nightly": {
        "task": "app.tasks.ghl_sync.sync_ghl_contacts",
        # 02:30 UTC — off-peak, away from the :05-:25 stat updaters above.
        # Daily cadence catches out-of-band GHL edits the webhook doesn't fire on.
        "schedule": crontab(minute=30, hour=2),
    },
}
