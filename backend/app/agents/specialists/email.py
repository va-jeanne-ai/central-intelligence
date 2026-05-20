"""EmailSpecialist — Domain expert for email marketing campaigns and sequences.

Sprint 3a / CI-MKT-EMAIL
Handles email campaign metric analysis and high-converting email drafting.
"""

from __future__ import annotations

import json
import logging

from app.agents.specialists.base import SpecialistAgent

logger = logging.getLogger(__name__)


class EmailSpecialist(SpecialistAgent):
    """Email marketing campaign analysis and drafting specialist.

    Domain: email_marketing

    DB tools:
    - get_email_metrics — read email campaign performance data

    Operator tools:
    - draft_email — draft marketing emails from context and audience data
    """

    SYSTEM_PROMPT = (
        "You are CI-MKT-EMAIL, the Email Specialist of Central Intelligence. "
        "Your domain is email marketing — campaign analysis, sequence writing, "
        "and subject line optimization. "
        "You analyze email performance metrics and draft high-converting email "
        "sequences grounded in Voice of Customer insights."
    )

    def __init__(self, session=None) -> None:
        super().__init__(
            spec_id="email-specialist",
            name="Email Specialist",
            domain="email_marketing",
            session=session,
        )
        self.system_prompt = self.SYSTEM_PROMPT

    # -------------------------------------------------------------------
    # Tool registration
    # -------------------------------------------------------------------

    def _register_db_tools(self) -> None:
        """Register read-only email data access tools."""

        self.register_tool(
            name="get_email_metrics",
            description="Get email campaign metrics and performance data.",
            input_schema={
                "type": "object",
                "properties": {
                    "campaign_type": {
                        "type": "string",
                        "description": "Filter by campaign type (optional)",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results (default 20)",
                        "default": 20,
                    },
                },
                "required": [],
            },
            handler=self._handle_get_email_metrics,
        )

    def _register_operator_tools(self) -> None:
        """Register email drafting action tools."""

        self.register_tool(
            name="draft_email",
            description=(
                "Draft a marketing email based on provided context and audience data."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "subject": {
                        "type": "string",
                        "description": "Email subject line",
                    },
                    "audience": {
                        "type": "string",
                        "description": "Target audience description (optional)",
                    },
                    "tone": {
                        "type": "string",
                        "description": "Tone or voice for the email (default: professional)",
                        "default": "professional",
                    },
                },
                "required": ["subject"],
            },
            handler=self._handle_draft_email,
        )

    # -------------------------------------------------------------------
    # Tool handlers
    # -------------------------------------------------------------------

    async def _handle_get_email_metrics(
        self, campaign_type: str = "", limit: int = 20
    ) -> str:
        if not self._session:
            return json.dumps({"error": "No database session available"})
        from app.repositories.marketing import EmailCampaignRepository
        repo = EmailCampaignRepository(self._session)
        stats = await repo.aggregate_stats()
        campaigns = await repo.find_sent(limit=limit)
        stats["recent_campaigns"] = [
            {"name": c.name, "subject": c.subject, "open_rate": c.open_rate, "click_rate": c.click_rate, "status": c.status}
            for c in campaigns
        ]
        return json.dumps(stats)

    async def _handle_draft_email(
        self,
        subject: str,
        audience: str = "",
        tone: str = "professional",
    ) -> str:
        return json.dumps({"subject": subject, "audience": audience, "tone": tone, "message": "Email draft delegated to AI"})
