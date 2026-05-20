"""Pydantic schemas for the promo calendar endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class PromotionResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    promo_type: str
    start_date: datetime
    end_date: datetime
    status: str
    department: str | None
    color: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PromotionListResponse(BaseModel):
    promotions: list[PromotionResponse]
    total: int


class CreatePromotionRequest(BaseModel):
    name: str
    description: str | None = None
    promo_type: str = "campaign"
    start_date: datetime
    end_date: datetime
    status: str = "planned"
    department: str | None = None
    color: str | None = None
    notes: str | None = None


class UpdatePromotionRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    promo_type: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    status: str | None = None
    department: str | None = None
    color: str | None = None
    notes: str | None = None
