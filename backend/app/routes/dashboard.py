"""
Dashboard stats and recommendations endpoints.

GET /api/v1/dashboard/stats
GET /api/v1/dashboard/recommendations

Aggregates real-time metrics from the database across three departments
(Sales, Fulfillment, Marketing) plus top-level KPIs, an 8-week lead-volume
series, and a recent-activity feed.

The recommendations endpoint queries key business metrics and sends them to
Claude (claude-3-haiku-20240307) to generate 4 actionable recommendations.
Results are cached in-memory for 15 minutes.

All queries run as raw SQL via sqlalchemy.text() in a single async session
to avoid the overhead of instantiating multiple ORM repositories for simple
COUNT / GROUP BY work.  The session is read-only — no writes occur here.

Column/table reference
----------------------
- leads            : id (uuid), name, status, source, created_at, deleted_at
- members          : id (uuid), status, membership_status, created_at, deleted_at
- calls            : id (text), date, call_type, scheduled_at, deleted_at, created_at
- content_ideas    : id (text), status, created_at, deleted_at
- insights         : id (text), created_at  (no soft-delete column)
- market_signals   : id (int), signal, signal_family, last_7_days, total_mentions
- pain_points      : id, description
"""

import json
import logging
import time
from datetime import datetime, timezone

import anthropic
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import AsyncSessionLocal, get_session
from app.schemas.dashboard import (
    DashboardStatsResponse,
    DepartmentStatsResponse,
    KpiResponse,
    LeadVolumePoint,
    RecentLead,
    RecommendationItem,
    RecommendationsResponse,
    StatCard,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["dashboard"])

# ---------------------------------------------------------------------------
# Helper: safe integer coercion from a query scalar
# ---------------------------------------------------------------------------

def _int(value: object) -> int:
    """Return value as int, falling back to 0 for None or non-numeric results."""
    try:
        return int(value) if value is not None else 0
    except (TypeError, ValueError):
        return 0


def _pct(numerator: int, denominator: int) -> str:
    """Format numerator/denominator as a percentage string, e.g. '12.3%'."""
    if denominator == 0:
        return "0%"
    return f"{(numerator / denominator * 100):.1f}%"


