"""Pydantic schemas for /api/v1/integrations endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class ProviderFieldSchema(BaseModel):
    """One form field definition rendered by the frontend."""

    key: str
    label: str
    type: str = "text"  # "text" | "password" | "select"
    secret: bool = False
    required: bool = False
    placeholder: str = ""
    help: str = ""


class ProviderSummary(BaseModel):
    """One row on the list page."""

    slug: str
    name: str
    icon: str = ""
    category: str = ""
    status: str  # "available" | "coming_soon"
    description: str = ""
    connected: bool = False
    last_synced_at: datetime | None = None
    last_sync_status: str | None = None
    oauth_pending: bool = False


class IntegrationDetail(ProviderSummary):
    """Detail-page payload: provider metadata + fields + currently-stored values."""

    fields: list[ProviderFieldSchema] = []
    # Currently-stored values. Secret fields are masked (e.g. "********us21").
    # Non-secret values are returned as-is so the form can pre-populate them.
    values: dict[str, str] = {}
    last_sync_error: str | None = None


class UpsertIntegrationRequest(BaseModel):
    """POST /api/v1/integrations/{slug} — Save form payload.

    For secret fields, a value of "" means "leave the existing ciphertext
    alone" (so the user doesn't have to re-type their API key when changing
    only the server_prefix).
    """

    values: dict[str, str] = {}


class TestIntegrationResponse(BaseModel):
    """POST /api/v1/integrations/{slug}/test — connectivity check result."""

    ok: bool
    message: str
    details: dict[str, Any] | None = None
