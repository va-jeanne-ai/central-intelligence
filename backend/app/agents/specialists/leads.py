"""LeadsSpecialist — Domain expert for the sales pipeline.

Sprint 5a / S02 (wrapped). Read-only specialist that surfaces lead volume,
sources, conversion, and funnel health on top of the existing leads data
layer. Lead CRUD stays in ``app.routes.leads`` — this agent never writes.
"""

from __future__ import annotations

import json
import logging

from app.agents.specialists.base import SpecialistAgent

logger = logging.getLogger(__name__)


class LeadsSpecialist(SpecialistAgent):
    """Sales pipeline analysis specialist.

    Domain: sales_leads

    DB tools:
    - get_leads_summary — KPIs, 8-week volume, source breakdown, funnel
    - get_lead_list     — filtered list of individual leads
    """

    SYSTEM_PROMPT = (
        "You are CI-SAL-LEADS, the Leads Specialist of Central Intelligence. "
        "Your domain is the sales pipeline — lead volume, lead sources, "
        "conversion rate, and the four-stage funnel (Leads → Appointments → "
        "Applications → Sales). You read pipeline data and explain where leads "
        "come from, where they stall, and which sources convert best. You "
        "report findings concisely with specific numbers; you never invent data."
    )

    def __init__(self, session=None) -> None:
        super().__init__(
            spec_id="leads-specialist",
            name="Leads Specialist",
            domain="sales_leads",
            session=session,
        )
        self.system_prompt = self.SYSTEM_PROMPT

    # -------------------------------------------------------------------
    # Tool registration
    # -------------------------------------------------------------------

    def _register_db_tools(self) -> None:
        """Register read-only pipeline data access tools."""

        self.register_tool(
            name="get_leads_summary",
            description=(
                "Get pipeline KPIs (total leads, leads this week, conversion "
                "rate, active applications), an 8-week lead-volume series, the "
                "source breakdown, and the four-stage sales funnel."
            ),
            input_schema={
                "type": "object",
                "properties": {},
                "required": [],
            },
            handler=self._handle_get_leads_summary,
        )

        self.register_tool(
            name="get_lead_list",
            description=(
                "Get a list of individual leads, optionally filtered by status "
                "or source. Statuses: new, contacted, qualified, appointment-set, "
                "sale, lost, stale."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "description": "Filter by DB status (optional)",
                    },
                    "source": {
                        "type": "string",
                        "description": "Filter by lead source (optional)",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results (default 50)",
                        "default": 50,
                    },
                },
                "required": [],
            },
            handler=self._handle_get_lead_list,
        )

        self.register_tool(
            name="get_appointments",
            description=(
                "Get booked appointments. Returns appointment KPIs (total, "
                "upcoming this week, show rate, no-show rate) plus a list of "
                "upcoming appointments (next 7 days). Use for questions like "
                "'what's booked this week?'."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Max upcoming appointments to list (default 20)",
                        "default": 20,
                    },
                },
                "required": [],
            },
            handler=self._handle_get_appointments,
        )

    def _register_operator_tools(self) -> None:
        """No write tools — lead CRUD lives in the leads route."""
        return None

    # -------------------------------------------------------------------
    # Tool handlers
    # -------------------------------------------------------------------

    async def _handle_get_leads_summary(self) -> str:
        if not self._session:
            return json.dumps({"error": "No database session available"})
        from app.repositories.sales_stats import compute_lead_stats

        return json.dumps(await compute_lead_stats(self._session))

    async def _handle_get_appointments(self, limit: int = 20) -> str:
        if not self._session:
            return json.dumps({"error": "No database session available"})
        from app.repositories.appointment_stats import (
            compute_appointment_stats,
            get_upcoming_appointments,
        )

        stats = await compute_appointment_stats(self._session)
        upcoming = await get_upcoming_appointments(self._session, limit=limit)
        return json.dumps({"kpis": stats["kpis"], "upcoming": upcoming})

    async def _handle_get_lead_list(
        self, status: str = "", source: str = "", limit: int = 50
    ) -> str:
        if not self._session:
            return json.dumps({"error": "No database session available"})
        from app.repositories.operational import LeadRepository

        repo = LeadRepository(self._session)
        if status:
            leads = await repo.find_by_status(status, limit=limit)
        elif source:
            leads = await repo.find_by_source(source, limit=limit)
        else:
            leads = await repo.list(limit=limit)

        return json.dumps(
            [
                {
                    "id": str(lead.id),
                    "name": lead.name,
                    "email": lead.email,
                    "status": lead.status,
                    "source": lead.source,
                }
                for lead in leads
            ]
        )