def _week_label(weeks_ago: int) -> str:
    """Return a compact week label like 'Wk 1' (oldest) through 'Wk 8' (current)."""
    # weeks_ago=7 is the oldest bucket, weeks_ago=0 is the current week
    position = 8 - weeks_ago
    return f"Wk {position}"


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.get(
    "/dashboard/stats",
    response_model=DashboardStatsResponse,
    summary="Dashboard real-time stats",
    description=(
        "Returns aggregated metrics across Sales, Fulfillment, and Marketing "
        "departments together with top-level KPIs, an 8-week lead-volume series, "
        "and the five most recently added leads."
    ),
)
async def get_dashboard_stats(
    session: AsyncSession = Depends(get_session),
) -> DashboardStatsResponse:
    """Aggregate and return dashboard statistics from the live database."""

    # ------------------------------------------------------------------
    # 1. SALES stats
    # ------------------------------------------------------------------

    # Total leads (non-deleted)
    row = await session.execute(
        text("SELECT COUNT(*) FROM leads WHERE deleted_at IS NULL")
    )
    total_leads: int = _int(row.scalar())

    # Leads created in the last 7 days
    row = await session.execute(
        text(
            "SELECT COUNT(*) FROM leads "
            "WHERE deleted_at IS NULL "
            "  AND created_at >= NOW() - INTERVAL '7 days'"
        )
    )
    leads_this_week: int = _int(row.scalar())

    # Leads created in the previous 7-day window (days 8–14 ago) for % change
    row = await session.execute(
        text(
            "SELECT COUNT(*) FROM leads "
            "WHERE deleted_at IS NULL "
            "  AND created_at >= NOW() - INTERVAL '14 days' "
            "  AND created_at  < NOW() - INTERVAL '7 days'"
        )
    )
    leads_prev_week: int = _int(row.scalar())

    # Conversion rate — leads whose status is 'closed_won'
    row = await session.execute(
        text(
            "SELECT COUNT(*) FROM leads "
            "WHERE deleted_at IS NULL "
            "  AND LOWER(status) = 'closed_won'"
        )
    )
    closed_won: int = _int(row.scalar())

    # Leads by status (for a compact pipeline label)
    row = await session.execute(
        text(
            "SELECT status, COUNT(*) AS cnt "
            "FROM leads "
            "WHERE deleted_at IS NULL AND status IS NOT NULL "
            "GROUP BY status "
            "ORDER BY cnt DESC "
            "LIMIT 5"
        )
    )
    status_rows = row.fetchall()

    # Pipeline = total non-closed leads (rough proxy for open opportunities)
    open_leads: int = total_leads - closed_won

    # Week-over-week change label
    if leads_prev_week == 0:
        wk_change = "+new"
    else:
        delta_pct = ((leads_this_week - leads_prev_week) / leads_prev_week) * 100
        sign = "+" if delta_pct >= 0 else ""
        wk_change = f"{sign}{delta_pct:.0f}% wk"

    sales_stats = [
        StatCard(label="New Leads", value=str(leads_this_week), sub=wk_change),
        StatCard(
            label="Conv. Rate",
            value=_pct(closed_won, total_leads),
            sub=f"{closed_won} closed",
        ),
        StatCard(label="Pipeline", value=str(open_leads), sub="open leads"),
    ]

    # ------------------------------------------------------------------
    # 2. FULFILLMENT stats
    # ------------------------------------------------------------------

    row = await session.execute(
        text(
            "SELECT COUNT(*) FROM members "
            "WHERE deleted_at IS NULL AND LOWER(status) = 'active'"
        )
    )
    active_members: int = _int(row.scalar())

    row = await session.execute(
        text(
            "SELECT COUNT(*) FROM members "
            "WHERE deleted_at IS NULL AND LOWER(status) = 'paused'"
        )
    )
    paused_members: int = _int(row.scalar())

    row = await session.execute(
        text(
            "SELECT COUNT(*) FROM members "
            "WHERE deleted_at IS NULL AND LOWER(status) = 'graduated'"
        )
    )
    graduated_members: int = _int(row.scalar())

    # Calls this week (coaching / fulfillment calls, all types)
    row = await session.execute(
        text(
            "SELECT COUNT(*) FROM calls "
            "WHERE deleted_at IS NULL "
            "  AND date >= NOW() - INTERVAL '7 days'"
        )
    )
    calls_this_week: int = _int(row.scalar())

    fulfillment_stats = [
        StatCard(label="Active Members", value=str(active_members), sub="enrolled"),
        StatCard(label="Paused", value=str(paused_members), sub="on hold"),
        StatCard(label="Calls This Week", value=str(calls_this_week), sub="sessions"),
        StatCard(label="Graduated", value=str(graduated_members), sub="completed"),
    ]

    # ------------------------------------------------------------------
    # 3. MARKETING stats
    # ------------------------------------------------------------------

    row = await session.execute(
        text("SELECT COUNT(*) FROM content_ideas WHERE deleted_at IS NULL")
    )
    total_content_ideas: int = _int(row.scalar())

    row = await session.execute(
        text(
            "SELECT COUNT(*) FROM content_ideas "
            "WHERE deleted_at IS NULL "
            "  AND LOWER(status) IN ('scheduled', 'approved')"
        )
    )
    scheduled_content: int = _int(row.scalar())

    # insights has no deleted_at column
    row = await session.execute(
        text("SELECT COUNT(*) FROM insights")
    )
    total_insights: int = _int(row.scalar())

    # Top market signals by 7-day activity
    row = await session.execute(
        text(
            "SELECT signal, last_7_days "
            "FROM market_signals "
            "ORDER BY last_7_days DESC, total_mentions DESC "
            "LIMIT 3"
        )
    )
    top_signals = row.fetchall()
    top_signal_label = top_signals[0][0] if top_signals else "—"

    marketing_stats = [
        StatCard(
            label="Content Ideas",
            value=str(total_content_ideas),
            sub=f"{scheduled_content} scheduled",
        ),
        StatCard(label="Insights", value=str(total_insights), sub="extracted"),
        StatCard(
            label="Top Signal",
            value=top_signal_label[:24] if top_signal_label else "—",
            sub="market signal",
        ),
    ]

    # ------------------------------------------------------------------
    # 4. KPIs
    # ------------------------------------------------------------------

    kpis = KpiResponse(
        total_leads=total_leads,
        leads_this_week=leads_this_week,
        calls_this_week=calls_this_week,
        active_members=active_members,
    )

    # ------------------------------------------------------------------
    # 5. Lead volume — last 8 weeks bucketed by calendar week
    # ------------------------------------------------------------------

    row = await session.execute(
        text(
            """
            SELECT
                FLOOR(EXTRACT(EPOCH FROM (NOW() - created_at)) / 604800)::int AS weeks_ago,
                COUNT(*) AS cnt
            FROM leads
            WHERE deleted_at IS NULL
              AND created_at >= NOW() - INTERVAL '8 weeks'
            GROUP BY weeks_ago
            ORDER BY weeks_ago DESC
            """
        )
    )
    volume_rows = {r[0]: _int(r[1]) for r in row.fetchall()}

    lead_volume: list[LeadVolumePoint] = [
        LeadVolumePoint(
            label=_week_label(w),
            value=volume_rows.get(w, 0),
        )
        for w in range(7, -1, -1)  # oldest (7 weeks ago) → newest (0 = current week)
    ]

    # ------------------------------------------------------------------
    # 6. Recent activity — last 5 leads
    # ------------------------------------------------------------------

    row = await session.execute(
        text(
            "SELECT id::text, name, status, source, created_at "
            "FROM leads "
            "WHERE deleted_at IS NULL "
            "ORDER BY created_at DESC "
            "LIMIT 5"
        )
    )
    recent_rows = row.fetchall()

    recent_leads: list[RecentLead] = [
        RecentLead(
            id=str(r[0]),
            name=r[1],
            status=r[2],
            source=r[3],
            created_at=r[4].isoformat() if r[4] is not None else None,
        )
        for r in recent_rows
    ]

    # ------------------------------------------------------------------
    # Assemble and return
    # ------------------------------------------------------------------

    logger.debug(
        "Dashboard stats computed — total_leads=%d leads_this_week=%d "
        "active_members=%d calls_this_week=%d",
        total_leads,
        leads_this_week,
        active_members,
        calls_this_week,
    )

    return DashboardStatsResponse(
        departments={
            "sales": DepartmentStatsResponse(stats=sales_stats),
            "fulfillment": DepartmentStatsResponse(stats=fulfillment_stats),
            "marketing": DepartmentStatsResponse(stats=marketing_stats),
        },
        kpis=kpis,
        lead_volume=lead_volume,
        recent_leads=recent_leads,
    )


