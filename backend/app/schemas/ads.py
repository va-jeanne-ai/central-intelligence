"""Pydantic schemas for ads endpoints."""
from __future__ import annotations
from pydantic import BaseModel, Field


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


# ─── GET /ads/overview — real data rebuild (deliverable 4) ─────────────────


class AdsOverviewKpis(BaseModel):
    """Top-level KPI tiles for the Ads page."""

    total_spend: float = 0.0
    total_impressions: int = 0
    total_leads: int = 0
    total_booked_calls: int = 0
    avg_cost_per_lead: float = 0.0
    avg_ctr: float = 0.0
    active_campaigns: int = 0
    total_campaigns: int = 0
    total_ads: int = 0


class AdsOverviewCampaign(BaseModel):
    """One row in the Campaigns table — identity + performance rollup."""

    campaign_id: str
    name: str | None = None
    status: str | None = None
    objective: str | None = None
    campaign_type: str | None = None
    daily_budget: float | None = None
    lifetime_budget: float | None = None
    start_date: str | None = None
    end_date: str | None = None
    ads_count: int = 0
    spend: float = 0.0
    leads: int = 0
    booked_calls: int = 0
    cost_per_lead: float = 0.0


class AdsOverviewTopAd(BaseModel):
    """One row in the Top Ads table — identity + latest/rollup performance."""

    ad_id: str
    name: str | None = None
    campaign_name: str | None = None
    ad_format: str | None = None
    status: str | None = None
    hook_text: str | None = None
    kpi_status: str | None = None
    spend: float = 0.0
    leads: int = 0
    cost_per_lead: float = 0.0
    ctr: float | None = None
    launched_date: str | None = None
    kill_date: str | None = None
    kill_reason: str | None = None


class AdsOverviewResponse(BaseModel):
    kpis: AdsOverviewKpis = Field(default_factory=AdsOverviewKpis)
    campaigns: list[AdsOverviewCampaign] = Field(default_factory=list)
    top_ads: list[AdsOverviewTopAd] = Field(default_factory=list)
