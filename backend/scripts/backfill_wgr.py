"""One-time (or repeatable) WGR → CI backfill driver.

Runs the full idempotent sync directly (no Celery worker needed). Safe to
re-run. ``--dry-run`` only reports WGR source counts vs current CI counts so you
can eyeball the expected load before writing.

Usage (from backend/):
    PYTHONPATH=. .venv/bin/python -m scripts.backfill_wgr --dry-run
    PYTHONPATH=. .venv/bin/python -m scripts.backfill_wgr --yes
"""

from __future__ import annotations

import asyncio
import sys

from sqlalchemy import func, select

from app.database import AsyncSessionLocal
from app.services import wgr_client
from app.services.wgr_sync import mapping, reader, upsert
from app.models.intelligence import BusinessProfile, MarketSignal, Offer
from app.models.marketing import OptInEvent, WebinarEngagement
from app.models.operational import Appointment, ContentIdea, Insight, Lead, Call
from app.models.sales import (
    CallScore, ClosedSale, CoachingStrike, EodReport, SalesActivity, SalesRep,
    ScorecardCategory, StrikeAction, StrikeEvidence, StrikeRule,
)

# WGR table → CI model, for the dry-run comparison.
_COMPARE = [
    ("leads", Lead), ("calls", Call), ("appointments", Appointment),
    ("insights", Insight), ("content_ideas", ContentIdea), ("market_signals", MarketSignal),
    ("offers", Offer), ("business_profile", BusinessProfile),
    ("sales_reps", SalesRep), ("sales_scorecard_categories", ScorecardCategory),
    ("sales_call_scores", CallScore), ("sales_strike_rules", StrikeRule),
    ("sales_coaching_strikes", CoachingStrike), ("sales_strike_actions", StrikeAction),
    ("sales_strike_evidence", StrikeEvidence), ("sales_eod_reports", EodReport),
    ("sales", ClosedSale), ("sales_activities", SalesActivity),
    ("webinar_engagements", WebinarEngagement), ("lead_opt_in_events", OptInEvent),
]


async def dry_run() -> None:
    print(f"{'WGR table':<30}{'WGR rows':>10}{'CI rows now':>14}")
    print("-" * 54)
    async with AsyncSessionLocal() as s:
        for wgr_table, model in _COMPARE:
            wgr_n = wgr_client.count(wgr_table)
            ci_n = (await s.execute(select(func.count()).select_from(model))).scalar()
            print(f"{wgr_table:<30}{wgr_n:>10}{ci_n:>14}")
    print("\nDry run only. Re-run with --yes to backfill.")


def execute() -> None:
    # Sync psycopg2 bulk loader — robust over the transaction pooler (the async
    # path hangs on sustained multi-batch writes).
    from app.services.wgr_sync import bulk_load
    counts = bulk_load.run_backfill(since=None)
    print("\nBackfill complete. Rows upserted per table:")
    for k, v in counts.items():
        print(f"  {k:<30}{v:>8}")
    print(f"  {'TOTAL':<30}{sum(counts.values()):>8}")


if __name__ == "__main__":
    if "--yes" in sys.argv:
        execute()
    else:
        asyncio.run(dry_run())
