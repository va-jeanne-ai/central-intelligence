"""add lead_notes table — append-only staff journal entries

Distinct from lead.notes (which holds the immutable provider payload,
e.g. the raw GHL webhook body). Each row is one staff-side observation
or reminder, displayed as a timeline on the lead detail page. Newest
first per (lead_id, created_at DESC) index.

Revision ID: g7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-05-21 22:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "g7b8c9d0e1f2"
down_revision: Union[str, None] = "f6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "lead_notes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "lead_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("leads.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "author_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    # Composite index — "most-recent notes for a lead" is the only access
    # pattern. DESC on created_at because Postgres can scan the index in
    # reverse but the planner prefers a matching index direction.
    op.execute(
        """
        CREATE INDEX ix_lead_notes_lead_created
        ON lead_notes (lead_id, created_at DESC)
        """
    )


def downgrade() -> None:
    op.drop_index("ix_lead_notes_lead_created", table_name="lead_notes")
    op.drop_table("lead_notes")
