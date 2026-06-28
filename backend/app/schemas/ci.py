"""Pydantic schemas for Central Intelligence (CI) webhook endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------

class PaginationMeta(BaseModel):
    page: int
    limit: int
    total: int
    totalPages: int
    hasNextPage: bool
    hasPreviousPage: bool


# ---------------------------------------------------------------------------
# Transcript endpoints
# ---------------------------------------------------------------------------

class UploadTranscriptRequest(BaseModel):
    file_content: str = Field(..., description="base64-encoded file content")
    file_name: str = Field(..., description="Original filename")
    file_type: Literal["txt", "pdf", "docx"]
    call_owner: str | None = None
    call_type: Literal[
        "Sales", "Discovery", "Coaching", "Accountability", "Support"
    ] | None = None
    # Optional entity links — a coaching transcript attaches to a member,
    # a sales transcript to a lead. Both optional/independent.
    lead_id: str | None = None
    member_id: str | None = None


class UploadTranscriptResponse(BaseModel):
    call_id: str
    status: str
    message: str


class ProcessTranscriptRequest(BaseModel):
    call_id: str = Field(..., description="ID of call to process")


class ProcessTranscriptResponse(BaseModel):
    call_id: str
    insights_count: int
    content_ideas_count: int
    tags_count: int
    status: str


# ---------------------------------------------------------------------------
# Calls
# ---------------------------------------------------------------------------

class CallSummary(BaseModel):
    call_id: str
    date: datetime | None = None
    call_type: str | None = None
    call_result: str | None = None
    # The rep/CSR who conducted the call (NOT the prospect).
    call_owner: str | None = None
    # The lead/prospect on the call (the person they're talking to). Resolved
    # from calls.lead_id → leads; null when the call isn't linked to a lead.
    lead_id: str | None = None
    lead_name: str | None = None
    transcript_quality: str | None = None
    processed_date: datetime | None = None
    insights_count: int = 0
    # Pain-type insights (Pain / Objection / Belief) — drives the "N pain
    # points" badge on the Sales Calls card.
    pain_points_count: int = 0
    content_ideas_count: int = 0
    # Duration (minutes) + a short transcript excerpt for the card preview.
    duration_minutes: float | None = None
    transcript_excerpt: str | None = None
    # Provenance: 'wgr' = mirrored from the client DB; else CI-analyzed.
    source: str | None = None
    # When CI ingested the row ("Date Added"), distinct from `date` (call date).
    created_at: datetime | None = None


class CallListResponse(BaseModel):
    data: list[CallSummary]
    pagination: PaginationMeta


class CallStats(BaseModel):
    """KPI tiles for the Sales Calls page."""

    total_calls: int = 0
    calls_this_month: int = 0
    # "Pain Points Found" — insights of type Pain / Objection / Belief.
    pain_points_found: int = 0
    content_ideas: int = 0
    # Month-over-month delta for the "This Month" tile.
    this_month_delta: int = 0


class TimeBucket(BaseModel):
    """One month's call count for the analytics trend chart."""

    label: str  # e.g. "Jan", "Feb"
    value: int = 0


class LabeledCount(BaseModel):
    """A label + count, for result breakdown and top-signal charts."""

    label: str
    count: int = 0


class CallAnalytics(BaseModel):
    """Data for the Sales Calls Analytics page."""

    calls_by_month: list[TimeBucket] = Field(default_factory=list)
    result_breakdown: list[LabeledCount] = Field(default_factory=list)
    top_pain_points: list[LabeledCount] = Field(default_factory=list)
    top_call_owners: list[LabeledCount] = Field(default_factory=list)


class CallFacets(BaseModel):
    """Distinct filterable values present in the calls table.

    Drives the calls-table filter dropdowns so the available options can
    never drift from the data the WGR sync / CI uploads produce.
    """

    call_type: list[str]
    call_result: list[str]


class CallDetail(BaseModel):
    call_id: str
    date: datetime | None = None
    call_type: str | None = None
    call_result: str | None = None
    call_owner: str | None = None
    transcript_quality: str | None = None
    processed_date: datetime | None = None
    transcript: str | None = None
    summary: str | None = None
    created_at: datetime | None = None
    # Provenance: 'wgr' = mirrored from the client DB; else CI-analyzed.
    source: str | None = None


class InsightBrief(BaseModel):
    insight_id: str
    insight_type: str | None = None
    signal_family: str | None = None
    signal: str | None = None
    raw_quote: str | None = None


# Inline-edit payloads for the call detail page.