# ---------------------------------------------------------------------------
# Recommendations endpoint — helpers, cache, and route
# ---------------------------------------------------------------------------

# Simple module-level in-memory cache (survives across requests within the
# same process; intentionally not shared across workers).
_recommendations_cache: dict = {"data": None, "timestamp": 0}
_CACHE_TTL_SECONDS = 900  # 15 minutes

RECOMMENDATIONS_PROMPT = """You are Central Intelligence, the AI business intelligence for a coaching/consulting business.

Based on the following business metrics, generate exactly 4 actionable recommendations. Each should be a single concise sentence that a business owner can act on this week.

Business Metrics:
{metrics_json}

Return a JSON array of exactly 4 objects. Each object has:
- "icon": a single emoji that represents the recommendation type (use 📞 for follow-ups, 📈 for growth/trends, 🎯 for retention, ⭐ for insights, 🔥 for urgent, 💡 for ideas)
- "text": one sentence with key numbers/phrases wrapped in <strong> tags

Example format:
[
  {{"icon": "📞", "text": "Follow up on <strong>5 stale leads</strong> — average age is 14 days"}},
  {{"icon": "📈", "text": "Webinar source drives <strong>33%</strong> of leads — increase ad spend"}}
]

Return ONLY the JSON array, no other text."""


