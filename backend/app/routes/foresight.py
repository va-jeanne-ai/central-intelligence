"""Foresight P1 endpoint.

  GET /api/v1/foresight/recommendations — published + gated cards, straight
  from the foresight_recommendations table (nightly-computed by
  app.tasks.foresight.compute_foresight_recommendations). Reads one tiny
  table (5 rows) — trivially fast, no aggregation at request time.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser, get_current_user
from app.database import get_session
from app.models.intelligence import ForesightRecommendation
from app.schemas.foresight import ForesightCard, ForesightRecommendationsResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/foresight", tags=["foresight"])


def _to_card(row: ForesightRecommendation) -> ForesightCard:
    return ForesightCard(
        id=row.id,
        status=row.status,
        confidence=row.confidence,
        title=row.title,
        department=row.department,
        hindsight_headline=row.hindsight_headline,
        hindsight_detail=row.hindsight_detail,
        evidence_href=row.evidence_href,
        evidence_label=row.evidence_label,
        insight_text=row.insight_text,
        action_text=row.action_text,
        lift_text=row.lift_text,
        hold_reason=row.hold_reason,
        baseline_label=row.baseline_label,
        baseline_rate=row.baseline_rate,
        baseline_low=row.baseline_low,
        baseline_high=row.baseline_high,
        variant_label=row.variant_label,
        variant_rate=row.variant_rate,
        variant_low=row.variant_low,
        variant_high=row.variant_high,
        n_label=row.n_label,
        computed_at=row.computed_at.isoformat(),
    )


@router.get("/recommendations", response_model=ForesightRecommendationsResponse)
async def get_foresight_recommendations(
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> ForesightRecommendationsResponse:
    """Return every nightly-computed Foresight card, split into published
    (lift + warning) and gated buckets, ordered by id for stable output."""
    logger.info("get_foresight_recommendations called — user=%s", current_user.id)

    rows = (
        await session.execute(
            select(ForesightRecommendation).order_by(ForesightRecommendation.id)
        )
    ).scalars().all()

    published = [
        _to_card(r) for r in rows if r.status in ("published_lift", "published_warning")
    ]
    gated = [_to_card(r) for r in rows if r.status == "gated"]
    computed_at = rows[0].computed_at.isoformat() if rows else None

    return ForesightRecommendationsResponse(
        published=published, gated=gated, computed_at=computed_at
    )
