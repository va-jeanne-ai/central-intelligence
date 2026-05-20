"""DM outreach endpoints.

POST /api/v1/dm  — analyze DM outreach and generate sequences
GET  /api/v1/dm  — retrieve current DM outreach data summary

Sprint 4a / M05-5
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser, get_current_user
from app.database import get_session
from app.repositories.marketing import DmStatsRepository
from app.repositories.shared_intelligence import SharedIntelligenceRepository
from app.schemas.dm import DMAnalyzeRequest, DMAnalyzeResponse, DMDataResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dm", tags=["dm"])


@router.post("", response_model=DMAnalyzeResponse)
async def analyze_dm(
    body: DMAnalyzeRequest,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> DMAnalyzeResponse:
    """Analyze DM outreach and generate sequences.

    Routes through MarketingDirector → DMSpecialist. The director queries
    ICP segments + pain points + content ideas via its data tools, then
    composes a personalised outreach plan with Claude.
    """
    from app.agents.directors.marketing import MarketingDirector

    # MarketingDirector.__init__ already registers dm_specialist.
    director = MarketingDirector(session=session)

    logger.info(
        "analyze_dm called — user=%s icp_segment=%s",
        current_user.id,
        body.icp_segment,
    )

    shared = SharedIntelligenceRepository(session)
    summary = await shared.get_marketing_summary()

    segment_clause = f" targeting the {body.icp_segment!r} ICP" if body.icp_segment else ""
    objective_clause = f" with the objective {body.objective!r}" if body.objective else ""
    prompt = (
        f"Draft a DM outreach sequence{segment_clause}{objective_clause}. "
        f"Use your data tools to ground the message in real pain points and "
        f"ICP profiles. Produce a short analysis of who to target and why, "
        f"then list 3-5 message blocks for the sequence (cold opener, value-add, "
        f"soft ask, follow-up). Keep tone conversational, not salesy."
    )

    analysis_text = ""
    async for chunk in director.stream_response(prompt):
        analysis_text += chunk

    return DMAnalyzeResponse(
        analysis=analysis_text,
        sequence=[],  # Message blocks are inline in `analysis` (markdown).
        recommendations=[],
        data_used={"icp": summary["icp"], "pain_points": summary["pain_points"]},
    )


@router.get("", response_model=DMDataResponse)
async def get_dm_data(
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> DMDataResponse:
    """Return current DM outreach data summary.

    Queries the dm_stats table via DmStatsRepository and returns
    aggregated totals across all tracked platforms.
    """
    logger.info("get_dm_data called — user=%s", current_user.id)

    repo = DmStatsRepository(session)
    totals = await repo.aggregate_totals()

    return DMDataResponse(
        outreach_sent=totals["total_outreach_sent"],
        response_rate=totals["avg_response_rate"],
        meetings_booked=totals["total_meetings_booked"],
        top_sequences=[],
        generated_at=datetime.now(timezone.utc).isoformat(),
    )
