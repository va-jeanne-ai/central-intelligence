"""
Pydantic schemas for the leads API contract.

These models define the public response shapes for:
  GET /api/v1/leads          — paginated lead list
  GET /api/v1/leads/stats    — KPIs, lead volume chart, source breakdown, funnel

Status mapping (DB → API):
  appointment-set  →  appointment_set
  sale             →  closed_won
  lost             →  closed_lost
  new / contacted / qualified / stale  →  unchanged

Keep field names stable — frontend components bind directly against them.
"""

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Lead list
# ---------------------------------------------------------------------------


class LeadRecord(BaseModel):
    """A single lead row returned in the paginated list."""

    id: str
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    status: str | None = None
    source: str | None = None
    notes: str | None = None
    createdAt: str | None = None  # noqa: N815 — camelCase to match frontend Lead type
    score: int = 0


class LeadListResponse(BaseModel):
    """Paginated list of leads."""

    leads: list[LeadRecord] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    per_page: int = 50


# ---------------------------------------------------------------------------
# Stats — KPIs
# ---------------------------------------------------------------------------


class LeadsKpiResponse(BaseModel):
    """Top-level lead KPIs."""

    total_leads: int = 0
    leads_this_week: int = 0
    conversion_rate: float = 0.0
    active_applications: int = 0


# ---------------------------------------------------------------------------
# Stats — Lead volume chart
# ---------------------------------------------------------------------------


class LeadVolumePoint(BaseModel):
    """One weekly bucket for the lead volume bar/line chart."""

    label: str
    value: int


# ---------------------------------------------------------------------------
# Stats — Source breakdown
# ---------------------------------------------------------------------------


class SourceBreakdownItem(BaseModel):
    """Share of leads from a single acquisition source."""

    source: str
    count: int = 0
    percentage: float = 0.0


# ---------------------------------------------------------------------------
# Stats — Sales funnel
# ---------------------------------------------------------------------------


class FunnelStage(BaseModel):
    """One horizontal bar in the sales funnel visualisation."""

    stage: str
    count: int = 0
    percentage: float = 0.0


# ---------------------------------------------------------------------------
# Composite stats response
# ---------------------------------------------------------------------------


class LeadsStatsResponse(BaseModel):
    """Full stats payload returned by GET /api/v1/leads/stats."""

    kpis: LeadsKpiResponse = Field(default_factory=LeadsKpiResponse)
    lead_volume: list[LeadVolumePoint] = Field(default_factory=list)
    source_breakdown: list[SourceBreakdownItem] = Field(default_factory=list)
    funnel: list[FunnelStage] = Field(default_factory=list)
