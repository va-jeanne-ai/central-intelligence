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

from sqlalchemy import insert, inspect, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.marketing import (
    EmailCampaign, InstagramPost, OptInEvent, SocialComment, WebinarEngagement,
)
from app.models.intelligence import (
    BusinessProfile, InsightTag, MarketSignal, Offer, TagDictionary,
)
from app.models.operational import Appointment, ContentIdea, Insight, Lead, Call
from app.models.sales import (
    CallScore, ClosedSale, CoachingStrike, EodReport, SalesActivity, SalesRep,
    ScorecardCategory, StrikeAction, StrikeEvidence, StrikeRule,
)
from app.services.wgr_sync import mapping, reader

logger = logging.getLogger(__name__)

BATCH = 500


def _attr_to_column_map(model) -> dict[str, str]:
    """ORM attribute name → DB column name, for attrs that differ from columns.

    The mapping functions key rows by ORM attribute (e.g. ``activity_metadata``),
    but ``pg_insert(model.__table__)`` operates on the Table and expects column
    names (e.g. ``metadata``). Where they differ, translate; otherwise the column
    name is rejected as an "unconsumed column name". Built from the mapper so any
    attr≠column pair (not just the known ``metadata`` one) is handled.
    """
    out: dict[str, str] = {}
    for attr in inspect(model).column_attrs:
        col_name = attr.expression.name
        if attr.key != col_name:
            out[attr.key] = col_name
    return out


async def _null_orphan_fks(
    session: AsyncSession,
    rows: list[dict[str, Any]],
    checks: list[tuple[str, Any]],
) -> dict[str, int]:
    """NULL nullable-FK columns whose referenced parent isn't present in CI.

    WGR child rows routinely reference a parent that CI filtered out (TEST_ calls)
    or hasn't synced into the current window. For ``ON DELETE SET NULL`` /
    nullable FK columns the schema's intent is to tolerate the gap, so we null the
    orphan rather than let the INSERT abort the whole sync transaction.

    ``checks`` is a list of ``(fk_key, parent_pk_column)`` — e.g.
    ``[("example_call_id", Call.id)]``. Mutates ``rows`` in place; returns a
    per-key count of how many references were nulled.
    """
    nulled: dict[str, int] = {}
    for fk_key, parent_pk in checks:
        ref_ids = {r[fk_key] for r in rows if r.get(fk_key)}
        if not ref_ids:
            continue
        present = set((await session.execute(
            select(parent_pk).where(parent_pk.in_(ref_ids))
        )).scalars())
        n = 0
        for r in rows:
            if r.get(fk_key) and r[fk_key] not in present:
                r[fk_key] = None
                n += 1
        if n:
            nulled[fk_key] = n
    return nulled


async def _on_conflict_upsert(
    session: AsyncSession, model, pk_col: str, rows: list[dict[str, Any]],
) -> int:
    """INSERT ... ON CONFLICT (pk) DO UPDATE for a batch. Returns rows written."""
    if not rows:
        return 0
    remap = _attr_to_column_map(model)
    if remap:
        rows = [
            {remap.get(k, k): v for k, v in row.items()}
            for row in rows
        ]
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


async def sync_calls(session: AsyncSession, *, since: Optional[str] = None) -> int:
    """Calls sync — like the generic native-PK path but resolves the WGR
    lead_id → CI lead UUID per batch so ``calls.lead_id`` is populated.

    Calls have a stable PK (CI id = WGR call_id) so we keep the ON-CONFLICT
    upsert; only the lead-FK resolution is bolted on (mirrors appointments).
    Without this, ``calls.lead_id`` stays NULL and the lead → calls → insights
    → insight_tags chain (used by the per-lead tags endpoint) is broken.
    """
    batch: list[dict[str, Any]] = []
    total = 0

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
        for m in maps:
            wgr_lead = m.pop("_wgr_lead_id", None)
            m["lead_id"] = lead_map.get(wgr_lead)
        written = await _on_conflict_upsert(session, Call, "id", maps)
        await session.commit()
        return written

    for raw in reader.read_table("calls", since=since):
        mapped = mapping.map_call(raw)
        if mapped is None:
            continue
        batch.append(mapped)
        if len(batch) >= BATCH:
            total += await flush(batch)
            batch = []
    total += await flush(batch)
    logger.info("wgr_sync calls: upserted %d", total)
    return total


