"""Email marketing endpoints.

POST /api/v1/email            — analyze email campaigns and return recommendations
POST /api/v1/email/draft      — generate a structured draft (subject + body + cta)
GET  /api/v1/email            — retrieve email performance data summary (legacy)
GET  /api/v1/email/campaigns  — filterable/sortable campaign list (deliverable 2)

Sprint 3a / CI-MKT-EMAIL
"""

from __future__ import annotations

import json
import logging
import re
from datetime import date, datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser, get_current_user
from app.database import get_session
from app.repositories.marketing import EmailCampaignRepository
from app.schemas.email import (
    CampaignDetailResponse,
    CreateCampaignDraftRequest,
    CreateCampaignDraftResponse,
    EmailAnalyzeRequest,
    EmailAnalyzeResponse,
    EmailCampaignListRow,
    EmailCampaignRow,
    EmailCampaignsFilterOptions,
    EmailCampaignsResponse,
    EmailCampaignsSummary,
    EmailDataResponse,
    EmailDraftRequest,
    EmailDraftResponse,
    UpdateCampaignDraftRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/email", tags=["email"])


def _int(value: object) -> int:
    """Return value as int, falling back to 0 for None or non-numeric values."""
    try:
        return int(value) if value is not None else 0
    except (TypeError, ValueError):
        return 0


def _float(value: object) -> float:
    """Return value as float, falling back to 0.0 for None or non-numeric values."""
    try:
        return float(value) if value is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


@router.post("", response_model=EmailAnalyzeResponse)
async def analyze_email(
    body: EmailAnalyzeRequest,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> EmailAnalyzeResponse:
    """Analyze email campaign performance and return recommendations.

    Routes through MarketingDirector → EmailSpecialist. The director queries
    EmailCampaignRepository directly via its data tools and composes the
    response with Claude.
    """
    from app.agents.directors.marketing import MarketingDirector

    # MarketingDirector.__init__ already registers email_writer.
    director = MarketingDirector(session=session)

    logger.info(
        "analyze_email called — user=%s campaign_type=%s",
        current_user.id,
        body.campaign_type,
    )

    # Keep the aggregate stats query for `metrics_summary` — frontend may
    # surface it as a sidebar / context block.
    repo = EmailCampaignRepository(session)
    stats = await repo.aggregate_stats()

    type_clause = f" focused on {body.campaign_type!r} campaigns" if body.campaign_type else ""
    period_clause = ""
    if body.date_from and body.date_to:
        period_clause = f" for the period {body.date_from} to {body.date_to}"
    prompt = (
        f"Analyze our email performance{type_clause}{period_clause}. "
        f"Use your data tools to pull recent campaign metrics (open rates, click "
        f"rates, unsubscribes). Produce a short, actionable analysis: lead with "
        f"the biggest finding, then 2-3 concrete recommendations for the next "
        f"campaign (subject-line tactics, segment splits, A/B tests to try)."
    )

    analysis_text = ""
    async for chunk in director.stream_response(prompt):
        analysis_text += chunk

    return EmailAnalyzeResponse(
        analysis=analysis_text,
        recommendations=[],  # Inline in `analysis` (markdown).
        metrics_summary=stats,
    )


# ----------------------------------------------------------------------
# Structured draft endpoint
# ----------------------------------------------------------------------

# Strips surrounding ```json ... ``` fences (or plain ```) that Claude
# sometimes wraps JSON in. Captures the inner content.
_JSON_FENCE_RE = re.compile(
    r"^\s*```(?:json)?\s*\n?(.*?)\n?```\s*$",
    re.DOTALL | re.IGNORECASE,
)


def _parse_email_draft(text: str) -> dict:
    """Parse the model's response into {subject, body, cta?}.

    Tries strict JSON first (handling ```json fences). On failure, falls back
    to a best-effort split: first non-empty line → subject, rest → body, cta=None.
    The fallback ensures the endpoint never crashes the page even if Claude
    deviates from the requested format.
    """
    stripped = text.strip()

    # Strip ```json … ``` (or plain ```) fences
    match = _JSON_FENCE_RE.match(stripped)
    if match:
        stripped = match.group(1).strip()

    try:
        parsed = json.loads(stripped)
        if isinstance(parsed, dict) and "subject" in parsed and "body" in parsed:
            return {
                "subject": str(parsed["subject"]).strip(),
                "body": str(parsed["body"]).strip(),
                "cta": str(parsed["cta"]).strip() if parsed.get("cta") else None,
            }
    except (json.JSONDecodeError, ValueError):
        pass

    # Fallback: split into lines, first non-empty = subject, rest = body
    lines = [line for line in text.splitlines() if line.strip()]
    subject_line = lines[0] if lines else "Untitled draft"
    body_content = "\n".join(lines[1:]).strip() if len(lines) > 1 else ""
    # Strip a `Subject:` prefix if Claude included one
    subject_clean = re.sub(r"^subject\s*:\s*", "", subject_line, flags=re.IGNORECASE).strip()
    return {"subject": subject_clean, "body": body_content, "cta": None}


@router.post("/draft", response_model=EmailDraftResponse)
async def draft_email(
    body: EmailDraftRequest,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> EmailDraftResponse:
    """Generate a structured email draft (subject + body + cta).

    Unlike POST /email which returns free-form markdown analysis, this
    endpoint asks the director to return a JSON object the compose form
    can apply directly to its Subject + Body fields.
    """
    from app.agents.directors.marketing import MarketingDirector

    director = MarketingDirector(session=session)

    logger.info(
        "draft_email called — user=%s subject_seed=%r audience=%r tone=%r",
        current_user.id,
        body.subject,
        body.audience,
        body.tone,
    )

    audience_clause = f" for the audience {body.audience!r}" if body.audience else ""
    tone_clause = f" in a {body.tone} tone" if body.tone else " in a warm, professional tone"
    prompt = (
        f"Draft a marketing email{audience_clause}{tone_clause}, seeded by the "
        f"subject idea: {body.subject!r}.\n\n"
        f"Delegate to the Email specialist (via delegate_to_email_writer) if "
        f"you need to ground the copy in recent campaign performance. "
        f"Otherwise produce the draft directly.\n\n"
        f"Return your answer as a JSON object with exactly these keys:\n"
        f"  - subject (string): the final subject line, polished and click-worthy\n"
        f"  - body (string): the full email body, with paragraph breaks. Use \\n for newlines.\n"
        f"  - cta (string): the call-to-action text (e.g. 'Book a call', 'Reply with Yes')\n\n"
        f"Output ONLY the JSON object. No prose before or after. No markdown fences."
    )

    raw = ""
    async for chunk in director.stream_response(prompt):
        raw += chunk

    parsed = _parse_email_draft(raw)
    return EmailDraftResponse(
        subject=parsed["subject"],
        body=parsed["body"],
        cta=parsed["cta"],
    )


@router.get("", response_model=EmailDataResponse)
async def get_email_data(
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> EmailDataResponse:
    """Return current email campaign data summary.

    Queries the email_stats table via EmailCampaignRepository and returns
    aggregated stats across all tracked campaigns.
    """
    logger.info("get_email_data called — user=%s", current_user.id)

    repo = EmailCampaignRepository(session)
    stats = await repo.aggregate_stats()
    sent_rows = await repo.find_sent(limit=20)
    draft_rows = await repo.find_drafts(limit=50)
    archived_rows = await repo.find_archived(limit=100)

    def _to_row(row) -> EmailCampaignRow:
        return EmailCampaignRow(
            id=str(row.id),
            name=row.name,
            subject=row.subject,
            campaign_type=row.campaign_type,
            status=row.status,
            sent_at=row.sent_at.isoformat() if row.sent_at else None,
            recipients_count=row.recipients_count,
            open_count=row.open_count,
            click_count=row.click_count,
            open_rate=row.open_rate,
            click_rate=row.click_rate,
            source=row.source,
            external_id=row.external_id,
            audience_name=row.audience_name,
            segment_text=row.segment_text,
            body_html=row.body_html,
            archive_url=row.archive_url,
        )

    return EmailDataResponse(
        campaigns=stats["campaigns"],
        avg_open_rate=stats["avg_open_rate"],
        avg_click_rate=stats["avg_click_rate"],
        generated_at=datetime.now(timezone.utc).isoformat(),
        recent_campaigns=[_to_row(r) for r in sent_rows],
        drafts=[_to_row(r) for r in draft_rows],
        archived=[_to_row(r) for r in archived_rows],
    )


# ---------------------------------------------------------------------------
# GET /api/v1/email/campaigns — filterable/sortable campaign list (deliverable 2)
# ---------------------------------------------------------------------------
#
# Audit (verified read-only, 2026-08-03): 2,426 rows in email_campaigns, all
# deleted_at IS NULL. status has exactly ONE distinct value ("sent") across
# every row — no drafts/archived exist outside the (removed) compose flow —
# so the status filter is still exposed data-driven (per filter_options) but
# will only ever offer one option today. campaign_type has 12 distinct
# non-degenerate values (Value/Education, Weekly Nurture, Story-led, Launch,
# Transactional, Promotional Offer, Client Win, Welcome/Onboarding,
# Re-engagement, Unclassifiable, 'regular', plus a few NULLs) — a real filter.
# sent_at spans 2016-07-25 to 2026-08-02 — a real date-range filter.
# bounce_count is always 0 today but is a real column, kept in the row shape.

_CAMPAIGNS_SORTABLE_COLUMNS: frozenset[str] = frozenset(
    {
        "sent_at",
        "recipients_count",
        "open_count",
        "click_count",
        "open_rate",
        "click_rate",
        "unsubscribe_count",
        "bounce_count",
    }
)


def _parse_campaigns_date_param(value: str | None, *, param_name: str) -> date | None:
    """Parse a query param as a strict ISO ``YYYY-MM-DD`` date.

    Mirrors ``ads._parse_date_param``: fail loudly with a 422 rather than let
    a malformed string reach a ``Date``-typed bind and surface as an opaque
    500 from the asyncpg driver.

    Pure function (no DB, no request context) — unit-tested directly in
    ``tests/test_email_campaigns.py``.
    """
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid {param_name}: {value!r} — expected ISO format YYYY-MM-DD",
        ) from exc


def _resolve_campaigns_sort_by(sort_by: str) -> str:
    """Return ``sort_by`` if it's in the injection-safe whitelist, else the default.

    Factored out of the route body so the whitelist-fallback behavior (invalid
    column → falls back to ``"sent_at"`` rather than raising) is unit-testable
    without a DB or request context.
    """
    return sort_by if sort_by in _CAMPAIGNS_SORTABLE_COLUMNS else "sent_at"


def _summarize_campaigns(campaigns: list["EmailCampaignListRow"]) -> "EmailCampaignsSummary":
    """Aggregate totals/averages over a list of campaign rows.

    Pure function — no DB access — so it can be unit-tested directly with
    plain ``EmailCampaignListRow`` instances. Averages are computed only over
    rows with a non-null rate (matches the route's prior inline behavior);
    an empty list returns all-zero fields rather than raising or dividing by
    zero.
    """
    count = len(campaigns)
    total_recipients = sum(c.recipients_count for c in campaigns)
    total_opens = sum(c.open_count for c in campaigns)
    total_clicks = sum(c.click_count for c in campaigns)
    open_rates = [c.open_rate for c in campaigns if c.open_rate is not None]
    click_rates = [c.click_rate for c in campaigns if c.click_rate is not None]
    return EmailCampaignsSummary(
        count=count,
        total_recipients=total_recipients,
        total_opens=total_opens,
        total_clicks=total_clicks,
        avg_open_rate=round(sum(open_rates) / len(open_rates), 2) if open_rates else 0.0,
        avg_click_rate=round(sum(click_rates) / len(click_rates), 2) if click_rates else 0.0,
    )


@router.get("/campaigns", response_model=EmailCampaignsResponse)
async def get_email_campaigns(
    sent_from: str | None = Query(
        default=None, description="Filter sent_at on/after this date (YYYY-MM-DD)"
    ),
    sent_to: str | None = Query(
        default=None, description="Filter sent_at on/before this date (YYYY-MM-DD)"
    ),
    campaign_type: str | None = Query(default=None, description="Filter by exact campaign_type"),
    status: str | None = Query(default=None, description="Filter by exact status"),
    search: str | None = Query(default=None, description="Search name or subject (ILIKE)"),
    sort_by: str = Query(default="sent_at", description="Column to sort by"),
    sort_dir: Literal["asc", "desc"] = Query(default="desc", description="Sort direction"),
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> EmailCampaignsResponse:
    """Return campaigns with metric filters, a date range, and server sort.

    Powers the rebuilt /marketing/email page: filter row (search, date range,
    campaign type, status, sort-by-metric), the sortable campaigns table, the
    per-row visual performance indicator (ScoreBar + tercile chip, computed
    client-side against this filtered set's max open_rate), and the "Top
    campaigns" ranking card (client-side top-5 slice of the same response).
    """
    logger.info(
        "get_email_campaigns called — user=%s sent_from=%s sent_to=%s "
        "campaign_type=%s status=%s search=%s sort_by=%s sort_dir=%s",
        current_user.id, sent_from, sent_to, campaign_type, status, search, sort_by, sort_dir,
    )

    # ---- Validate / sanitise params (all bind-safe or whitelisted) --------
    parsed_from = _parse_campaigns_date_param(sent_from, param_name="sent_from")
    parsed_to = _parse_campaigns_date_param(sent_to, param_name="sent_to")
    sort_by = _resolve_campaigns_sort_by(sort_by)
    # sort_dir is already constrained to the Literal by FastAPI/Pydantic.

    where_sql = "deleted_at IS NULL"
    params: dict[str, object] = {}
    if parsed_from is not None:
        where_sql += " AND sent_at >= :sent_from"
        params["sent_from"] = parsed_from
    if parsed_to is not None:
        where_sql += " AND sent_at <= :sent_to"
        params["sent_to"] = parsed_to
    if campaign_type:
        where_sql += " AND campaign_type = :campaign_type"
        params["campaign_type"] = campaign_type
    if status:
        where_sql += " AND status = :status"
        params["status"] = status
    if search:
        where_sql += " AND (name ILIKE :search OR subject ILIKE :search)"
        params["search"] = f"%{search}%"

    # ---- Filtered rows ------------------------------------------------------
    rows = (
        await session.execute(
            text(
                f"""
                SELECT
                    id, name, subject, campaign_type, status, sent_at,
                    audience_name, recipients_count, open_count, click_count,
                    unsubscribe_count, bounce_count, open_rate, click_rate,
                    archive_url
                FROM email_campaigns
                WHERE {where_sql}
                ORDER BY {sort_by} {sort_dir} NULLS LAST, id ASC
                """  # noqa: S608 — where_sql/sort_by built from fixed whitelists above
            ),
            params,
        )
    ).mappings().all()

    campaigns = [
        EmailCampaignListRow(
            id=str(r["id"]),
            name=r["name"],
            subject=r["subject"],
            campaign_type=r["campaign_type"],
            status=r["status"],
            sent_at=r["sent_at"].isoformat() if r["sent_at"] else None,
            audience_name=r["audience_name"],
            recipients_count=_int(r["recipients_count"]),
            open_count=_int(r["open_count"]),
            click_count=_int(r["click_count"]),
            unsubscribe_count=_int(r["unsubscribe_count"]),
            bounce_count=_int(r["bounce_count"]),
            open_rate=_float(r["open_rate"]) if r["open_rate"] is not None else None,
            click_rate=_float(r["click_rate"]) if r["click_rate"] is not None else None,
            archive_url=r["archive_url"],
        )
        for r in rows
    ]

    # ---- Summary over the FILTERED set --------------------------------------
    summary = _summarize_campaigns(campaigns)

    # ---- Filter options — distinct values actually present (unfiltered) ---
    # Data-driven per the leads page philosophy: never offer a dropdown
    # option with zero matching rows.
    type_rows = (
        await session.execute(
            text(
                "SELECT DISTINCT campaign_type FROM email_campaigns "
                "WHERE deleted_at IS NULL AND campaign_type IS NOT NULL "
                "ORDER BY campaign_type"
            )
        )
    ).scalars().all()
    status_rows = (
        await session.execute(
            text(
                "SELECT DISTINCT status FROM email_campaigns "
                "WHERE deleted_at IS NULL AND status IS NOT NULL "
                "ORDER BY status"
            )
        )
    ).scalars().all()
    filter_options = EmailCampaignsFilterOptions(
        campaign_types=list(type_rows),
        statuses=list(status_rows),
    )

    return EmailCampaignsResponse(
        campaigns=campaigns,
        summary=summary,
        filter_options=filter_options,
    )


@router.post("/campaigns", response_model=CreateCampaignDraftResponse, status_code=201)
async def create_campaign_draft(
    body: CreateCampaignDraftRequest,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> CreateCampaignDraftResponse:
    """Create a manual draft campaign from the compose UI.

    Writes to email_campaigns with source='manual', status='draft'. The new
    row shows up on /marketing/email immediately with the indigo 'manual'
    badge. Sending is deferred to a separate, guarded flow.
    """
    repo = EmailCampaignRepository(session)
    instance = await repo.create(
        name=body.name,
        subject=body.subject,
        body_html=body.body_html,
        audience_name=body.audience_name,
        segment_text=body.segment_text,
        campaign_type=body.campaign_type,
        blocks_json=body.blocks_json,
        status="draft",
        source="manual",
    )
    await session.commit()
    logger.info(
        "create_campaign_draft — user=%s id=%s name=%r",
        current_user.id, instance.id, body.name,
    )
    return CreateCampaignDraftResponse(
        id=str(instance.id),
        status=instance.status,
        source=instance.source or "manual",
    )


# ---------------------------------------------------------------------------
# GET /api/v1/email/campaigns/{id}  — load a draft for editing
# ---------------------------------------------------------------------------


@router.get("/campaigns/{campaign_id}", response_model=CampaignDetailResponse)
async def get_campaign(
    campaign_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> CampaignDetailResponse:
    """Load a single campaign by id.

    Used by the compose page when opening an existing draft for editing —
    the response carries blocks_json so the page builder can hydrate its
    state. Legacy drafts (saved before block editing) have blocks_json=null;
    the compose page handles that by mounting an empty canvas with a notice.
    """
    from uuid import UUID
    try:
        uid = UUID(campaign_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Campaign not found")

    repo = EmailCampaignRepository(session)
    row = await repo.get(uid)
    if row is None:
        raise HTTPException(status_code=404, detail="Campaign not found")

    return CampaignDetailResponse(
        id=str(row.id),
        name=row.name,
        subject=row.subject,
        body_html=row.body_html or "",
        audience_name=row.audience_name,
        segment_text=row.segment_text,
        campaign_type=row.campaign_type,
        status=row.status,
        source=row.source,
        blocks_json=row.blocks_json,
    )


# ---------------------------------------------------------------------------
# PATCH /api/v1/email/campaigns/{id}  — update an existing draft in place
# ---------------------------------------------------------------------------


@router.patch("/campaigns/{campaign_id}", response_model=CreateCampaignDraftResponse)
async def update_campaign(
    campaign_id: str,
    body: UpdateCampaignDraftRequest,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> CreateCampaignDraftResponse:
    """Partial-update a campaign draft.

    Only fields present in the request body are written (Pydantic v2's
    model_dump(exclude_unset=True) distinguishes missing vs. explicit null).
    Refuses to touch rows where status != 'draft' — sent/sending campaigns
    are read-only via this surface.
    """
    from uuid import UUID
    try:
        uid = UUID(campaign_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Campaign not found")

    repo = EmailCampaignRepository(session)
    row = await repo.get(uid)
    if row is None:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if row.status != "draft":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot edit campaign in status={row.status!r}; only drafts are editable.",
        )

    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(row, field, value)

    session.add(row)
    await session.commit()
    await session.refresh(row)

    logger.info(
        "update_campaign — user=%s id=%s fields=%s",
        current_user.id, row.id, list(updates.keys()),
    )
    return CreateCampaignDraftResponse(
        id=str(row.id),
        status=row.status,
        source=row.source or "manual",
    )


# ---------------------------------------------------------------------------
# DELETE /api/v1/email/campaigns/{id}  — soft-delete a draft
# ---------------------------------------------------------------------------


@router.delete("/campaigns/{campaign_id}", status_code=204)
async def delete_campaign(
    campaign_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Soft-delete a draft campaign.

    Sets `deleted_at` (the SoftDeleteMixin column) rather than removing
    the row, so it's recoverable from the DB if needed. Sent campaigns
    are protected — deleting historical metrics is a different
    operation and not exposed here.
    """
    from uuid import UUID
    try:
        uid = UUID(campaign_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Campaign not found")

    repo = EmailCampaignRepository(session)
    row = await repo.get(uid)
    if row is None:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if row.status != "draft":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete campaign in status={row.status!r}; only drafts can be deleted via this surface.",
        )

    await repo.soft_delete(uid)
    await session.commit()

    logger.info(
        "delete_campaign — user=%s id=%s", current_user.id, row.id,
    )
    return None


# ---------------------------------------------------------------------------
# POST /api/v1/email/campaigns/{id}/duplicate  — copy a draft
# ---------------------------------------------------------------------------


@router.post(
    "/campaigns/{campaign_id}/duplicate",
    response_model=CreateCampaignDraftResponse,
    status_code=201,
)
async def duplicate_campaign(
    campaign_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> CreateCampaignDraftResponse:
    """Clone an existing campaign as a new draft.

    The clone always starts in status='draft' regardless of the source's
    status — duplicating a sent campaign is a legitimate "I want to send
    something similar" workflow. We copy the editable content but reset
    metrics/timestamps and append "(copy)" to the name so the user can
    spot it in the list.
    """
    from uuid import UUID
    try:
        uid = UUID(campaign_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Campaign not found")

    repo = EmailCampaignRepository(session)
    src = await repo.get(uid)
    if src is None:
        raise HTTPException(status_code=404, detail="Campaign not found")

    clone = await repo.create(
        name=f"{src.name} (copy)",
        subject=src.subject,
        body_html=src.body_html,
        audience_name=src.audience_name,
        segment_text=src.segment_text,
        campaign_type=src.campaign_type,
        blocks_json=src.blocks_json,
        status="draft",
        source="manual",
    )
    await session.commit()

    logger.info(
        "duplicate_campaign — user=%s src=%s clone=%s",
        current_user.id, src.id, clone.id,
    )
    return CreateCampaignDraftResponse(
        id=str(clone.id),
        status=clone.status,
        source=clone.source or "manual",
    )


# ---------------------------------------------------------------------------
# POST /api/v1/email/campaigns/{id}/archive
# POST /api/v1/email/campaigns/{id}/unarchive
# ---------------------------------------------------------------------------


@router.post(
    "/campaigns/{campaign_id}/archive",
    response_model=CreateCampaignDraftResponse,
)
async def archive_campaign(
    campaign_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> CreateCampaignDraftResponse:
    """Move a sent campaign into the archived state.

    Sent campaigns can accumulate clutter once the user has moved on.
    Archiving sets status='archived' (separate from soft delete — the
    row stays visible in the Archived section so the user can restore
    it). Drafts use Delete instead; trying to archive a draft 400s.
    """
    from uuid import UUID
    try:
        uid = UUID(campaign_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Campaign not found")

    repo = EmailCampaignRepository(session)
    row = await repo.get(uid)
    if row is None:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if row.status == "draft":
        raise HTTPException(
            status_code=400,
            detail="Drafts use Delete, not Archive. Archive is for sent campaigns.",
        )
    if row.status == "archived":
        # Idempotent — return current state instead of 400ing.
        return CreateCampaignDraftResponse(
            id=str(row.id), status=row.status, source=row.source or "manual",
        )

    row.status = "archived"
    session.add(row)
    await session.commit()
    await session.refresh(row)

    logger.info("archive_campaign — user=%s id=%s", current_user.id, row.id)
    return CreateCampaignDraftResponse(
        id=str(row.id), status=row.status, source=row.source or "manual",
    )


@router.post(
    "/campaigns/{campaign_id}/unarchive",
    response_model=CreateCampaignDraftResponse,
)
async def unarchive_campaign(
    campaign_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> CreateCampaignDraftResponse:
    """Restore an archived campaign back to status='sent'.

    Only archived rows are restorable through this endpoint. Anything
    else 400s — there's no ambiguous target state.
    """
    from uuid import UUID
    try:
        uid = UUID(campaign_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Campaign not found")

    repo = EmailCampaignRepository(session)
    row = await repo.get(uid)
    if row is None:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if row.status != "archived":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot unarchive campaign in status={row.status!r}.",
        )

    row.status = "sent"
    session.add(row)
    await session.commit()
    await session.refresh(row)

    logger.info("unarchive_campaign — user=%s id=%s", current_user.id, row.id)
    return CreateCampaignDraftResponse(
        id=str(row.id), status=row.status, source=row.source or "manual",
    )
