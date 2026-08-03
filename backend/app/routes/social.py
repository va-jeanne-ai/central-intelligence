"""Social media endpoints.

POST /api/v1/social           — analyze social media performance and generate scripts
GET  /api/v1/social            — retrieve social media data summary
GET  /api/v1/social/overview   — Greg-spec social page rebuild (deliverable 1)

Sprint 3a / CI-MKT-SOCIAL
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser, get_current_user
from app.database import get_session
from app.repositories.marketing import (
    InstagramPostRepository,
    SocialCommentRepository,
    SocialStatsRepository,
)
from app.repositories.social_stats import (
    attach_post_lead_counts,
    build_keyword_totals,
    build_leads_by_day,
    build_summary_stats,
    filter_posts,
    paginate_posts,
    sort_posts,
)
from app.services.integrations_registry import get_provider
from app.schemas.social import (
    SocialAnalyzeRequest,
    SocialAnalyzeResponse,
    SocialDataResponse,
    SocialOverviewLeadDay,
    SocialOverviewPost,
    SocialOverviewResponse,
    SocialOverviewSummary,
    SocialPlatformMetric,
)

# Platforms shown in the per-platform breakdown, in display order.
_BREAKDOWN_PLATFORMS = ["instagram", "facebook", "tiktok", "linkedin"]

# Columns the Posts table can sort by — matches sort_posts()'s "timestamp"
# alias for posted_at plus every sortable column exposed in the frontend
# (frontend/.../marketing/social/page.tsx's SortCol union). Whitelisted so
# an unrecognized value fails loudly (422) instead of silently degrading
# sort_posts() to an unsorted pass-through.
_SORT_COLUMNS = {
    "timestamp", "likes_count", "comments_count", "views",
    "avg_watch_time_sec", "reach", "saves_count", "shares_count",
    "engagement_rate",
}

# Documented gaps between Greg's live-Graph-API tracking page and this
# DB-backed rebuild — surfaced in every /overview response so the frontend
# (and anyone hitting the endpoint directly) sees them without needing to
# read FEATURE-VERIFICATION.md. See that doc for full detail.
_KNOWN_GAPS = [
    "Live connect/refresh from the Instagram Graph API is not mirrored here "
    "(no live scrape state in either DB) — posts reflect the WGR mirror's "
    "last sync, not a live pull.",
    "Skip Rate and Follows (reel-only Graph API insights) are not present "
    "in the instagram_posts mirror — omitted rather than fabricated.",
    "Total Watch Time is approximated as the sum of avg_watch_time_sec per "
    "reel — the mirror does not carry Graph API's total watch-time metric.",
    "Leads by Day is bucketed in UTC, not the tenant's configured timezone "
    "(WGR's comment_leads_by_day() RPC uses ac_timezone, default "
    "America/Denver) — a minor day-boundary difference.",
]

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/social", tags=["social"])


def _parse_date_param(value: str | None, *, param_name: str) -> date | None:
    """Parse a query param as a strict ISO ``YYYY-MM-DD`` date.

    Same idiom as ``routes/ads.py._parse_date_param``: fail loudly (422)
    rather than let a malformed string reach SQL as an opaque 500.
    """
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid {param_name}: {value!r} — expected ISO format YYYY-MM-DD",
        ) from exc


def _validate_sort_col(value: str) -> str:
    """Validate ``sort_col`` against the Posts table's whitelist.

    Unlike ``routes/email.py._resolve_campaigns_sort_by`` (which silently
    falls back to a default on an unrecognized column — safe for a route
    where the sort is a nice-to-have), an unrecognized ``sort_col`` here
    fails loudly with a 422: silently degrading to "unsorted" would look
    like a working sort that quietly stopped ordering results, which is
    worse than an explicit error for a page whose whole point is a
    sortable table. Also the injection guard: sort_posts() never sees a
    value outside this whitelist.
    """
    if value not in _SORT_COLUMNS:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid sort_col: {value!r} — expected one of {sorted(_SORT_COLUMNS)}",
        )
    return value


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


@router.get("/overview", response_model=SocialOverviewResponse)
async def get_social_overview(
    date_from: str | None = Query(
        default=None, description="Filter posts/leads on/after this date (YYYY-MM-DD)"
    ),
    date_to: str | None = Query(
        default=None, description="Filter posts/leads on/before this date (YYYY-MM-DD)"
    ),
    media_type: str | None = Query(
        default=None,
        description="REELS | IMAGE | VIDEO | CAROUSEL_ALBUM — matches Greg's ig-type-filter",
    ),
    sort_col: str = Query(default="timestamp", description="Posts table sort column"),
    sort_dir: str = Query(default="desc", pattern="^(asc|desc)$"),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> SocialOverviewResponse:
    """Rebuild Greg's own social tracking page (deliverable 1) from the WGR
    mirrors — ``instagram_posts`` (posts + engagement + reel metrics) joined
    against ``wgr_post_comment_leads`` (per-post/keyword lead counts) and
    ``wgr_comment_events`` (day-bucketed lead arrivals).

    Layout/metrics/structure mirror ``view-mkt-social`` in
    ``central-intelligence-greg/index.html`` 1:1: summary stat cards,
    per-keyword lead cards + Total Leads, Leads by Day table, sortable Posts
    table. Widgets Greg's page renders from a LIVE Instagram Graph API
    connection (not a DB table) are necessarily out of scope here — see
    ``_KNOWN_GAPS`` and FEATURE-VERIFICATION.md.
    """
    logger.info(
        "get_social_overview called — user=%s date_from=%s date_to=%s media_type=%s",
        current_user.id, date_from, date_to, media_type,
    )

    sort_col = _validate_sort_col(sort_col)

    parsed_from = _parse_date_param(date_from, param_name="date_from")
    parsed_to = _parse_date_param(date_to, param_name="date_to")

    # ---- Post identity + engagement (unfiltered read; filtered in Python —
    # small table, ~2.7k rows, same approach as ads.py's identity reads). ---
    post_rows = (
        await session.execute(
            text(
                """
                SELECT id, ig_media_id, permalink, media_type, is_reel, caption,
                       posted_at, likes_count, comments_count, saves_count,
                       shares_count, reach, views, avg_watch_time_sec, engagement_rate
                FROM instagram_posts
                ORDER BY posted_at DESC NULLS LAST
                """
            )
        )
    ).mappings().all()
    all_posts = [dict(r) for r in post_rows]

    filtered_posts = filter_posts(
        all_posts, date_from=parsed_from, date_to=parsed_to, media_type=media_type,
    )

    # ---- Per-post/keyword lead rollup (small table, ~2.7k rows). -----------
    lead_rows = (
        await session.execute(
            text("SELECT ig_media_id, keyword_counts, total_leads FROM wgr_post_comment_leads")
        )
    ).mappings().all()
    lead_rows = [dict(r) for r in lead_rows]

    summary = build_summary_stats(filtered_posts)
    kw_totals = build_keyword_totals(filtered_posts, lead_rows)
    summary["total_leads"] = kw_totals["total_leads"]
    summary["per_keyword_leads"] = kw_totals["per_keyword"]
    summary["keywords"] = kw_totals["keywords"]

    posts_with_leads = attach_post_lead_counts(filtered_posts, lead_rows)
    sorted_posts = sort_posts(posts_with_leads, sort_col=sort_col, sort_dir=sort_dir)
    page, posts_total = paginate_posts(sorted_posts, limit=limit, offset=offset)

    # ---- Leads by Day — comment-event frame (WGR comment_leads_by_day()
    # RPC equivalent), scoped by the same date range as the Posts table. ----
    event_rows = (
        await session.execute(
            text("SELECT occurred_at, keyword FROM wgr_comment_events")
        )
    ).mappings().all()
    events = [dict(r) for r in event_rows]
    lbd = build_leads_by_day(events, date_from=parsed_from, date_to=parsed_to)

    leads_by_day = [
        SocialOverviewLeadDay(
            day=d["day"],
            total=d.get("total", 0),
            per_keyword={k: v for k, v in d.items() if k not in ("day", "total")},
        )
        for d in lbd["days"]
    ]

    posts_out = [
        SocialOverviewPost(
            id=str(p["id"]),
            ig_media_id=p.get("ig_media_id"),
            permalink=p.get("permalink"),
            media_type=p.get("media_type"),
            is_reel=bool(p.get("is_reel")),
            caption=p.get("caption"),
            posted_at=p["posted_at"].isoformat() if p.get("posted_at") else None,
            likes_count=p.get("likes_count"),
            comments_count=p.get("comments_count"),
            views=p.get("views"),
            reach=p.get("reach"),
            saves_count=p.get("saves_count"),
            shares_count=p.get("shares_count"),
            avg_watch_time_sec=p.get("avg_watch_time_sec"),
            engagement_rate=p.get("engagement_rate"),
            lead_counts=p.get("lead_counts", {}),
            lead_total=p.get("lead_total", 0),
        )
        for p in page
    ]

    return SocialOverviewResponse(
        summary=SocialOverviewSummary(**summary),
        posts=posts_out,
        posts_total=posts_total,
        leads_by_day=leads_by_day,
        keywords=lbd["keywords"] or kw_totals["keywords"],
        date_from=date_from,
        date_to=date_to,
        generated_at=datetime.now(timezone.utc).isoformat(),
        gaps=_KNOWN_GAPS,
    )