async def sync_market_signals(session: AsyncSession) -> int:
    """market_signals merge on (signal_family, signal) unique key."""
    total = 0
    batch: list[dict[str, Any]] = []

    nulled_total = 0

    async def flush(maps: list[dict[str, Any]]) -> int:
        nonlocal nulled_total
        if not maps:
            return 0
        # example_call_id → calls is nullable / ON DELETE SET NULL: null orphan
        # refs to calls CI filtered out (e.g. TEST_) so they don't abort the sync.
        nulled = await _null_orphan_fks(session, maps, [("example_call_id", Call.id)])
        nulled_total += sum(nulled.values())
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
    logger.info(
        "wgr_sync market_signals: upserted %d (nulled %d orphan example_call_id)",
        total, nulled_total,
    )
    return total


# ---------------------------------------------------------------------------
# Strike evidence — FK-safe upsert. WGR's sales_strike_evidence can reference a
# strike_id / call_score_id that isn't present in CI (e.g. the parent score was
# filtered out as a TEST_ call, or the strike fell outside a watermark window).
# The generic native-PK upsert blindly inserts those orphan IDs and trips the
# FKs, aborting the whole sync transaction. Here we resolve references against
# what's actually in CI first:
#   * call_score_id (nullable, ON DELETE SET NULL) → NULL the orphan, matching
#     the schema's intent that a missing score is tolerated.
#   * strike_id (NOT NULL, ON DELETE CASCADE) → no parent means the row cannot
#     exist; SKIP it (and log) rather than fabricate a dangling child.
# ---------------------------------------------------------------------------

async def sync_strike_evidence(session: AsyncSession, *, since: Optional[str] = None) -> int:
    total = 0
    skipped_no_strike = 0
    nulled_score = 0
    batch: list[dict[str, Any]] = []

    async def flush(maps: list[dict[str, Any]]) -> int:
        nonlocal skipped_no_strike, nulled_score
        if not maps:
            return 0
        # strike_id → sales_coaching_strikes is NOT NULL: a missing parent means
        # the row can't exist, so skip it (can't null a required FK).
        strike_ids = {m["strike_id"] for m in maps if m.get("strike_id")}
        present_strikes = set((await session.execute(
            select(CoachingStrike.strike_id).where(CoachingStrike.strike_id.in_(strike_ids))
        )).scalars()) if strike_ids else set()
        clean: list[dict[str, Any]] = []
        for m in maps:
            if not m.get("strike_id") or m["strike_id"] not in present_strikes:
                skipped_no_strike += 1
                continue
            clean.append(m)
        if not clean:
            return 0
        # call_score_id → sales_call_scores is nullable / SET NULL: null orphans.
        nulled = await _null_orphan_fks(session, clean, [("call_score_id", CallScore.score_id)])
        nulled_score += sum(nulled.values())
        written = await _on_conflict_upsert(session, StrikeEvidence, "evidence_id", clean)
        await session.commit()
        return written

    for raw in reader.read_table("sales_strike_evidence", since=since):
        mapped = mapping.map_strike_evidence(raw)
        if mapped is None:
            continue
        batch.append(mapped)
        if len(batch) >= BATCH:
            total += await flush(batch)
            batch = []
    total += await flush(batch)
    logger.info(
        "wgr_sync sales_strike_evidence: upserted %d (skipped %d w/o strike, nulled %d orphan scores)",
        total, skipped_no_strike, nulled_score,
    )
    return total


