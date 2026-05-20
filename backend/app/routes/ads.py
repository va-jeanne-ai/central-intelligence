"""Paid ads endpoints.

POST /api/v1/ads  — analyze ad performance and generate ad copy
GET  /api/v1/ads  — retrieve current ads data summary

Sprint 4a / M04-5
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser, get_current_user
from app.database import get_session
from app.repositories.marketing import AdsStatsRepository
from app.repositories.shared_intelligence import SharedIntelligenceRepository
from app.schemas.ads import AdsAnalyzeRequest, AdsAnalyzeResponse, AdsDataResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ads", tags=["ads"])


@router.post("", response_model=AdsAnalyzeResponse)
async def analyze_ads(
    body: AdsAnalyzeRequest,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> AdsAnalyzeResponse:
    """Analyze ad performance and generate ad copy.

    Routes through MarketingDirector → AdsSpecialist. The director loop
    queries content ideas, pain points, and offers via its data tools, then
    composes the response with Claude. We aggregate the stream into a single
    string for the `analysis` field to preserve the existing JSON contract.
    """
    # Lazy import to avoid circular imports at module load time.
    from app.agents.directors.marketing import MarketingDirector

    # MarketingDirector.__init__ already registers all specialists
    # (ads_manager, dm_specialist, email_writer, social_media, etc.).
    # Re-registering here used to create duplicate `delegate_to_<id>` tools
    # and would 400 with "Tool names must be unique."
    director = MarketingDirector(session=session)

    logger.info(
        "analyze_ads called — user=%s platform=%s",
        current_user.id,
        body.platform,
    )

    # Keep the data summary call for the response's `data_used` field — it's
    # cheap and the frontend may display it as evidence of grounding.
    shared = SharedIntelligenceRepository(session)
    summary = await shared.get_marketing_summary()

    # Build the user-turn message. The director's system prompt + data tools
    # do the heavy lifting; we just pass through the request's intent.
    period_clause = ""
    if body.date_from and body.date_to:
        period_clause = f" for the period {body.date_from} to {body.date_to}"
    platform_clause = f" focused on the {body.platform} platform" if body.platform else ""
    prompt = (
        f"Analyze our paid ads strategy{platform_clause}{period_clause}. "
        f"Use your data tools to pull context (top pain points, active offers, "
        f"ICP segments). Then produce a short, actionable analysis followed by "
        f"2-3 ad-copy variants tailored to the platform."
    )

    analysis_text = ""
    async for chunk in director.stream_response(prompt):
        analysis_text += chunk

    return AdsAnalyzeResponse(
        analysis=analysis_text,
        ad_copy="",  # Variants live inline in `analysis` (markdown). Filling
                    # this field separately requires structured-output prompting.
        recommendations=[],  # Same — director's analysis already includes recs.
        data_used={
            "content_ideas": summary["content_ideas"],
            "pain_points": summary["pain_points"],
            "offers": {"active_count": summary["offers"]["active_count"]},
        },
    )


@router.get("", response_model=AdsDataResponse)
async def get_ads_data(
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> AdsDataResponse:
    """Return current ads data summary.

    Queries the ads_stats table via AdsStatsRepository and returns
    aggregated totals across all tracked campaigns and platforms.
    """
    logger.info("get_ads_data called — user=%s", current_user.id)

    repo = AdsStatsRepository(session)
    totals = await repo.aggregate_totals()

    return AdsDataResponse(
        campaigns=totals["total_campaigns"],
        avg_roas=totals["avg_roas"],
        total_spend=totals["total_spend"],
        top_ads=[],
        generated_at=datetime.now(timezone.utc).isoformat(),
    )
