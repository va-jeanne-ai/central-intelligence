"""
Pydantic schemas for the appointments API contract.

Response shapes for:
  GET    /api/v1/appointments              — paginated list
  GET    /api/v1/appointments/stats        — KPIs, volume, status breakdown
  GET    /api/v1/appointments/{id}         — detail (+ linked lead/member name)
  PATCH  /api/v1/appointments/{id}         — partial update
  POST   /api/v1/appointments              — manual booking
  DELETE /api/v1/appointments/{id}         — soft-cancel (status='cancelled')

Mirrors schemas/members.py. Keep field names stable — frontend binds to them.
"""

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------


class AppointmentRecord(BaseModel):
    """A single appointment row in the paginated list."""

    id: str
    contact_name: str | None = None
    contact_email: str | None = None
    lead_id: str | None = None
    member_id: str | None = None
    status: str | None = None
    appointment_type: str | None = None
    scheduledAt: str | None = None  # noqa: N815 — camelCase for frontend binding
    source: str | None = None


class AppointmentListResponse(BaseModel):
    appointments: list[AppointmentRecord] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    per_page: int = 50


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


class AppointmentKpiResponse(BaseModel):
    total: int = 0
    upcoming_this_week: int = 0
    showed: int = 0
    no_show: int = 0
    show_rate: float = 0.0
    no_show_rate: float = 0.0


class AppointmentVolumePoint(BaseModel):
    label: str
    value: int


class StatusBreakdownItem(BaseModel):
    status: str
    count: int = 0
    percentage: float = 0.0


class AppointmentStatsResponse(BaseModel):
    kpis: AppointmentKpiResponse = Field(default_factory=AppointmentKpiResponse)
    appointment_volume: list[AppointmentVolumePoint] = Field(default_factory=list)
    status_breakdown: list[StatusBreakdownItem] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Detail
# ---------------------------------------------------------------------------


class AppointmentDetailResponse(BaseModel):
    id: str
    contact_name: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    lead_id: str | None = None
    lead_name: str | None = None
    member_id: str | None = None
    member_name: str | None = None
    status: str | None = None
    appointment_type: str | None = None
    scheduled_at: str | None = None
    end_at: str | None = None
    source: str | None = None
    external_id: str | None = None
    notes: str | None = None
    created_at: str | None = None


# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------


class CreateAppointmentRequest(BaseModel):
    """Manual booking. scheduled_at required; everything else optional."""

    scheduled_at: str = Field(..., min_length=1)
    end_at: str | None = None
    contact_name: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    appointment_type: str | None = None
    status: str | None = None  # defaults to 'booked' in the route
    lead_id: str | None = None
    member_id: str | None = None
    notes: str | None = None


class UpdateAppointmentRequest(BaseModel):
    """Partial update; only provided keys are written."""

    status: str | None = None
    scheduled_at: str | None = None
    end_at: str | None = None
    appointment_type: str | None = None
    notes: str | None = None


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------


class AppointmentHistoryEvent(BaseModel):
    id: str
    action: str
    before: dict | None = None
    after: dict | None = None
    author_id: str | None = None
    author_email: str | None = None
    created_at: str


class AppointmentHistoryResponse(BaseModel):
    events: list[AppointmentHistoryEvent] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Lead-detail card (GET /leads/{id}/appointments)
# ---------------------------------------------------------------------------


class LeadAppointmentsResponse(BaseModel):
    appointments: list[AppointmentRecord] = Field(default_factory=list)
    total: int = 0