async def sync_insight_tags(session: AsyncSession, *, since: Optional[str] = None) -> int:
    """Sync insight_tags after insights + tag_dictionary. Nulls orphan insight_ids.

    insight_id → insights.id is nullable: ~51 WGR tags point at insights CI didn't
    sync, so we keep the tag and null the dangling link (orphan-tolerant), same as
    strike evidence. tag → tag_dictionary.tag is satisfied by _seed_tag_dictionary."""
    total = 0
    nulled = 0
    batch: list[dict[str, Any]] = []

    async def flush(maps: list[dict[str, Any]]) -> int:
        nonlocal nulled
        if not maps:
            return 0
        n = await _null_orphan_fks(session, maps, [("insight_id", Insight.id)])
        nulled += sum(n.values())
        written = await _on_conflict_upsert(session, InsightTag, "id", maps)
        await session.commit()
        return written

    for raw in reader.read_table("insight_tags", since=since):
        mapped = mapping.map_insight_tag(raw)
        if mapped is None:
            continue
        batch.append(mapped)
        if len(batch) >= BATCH:
            total += await flush(batch)
            batch = []
    total += await flush(batch)
    logger.info("wgr_sync insight_tags: upserted %d (nulled %d orphan insight_ids)", total, nulled)
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
    # calls handled by sync_calls (resolves lead_id FK) — must run before insights.
    ("insights", Insight, "id", mapping.map_insight),
    ("content_ideas", ContentIdea, "id", mapping.map_content_idea),
    ("sales_strike_rules", StrikeRule, "rule_id", mapping.map_strike_rule),
    ("sales_call_scores", CallScore, "score_id", mapping.map_call_score),
    ("sales_coaching_strikes", CoachingStrike, "strike_id", mapping.map_coaching_strike),
    ("sales_strike_actions", StrikeAction, "action_id", mapping.map_strike_action),
    # sales_strike_evidence handled by sync_strike_evidence (FK-orphan resolution).
    ("sales_eod_reports", EodReport, "report_id", mapping.map_eod_report),
    ("sales", ClosedSale, "sale_id", mapping.map_closed_sale),
    ("sales_activities", SalesActivity, "activity_id", mapping.map_sales_activity),
    ("webinar_engagements", WebinarEngagement, "engagement_id", mapping.map_webinar_engagement),
    ("lead_opt_in_events", OptInEvent, "opt_in_event_id", mapping.map_opt_in_event),
    # insight_tags handled by sync_insight_tags (FK-orphan resolution like evidence).
]

# (source, external_id)-deduped marketing/social mirrors — UUID PK assigned by CI.
_SOURCE_EXTERNAL_PLAN: list[tuple] = [
    ("email_campaigns", EmailCampaign, mapping.map_email_campaign),
    ("comment_events", SocialComment, mapping.map_social_comment),
    ("instagram_posts", InstagramPost, mapping.map_instagram_post),
]


async def _sync_source_external(
    session: AsyncSession, *, wgr_table: str, model,
    map_fn: Callable[[dict], Optional[dict]], since: Optional[str],
) -> int:
    """Sync a WGR table into a CI table deduped on (source='wgr', external_id).

    Same shape as ``sync_leads``: select existing rows by external_id, bulk-insert
    the new ones with a generated UUID, update the (rare) already-present ones."""
    total = 0
    batch: list[dict[str, Any]] = []

    async def flush(maps: list[dict[str, Any]]) -> int:
        if not maps:
            return 0
        maps = list({m["external_id"]: m for m in maps}.values())  # last wins
        ext_ids = [m["external_id"] for m in maps]
        existing = (await session.execute(
            select(model.id, model.external_id).where(
                model.source == mapping.WGR_SOURCE, model.external_id.in_(ext_ids),
            )
        )).all()
        by_ext = {ext: rid for rid, ext in existing}
        new_rows = [
            {"id": uuid.uuid4(), **m} for m in maps if m["external_id"] not in by_ext
        ]
        if new_rows:
            await session.execute(insert(model), new_rows)
        for m in maps:
            if m["external_id"] in by_ext:
                await session.execute(
                    update(model).where(model.id == by_ext[m["external_id"]]).values(**m)
                )
        await session.commit()
        return len(maps)

    for raw in reader.read_table(wgr_table, since=since):
        mapped = map_fn(raw)
        if mapped is None:
            continue
        batch.append(mapped)
        if len(batch) >= BATCH:
            total += await flush(batch)
            batch = []
    total += await flush(batch)
    logger.info("wgr_sync %s → %s: upserted %d", wgr_table, model.__tablename__, total)
    return total


