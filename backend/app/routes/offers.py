"""Offer catalog endpoints and offer generation trigger.

GET  /api/v1/offers          — list active offers (app-CRUD test data — see
                                catalog note below)
POST /api/v1/offers          — create a new offer manually
GET  /api/v1/offers/catalog  — real WGR offer catalog + revenue (deliverable 5)
POST /api/v1/offer-generate  — trigger AI-driven offer generation (Celery)

Sprint 4b / M06-4 / OPS-O4
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser, get_current_user
from app.database import get_session
from app.repositories.offer_stats import build_offer_catalog, build_payment_level_rollup
from app.schemas.offers import (
    CreateOfferRequest,
    OfferCatalogItem,
    OfferCatalogResponse,
    OfferGenerateRequest,
    OfferGenerateResponse,
    OfferListResponse,
    OfferPaymentLevelRow,
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
# Endpoint: GET /api/v1/offers/catalog
# ---------------------------------------------------------------------------
#
# Discovery (2026-08): CI's own `offers` table (18 rows) is app-CRUD test
# data ("This is a new offer", "just checking") — the real offers were never
# synced into it (untouched by this endpoint; the CRUD flow above still
# works against it). The real catalog was mirrored 2026-08-04 into
# `wgr_offers` (11 rows) / `wgr_offer_mappings` (15 rows) — see
# app/services/wgr_sync. `closed_sales.offer_id` references WGR offer ids,
# so revenue per offer is a join away.


@router.get("/catalog", response_model=OfferCatalogResponse)
async def get_offers_catalog(
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> OfferCatalogResponse:
    """Return the real WGR offer catalog with per-offer sales/revenue rollup.

    LEFT JOINs `closed_sales` on `offer_id` (grouped, not row-by-row) onto
    the real `wgr_offers` catalog; sales whose `offer_id` is null OR doesn't
    match any known offer land in a synthetic "Unattributed" row so total
    revenue always reconciles with `closed_sales`'s true sum, regardless of
    catalog coverage gaps. Also returns the payment-level breakdown from
    `wgr_offer_mappings`, grouped per program.
    """
    logger.info("get_offers_catalog called — user=%s", current_user.id)

    offer_rows = (
        await session.execute(
            text(
                "SELECT offer_id, name, offer_type, description, price, status, url "
                "FROM wgr_offers ORDER BY name"
            )
        )
    ).mappings().all()

    sales_rows = (
        await session.execute(
            text(
                "SELECT offer_id, COUNT(*) AS sales_count, "
                "COALESCE(SUM(amount_collected), 0) AS revenue "
                "FROM closed_sales GROUP BY offer_id"
            )
        )
    ).mappings().all()
    sales_by_offer: dict[str | None, tuple[int, float]] = {
        r["offer_id"]: (r["sales_count"], float(r["revenue"])) for r in sales_rows
    }

    mapping_rows = (
        await session.execute(
            text(
                "SELECT program, payment_level, offer_id, amount_collected, revenue_earned "
                "FROM wgr_offer_mappings"
            )
        )
    ).mappings().all()

    catalog_rows = build_offer_catalog(
        [dict(r) for r in offer_rows], sales_by_offer
    )
    payment_level_rows = build_payment_level_rollup([dict(r) for r in mapping_rows])

    total_revenue = round(sum(r["revenue"] for r in catalog_rows), 2)
    total_sales_count = sum(r["sales_count"] for r in catalog_rows)

    return OfferCatalogResponse(
        offers=[OfferCatalogItem(**r) for r in catalog_rows],
        payment_levels=[OfferPaymentLevelRow(**r) for r in payment_level_rows],
        total_revenue=total_revenue,
        total_sales_count=total_sales_count,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )


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
