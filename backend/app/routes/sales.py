"""Sales department summary endpoint.

GET /api/v1/sales/summary

Aggregates sales-domain metrics: pipeline KPIs, the 8-week lead-volume
series, source breakdown, the four-stage funnel, the most frequent pain
points, and recent call insights. Mirrors the marketing summary endpoint.
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.repositories.appointment_stats import compute_appointment_stats
from app.repositories.sales_stats import (
    compute_lead_stats,
    get_recent_insights,
    get_top_pain_points,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["sales"])


@router.get(
    "/sales/summary",
    summary="Sales department summary",
    description=(
        "Returns aggregated metrics for the sales department: pipeline KPIs, "
        "an 8-week lead-volume series, source breakdown, the four-stage sales "
        "funnel, the most frequent pain points, and recent call insights."
    ),
)
async def get_sales_summary(
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Aggregate and return sales department metrics."""

    stats = await compute_lead_stats(session)
    pain_points = await get_top_pain_points(session, limit=10)
    recent_insights = await get_recent_insights(session, limit=10)
    appt = await compute_appointment_stats(session)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "department": "sales",
        "kpis": stats["kpis"],
        "lead_volume": stats["lead_volume"],
        "source_breakdown": stats["source_breakdown"],
        "funnel": stats["funnel"],
        "pain_points": pain_points,
        "recent_insights": recent_insights,
        # Real booked-appointment counts (the funnel's "Appointments" stage
        # remains the lead-status proxy — these are a distinct, additive metric).
        "appointments": {
            "kpis": appt["kpis"],
            "status_breakdown": appt["status_breakdown"],
        },
    }


@router.get(
    "/reps",
    summary="Light reps listing for filter dropdowns",
    description=(
        "Returns id/full_name/status for sales_reps whose status is active or "
        "probation — the set relevant to a rep filter dropdown (terminated reps "
        "excluded). Lighter than /analytics/team, which also assembles metrics."
    ),
)
async def list_reps(
    include_all: bool = Query(
        default=False,
        description="Include every status (including terminated) instead of just active/probation.",
    ),
    session: AsyncSession = Depends(get_session),
) -> dict:
    where = "" if include_all else "WHERE status IN ('active', 'probation')"
    rows = (await session.execute(
        text(
            f"SELECT rep_id, full_name, status FROM sales_reps {where} "  # noqa: S608 — where is a fixed literal, no user input
            "ORDER BY full_name ASC"
        )
    )).mappings().all()
    return {
        "reps": [
            {"rep_id": r["rep_id"], "full_name": r["full_name"], "status": r["status"]}
            for r in rows
        ]
    }
