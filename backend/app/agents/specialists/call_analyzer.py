"""CallAnalyzerSpecialist — Domain expert for sales-call intelligence.

Sprint 5a / S03 (wrapped). Read-only specialist that surfaces insights the
call-analysis pipeline already extracted from transcripts: recurring
objections, pain points, and buying triggers.

NOTE: distinct from ``app.prompts.call_analyzer_v1`` and the Celery
``analyze_call`` task, which do the heavy extraction. This specialist only
*reads* the resulting ``insights`` rows for the Sales Director.
"""

from __future__ import annotations

import json
import logging

from app.agents.specialists.base import SpecialistAgent

logger = logging.getLogger(__name__)


class CallAnalyzerSpecialist(SpecialistAgent):
    """Sales-call intelligence specialist.

    Domain: sales_calls

    DB tools:
    - get_recent_calls   — most recent analyzed calls
    - get_call_insights  — extracted insights (objections, pain, triggers)
    - get_top_pain_points — most frequent pain points across calls
    """

    SYSTEM_PROMPT = (
        "You are CI-SAL-CALLS, the Call Analyzer Specialist of Central "
        "Intelligence. Your domain is sales-call intelligence — the recurring "
        "objections, pain points, and buying triggers extracted from call "
        "transcripts. You read the analyzed insights and explain the patterns "
        "that show up across calls, grounded in real quotes. You report "
        "concisely and never fabricate data."
    )

    def __init__(self, session=None) -> None:
        super().__init__(
            spec_id="call-analyzer-specialist",
            name="Call Analyzer Specialist",
            domain="sales_calls",
            session=session,
        )
        self.system_prompt = self.SYSTEM_PROMPT

    # -------------------------------------------------------------------
    # Tool registration
    # -------------------------------------------------------------------

    def _register_db_tools(self) -> None:
        """Register read-only call-intelligence tools."""

        self.register_tool(
            name="get_recent_calls",
            description="Get the most recently analyzed sales calls, newest first.",
            input_schema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of calls (default 20)",
                        "default": 20,
                    },
                },
                "required": [],
            },
            handler=self._handle_get_recent_calls,
        )

        self.register_tool(
            name="get_call_insights",
            description=(
                "Get insights extracted from call transcripts, optionally "
                "filtered by insight type (e.g. Pain, Objection, Goal). Returns "
                "the signal, raw quote, real problem, and buying trigger."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "insight_type": {
                        "type": "string",
                        "description": "Filter by insight type (optional)",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of insights (default 20)",
                        "default": 20,
                    },
                },
                "required": [],
            },
            handler=self._handle_get_call_insights,
        )

        self.register_tool(
            name="get_top_pain_points",
            description="Get the most frequently mentioned pain points across all calls.",
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

    def _register_operator_tools(self) -> None:
        """No write tools — transcription/analysis runs in Celery tasks."""
        return None

    # -------------------------------------------------------------------
    # Tool handlers
    # -------------------------------------------------------------------

    async def _handle_get_recent_calls(self, limit: int = 20) -> str:
        if not self._session:
            return json.dumps({"error": "No database session available"})
        from app.models.operational import Call
        from app.repositories.operational import CallRepository

        repo = CallRepository(self._session)
        stmt = (
            repo._base_select()
            .order_by(Call.date.desc().nullslast())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        calls = list(result.scalars().all())

        return json.dumps(
            [
                {
                    "id": c.id,
                    "date": c.date.isoformat() if c.date else None,
                    "call_type": c.call_type,
                    "call_result": c.call_result,
                    "summary": c.summary,
                }
                for c in calls
            ]
        )

    async def _handle_get_call_insights(
        self, insight_type: str = "", limit: int = 20
    ) -> str:
        if not self._session:
            return json.dumps({"error": "No database session available"})
        from app.repositories.operational import InsightRepository

        repo = InsightRepository(self._session)
        if insight_type:
            insights = await repo.find_by_insight_type(insight_type, limit=limit)
            data = [
                {
                    "id": i.id,
                    "insight_type": i.insight_type,
                    "signal_family": i.signal_family,
                    "signal": i.signal,
                    "signal_strength": i.signal_strength,
                    "raw_quote": i.raw_quote,
                    "the_real_problem": i.the_real_problem,
                    "buying_trigger": i.buying_trigger,
                    "objection_created": i.objection_created,
                    "frequency_score": i.frequency_score,
                }
                for i in insights
            ]
        else:
            from app.repositories.sales_stats import get_recent_insights

            data = await get_recent_insights(self._session, limit=limit)

        return json.dumps(data)

    async def _handle_get_top_pain_points(self, limit: int = 10) -> str:
        if not self._session:
            return json.dumps({"error": "No database session available"})
        from app.repositories.sales_stats import get_top_pain_points

        return json.dumps(await get_top_pain_points(self._session, limit=limit))
