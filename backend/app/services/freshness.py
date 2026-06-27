"""Data-freshness catalog + computation.

Answers the question "is the data up to date?" for every scheduled data
source CI maintains. Two facts drive the answer for each source:

  1. **When did it last successfully run?** — read from one of two places:
       * ``integrations.last_synced_at`` for credential-style providers
         (Mailchimp, Instagram, Facebook, GHL, Google Workspace).
       * the latest ``sync_log`` row for that ``operation`` for task-style
         syncs (WGR, the Google nightly sweeps), which is where tasks
         without an ``integrations`` row record their runs.
  2. **How stale is too stale?** — each source declares the cadence its
     Celery beat entry runs at (see ``app/tasks/celery_app.py``). We allow
     a grace multiple of that interval before calling a source ``stale``;
     a source that has never run is ``unknown``.

The cadences below MIRROR the beat schedule. If you change an interval in
``celery_app.py``, change it here too — there is no runtime coupling, by
design (this endpoint must answer even when the worker/beat are down,
which is exactly when staleness matters most).

This module is pure aside from the two DB reads in ``compute_freshness``;
the verdict logic (:func:`classify`) is a pure function so it's unit-testable
without a database.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import SyncLog
from app.models.integration import Integration
from app.models.intelligence import MarketSignal
from app.models.marketing import FunnelStats


Verdict = Literal["fresh", "stale", "unknown"]

# How long past a source's expected interval before we flag it ``stale``.
# 3× absorbs a couple of missed beat ticks (a worker restart, a slow run)
# without crying wolf, while still catching a genuinely stuck sync.
GRACE_MULTIPLE = 3


@dataclass(frozen=True)
class FreshnessSource:
    """One scheduled data source we report freshness for."""

    key: str  # stable identifier returned to the UI
    label: str  # human-facing name
    # Where the "last ran" timestamp lives:
    #   ("integration", "<provider slug>")  → integrations.last_synced_at
    #   ("sync_log", "<operation>")         → latest sync_log row for op
    #   ("table_updated_at", "<table key>") → MAX(updated_at) on a results
    #       table, for tasks that record neither (funnel_stats, market_signals).
    source_kind: Literal["integration", "sync_log", "table_updated_at"]
    source_ref: str
    interval_minutes: int  # cadence from the beat schedule
    description: str


# Order here is display order. Most business-critical upstream first.
SOURCES: list[FreshnessSource] = [
    FreshnessSource(
        key="wgr",
        label="WGR mirror (leads, calls, appointments)",
        source_kind="sync_log",
        source_ref="wgr_sync",
        interval_minutes=60,  # wgr-sync-hourly
        description="The client's WGR mirror — CI's single upstream for "
        "leads, calls, and appointments. Pulls incrementally every hour.",
    ),
    FreshnessSource(
        key="funnel_stats",
        # funnel_stats task records neither an integrations row nor a
        # sync_log entry — its only freshness signal is the upserted rows'
        # updated_at.
        label="Funnel stats",
        source_kind="table_updated_at",
        source_ref="funnel_stats",
        interval_minutes=60,  # funnel-stats-hourly
        description="Aggregation over funnel_events, recomputed hourly.",
    ),
    FreshnessSource(
        key="market_signals",
        # Same as funnel_stats — freshness is MAX(updated_at) on the
        # recomputed market_signals rows.
        label="Market signals",
        source_kind="table_updated_at",
        source_ref="market_signals",
        interval_minutes=60,  # market-signals-hourly
        description="Rolling 7d/30d windows recomputed from insights, hourly.",
    ),
    FreshnessSource(
        key="instagram",
        label="Instagram metrics",
        source_kind="integration",
        source_ref="instagram",
        interval_minutes=360,  # social-stats-every-6h
        description="Organic post metrics via the Meta Graph API, every 6h.",
    ),
    FreshnessSource(
        key="facebook",
        label="Facebook metrics",
        source_kind="integration",
        source_ref="facebook",
        interval_minutes=360,  # social-stats-every-6h
        description="Page metrics via the Meta Graph API, every 6h.",
    ),
    FreshnessSource(
        key="mailchimp",
        label="Email stats (Mailchimp)",
        source_kind="integration",
        source_ref="mailchimp",
        interval_minutes=360,  # email-stats-every-6h
        description="Campaign opens/clicks/bounces, every 6h.",
    ),
    FreshnessSource(
        key="ghl",
        label="Go High Level contacts",
        source_kind="integration",
        source_ref="ghl",
        interval_minutes=1440,  # nightly pull (when ghl_inbound_enabled)
        description="Contact backfill from GHL. Webhook is real-time; the "
        "pull catches out-of-band edits nightly.",
    ),
    FreshnessSource(
        key="google_workspace",
        label="Gmail / Drive / Calendar",
        source_kind="integration",
        source_ref="google_workspace",
        interval_minutes=1440,  # gmail/drive/calendar nightly sweeps
        description="Per-user Google sync — Gmail threads, Drive files, "
        "Calendar events. Swept nightly.",
    ),
]


@dataclass(frozen=True)
class FreshnessResult:
    """Computed freshness for one source — the per-row payload to the UI."""

    key: str
    label: str
    description: str
    interval_minutes: int
    last_run_at: datetime | None
    last_status: str | None  # raw status string from the source, if any
    age_minutes: float | None  # None when never run
    verdict: Verdict
    detail: str  # short human explanation of the verdict


def classify(
    last_run_at: datetime | None,
    interval_minutes: int,
    now: datetime,
) -> tuple[Verdict, float | None]:
    """Pure verdict logic. Returns (verdict, age_minutes).

    ``unknown`` when the source has never run. Otherwise ``fresh`` while the
    age is within ``GRACE_MULTIPLE`` intervals, else ``stale``.
    """
    if last_run_at is None:
        return "unknown", None

    # Treat naive timestamps as UTC — our columns are timezone-aware but be
    # defensive so a stray naive value can't raise on subtraction.
    if last_run_at.tzinfo is None:
        last_run_at = last_run_at.replace(tzinfo=timezone.utc)

    age_minutes = (now - last_run_at).total_seconds() / 60.0
    threshold = interval_minutes * GRACE_MULTIPLE
    verdict: Verdict = "fresh" if age_minutes <= threshold else "stale"
    return verdict, age_minutes


def _humanize_age(age_minutes: float) -> str:
    """'42 min', '3.2 h', '2.1 d' — matches the frontend's rough buckets."""
    if age_minutes < 60:
        return f"{round(age_minutes)} min"
    hours = age_minutes / 60
    if hours < 24:
        return f"{hours:.1f} h"
    return f"{hours / 24:.1f} d"