async def _query_recommendation_metrics(session: AsyncSession) -> dict:
    """Run the seven business-metric queries needed to generate recommendations."""

    # 1. Lead pipeline by status
    row = await session.execute(
        text(
            "SELECT status, COUNT(*) AS cnt "
            "FROM leads "
            "WHERE deleted_at IS NULL "
            "GROUP BY status"
        )
    )
    pipeline_by_status = {r[0]: _int(r[1]) for r in row.fetchall()}

    # 2. Stale leads (status 'new' or 'contacted', older than 7 days)
    row = await session.execute(
        text(
            "SELECT COUNT(*), "
            "  AVG(EXTRACT(EPOCH FROM (NOW() - created_at))/86400)::int AS avg_days "
            "FROM leads "
            "WHERE deleted_at IS NULL "
            "  AND status IN ('new', 'contacted') "
            "  AND created_at < NOW() - INTERVAL '7 days'"
        )
    )
    stale_row = row.fetchone()
    stale_count = _int(stale_row[0]) if stale_row else 0
    stale_avg_days = _int(stale_row[1]) if stale_row else 0

    # 3. Member status breakdown
    row = await session.execute(
        text(
            "SELECT membership_status, COUNT(*) AS cnt "
            "FROM members "
            "WHERE deleted_at IS NULL "
            "GROUP BY membership_status"
        )
    )
    members_by_status = {r[0]: _int(r[1]) for r in row.fetchall()}

    # 4. Recent calls in last 7 days by type
    row = await session.execute(
        text(
            "SELECT call_type, COUNT(*) AS cnt "
            "FROM calls "
            "WHERE deleted_at IS NULL "
            "  AND scheduled_at >= NOW() - INTERVAL '7 days' "
            "GROUP BY call_type"
        )
    )
    recent_calls_by_type = {r[0]: _int(r[1]) for r in row.fetchall()}

    # 5. Top 5 pain points
    row = await session.execute(
        text(
            "SELECT description, COUNT(*) AS cnt "
            "FROM pain_points "
            "GROUP BY description "
            "ORDER BY cnt DESC "
            "LIMIT 5"
        )
    )
    top_pain_points = [{"description": r[0], "count": _int(r[1])} for r in row.fetchall()]

    # 6. Lead source performance
    row = await session.execute(
        text(
            "SELECT source, COUNT(*) AS cnt "
            "FROM leads "
            "WHERE deleted_at IS NULL "
            "GROUP BY source "
            "ORDER BY cnt DESC"
        )
    )
    leads_by_source = {r[0]: _int(r[1]) for r in row.fetchall()}

    # 7. Conversion count (leads that became sales)
    row = await session.execute(
        text(
            "SELECT COUNT(*) "
            "FROM leads "
            "WHERE deleted_at IS NULL "
            "  AND status = 'sale'"
        )
    )
    total_sales = _int(row.scalar())

    return {
        "pipeline_by_status": pipeline_by_status,
        "stale_leads": {"count": stale_count, "avg_age_days": stale_avg_days},
        "members_by_status": members_by_status,
        "recent_calls_by_type": recent_calls_by_type,
        "top_pain_points": top_pain_points,
        "leads_by_source": leads_by_source,
        "total_sales": total_sales,
    }


def _fallback_recommendations(metrics: dict) -> list[RecommendationItem]:
    """
    Generate plain-text recommendations from raw metrics without calling Claude.
    Used when the Claude API call fails or returns unparseable output.
    """
    recs: list[RecommendationItem] = []

    # Stale leads recommendation
    stale = metrics.get("stale_leads", {})
    stale_count = stale.get("count", 0)
    avg_days = stale.get("avg_age_days", 0)
    if stale_count > 0:
        recs.append(
            RecommendationItem(
                id="rec-1",
                icon="📞",
                text=(
                    f"Follow up on <strong>{stale_count} stale lead"
                    f"{'s' if stale_count != 1 else ''}</strong>"
                    + (f" — average age is {avg_days} days" if avg_days else "")
                ),
            )
        )
    else:
        recs.append(
            RecommendationItem(
                id="rec-1",
                icon="📞",
                text="Your lead pipeline is up to date — keep the momentum going",
            )
        )

    # Top lead source recommendation
    sources = metrics.get("leads_by_source", {})
    total_leads = sum(sources.values())
    if sources and total_leads > 0:
        top_source, top_count = next(iter(sources.items()))
        pct = round(top_count / total_leads * 100)
        recs.append(
            RecommendationItem(
                id="rec-2",
                icon="📈",
                text=(
                    f"<strong>{top_source}</strong> drives <strong>{pct}%</strong>"
                    " of leads — consider increasing investment there"
                ),
            )
        )
    else:
        recs.append(
            RecommendationItem(
                id="rec-2",
                icon="📈",
                text="Diversify your lead sources to reduce pipeline risk",
            )
        )

    # Member retention recommendation
    members = metrics.get("members_by_status", {})
    inactive = members.get("inactive", 0) + members.get("paused", 0)
    if inactive > 0:
        recs.append(
            RecommendationItem(
                id="rec-3",
                icon="🎯",
                text=(
                    f"<strong>{inactive} member"
                    f"{'s are' if inactive != 1 else ' is'}</strong>"
                    " inactive or paused — schedule check-in calls this week"
                ),
            )
        )
    else:
        recs.append(
            RecommendationItem(
                id="rec-3",
                icon="🎯",
                text="All members are active — great retention, focus on upsells",
            )
        )

    # Top pain point recommendation
    pain_points = metrics.get("top_pain_points", [])
    if pain_points:
        top_pp = pain_points[0]
        recs.append(
            RecommendationItem(
                id="rec-4",
                icon="⭐",
                text=(
                    f"Pain point <strong>\"{top_pp['description']}\"</strong>"
                    f" appears {top_pp['count']} time"
                    f"{'s' if top_pp['count'] != 1 else ''}"
                    " — use it in your next email or content piece"
                ),
            )
        )
    else:
        sales_count = metrics.get("total_sales", 0)
        recs.append(
            RecommendationItem(
                id="rec-4",
                icon="⭐",
                text=(
                    f"<strong>{sales_count} lead"
                    f"{'s have' if sales_count != 1 else ' has'}</strong>"
                    " converted to sales — capture their success stories"
                ),
            )
        )

    # Ensure exactly 4 items; pad with a generic if needed
    while len(recs) < 4:
        recs.append(
            RecommendationItem(
                id=f"rec-{len(recs) + 1}",
                icon="💡",
                text="Review your weekly metrics and set a priority action for tomorrow",
            )
        )

    return recs[:4]


