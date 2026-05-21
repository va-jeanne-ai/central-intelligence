"""add integrations table

Stores third-party connector state (Mailchimp, Google Calendar, etc.)
keyed by provider slug. Credentials are Fernet-encrypted at rest in
``credentials_encrypted``; non-secret config goes in the ``config`` JSONB
column. ``tenant_id`` is nullable + FK-less in v1 — F29 (multi-tenancy)
will backfill, add FK, and make NOT NULL.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-05-21 02:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "integrations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("provider", sa.String(length=64), nullable=False, index=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="disconnected"),
        sa.Column("credentials_encrypted", sa.Text(), nullable=True),
        sa.Column("config", postgresql.JSONB(), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_sync_status", sa.String(length=32), nullable=True),
        sa.Column("last_sync_error", sa.Text(), nullable=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("provider", name="uq_integrations_provider"),
    )


def downgrade() -> None:
    op.drop_table("integrations")
