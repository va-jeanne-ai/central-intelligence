"""Fulfillment department summary endpoint.

GET /api/v1/fulfillment/summary

Aggregates fulfillment-domain metrics: member KPIs, the 8-week enrollment
volume series, status breakdown, the goal funnel, recent member wins, the
most frequent blocks/pain points, and recent call insights. Mirrors the
sales/marketing summary endpoints.
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.repositories.fulfillment_stats import compute_member_stats, get_recent_wins
from app.repositories.sales_stats import get_recent_insights, get_top_pain_points
from app.repositories.tech_sos_stats import compute_ticket_stats

logger = logging.getLogger(__name__)

router = APIRouter(tags=["fulfillment"])


@router.get(
    "/fulfillment/summary",
    summary="Fulfillment department summary",
    description=(
        "Returns aggregated metrics for the fulfillment department: member "
        "KPIs, an 8-week enrollment-volume series, status breakdown, the goal "
        "funnel, recent member wins, the most frequent blocks/pain points, and "
        "recent call insights."
    ),
)
async def get_fulfillment_summary(
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Aggregate and return fulfillment department metrics."""

    stats = await compute_member_stats(session)
    recent_wins = await get_recent_wins(session, limit=10)
    pain_points = await get_top_pain_points(session, limit=10)
    recent_insights = await get_recent_insights(session, limit=10)
    tickets = await compute_ticket_stats(session)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "department": "fulfillment",
        "kpis": stats["kpis"],
        "enrollment_volume": stats["enrollment_volume"],
        "status_breakdown": stats["status_breakdown"],
        "goal_funnel": stats["goal_funnel"],
        "recent_wins": recent_wins,
        "pain_points": pain_points,
        "recent_insights": recent_insights,
        # Tech SOS (support tickets) — additive block; member KPIs/funnel unchanged.
        "tech_sos": {
            "kpis": tickets["kpis"],
            "category_breakdown": tickets["category_breakdown"],
        },
    }
