"""FulfillmentDirector — Department coordinator for the Fulfillment domain.

Sprint 6a-lite / DIR-F1, DIR-F3. Extends DirectorAgent with fulfillment-specific
data tools (member summary, top blocks/pain points) and registers the two
read-only fulfillment specialists: the members analyst and the coaching analyst.

Wiring specialists:
    director = FulfillmentDirector(session=db_session)
    # members_analyst + coaching are registered automatically in __init__
"""

import json
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.agents.directors.base import DirectorAgent, WINDOW_PARAMS, build_window
from app.prompts.fulfillment_director_v1 import FULFILLMENT_DIRECTOR_SYSTEM_PROMPT_V1

logger = logging.getLogger(__name__)


class FulfillmentDirector(DirectorAgent):
    """Department head for the Fulfillment domain.

    Registered data tools give Claude access to:
    - get_fulfillment_summary — member KPIs, enrollment volume, status, goal funnel
    - get_top_pain_points     — most frequent blocks / pain points across members

    Registered specialists (auto-create delegate_to_* tools):
    - members_analyst → MembersSpecialist
    - coaching        → CoachingSpecialist

    Pass a live ``AsyncSession`` at construction time; the director creates
    all repositories lazily from it.
    """

    def __init__(
        self,
        session: AsyncSession,
        director_id: str = "fulfillment-director",
        name: str = "Fulfillment Director",
        model: str = settings.anthropic_model_default,
    ):
        self._session = session
        super().__init__(
            director_id=director_id, name=name, department="fulfillment", model=model
        )
        self.system_prompt = FULFILLMENT_DIRECTOR_SYSTEM_PROMPT_V1

        # Register Members specialist (F01 — wrapped)
        from app.agents.specialists.members import MembersSpecialist
        members_specialist = MembersSpecialist(session=session)
        self.register_specialist("members_analyst", members_specialist)

        # Register Coaching specialist (F02 — wrapped)
        from app.agents.specialists.coaching import CoachingSpecialist
        coaching_specialist = CoachingSpecialist(session=session)
        self.register_specialist("coaching", coaching_specialist)

    def _register_data_tools(self) -> None:
        """Wire up read-only fulfillment data-access tools."""

        self.register_tool(
            name="get_fulfillment_summary",
            description=(
                "Retrieve the fulfillment summary: member KPIs (total members, "
                "enrolled this week, active members, goals completed), an "
                "enrollment-volume series (default 8 weeks, set window_weeks to "
                "change), the status breakdown, and the goal funnel (Goals Set → "
                "In Progress → Completed). Pass date_from/date_to to scope the "
                "report to an enrollment-date window. Every number is computed in "
                "SQL; the response carries a _meta block naming the window used."
            ),
            input_schema={
                "type": "object",
                "properties": {**WINDOW_PARAMS},
                "required": [],
            },
            handler=self._handle_get_fulfillment_summary,
        )

        self.register_tool(
            name="get_top_pain_points",
            description="Retrieve the most frequently mentioned blocks / pain points across members.",
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

    async def _handle_get_fulfillment_summary(
        self,
        date_from: str | None = None,
        date_to: str | None = None,
        window_weeks: int = 8,
    ) -> str:
        from app.repositories.fulfillment_stats import compute_member_stats

        window = build_window(date_from, date_to, window_weeks)
        return json.dumps(await compute_member_stats(self._session, **window))

    async def _handle_get_top_pain_points(self, limit: int = 10) -> str:
        from app.repositories.sales_stats import get_top_pain_points

        return json.dumps(await get_top_pain_points(self._session, limit=limit))
