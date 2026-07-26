"""Mirror WGR lead_engagements (attribution touches).

UTM/page_url columns are Text — unbounded upstream. Probe 2026-07-26 found
the table empty upstream (Greg's email-attribution flow not producing yet);
the mirror ships anyway and fills when it goes live.

Revision ID: a8f9a0b1c2d3
Revises: z7e8f9a0b1c2
Create Date: 2026-07-27 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a8f9a0b1c2d3"
down_revision: Union[str, None] = "z7e8f9a0b1c2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "lead_engagements",
        sa.Column("engagement_id", sa.String(128), primary_key=True),
        sa.Column("wgr_lead_id", sa.String(128), nullable=True),
        sa.Column("ghl_contact_id", sa.String(128), nullable=True),
        sa.Column("engagement_type", sa.String(64), nullable=True),
        sa.Column("engagement_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("utm_source", sa.Text(), nullable=True),
        sa.Column("utm_medium", sa.Text(), nullable=True),
        sa.Column("utm_campaign", sa.Text(), nullable=True),
        sa.Column("utm_content", sa.Text(), nullable=True),
        sa.Column("source_type", sa.String(64), nullable=True),
        sa.Column("email_campaign_id", sa.String(128), nullable=True),
        sa.Column("email_id", sa.String(128), nullable=True),
        sa.Column("offer_id", sa.String(128), nullable=True),
        sa.Column("page_url", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
    for col in ("wgr_lead_id", "ghl_contact_id", "engagement_type",
                "engagement_date", "email_id"):
        op.create_index(f"ix_lead_engagements_{col}", "lead_engagements", [col])


def downgrade() -> None:
    for col in ("email_id", "engagement_date", "engagement_type",
                "ghl_contact_id", "wgr_lead_id"):
        op.drop_index(f"ix_lead_engagements_{col}", table_name="lead_engagements")
    op.drop_table("lead_engagements")
