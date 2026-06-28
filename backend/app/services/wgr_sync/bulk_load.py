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
    # calls handled by _load_calls (resolves lead_id FK) — runs before insights.
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
# insight_tags is loaded separately (after seeding tag_dictionary to satisfy the
# FK insight_tags.tag → tag_dictionary.tag, which WGR doesn't enforce).

# CI tables deduped on a unique (source, external_id) — UUID PK assigned at
# insert. Mirrored read-only from WGR; written only by the sync. The 4th element
# is True when the unique index is PARTIAL (email_campaigns, pre-existing schema).
_SOURCE_EXTERNAL_PLAN: list[tuple[str, str, Callable, bool]] = [
    ("email_campaigns", "email_campaigns", mapping.map_email_campaign, True),
    ("comment_events", "social_comments", mapping.map_social_comment, False),
    ("instagram_posts", "instagram_posts", mapping.map_instagram_post, False),
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
        # 1b. calls — resolves lead_id FK (needs leads) and must run before
        #     insights (whose FK targets calls). Pulled out of _PLAN.
        counts["calls"] = _load_calls(conn, since)
        # 2. native-PK family.
        for wgr_table, ci_table, map_fn, pk in _PLAN:
            counts[ci_table] = _load_native(conn, wgr_table, ci_table, map_fn, pk, since)
        # 2b. tag_dictionary (FK parent) then insight_tags (orphan-tolerant).
        counts["tag_dictionary"] = _load_tag_dictionary(conn)
        counts["insight_tags"] = _load_insight_tags(conn, since)
        # 2c. (source, external_id)-deduped marketing/social mirrors.
        for wgr_table, ci_table, map_fn, partial in _SOURCE_EXTERNAL_PLAN:
            counts[ci_table] = _load_source_external(
                conn, wgr_table, ci_table, map_fn, since, partial=partial)
        # 3. appointments (needs leads), market_signals.
        counts["appointments"] = _load_appointments(conn, since)
        counts["market_signals"] = _load_market_signals(conn)
        # 4. enrich CI calls with WGR transcripts + analysis prose (for RAG).
        counts["calls_enriched"] = _enrich_calls(conn)
    finally:
        conn.close()
    return counts


def _enrich_calls(conn) -> int:
    """Backfill CI ``calls.transcript_text`` + ``calls.summary`` from WGR's
    ``sales_call_transcripts`` and ``sales_call_analyses`` (joined on call_id ==
    CI call id). These WGR tables aren't imported as CI tables — their rich text
    lands directly on the matching call so it's embeddable in-DB (Phase 5 RAG).
    Idempotent: re-running just overwrites with the same text."""
    transcripts = {
        r["call_id"]: (r.get("transcript_labeled") or r.get("transcript_raw"))
        for r in reader.wgr_client.query(
            "SELECT call_id, transcript_labeled, transcript_raw FROM sales_call_transcripts"
        )
        if r.get("call_id")
    }
    analyses = {}
    for r in reader.wgr_client.query(
        "SELECT call_id, call_summary, performance_notes FROM sales_call_analyses"
    ):
        cid = r.get("call_id")
        if not cid:
            continue
        parts = [p for p in (r.get("call_summary"), r.get("performance_notes")) if p]
        if parts:
            analyses[cid] = "\n\n".join(parts)

    call_ids = set(transcripts) | set(analyses)
    n = 0
    with conn.cursor() as cur:
        for cid in call_ids:
            cur.execute(
                'UPDATE calls SET transcript_text = COALESCE(%s, transcript_text), '
                'summary = COALESCE(%s, summary) WHERE id = %s',
                (transcripts.get(cid), analyses.get(cid), cid),
            )
            n += cur.rowcount or 0
    conn.commit()
    logger.info("bulk_load enrich calls: updated %d", n)
    return n


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


def _load_source_external(conn, wgr_table, ci_table, map_fn, since, partial=False) -> int:
    """Loader for CI tables deduped on a unique (source, external_id).

    Mirrors WGR-sourced marketing/social tables (email_campaigns, social_comments,
    instagram_posts) whose CI PK is a generated UUID — we assign the UUID on
    insert and let ON CONFLICT update the existing row on re-run. ``partial=True``
    for tables whose unique index is PARTIAL (email_campaigns, like leads): the
    ON CONFLICT must repeat the index's WHERE predicate to match it."""
    first: dict | None = None
    for raw in reader.read_table(wgr_table, since=since):
        m = map_fn(raw)
        if m is not None:
            first = m
            break
    if first is None:
        logger.info("bulk_load %s: no rows", wgr_table)
        return 0

    def inject(m: dict) -> None:
        m["id"] = str(uuid.uuid4())

    cols = list(first.keys())  # source/external_id + mapped fields (no id yet)
    where = (" WHERE source IS NOT NULL AND external_id IS NOT NULL" if partial else "")
    conflict = (f"ON CONFLICT (source, external_id){where} DO UPDATE SET "
                + _excl(cols, ("source", "external_id")))
    return _load_table(conn, wgr_table=wgr_table, ci_table=ci_table,
                       map_fn=map_fn, conflict_sql=conflict,
                       since=since, inject=inject)


def _load_tag_dictionary(conn) -> int:
    """Seed CI ``tag_dictionary`` from WGR's tags before loading insight_tags.

    CI enforces an FK ``insight_tags.tag → tag_dictionary.tag`` that WGR does
    not — WGR's ``tag_dictionary`` is empty while ``insight_tags`` references
    hundreds of tags. We derive the dictionary from the distinct tags actually
    used (union'd with any rows WGR does have), so the FK is satisfied. Idempotent
    via ON CONFLICT (tag) DO NOTHING."""
    # Prefer WGR's own dictionary rows (carry tag_type/synonyms/notes); fall back
    # to bare distinct tags from insight_tags for the rest.
    rows: dict[str, dict] = {}
    for r in reader.wgr_client.query(
        "SELECT tag, tag_type, synonyms, notes FROM tag_dictionary WHERE tag IS NOT NULL"
    ):
        t = (r.get("tag") or "").strip()
        if t:
            rows[t] = {"tag": t, "tag_type": r.get("tag_type"),
                       "synonyms": r.get("synonyms"), "notes": r.get("notes")}
    for r in reader.wgr_client.query(
        "SELECT DISTINCT tag FROM insight_tags WHERE tag IS NOT NULL"
    ):
        t = (r.get("tag") or "").strip()
        if t and t not in rows:
            rows[t] = {"tag": t, "tag_type": None, "synonyms": None, "notes": None}
    if not rows:
        return 0
    values = [(d["tag"], d["tag_type"], d["synonyms"], d["notes"]) for d in rows.values()]
    with conn.cursor() as cur:
        execute_values(
            cur,
            "INSERT INTO tag_dictionary (tag, tag_type, synonyms, notes) VALUES %s "
            "ON CONFLICT (tag) DO NOTHING",
            values,
            page_size=PAGE,
        )
    conn.commit()
    logger.info("bulk_load tag_dictionary: seeded %d tags", len(values))
    return len(values)


def _load_insight_tags(conn, since) -> int:
    """Load insight_tags after seeding tag_dictionary; null orphaned insight_ids.

    51-ish WGR tags reference insights CI didn't sync (filtered / out of window).
    insight_id is nullable in CI, so we keep the tag and null the dangling link
    rather than dropping the row — same orphan-tolerant policy as sales evidence."""
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM insights")
        ci_insight_ids = {r[0] for r in cur.fetchall()}

    def inject(m: dict) -> None:
        if m.get("insight_id") and m["insight_id"] not in ci_insight_ids:
            m["insight_id"] = None

    return _load_native_with_inject(
        conn, "insight_tags", "insight_tags", mapping.map_insight_tag, ("id",),
        since, inject,
    )


def _load_native_with_inject(conn, wgr_table, ci_table, map_fn, pk, since, inject) -> int:
    """_load_native variant that runs an inject() on each mapped row."""
    first: dict | None = None
    for raw in reader.read_table(wgr_table, since=since):
        m = map_fn(raw)
        if m is not None:
            first = m
            break
    if first is None:
        logger.info("bulk_load %s: no rows", wgr_table)
        return 0
    conflict = _conflict_clause_for(ci_table, _remap(dict(first)), pk)
    return _load_table(conn, wgr_table=wgr_table, ci_table=ci_table, map_fn=map_fn,
                       conflict_sql=conflict, since=since, inject=inject)


def _load_calls(conn, since) -> int:
    """Calls loader: native ON-CONFLICT upsert (CI id = WGR call_id) PLUS lead_id
    FK resolution (WGR 'LEAD_xxx' → CI lead UUID), so the lead → calls → insights
    → insight_tags chain that powers per-lead tags isn't broken. Mirrors the
    async ``upsert.sync_calls`` so the two sync paths stay in agreement.
    """
    with conn.cursor() as cur:
        cur.execute("SELECT external_id, id FROM leads WHERE source='wgr'")
        lead_map = {ext: lid for ext, lid in cur.fetchall()}

    # Peek one mapped row (with lead_id injected) to build the conflict clause.
    first: dict | None = None
    for raw in reader.read_table("calls", since=since):
        m = mapping.map_call(raw)
        if m is not None:
            first = dict(m)
            first["lead_id"] = lead_map.get(first.pop("_wgr_lead_id", None))
            break
    if first is None:
        logger.info("bulk_load calls: no rows")
        return 0

    def inject(m: dict) -> None:
        m["lead_id"] = lead_map.get(m.pop("_wgr_lead_id", None))

    conflict = _conflict_clause_for("calls", _remap(first), ("id",))
    return _load_table(conn, wgr_table="calls", ci_table="calls",
                       map_fn=mapping.map_call, conflict_sql=conflict,
                       since=since, inject=inject)


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


def _null_orphan_example_call_id(m: dict, ci_call_ids: set) -> None:
    """Null a market_signal's example_call_id if it references a call not in CI.

    Pure decision logic, extracted so it's unit-testable without a live DB.
    WGR signals can reference a call CI filtered out (TEST_) or hasn't synced;
    the FK to calls (ON DELETE SET NULL) would otherwise abort the insert batch.
    """
    if m.get("example_call_id") and m["example_call_id"] not in ci_call_ids:
        m["example_call_id"] = None


def _load_market_signals(conn) -> int:
    first = None
    for raw in reader.read_table("market_signals"):
        m = mapping.map_market_signal(raw)
        if m is not None:
            first = m
            break
    if first is None:
        return 0

    # example_call_id → calls is a real FK (ON DELETE SET NULL). WGR signals can
    # reference a call CI filtered out (TEST_) or hasn't synced; left as-is the FK
    # violation aborts the whole batch and silently drops those rows. Null the
    # orphan ref before insert — same orphan-tolerant policy as the async path
    # (upsert.sync_market_signals via _null_orphan_fks) and _load_insight_tags.
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM calls")
        ci_call_ids = {r[0] for r in cur.fetchall()}

    def inject(m: dict) -> None:
        _null_orphan_example_call_id(m, ci_call_ids)

    conflict = ("ON CONFLICT (signal_family, signal) DO UPDATE SET "
                + _excl(list(first.keys()), ("signal_family", "signal")))
    return _load_table(conn, wgr_table="market_signals", ci_table="market_signals",
                       map_fn=mapping.map_market_signal, conflict_sql=conflict,
                       inject=inject)
