"""Third-party integration credentials.

One row per provider (Mailchimp, Google Calendar, Meta Ads, etc.) — the
canonical storage for "is this integration connected and what are its
credentials?". Service clients (e.g. ``app/services/mailchimp_client.py``)
read from this table first and fall back to ``settings.*`` when no row
exists, so existing env-var-based dev setups keep working.

Single-tenant for now: ``tenant_id`` is nullable and FK-less. When F29
(multi-tenancy) lands we'll backfill it, add the FK, and switch the
unique constraint to ``(provider, tenant_id)``.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Integration(Base, TimestampMixin):
    """Connection record for one third-party provider."""

    __tablename__ = "integrations"
    __table_args__ = (
        # v1 single-tenant: provider alone is unique. F29 will swap this for
        # a partial unique on (provider, tenant_id).
        UniqueConstraint("provider", name="uq_integrations_provider"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    provider: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="disconnected"
    )  # connected | disconnected | error

    # Fernet-encrypted JSON blob of {field_key: plaintext_value} for every
    # field flagged secret=True in the provider registry. Nullable so
    # disconnected rows don't keep stale ciphertext around.
    credentials_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Non-secret config (e.g. Mailchimp server_prefix, Google Calendar id).
    # JSONB so we can query/index later if needed.
    config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    last_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_sync_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    last_sync_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Future multi-tenancy hook (F29). No FK yet — `users` exists but no
    # tenants table does, and we don't want to lock in a shape that may
    # change. When F29 lands: backfill, add FK + index, make NOT NULL.
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
