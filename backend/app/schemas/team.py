"""Schemas for the Members page sourced from the sales team (sales_reps).

The Members page is the team roster: each "member" is a rep the leads talk to.
These power the directory cards, the KPI tiles, and the selected-rep detail
panel (performance, recent EOD reports, call history).
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class TeamStats(BaseModel):
    """KPI tiles for the Members (team) page."""

    total_members: int = 0
    active_members: int = 0
    # Reps on probation (or otherwise not active) — the "At-Risk" tile.
    at_risk_members: int = 0
    calls_this_month: int = 0
    # Month-over-month delta for the active count (this month − last month hires).
    active_delta: int = 0


class TeamMemberRow(BaseModel):
    """One rep card in the Member Directory."""

    rep_id: str
    name: str
    email: str | None = None
    role: str | None = None
    status: str  # active | probation | terminated | …
    hired_at: str | None = None
    capabilities: list[str] = Field(default_factory=list)
    calls_count: int = 0  # total calls this rep ran (by call_owner match)


class TeamListResponse(BaseModel):
    members: list[TeamMemberRow] = Field(default_factory=list)
    total: int = 0


class PerformanceBar(BaseModel):
    """One labeled progress bar on the rep detail panel."""

    label: str
    percent: float  # 0–100
    detail: str | None = None  # e.g. "avg 2.4 / 10 over 56 calls"


class SubmissionRow(BaseModel):
    """An EOD report — the rep's "Recent Submissions"."""

    label: str
    date: str | None = None
    delivered: bool = False  # whether it was delivered (e.g. to Slack)


class CallHistoryRow(BaseModel):
    """One call in the rep's Call History."""

    call_id: str
    call_type: str | None = None
    call_result: str | None = None
    date: str | None = None


class TeamMemberDetail(BaseModel):
    """The selected-rep panel: header facts + performance + submissions + calls."""

    rep_id: str
    name: str
    email: str | None = None
    role: str | None = None
    status: str
    hired_at: str | None = None
    days_active: int | None = None
    capabilities: list[str] = Field(default_factory=list)
    performance: list[PerformanceBar] = Field(default_factory=list)
    recent_submissions: list[SubmissionRow] = Field(default_factory=list)
    call_history: list[CallHistoryRow] = Field(default_factory=list)
