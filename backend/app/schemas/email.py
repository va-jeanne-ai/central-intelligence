"""Pydantic schemas for email endpoints."""

from __future__ import annotations

from pydantic import BaseModel


class EmailAnalyzeRequest(BaseModel):
    campaign_type: str | None = None
    date_from: str | None = None
    date_to: str | None = None


class EmailDraftRequest(BaseModel):
    subject: str
    audience: str | None = None
    tone: str | None = None


class EmailAnalyzeResponse(BaseModel):
    analysis: str
    recommendations: list[str]
    metrics_summary: dict


class EmailDraftResponse(BaseModel):
    subject: str
    body: str
    cta: str | None = None


class EmailDataResponse(BaseModel):
    campaigns: int
    avg_open_rate: float
    avg_click_rate: float
    generated_at: str
