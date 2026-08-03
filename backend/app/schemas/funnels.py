"""Pydantic schemas for funnel webhook and stats endpoints.

Sprint 3b / M03-3
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class FunnelWebhookRequest(BaseModel):
    """Incoming funnel event from an external source."""

    funnel_id: str
    event_type: str  # e.g. "view", "click", "opt_in", "purchase"
    stage: str
    metadata: dict[str, Any] = {}


class FunnelWebhookResponse(BaseModel):
    """Acknowledgement returned after processing a funnel event."""

    received: bool
    funnel_id: str
    event_type: str
    stage: str
    processed_at: str


class FunnelStatsResponse(BaseModel):
    """Summary stats for a single funnel."""

    funnel_id: str
    stage: str
    event_count: int
    updated_at: str


class FunnelStageStats(BaseModel):
    """Stats for a single funnel stage."""

    funnel_id: str
    stage: str
    event_count: int
    conversion_rate: float | None = None
    updated_at: str


class FunnelDataResponse(BaseModel):
    """Aggregated funnel data returned by GET /funnels."""

    stages: list[FunnelStageStats] = []
    generated_at: str


# ─── GET /funnels/overview — real data rebuild from lead_journey (deliverable 3) ──


class FunnelOverviewStage(BaseModel):
    """One stage in the overall (unsliced) funnel — ordered leads ->
    registered -> watched -> booked appt -> discovery held -> closed."""

    stage: str
    label: str
    count: int = 0
    pct_of_leads: float = 0.0
    conversion_from_previous: float | None = None


class FunnelChannelRow(BaseModel):
    """One channel bucket's stage counts + lead->close rate."""

    channel: str
    platform: str | None = None
    reportable: bool = True
    leads: int = 0
    registered: int = 0
    watched: int = 0
    booked_appt: int = 0
    discovery_held: int = 0
    closed: int = 0
    lead_to_close_pct: float = 0.0


class FunnelOverviewResponse(BaseModel):
    """Response for GET /api/v1/funnels/overview."""

    overall: list[FunnelOverviewStage] = []
    by_channel: list[FunnelChannelRow] = []
    generated_at: str = ""
