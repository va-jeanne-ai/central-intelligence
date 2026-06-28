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

    total_leads: int = 0  # scoped to the selected entry-date range
    all_time_total: int = 0  # unscoped total, for the headline "Total Leads" card
    leads_this_week: int = 0
    conversion_rate: float = 0.0
    active_applications: int = 0
    avg_deal_value: float = 0.0  # avg amount_collected per closed sale (in range)


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


# ---------------------------------------------------------------------------
# Lead detail — GET /api/v1/leads/{id}
# ---------------------------------------------------------------------------


class LeadCallSummary(BaseModel):
    """Minimal call row for the lead detail activity timeline.

    ``processed_date`` is NULL while the background analyzer is still
    running — the frontend renders an "in-progress" row variant in that
    state and polls until the timestamp lands.
    """

    id: str
    date: str | None = None
    call_type: str | None = None
    insights_count: int = 0
    processed_date: str | None = None


class LeadGoalSummary(BaseModel):
    id: str
    goal_text: str | None = None
    status: str | None = None
    target_date: str | None = None


class LeadPainPointSummary(BaseModel):
    id: str
    text: str | None = None
    category: str | None = None


class LeadObjectionSummary(BaseModel):
    id: str
    objection_text: str | None = None
    resolution_offered: str | None = None


class NoteRow(BaseModel):
    """One staff journal entry rendered on the lead detail timeline."""

    id: str
    body: str
    author_id: str | None = None
    author_email: str | None = None
    created_at: str


class LeadDetailResponse(BaseModel):
    """Full payload for GET /api/v1/leads/{id}.

    `notes_raw` carries the immutable upstream provider payload (e.g. the
    GHL webhook JSON) as a string — the frontend parses it for the
    "Initial Submission" card. `staff_notes` is the editable journal.
    """

    id: str
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    status: str | None = None
    source: str | None = None
    score: int = 0
    external_id: str | None = None
    # When the lead entered the funnel upstream (WGR). May be null.
    entry_date: str | None = None
    created_at: str | None = None
    notes_raw: str | None = None
    calls: list[LeadCallSummary] = Field(default_factory=list)
    goals: list[LeadGoalSummary] = Field(default_factory=list)
    pain_points: list[LeadPainPointSummary] = Field(default_factory=list)
    objections: list[LeadObjectionSummary] = Field(default_factory=list)
    staff_notes: list[NoteRow] = Field(default_factory=list)


class UpdateLeadRequest(BaseModel):
    """Partial-update payload for PATCH /api/v1/leads/{id}.

    All fields optional; only provided keys are written. Status uses
    the API enum (e.g. "appointment_set"); the route translates to the
    DB form via `_API_TO_DB_STATUSES`.
    """

    name: str | None = None
    status: str | None = None
    phone: str | None = None


class CreateNoteRequest(BaseModel):
    """Payload for POST /api/v1/leads/{id}/notes."""

    body: str = Field(..., min_length=1, max_length=4000)


# ---------------------------------------------------------------------------
# Lead history — GET /api/v1/leads/{id}/history
# ---------------------------------------------------------------------------


class LeadHistoryEvent(BaseModel):
    """One row in the lead's audit-log timeline.

    `action` is a dotted string like ``lead.status_changed``. `before` /
    `after` carry the field-level diff as free-form JSON — the frontend
    renderer keys off `action` to know what fields to expect inside.
    The synthetic ``lead.created`` event lacks a real audit row id; we
    return a deterministic string ``"synthetic-created"`` so the
    frontend can still use it as a React key.
    """

    id: str
    action: str
    before: dict | None = None
    after: dict | None = None
    author_id: str | None = None
    author_email: str | None = None
    created_at: str


class LeadHistoryResponse(BaseModel):
    """Full history payload returned by GET /api/v1/leads/{id}/history.

    Events are ordered newest-first. A synthetic ``lead.created`` event
    is always appended as the oldest entry — so even leads that pre-date
    audit-log writes have a "Created" anchor row.
    """

    events: list[LeadHistoryEvent] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Lead email threads — GET /api/v1/leads/{id}/emails
# ---------------------------------------------------------------------------


class EmailAttachmentMeta(BaseModel):
    """Filename + size + mime for one attachment. No bytes."""

    filename: str
    size: int = 0
    mime_type: str | None = None


class EmailMessageRow(BaseModel):
    """One message in a thread. Body is plain-text only."""

    id: str
    from_address: str | None = None
    to_addresses: list[str] = Field(default_factory=list)
    cc_addresses: list[str] = Field(default_factory=list)
    subject: str | None = None
    body_text: str | None = None
    sent_at: str | None = None
    has_attachments: bool = False
    attachments_meta: list[EmailAttachmentMeta] = Field(default_factory=list)


class EmailThreadRow(BaseModel):
    """One Gmail thread linked to a lead, with its messages nested."""

    id: str
    subject: str | None = None
    last_message_at: str | None = None
    message_count: int = 0
    messages: list[EmailMessageRow] = Field(default_factory=list)


class EmailThreadsResponse(BaseModel):
    """Full payload for ``GET /api/v1/leads/{id}/emails``.

    Threads are ordered newest-first by ``last_message_at`` so the lead
    detail page can render them in the order staff expect.
    """

    threads: list[EmailThreadRow] = Field(default_factory=list)


class DocumentRow(BaseModel):
    """One Drive file shared with this lead's email address."""

    id: str
    name: str | None = None
    mime_type: str | None = None
    owner_email: str | None = None
    modified_time: str | None = None
    web_view_link: str | None = None
    parent_folder_name: str | None = None
    size_bytes: int | None = None


class DocumentsResponse(BaseModel):
    """Payload for ``GET /api/v1/leads/{id}/documents``.

    Files are ordered newest-first by ``modified_time``. Same Drive
    file appearing in two users' mailboxes is dedup'd here on
    ``provider_file_id``.
    """

    files: list[DocumentRow] = Field(default_factory=list)


class ConversationMessageRow(BaseModel):
    """One message in a lead's omni-channel conversation log.

    Sourced from ``sales_activities`` (SMS / Instagram + Facebook DMs /
    email / calls). ``direction`` is derived from the activity_type
    suffix (``inbound`` / ``outbound`` / ``unknown``).
    """

    id: str
    channel: str | None = None  # sms | instagram | facebook | email | phone
    activity_type: str | None = None  # e.g. sms_outbound, social_dm_inbound
    direction: str = "unknown"  # inbound | outbound | unknown
    body: str | None = None
    occurred_at: str | None = None
    duration_seconds: int | None = None


class ConversationsResponse(BaseModel):
    """Payload for ``GET /api/v1/leads/{id}/conversations``.

    Messages are ordered oldest-first by ``occurred_at`` so reading
    top-to-bottom matches the real conversation flow. ``channels`` is the
    distinct set present, for filter chips in the UI.
    """

    messages: list[ConversationMessageRow] = Field(default_factory=list)
    total: int = 0
    channels: list[str] = Field(default_factory=list)


class LeadTagRow(BaseModel):
    """One tag on a lead, with how many times it appears across their calls."""

    tag: str
    count: int = 1


class LeadTagsResponse(BaseModel):
    """Payload for ``GET /api/v1/leads/{id}/tags``.

    Tags are aggregated across the lead's calls' insights
    (lead → calls → insights → insight_tags), distinct tags ordered by
    frequency desc. Empty when the lead has no tagged calls.
    """

    tags: list[LeadTagRow] = Field(default_factory=list)
    total: int = 0
