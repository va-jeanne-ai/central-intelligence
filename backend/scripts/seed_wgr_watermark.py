"""Seed the WGR sync watermark so the first enabled hourly run pulls deltas only.

The Phase 4 backfill loaded ~56k WGR rows into CI via the *synchronous* psycopg2
bulk loader (``wgr_sync/bulk_load.py``) — sustained async multi-batch writes hang
on CI's transaction pooler. The hourly task (``app.tasks.wgr_sync.sync_wgr``) runs
over asyncpg, and with no stored watermark it would do a *full* async pull on its
first run — exactly the workload the sync loader was written to avoid.

This script writes a successful ``wgr_sync`` ``SyncLog`` row whose ``watermark`` is
``--as-of`` (default: now). With that in place, the first hourly run resolves an
incremental ``since`` and pulls only rows changed after the backfill — a small,
pooler-safe delta. Run this ONCE, after the backfill and before flipping
``CLIENT_SYNC_ENABLED=true``.

Usage (from backend/):
    PYTHONPATH=. .venv/bin/python -m scripts.seed_wgr_watermark            # as-of now
    PYTHONPATH=. .venv/bin/python -m scripts.seed_wgr_watermark --as-of 2026-06-18T00:00:00+00:00
    PYTHONPATH=. .venv/bin/python -m scripts.seed_wgr_watermark --show     # inspect, no write
"""

from __future__ import annotations

import argparse
import asyncio
import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.audit import SyncLog
from app.tasks.wgr_sync import SYNC_OPERATION


async def _latest(session) -> SyncLog | None:
    return (await session.execute(
        select(SyncLog)
        .where(SyncLog.operation == SYNC_OPERATION, SyncLog.status == "ok")
        .order_by(SyncLog.created_at.desc())
        .limit(1)
    )).scalar_one_or_none()


async def _run(as_of: datetime, show: bool) -> None:
    async with AsyncSessionLocal() as session:
        existing = await _latest(session)
        if existing:
            wm = (existing.details or {}).get("watermark")
            print(f"existing wgr_sync watermark: {wm} (logged {existing.created_at.isoformat()})")
        else:
            print("no existing wgr_sync watermark")

        if show:
            return

        if existing:
            print("refusing to seed — a watermark already exists. Use --show to inspect, "
                  "or let the hourly task advance it. Delete the row manually to re-seed.")
            return

        session.add(SyncLog(
            id=uuid.uuid4(),
            operation=SYNC_OPERATION,
            table_name=None,
            record_count=0,
            status="ok",
            details={
                "since": None,
                "source": "seed",
                "watermark": as_of.isoformat(),
                "counts": {},
                "note": "bootstrap watermark — Phase 4 backfill already loaded; "
                        "first hourly run pulls deltas only.",
            },
        ))
        await session.commit()
        print(f"seeded wgr_sync watermark = {as_of.isoformat()}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Seed the WGR sync watermark.")
    ap.add_argument("--as-of", help="ISO timestamp for the seed watermark (default: now, UTC).")
    ap.add_argument("--show", action="store_true", help="Only print the current watermark; no write.")
    args = ap.parse_args()

    if args.as_of:
        as_of = datetime.fromisoformat(args.as_of)
        if as_of.tzinfo is None:
            as_of = as_of.replace(tzinfo=timezone.utc)
    else:
        as_of = datetime.now(timezone.utc)

    asyncio.run(_run(as_of, args.show))


if __name__ == "__main__":
    main()