async def _call_claude_for_recommendations(
    metrics: dict,
) -> list[RecommendationItem]:
    """
    Send business metrics to Claude and parse the returned JSON array into
    RecommendationItem instances.  Raises on API or parse failure so the
    caller can fall back to deterministic recommendations.
    """
    prompt = RECOMMENDATIONS_PROMPT.format(metrics_json=json.dumps(metrics, indent=2))

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    message = await client.messages.create(
        model="claude-3-haiku-20240307",
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )

    raw_text: str = message.content[0].text.strip()

    # Claude should return a bare JSON array; parse and validate shape
    parsed = json.loads(raw_text)
    if not isinstance(parsed, list):
        raise ValueError(f"Claude response is not a JSON array: {raw_text[:200]}")

    items: list[RecommendationItem] = []
    for idx, item in enumerate(parsed[:4], start=1):
        items.append(
            RecommendationItem(
                id=f"rec-{idx}",
                icon=str(item.get("icon", "💡")),
                text=str(item.get("text", "")),
            )
        )

    if len(items) < 4:
        raise ValueError(f"Claude returned only {len(items)} recommendations, expected 4")

    return items


@router.get(
    "/dashboard/recommendations",
    response_model=RecommendationsResponse,
    summary="AI-generated business recommendations",
    description=(
        "Queries key business metrics and asks Claude to produce 4 actionable "
        "recommendations.  Results are cached in-memory for 15 minutes to avoid "
        "redundant API calls on repeated dashboard loads."
    ),
)
async def get_dashboard_recommendations() -> RecommendationsResponse:
    """Return AI-generated actionable recommendations based on live business metrics."""

    now = time.monotonic()

    # Serve from cache if still fresh
    if (
        _recommendations_cache["data"] is not None
        and (now - _recommendations_cache["timestamp"]) < _CACHE_TTL_SECONDS
    ):
        logger.debug("Serving recommendations from cache")
        cached_payload: RecommendationsResponse = _recommendations_cache["data"]
        return RecommendationsResponse(
            recommendations=cached_payload.recommendations,
            generated_at=cached_payload.generated_at,
            cached=True,
        )

    # Open a fresh session (not via Depends so we control lifetime here)
    async with AsyncSessionLocal() as session:
        try:
            metrics = await _query_recommendation_metrics(session)
        except Exception:
            logger.exception("Failed to query recommendation metrics")
            metrics = {}

    generated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    used_ai = False

    # Attempt Claude call; fall back to deterministic recommendations on any error
    if settings.anthropic_api_key:
        try:
            recommendations = await _call_claude_for_recommendations(metrics)
            used_ai = True
        except Exception:
            logger.exception(
                "Claude recommendations call failed — falling back to deterministic output"
            )
            recommendations = _fallback_recommendations(metrics)
    else:
        logger.debug(
            "anthropic_api_key not configured — using deterministic recommendations"
        )
        recommendations = _fallback_recommendations(metrics)

    logger.info(
        "Recommendations generated — ai=%s stale_leads=%d",
        used_ai,
        metrics.get("stale_leads", {}).get("count", 0),
    )

    payload = RecommendationsResponse(
        recommendations=recommendations,
        generated_at=generated_at,
        cached=False,
    )

    # Store in cache
    _recommendations_cache["data"] = payload
    _recommendations_cache["timestamp"] = now

    return payload
