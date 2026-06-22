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
