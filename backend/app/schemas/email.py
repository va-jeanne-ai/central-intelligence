"""Pydantic schemas for email endpoints."""

from __future__ import annotations

from pydantic import BaseModel


class EmailAnalyzeRequest(BaseModel):
    campaign_type: str | None = None
    date_from: str | None = None
    date_to: str | None = None


class EmailDraftRequest(BaseModel):
    subject: str
    audience: str | None = None
    tone: str | None = None


class EmailAnalyzeResponse(BaseModel):
    analysis: str
    recommendations: list[str]
    metrics_summary: dict


class EmailDraftResponse(BaseModel):
    subject: str
    body: str
    cta: str | None = None


class CreateCampaignDraftRequest(BaseModel):
    """Payload for POST /api/v1/email/campaigns — manual draft creation from the compose UI."""

    name: str
    subject: str | None = None
    body_html: str
    audience_name: str | None = None
    segment_text: str | None = None
    campaign_type: str | None = None  # "regular" | "plain_text" | "template"
    # JSON-serialized Block[] from the page builder. When present, lets
    # the compose page round-trip via PATCH /campaigns/{id}.
    blocks_json: str | None = None


class CreateCampaignDraftResponse(BaseModel):
    id: str
    status: str
    source: str


class UpdateCampaignDraftRequest(BaseModel):
    """Payload for PATCH /api/v1/email/campaigns/{id} — partial draft update.

    All fields optional; only provided ones overwrite. Empty string clears.
    """

    name: str | None = None
    subject: str | None = None
    body_html: str | None = None
    audience_name: str | None = None
    segment_text: str | None = None
    campaign_type: str | None = None
    blocks_json: str | None = None


class CampaignDetailResponse(BaseModel):
    """Payload for GET /api/v1/email/campaigns/{id} — load a draft for editing.

    Returns the full row including blocks_json so the compose page can
    hydrate the block builder state.
    """

    id: str
    name: str
    subject: str | None = None
    body_html: str
    audience_name: str | None = None
    segment_text: str | None = None
    campaign_type: str | None = None
    status: str
    source: str | None = None
    blocks_json: str | None = None


class EmailCampaignRow(BaseModel):
    """One row in the recent-campaigns list on /marketing/email."""

    id: str
    name: str
    subject: str | None = None
    campaign_type: str | None = None
    status: str
    sent_at: str | None = None
    recipients_count: int = 0
    open_count: int = 0
    click_count: int = 0
    open_rate: float | None = None
    click_rate: float | None = None
    # Provenance: which integration produced this row.
    source: str | None = None
    external_id: str | None = None
    # Read-only context surfaced in the click-to-expand row.
    audience_name: str | None = None
    segment_text: str | None = None
    body_html: str | None = None
    archive_url: str | None = None


class EmailDataResponse(BaseModel):
    campaigns: int
    avg_open_rate: float
    avg_click_rate: float
    generated_at: str
    # 20 most-recent sent campaigns with their per-row metrics + source badge.
    recent_campaigns: list[EmailCampaignRow] = []
    # 50 most-recently-edited drafts, newest first. Surfaced on
    # /marketing/email as a separate section above the sent list.
    drafts: list[EmailCampaignRow] = []
    # Archived campaigns — sent rows the user moved out of the main list.
    # Surfaced under a collapsible "Archived" section on /marketing/email
    # with a Restore action.
    archived: list[EmailCampaignRow] = []


# ---------------------------------------------------------------------------
# GET /api/v1/email/campaigns — filterable, sortable campaign list (deliverable 2)
# ---------------------------------------------------------------------------


class EmailCampaignListRow(BaseModel):
    """One row in the filterable/sortable campaigns table."""

    id: str
    name: str
    subject: str | None = None
    campaign_type: str | None = None
    status: str
    sent_at: str | None = None
    audience_name: str | None = None
    recipients_count: int = 0
    open_count: int = 0
    click_count: int = 0
    unsubscribe_count: int = 0
    bounce_count: int = 0
    open_rate: float | None = None
    click_rate: float | None = None
    archive_url: str | None = None


class EmailCampaignsSummary(BaseModel):
    """Aggregate stats over the FILTERED set (not the whole table).

    ``max_open_rate`` is the filtered set's max ``open_rate`` (NULLs
    excluded) — the ScoreBar on each row normalizes against this value
    server-side now instead of recomputing it client-side from a
    single page of rows.
    """

    count: int = 0
    total_recipients: int = 0
    total_opens: int = 0
    total_clicks: int = 0
    avg_open_rate: float = 0.0
    avg_click_rate: float = 0.0
    max_open_rate: float = 0.0


class EmailCampaignsTierThresholds(BaseModel):
    """Tercile cut points for ``open_rate`` over the FILTERED set (not the
    current page), computed in SQL via ``percentile_cont``. The frontend
    classifies each row as Top (> ``high``) / Mid (between) / Low (<= ``low``).

    ``all_equal`` mirrors the documented all-equal edge case from the prior
    client-side ``tierOf()`` helper: when every open_rate in the filtered set
    is identical (including all-zero, or a filtered set of 0-1 rows), no row
    is actually distinguishable from its peers — the frontend must render
    every row as "Mid" rather than let a degenerate 0-width band produce
    misleading Top/Low chips.
    """

    low: float = 0.0
    high: float = 0.0
    all_equal: bool = True


class EmailCampaignsFilterOptions(BaseModel):
    """Distinct values actually present in the (unfiltered) table — drives
    the frontend's filter dropdowns so every option is guaranteed non-empty.
    """

    campaign_types: list[str] = []
    statuses: list[str] = []


class EmailCampaignsResponse(BaseModel):
    campaigns: list[EmailCampaignListRow] = []
    total: int = 0
    page: int = 1
    per_page: int = 50
    summary: EmailCampaignsSummary = EmailCampaignsSummary()
    tier_thresholds: EmailCampaignsTierThresholds = EmailCampaignsTierThresholds()
    # Top-5 by the requested sort metric over the WHOLE filtered set (not
    # just the current page) — powers the "Top campaigns" ranking card.
    top_campaigns: list[EmailCampaignListRow] = []
    filter_options: EmailCampaignsFilterOptions = EmailCampaignsFilterOptions()
