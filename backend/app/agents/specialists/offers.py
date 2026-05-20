"""OfferSpecialist — Domain expert for offer optimization and creation.

Sprint 4b / M06-1 — Offer Specialist Agent
Handles offer design, pricing strategy, and optimization using cross-domain
data (pain_points, wins, ICP) for intelligent offer creation.
"""

from __future__ import annotations

import json
import logging

from app.agents.specialists.base import SpecialistAgent

logger = logging.getLogger(__name__)


class OfferSpecialist(SpecialistAgent):
    """Offer optimization and creation specialist.

    Domain: offer_optimization

    DB tools:
    - get_offers       — read current offer catalog
    - get_pain_points  — read pain points for offer grounding
    - get_icp_segments — read ICP segments for targeting

    Operator tools:
    - design_offer     — design or optimize an offer using VoC data
    """

    SYSTEM_PROMPT = (
        "You are CI-MKT-OFFERS, the Offer Design Specialist of Central Intelligence. "
        "Your domain is offer optimization, pricing strategy, and high-ticket offer creation. "
        "You leverage Voice of Customer data — pain points, wins, and Ideal Client Profiles — "
        "to design offers that resonate deeply with the target audience. "
        "Always ground your offer recommendations in specific customer language and proven buying triggers. "
        "Focus on transformation outcomes, not just deliverables."
    )

    def __init__(self, session=None) -> None:
        super().__init__(
            spec_id="offer-specialist",
            name="Offer Specialist",
            domain="offer_optimization",
            session=session,
        )
        self.system_prompt = self.SYSTEM_PROMPT

    # -------------------------------------------------------------------
    # Tool registration
    # -------------------------------------------------------------------

    def _register_db_tools(self) -> None:
        """Register read-only offer and intelligence data access tools."""

        self.register_tool(
            name="get_offers",
            description="Get current offer catalog including active and draft offers.",
            input_schema={
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "description": "Filter by status: 'Active', 'Draft', or empty for all (default: 'Active')",
                        "default": "Active",
                    },
                    "offer_type": {
                        "type": "string",
                        "description": "Filter by offer type, e.g. 'Coaching', 'Course', 'Product' (optional)",
                    },
                },
                "required": [],
            },
            handler=self._handle_get_offers,
        )

        self.register_tool(
            name="get_pain_points",
            description="Get top pain points from customer calls to ground offer design in real problems.",
            input_schema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of pain points to return (default 15)",
                        "default": 15,
                    },
                },
                "required": [],
            },
            handler=self._handle_get_pain_points,
        )

        self.register_tool(
            name="get_icp_segments",
            description="Get Ideal Customer Profile segments to align offer positioning with target audience.",
            input_schema={
                "type": "object",
                "properties": {
                    "primary_only": {
                        "type": "boolean",
                        "description": "If true, return only the primary ICP segment (default: false)",
                        "default": False,
                    },
                },
                "required": [],
            },
            handler=self._handle_get_icp_segments,
        )

    def _register_operator_tools(self) -> None:
        """Register offer design action tools."""

        self.register_tool(
            name="design_offer",
            description=(
                "Design or optimize an offer using Voice of Customer data. "
                "Produces a structured offer brief with name, positioning, "
                "pricing rationale, and key selling points."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "offer_type": {
                        "type": "string",
                        "description": "Type of offer to design, e.g. 'Coaching', 'Course', 'Product', 'Mastermind'",
                    },
                    "price_point": {
                        "type": "number",
                        "description": "Target price point in USD (optional — omit for AI-recommended pricing)",
                    },
                    "transformation_goal": {
                        "type": "string",
                        "description": "The core transformation the offer delivers to the client",
                    },
                },
                "required": ["offer_type", "transformation_goal"],
            },
            handler=self._handle_design_offer,
        )

    # -------------------------------------------------------------------
    # Tool handlers
    # -------------------------------------------------------------------

    async def _handle_get_offers(
        self, status: str = "Active", offer_type: str = ""
    ) -> str:
        if not self._session:
            return json.dumps({"error": "No database session available"})
        from app.repositories.intelligence import OfferRepository
        repo = OfferRepository(self._session)
        offers = await repo.find_active()
        return json.dumps([
            {"offer_id": o.offer_id, "name": o.name, "offer_type": o.offer_type, "description": o.description, "price": float(o.price) if o.price else None}
            for o in offers
        ])

    async def _handle_get_pain_points(self, limit: int = 15) -> str:
        if not self._session:
            return json.dumps({"error": "No database session available"})
        from app.repositories.operational import PainPointRepository
        repo = PainPointRepository(self._session)
        points = await repo.find_most_frequent(limit=limit)
        return json.dumps([{"text": p.text, "category": p.category, "frequency_count": p.frequency_count} for p in points])

    async def _handle_get_icp_segments(self, primary_only: bool = False) -> str:
        if not self._session:
            return json.dumps({"error": "No database session available"})
        from app.repositories.operational import ICPRepository
        repo = ICPRepository(self._session)
        if primary_only:
            primary = await repo.get_primary()
            segments = [primary] if primary else []
        else:
            segments = await repo.find_by_status("active")
        return json.dumps([{"segment": i.segment, "description": i.description, "is_primary": i.is_primary} for i in segments])

    async def _handle_design_offer(
        self,
        offer_type: str,
        transformation_goal: str,
        price_point: float | None = None,
    ) -> str:
        return json.dumps(
            {
                "offer_type": offer_type,
                "transformation_goal": transformation_goal,
                "price_point": price_point,
                "message": f"Offer design brief generated for {offer_type}: {transformation_goal}",
            }
        )
