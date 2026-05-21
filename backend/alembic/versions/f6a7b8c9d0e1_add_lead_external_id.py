"""add leads.external_id (for source-tagged dedup)

Mirrors the email_campaigns provenance pattern: a nullable external_id
column plus a partial unique index on (source, external_id) where both
are not null. Used by the GHL webhook endpoint to dedup pushed contacts
by their stable GHL contact_id rather than email (which can change).

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-05-21 08:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "leads",
        sa.Column("external_id", sa.String(length=128), nullable=True),
    )
    op.create_index(
        "ix_leads_external_id", "leads", ["external_id"], unique=False
    )

    # Partial unique index — only enforced when both columns are populated.
    # Rows with NULL external_id (manual entries, legacy seed) don't fight
    # for uniqueness. Same shape as uq_email_campaigns_source_external_id.
    op.execute(
        """
        CREATE UNIQUE INDEX uq_leads_source_external_id
        ON leads (source, external_id)
        WHERE source IS NOT NULL AND external_id IS NOT NULL
        """
    )


def downgrade() -> None:
    op.drop_index("uq_leads_source_external_id", table_name="leads")
    op.drop_index("ix_leads_external_id", table_name="leads")
    op.drop_column("leads", "external_id")