class UpdateCallRequest(BaseModel):
    """Partial-update payload for PATCH /ci/calls/{call_id}.

    All fields optional — only provided keys are written. ``summary`` set to
    an empty string clears the column; omitting it leaves it untouched.
    """

    summary: str | None = None
    call_type: str | None = None
    call_owner: str | None = None
    call_result: str | None = None
    # Connect (or re-connect) the call to a lead. UUID string; "" clears the
    # link. Resolved/validated in the route (it's a UUID FK, not a plain str).
    lead_id: str | None = None


class UpdateInsightRequest(BaseModel):
    """Partial-update payload for PATCH /ci/insights/{insight_id}.

    Only the four fields shown on the call detail page are editable here.
    Deeper insight fields can be edited via the standalone insight detail
    page when that surface exists.
    """

    signal: str | None = None
    signal_family: str | None = None
    insight_type: str | None = None
    raw_quote: str | None = None


class ContentIdeaBrief(BaseModel):
    content_id: str
    content_format: str | None = None
    status: str | None = None
    priority_level: str | None = None
    idea_score: float | None = None


class ContentIdeaDetail(BaseModel):
    """Full content-idea brief — every field the analyzer generates from a call.

    Surfaced on the call-detail page so the idea reads as a shootable brief
    (hook, premise, CTA, source quote) rather than a 'Reel · High' label.
    """

    content_id: str
    insight_id: str | None = None
    call_id: str | None = None
    source: str | None = None
    market_audience: str | None = None
    content_format: str | None = None
    content_angle: str | None = None
    trigger_insight: str | None = None
    raw_quote: str | None = None
    content_premise: str | None = None
    hook_opening_line: str | None = None
    teaching_point: str | None = None
    cta_idea: str | None = None
    priority_level: str | None = None
    best_platform: str | None = None
    repurpose_opportunities: str | None = None
    idea_score: float | None = None
    status: str | None = None
    created_at: datetime | None = None


class CallDetailResponse(BaseModel):
    call: CallDetail
    # Full insight payload (every analysis field) so the call-detail page can
    # surface the deep marketing/psychology data, not just the 4-field brief.
    # InsightDetail is defined further down — forward ref resolved via
    # model_rebuild() after its definition.
    insights: list["InsightDetail"]
    # Full content-idea brief (hook, premise, CTA, etc.), not just format/status.
    content_ideas: list[ContentIdeaDetail]


# ---------------------------------------------------------------------------
# Insights
# ---------------------------------------------------------------------------

class InsightSummary(BaseModel):
    insight_id: str
    call_id: str | None = None
    speaker_name: str | None = None
    insight_type: str | None = None
    signal_family: str | None = None
    signal: str | None = None
    signal_strength: str | None = None
    raw_quote: str | None = None
    marketing_translation: str | None = None
    hook_angle_example: str | None = None
    best_use_case: str | None = None
    quote_confidence: str | None = None
    frequency_score: int = 1


class InsightListResponse(BaseModel):
    data: list[InsightSummary]
    pagination: PaginationMeta


class InsightFacets(BaseModel):
    """Distinct filterable values actually present in the insights table.

    Drives the insights-page filter dropdowns so the available options can
    never drift from the data the analyzer/WGR sync produce.
    """

    insight_type: list[str]
    signal_family: list[str]
    signal_strength: list[str]


class InsightDetail(BaseModel):
    insight_id: str
    call_id: str | None = None
    speaker_name: str | None = None
    insight_type: str | None = None
    signal_family: str | None = None
    signal: str | None = None
    signal_strength: str | None = None
    pain_layer: str | None = None
    raw_quote: str | None = None
    what_they_say: str | None = None
    the_real_problem: str | None = None
    emotional_driver: str | None = None
    core_fear_revealed: str | None = None
    false_belief_revealed: str | None = None
    structural_obstacle: str | None = None
    identity_signal: str | None = None
    buying_trigger: str | None = None
    objection_created: str | None = None
    marketing_translation: str | None = None
    hook_angle_example: str | None = None
    best_use_case: str | None = None
    quote_confidence: str | None = None
    frequency_score: int = 1
    created_at: datetime | None = None


class InsightDetailResponse(BaseModel):
    insight: InsightDetail
    tags: list[str]
    related_content_ideas: list[ContentIdeaBrief]


# CallDetailResponse references InsightDetail (defined above) via a forward
# ref; resolve it now that InsightDetail exists.
CallDetailResponse.model_rebuild()


# ---------------------------------------------------------------------------
# Content Ideas
# ---------------------------------------------------------------------------

class ContentIdeaSummary(BaseModel):
    content_id: str
    insight_id: str | None = None
    call_id: str | None = None
    content_format: str | None = None
    # `content_premise` was originally a Text column on ContentIdea but not in
    # the summary schema. Surfaced here so the UI can show the idea's title /
    # description without a separate detail fetch.
    content_premise: str | None = None
    status: str | None = None
    priority_level: str | None = None
    idea_score: float | None = None
    created_at: datetime | None = None


