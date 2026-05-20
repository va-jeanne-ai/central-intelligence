"""Offer catalog endpoints and offer generation trigger.

GET  /api/v1/offers         — list active offers
POST /api/v1/offers         — create a new offer manually
POST /api/v1/offer-generate — trigger AI-driven offer generation (Celery)

Sprint 4b / M06-4 / OPS-O4
"""

from __future__ import annotations

import logging
from uuid import uuid4

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser, get_current_user
from app.database import get_session
from app.schemas.offers import (
    CreateOfferRequest,
    OfferGenerateRequest,
    OfferGenerateResponse,
    OfferListResponse,
    OfferResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/offers", tags=["offers"])


@router.get("", response_model=OfferListResponse)
async def list_offers(
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> OfferListResponse:
    """Return all active offers from the catalog. Sprint 4b / M06-4."""
    from app.repositories.intelligence import OfferRepository

    repo = OfferRepository(session)
    try:
        results = await repo.find_active()
        offers = [OfferResponse.model_validate(o) for o in results]
        return OfferListResponse(offers=offers, total=len(offers))
    except Exception:
        logger.exception("list_offers failed — user=%s", current_user.id)
        raise


@router.post("", response_model=OfferResponse)
async def create_offer(
    body: CreateOfferRequest,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> OfferResponse:
    """Create a new offer manually. Sprint 4b / M06-4."""
    from app.models.intelligence import Offer
    from app.repositories.intelligence import OfferRepository  # noqa: F401

    try:
        offer_id = body.offer_id if body.offer_id else uuid4().hex
        offer = Offer(
            offer_id=offer_id,
            name=body.name,
            offer_type=body.offer_type,
            description=body.description,
            price=body.price,
            status=body.status,
            url=body.url,
            notes=body.notes,
        )
        session.add(offer)
        await session.commit()
        await session.refresh(offer)
        logger.info(
            "create_offer called — user=%s offer_id=%s",
            current_user.id,
            offer.offer_id,
        )
        return OfferResponse.model_validate(offer)
    except Exception:
        logger.exception("create_offer failed — user=%s", current_user.id)
        raise


# ---------------------------------------------------------------------------
# Offer Generation trigger router
# ---------------------------------------------------------------------------

generate_router = APIRouter(prefix="/offer-generate", tags=["offers"])


@generate_router.post("", response_model=OfferGenerateResponse)
async def trigger_offer_generation(
    body: OfferGenerateRequest,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> OfferGenerateResponse:
    """Trigger an Offer Generator Celery task. Sprint 4b / OPS-O4."""
    from app.tasks.offer_generator import generate_offers

    task = generate_offers.delay(offer_type=body.offer_type, max_offers=body.max_offers)
    logger.info(
        "trigger_offer_generation — user=%s task_id=%s",
        current_user.id,
        task.id,
    )
    return OfferGenerateResponse(
        task_id=task.id,
        status="queued",
        message=f"Offer generation queued for type '{body.offer_type}'",
    )
