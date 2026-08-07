"""Pydantic schemas for GET /foresight/recommendations."""
from __future__ import annotations

from pydantic import BaseModel


class ForesightCard(BaseModel):
    id: str
    status: str
    confidence: str | None = None
    title: str
    department: str
    hindsight_headline: str
    hindsight_detail: str
    evidence_href: str
    evidence_label: str
    insight_text: str
    action_text: str
    lift_text: str
    hold_reason: str | None = None
    baseline_label: str
    baseline_rate: float
    baseline_low: float
    baseline_high: float
    variant_label: str
    variant_rate: float
    variant_low: float
    variant_high: float
    n_label: str
    computed_at: str


class ForesightRecommendationsResponse(BaseModel):
    published: list[ForesightCard] = []
    gated: list[ForesightCard] = []
    computed_at: str | None = None
