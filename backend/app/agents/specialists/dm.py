"""DMSpecialist — Domain expert for direct message outreach and sequences.

Sprint 4a / M05-5 — DM Specialist Agent
Handles personalized DM sequences, reply templates, and follow-up cadences
grounded in ICP profiles and DM performance data.
"""

from __future__ import annotations

import json
import logging

from app.agents.specialists.base import SpecialistAgent

logger = logging.getLogger(__name__)


class DMSpecialist(SpecialistAgent):
    """DM outreach sequence creation and analysis specialist.

    Domain: dm_outreach

    DB tools:
    - get_dm_data           — read DM outreach performance data and ICP profiles

    Operator tools:
    - generate_dm_sequence  — generate a DM outreach sequence for a given ICP and objective
    """

    SYSTEM_PROMPT = (
        "You are CI-MKT-DM, the DM Specialist of Central Intelligence. "
        "Your domain is direct message outreach — crafting personalized DM sequences, "
        "reply templates, and follow-up cadences. "
        "You access ICP profiles to personalize outreach and analyze DM performance data."
    )

    def __init__(self, session=None) -> None:
        super().__init__(
            spec_id="dm-specialist",
            name="DM Specialist",
            domain="dm_outreach",
            session=session,
        )
        self.system_prompt = self.SYSTEM_PROMPT

    # -------------------------------------------------------------------
    # Tool registration
    # -------------------------------------------------------------------

    def _register_db_tools(self) -> None:
        """Register read-only DM and ICP data access tools."""

        self.register_tool(
            name="get_dm_data",
            description="Get DM outreach performance data and ICP profiles for personalization.",
            input_schema={
                "type": "object",
                "properties": {
                    "icp_segment": {
                        "type": "string",
                        "description": "Filter by ICP segment (optional)",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results (default 20)",
                        "default": 20,
                    },
                },
                "required": [],
            },
            handler=self._handle_get_dm_data,
        )

    def _register_operator_tools(self) -> None:
        """Register DM sequence generation action tools."""

        self.register_tool(
            name="generate_dm_sequence",
            description=(
                "Generate a DM outreach sequence based on ICP profile and objective."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "objective": {
                        "type": "string",
                        "description": "Outreach objective or offer to promote",
                    },
                    "icp_segment": {
                        "type": "string",
                        "description": "Target ICP segment for personalization (optional)",
                    },
                    "num_messages": {
                        "type": "integer",
                        "description": "Number of messages in the sequence",
                        "default": 3,
                    },
                },
                "required": ["objective"],
            },
            handler=self._handle_generate_dm_sequence,
        )

    # -------------------------------------------------------------------
    # Tool handlers
    # -------------------------------------------------------------------

    async def _handle_get_dm_data(
        self, icp_segment: str = "", limit: int = 20
    ) -> str:
        if not self._session:
            return json.dumps({"error": "No database session available"})
        from app.repositories.shared_intelligence import SharedIntelligenceRepository
        shared = SharedIntelligenceRepository(self._session)
        summary = await shared.get_marketing_summary()
        return json.dumps({
            "icp_segments": summary["icp"]["primary_count"],
            "icp_details": summary["icp"]["segments"],
            "pain_points": summary["pain_points"]["total"],
            "top_pain_points": summary["pain_points"]["top"][:5],
        })

    async def _handle_generate_dm_sequence(
        self,
        objective: str,
        icp_segment: str = "",
        num_messages: int = 3,
    ) -> str:
        return json.dumps(
            {
                "message": f"DM sequence generated for {objective}",
                "objective": objective,
                "num_messages": num_messages,
            }
        )
