"""
Pydantic schemas for the Tech SOS (support ticket) API contract.

Response shapes for:
  GET    /api/v1/tech-sos              — paginated list
  GET    /api/v1/tech-sos/stats        — KPIs, category + status breakdown, volume
  GET    /api/v1/tech-sos/{id}         — detail (+ member name)
  GET    /api/v1/tech-sos/{id}/history — audit timeline
  POST   /api/v1/tech-sos              — staff create (member dropdown)
  POST   /api/v1/tech-sos/submit       — public member submit (no auth)
  PATCH  /api/v1/tech-sos/{id}         — update status/category/priority/resolution
  DELETE /api/v1/tech-sos/{id}         — soft-delete

Mirrors schemas/appointments.py. Keep field names stable — frontend binds to them.
"""

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------


class TicketRecord(BaseModel):
    id: str
    member_id: str | None = None
    member_name: str | None = None
    contact_name: str | None = None
    contact_email: str | None = None
    subject: str | None = None
    category: str | None = None
    status: str | None = None
    priority: str | None = None
    source: str | None = None
    createdAt: str | None = None  # noqa: N815 — camelCase for frontend binding
    resolvedAt: str | None = None  # noqa: N815


class TicketListResponse(BaseModel):
    tickets: list[TicketRecord] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    per_page: int = 50


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


class TicketKpiResponse(BaseModel):
    total: int = 0
    open: int = 0
    in_progress: int = 0
    resolved: int = 0
    avg_resolution_hours: float = 0.0


class CategoryBreakdownItem(BaseModel):
    category: str
    count: int = 0
    percentage: float = 0.0


class StatusBreakdownItem(BaseModel):
    status: str
    count: int = 0
    percentage: float = 0.0


class TicketVolumePoint(BaseModel):
    label: str
    value: int


class TicketStatsResponse(BaseModel):
    kpis: TicketKpiResponse = Field(default_factory=TicketKpiResponse)
    category_breakdown: list[CategoryBreakdownItem] = Field(default_factory=list)
    status_breakdown: list[StatusBreakdownItem] = Field(default_factory=list)
    ticket_volume: list[TicketVolumePoint] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Detail
# ---------------------------------------------------------------------------


class TicketDetailResponse(BaseModel):
    id: str
    member_id: str | None = None
    member_name: str | None = None
    contact_name: str | None = None
    contact_email: str | None = None
    subject: str | None = None
    description: str | None = None
    category: str | None = None
    status: str | None = None
    priority: str | None = None
    resolution: str | None = None
    source: str | None = None
    created_at: str | None = None
    resolved_at: str | None = None


# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------


class CreateTicketRequest(BaseModel):
    """Staff create — member optional (logged on a member's behalf)."""

    subject: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    member_id: str | None = None
    contact_name: str | None = None
    contact_email: str | None = None
    category: str | None = None
    priority: str | None = None  # defaults 'normal'


class SubmitTicketRequest(BaseModel):
    """Public member submit — no member_id (best-effort linked by email)."""

    subject: str = Field(..., min_length=1, max_length=255)
    description: str = Field(..., min_length=1)
    contact_name: str | None = None
    contact_email: str | None = None
    category: str | None = None


class UpdateTicketRequest(BaseModel):
    subject: str | None = None
    description: str | None = None
    category: str | None = None
    status: str | None = None
    priority: str | None = None
    resolution: str | None = None


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------


class TicketHistoryEvent(BaseModel):
    id: str
    action: str
    before: dict | None = None
    after: dict | None = None
    author_id: str | None = None
    author_email: str | None = None
    created_at: str


class TicketHistoryResponse(BaseModel):
    events: list[TicketHistoryEvent] = Field(default_factory=list)


# Minimal ack for the public submit endpoint (don't leak internal state).
class SubmitTicketResponse(BaseModel):
    id: str
    status: str = "open"
    message: str = "Ticket submitted"
