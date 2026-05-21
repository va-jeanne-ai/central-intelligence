"""add email_campaigns.source + external_id (provenance for connector data)

Tags each campaign row with which integration produced it (Mailchimp,
seed data, manual entry, etc.) and the upstream stable ID where the
provider supplies one. The Celery task then dedups on
(source, external_id) instead of name, so a rename in Mailchimp
updates the existing row rather than inserting a duplicate.

Also stamps the 3 known seed-data rows with source='seed' so they're
visually distinguishable from real Mailchimp pulls on /marketing/email.

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-05-21 03:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_SEED_NAMES = (
    "Weekly Newsletter #42",
    "New Program Launch",
    "Re-engagement Sequence",
)


def upgrade() -> None:
    op.add_column(
        "email_campaigns",
        sa.Column("source", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "email_campaigns",
        sa.Column("external_id", sa.String(length=128), nullable=True),
    )
    op.create_index(
        "ix_email_campaigns_source", "email_campaigns", ["source"], unique=False
    )
    op.create_index(
        "ix_email_campaigns_external_id",
        "email_campaigns",
        ["external_id"],
        unique=False,
    )

    # Partial unique index on (source, external_id) for connectors with stable
    # IDs. The WHERE clause means rows without an external_id (manual entries,
    # legacy seed) don't fight for uniqueness.
    op.execute(
        """
        CREATE UNIQUE INDEX uq_email_campaigns_source_external_id
        ON email_campaigns (source, external_id)
        WHERE source IS NOT NULL AND external_id IS NOT NULL
        """
    )

    # Backfill the seed-data rows so they're visibly distinguishable from
    # real Mailchimp pulls. Any row whose name matches one of the original
    # seed entries from app/tasks/email_stats.py:_SEED_CAMPAIGNS gets
    # source='seed'. Real Mailchimp rows (created after this migration) get
    # source='mailchimp' written by the task itself.
    placeholders = ", ".join(f"'{n}'" for n in _SEED_NAMES)
    op.execute(
        f"""
        UPDATE email_campaigns
           SET source = 'seed'
         WHERE source IS NULL AND name IN ({placeholders})
        """
    )


def downgrade() -> None:
    op.drop_index("uq_email_campaigns_source_external_id", table_name="email_campaigns")
    op.drop_index("ix_email_campaigns_external_id", table_name="email_campaigns")
    op.drop_index("ix_email_campaigns_source", table_name="email_campaigns")
    op.drop_column("email_campaigns", "external_id")
    op.drop_column("email_campaigns", "source")
