"""SocialMediaSpecialist — Domain expert for social media content and analytics.

Sprint 3a / CI-MKT-SOCIAL
Handles social media performance data analysis and script/caption generation.
"""

from __future__ import annotations

import json
import logging

from app.agents.specialists.base import SpecialistAgent

logger = logging.getLogger(__name__)


class SocialMediaSpecialist(SpecialistAgent):
    """Social media content creation and analysis specialist.

    Domain: social_media_marketing

    DB tools:
    - get_social_data   — read social media metrics and content performance

    Operator tools:
    - generate_social_script — produce scripts, captions, and posts
    """

    SYSTEM_PROMPT = (
        "You are CI-MKT-SOCIAL, the Social Media Specialist of Central Intelligence. "
        "Your domain is social media content creation and analysis. "
        "You analyze social media performance data and generate high-converting "
        "scripts, captions, and posts tailored to each platform. "
        "Always use Voice of Customer data to ground your content in real audience language."
    )

    def __init__(self, session=None) -> None:
        super().__init__(
            spec_id="social-media-specialist",
            name="Social Media Specialist",
            domain="social_media_marketing",
            session=session,
        )
        self.system_prompt = self.SYSTEM_PROMPT

    # -------------------------------------------------------------------
    # Tool registration
    # -------------------------------------------------------------------

    def _register_db_tools(self) -> None:
        """Register read-only social data access tools."""

        self.register_tool(
            name="get_social_data",
            description="Get social media metrics and content performance data from the database.",
            input_schema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results (default 20)",
                        "default": 20,
                    },
                },
                "required": [],
            },
            handler=self._handle_get_social_data,
        )

    def _register_operator_tools(self) -> None:
        """Register content-generation action tools."""

        self.register_tool(
            name="generate_social_script",
            description=(
                "Generate a social media script or post caption based on provided context."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "The topic or subject matter for the script",
                    },
                    "platform": {
                        "type": "string",
                        "description": "Target social media platform (default: LinkedIn)",
                        "default": "LinkedIn",
                    },
                    "tone": {
                        "type": "string",
                        "description": "Tone or voice for the content (default: professional)",
                        "default": "professional",
                    },
                },
                "required": ["topic"],
            },
            handler=self._handle_generate_social_script,
        )

    # -------------------------------------------------------------------
    # Tool handlers
    # -------------------------------------------------------------------

    async def _handle_get_social_data(self, limit: int = 20) -> str:
        if not self._session:
            return json.dumps({"error": "No database session available"})
        from app.repositories.marketing import SocialStatsRepository
        repo = SocialStatsRepository(self._session)
        totals = await repo.aggregate_totals()
        return json.dumps(totals)

    async def _handle_generate_social_script(
        self,
        topic: str,
        platform: str = "LinkedIn",
        tone: str = "professional",
    ) -> str:
        return json.dumps({"topic": topic, "platform": platform, "tone": tone, "message": "Script generation delegated to AI"})
