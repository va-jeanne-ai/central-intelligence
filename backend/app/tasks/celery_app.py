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
        "app.tasks.market_signals",
        "app.tasks.ads_stats",
        "app.tasks.offer_generator",
        "app.tasks.ghl_sync",
        "app.tasks.ghl_push",
        "app.tasks.gmail_sync",
        "app.tasks.drive_sync",
        "app.tasks.calendar_sync",
        "app.tasks.embed_worker",
        "app.tasks.embed_backfill",
        "app.tasks.wgr_sync",
        "app.tasks.metric_snapshots",
        "app.tasks.overall_insight",
        "app.tasks.weekly_digest",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    # Default fork count for a bare `celery worker` (no --concurrency flag).
    # Unbounded, celery forks one child per CPU core and each child opens its
    # own DB pool — enough to exhaust the Supabase session pooler's 15-client
    # cap alongside production (EMAXCONNSESSION, repeatedly on 2026-07-17).
    # A CLI --concurrency flag still overrides this (prod compose passes 2).
    worker_concurrency=2,
)

# Beat schedule — staggered intervals (UTC) so tasks don't all fire simultaneously.
# Each task is safe re-running: upsert semantics, no double-inserts, no wipe of seeded data
# (the 5 stats updaters key on current-month period_start, which differs from seed periods).
celery_app.conf.beat_schedule = {
    "funnel-stats-hourly": {
        "task": "app.tasks.funnel_stats.update_funnel_stats",
        "schedule": crontab(minute=5),  # every hour at :05 — cheap aggregation over funnel_events
    },
    "market-signals-hourly": {
        "task": "app.tasks.market_signals.update_market_signals",
        # every hour at :35 — recompute market_signals from insights (rolling 7d/30d
        # windows need a full recompute, not increments). Off the :05–:25 updaters.
        "schedule": crontab(minute=35),
    },
    "metric-snapshots-daily": {
        "task": "app.tasks.metric_snapshots.capture_metric_snapshots",
        # 03:50 UTC daily — snapshot every registered outcome metric into the
        # metric_snapshots timeseries (data-intelligence engine). Runs after the
        # nightly syncs so the day's snapshot reflects freshly-pooled data.
        # Idempotent per day (unique constraint upserts).
        "schedule": crontab(minute=50, hour=3),
    },
    "overall-insight-daily": {
        "task": "app.tasks.overall_insight.capture_overall_insight",
        # 04:05 UTC daily — 15 min AFTER metric-snapshots so the assessment reads the
        # day's fresh snapshots/trends/recommendations. Compounds on the prior day.
        # COST: one paid Claude call per run when mock_mode=False; a free mock otherwise.
        # Idempotent per day (upsert on insight_date).
        "schedule": crontab(minute=5, hour=4),
    },
    "weekly-digest-mondays": {
        "task": "app.tasks.weekly_digest.capture_weekly_digest",
        # 05:05 UTC Mondays — 1 hour AFTER the daily overall-insight run so the digest
        # can read Monday's own fresh daily assessment as part of the week it covers.
        # COST: at most one paid Claude call per run when mock_mode=False; no-ops
        # entirely (no call) if there's no data for the week. Idempotent per week
        # (upsert on insight_date=week-start, period='weekly').
        "schedule": crontab(minute=5, hour=5, day_of_week=1),
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
    # NOTE: ghl-contacts-sync-nightly was removed in the WGR rebase. CI no longer
    # pulls contacts directly from GoHighLevel — the client's WGR mirror is the
    # single upstream for leads/appointments (see app/tasks/wgr_sync.py). The
    # ghl_sync task module stays importable so the path can be restored by
    # re-adding this entry and setting ghl_inbound_enabled=True.
    "gmail-thread-sync-nightly": {
        "task": "app.tasks.gmail_sync.sync_gmail_threads",
        # 02:45 UTC — runs after the GHL sync so newly-discovered leads
        # get their email threads on the same nightly cycle.
        "schedule": crontab(minute=45, hour=2),
    },
    "google-drive-sync-nightly": {
        "task": "app.tasks.drive_sync.sync_drive_files",
        # 03:00 UTC — runs after Gmail. Drive sweeps every connected
        # user's files and enqueues embed_pending rows for changed
        # content; the embed_worker (below) picks them up shortly after.
        "schedule": crontab(minute=0, hour=3),
    },
    "google-calendar-sync-nightly": {
        "task": "app.tasks.calendar_sync.sync_calendar_events",
        # 03:15 UTC — 15 minutes after Drive so we don't open two
        # Google API + Supabase connection storms at the same instant.
        "schedule": crontab(minute=15, hour=3),
    },
    "embed-queue-drain": {
        "task": "app.tasks.embed_worker.drain_embed_queue",
        # Every 2 minutes — keeps the RAG corpus close to real-time
        # without long-running tasks. Drains a batch each tick.
        "schedule": crontab(minute="*/2"),
    },
    "wgr-sync-hourly": {
        "task": "app.tasks.wgr_sync.sync_wgr",
        # :50 every hour — incremental pull from the client's WGR mirror (CI's
        # single upstream for leads/calls/appointments/etc.). No-op unless
        # client_sync_enabled=True. Off-peak of the other updaters.
        "schedule": crontab(minute=50),
    },
}
