"""Mirror WGR Meta Ads tables (campaigns, ads, daily performance).

Probe 2026-07-26: 29 campaigns / 472 ads / 635 perf rows upstream — gate GO.
Free-text columns are Text (unbounded upstream).

Revision ID: b9a0b1c2d3e4
Revises: a8f9a0b1c2d3
Create Date: 2026-07-27 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b9a0b1c2d3e4"
down_revision: Union[str, None] = "a8f9a0b1c2d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "meta_campaigns",
        sa.Column("campaign_id", sa.String(128), primary_key=True),
        sa.Column("meta_campaign_id", sa.String(128), nullable=True),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("campaign_type", sa.String(64), nullable=True),
        sa.Column("objective", sa.String(128), nullable=True),
        sa.Column("status", sa.String(64), nullable=True),
        sa.Column("daily_budget", sa.Numeric(10, 2), nullable=True),
        sa.Column("lifetime_budget", sa.Numeric(10, 2), nullable=True),
        sa.Column("targeting_type", sa.String(64), nullable=True),
        sa.Column("targeting_notes", sa.Text(), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "meta_ads",
        sa.Column("ad_id", sa.String(128), primary_key=True),
        sa.Column("campaign_id", sa.String(128), nullable=True),
        sa.Column("meta_ad_id", sa.String(128), nullable=True),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("ad_format", sa.String(64), nullable=True),
        sa.Column("status", sa.String(64), nullable=True),
        sa.Column("hook_text", sa.Text(), nullable=True),
        sa.Column("hook_type", sa.String(128), nullable=True),
        sa.Column("script_body", sa.Text(), nullable=True),
        sa.Column("script_cta", sa.Text(), nullable=True),
        sa.Column("framework_used", sa.String(64), nullable=True),
        sa.Column("offer_id", sa.String(128), nullable=True),
        sa.Column("target_audience", sa.Text(), nullable=True),
        sa.Column("calendar_entry_id", sa.String(128), nullable=True),
        sa.Column("parent_ad_id", sa.String(128), nullable=True),
        sa.Column("iteration_notes", sa.Text(), nullable=True),
        sa.Column("result", sa.Text(), nullable=True),
        sa.Column("launched_date", sa.Date(), nullable=True),
        sa.Column("kill_date", sa.Date(), nullable=True),
        sa.Column("kill_reason", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "meta_ad_performance",
        sa.Column("perf_id", sa.String(128), primary_key=True),
        sa.Column("ad_id", sa.String(128), nullable=True),
        sa.Column("snapshot_date", sa.Date(), nullable=True),
        sa.Column("snapshot_type", sa.String(32), nullable=True),
        sa.Column("amount_spent", sa.Numeric(10, 2), nullable=True),
        sa.Column("impressions", sa.Integer(), nullable=True),
        sa.Column("reach", sa.Integer(), nullable=True),
        sa.Column("leads", sa.Integer(), nullable=True),
        sa.Column("cost_per_lead", sa.Numeric(10, 2), nullable=True),
        sa.Column("booked_calls", sa.Integer(), nullable=True),
        sa.Column("cost_per_booked_call", sa.Numeric(10, 2), nullable=True),
        sa.Column("link_clicks", sa.Integer(), nullable=True),
        sa.Column("cost_per_link_click", sa.Numeric(10, 2), nullable=True),
        sa.Column("hook_rate", sa.Numeric(5, 2), nullable=True),
        sa.Column("hold_rate", sa.Numeric(5, 2), nullable=True),
        sa.Column("ctr", sa.Numeric(5, 2), nullable=True),
        sa.Column("cpm", sa.Numeric(10, 2), nullable=True),
        sa.Column("frequency", sa.Numeric(5, 2), nullable=True),
        sa.Column("kpi_status", sa.String(64), nullable=True),
        sa.Column("metric_notes", sa.Text(), nullable=True),
        sa.Column("action_taken", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_meta_ads_campaign_id", "meta_ads", ["campaign_id"])
    op.create_index("ix_meta_ad_performance_ad_id", "meta_ad_performance", ["ad_id"])
    op.create_index("ix_meta_ad_performance_snapshot_date", "meta_ad_performance",
                    ["snapshot_date"])


def downgrade() -> None:
    op.drop_index("ix_meta_ad_performance_snapshot_date", table_name="meta_ad_performance")
    op.drop_index("ix_meta_ad_performance_ad_id", table_name="meta_ad_performance")
    op.drop_index("ix_meta_ads_campaign_id", table_name="meta_ads")
    op.drop_table("meta_ad_performance")
    op.drop_table("meta_ads")
    op.drop_table("meta_campaigns")
