"""Pydantic schemas for social media endpoints."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class SocialAnalyzeRequest(BaseModel):
    date_from: str | None = None
    date_to: str | None = None
    # Script-generator fields (the /marketing/social/scripts page sends these).
    topic: str | None = None
    platform: str | None = None  # "instagram" | "facebook" | "linkedin" | "tiktok"
    brand_voice: str | None = None  # "professional" | "casual" | "playful" | ...


class SocialPost(BaseModel):
    id: str
    platform: str
    content: str | None = None
    engagement_rate: float | None = None
    posted_at: datetime | None = None


class SocialAnalyzeResponse(BaseModel):
    analysis: str
    script: str
    recommendations: list[str]
    data_used: dict


class SocialPlatformMetric(BaseModel):
    """Per-platform row for the breakdown card.

    ``connected`` reflects the integrations table (an actual connection),
    not merely the presence of a (possibly seed) social_stats row.
    ``provider_status`` is the registry status ('available' = has a connect
    form; 'coming_soon' = not wired yet → show a disabled tag, no button).
    Metric fields are null until the platform is connected + synced.
    """

    platform: str  # "instagram" | "facebook" | "linkedin" | "tiktok"
    connected: bool = False
    provider_status: str = "available"  # "available" | "coming_soon"
    followers: int | None = None
    posts_count: int | None = None
    engagement_rate: float | None = None


class SocialDataResponse(BaseModel):
    posts: int
    engagement: float
    followers: int
    by_platform: list[SocialPlatformMetric] = []
    top_content: list[dict]
    # Recent genuine comments (bare keyword triggers excluded).
    recent_comments: list[dict] = []
    generated_at: str


# ─── GET /social/overview — Greg-spec rebuild (deliverable 1) ──────────────


class SocialOverviewSummary(BaseModel):
    """Summary stat cards row — mirrors Greg's page's ig-s-* tiles."""

    posts_in_range: int = 0
    reels_count: int = 0
    carousels_count: int = 0
    total_watch_time_sec: int = 0
    total_views: int = 0
    total_reach: int = 0
    total_likes: int = 0
    total_saves: int = 0
    total_leads: int = 0
    per_keyword_leads: dict[str, int] = {}
    keywords: list[str] = []


class SocialOverviewPost(BaseModel):
    """One row in the Posts table."""

    id: str
    ig_media_id: str | None = None
    permalink: str | None = None
    media_type: str | None = None
    is_reel: bool = False
    caption: str | None = None
    posted_at: str | None = None
    likes_count: int | None = None
    comments_count: int | None = None
    views: int | None = None
    reach: int | None = None
    saves_count: int | None = None
    shares_count: int | None = None
    avg_watch_time_sec: int | None = None
    engagement_rate: float | None = None
    lead_counts: dict[str, int] = {}
    lead_total: int = 0


class SocialOverviewLeadDay(BaseModel):
    """One row in the Leads by Day table."""

    day: str
    total: int = 0
    per_keyword: dict[str, int] = {}


class SocialOverviewResponse(BaseModel):
    summary: SocialOverviewSummary
    posts: list[SocialOverviewPost]
    posts_total: int
    leads_by_day: list[SocialOverviewLeadDay]
    keywords: list[str] = []
    date_from: str | None = None
    date_to: str | None = None
    generated_at: str
    gaps: list[str] = []
