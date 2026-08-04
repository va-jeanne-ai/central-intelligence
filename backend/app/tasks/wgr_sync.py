"""Celery task: sync the client's (Greg/WGR) database into CI.

Gated on ``settings.client_sync_enabled``. The watermark for incremental pulls is
persisted in CI's ``sync_log`` table (operation=``wgr_sync``):

  * On each run we read the watermark from the most recent successful ``wgr_sync``
    ``SyncLog`` row (``details->>'watermark'``) and pull only WGR rows whose change
    timestamp is ``>=`` that value, minus a small safety lookback. The first run
    ever finds no prior row → ``since`` is None → full pull (backfill).
  * The *new* watermark is the wall-clock instant captured **before** any WGR row
    is read, so rows written while the run is in flight are caught next time. We
    record it (and per-table counts) in the ``SyncLog`` row written at the end.

The lookback overlap is safe because every write is an idempotent upsert
(``wgr_sync.upsert``) — re-pulling a row already synced is a no-op-or-refresh.

Reads are strictly read-only (``wgr_client`` forces it).
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.config import settings
from app.database import AsyncSessionLocal
from app.models.audit import SyncLog
from app.services.wgr_sync import upsert
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

SYNC_OPERATION = "wgr_sync"

# ---------------------------------------------------------------------------
# Run lock (plan Task 5b): serializes hourly beat, user trigger, and manual
# full pulls. Redis, not Postgres advisory locks — the app DB sits behind
# Supabase's pooler, where session-scoped advisory locks are unreliable.
# ---------------------------------------------------------------------------

import redis as _redis_lib  # noqa: E402 — grouped with its constants

LOCK_KEY = "wgr_sync:run_lock"
# Generous vs. minutes-long runs — avoids TTL-renewal machinery while still
# self-clearing if a worker dies mid-run.
LOCK_TTL_SECONDS = 2 * 60 * 60

# Compare-and-delete: only the owner's token may release the lock (a naive
# DELETE could release a successor's lock after our TTL expired).
_RELEASE_LUA = """
if redis.call('get', KEYS[1]) == ARGV[1] then
    return redis.call('del', KEYS[1])
