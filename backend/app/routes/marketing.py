"""Marketing department summary endpoint.

GET /api/v1/marketing/summary

Aggregates metrics across marketing-domain tables: content ideas, market
signals, insights, pain points, wins, goals, objections, offers, ICP, and
the business profile / monthly preferences.
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.repositories.shared_intelligence import SharedIntelligenceRepository
from app.repositories.intelligence import IntelligenceRepository

logger = logging.getLogger(__name__)

router = APIRouter(tags=["marketing"])


@router.get(
    "/marketing/summary",
    summary="Marketing department summary",
    description=(
        "Returns aggregated metrics for the marketing department: "
        "content ideas pipeline, market signals, insights, pain points, "
        "offers, ICP segments, goals and objections."
    ),
)
async def get_marketing_summary(
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Aggregate and return marketing department metrics."""

    shared = SharedIntelligenceRepository(session)
    intel = IntelligenceRepository(session)

    # Core shared-intelligence summary
    summary = await shared.get_marketing_summary()

    # Market signals — trending + top overall
    trending_signals = await intel.market_signals.find_trending(limit=10)
    top_signals = await intel.market_signals.find_top_overall(limit=5)

    # Content brief (includes monthly prefs + business profile)
    content_brief = await intel.get_content_intelligence_brief()

    # Insights count via raw SQL (no soft-delete column on insights table)
    row = await session.execute(text("SELECT COUNT(*) FROM insights"))
    total_insights: int = int(row.scalar() or 0)

    row = await session.execute(
        text(
            "SELECT COUNT(*) FROM insights "
            "WHERE created_at >= NOW() - INTERVAL '7 days'"
        )
    )
    insights_this_week: int = int(row.scalar() or 0)

    # Wins count
    row = await session.execute(
        text("SELECT COUNT(*) FROM wins WHERE deleted_at IS NULL")
    )
    total_wins: int = int(row.scalar() or 0)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "department": "marketing",
        "content_ideas": summary["content_ideas"],
        "pain_points": summary["pain_points"],
        "offers": summary["offers"],
        "icp": summary["icp"],
        "goals": summary["goals"],
        "objections": summary["objections"],
        "market_signals": {
            "trending": [
                {
                    "signal_family": s.signal_family,
                    "signal": s.signal,
                    "last_7_days": s.last_7_days,
                    "best_marketing_angle": s.best_marketing_angle,
                }
                for s in trending_signals
            ],
            "top_overall": [
                {
                    "signal_family": s.signal_family,
                    "signal": s.signal,
                    "total_mentions": s.total_mentions,
                }
                for s in top_signals
            ],
        },
        "insights": {
            "total": total_insights,
            "this_week": insights_this_week,
        },
        "wins": {
            "total": total_wins,
        },
        "business_context": {
            "business_profile": content_brief.get("business_profile"),
            "monthly_preferences": content_brief.get("monthly_preferences"),
        },
    }
