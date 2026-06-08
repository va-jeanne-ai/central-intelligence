"""CoachingSpecialist — Domain expert for coaching-call intelligence.

Sprint 6a-lite / F02 (wrapped). Read-only specialist that surfaces what the
coaching-call analyzer already extracted: member wins, blocks to progress
(pain points), and call insights.

NOTE: distinct from ``app.prompts.coaching_analyzer_v1`` + the Celery
``analyze_call`` task, which do the heavy extraction. This specialist only
*reads* the resulting rows for the Fulfillment Director.
"""

from __future__ import annotations

import json
import logging

from app.agents.specialists.base import SpecialistAgent

logger = logging.getLogger(__name__)


class CoachingSpecialist(SpecialistAgent):
    """Coaching-call intelligence specialist.

    Domain: fulfillment_coaching

    DB tools:
    - get_recent_coaching_calls — most recent analyzed coaching calls
    - get_recent_wins           — member wins, newest first
    - get_top_pain_points       — most frequent blocks/pain across members
    """

    SYSTEM_PROMPT = (
        "You are CI-FUL-COACHING, the Coaching Specialist of Central Intelligence. "
        "Your domain is coaching-call intelligence — the wins members report, the "
        "blocks holding back their progress, and the patterns across coaching "
        "sessions. You read the analyzed coaching data and explain member progress "
        "and recurring blocks, grounded in real quotes. You report concisely and "
        "never fabricate data."
    )

    def __init__(self, session=None) -> None:
        super().__init__(
            spec_id="coaching-specialist",
            name="Coaching Specialist",
            domain="fulfillment_coaching",
            session=session,
        )
        self.system_prompt = self.SYSTEM_PROMPT

    # -------------------------------------------------------------------
    # Tool registration
    # -------------------------------------------------------------------

    def _register_db_tools(self) -> None:
        """Register read-only coaching-intelligence tools."""

        self.register_tool(
            name="get_recent_coaching_calls",
            description="Get the most recent analyzed coaching calls, newest first.",
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
            handler=self._handle_get_recent_coaching_calls,
        )

        self.register_tool(
            name="get_recent_wins",
            description="Get the most recent member wins, newest first.",
            input_schema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of wins (default 10)",
                        "default": 10,
                    },
                },
                "required": [],
            },
            handler=self._handle_get_recent_wins,
        )

        self.register_tool(
            name="get_top_pain_points",
            description="Get the most frequently mentioned blocks / pain points across members.",
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

    async def _handle_get_recent_coaching_calls(self, limit: int = 20) -> str:
        if not self._session:
            return json.dumps({"error": "No database session available"})
        from app.models.operational import Call
        from app.repositories.operational import CallRepository

        repo = CallRepository(self._session)
        # Coaching calls only, newest first.
        stmt = (
            repo._base_select()
            .where(Call.call_type.ilike("%coaching%"))
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
                    "member_id": str(c.member_id) if c.member_id else None,
                    "summary": c.summary,
                }
                for c in calls
            ]
        )

    async def _handle_get_recent_wins(self, limit: int = 10) -> str:
        if not self._session:
            return json.dumps({"error": "No database session available"})
        from app.repositories.fulfillment_stats import get_recent_wins

        return json.dumps(await get_recent_wins(self._session, limit=limit))

    async def _handle_get_top_pain_points(self, limit: int = 10) -> str:
        if not self._session:
            return json.dumps({"error": "No database session available"})
        from app.repositories.sales_stats import get_top_pain_points

        return json.dumps(await get_top_pain_points(self._session, limit=limit))
