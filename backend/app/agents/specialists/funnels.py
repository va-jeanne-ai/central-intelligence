"""FunnelsSpecialist — Domain expert for funnel analysis and conversion optimization.

Sprint 3b / M03-1 — Funnels Specialist Agent
Handles funnel conversion data analysis and landing page strategy.
"""

from __future__ import annotations

import json
import logging

from app.agents.specialists.base import SpecialistAgent

logger = logging.getLogger(__name__)


class FunnelsSpecialist(SpecialistAgent):
    """Funnel analysis and conversion optimization specialist.

    Domain: funnel_analysis

    DB tools:
    - get_funnel_data — read funnel metrics and conversion performance

    Operator tools:
    - analyze_funnel — analyze a specific funnel stage for drop-off and improvement
    """

    SYSTEM_PROMPT = (
        "You are CI-MKT-FUNNELS, the Funnel Analyst Specialist of Central Intelligence. "
        "Your domain is funnel analysis, conversion optimization, and landing page strategy. "
        "You analyze funnel drop-off points and conversion data to identify improvement "
        "opportunities grounded in Voice of Customer insights. "
        "Always tie your recommendations to specific pain points and objections from the CI pool."
    )

    def __init__(self, session=None) -> None:
        super().__init__(
            spec_id="funnels-specialist",
            name="Funnels Specialist",
            domain="funnel_analysis",
            session=session,
        )
        self.system_prompt = self.SYSTEM_PROMPT

    # -------------------------------------------------------------------
    # Tool registration
    # -------------------------------------------------------------------

    def _register_db_tools(self) -> None:
        """Register read-only funnel data access tools."""

        self.register_tool(
            name="get_funnel_data",
            description="Get funnel conversion metrics and stage performance data.",
            input_schema={
                "type": "object",
                "properties": {
                    "funnel_id": {
                        "type": "string",
                        "description": "Filter by specific funnel ID (optional)",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results (default 20)",
                        "default": 20,
                    },
                },
                "required": [],
            },
            handler=self._handle_get_funnel_data,
        )

    def _register_operator_tools(self) -> None:
        """Register funnel analysis action tools."""

        self.register_tool(
            name="analyze_funnel",
            description=(
                "Analyze a specific funnel stage for drop-off points and "
                "recommend conversion improvements."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "stage": {
                        "type": "string",
                        "description": "Funnel stage to analyze (e.g. opt-in, sales page, checkout)",
                    },
                    "conversion_rate": {
                        "type": "number",
                        "description": "Current conversion rate for this stage (0.0-1.0, optional)",
                    },
                },
                "required": ["stage"],
            },
            handler=self._handle_analyze_funnel,
        )

    # -------------------------------------------------------------------
    # Tool handlers
    # -------------------------------------------------------------------

    async def _handle_get_funnel_data(
        self, funnel_id: str = "", limit: int = 20
    ) -> str:
        if not self._session:
            return json.dumps({"error": "No database session available"})
        from app.repositories.marketing import FunnelStatsRepository
        repo = FunnelStatsRepository(self._session)
        if funnel_id:
            stats = await repo.find_by_funnel(funnel_id)
        else:
            stats = await repo.find_all_latest()
        return json.dumps([
            {"funnel_id": s.funnel_id, "stage": s.stage, "event_count": s.event_count, "conversion_rate": s.conversion_rate}
            for s in stats
        ])

    async def _handle_analyze_funnel(
        self,
        stage: str,
        conversion_rate: float | None = None,
    ) -> str:
        if not self._session:
            return json.dumps({"error": "No database session available"})
        from app.repositories.marketing import FunnelEventRepository
        repo = FunnelEventRepository(self._session)
        events = await repo.find_by_stage(stage, limit=100)
        return json.dumps({"stage": stage, "event_count": len(events), "conversion_rate": conversion_rate})
