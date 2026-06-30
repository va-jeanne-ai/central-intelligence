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
          "source_breakdown": [{"source": str, "count": int, "percentage": float}, ...],
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

    # ---- 6. Source breakdown (in range) -------------------------------------
    row = await session.execute(
        text(
            f"""
            SELECT
                COALESCE(LOWER(source), 'other') AS src,
                COUNT(*) AS cnt
            FROM leads
            WHERE deleted_at IS NULL{range_sql}
            GROUP BY src
            ORDER BY cnt DESC
            """
        ),
        params,
    )
    source_rows = row.fetchall()

    source_total: int = sum(_int(r[1]) for r in source_rows)
    source_breakdown: list[dict] = []
    for r in source_rows:
        src, cnt = r[0], _int(r[1])
        pct = round((cnt / source_total * 100), 1) if source_total > 0 else 0.0
        source_breakdown.append({"source": src, "count": cnt, "percentage": pct})

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
