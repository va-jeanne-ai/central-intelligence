"""Idempotent WGR → CI upserts.

Reads from WGR (read-only) via ``reader``, maps via ``mapping``, and upserts into
CI's own DB in small batches (the CI Supabase is pooler-only with a short
``statement_timeout``, so we never run an unbounded statement — same lesson as
``scripts/clear_domain_data.py``).

Upsert strategy per table family:
  * WGR-native-PK tables (sales_*, offers, business_profile, insights,
    content_ideas, calls, webinar/opt-in) → Postgres ``INSERT ... ON CONFLICT
    (<pk>) DO UPDATE``. Re-running is a no-op-or-refresh.
  * leads → merge on the partial unique index ``(source='wgr', external_id)``;
    CI generates the UUID PK so new rows get a fresh uuid4.
  * appointments → no unique index on (source, external_id), so select-by
    (source, external_id) then insert/update. lead linkage resolved from the
    WGR lead_id → CI lead row.
  * market_signals → unique on (signal_family, signal); merge on that.

All functions take an open AsyncSession and commit in batches. Counts returned.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Callable, Iterable, Optional

from sqlalchemy import insert, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.marketing import OptInEvent, WebinarEngagement
from app.models.intelligence import BusinessProfile, MarketSignal, Offer
from app.models.operational import Appointment, ContentIdea, Insight, Lead, Call
from app.models.sales import (
    CallScore, ClosedSale, CoachingStrike, EodReport, SalesActivity, SalesRep,
    ScorecardCategory, StrikeAction, StrikeEvidence, StrikeRule,
)
from app.services.wgr_sync import mapping, reader

logger = logging.getLogger(__name__)

BATCH = 500


async def _on_conflict_upsert(
    session: AsyncSession, model, pk_col: str, rows: list[dict[str, Any]],
) -> int:
    """INSERT ... ON CONFLICT (pk) DO UPDATE for a batch. Returns rows written."""
    if not rows:
        return 0
    stmt = pg_insert(model.__table__).values(rows)
    update_cols = {
        c.name: stmt.excluded[c.name]
        for c in model.__table__.columns
        if c.name != pk_col and c.name != "created_at"
    }
    stmt = stmt.on_conflict_do_update(index_elements=[pk_col], set_=update_cols)
    await session.execute(stmt)
    return len(rows)


async def _sync_native_pk(
    session: AsyncSession, *, wgr_table: str, model, pk_col: str,
    map_fn: Callable[[dict], Optional[dict]], since: Optional[str],
) -> int:
    """Generic sync for WGR-native-PK tables, batched + ON CONFLICT."""
    batch: list[dict[str, Any]] = []
    total = 0
    for raw in reader.read_table(wgr_table, since=since):
        mapped = map_fn(raw)
        if mapped is None:
            continue
        batch.append(mapped)
        if len(batch) >= BATCH:
            total += await _on_conflict_upsert(session, model, pk_col, batch)
            await session.commit()
            batch = []
    if batch:
        total += await _on_conflict_upsert(session, model, pk_col, batch)
        await session.commit()
    logger.info("wgr_sync %s: upserted %d", wgr_table, total)
    return total


# ---------------------------------------------------------------------------
# Leads — merge on (source='wgr', external_id); CI generates UUID PK.
# ---------------------------------------------------------------------------

async def sync_leads(session: AsyncSession, *, since: Optional[str] = None) -> int:
    total = 0
    batch_maps: list[dict[str, Any]] = []

    async def flush(maps: list[dict[str, Any]]) -> int:
        if not maps:
            return 0
        # De-dup within the batch on external_id (last wins) so a single bulk
        # insert can't violate the unique index.
        maps = list({m["external_id"]: m for m in maps}.values())
        ext_ids = [m["external_id"] for m in maps]
        existing = (await session.execute(
            select(Lead.id, Lead.external_id).where(
                Lead.source == mapping.WGR_SOURCE, Lead.external_id.in_(ext_ids),
            )
        )).all()
        by_ext = {ext: lid for lid, ext in existing}
        # Bulk-insert the new rows in one statement; per-row update only the
        # (usually rare) already-present ones.
        new_rows = [
            {"id": uuid.uuid4(), **m} for m in maps if m["external_id"] not in by_ext
        ]
        if new_rows:
            await session.execute(insert(Lead), new_rows)
        for m in maps:
            if m["external_id"] in by_ext:
                await session.execute(
                    update(Lead).where(Lead.id == by_ext[m["external_id"]]).values(**m)
                )
        await session.commit()
        return len(maps)

    for raw in reader.read_table("leads", since=since):
        mapped = mapping.map_lead(raw)
        if mapped is None:
            continue
        batch_maps.append(mapped)
        if len(batch_maps) >= BATCH:
            total += await flush(batch_maps)
            batch_maps = []
    total += await flush(batch_maps)
    logger.info("wgr_sync leads: upserted %d", total)
    return total


# ---------------------------------------------------------------------------
# Appointments — select-by (source, external_id), then insert/update. Resolve
# the CI lead UUID from the WGR lead_id carried on the mapped row.
# ---------------------------------------------------------------------------

async def sync_appointments(session: AsyncSession, *, since: Optional[str] = None) -> int:
    total = 0
    batch: list[dict[str, Any]] = []

    async def flush(maps: list[dict[str, Any]]) -> int:
        if not maps:
            return 0
        # Resolve WGR lead_id → CI lead UUID in one query for the batch.
        wgr_lead_ids = {m["_wgr_lead_id"] for m in maps if m.get("_wgr_lead_id")}
        lead_map: dict[str, Any] = {}
        if wgr_lead_ids:
            rows = (await session.execute(
                select(Lead.external_id, Lead.id).where(
                    Lead.source == mapping.WGR_SOURCE, Lead.external_id.in_(wgr_lead_ids),
                )
            )).all()
            lead_map = {ext: lid for ext, lid in rows}
        maps = list({m["external_id"]: m for m in maps}.values())
        ext_ids = [m["external_id"] for m in maps]
        existing = (await session.execute(
            select(Appointment.id, Appointment.external_id).where(
                Appointment.source == mapping.WGR_SOURCE, Appointment.external_id.in_(ext_ids),
            )
        )).all()
        by_ext = {ext: aid for aid, ext in existing}
        new_rows = []
        updates = []
        for m in maps:
            wgr_lead = m.pop("_wgr_lead_id", None)
            m["lead_id"] = lead_map.get(wgr_lead)
            if m["external_id"] in by_ext:
                updates.append(m)
            else:
                new_rows.append({"id": uuid.uuid4(), **m})
        if new_rows:
            await session.execute(insert(Appointment), new_rows)
        for m in updates:
            await session.execute(
                update(Appointment).where(Appointment.id == by_ext[m["external_id"]]).values(**m)
            )
        await session.commit()
        return len(maps)

    for raw in reader.read_table("appointments", since=since):
        mapped = mapping.map_appointment(raw)
        if mapped is None:
            continue
        batch.append(mapped)
        if len(batch) >= BATCH:
            total += await flush(batch)
            batch = []
    total += await flush(batch)
    logger.info("wgr_sync appointments: upserted %d", total)
    return total


async def sync_market_signals(session: AsyncSession) -> int:
    """market_signals merge on (signal_family, signal) unique key."""
    total = 0
    batch: list[dict[str, Any]] = []

    async def flush(maps: list[dict[str, Any]]) -> int:
        if not maps:
            return 0
        stmt = pg_insert(MarketSignal.__table__).values(maps)
        update_cols = {
            c.name: stmt.excluded[c.name]
            for c in MarketSignal.__table__.columns
            if c.name not in ("id", "signal_family", "signal")
        }
        stmt = stmt.on_conflict_do_update(
            index_elements=["signal_family", "signal"], set_=update_cols,
        )
        await session.execute(stmt)
        await session.commit()
        return len(maps)

    for raw in reader.read_table("market_signals"):
        mapped = mapping.map_market_signal(raw)
        if mapped is None:
            continue
        batch.append(mapped)
        if len(batch) >= BATCH:
            total += await flush(batch)
            batch = []
    total += await flush(batch)
    logger.info("wgr_sync market_signals: upserted %d", total)
    return total


# ---------------------------------------------------------------------------
# Orchestrator — runs all tables in dependency order. Returns per-table counts.
# ---------------------------------------------------------------------------

# (wgr_table, model, pk_col, map_fn) for the native-PK family, in FK-safe order.
_NATIVE_PLAN: list[tuple] = [
    ("business_profile", BusinessProfile, "id", mapping.map_business_profile),
    ("offers", Offer, "offer_id", mapping.map_offer),
    ("sales_reps", SalesRep, "rep_id", mapping.map_sales_rep),
    ("sales_scorecard_categories", ScorecardCategory, "category_id", mapping.map_scorecard_category),
    ("calls", Call, "id", mapping.map_call),
    ("insights", Insight, "id", mapping.map_insight),
    ("content_ideas", ContentIdea, "id", mapping.map_content_idea),
    ("sales_strike_rules", StrikeRule, "rule_id", mapping.map_strike_rule),
    ("sales_call_scores", CallScore, "score_id", mapping.map_call_score),
    ("sales_coaching_strikes", CoachingStrike, "strike_id", mapping.map_coaching_strike),
    ("sales_strike_actions", StrikeAction, "action_id", mapping.map_strike_action),
    ("sales_strike_evidence", StrikeEvidence, "evidence_id", mapping.map_strike_evidence),
    ("sales_eod_reports", EodReport, "report_id", mapping.map_eod_report),
    ("sales", ClosedSale, "sale_id", mapping.map_closed_sale),
    ("sales_activities", SalesActivity, "activity_id", mapping.map_sales_activity),
    ("webinar_engagements", WebinarEngagement, "engagement_id", mapping.map_webinar_engagement),
    ("lead_opt_in_events", OptInEvent, "opt_in_event_id", mapping.map_opt_in_event),
]


async def sync_all(session: AsyncSession, *, since: Optional[str] = None) -> dict[str, int]:
    """Full WGR → CI sync in dependency order. Idempotent. Returns counts."""
    counts: dict[str, int] = {}

    # 1. leads first (appointments + sales reference CI lead UUIDs).
    counts["leads"] = await sync_leads(session, since=since)
    # 2. native-PK tables (business_profile/offers/reps/calls/insights/... first
    #    in the list so their children's FKs resolve).
    for wgr_table, model, pk_col, map_fn in _NATIVE_PLAN:
        counts[wgr_table] = await _sync_native_pk(
            session, wgr_table=wgr_table, model=model, pk_col=pk_col,
            map_fn=map_fn, since=since,
        )
    # 3. appointments (needs leads) + market_signals.
    counts["appointments"] = await sync_appointments(session, since=since)
    counts["market_signals"] = await sync_market_signals(session)
    return counts