end
return 0
"""


def _redis():
    # settings.redis_url — the same source Celery uses (celery_app.py).
    return _redis_lib.Redis.from_url(settings.redis_url)


def _acquire_lock(token: str) -> bool:
    # Fail CLOSED — but ONLY on real connectivity errors. Programming errors
    # must crash loudly, never masquerade as "lock held".
    try:
        return bool(_redis().set(LOCK_KEY, token, nx=True, ex=LOCK_TTL_SECONDS))
    except (_redis_lib.exceptions.RedisError, OSError):
        logger.error("wgr_sync: redis unreachable for run lock — skipping run")
        return False


def _release_lock(token: str) -> None:
    try:
        _redis().eval(_RELEASE_LUA, 1, LOCK_KEY, token)
    except Exception:
        pass  # TTL expiry is the backstop


def advances_watermark(since_override: str | None) -> bool:
    """Only scheduled/incremental (None) and full pulls own the canonical
    watermark. A manual partial pull (since=<ISO>) repairs a window; it must
    never advance the cursor past unpulled history (an operator running
    since=now would otherwise skip everything behind it, forever)."""
    return since_override in (None, FORCE_FULL)


def pick_watermark(details_rows) -> datetime | None:
    """Latest row that actually CARRIES a watermark — walks past
    watermark-held rows (manual partial pulls) so one manual pull doesn't
    degrade the next hourly run into a surprise full pull. Pure — no I/O."""
    for row in details_rows:
        raw = row.get("watermark") if isinstance(row, dict) else None
        if not raw:
            continue
        try:
            return datetime.fromisoformat(raw)
        except (ValueError, TypeError):
            logger.warning("wgr_sync: unparseable stored watermark %r — skipping", raw)
            continue
    return None

# Overlap subtracted from the stored watermark before pulling, to catch rows that
# were committed on the WGR side during the previous run or under clock skew.
# Idempotent upserts make the re-pull harmless.
WATERMARK_LOOKBACK = timedelta(minutes=5)

# Sentinel ``since`` value to force a full pull regardless of stored watermark.
FORCE_FULL = "full"


async def _read_watermark(session) -> datetime | None:
    """Return the watermark from the latest successful wgr_sync run that
    carries one (manual partial pulls write watermark_held rows — skip them),
    or None."""
    rows = (await session.execute(
        select(SyncLog.details)
        .where(SyncLog.operation == SYNC_OPERATION, SyncLog.status == "ok")
        .order_by(SyncLog.created_at.desc())
        .limit(20)
    )).scalars()
    return pick_watermark(rows)


def resolve_since(
    since_override: str | None, stored: datetime | None,
) -> tuple[str | None, str]:
    """Decide the effective ``since`` for a run. Pure — no I/O.

    Returns ``(since, source)``:
      * ``since_override`` None        → stored watermark minus lookback, or full
        if none stored yet (``incremental`` / ``bootstrap-full``).
      * ``since_override`` ``"full"``  → full pull, ignoring the stored watermark.
      * ``since_override`` ISO string  → that value verbatim (manual re-sync).
    """
    if since_override == FORCE_FULL:
        return None, "forced-full"
    if since_override:
        return since_override, "manual"
    if stored is None:
        return None, "bootstrap-full"
    return (stored - WATERMARK_LOOKBACK).isoformat(), "incremental"


async def _run(since_override: str | None) -> dict:
    """Resolve the watermark, run the sync, and persist a SyncLog row."""
    # Capture the next watermark BEFORE touching WGR so in-flight writes are
    # caught on the following run.
    new_watermark = datetime.now(timezone.utc)

    async with AsyncSessionLocal() as session:
        stored = None if since_override else await _read_watermark(session)
        since, source = resolve_since(since_override, stored)

        logger.info("wgr_sync: %s pull (since=%s)", source, since)

        try:
            counts = await upsert.sync_all(session, since=since)
        except Exception as exc:  # noqa: BLE001 — record the failure, then re-raise.
            # The sync failure aborts the transaction; roll back before writing
            # the error row, or the INSERT itself fails with
            # InFailedSQLTransactionError and the real cause is never recorded.
            await session.rollback()
            session.add(SyncLog(
                id=uuid.uuid4(),
                operation=SYNC_OPERATION,
                table_name=None,
                record_count=0,
                status="error",
                details={"since": since, "source": source, "fatal": str(exc)[:500]},
            ))
            await session.commit()
            raise

        total = sum(counts.values())
        # Persist the new watermark only on a clean run, so a failed run never
        # advances it — and only for runs that OWN the cursor (incremental /
        # full); manual partial pulls write watermark_held instead.
        details = {"since": since, "source": source, "counts": counts}
        if advances_watermark(since_override):
            details["watermark"] = new_watermark.isoformat()
        else:
            details["watermark_held"] = True
        session.add(SyncLog(
            id=uuid.uuid4(),
            operation=SYNC_OPERATION,
            table_name=None,
            record_count=total,
            status="ok",
            details=details,
        ))
        await session.commit()
        return {"total": total, "counts": counts, "since": since,
                "watermark": details.get("watermark"),
                "watermark_held": details.get("watermark_held", False)}


@celery_app.task(name="app.tasks.wgr_sync.sync_wgr")
def sync_wgr(since: str | None = None) -> dict:
    """Pull WGR → CI.

    ``since``: None = incremental from the stored watermark (first run is a full
    backfill); ``"full"`` = force a full pull; an ISO timestamp = manual re-sync
    from that point.
    """
    if not settings.client_sync_enabled:
        logger.info("wgr_sync: skipped — client_sync_enabled is False")
        return {"status": "skipped", "reason": "client_sync_enabled is False"}

    # Run lock: acquired BEFORE _run() reads the watermark, so no two runs
    # (hourly beat / user trigger / manual pull) can interleave.
    lock_token = str(uuid.uuid4())
    if not _acquire_lock(lock_token):
        logger.info("wgr_sync: skipped — run lock not acquired")
        return {"status": "skipped",
                "reason": "run lock not acquired (held, or redis unreachable — check logs)"}
    try:
        started = datetime.now(timezone.utc)
        result = asyncio.run(_run(since))
    finally:
        _release_lock(lock_token)
    logger.info(
        "wgr_sync: done in %.1fs — %d rows across %d tables (watermark=%s)",
        (datetime.now(timezone.utc) - started).total_seconds(),
        result["total"], len(result["counts"]),
        result["watermark"] or "held",
    )

    # Feed newly-synced rows into the RAG corpus (project RAG-everything policy):
    # without this, synced WGR rows are queryable by SQL but invisible to chat —
    # the vector store would freeze at the Phase 5 snapshot. We chain the two
    # idempotent enqueue backfills rather than filter by a `since` window: these
    # tables carry only `created_at` (preserved across upserts) and no
    # `updated_at`, so a time filter would silently skip re-embedding rows whose
    # content changed upstream. The backfills full-scan but `_enqueue_missing`
    # dedups on content_hash, so only genuinely new/changed rows reach Voyage.
    # Skip entirely when nothing synced — no new rows means nothing to embed.
    enqueued = False
    if result["total"] > 0:
        # Lazy import — avoids a task-module import cycle at worker startup.
        from app.tasks.embed_backfill import (
            backfill_email_campaigns_embeddings,
            backfill_insights_embeddings,
            backfill_wgr_embeddings,
        )
        backfill_wgr_embeddings.delay()
        backfill_insights_embeddings.delay()
        # email_campaigns is one of the tables WGR mirrors directly (see
        # wgr_sync/upsert.py) — a WGR sync can bring in campaigns the
        # Mailchimp task never saw, so chain the same embed backfill here too.
        backfill_email_campaigns_embeddings.delay()
        enqueued = True
        logger.info(
            "wgr_sync: enqueued WGR + insights + email_campaigns embedding backfills"
        )

    return {"status": "ok", "embed_backfills_enqueued": enqueued, **result}
