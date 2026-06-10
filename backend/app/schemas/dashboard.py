"""
Pydantic schemas for the dashboard stats API contract.

These models define the public response shape for GET /api/v1/dashboard/stats.
Keep field names stable — frontend components bind directly against them.
"""

from typing import Any

from pydantic import BaseModel, Field


class StatCard(BaseModel):
    """A single labelled metric tile for a department panel."""

    label: str
    value: str
    sub: str = ""


class DepartmentStatsResponse(BaseModel):
    """Stats for one business department."""

    stats: list[StatCard] = Field(default_factory=list)


class KpiResponse(BaseModel):
    """Top-level business KPIs shown in the hero row."""

    total_leads: int = 0
    leads_this_week: int = 0
    calls_this_week: int = 0
    active_members: int = 0


class LeadVolumePoint(BaseModel):
    """A single week bucket for the lead volume sparkline / bar chart."""

    label: str
    value: int


class RecentLead(BaseModel):
    """Minimal lead record for the recent-activity feed."""

    id: str
    name: str | None = None
    status: str | None = None
    source: str | None = None
    created_at: str | None = None


class DashboardStatsResponse(BaseModel):
    """Full dashboard stats payload returned by GET /api/v1/dashboard/stats."""

    departments: dict[str, DepartmentStatsResponse] = Field(default_factory=dict)
    kpis: KpiResponse = Field(default_factory=KpiResponse)
    lead_volume: list[LeadVolumePoint] = Field(default_factory=list)
    recent_leads: list[RecentLead] = Field(default_factory=list)


class RecommendationItem(BaseModel):
    """A single AI-generated business recommendation."""

    id: str
    icon: str
    text: str


class RecommendationsResponse(BaseModel):
    """Payload returned by GET /api/v1/dashboard/recommendations."""

    recommendations: list[RecommendationItem]
    generated_at: str
    cached: bool = False


class WeeklyFocusItem(BaseModel):
    """A single cross-department focus priority for the week."""

    title: str
    detail: str


class WeeklyFocusResponse(BaseModel):
    """Payload returned by GET /api/v1/dashboard/weekly-focus.

    A synthesized cross-department answer to "what should we focus on this
    week?" produced by Central Intelligence delegating to the three Directors.
    """

    focus: list[WeeklyFocusItem]
    summary: str = ""
    generated_at: str
    cached: bool = False


class ScheduleBriefItem(BaseModel):
    """A single calendar event in the dashboard schedule brief."""

    title: str
    start: str  # ISO 8601
    end: str | None = None
    is_all_day: bool = False
    location: str | None = None
    attendees_count: int = 0
    status: str | None = None  # confirmed | tentative | cancelled


class ScheduleBriefResponse(BaseModel):
    """Payload returned by GET /api/v1/dashboard/schedule-brief.

    The logged-in user's calendar events for a given day window (the
    frontend passes its local day bounds so 'today' matches the user's
    wall clock). Deterministic — read straight from google_calendar_events,
    no AI.
    """

    items: list[ScheduleBriefItem]
    summary: str = ""
    event_count: int = 0
    calendar_connected: bool = False
    generated_at: str
