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


class EmailCampaignRow(BaseModel):
    """One row in the recent-campaigns list on /marketing/email."""

    id: str
    name: str
    subject: str | None = None
    campaign_type: str | None = None
    status: str
    sent_at: str | None = None
    recipients_count: int = 0
    open_count: int = 0
    click_count: int = 0
    open_rate: float | None = None
    click_rate: float | None = None
    # Provenance: which integration produced this row.
    source: str | None = None
    external_id: str | None = None


class EmailDataResponse(BaseModel):
    campaigns: int
    avg_open_rate: float
    avg_click_rate: float
    generated_at: str
    # 20 most-recent sent campaigns with their per-row metrics + source badge.
    recent_campaigns: list[EmailCampaignRow] = []