def _detail_for(verdict: Verdict, age_minutes: float | None, interval_minutes: int) -> str:
    if verdict == "unknown":
        return "Has never run — no sync recorded yet."
    assert age_minutes is not None  # narrowed by verdict != unknown
    ago = _humanize_age(age_minutes)
    if verdict == "fresh":
        return f"Last synced {ago} ago — within its {interval_minutes // 60 or 1}h cadence."
    return (
        f"Last synced {ago} ago — past {GRACE_MULTIPLE}× its expected cadence. "
        "If the worker/beat were stopped (e.g. end of day), this is expected; "
        "start them and let the schedule catch up."
    )


async def _last_run_from_integration(
    session: AsyncSession, slug: str
) -> tuple[datetime | None, str | None]:
    row = (
        await session.execute(
            select(Integration).where(Integration.provider == slug)
        )
    ).scalar_one_or_none()
    if row is None:
        return None, None
    return row.last_synced_at, row.last_sync_status


async def _last_run_from_sync_log(
    session: AsyncSession, operation: str
) -> tuple[datetime | None, str | None]:
    """Latest *successful* run for an operation, falling back to latest of any
    status so a source that's only ever errored still reports its last attempt."""
    ok_row = (
        await session.execute(
            select(SyncLog)
            .where(SyncLog.operation == operation, SyncLog.status == "ok")
            .order_by(SyncLog.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if ok_row is not None:
        return ok_row.created_at, ok_row.status

    any_row = (
        await session.execute(
            select(SyncLog)
            .where(SyncLog.operation == operation)
            .order_by(SyncLog.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if any_row is None:
        return None, None
    return any_row.created_at, any_row.status


# MAX(updated_at) lookups for tasks that record their freshness only in the
# results table they write. Keyed by the source_ref used in SOURCES above.
_UPDATED_AT_COLUMNS = {
    "funnel_stats": FunnelStats.updated_at,
    "market_signals": MarketSignal.updated_at,
}


async def _last_run_from_table(
    session: AsyncSession, table_key: str
) -> tuple[datetime | None, str | None]:
    column = _UPDATED_AT_COLUMNS.get(table_key)
    if column is None:
        return None, None
    latest = (await session.execute(select(func.max(column)))).scalar_one_or_none()
    # No status concept for a bare MAX(updated_at); the verdict carries the signal.
    return latest, None


async def compute_freshness(
    session: AsyncSession, now: datetime
) -> list[FreshnessResult]:
    """Read each source's last-run timestamp and classify it. ``now`` is
    injected so callers (and tests) control the clock."""
    results: list[FreshnessResult] = []
    for src in SOURCES:
        if src.source_kind == "integration":
            last_run_at, last_status = await _last_run_from_integration(
                session, src.source_ref
            )
        elif src.source_kind == "sync_log":
            last_run_at, last_status = await _last_run_from_sync_log(
                session, src.source_ref
            )
        else:  # table_updated_at
            last_run_at, last_status = await _last_run_from_table(
                session, src.source_ref
            )

        verdict, age = classify(last_run_at, src.interval_minutes, now)
        results.append(
            FreshnessResult(
                key=src.key,
                label=src.label,
                description=src.description,
                interval_minutes=src.interval_minutes,
                last_run_at=last_run_at,
                last_status=last_status,
                age_minutes=age,
                verdict=verdict,
                detail=_detail_for(verdict, age, src.interval_minutes),
            )
        )
    return results
