"""
Pydantic schemas for the members API contract.

Response shapes for:
  GET    /api/v1/members              — paginated member list
  GET    /api/v1/members/stats        — KPIs, enrollment volume, status, goal funnel
  GET    /api/v1/members/{id}         — full detail (calls/goals/wins/pain/notes)
  GET    /api/v1/members/{id}/history — audit-log timeline
  PATCH  /api/v1/members/{id}         — partial update
  POST   /api/v1/members/{id}/notes   — add staff note
  DELETE /api/v1/members/{id}/notes/{note_id}

Mirrors schemas/leads.py. Keep field names stable — frontend components bind
directly against them.
"""

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Member list
# ---------------------------------------------------------------------------


class MemberRecord(BaseModel):
    """A single member row returned in the paginated list."""

    id: str
    name: str | None = None
    email: str | None = None
    status: str | None = None
    coach_id: str | None = None
    enrollmentDate: str | None = None  # noqa: N815 — camelCase for frontend binding


class MemberListResponse(BaseModel):
    """Paginated list of members."""

    members: list[MemberRecord] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    per_page: int = 50


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


class MemberKpiResponse(BaseModel):
    """Top-level member KPIs."""

    total_members: int = 0
    members_this_week: int = 0
    active_members: int = 0
    goals_completed: int = 0


class EnrollmentVolumePoint(BaseModel):
    """One weekly bucket for the enrollment volume chart."""

    label: str
    value: int


class StatusBreakdownItem(BaseModel):
    """Share of members in a single status."""

    status: str
    count: int = 0
    percentage: float = 0.0


class GoalFunnelStage(BaseModel):
    """One horizontal bar in the goal funnel visualisation."""

    stage: str
    count: int = 0
    percentage: float = 0.0


class MemberStatsResponse(BaseModel):
    """Full stats payload returned by GET /api/v1/members/stats."""

    kpis: MemberKpiResponse = Field(default_factory=MemberKpiResponse)
    enrollment_volume: list[EnrollmentVolumePoint] = Field(default_factory=list)
    status_breakdown: list[StatusBreakdownItem] = Field(default_factory=list)
    goal_funnel: list[GoalFunnelStage] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Member detail
# ---------------------------------------------------------------------------


class MemberCallSummary(BaseModel):
    """Minimal call row for the member detail timeline."""

    id: str
    date: str | None = None
    call_type: str | None = None
    insights_count: int = 0
    processed_date: str | None = None


class MemberGoalSummary(BaseModel):
    id: str
    goal_text: str | None = None
    status: str | None = None
    target_date: str | None = None


class MemberWinSummary(BaseModel):
    id: str
    win_text: str | None = None
    impact_area: str | None = None
    win_date: str | None = None


class MemberPainPointSummary(BaseModel):
    id: str
    text: str | None = None
    category: str | None = None


class MemberNoteRow(BaseModel):
    """One staff journal entry rendered on the member detail timeline."""

    id: str
    body: str
    author_id: str | None = None
    author_email: str | None = None
    created_at: str


class MemberDetailResponse(BaseModel):
    """Full payload for GET /api/v1/members/{id}."""

    id: str
    name: str | None = None
    email: str | None = None
    status: str | None = None
    coach_id: str | None = None
    enrollment_date: str | None = None
    created_at: str | None = None
    calls: list[MemberCallSummary] = Field(default_factory=list)
    goals: list[MemberGoalSummary] = Field(default_factory=list)
    wins: list[MemberWinSummary] = Field(default_factory=list)
    pain_points: list[MemberPainPointSummary] = Field(default_factory=list)
    staff_notes: list[MemberNoteRow] = Field(default_factory=list)


class CreateMemberRequest(BaseModel):
    """Payload for POST /api/v1/members.

    ``name`` is required; everything else is optional. ``status`` defaults to
    "active" when omitted. ``enrollment_date`` is an ISO date/datetime string.
    """

    name: str = Field(..., min_length=1, max_length=255)
    email: str | None = None
    status: str | None = None
    coach_id: str | None = None
    enrollment_date: str | None = None


class UpdateMemberRequest(BaseModel):
    """Partial-update payload for PATCH /api/v1/members/{id}.

    All fields optional; only provided keys are written.
    """

    name: str | None = None
    email: str | None = None
    status: str | None = None
    coach_id: str | None = None


class CreateMemberNoteRequest(BaseModel):
    """Payload for POST /api/v1/members/{id}/notes."""

    body: str = Field(..., min_length=1, max_length=4000)


# ---------------------------------------------------------------------------
# Member history
# ---------------------------------------------------------------------------


class MemberHistoryEvent(BaseModel):
    """One row in the member's audit-log timeline.

    ``action`` is a dotted string like ``member.status_changed``. ``before`` /
    ``after`` carry the field-level diff as free-form JSON.
    """

    id: str
    action: str
    before: dict | None = None
    after: dict | None = None
    author_id: str | None = None
    author_email: str | None = None
    created_at: str


class MemberHistoryResponse(BaseModel):
    """Full history payload. Events newest-first; a synthetic
    ``member.created`` event anchors the oldest entry."""

    events: list[MemberHistoryEvent] = Field(default_factory=list)
