"""Shared sales-pipeline aggregation helpers.

Single source of truth for the lead KPI / volume / source / funnel
aggregation. Both the ``GET /api/v1/leads/stats`` route and the Sales
department surfaces (``GET /api/v1/sales/summary`` and the Sales Director
agent's ``get_sales_summary`` tool) consume ``compute_lead_stats`` so the
funnel definition can never drift between them.

The SQL below is lifted verbatim from the original inline implementation in
``app.routes.leads.get_leads_stats`` — keep it byte-identical to preserve the
verified funnel semantics.

Status vocabulary (DB values, lowercased):
  new / contacted / qualified / appointment-set / sale / lost / stale
"""

from __future__ import annotations

import logging
from datetime import date

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.attribution import bucket_channel_combos, build_resolver, summarize_channels

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Private numeric coercion + labelling helpers (copied from routes/leads.py)
# ---------------------------------------------------------------------------


def _int(value: object) -> int:
    """Return value as int, falling back to 0 for None or non-numeric values."""
    try:
        return int(value) if value is not None else 0
    except (TypeError, ValueError):
        return 0


def _channel_buckets_to_breakdown(buckets: list[dict]) -> list[dict]:
    """Turn ``summarize_channels`` buckets into the breakdown dicts
    ``compute_lead_stats`` returns, adding the 1-dp ``percentage`` (of the
    bucket total — always the same total as ``kpis.total_leads`` since the
    combos are grouped from the same range-scoped query) and the
    transitional ``source`` key (see ``SourceBreakdownItem`` docstring).

    Pure function — no DB — so it is unit-testable with fake bucket lists.

    The returned list is sorted by ``count`` descending (largest bucket
    first), tie-broken by ``channel`` name ascending, so the order is fully
    deterministic. ``summarize_channels`` builds its buckets via a dict/
    hash-agg with no guaranteed iteration order — without this sort the
    donut/legend order (and the ``/leads/stats`` + ``/sales/summary``
    response order) could shuffle between otherwise-identical requests.
    """
    total = sum(_int(b["count"]) for b in buckets)
    breakdown: list[dict] = []
    for b in buckets:
        cnt = _int(b["count"])
        pct = round((cnt / total * 100), 1) if total > 0 else 0.0
        breakdown.append(
            {
                # Transitional: `source` mirrors `channel` so the current
                # frontend donut (reads `.source`) keeps rendering until
                # Task 4 switches it to `.channel`; drop `source` after that.
                "source": b["channel"],
                "channel": b["channel"],
                "platform": b.get("platform"),
                "reportable": b.get("reportable", True),
                "count": cnt,
                "percentage": pct,
            }
        )
    breakdown.sort(key=lambda item: (-item["count"], item["channel"]))
    return breakdown


# ---------------------------------------------------------------------------
# Revenue-by-channel aggregation (deliverable 9b — sales half of Source
# Attribution; the leads half already lives in _channel_buckets_to_breakdown)
# ---------------------------------------------------------------------------


def _float(value: object) -> float:
    """Return value as float, falling back to 0.0 for None or non-numeric values."""
    try:
        return float(value) if value is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def _revenue_buckets_to_breakdown(buckets: list[dict]) -> list[dict]:
    """Turn revenue-scoped channel buckets into the response dicts
    ``compute_revenue_by_channel`` returns.

    Mirrors ``_channel_buckets_to_breakdown``'s shape/ordering contract but
    aggregates ``revenue`` (sum of ``amount_collected``) and ``sales_count``
    instead of a plain lead count — the two surfaces intentionally diverge
    here since a "count" of leads and a "count" of sales are different axes.

    Pure function — no DB — so it is unit-testable with fake bucket lists.
    Input buckets: list of dicts with channel/platform/reportable/revenue/
    sales_count. Percentages are 1-dp shares of total revenue (not sales
    count) since this is a revenue breakdown. Sorted revenue desc, tie-broken
    by channel name ascending, for the same shuffle-avoidance reason
    documented on ``_channel_buckets_to_breakdown``.
    """
    total_revenue = sum(_float(b.get("revenue")) for b in buckets)
    breakdown: list[dict] = []
    for b in buckets:
        revenue = round(_float(b.get("revenue")), 2)
        pct = round((revenue / total_revenue * 100), 1) if total_revenue > 0 else 0.0
        breakdown.append(
            {
                "channel": b["channel"],
                "platform": b.get("platform"),
                "reportable": b.get("reportable", True),
                "sales_count": _int(b.get("sales_count")),
                "revenue": revenue,
                "revenue_percentage": pct,
            }
        )
    breakdown.sort(key=lambda item: (-item["revenue"], item["channel"]))
    return breakdown


