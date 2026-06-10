"""
Pydantic schemas for the goals (accountability) API contract.

Response shapes for:
  GET    /api/v1/goals              — paginated list (cross-member)
  GET    /api/v1/goals/stats        — KPIs, funnel, status breakdown
  GET    /api/v1/goals/{id}         — detail (+ member name)
  GET    /api/v1/goals/{id}/history — audit timeline
  POST   /api/v1/goals              — create a goal for a member
  PATCH  /api/v1/goals/{id}         — update text/status/target_date
  DELETE /api/v1/goals/{id}         — soft-delete

Mirrors schemas/members.py. Keep field names stable — frontend binds to them.
"""

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------


class GoalRecord(BaseModel):
    id: str
    member_id: str | None = None
    member_name: str | None = None
    goal_text: str | None = None
    status: str | None = None
    stage: str | None = None
    targetDate: str | None = None  # noqa: N815 — camelCase for frontend binding
    created_at: str | None = None
    overdue: bool = False


class GoalListResponse(BaseModel):
    goals: list[GoalRecord] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    per_page: int = 50


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


class GoalKpiResponse(BaseModel):
    total: int = 0
    in_progress: int = 0
    completed: int = 0
    overdue: int = 0


class GoalFunnelStage(BaseModel):
    stage: str
    count: int = 0
    percentage: float = 0.0


class StatusBreakdownItem(BaseModel):
    status: str
    count: int = 0
    percentage: float = 0.0


class GoalStatsResponse(BaseModel):
    kpis: GoalKpiResponse = Field(default_factory=GoalKpiResponse)
    goal_funnel: list[GoalFunnelStage] = Field(default_factory=list)
    status_breakdown: list[StatusBreakdownItem] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Detail
# ---------------------------------------------------------------------------


class GoalDetailResponse(BaseModel):
    id: str
    member_id: str | None = None
    member_name: str | None = None
    goal_text: str | None = None
    status: str | None = None
    stage: str | None = None
    target_date: str | None = None
    created_at: str | None = None
    overdue: bool = False


# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------


class CreateGoalRequest(BaseModel):
    member_id: str = Field(..., min_length=1)
    goal_text: str = Field(..., min_length=1, max_length=2000)
    target_date: str | None = None
    status: str | None = None  # defaults to 'active' in the route
    stage: str | None = None   # defaults to 'todo' in the route


class UpdateGoalRequest(BaseModel):
    goal_text: str | None = None
    status: str | None = None
    stage: str | None = None
    target_date: str | None = None


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------


class GoalHistoryEvent(BaseModel):
    id: str
    action: str
    before: dict | None = None
    after: dict | None = None
    author_id: str | None = None
    author_email: str | None = None
    created_at: str


class GoalHistoryResponse(BaseModel):
    events: list[GoalHistoryEvent] = Field(default_factory=list)
