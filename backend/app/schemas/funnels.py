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
