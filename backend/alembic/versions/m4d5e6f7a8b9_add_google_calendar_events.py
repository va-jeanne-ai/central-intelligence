"""add google_calendar_events for the Calendar ingest pipeline

Calendar is intentionally a first-class data surface: the dedicated
``/calendar`` page lists events, the lead-detail Events card surfaces
matching events by attendee email, and the chat agent gets both a
structured ``query_calendar`` tool (time-window questions) and the
polymorphic ``search_knowledge_base`` semantic search (the events get
embedded just like Gmail/Drive/notes/insights via the existing
``embed_pending`` queue).

Recurring events are stored as expanded instances (``singleEvents=true``
on the Google API call) so "what's on Tuesday at 9am" returns a single
concrete row rather than forcing the chat to compute recurrence.

Revision ID: m4d5e6f7a8b9
Revises: l3c4d5e6f7a8
Create Date: 2026-05-28 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "m4d5e6f7a8b9"
down_revision: Union[str, None] = "l3c4d5e6f7a8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "google_calendar_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "connected_via_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # Google's event id. For recurring events we pass through
        # singleEvents=true, so each instance has its own id (parent
        # id + "_" + RFC5545 timestamp suffix). Store verbatim.
        sa.Column("provider_event_id", sa.String(256), nullable=False),
        sa.Column("calendar_id", sa.String(256), nullable=False),
        sa.Column("calendar_name", sa.String(255), nullable=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("location", sa.Text(), nullable=True),
        sa.Column("organizer_email", sa.String(255), nullable=True),
        # JSONB array of {email, displayName, responseStatus} objects.
        # GIN-indexed for lead-by-email containment queries.
        sa.Column("attendees", postgresql.JSONB, nullable=True),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "is_all_day",
            sa.Boolean(),
            server_default=sa.text("FALSE"),
            nullable=False,
        ),
        sa.Column("event_link", sa.Text(), nullable=True),
        # 'confirmed', 'tentative', or 'cancelled' from Google's status field.
        sa.Column("status", sa.String(32), nullable=True),
        # NULL for one-off events; populated for instances expanded from
        # a recurring definition.
        sa.Column("recurring_event_id", sa.String(256), nullable=True),
        # Cached title + description + attendees concatenation used by
        # the embed worker. Re-computed at upsert time.
        sa.Column("extracted_text", sa.Text(), nullable=True),
        # sha256(extracted_text)[:64] — diff key against the most recent
        # row in `embeddings` to decide whether to re-embed.
        sa.Column("content_hash", sa.String(64), nullable=True),
        sa.Column("last_extracted_at", sa.DateTime(timezone=True), nullable=True),
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
            "provider_event_id", "connected_via_user_id",
            name="uq_google_calendar_events_provider_user",
        ),
    )
    op.create_index(
        "ix_google_calendar_events_user_start",
        "google_calendar_events",
        ["connected_via_user_id", sa.text("start_time DESC")],
        unique=False,
    )
    # GIN on attendees for the lead-detail Events card and the chat
    # agent's query_calendar(attendee_email_contains=...) tool.
    op.execute(
        "CREATE INDEX ix_google_calendar_events_attendees "
        "ON google_calendar_events USING GIN (attendees)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_google_calendar_events_attendees")
    op.drop_index(
        "ix_google_calendar_events_user_start",
        table_name="google_calendar_events",
    )
    op.drop_table("google_calendar_events")
