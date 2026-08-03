"""Mirror WGR lead_journey (per-lead journey summary).

One row per WGR lead: webinar watch behavior, appointment history summary,
sales progression (close date / amount collected / days to close), and
WGR's own first/last channel labels. Upstream rebuilds this table (no
watermark, no PK there — lead_id verified unique/non-null on 12,818 rows,
probe 2026-08-03), so the sync mirrors it via snapshot reconcile.

Revision ID: c0d1e2f3a4b5
Revises: b9a0b1c2d3e4
Create Date: 2026-08-03 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c0d1e2f3a4b5"
down_revision: Union[str, None] = "b9a0b1c2d3e4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "lead_journey",
        sa.Column("lead_id", sa.String(128), primary_key=True),
        sa.Column("ghl_contact_id", sa.String(128), nullable=True),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("entry_date", sa.Date(), nullable=True),
        sa.Column("utm_source_first", sa.Text(), nullable=True),
        sa.Column("utm_medium_first", sa.Text(), nullable=True),
        sa.Column("utm_content_first", sa.Text(), nullable=True),
        sa.Column("channel_first", sa.Text(), nullable=True),
        sa.Column("attr_derived_from", sa.Text(), nullable=True),
        sa.Column("attr_order_evidence", sa.Text(), nullable=True),
        sa.Column("utm_source_last", sa.Text(), nullable=True),
        sa.Column("utm_medium_last", sa.Text(), nullable=True),
        sa.Column("channel_last", sa.Text(), nullable=True),
        sa.Column("commenter_link_status", sa.Text(), nullable=True),
        sa.Column("first_comment_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("comment_keyword", sa.Text(), nullable=True),
        sa.Column("webinar_count", sa.BigInteger(), nullable=True),
        sa.Column("webinar_registered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("watched_live", sa.Boolean(), nullable=True),
        sa.Column("watched_replay", sa.Boolean(), nullable=True),
        sa.Column("watch_seconds_total", sa.BigInteger(), nullable=True),
        sa.Column("last_opted_in_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("appt_count", sa.BigInteger(), nullable=True),
        sa.Column("first_appt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_appt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_appt_outcome", sa.Text(), nullable=True),
        sa.Column("last_appt_booked_by", sa.Text(), nullable=True),
        sa.Column("last_appt_source", sa.Text(), nullable=True),
        sa.Column("call_count", sa.BigInteger(), nullable=True),
        sa.Column("first_call_date", sa.Date(), nullable=True),
        sa.Column("discovery_occurred", sa.Boolean(), nullable=True),
        sa.Column("discovery_held", sa.Boolean(), nullable=True),
        sa.Column("sale_id", sa.String(128), nullable=True),
        sa.Column("close_date", sa.Date(), nullable=True),
        sa.Column("amount_collected", sa.Float(), nullable=True),
        sa.Column("days_to_close", sa.Integer(), nullable=True),
        sa.Column("journey_gap", sa.Text(), nullable=True),
        sa.Column("appt_qualified", sa.Boolean(), nullable=True),
        sa.Column("appt_flagged", sa.Boolean(), nullable=True),
        sa.Column("appt_qual_grade", sa.Text(), nullable=True),
    )
    op.create_index("ix_lead_journey_ghl_contact_id", "lead_journey", ["ghl_contact_id"])


def downgrade() -> None:
    op.drop_index("ix_lead_journey_ghl_contact_id", table_name="lead_journey")
    op.drop_table("lead_journey")
