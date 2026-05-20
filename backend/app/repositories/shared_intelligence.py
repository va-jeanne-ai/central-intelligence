"""Shared intelligence repository — facade for the 7 cross-department tables.

Provides a single entry-point for querying goals, wins, pain_points,
objections, content_ideas, icp, and offers in a unified API.
"""

from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select

from app.models.operational import Goal, Win, PainPoint, Objection, ContentIdea, ICP
from app.models.intelligence import Offer
from app.repositories.operational import (
    GoalRepository,
    WinRepository,
    PainPointRepository,
    ObjectionRepository,
    ContentIdeaRepository,
    ICPRepository,
)
from app.repositories.intelligence import OfferRepository


class SharedIntelligenceRepository:
    """Facade for all 7 shared intelligence tables.

    Composes sub-repositories and provides cross-table aggregation queries
    that are useful for marketing intelligence and department summaries.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.goals = GoalRepository(session)
        self.wins = WinRepository(session)
        self.pain_points = PainPointRepository(session)
        self.objections = ObjectionRepository(session)
        self.content_ideas = ContentIdeaRepository(session)
        self.icp = ICPRepository(session)
        self.offers = OfferRepository(session)

    async def get_marketing_summary(self) -> dict[str, Any]:
        """Aggregate a marketing intelligence summary across all shared tables."""
        # Content ideas by status
        ideas_by_status: dict[str, int] = {}
        for status in ("Idea", "Draft", "Scheduled", "Approved", "Published"):
            ideas = await self.content_ideas.find_by_status(status)
            if ideas:
                ideas_by_status[status] = len(ideas)

        top_ideas = await self.content_ideas.find_top_scored(limit=5)

        # Pain points
        top_pain_points = await self.pain_points.find_most_frequent(limit=10)

        # Active offers
        active_offers = await self.offers.find_active()

        # ICP segments
        primary_icps = await self.icp.list_all(status="active")

        # Goals by status
        active_goals = await self.goals.find_by_status("active")
        completed_goals = await self.goals.find_by_status("completed")

        # Unresolved objections
        unresolved_objections = await self.objections.find_unresolved()

        return {
            "content_ideas": {
                "by_status": ideas_by_status,
                "top_scored": [
                    {
                        "id": i.id,
                        "content_angle": i.content_angle,
                        "content_format": i.content_format,
                        "idea_score": i.idea_score,
                        "status": i.status,
                    }
                    for i in top_ideas
                ],
            },
            "pain_points": {
                "total": len(top_pain_points),
                "top": [
                    {
                        "text": p.text,
                        "category": p.category,
                        "frequency_count": p.frequency_count,
                    }
                    for p in top_pain_points
                ],
            },
            "offers": {
                "active_count": len(active_offers),
                "active": [
                    {"offer_id": o.offer_id, "name": o.name, "offer_type": o.offer_type}
                    for o in active_offers
                ],
            },
            "icp": {
                "primary_count": len(primary_icps),
                "segments": [
                    {
                        "segment": i.segment,
                        "description": i.description,
                        "is_primary": i.is_primary,
                    }
                    for i in primary_icps
                ],
            },
            "goals": {
                "active_count": len(active_goals),
                "completed_count": len(completed_goals),
            },
            "objections": {
                "unresolved_count": len(unresolved_objections),
            },
        }
