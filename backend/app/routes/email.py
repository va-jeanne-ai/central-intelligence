"""Email marketing endpoints.

POST /api/v1/email        — analyze email campaigns and return recommendations
POST /api/v1/email/draft  — generate a structured draft (subject + body + cta)
GET  /api/v1/email        — retrieve email performance data summary

Sprint 3a / CI-MKT-EMAIL
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser, get_current_user
from app.database import get_session
from app.repositories.marketing import EmailCampaignRepository
from app.schemas.email import (
    EmailAnalyzeRequest,
    EmailAnalyzeResponse,
    EmailCampaignRow,
    EmailDataResponse,
    EmailDraftRequest,
    EmailDraftResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/email", tags=["email"])


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

    return EmailDataResponse(
        campaigns=stats["campaigns"],
        avg_open_rate=stats["avg_open_rate"],
        avg_click_rate=stats["avg_click_rate"],
        generated_at=datetime.now(timezone.utc).isoformat(),
        recent_campaigns=[
            EmailCampaignRow(
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
            )
            for row in sent_rows
        ],
    )
