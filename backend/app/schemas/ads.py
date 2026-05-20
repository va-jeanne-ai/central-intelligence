"""Pydantic schemas for ads endpoints."""
from __future__ import annotations
from pydantic import BaseModel


class AdsAnalyzeRequest(BaseModel):
    platform: str | None = None
    date_from: str | None = None
    date_to: str | None = None


class AdsAnalyzeResponse(BaseModel):
    analysis: str
    ad_copy: str
    recommendations: list[str]
    data_used: dict


class AdsDataResponse(BaseModel):
    campaigns: int
    avg_roas: float
    total_spend: float
    top_ads: list[dict]
    generated_at: str