async def compute_revenue_by_channel(
    session: AsyncSession,
    *,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[dict]:
    """Aggregate closed-sales revenue into the same channel buckets the lead
    source_breakdown uses, scoped by ``closed_sales.close_date`` (NOT
    ``leads.entry_date`` — a different axis: when the deal closed, not when
    the lead entered the funnel).

    ``closed_sales`` (not ``lead_journey``, which mirrors a disagreeing
    total) is the revenue source of truth — same table the existing avg
    deal value KPI reads. Joins to ``leads`` via ``external_id`` first (the
    join that covers all 83 closed sales today), falling back to
    ``ghl_contact_id`` for email-merged leads (same join contract as
    lead_engagements/lead_journey — see their docstrings). A closed sale
    whose lead row can't be found at all (neither join hits) still counts
    toward revenue — it just carries all-null UTMs, which
    ``bucket_channel_combos`` buckets as "No attribution".

    Returns a list of dicts (mirrors ``source_breakdown``'s plain-dict
    contract so both the /sales/summary and /leads/stats routes can consume
    it directly):

        [{"channel": str, "platform": str | None, "reportable": bool,
          "sales_count": int, "revenue": float, "revenue_percentage": float}, ...]

    Sorted revenue desc, channel name asc as tiebreak (see
    ``_revenue_buckets_to_breakdown``).
    """
    range_sql = ""
    params: dict[str, object] = {}

    def _as_date(v: str | None) -> date | None:
        if not v:
            return None
        try:
            return date.fromisoformat(v)
        except ValueError:
            return None

    d_from, d_to = _as_date(date_from), _as_date(date_to)
    if d_from is not None:
        range_sql += " AND cs.close_date >= :date_from"
        params["date_from"] = d_from
    if d_to is not None:
        range_sql += " AND cs.close_date <= :date_to"
        params["date_to"] = d_to

    # Two LEFT JOINs (external_id preferred, ghl_contact_id fallback) +
    # COALESCE so every closed sale is represented exactly once even if
    # only the fallback join hits, and still represented (with all-null
    # UTMs) if neither join hits. Soft-deleted leads are excluded from
    # both join targets so a deleted lead's row can't smuggle in real UTMs
    # — it degrades to the same all-null "No attribution" treatment as a
    # missing lead, which is the intended behavior (a deleted lead is not
    # a reportable attribution source).
    row = await session.execute(
        text(
            f"""
            SELECT
                COALESCE(l_ext.utm_source_first,  l_ghl.utm_source_first)  AS utm_source_first,
                COALESCE(l_ext.utm_medium_first,  l_ghl.utm_medium_first)  AS utm_medium_first,
                COALESCE(l_ext.utm_content_first, l_ghl.utm_content_first) AS utm_content_first,
                COALESCE(l_ext.utm_source_last,   l_ghl.utm_source_last)   AS utm_source_last,
                COALESCE(l_ext.utm_medium_last,   l_ghl.utm_medium_last)   AS utm_medium_last,
                COALESCE(l_ext.utm_content_last,  l_ghl.utm_content_last)  AS utm_content_last,
                SUM(cs.amount_collected) AS revenue,
                COUNT(*) AS sales_count
            FROM closed_sales cs
            LEFT JOIN leads l_ext
                   ON l_ext.external_id = cs.lead_id
                  AND l_ext.deleted_at IS NULL
            LEFT JOIN leads l_ghl
                   ON l_ghl.ghl_contact_id = cs.ghl_contact_id
                  AND l_ghl.deleted_at IS NULL
                  AND cs.ghl_contact_id IS NOT NULL
            WHERE 1=1{range_sql}
            GROUP BY 1, 2, 3, 4, 5, 6
            """
        ),
        params,
    )
    combo_rows = row.fetchall()

    taxonomy_rows = (await session.execute(text("SELECT * FROM attribution_taxonomy"))).fetchall()
    resolver = build_resolver(taxonomy_rows)

    combos = [
        (r[0], r[1], r[2], r[3], r[4], r[5], _int(r[7])) for r in combo_rows
    ]
    mapping, _buckets = bucket_channel_combos(combos, resolver)

    # bucket_channel_combos aggregates a plain lead/row *count* per bucket —
    # for revenue we need to re-aggregate ourselves using the returned
    # combo->label mapping so we sum amount_collected (not sales_count) per
    # bucket, while still reusing the exact same bucketing rules/labels.
    revenue_buckets: dict[str, dict] = {}
    for r in combo_rows:
        key = (r[0], r[1], r[2], r[3], r[4], r[5])
        label = mapping.get(key, "No attribution")
        revenue = _float(r[6])
        sales_count = _int(r[7])
        if label in revenue_buckets:
            revenue_buckets[label]["revenue"] += revenue
            revenue_buckets[label]["sales_count"] += sales_count
        else:
            # platform/reportable for a bucket are constant across every
            # combo that maps to it (bucket_channel_combos resolves a single
            # channel/platform/reportable triple per bucket label), so it's
            # safe to look them up from the count-bucket for this label.
            src_bucket = next((b for b in _buckets if b["channel"] == label), {})
            revenue_buckets[label] = {
                "channel": label,
                "platform": src_bucket.get("platform"),
                "reportable": src_bucket.get("reportable", True),
                "revenue": revenue,
                "sales_count": sales_count,
            }

    return _revenue_buckets_to_breakdown(list(revenue_buckets.values()))


# ---------------------------------------------------------------------------
# Lead stats aggregation
# ---------------------------------------------------------------------------


async def compute_lead_stats(
    session: AsyncSession,
    *,
    date_from: str | None = None,
    date_to: str | None = None,
    window_weeks: int = 8,
) -> dict:
    """Aggregate lead data into KPIs, an 8-week volume series, source
    breakdown, and a four-stage sales funnel.

    ``date_from`` / ``date_to`` (ISO ``YYYY-MM-DD``) scope the *report* numbers
    — total, funnel, conversion, active applications, and source breakdown — to
    leads whose **entry_date** (the upstream funnel-entry date, NOT created_at /
    sync date) falls in [from, to] inclusive. Omitting them reports all-time.
    The 8-week ``lead_volume`` sparkline and ``leads_this_week`` KPI stay
    time-relative (they're rolling windows, not part of the ranged report).

    Returns a plain dict (not a Pydantic model) so both the leads route and
    the agent tooling can consume it:

        {
          "kpis": {total_leads, leads_this_week, conversion_rate, active_applications},
          "lead_volume": [{"label": str, "value": int}, ...],          # 8 points
          "source_breakdown": [
              {"source": str, "channel": str, "platform": str | None,
               "reportable": bool, "count": int, "percentage": float}, ...
          ],  # `source` mirrors `channel` transitionally (see
              # _channel_buckets_to_breakdown); sorted count-desc
          "funnel": [{"stage": str, "count": int, "percentage": float}, ...],  # 4 stages
        }
    """

    # entry_date range clause + bind params, applied to every "report" query so
    # the funnel/KPIs/source all reflect the same window. `entry_date` is ~99%
    # populated; rows with a NULL entry_date are excluded when a range is set.
    # entry_date is a DATE column; asyncpg needs an actual date object for the
    # bind param (it won't coerce an ISO string). Parse here; bad input is
    # ignored rather than erroring the whole report.
    range_sql = ""
    params: dict[str, object] = {}

    def _as_date(v: str | None) -> date | None:
        if not v:
            return None
        try:
            return date.fromisoformat(v)
        except ValueError:
            return None

    d_from, d_to = _as_date(date_from), _as_date(date_to)
    if d_from is not None:
        range_sql += " AND entry_date >= :date_from"
        params["date_from"] = d_from
    if d_to is not None:
        range_sql += " AND entry_date <= :date_to"
        params["date_to"] = d_to

    # ---- 1. Total leads (non-deleted, in range) -----------------------------
    row = await session.execute(
        text(f"SELECT COUNT(*) FROM leads WHERE deleted_at IS NULL{range_sql}"),
        params,
    )
    total_leads: int = _int(row.scalar())

    # All-time total (NOT range-scoped) — the KPI card shows this as the headline
    # number with the in-range count as its subtitle, so "Total Leads" stays
    # honest regardless of the selected range.
    row = await session.execute(
        text("SELECT COUNT(*) FROM leads WHERE deleted_at IS NULL")
    )
    all_time_total: int = _int(row.scalar())

    # ---- 2. Leads ENTERED in the last 7 days --------------------------------
    # Counts on entry_date (the lead's funnel-entry date), not created_at — the
    # latter is sync time and bunches all rows into the backfill window, which
    # overstated "this week". A fixed rolling 7-day window (not the range).
    row = await session.execute(
        text(
            "SELECT COUNT(*) FROM leads "
            "WHERE deleted_at IS NULL "
            "  AND entry_date >= (NOW() - INTERVAL '7 days')::date"
        )
    )
    leads_this_week: int = _int(row.scalar())

    # ---- 3. Conversion rate — status 'sale' in DB (in range) ----------------
    row = await session.execute(
        text(
            "SELECT COUNT(*) FROM leads "
            "WHERE deleted_at IS NULL "
            "  AND LOWER(status) = 'sale'"
            f"{range_sql}"
        ),
        params,
    )
    sold_count: int = _int(row.scalar())

    conversion_rate: float = 0.0
    if total_leads > 0:
        conversion_rate = round((sold_count / total_leads) * 100, 2)

    # ---- 4. Active applications — qualified + appointment-set (in range) ----
    row = await session.execute(
        text(
            "SELECT COUNT(*) FROM leads "
            "WHERE deleted_at IS NULL "
            "  AND LOWER(status) IN ('qualified', 'appointment-set')"
            f"{range_sql}"
        ),
        params,
    )
    active_applications: int = _int(row.scalar())

    # ---- 4b. Avg deal value — avg amount_collected on closed sales (in range) --
    # Scoped via the sale's lead entry_date so it tracks the same window as the
    # rest of the report. closed_sales.lead_id holds the raw WGR id (varchar), so
    # join on leads.external_id (same as sales_activities), NOT the CI UUID.
    row = await session.execute(
        text(
            f"""
            SELECT AVG(cs.amount_collected)
            FROM closed_sales cs
            JOIN leads l ON l.external_id = cs.lead_id
            WHERE l.deleted_at IS NULL
              AND cs.amount_collected IS NOT NULL
              {range_sql.replace('entry_date', 'l.entry_date')}
            """
        ),
        params,
    )
    avg_deal_raw = row.scalar()
    avg_deal_value: float = round(float(avg_deal_raw), 2) if avg_deal_raw is not None else 0.0

    kpis = {
        "total_leads": total_leads,  # range-scoped (in the selected window)
        "all_time_total": all_time_total,  # unscoped, for the headline KPI
        "leads_this_week": leads_this_week,
        "conversion_rate": conversion_rate,
        "active_applications": active_applications,
        "avg_deal_value": avg_deal_value,  # range-scoped, for the funnel rail
    }

    # ---- 5. Lead volume — `window_weeks` weeks ending at range end, by entry_date
    # Bucketed on entry_date (not created_at) and anchored to the selected
    # range's end (date_to), falling back to today when no end is set. This
    # keeps it a real trailing trend while following the entered-date window.
    # `window_weeks` (default 8) is clamped at the tool layer; clamp again here
    # so a direct caller can't ask for a 0- or 10000-bucket series.
    weeks = max(1, min(int(window_weeks), 52))
    vol_anchor = d_to or date.today()
    row = await session.execute(
        text(
            """
            SELECT
                FLOOR((CAST(:anchor AS date) - entry_date) / 7)::int AS weeks_ago,
                COUNT(*) AS cnt
            FROM leads
            WHERE deleted_at IS NULL
              AND entry_date IS NOT NULL
              AND entry_date >  CAST(:anchor AS date) - (:weeks * INTERVAL '1 week')
              AND entry_date <= CAST(:anchor AS date)
            GROUP BY weeks_ago
            ORDER BY weeks_ago DESC
            """
        ),
        {"anchor": vol_anchor, "weeks": weeks},
    )
    volume_map: dict[int, int] = {r[0]: _int(r[1]) for r in row.fetchall()}

    # The newest bucket is "Now" only when the anchor really is today; for a
    # past range end it's just the last week (Wk N).
    anchor_is_today = vol_anchor == date.today()
    lead_volume: list[dict] = [
        {
            "label": "Now" if (w == 0 and anchor_is_today) else f"Wk {weeks - w}",
            "value": volume_map.get(w, 0),
        }
        for w in range(weeks - 1, -1, -1)  # oldest (Wk 1) → newest (anchor week)
    ]

    # ---- 6. Source / channel breakdown (in range) ---------------------------
    # Grouped on the six raw UTM fields (never rewritten) so distinct combos
    # can be resolved to a canonical channel at read time via the taxonomy —
    # channel is never stored (see attribution.py contract).
    row = await session.execute(
        text(
            f"""
            SELECT utm_source_first, utm_medium_first, utm_content_first,
                   utm_source_last,  utm_medium_last,  utm_content_last,
                   COUNT(*) AS cnt
            FROM leads
            WHERE deleted_at IS NULL{range_sql}
            GROUP BY 1,2,3,4,5,6
            """
        ),
        params,
    )
    combo_rows = row.fetchall()

    taxonomy_row = await session.execute(text("SELECT * FROM attribution_taxonomy"))
    resolver = build_resolver(taxonomy_row.fetchall())

    combos = [
        (r[0], r[1], r[2], r[3], r[4], r[5], _int(r[6])) for r in combo_rows
    ]
    channel_buckets = summarize_channels(combos, resolver)
    source_breakdown: list[dict] = _channel_buckets_to_breakdown(channel_buckets)

    # ---- 7. Sales funnel ----------------------------------------------------
    # Four stages, each counting a progressively narrower group of statuses:
    #   Leads        — all non-deleted
    #   Appointments — appointment-set
    #   Applications — qualified + appointment-set  (everyone who qualified)
    #   Sales        — sale (closed_won in API vocabulary)

    # WHERE scopes all stages to the same entry_date window; deleted_at lives in
    # each CASE too (harmless belt-and-braces) — the WHERE is what the range hooks.
    row = await session.execute(
        text(
            f"""
            SELECT
                SUM(CASE WHEN deleted_at IS NULL THEN 1 ELSE 0 END)                        AS all_leads,
                SUM(CASE WHEN deleted_at IS NULL AND LOWER(status) = 'appointment-set'
                         THEN 1 ELSE 0 END)                                                 AS appointments,
                SUM(CASE WHEN deleted_at IS NULL AND LOWER(status) IN ('qualified', 'appointment-set')
                         THEN 1 ELSE 0 END)                                                 AS applications,
                SUM(CASE WHEN deleted_at IS NULL AND LOWER(status) = 'sale'
                         THEN 1 ELSE 0 END)                                                 AS sales
            FROM leads
            WHERE deleted_at IS NULL{range_sql}
            """
        ),
        params,
    )
    funnel_row = row.fetchone()
    f_all = _int(funnel_row[0]) if funnel_row else 0
    f_appts = _int(funnel_row[1]) if funnel_row else 0
    f_apps = _int(funnel_row[2]) if funnel_row else 0
    f_sales = _int(funnel_row[3]) if funnel_row else 0

    def _funnel_pct(count: int, base: int) -> float:
        if base == 0:
            return 0.0
        return round(count / base * 100, 1)

    funnel: list[dict] = [
        {"stage": "Leads", "count": f_all, "percentage": 100.0},
        {"stage": "Appointments", "count": f_appts, "percentage": _funnel_pct(f_appts, f_all)},
        {"stage": "Applications", "count": f_apps, "percentage": _funnel_pct(f_apps, f_all)},
        {"stage": "Sales", "count": f_sales, "percentage": _funnel_pct(f_sales, f_all)},
    ]

    logger.debug(
        "compute_lead_stats — total=%d this_week=%d conversion=%.2f%% active_apps=%d",
        total_leads,
        leads_this_week,
        conversion_rate,
        active_applications,
    )

    return {
        "kpis": kpis,
        "lead_volume": lead_volume,
        "source_breakdown": source_breakdown,
        "funnel": funnel,
        # Trace block: which window produced these numbers. Lets the director
        # (and any auditor) see the exact scope it's reasoning over instead of
        # guessing. Routes ignore it; the agent tooling surfaces it.
        "_meta": {
            "window_weeks": weeks,
            "date_from": date_from,
            "date_to": date_to,
            "anchor": vol_anchor.isoformat(),
        },
    }


# ---------------------------------------------------------------------------
# Pain points + recent insights — shared by the Sales Director + specialists
# ---------------------------------------------------------------------------


async def get_top_pain_points(session: AsyncSession, limit: int = 10) -> list[dict]:
    """Return the most frequently mentioned pain points across all subjects."""
    from app.repositories.operational import PainPointRepository

    repo = PainPointRepository(session)
    points = await repo.find_most_frequent(limit=limit)
    return [
        {
            "text": p.text,
            "category": p.category,
            "frequency_count": p.frequency_count,
        }
        for p in points
    ]


async def get_recent_insights(session: AsyncSession, limit: int = 20) -> list[dict]:
    """Return the most recent call insights, newest first.

    Projects only the verified ``insights`` columns relevant to sales review.
    """
    from app.models.operational import Insight
    from app.repositories.operational import InsightRepository

    repo = InsightRepository(session)
    stmt = repo._base_select().order_by(Insight.created_at.desc()).limit(limit)
    result = await session.execute(stmt)
    insights = list(result.scalars().all())

    return [
        {
            "id": i.id,
            "call_id": i.call_id,
            "insight_type": i.insight_type,
            "signal_family": i.signal_family,
            "signal": i.signal,
            "signal_strength": i.signal_strength,
            "raw_quote": i.raw_quote,
            "what_they_say": i.what_they_say,
            "the_real_problem": i.the_real_problem,
            "buying_trigger": i.buying_trigger,
            "objection_created": i.objection_created,
            "frequency_score": i.frequency_score,
            "created_at": i.created_at.isoformat() if i.created_at else None,
        }
        for i in insights
    ]
