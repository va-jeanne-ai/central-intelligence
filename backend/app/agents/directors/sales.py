"""SalesDirector — Department coordinator for the Sales domain.

Sprint 5a / DIR-S1, DIR-S3. Extends DirectorAgent with sales-specific data
tools (pipeline summary, top pain points) and registers the two read-only
sales specialists: the leads analyst and the call analyzer.

Wiring specialists:
    director = SalesDirector(session=db_session)
    # leads_analyst + call_analyzer are registered automatically in __init__
"""

import json
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.directors.base import DirectorAgent, WINDOW_PARAMS, build_window
from app.prompts.sales_director_v1 import SALES_DIRECTOR_SYSTEM_PROMPT_V1

logger = logging.getLogger(__name__)


class SalesDirector(DirectorAgent):
    """Department head for the Sales domain.

    Registered data tools give Claude access to:
    - get_sales_summary    — pipeline KPIs, volume, source breakdown, funnel
    - get_top_pain_points  — most frequent pain points from sales calls

    Registered specialists (auto-create delegate_to_* tools):
    - leads_analyst  → LeadsSpecialist
    - call_analyzer  → CallAnalyzerSpecialist

    Pass a live ``AsyncSession`` at construction time; the director creates
    all repositories lazily from it.
    """

    def __init__(
        self,
        session: AsyncSession,
        director_id: str = "sales-director",
        name: str = "Sales Director",
        model: str = "claude-sonnet-4-6",
    ):
        self._session = session
        super().__init__(director_id=director_id, name=name, department="sales", model=model)
        self.system_prompt = SALES_DIRECTOR_SYSTEM_PROMPT_V1

        # Register Leads specialist (S02 — wrapped)
        from app.agents.specialists.leads import LeadsSpecialist
        leads_specialist = LeadsSpecialist(session=session)
        self.register_specialist("leads_analyst", leads_specialist)

        # Register Call Analyzer specialist (S03 — wrapped)
        from app.agents.specialists.call_analyzer import CallAnalyzerSpecialist
        call_analyzer_specialist = CallAnalyzerSpecialist(session=session)
        self.register_specialist("call_analyzer", call_analyzer_specialist)

    def _register_data_tools(self) -> None:
        """Wire up read-only sales data-access tools."""

        self.register_tool(
            name="get_sales_summary",
            description=(
                "Retrieve the sales pipeline summary: KPIs (total leads, leads "
                "this week, conversion rate, active applications), a lead-volume "
                "series (default 8 weeks, set window_weeks to change), the source "
                "breakdown, and the four-stage sales funnel (Leads → Appointments "
                "→ Applications → Sales). Pass date_from/date_to to scope the "
                "report to an entry-date window. Every number is computed in SQL; "
                "the response carries a _meta block naming the exact window used."
            ),
            input_schema={
                "type": "object",
                "properties": {**WINDOW_PARAMS},
                "required": [],
            },
            handler=self._handle_get_sales_summary,
        )

        self.register_tool(
            name="get_top_pain_points",
            description="Retrieve the most frequently mentioned pain points from sales calls.",
            input_schema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Number of pain points to return (default 10)",
                        "default": 10,
                    },
                },
                "required": [],
            },
            handler=self._handle_get_top_pain_points,
        )

    # -------------------------------------------------------------------
    # Tool handlers
    # -------------------------------------------------------------------

    async def _handle_get_sales_summary(
        self,
        date_from: str | None = None,
        date_to: str | None = None,
        window_weeks: int = 8,
    ) -> str:
        from app.repositories.sales_stats import compute_lead_stats

        window = build_window(date_from, date_to, window_weeks)
        return json.dumps(await compute_lead_stats(self._session, **window))

    async def _handle_get_top_pain_points(self, limit: int = 10) -> str:
        from app.repositories.sales_stats import get_top_pain_points

        return json.dumps(await get_top_pain_points(self._session, limit=limit))
