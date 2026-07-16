"""Schemas for instance configuration (profile + branding)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class InstanceProfileResponse(BaseModel):
    """The full instance profile as stored (nulls mean 'use built-in default')."""

    business_name: str | None = None
    vertical: str | None = None
    business_description: str | None = None
    target_audience: str | None = None
    brand_voice: str | None = None
    vertical_context: dict[str, str] | None = None
    terminology: dict[str, str] | None = None
    benchmarks: dict[str, str] | None = None
    app_name: str | None = None
    tagline: str | None = None
    logo_url: str | None = None
    colors: dict[str, str] | None = None
    currency_code: str | None = None
    currency_symbol: str | None = None
    timezone: str | None = None
    locale: str | None = None
    exists: bool = Field(
        default=True,
        description="False when no instance_profile row exists yet (defaults in effect).",
    )


class UpdateInstanceProfileRequest(BaseModel):
    """Partial update — only provided fields change. Admin only."""

    business_name: str | None = None
    vertical: str | None = None
    business_description: str | None = None
    target_audience: str | None = None
    brand_voice: str | None = None
    vertical_context: dict[str, str] | None = None
    terminology: dict[str, str] | None = None
    benchmarks: dict[str, str] | None = None
    app_name: str | None = None
    tagline: str | None = None
    logo_url: str | None = None
    colors: dict[str, str] | None = None
    currency_code: str | None = None
    currency_symbol: str | None = None
    timezone: str | None = None
    locale: str | None = None


class BrandingResponse(BaseModel):
    """Public-safe subset used by the frontend shell and login page."""

    app_name: str = "Central Intelligence"
    tagline: str = "AI Command Center"
    logo_url: str | None = None
    colors: dict[str, str] = {}
    currency_code: str = "USD"
    currency_symbol: str = "$"
    locale: str = "en-US"
