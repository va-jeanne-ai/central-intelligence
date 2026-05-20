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


class SocialDataResponse(BaseModel):
    posts: int
    engagement: float
    followers: int
    top_content: list[dict]
    generated_at: str
