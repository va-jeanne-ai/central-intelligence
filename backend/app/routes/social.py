"""Social media endpoints.

POST /api/v1/social  — analyze social media performance and generate scripts
GET  /api/v1/social  — retrieve social media data summary

Sprint 3a / CI-MKT-SOCIAL
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser, get_current_user
from app.database import get_session
from app.repositories.marketing import (
    InstagramPostRepository,
    SocialCommentRepository,
    SocialStatsRepository,
)
from app.services.integrations_registry import get_provider
from app.schemas.social import (
    SocialAnalyzeRequest,
    SocialAnalyzeResponse,
    SocialDataResponse,
    SocialPlatformMetric,
)

# Platforms shown in the per-platform breakdown, in display order.
_BREAKDOWN_PLATFORMS = ["instagram", "facebook", "tiktok", "linkedin"]

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/social", tags=["social"])


@router.post("", response_model=SocialAnalyzeResponse)
async def analyze_social(
    body: SocialAnalyzeRequest,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> SocialAnalyzeResponse:
    """Analyze social media performance and generate a content script.

    Routes through MarketingDirector → SocialMediaSpecialist. The director
    pulls platform stats via its data tools and composes a strategy + a
    short script suggestion with Claude.
    """
    from app.agents.directors.marketing import MarketingDirector

    # MarketingDirector.__init__ already registers social_media.
    director = MarketingDirector(session=session)

    logger.info(
        "analyze_social called — user=%s date_from=%s date_to=%s",
        current_user.id,
        body.date_from,
        body.date_to,
    )

    repo = SocialStatsRepository(session)
    totals = await repo.aggregate_totals()

    # Two modes:
    #   Script mode: caller sends topic + platform + brand_voice → produce
    #                a script for that specific topic on that platform.
    #   Analysis mode: caller sends date_from/date_to (or nothing) → analyze
    #                  recent performance + suggest a script for the strongest platform.
    if body.topic:
        platform_clause = f"the {body.platform}" if body.platform else "the platform best suited to this topic"
        voice_clause = f" in a {body.brand_voice} tone" if body.brand_voice else ""
        prompt = (
            f"Write a short social media script for {platform_clause}{voice_clause}, "
            f"on the topic: {body.topic!r}.\n\n"
            f"Delegate to the Social Media specialist (via delegate_to_social_media) "
            f"if you need recent performance data to ground the script. Otherwise "
            f"produce the script directly. Structure: a strong hook line, 3-5 beats "
            f"that build the story, and a clear call-to-action."
        )
    else:
        period_clause = ""
        if body.date_from and body.date_to:
            period_clause = f" for the period {body.date_from} to {body.date_to}"
        prompt = (
            f"Analyze our social media performance{period_clause}. **Delegate to the "
            f"Social Media specialist** (via delegate_to_social_media) to pull "
            f"per-platform stats (Instagram, Facebook, LinkedIn, TikTok — followers, "
            f"engagement, reach). Then write your own analysis that **names each "
            f"platform explicitly** with its specific metrics. Identify the strongest "
            f"and weakest platform with reasoning. Finally, produce a short content "
            f"script idea (hook + 3-5 beats) tailored to the strongest platform's "
            f"audience."
        )

    analysis_text = ""
    async for chunk in director.stream_response(prompt):
        analysis_text += chunk

    # In Script mode the page renders `script`; in Analysis mode it might
    # render `analysis`. Easiest: populate both with the same text so either
    # rendering path works without a frontend change.
    return SocialAnalyzeResponse(
        analysis=analysis_text,
        script=analysis_text,
        recommendations=[],
        data_used=totals,
    )


@router.get("", response_model=SocialDataResponse)
async def get_social_data(
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> SocialDataResponse:
    """Return current social media data summary.

    Queries the social_stats table via SocialStatsRepository and returns
    aggregated totals across all tracked accounts.
    """
    logger.info("get_social_data called — user=%s", current_user.id)

    repo = SocialStatsRepository(session)
    totals = await repo.aggregate_totals()

    # Which social providers are actually connected (integrations table) +
    # their registry status (available vs coming_soon). Connection drives
    # whether the breakdown shows metrics or a "Connect" button.
    connected_rows = (
        await session.execute(
            text(
                "SELECT provider FROM integrations "
                "WHERE provider = ANY(:slugs) AND status = 'connected'"
            ),
            {"slugs": _BREAKDOWN_PLATFORMS},
        )
    ).scalars().all()
    connected = set(connected_rows)

    # One row per display platform (always all four). Metrics only when the
    # platform is connected AND has a synced row — otherwise the frontend
    # shows a Connect button (available) or a Coming-soon tag (coming_soon).
    by_platform: list[SocialPlatformMetric] = []
    for platform in _BREAKDOWN_PLATFORMS:
        provider = get_provider(platform)
        provider_status = provider["status"] if provider else "available"
        is_connected = platform in connected
        row = await repo.find_latest_by_platform(platform) if is_connected else None
        by_platform.append(
            SocialPlatformMetric(
                platform=platform,
                connected=is_connected,
                provider_status=provider_status,
                followers=row.followers if row else None,
                posts_count=row.posts_count if row else None,
                engagement_rate=row.engagement_rate if row else None,
            )
        )

    # Recent Instagram posts (per-post WGR mirror) for the "Recent Posts" card.
    ig_repo = InstagramPostRepository(session)
    recent_posts = await ig_repo.find_recent(limit=12)
    top_content = [
        {
            "id": str(p.id),
            "platform": "instagram",
            "caption": p.caption,
            "permalink": p.permalink,
            "media_type": p.media_type,
            "is_reel": p.is_reel,
            "posted_at": p.posted_at.isoformat() if p.posted_at else None,
            "likes_count": p.likes_count,
            "comments_count": p.comments_count,
            "saves_count": p.saves_count,
            "reach": p.reach,
            "views": p.views,
            "engagement_rate": p.engagement_rate,
        }
        for p in recent_posts
    ]

    # Recent substantive comments (real voice-of-customer; trigger words excluded).
    comment_repo = SocialCommentRepository(session)
    recent = await comment_repo.find_recent_substantive(limit=15)
    recent_comments = [
        {
            "id": str(c.id),
            "platform": c.platform,
            "comment_text": c.comment_text,
            "commented_at": c.commented_at.isoformat() if c.commented_at else None,
        }
        for c in recent
    ]

    return SocialDataResponse(
        posts=totals["total_posts"],
        engagement=totals["avg_engagement"],
        followers=totals["total_followers"],
        by_platform=by_platform,
        top_content=top_content,
        recent_comments=recent_comments,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )
