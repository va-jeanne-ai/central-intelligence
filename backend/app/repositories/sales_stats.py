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


def _week_label(weeks_ago: int) -> str:
    """Return a compact week label.

    weeks_ago=7 → 'Wk 1' (oldest), weeks_ago=0 → 'Now' (current).
    """
    if weeks_ago == 0:
        return "Now"
    return f"Wk {8 - weeks_ago}"


# ---------------------------------------------------------------------------
# Lead stats aggregation
# ---------------------------------------------------------------------------


async def compute_lead_stats(session: AsyncSession) -> dict:
    """Aggregate lead data into KPIs, an 8-week volume series, source
    breakdown, and a four-stage sales funnel.

    Returns a plain dict (not a Pydantic model) so both the leads route and
    the agent tooling can consume it:

        {
          "kpis": {total_leads, leads_this_week, conversion_rate, active_applications},
          "lead_volume": [{"label": str, "value": int}, ...],          # 8 points
          "source_breakdown": [{"source": str, "count": int, "percentage": float}, ...],
          "funnel": [{"stage": str, "count": int, "percentage": float}, ...],  # 4 stages
        }
    """

    # ---- 1. Total leads (non-deleted) ---------------------------------------
    row = await session.execute(
        text("SELECT COUNT(*) FROM leads WHERE deleted_at IS NULL")
    )
    total_leads: int = _int(row.scalar())

    # ---- 2. Leads created in the last 7 days --------------------------------
    row = await session.execute(
        text(
            "SELECT COUNT(*) FROM leads "
            "WHERE deleted_at IS NULL "
            "  AND created_at >= NOW() - INTERVAL '7 days'"
        )
    )
    leads_this_week: int = _int(row.scalar())

    # ---- 3. Conversion rate — status 'sale' in DB ---------------------------
    row = await session.execute(
        text(
            "SELECT COUNT(*) FROM leads "
            "WHERE deleted_at IS NULL "
            "  AND LOWER(status) = 'sale'"
        )
    )
    sold_count: int = _int(row.scalar())

    conversion_rate: float = 0.0
    if total_leads > 0:
        conversion_rate = round((sold_count / total_leads) * 100, 2)

    # ---- 4. Active applications — qualified + appointment-set ---------------
    row = await session.execute(
        text(
            "SELECT COUNT(*) FROM leads "
            "WHERE deleted_at IS NULL "
            "  AND LOWER(status) IN ('qualified', 'appointment-set')"
        )
    )
    active_applications: int = _int(row.scalar())

    kpis = {
        "total_leads": total_leads,
        "leads_this_week": leads_this_week,
        "conversion_rate": conversion_rate,
        "active_applications": active_applications,
    }

    # ---- 5. Lead volume — last 8 calendar weeks -----------------------------
    row = await session.execute(
        text(
            """
            SELECT
                FLOOR(EXTRACT(EPOCH FROM (NOW() - created_at)) / 604800)::int AS weeks_ago,
                COUNT(*) AS cnt
            FROM leads
            WHERE deleted_at IS NULL
              AND created_at >= NOW() - INTERVAL '8 weeks'
            GROUP BY weeks_ago
            ORDER BY weeks_ago DESC
            """
        )
    )
    volume_map: dict[int, int] = {r[0]: _int(r[1]) for r in row.fetchall()}

    lead_volume: list[dict] = [
        {"label": _week_label(w), "value": volume_map.get(w, 0)}
        for w in range(7, -1, -1)  # oldest (Wk 1) → newest (Now)
    ]

    # ---- 6. Source breakdown ------------------------------------------------
    row = await session.execute(
        text(
            """
            SELECT
                COALESCE(LOWER(source), 'other') AS src,
                COUNT(*) AS cnt
            FROM leads
            WHERE deleted_at IS NULL
            GROUP BY src
            ORDER BY cnt DESC
            """
        )
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

    row = await session.execute(
        text(
            """
            SELECT
                SUM(CASE WHEN deleted_at IS NULL THEN 1 ELSE 0 END)                        AS all_leads,
                SUM(CASE WHEN deleted_at IS NULL AND LOWER(status) = 'appointment-set'
                         THEN 1 ELSE 0 END)                                                 AS appointments,
                SUM(CASE WHEN deleted_at IS NULL AND LOWER(status) IN ('qualified', 'appointment-set')
                         THEN 1 ELSE 0 END)                                                 AS applications,
                SUM(CASE WHEN deleted_at IS NULL AND LOWER(status) = 'sale'
                         THEN 1 ELSE 0 END)                                                 AS sales
            FROM leads
            """
        )
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
