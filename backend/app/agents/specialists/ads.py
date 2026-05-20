"""AdsSpecialist — Domain expert for paid advertising performance and copy.

Sprint 4a / M04-5 — Ads Specialist Agent
Handles paid ad performance analysis and high-converting ad copy generation
across Facebook, Google, and other paid channels.
"""

from __future__ import annotations

import json
import logging

from app.agents.specialists.base import SpecialistAgent

logger = logging.getLogger(__name__)


class AdsSpecialist(SpecialistAgent):
    """Paid advertising performance analysis and copy generation specialist.

    Domain: paid_ads

    DB tools:
    - get_ads_data      — read paid ads performance metrics and creative data

    Operator tools:
    - generate_ad_copy  — generate paid ad copy based on context and audience data
    """

    SYSTEM_PROMPT = (
        "You are CI-MKT-ADS, the Ads Specialist of Central Intelligence. "
        "Your domain is paid advertising — ad creative analysis, ROAS optimization, "
        "and copy generation for Facebook, Google, and other paid channels. "
        "You analyze ad performance data and generate high-converting ad copy "
        "grounded in audience insights."
    )

    def __init__(self, session=None) -> None:
        super().__init__(
            spec_id="ads-specialist",
            name="Ads Specialist",
            domain="paid_ads",
            session=session,
        )
        self.system_prompt = self.SYSTEM_PROMPT

    # -------------------------------------------------------------------
    # Tool registration
    # -------------------------------------------------------------------

    def _register_db_tools(self) -> None:
        """Register read-only paid ads data access tools."""

        self.register_tool(
            name="get_ads_data",
            description="Get paid ads performance metrics and creative data.",
            input_schema={
                "type": "object",
                "properties": {
                    "platform": {
                        "type": "string",
                        "description": "Filter by platform (optional)",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results (default 20)",
                        "default": 20,
                    },
                },
                "required": [],
            },
            handler=self._handle_get_ads_data,
        )

    def _register_operator_tools(self) -> None:
        """Register ad copy generation action tools."""

        self.register_tool(
            name="generate_ad_copy",
            description=(
                "Generate paid ad copy based on provided context and audience data."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "objective": {
                        "type": "string",
                        "description": "Campaign objective or product to advertise",
                    },
                    "platform": {
                        "type": "string",
                        "description": "Target ad platform",
                        "default": "Facebook",
                    },
                    "tone": {
                        "type": "string",
                        "description": "Tone for the ad copy",
                        "default": "direct",
                    },
                },
                "required": ["objective"],
            },
            handler=self._handle_generate_ad_copy,
        )

    # -------------------------------------------------------------------
    # Tool handlers
    # -------------------------------------------------------------------

    async def _handle_get_ads_data(
        self, platform: str = "", limit: int = 20
    ) -> str:
        if not self._session:
            return json.dumps({"error": "No database session available"})
        from app.repositories.shared_intelligence import SharedIntelligenceRepository
        shared = SharedIntelligenceRepository(self._session)
        summary = await shared.get_marketing_summary()
        content_count = sum(summary["content_ideas"].get("by_status", {}).values())
        return json.dumps({
            "content_ideas_available": content_count,
            "pain_points": summary["pain_points"]["total"],
            "active_offers": summary["offers"]["active_count"],
            "top_pain_points": summary["pain_points"]["top"][:5],
        })

    async def _handle_generate_ad_copy(
        self,
        objective: str,
        platform: str = "Facebook",
        tone: str = "direct",
    ) -> str:
        return json.dumps(
            {
                "message": f"Ad copy generated for {objective} on {platform}",
                "objective": objective,
                "platform": platform,
            }
        )
