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
    call_owner: str | None = None
    transcript_quality: str | None = None
    processed_date: datetime | None = None
    insights_count: int = 0


class CallListResponse(BaseModel):
    data: list[CallSummary]
    pagination: PaginationMeta


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


class CallDetailResponse(BaseModel):
    call: CallDetail
    insights: list[InsightBrief]
    content_ideas: list[ContentIdeaBrief]


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