class ContentIdeaListResponse(BaseModel):
    data: list[ContentIdeaSummary]
    pagination: PaginationMeta


class UpdateContentIdeaRequest(BaseModel):
    # EC-08: Extended status set covering new→in_progress→used→archived lifecycle
    status: Literal["new", "in_progress", "used", "Idea", "Scheduled", "Written", "Sent", "Archived", "archived"]
    notes: str | None = None


class UpdateContentIdeaResponse(BaseModel):
    content_id: str
    status: str
    updated_at: datetime | None = None


class CreateContentIdeaRequest(BaseModel):
    """Payload for POST /api/v1/ci/content-ideas — manual idea creation from the UI.

    The frontend sends a small {title, platform, status} payload; the backend
    maps `title` → `content_premise` and `platform` → `content_format`. Status
    defaults to "Idea" (the start of the lifecycle); any of the existing
    UpdateContentIdeaRequest literals are accepted.
    """

    title: str
    platform: str | None = None
    status: Literal["new", "in_progress", "used", "Idea", "Scheduled", "Written", "Sent", "Archived", "archived"] = "Idea"


# ---------------------------------------------------------------------------
# F19: Call analyzer trigger + paste-transcript schemas
# ---------------------------------------------------------------------------


class AnalyzeCallResponse(BaseModel):
    """Response from POST /api/v1/ci/calls/{call_id}/analyze.

    The analyzer runs asynchronously (Celery), so this just acknowledges
    enqueueing. Poll the call's insights via GET /ci/calls/{id} or
    GET /ci/insights?call_id=... to see results once the worker finishes.
    """

    call_id: str
    task_id: str
    status: str  # "queued"
    message: str


class CreateCallFromTranscriptRequest(BaseModel):
    """Payload for POST /api/v1/ci/calls — create a Call row by pasting a transcript.

    Skips Whisper entirely. Used for testing the analyzer pipeline without
    needing audio, and for ingesting transcripts that came from a third-party
    source. The Celery analyzer is auto-chained to fire on the new Call.
    """

    transcript_text: str
    call_type: str | None = None  # sales_call | coaching | appointment
    call_owner: str | None = None
    speaker_hints: str | None = None  # optional inline hints for the analyzer
    # Optional FK links — present if the caller knows who the transcript is about.
    member_id: str | None = None
    lead_id: str | None = None


class CreateCallFromTranscriptResponse(BaseModel):
    call_id: str
    analyzer_task_id: str | None = None
    status: str  # "created" | "queued_for_analysis"


# ---------------------------------------------------------------------------
# Market Signals
# ---------------------------------------------------------------------------

class MarketSignalItem(BaseModel):
    signal_family: str | None = None
    signal: str | None = None
    insight_type: str | None = None
    total_mentions: int = 0
    last_30_days: int = 0
    last_7_days: int = 0
    example_quote: str | None = None
    best_marketing_angle: str | None = None


class MarketSignalListResponse(BaseModel):
    data: list[MarketSignalItem]


class MarketSignalFacets(BaseModel):
    """Distinct filterable values present in the market_signals table.

    Drives the market-signals page filter dropdowns so the available
    options can never drift from the aggregated data.
    """

    insight_type: list[str]
    signal_family: list[str]


# ---------------------------------------------------------------------------
# Tags
# ---------------------------------------------------------------------------

class TagItem(BaseModel):
    tag: str
    tag_type: str | None = None
    synonyms: list[str] | None = None
    notes: str | None = None


class TagListResponse(BaseModel):
    data: list[TagItem]


# ---------------------------------------------------------------------------
# Offers
# ---------------------------------------------------------------------------

class OfferItem(BaseModel):
    offer_id: str
    name: str | None = None
    offer_type: str | None = None
    status: str = "Active"
    description: str | None = None
    created_at: datetime | None = None


class OfferListResponse(BaseModel):
    data: list[OfferItem]


# ---------------------------------------------------------------------------
# Monthly Preferences
# ---------------------------------------------------------------------------

class MonthlyPreferenceResponse(BaseModel):
    month: int | None = None
    year: int | None = None
    sending_days: list[str] | None = None
    emails_per_week: int | None = None
    email_types: list[str] | None = None
    primary_goal: str | None = None
    secondary_goal: str | None = None
    active_offers: list[str] | None = None
    updated_at: datetime | None = None


class UpdateMonthlyPreferencesRequest(BaseModel):
    sending_days: list[str]
    emails_per_week: int
    email_types: list[str]
    primary_goal: str
    secondary_goal: str
    active_offers: list[str]


# ---------------------------------------------------------------------------
# Data Sync Bridge responses
# ---------------------------------------------------------------------------

class SyncResult(BaseModel):
    synced_count: int
    skipped_count: int = 0
    errors: list[str] = []