async def _seed_tag_dictionary(session: AsyncSession) -> int:
    """Seed CI tag_dictionary from WGR's tags (insight_tags + any dict rows).

    WGR's tag_dictionary is empty but insight_tags references hundreds of tags;
    CI enforces the FK WGR doesn't. ON CONFLICT (tag) DO NOTHING keeps it
    idempotent. Async mirror of bulk_load._load_tag_dictionary."""
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    tags: dict[str, dict] = {}
    for r in reader.wgr_client.query(
        "SELECT tag, tag_type, synonyms, notes FROM tag_dictionary WHERE tag IS NOT NULL"
    ):
        t = (r.get("tag") or "").strip()
        if t:
            tags[t] = {"tag": t, "tag_type": r.get("tag_type"),
                       "synonyms": r.get("synonyms"), "notes": r.get("notes")}
    for r in reader.wgr_client.query(
        "SELECT DISTINCT tag FROM insight_tags WHERE tag IS NOT NULL"
    ):
        t = (r.get("tag") or "").strip()
        if t and t not in tags:
            tags[t] = {"tag": t, "tag_type": None, "synonyms": None, "notes": None}
    if not tags:
        return 0
    stmt = pg_insert(TagDictionary.__table__).values(list(tags.values()))
    stmt = stmt.on_conflict_do_nothing(index_elements=["tag"])
    await session.execute(stmt)
    await session.commit()
    return len(tags)


async def sync_all(session: AsyncSession, *, since: Optional[str] = None) -> dict[str, int]:
    """Full WGR → CI sync in dependency order. Idempotent. Returns counts."""
    counts: dict[str, int] = {}

    # 1. leads first (appointments + sales reference CI lead UUIDs).
    counts["leads"] = await sync_leads(session, since=since)
    # 1b. seed tag_dictionary so insight_tags' FK (tag → tag_dictionary.tag),
    #     which WGR doesn't enforce, is satisfied before the native loop.
    counts["tag_dictionary"] = await _seed_tag_dictionary(session)
    # 1c. calls — resolves the lead_id FK (needs leads from step 1) and must run
    #     before insights (whose FK targets calls). Pulled out of _NATIVE_PLAN.
    counts["calls"] = await sync_calls(session, since=since)
    # 2. native-PK tables (business_profile/offers/reps/insights/... in the list
    #    so their children's FKs resolve).
    for wgr_table, model, pk_col, map_fn in _NATIVE_PLAN:
        counts[wgr_table] = await _sync_native_pk(
            session, wgr_table=wgr_table, model=model, pk_col=pk_col,
            map_fn=map_fn, since=since,
        )
    # 3. strike evidence (needs strikes + scores from the loop above) — resolves
    #    orphan FKs against what's actually in CI before inserting.
    counts["sales_strike_evidence"] = await sync_strike_evidence(session, since=since)
    # 3b. insight_tags (needs insights from the native loop) — nulls orphan FKs.
    counts["insight_tags"] = await sync_insight_tags(session, since=since)
    # 4. appointments (needs leads) + market_signals.
    counts["appointments"] = await sync_appointments(session, since=since)
    counts["market_signals"] = await sync_market_signals(session)
    # 5. (source, external_id)-deduped marketing/social mirrors.
    for wgr_table, model, map_fn in _SOURCE_EXTERNAL_PLAN:
        counts[wgr_table] = await _sync_source_external(
            session, wgr_table=wgr_table, model=model, map_fn=map_fn, since=since,
        )
    return counts
