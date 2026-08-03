"""Social media endpoints.

POST /api/v1/social           — analyze social media performance and generate scripts
GET  /api/v1/social            — retrieve social media data summary
GET  /api/v1/social/overview   — Greg-spec social page rebuild (deliverable 1)

Sprint 3a / CI-MKT-SOCIAL
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser, get_current_user
from app.database import AsyncSessionLocal, get_session
from app.repositories.marketing import (
    InstagramPostRepository,
    SocialCommentRepository,
    SocialStatsRepository,
)
from app.repositories.social_stats import (
    attach_post_lead_counts,
    build_group_lead_days,
    build_keyword_totals,
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
# to an unsorted pass-through — and so it's safe to interpolate directly
# into an ORDER BY clause (no user input ever reaches SQL text unescaped).
_SORT_COLUMNS = {
    "timestamp", "likes_count", "comments_count", "views",
    "avg_watch_time_sec", "reach", "saves_count", "shares_count",
    "engagement_rate",
}

# sort_col (API/frontend name) -> instagram_posts column, for ORDER BY.
# "timestamp" is the one alias (matches sort_posts()'s pure-Python
# equivalent, kept for the response's own in-memory day/keyword work).
_SORT_COLUMN_SQL = {
    "timestamp": "posted_at",
    "likes_count": "likes_count",
    "comments_count": "comments_count",
    "views": "views",
    "avg_watch_time_sec": "avg_watch_time_sec",
    "reach": "reach",
    "saves_count": "saves_count",
    "shares_count": "shares_count",
    "engagement_rate": "engagement_rate",
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


def _build_post_filter_sql(
    *,
    date_from: date | None,
    date_to: date | None,
    media_type: str | None,
    table_alias: str | None = None,
) -> tuple[str, dict[str, object]]:
    """Build the ``instagram_posts`` WHERE clause + bind params shared by
    the summary/page/keyword queries, so all three agree on exactly the
    same filtered row set. Mirrors ``filter_posts()``'s semantics: inclusive
    date bounds on ``posted_at``, "REELS" matches ``is_reel``, any other
    value matches ``media_type`` case-insensitively.

    ``table_alias`` qualifies every column reference (e.g. ``"p"`` ->
    ``p.posted_at``) — REQUIRED whenever this clause is reused inside a
    query that JOINs ``instagram_posts`` against another table which has
    same-named columns (``wgr_post_comment_leads`` also has ``posted_at``/
    ``is_reel``/``media_type`` — see its migration), or Postgres raises
    ``AmbiguousColumnError``. Leave ``None`` for queries selecting FROM
    ``instagram_posts`` alone with no alias.

    ``media_type`` is bound as a query param (never interpolated) — safe
    against injection even though it's compared with ``UPPER(...)``.
    """
    prefix = f"{table_alias}." if table_alias else ""
    clauses = ["1=1"]
    params: dict[str, object] = {}
    if date_from is not None:
        clauses.append(f"{prefix}posted_at::date >= :date_from")
        params["date_from"] = date_from
    if date_to is not None:
        clauses.append(f"{prefix}posted_at::date <= :date_to")
        params["date_to"] = date_to
    if media_type:
        if media_type == "REELS":
            clauses.append(f"{prefix}is_reel IS TRUE")
        else:
            clauses.append(f"UPPER({prefix}media_type) = UPPER(:media_type)")
            params["media_type"] = media_type
    return " AND ".join(clauses), params


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

    where_sql, where_params = _build_post_filter_sql(
        date_from=parsed_from, date_to=parsed_to, media_type=media_type,
    )
    # Alias-qualified variant for the keyword-totals query, which JOINs
    # instagram_posts (aliased "p") against wgr_post_comment_leads (aliased
    # "l") — both tables have posted_at/is_reel/media_type columns (see
    # wgr_post_comment_leads's own columns in its migration), so the
    # unqualified where_sql above raises AmbiguousColumnError there.
    where_sql_p, where_params_p = _build_post_filter_sql(
        date_from=parsed_from, date_to=parsed_to, media_type=media_type,
        table_alias="p",
    )
    order_col = _SORT_COLUMN_SQL[sort_col]
    order_dir = "ASC" if sort_dir == "asc" else "DESC"

    date_filter_sql = ""
    date_filter_params: dict[str, object] = {}
    if parsed_from is not None:
        date_filter_sql += " AND occurred_at::date >= :lbd_date_from"
        date_filter_params["lbd_date_from"] = parsed_from
    if parsed_to is not None:
        date_filter_sql += " AND occurred_at::date <= :lbd_date_to"
        date_filter_params["lbd_date_to"] = parsed_to

    # ---- Four independent, filter-scoped queries run CONCURRENTLY, each on
    # its own pooler connection (pool_size=5 gives headroom), instead of
    # sequentially on one session. This is the fix for the SQL-first
    # rewrite still landing at ~5-6s: each query is fast on its own (the
    # regression was never any single query — it was the original design's
    # "SELECT * incl. captions for all 2,754 rows" 54s scan), but four
    # sequential round-trips to the Supabase transaction pooler over WAN
    # each pay their own ~0.3-1s latency PLUS a ~2.4s first-connection tax
    # apiece if run on separate sessions serially — stacking to 5-8s+ even
    # after every query itself is small. Running them concurrently overlaps
    # that latency instead of summing it. Three of the four open their own
    # fresh session (AsyncSessionLocal — same pattern as dashboard.py);
    # the route's injected `session` handles the fourth (posts page), since
    # that's the one whose result composition most naturally lives on the
    # request-scoped session. None of the four queries depend on another's
    # result, so no data race — this is pure query parallelism.
    #
    # 1. Summary KPIs — ONE aggregate query over the filtered set. No row
    #    fetch: touches zero caption bytes.
    # 2. Keyword totals — bounded SELECT of (ig_media_id, keyword_counts,
    #    total_leads) for FILTERED posts only, via a join against
    #    instagram_posts on the same where_sql. No captions.
    # 3. Posts page — SQL ORDER BY (whitelisted) + LIMIT/OFFSET, ONLY the
    #    requested page. Caption truncated server-side (LEFT(caption, 300))
    #    — the table renders a preview; the full post is one permalink
    #    click away on Instagram.
    # 4. Leads by Day — GROUP BY (day, keyword) aggregate over
    #    wgr_comment_events, not a raw 15,856-row fetch (that alone
    #    measured 2-4s). build_group_lead_days reshapes the pre-counted
    #    groups into the same shape build_leads_by_day produces from raw
    #    rows.
    async def _fetch_summary() -> dict:
        async with AsyncSessionLocal() as s:
            row = (
                await s.execute(
                    text(
                        f"""
                        SELECT
                            COUNT(*) AS posts_in_range,
                            COUNT(*) FILTER (WHERE is_reel) AS reels_count,
                            COUNT(*) FILTER (WHERE UPPER(media_type) = 'CAROUSEL_ALBUM') AS carousels_count,
                            COALESCE(SUM(avg_watch_time_sec) FILTER (WHERE is_reel), 0) AS total_watch_time_sec,
                            COALESCE(SUM(views) FILTER (WHERE is_reel), 0) AS total_views,
                            COALESCE(SUM(reach), 0) AS total_reach,
                            COALESCE(SUM(likes_count), 0) AS total_likes,
                            COALESCE(SUM(saves_count), 0) AS total_saves
                        FROM instagram_posts
                        WHERE {where_sql}
                        """  # noqa: S608 — where_sql built from a fixed whitelist in _build_post_filter_sql
                    ),
                    where_params,
                )
            ).mappings().one()
            return dict(row)

    async def _fetch_lead_rows() -> list[dict]:
        async with AsyncSessionLocal() as s:
            rows = (
                await s.execute(
                    text(
                        f"""
                        SELECT l.ig_media_id, l.keyword_counts, l.total_leads
                        FROM wgr_post_comment_leads l
                        JOIN instagram_posts p ON p.ig_media_id = l.ig_media_id
                        WHERE {where_sql_p}
                        """  # noqa: S608 — where_sql_p built from a fixed whitelist in _build_post_filter_sql, alias-qualified
                    ),
                    where_params_p,
                )
            ).mappings().all()
            return [dict(r) for r in rows]

    async def _fetch_event_groups() -> list[dict]:
        async with AsyncSessionLocal() as s:
            rows = (
                await s.execute(
                    text(
                        f"""
                        SELECT occurred_at::date AS day, LOWER(TRIM(keyword)) AS keyword, COUNT(*) AS n
                        FROM wgr_comment_events
                        WHERE keyword IS NOT NULL AND TRIM(keyword) != ''{date_filter_sql}
                        GROUP BY occurred_at::date, LOWER(TRIM(keyword))
                        """  # noqa: S608 — date_filter_sql built from a fixed template above
                    ),
                    date_filter_params,
                )
            ).mappings().all()
            return [dict(r) for r in rows]

    async def _fetch_page() -> list[dict]:
        rows = (
            await session.execute(
                text(
                    f"""
                    SELECT id, ig_media_id, permalink, media_type, is_reel,
                           LEFT(caption, 300) AS caption,
                           posted_at, likes_count, comments_count, saves_count,
                           shares_count, reach, views, avg_watch_time_sec, engagement_rate
                    FROM instagram_posts
                    WHERE {where_sql}
                    ORDER BY {order_col} {order_dir} NULLS LAST
                    LIMIT :limit OFFSET :offset
                    """  # noqa: S608 — where_sql/order_col/order_dir all built from fixed whitelists
                ),
                {**where_params, "limit": limit, "offset": offset},
            )
        ).mappings().all()
        return [dict(r) for r in rows]

    summary_row, lead_rows, groups, page = await asyncio.gather(
        _fetch_summary(), _fetch_lead_rows(), _fetch_event_groups(), _fetch_page(),
    )

    summary = {
        "posts_in_range": summary_row["posts_in_range"],
        "reels_count": summary_row["reels_count"],
        "carousels_count": summary_row["carousels_count"],
        "total_watch_time_sec": int(summary_row["total_watch_time_sec"]),
        "total_views": int(summary_row["total_views"]),
        "total_reach": int(summary_row["total_reach"]),
        "total_likes": int(summary_row["total_likes"]),
        "total_saves": int(summary_row["total_saves"]),
    }
    posts_total = summary["posts_in_range"]

    lead_by_media_id = {r["ig_media_id"]: r for r in lead_rows if r.get("ig_media_id")}

    # build_keyword_totals scopes by post_ids present in `posts` — pass a
    # bare-id stand-in list (no caption/engagement fields needed for this
    # rollup) so the pure helper's contract (posts, lead_rows) is unchanged.
    kw_totals = build_keyword_totals(
        [{"ig_media_id": mid} for mid in lead_by_media_id], lead_rows,
    )
    summary["total_leads"] = kw_totals["total_leads"]
    summary["per_keyword_leads"] = kw_totals["per_keyword"]
    summary["keywords"] = kw_totals["keywords"]

    # Merge lead_counts onto just the page rows (cheap — page is <= 500
    # rows, and lead_by_media_id was already fetched, filter-scoped, above).
    page = attach_post_lead_counts(page, list(lead_by_media_id.values()))

    lbd = build_group_lead_days(groups)

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
