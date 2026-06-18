"""Fast synchronous bulk loader for the WGR → CI backfill.

Why sync (psycopg2) instead of the async upsert path: CI's Supabase is reachable
only through the transaction pooler, and sustained multi-batch async (asyncpg)
writes hang in `idle in transaction` / ClientRead. A single persistent psycopg2
connection with ``execute_values`` (the same driver pg_dump/psql use) loads the
~55k rows reliably and fast.

This module is used by ``scripts/backfill_wgr.py`` for the one-shot backfill.
The async ``upsert.py`` path stays for the hourly incremental Celery task, where
batches are small and the hang doesn't manifest.

All inserts are idempotent via ``ON CONFLICT ... DO UPDATE``:
  * native-PK tables conflict on their PK
  * leads/appointments conflict on the partial unique index (source, external_id)
  * market_signals conflicts on (signal_family, signal)
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Callable, Optional

import psycopg2
from psycopg2.extras import Json, execute_values

from app.config import settings
from app.services.wgr_sync import mapping, reader

logger = logging.getLogger(__name__)

PAGE = 1000

# Mapping functions emit SQLAlchemy attribute names; a few differ from the DB
# column. The bulk loader writes raw column names, so remap those keys here.
_ATTR_TO_COLUMN = {"activity_metadata": "metadata"}


def _remap(m: dict) -> dict:
    """Rename mapped SQLAlchemy-attr keys to their DB column names (in place)."""
    for attr, col in _ATTR_TO_COLUMN.items():
        if attr in m:
            m[col] = m.pop(attr)
    return m


def _sync_url() -> str:
    return settings.database_url.replace("+asyncpg", "")


def _load_table(
    conn, *, wgr_table: str, ci_table: str, map_fn: Callable[[dict], Optional[dict]],
    conflict_sql: str, since: Optional[str] = None,
    inject: Optional[Callable[[dict], None]] = None,
    skip_fn: Optional[Callable[[dict], bool]] = None,
) -> int:
    """Stream a WGR table → CI via execute_values batches. Returns rows written.

    ``conflict_sql`` is the full ``ON CONFLICT (...) DO UPDATE SET ...`` clause
    (or ``ON CONFLICT DO NOTHING``). ``inject`` optionally mutates each mapped
    dict before insert. ``skip_fn`` returns True to drop a mapped row (e.g.
    cross-batch dedup) after inject ran."""
    total = 0
    batch: list[dict] = []
    cols: list[str] | None = None

    def flush(rows: list[dict]) -> int:
        nonlocal cols
        if not rows:
            return 0
        if cols is None:
            cols = list(rows[0].keys())
        collist = ", ".join(f'"{c}"' for c in cols)
        # Wrap dicts as JSONB (psycopg2 can't adapt a raw dict). Lists are left
        # as-is — psycopg2 adapts Python lists to Postgres ARRAY columns natively
        # (capabilities / applies_to_roles).
        tuples = [
            tuple(
                Json(v) if isinstance(v, dict) else v
                for v in (r.get(c) for c in cols)
            )
            for r in rows
        ]
        with conn.cursor() as cur:
            execute_values(
                cur,
                f'INSERT INTO public."{ci_table}" ({collist}) VALUES %s {conflict_sql}',
                tuples,
                page_size=PAGE,
            )
        conn.commit()
        return len(rows)

    for raw in reader.read_table(wgr_table, since=since):
        mapped = map_fn(raw)
        if mapped is None:
            continue
        if inject:
            inject(mapped)
        if skip_fn and skip_fn(mapped):
            continue
        _remap(mapped)
        batch.append(mapped)
        if len(batch) >= PAGE:
            total += flush(batch)
            batch = []
    total += flush(batch)
    logger.info("bulk_load %s → %s: %d", wgr_table, ci_table, total)
    return total


def _excl(cols: list[str], pk: tuple[str, ...]) -> str:
    """Build 'col = EXCLUDED.col' for every col not in the conflict target / created_at."""
    updatable = [c for c in cols if c not in pk and c != "created_at"]
    return ", ".join(f'"{c}" = EXCLUDED."{c}"' for c in updatable)


# Per-table plan: (wgr_table, ci_table, map_fn, pk_cols_for_conflict).
# For native-PK tables the conflict target is the PK; SET clause is computed from
# the first batch's columns at run time via a DO UPDATE built per table below.
_PLAN: list[tuple[str, str, Callable, tuple[str, ...]]] = [
    ("business_profile", "business_profile", mapping.map_business_profile, ("id",)),
    ("offers", "offers", mapping.map_offer, ("offer_id",)),
    ("sales_reps", "sales_reps", mapping.map_sales_rep, ("rep_id",)),
    ("sales_scorecard_categories", "sales_scorecard_categories", mapping.map_scorecard_category, ("category_id",)),
    ("calls", "calls", mapping.map_call, ("id",)),
    ("insights", "insights", mapping.map_insight, ("id",)),
    ("content_ideas", "content_ideas", mapping.map_content_idea, ("id",)),
    ("sales_strike_rules", "sales_strike_rules", mapping.map_strike_rule, ("rule_id",)),
    ("sales_call_scores", "sales_call_scores", mapping.map_call_score, ("score_id",)),
    ("sales_coaching_strikes", "sales_coaching_strikes", mapping.map_coaching_strike, ("strike_id",)),
    ("sales_strike_actions", "sales_strike_actions", mapping.map_strike_action, ("action_id",)),
    ("sales_strike_evidence", "sales_strike_evidence", mapping.map_strike_evidence, ("evidence_id",)),
    ("sales_eod_reports", "sales_eod_reports", mapping.map_eod_report, ("report_id",)),
    ("sales", "closed_sales", mapping.map_closed_sale, ("sale_id",)),
    ("sales_activities", "sales_activities", mapping.map_sales_activity, ("activity_id",)),
    ("webinar_engagements", "webinar_engagements", mapping.map_webinar_engagement, ("engagement_id",)),
    ("lead_opt_in_events", "opt_in_events", mapping.map_opt_in_event, ("opt_in_event_id",)),
]


def _conflict_clause_for(table: str, sample: dict, pk: tuple[str, ...]) -> str:
    cols = list(sample.keys())
    target = ", ".join(f'"{c}"' for c in pk)
    setclause = _excl(cols, pk)
    return f"ON CONFLICT ({target}) DO UPDATE SET {setclause}" if setclause else f"ON CONFLICT ({target}) DO NOTHING"


def run_backfill(since: Optional[str] = None) -> dict[str, int]:
    """Full idempotent backfill via sync psycopg2. Returns per-table counts."""
    counts: dict[str, int] = {}
    conn = psycopg2.connect(_sync_url(), connect_timeout=20)
    conn.autocommit = False
    try:
        # 1. leads first — conflict on the partial unique index (source, external_id).
        counts["leads"] = _load_leads(conn, since)
        # 2. native-PK family.
        for wgr_table, ci_table, map_fn, pk in _PLAN:
            counts[ci_table] = _load_native(conn, wgr_table, ci_table, map_fn, pk, since)
        # 3. appointments (needs leads), market_signals.
        counts["appointments"] = _load_appointments(conn, since)
        counts["market_signals"] = _load_market_signals(conn)
    finally:
        conn.close()
    return counts


def _load_native(conn, wgr_table, ci_table, map_fn, pk, since) -> int:
    """Native-PK table loader: builds the ON CONFLICT clause from the first row."""
    first: dict | None = None
    # Peek at one mapped row to construct the conflict clause.
    for raw in reader.read_table(wgr_table, since=since):
        m = map_fn(raw)
        if m is not None:
            first = m
            break
    if first is None:
        logger.info("bulk_load %s: no rows", wgr_table)
        return 0
    conflict = _conflict_clause_for(ci_table, _remap(first), pk)
    return _load_table(conn, wgr_table=wgr_table, ci_table=ci_table, map_fn=map_fn,
                       conflict_sql=conflict, since=since)


def _load_leads(conn, since) -> int:
    # CI enforces a UNIQUE index on leads.email, but WGR's leads.email is not
    # unique (a handful of people opted in twice). Collapse to one CI lead per
    # email across the whole load (first WGR lead_id wins as external_id); rows
    # with no email are unaffected. Done up front so batches never collide.
    seen_emails: set[str] = set()

    def skip(m: dict) -> bool:
        e = (m.get("email") or "").lower()
        if not e:
            return False
        if e in seen_emails:
            return True  # already loaded this email; drop the duplicate WGR lead
        seen_emails.add(e)
        return False

    def inject(m: dict) -> None:
        m["id"] = str(uuid.uuid4())
    # conflict on the partial unique index columns (source, external_id)
    sample = {"id": "x", "source": "wgr", "external_id": "x", "name": None,
              "email": None, "phone": None, "status": None, "notes": None}
    # The unique index uq_leads_source_external_id is PARTIAL, so ON CONFLICT must
    # repeat its WHERE predicate to match it.
    conflict = ("ON CONFLICT (source, external_id) "
                "WHERE source IS NOT NULL AND external_id IS NOT NULL "
                "DO UPDATE SET "
                + _excl([c for c in sample if c != "id"], ("source", "external_id")))
    return _load_table(conn, wgr_table="leads", ci_table="leads",
                       map_fn=mapping.map_lead, conflict_sql=conflict,
                       since=since, inject=inject, skip_fn=skip)


def _load_appointments(conn, since) -> int:
    # appointments has NO unique index on (source, external_id) — only the PK and
    # a non-unique external_id index — so ON CONFLICT can't dedup here. Instead
    # delete-then-insert the WGR-sourced rows: idempotent at the table level and
    # safe because CI's own GHL appointment ingestion is disabled (Phase 2), so
    # 'wgr' is the only source writing this table.
    with conn.cursor() as cur:
        cur.execute("SELECT external_id, id FROM leads WHERE source='wgr'")
        lead_map = {ext: lid for ext, lid in cur.fetchall()}
        cur.execute("DELETE FROM appointments WHERE source='wgr'")
    conn.commit()

    def inject(m: dict) -> None:
        m["id"] = str(uuid.uuid4())
        m["lead_id"] = lead_map.get(m.pop("_wgr_lead_id", None))

    return _load_table(conn, wgr_table="appointments", ci_table="appointments",
                       map_fn=mapping.map_appointment, conflict_sql="",
                       since=since, inject=inject)


def _load_market_signals(conn) -> int:
    first = None
    for raw in reader.read_table("market_signals"):
        m = mapping.map_market_signal(raw)
        if m is not None:
            first = m
            break
    if first is None:
        return 0
    conflict = ("ON CONFLICT (signal_family, signal) DO UPDATE SET "
                + _excl(list(first.keys()), ("signal_family", "signal")))
    return _load_table(conn, wgr_table="market_signals", ci_table="market_signals",
                       map_fn=mapping.map_market_signal, conflict_sql=conflict)
