"""MarketingDirector — Department coordinator for the Marketing domain.

Extends DirectorAgent with marketing-specific data tools that give Claude
read access to content ideas, market signals, pain points, offers, ICP
segments, and the business profile + monthly preferences.

Wiring specialists:
    director = MarketingDirector(session=db_session)
    director.register_specialist("email_writer", EmailWriterSpecialist(...))
    director.register_specialist("content_planner", ContentPlannerSpecialist(...))
"""

import json
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.directors.base import DirectorAgent
from app.prompts.data_integrity import DATA_INTEGRITY_RULE

logger = logging.getLogger(__name__)


class MarketingDirector(DirectorAgent):
    """Department head for the Marketing domain.

    Registered data tools give Claude access to:
    - get_content_ideas         — retrieve content ideas by status
    - get_top_pain_points       — most frequent pain points
    - get_active_offers         — current offer catalog
    - get_icp_segments          — ideal customer profile segments
    - get_market_signals        — trending market signals
    - get_content_brief         — cross-domain intelligence brief

    Pass a live ``AsyncSession`` at construction time; the director creates
    all repositories lazily from it.
    """

    SYSTEM_PROMPT = """\
You are the Marketing Director — a senior AI strategist presenting directly to the business owner.

## Your Role

You lead the marketing department. You have a team of specialists (social media, email, funnels, ads, DM, offers) that you orchestrate behind the scenes. You also have direct access to business intelligence data (pain points, market signals, content ideas, ICP profiles, offers).

## How to Respond

You are speaking DIRECTLY to the business owner — not to another AI agent. Your responses must be:

- **Conversational and engaging** — write like a sharp marketing director in a strategy meeting
- **Data-driven** — cite specific numbers, percentages, and trends from the real data
- **Actionable** — every insight should lead to a clear recommendation
- **Visually structured** — use markdown headers, bullet points, bold for key metrics, and clear sections
- **Concise** — lead with the headline finding, then support with details. No filler.

NEVER return raw JSON. NEVER expose internal agent names or tool names. NEVER say "delegating to specialist" or describe your internal process. Just present the findings as if you did the analysis yourself.

## Before Responding: Intelligence Pre-Flight

Silently query your data tools before answering. Choose based on the task:

- Content tasks: call get_top_pain_points(limit=5), get_content_ideas(status="Idea", limit=10)
- Offer tasks: call get_icp_segments(primary_only=True), get_active_offers(), get_top_pain_points(limit=10)
- Strategy/review tasks: call get_content_brief()
- Trend tasks: call get_market_signals(limit=15)

Use the returned data to enrich your answer with real numbers. If a data call fails, work with what you have — don't mention the failure to the user.

## Routing (Internal — Never Expose This)

Route tasks to specialists silently:
- Social questions → delegate_to_social_media
- Email questions → delegate_to_email_writer
- Funnel questions → delegate_to_funnel_analyst
- Ad questions → delegate_to_ads_manager
- DM questions → delegate_to_dm_specialist
- Offer questions → delegate_to_offer_creator
- Multi-channel reviews → dispatch multiple specialists in parallel

Synthesize all specialist responses into ONE cohesive answer. The user should never know multiple specialists were involved.

## Response Structure (for reviews and analysis)

Use this general structure, adapting section names to fit the topic:

### Headline Finding
One bold sentence summarizing the overall state.

### Key Metrics
- Use bullet points with **bold numbers**
- Compare to benchmarks where possible

### What's Working
- Specific wins with data

### Where We're Losing
- Specific gaps with data and root cause

### This Week's Priority
One concrete, specific action to take immediately.

### Gaps to Note
Brief mention of any data limitations (optional, only if material).

## Quality Checklist (internal)

Before responding, verify:
1. Every claim is backed by a specific number from the data
2. Cross-channel patterns are called out (e.g., same VoC gap across email and social)
3. The priority action is specific enough to execute today
4. The tone is confident and direct — like a CMO briefing, not a report
""" + DATA_INTEGRITY_RULE

    def __init__(
        self,
        session: AsyncSession,
        director_id: str = "marketing-director",
        name: str = "Marketing Director",
        model: str = "claude-sonnet-4-6",
    ):
        self._session = session
        super().__init__(director_id=director_id, name=name, department="marketing", model=model)
        self.system_prompt = self.SYSTEM_PROMPT

        # Register Social Media specialist
        from app.agents.specialists.social_media import SocialMediaSpecialist
        social_specialist = SocialMediaSpecialist(session=session)
        self.register_specialist("social_media", social_specialist)

        # Register Email specialist
        from app.agents.specialists.email import EmailSpecialist
        email_specialist = EmailSpecialist(session=session)
        self.register_specialist("email_writer", email_specialist)

        # Register Funnels specialist (M03-4)
        from app.agents.specialists.funnels import FunnelsSpecialist
        funnels_specialist = FunnelsSpecialist(session=session)
        self.register_specialist("funnel_analyst", funnels_specialist)

        # Register Ads specialist (M04-5)
        from app.agents.specialists.ads import AdsSpecialist
        ads_specialist = AdsSpecialist(session=session)
        self.register_specialist("ads_manager", ads_specialist)

        # Register DM specialist (M05-5)
        from app.agents.specialists.dm import DMSpecialist
        dm_specialist = DMSpecialist(session=session)
        self.register_specialist("dm_specialist", dm_specialist)

        # Register Offers specialist (M06-5)
        from app.agents.specialists.offers import OfferSpecialist
        offers_specialist = OfferSpecialist(session=session)
        self.register_specialist("offer_creator", offers_specialist)

    def _register_data_tools(self) -> None:
        """Wire up read-only marketing data-access tools."""

        # Lazy import to avoid circular dependency at module load time.
        from app.repositories.shared_intelligence import SharedIntelligenceRepository
        from app.repositories.intelligence import IntelligenceRepository

        self.register_tool(
            name="get_content_ideas",
            description=(
                "Retrieve content ideas from the database, optionally filtered by status. "
                "Valid statuses: Idea, Draft, Scheduled, Approved, Published. "
                "Leave status empty to get top-scored ideas across all statuses."
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
                        "description": "Maximum number of results (default 20)",
                        "default": 20,
                    },
                },
                "required": [],
            },
            handler=self._handle_get_content_ideas,
        )

        self.register_tool(
            name="get_top_pain_points",
            description=(
                "Retrieve the most frequently mentioned pain points from customer "
                "calls, ranked by a precomputed frequency_count. This is an "
                "all-history counter, not a dated feed — there is no date-range "
                "slice for it; don't infer one. Each item reports its "
                "frequency_count so the ranking basis is visible."
            ),
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
            handler=self._handle_get_pain_points,
        )

        self.register_tool(
            name="get_active_offers",
            description="Retrieve the current active offer catalog.",
            input_schema={
                "type": "object",
                "properties": {},
                "required": [],
            },
            handler=self._handle_get_active_offers,
        )

        self.register_tool(
            name="get_icp_segments",
            description="Retrieve Ideal Customer Profile (ICP) segments.",
            input_schema={
                "type": "object",
                "properties": {
                    "primary_only": {
                        "type": "boolean",
                        "description": "If true, return only primary ICP segments",
                        "default": False,
                    },
                },
                "required": [],
            },
            handler=self._handle_get_icp_segments,
        )

        self.register_tool(
            name="get_market_signals",
            description=(
                "Retrieve market signals from customer call analysis. These are "
                "stored as precomputed counters, NOT dated rows, so only two "
                "timeframes are real: 'trending' ranks by a precomputed last-7-day "
                "activity counter; 'all_time' ranks by total mentions across all "
                "history. There is no arbitrary date-range slice for this data — do "
                "not infer one. Each signal reports last_7_days and total_mentions "
                "so you can see the basis of the ranking."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "timeframe": {
                        "type": "string",
                        "enum": ["trending", "all_time"],
                        "description": (
                            "'trending' = precomputed last-7-day counter (default); "
                            "'all_time' = total mentions across all history."
                        ),
                        "default": "trending",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of signals to return (default 15)",
                        "default": 15,
                    },
                },
                "required": [],
            },
            handler=self._handle_get_market_signals,
        )

        self.register_tool(
            name="get_content_brief",
            description=(
                "Generate a comprehensive content intelligence brief that combines "
                "trending signals, top tags, active offers, and current monthly preferences."
            ),
            input_schema={
                "type": "object",
                "properties": {},
                "required": [],
            },
            handler=self._handle_get_content_brief,
        )

    # -------------------------------------------------------------------
    # Tool handlers
    # -------------------------------------------------------------------

    async def _handle_get_content_ideas(
        self, status: str = "", limit: int = 20
    ) -> str:
        from app.repositories.operational import ContentIdeaRepository

        repo = ContentIdeaRepository(self._session)
        if status:
            ideas = await repo.find_by_status(status, limit=limit)
        else:
            ideas = await repo.find_top_scored(limit=limit)

        return json.dumps(
            [
                {
                    "id": i.id,
                    "content_angle": i.content_angle,
                    "content_format": i.content_format,
                    "idea_score": i.idea_score,
                    "status": i.status,
                    "best_platform": i.best_platform,
                    "hook_opening_line": i.hook_opening_line,
                }
                for i in ideas
            ]
        )

    async def _handle_get_pain_points(self, limit: int = 10) -> str:
        from app.repositories.operational import PainPointRepository

        repo = PainPointRepository(self._session)
        points = await repo.find_most_frequent(limit=limit)
        return json.dumps(
            [
                {
                    "text": p.text,
                    "category": p.category,
                    "frequency_count": p.frequency_count,
                }
                for p in points
            ]
        )

    async def _handle_get_active_offers(self) -> str:
        from app.repositories.intelligence import OfferRepository

        repo = OfferRepository(self._session)
        offers = await repo.find_active()
        return json.dumps(
            [
                {
                    "offer_id": o.offer_id,
                    "name": o.name,
                    "offer_type": o.offer_type,
                    "description": o.description,
                    "price": float(o.price) if o.price is not None else None,
                }
                for o in offers
            ]
        )

    async def _handle_get_icp_segments(self, primary_only: bool = False) -> str:
        from app.repositories.operational import ICPRepository

        repo = ICPRepository(self._session)
        if primary_only:
            primary = await repo.get_primary()
            segments = [primary] if primary else []
        else:
            segments = await repo.find_by_status("active")

        return json.dumps(
            [
                {
                    "segment": i.segment,
                    "description": i.description,
                    "demographics": i.demographics,
                    "pain_summary": i.pain_summary,
                    "buying_triggers": i.buying_triggers,
                    "is_primary": i.is_primary,
                }
                for i in segments
            ]
        )

    async def _handle_get_market_signals(
        self, timeframe: str = "trending", limit: int = 15
    ) -> str:
        from app.repositories.intelligence import MarketSignalRepository

        repo = MarketSignalRepository(self._session)
        # Only two real bases exist for this denormalized counter data; anything
        # other than the explicit 'all_time' falls back to the trending counter.
        if timeframe == "all_time":
            signals = await repo.find_top_overall(limit=limit)
        else:
            signals = await repo.find_trending(limit=limit)
        return json.dumps(
            {
                "_meta": {
                    "timeframe": "all_time" if timeframe == "all_time" else "trending",
                    "basis": (
                        "total_mentions counter (all history)"
                        if timeframe == "all_time"
                        else "last_7_days precomputed counter"
                    ),
                },
                "signals": [
                    {
                        "signal_family": s.signal_family,
                        "signal": s.signal,
                        "last_7_days": s.last_7_days,
                        "total_mentions": s.total_mentions,
                        "best_marketing_angle": s.best_marketing_angle,
                    }
                    for s in signals
                ],
            }
        )

    async def _handle_get_content_brief(self) -> str:
        from app.repositories.intelligence import IntelligenceRepository

        repo = IntelligenceRepository(self._session)
        brief = await repo.get_content_intelligence_brief()
        return json.dumps(brief)
