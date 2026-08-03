"""Pydantic schemas for offer CRUD and offer generation endpoints.

Sprint 4b / M06-4 / OPS-O4
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, field_serializer


# ---------------------------------------------------------------------------
# Offer CRUD schemas
# ---------------------------------------------------------------------------


class OfferResponse(BaseModel):
    """Single offer record in API responses."""

    offer_id: str
    name: Optional[str] = None
    offer_type: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    status: str
    url: Optional[str] = None
    notes: Optional[str] = None
    # SQLAlchemy column is `DateTime(timezone=True)` → we get a datetime
    # object from `from_attributes`. Previously typed as `str` which made
    # `model_validate(offer)` raise a 500. Type it as datetime and serialize
    # to ISO 8601 on the way out so the JSON contract is unchanged.
    created_at: datetime

    model_config = {"from_attributes": True}

    @field_serializer("created_at")
    def _serialize_created_at(self, value: datetime) -> str:
        return value.isoformat()


class OfferListResponse(BaseModel):
    """Response from GET /api/v1/offers."""

    offers: list[OfferResponse]
    total: int


class CreateOfferRequest(BaseModel):
    """Payload for POST /api/v1/offers to create a new offer manually."""

    offer_id: Optional[str] = None
    name: str
    offer_type: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    status: str = "Active"
    url: Optional[str] = None
    notes: Optional[str] = None


# ---------------------------------------------------------------------------
# Offer Generator schemas (OPS-O4)
# ---------------------------------------------------------------------------


class OfferGenerateRequest(BaseModel):
    """Optional parameters for triggering an Offer Generator run."""

    offer_type: str = "Coaching"
    max_offers: int = 3


class OfferGenerateResponse(BaseModel):
    """Response from POST /api/v1/offer-generate."""

    task_id: str
    status: str
    message: str


class OfferTaskStatusResponse(BaseModel):
    """Status of an enqueued offer generation Celery task."""

    task_id: str
    status: str
    result: Optional[Any] = None


# ---------------------------------------------------------------------------
# GET /offers/catalog — real WGR offer catalog + revenue (deliverable 5)
# ---------------------------------------------------------------------------


class OfferCatalogItem(BaseModel):
    """One real offer (or the synthetic 'Unattributed' row) with its
    closed-sales rollup."""

    offer_id: Optional[str] = None
    name: Optional[str] = None
    offer_type: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    status: Optional[str] = None
    url: Optional[str] = None
    sales_count: int = 0
    revenue: float = 0.0


class OfferPaymentLevelRow(BaseModel):
    """One (program, payment_level) row from wgr_offer_mappings."""

    program: Optional[str] = None
    payment_level: Optional[str] = None
    offer_id: Optional[str] = None
    amount_collected: float = 0.0
    revenue_earned: float = 0.0


class OfferCatalogResponse(BaseModel):
    """Response for GET /api/v1/offers/catalog."""

    offers: list[OfferCatalogItem] = []
    payment_levels: list[OfferPaymentLevelRow] = []
    total_revenue: float = 0.0
    total_sales_count: int = 0
    generated_at: str = ""
