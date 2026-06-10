"""MembersSpecialist — Domain expert for the member roster.

Sprint 6a-lite / F01 (wrapped). Read-only specialist that surfaces member
counts, statuses, enrollment trends, and goal progress on top of the existing
members data layer. Member CRUD stays in ``app.routes.members`` — this agent
never writes.
"""

from __future__ import annotations

import json
import logging

from app.agents.specialists.base import SpecialistAgent

logger = logging.getLogger(__name__)


class MembersSpecialist(SpecialistAgent):
    """Member-roster analysis specialist.

    Domain: fulfillment_members

    DB tools:
    - get_member_stats — KPIs, enrollment volume, status breakdown, goal funnel
    - get_member_list  — filtered list of individual members
    - get_member_goals — goals for a specific member
    """

    SYSTEM_PROMPT = (
        "You are CI-FUL-MEMBERS, the Members Specialist of Central Intelligence. "
        "Your domain is the active member roster — how many members are enrolled, "
        "their statuses (active, paused, graduated, churned), enrollment trends, "
        "and goal progress. You read member data and explain roster health, "
        "retention signals, and where members stand on their goals. You report "
        "concisely with specific numbers and never invent data."
    )

    def __init__(self, session=None) -> None:
        super().__init__(
            spec_id="members-specialist",
            name="Members Specialist",
            domain="fulfillment_members",
            session=session,
        )
        self.system_prompt = self.SYSTEM_PROMPT

    # -------------------------------------------------------------------
    # Tool registration
    # -------------------------------------------------------------------

    def _register_db_tools(self) -> None:
        """Register read-only member data access tools."""

        self.register_tool(
            name="get_member_stats",
            description=(
                "Get member roster KPIs (total members, enrolled this week, active "
                "members, goals completed), an 8-week enrollment-volume series, the "
                "status breakdown, and the goal funnel (Goals Set → In Progress → "
                "Completed)."
            ),
            input_schema={
                "type": "object",
                "properties": {},
                "required": [],
            },
            handler=self._handle_get_member_stats,
        )

        self.register_tool(
            name="get_member_list",
            description=(
                "Get a list of individual members, optionally filtered by status "
                "(active, paused, graduated, churned)."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "description": "Filter by status (optional)",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results (default 50)",
                        "default": 50,
                    },
                },
                "required": [],
            },
            handler=self._handle_get_member_list,
        )

        self.register_tool(
            name="get_member_goals",
            description="Get the goals for a specific member by member id.",
            input_schema={
                "type": "object",
                "properties": {
                    "member_id": {
                        "type": "string",
                        "description": "The member's UUID",
                    },
                },
                "required": ["member_id"],
            },
            handler=self._handle_get_member_goals,
        )

        self.register_tool(
            name="get_goal_progress",
            description=(
                "Get accountability/goal progress across all members: KPIs "
                "(total, in progress, completed, overdue), the goal funnel "
                "(Goals Set → In Progress → Completed), and the status breakdown. "
                "Use for 'how are members tracking on their goals?'."
            ),
            input_schema={
                "type": "object",
                "properties": {},
                "required": [],
            },
            handler=self._handle_get_goal_progress,
        )

    def _register_operator_tools(self) -> None:
        """No write tools — member CRUD lives in the members route."""
        return None

    # -------------------------------------------------------------------
    # Tool handlers
    # -------------------------------------------------------------------

    async def _handle_get_member_stats(self) -> str:
        if not self._session:
            return json.dumps({"error": "No database session available"})
        from app.repositories.fulfillment_stats import compute_member_stats

        return json.dumps(await compute_member_stats(self._session))

    async def _handle_get_member_list(self, status: str = "", limit: int = 50) -> str:
        if not self._session:
            return json.dumps({"error": "No database session available"})
        from app.repositories.operational import MemberRepository

        repo = MemberRepository(self._session)
        if status:
            members = await repo.find_by_status(status, limit=limit)
        else:
            members = await repo.list(limit=limit)

        return json.dumps(
            [
                {
                    "id": str(m.id),
                    "name": m.name,
                    "email": m.email,
                    "status": m.status,
                    "enrollment_date": m.enrollment_date.isoformat()
                    if m.enrollment_date
                    else None,
                }
                for m in members
            ]
        )

    async def _handle_get_member_goals(self, member_id: str) -> str:
        if not self._session:
            return json.dumps({"error": "No database session available"})
        import uuid as _uuid

        from app.repositories.operational import GoalRepository

        try:
            mid = _uuid.UUID(member_id)
        except (ValueError, TypeError):
            return json.dumps({"error": "Invalid member_id"})

        repo = GoalRepository(self._session)
        goals = await repo.find_by_member(mid)
        return json.dumps(
            [
                {
                    "id": str(g.id),
                    "goal_text": g.goal_text,
                    "status": g.status,
                    "target_date": g.target_date.isoformat() if g.target_date else None,
                }
                for g in goals
            ]
        )

    async def _handle_get_goal_progress(self) -> str:
        if not self._session:
            return json.dumps({"error": "No database session available"})
        from app.repositories.goal_stats import compute_goal_stats

        return json.dumps(await compute_goal_stats(self._session))
