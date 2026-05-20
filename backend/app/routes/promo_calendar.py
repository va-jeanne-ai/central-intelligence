"""Promo calendar endpoints.

GET    /api/v1/promo-calendar             — list promotions (optional date-range filter)
POST   /api/v1/promo-calendar             — create a promotion
PUT    /api/v1/promo-calendar/{promotion_id} — update a promotion
DELETE /api/v1/promo-calendar/{promotion_id} — soft-delete a promotion

Sprint 4b / CI-MKT-PROMO
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser, get_current_user
from app.database import get_session
from app.repositories.marketing import PromotionRepository
from app.schemas.promo_calendar import (
    CreatePromotionRequest,
    PromotionListResponse,
    PromotionResponse,
    UpdatePromotionRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/promo-calendar", tags=["promo-calendar"])


@router.get("", response_model=PromotionListResponse)
async def list_promotions(
    start: datetime | None = Query(default=None, description="Filter start (ISO datetime)"),
    end: datetime | None = Query(default=None, description="Filter end (ISO datetime)"),
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> PromotionListResponse:
    """Return promotions, optionally filtered to those overlapping a date range.

    When start and end are both provided, only promotions whose date range
    overlaps [start, end] are returned.  When neither is provided, all active
    and planned promotions are returned.
    """
    logger.info(
        "list_promotions called — user=%s start=%s end=%s",
        current_user.id,
        start,
        end,
    )

    repo = PromotionRepository(session)

    if start is not None and end is not None:
        results = await repo.find_by_date_range(start, end)
    else:
        results = await repo.find_active()

    promotions = [PromotionResponse.model_validate(p) for p in results]
    return PromotionListResponse(promotions=promotions, total=len(promotions))


@router.post("", response_model=PromotionResponse, status_code=status.HTTP_201_CREATED)
async def create_promotion(
    body: CreatePromotionRequest,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> PromotionResponse:
    """Create a new promotional calendar entry."""
    from app.models.marketing import Promotion

    logger.info(
        "create_promotion called — user=%s name='%s'",
        current_user.id,
        body.name,
    )

    promotion = Promotion(
        name=body.name,
        description=body.description,
        promo_type=body.promo_type,
        start_date=body.start_date,
        end_date=body.end_date,
        status=body.status,
        department=body.department,
        color=body.color,
        notes=body.notes,
    )
    session.add(promotion)
    await session.commit()
    await session.refresh(promotion)

    logger.info(
        "create_promotion succeeded — user=%s promotion_id=%s",
        current_user.id,
        promotion.id,
    )

    return PromotionResponse.model_validate(promotion)


@router.put("/{promotion_id}", response_model=PromotionResponse)
async def update_promotion(
    promotion_id: uuid.UUID,
    body: UpdatePromotionRequest,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> PromotionResponse:
    """Update an existing promotional calendar entry by ID."""
    logger.info(
        "update_promotion called — user=%s promotion_id=%s",
        current_user.id,
        promotion_id,
    )

    repo = PromotionRepository(session)
    promotion = await repo.get(promotion_id)

    if promotion is None or promotion.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Promotion {promotion_id} not found",
        )

    update_fields = body.model_dump(exclude_unset=True)
    for field, value in update_fields.items():
        if hasattr(promotion, field):
            setattr(promotion, field, value)

    session.add(promotion)
    await session.commit()
    await session.refresh(promotion)

    logger.info(
        "update_promotion succeeded — user=%s promotion_id=%s",
        current_user.id,
        promotion_id,
    )

    return PromotionResponse.model_validate(promotion)


@router.delete("/{promotion_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_promotion(
    promotion_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> None:
    """Soft-delete a promotional calendar entry by ID."""
    logger.info(
        "delete_promotion called — user=%s promotion_id=%s",
        current_user.id,
        promotion_id,
    )

    repo = PromotionRepository(session)
    promotion = await repo.get(promotion_id)

    if promotion is None or promotion.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Promotion {promotion_id} not found",
        )

    promotion.deleted_at = datetime.now(timezone.utc)
    session.add(promotion)
    await session.commit()

    logger.info(
        "delete_promotion succeeded — user=%s promotion_id=%s",
        current_user.id,
        promotion_id,
    )
