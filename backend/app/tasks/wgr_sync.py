"""Celery task: sync the client's (Greg/WGR) database into CI.

Gated on ``settings.client_sync_enabled``. The first run is a full backfill
(watermark null → full pull); subsequent runs pass a watermark so only changed
rows are pulled. Watermark is stored per-source in CI's ``sync_log``.

Reads are strictly read-only (``wgr_client`` forces it). Writes are idempotent
upserts (``wgr_sync.upsert``), so re-running never duplicates.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from app.config import settings
from app.database import AsyncSessionLocal
from app.services.wgr_sync import upsert
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

SYNC_OPERATION = "wgr_sync"


async def _run(since: str | None) -> dict[str, int]:
    async with AsyncSessionLocal() as session:
        return await upsert.sync_all(session, since=since)


@celery_app.task(name="app.tasks.wgr_sync.sync_wgr")
def sync_wgr(since: str | None = None) -> dict:
    """Pull WGR → CI. ``since`` ISO timestamp for incremental; None = full backfill."""
    if not settings.client_sync_enabled:
        logger.info("wgr_sync: skipped — client_sync_enabled is False")
        return {"status": "skipped", "reason": "client_sync_enabled is False"}

    started = datetime.now(timezone.utc)
    counts = asyncio.run(_run(since))
    total = sum(counts.values())
    logger.info(
        "wgr_sync: done in %.1fs — %d rows across %d tables",
        (datetime.now(timezone.utc) - started).total_seconds(), total, len(counts),
    )
    return {"status": "ok", "total": total, "counts": counts}
