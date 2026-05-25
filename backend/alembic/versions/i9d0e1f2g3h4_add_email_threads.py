"""add email_threads + email_messages tables — Gmail thread sync storage

Backs the Gmail integration feature: for each lead with an email address,
the nightly Celery task pulls messages where the lead's address appears
as From/To/Cc/Bcc, then upserts them into these tables. The lead detail
page renders threads as collapsed rows that expand to show messages.

Two tables:

  email_threads:
    one row per Gmail thread linked to a lead. Composite unique on
    (lead_id, provider_thread_id) so the same thread never duplicates.
    last_message_at + message_count are maintained by the upsert helper
    so the lead-detail GET doesn't need an aggregate query per row.

  email_messages:
    one row per Gmail message inside a thread. provider_message_id is
    globally unique (Gmail guarantees stable ids). Bodies are plain text
    only; attachments are recorded as metadata (filename + size + mime)
    but not downloaded.

Revision ID: i9d0e1f2g3h4
Revises: h8c9d0e1f2g3
Create Date: 2026-05-25 22:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "i9d0e1f2g3h4"
down_revision: Union[str, None] = "h8c9d0e1f2g3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "email_threads",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "lead_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("leads.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider_thread_id", sa.String(128), nullable=False),
        sa.Column("subject", sa.Text(), nullable=True),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("message_count", sa.Integer(), nullable=False, server_default="0"),
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
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "lead_id", "provider_thread_id", name="uq_email_threads_lead_provider",
        ),
    )
    # "all threads for this lead, newest first" — the single read pattern.
    op.execute(
        """
        CREATE INDEX ix_email_threads_lead_recency
        ON email_threads (lead_id, last_message_at DESC NULLS LAST)
        """
    )

    op.create_table(
        "email_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "thread_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("email_threads.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "provider_message_id",
            sa.String(128),
            nullable=False,
            unique=True,
        ),
        sa.Column("from_address", sa.String(255), nullable=True),
        sa.Column("to_addresses", postgresql.JSONB, nullable=True),
        sa.Column("cc_addresses", postgresql.JSONB, nullable=True),
        sa.Column("subject", sa.Text(), nullable=True),
        sa.Column("body_text", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "has_attachments",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("attachments_meta", postgresql.JSONB, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    # Drives thread expansion render — every message in order.
    op.execute(
        """
        CREATE INDEX ix_email_messages_thread_chronological
        ON email_messages (thread_id, sent_at)
        """
    )


def downgrade() -> None:
    op.drop_index(
        "ix_email_messages_thread_chronological", table_name="email_messages",
    )
    op.drop_table("email_messages")
    op.drop_index("ix_email_threads_lead_recency", table_name="email_threads")
    op.drop_table("email_threads")
