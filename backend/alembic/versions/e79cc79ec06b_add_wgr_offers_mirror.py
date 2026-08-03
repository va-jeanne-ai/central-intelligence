"""Mirror WGR offers + offer_mappings (real product catalog).

The app's own `offers` table is CRUD test data (18 rows: "This is a new
offer", "just checking") — never clobbered. The real catalog lives in WGR:
`offers` (11 rows) and `offer_mappings` (15 rows, per-program payment-level
rows). Both are small, upstream-owned tables with no watermark, so they sync
via snapshot reconcile (same precedent as `lead_journey` / `meta_campaigns`).
`offer_mappings` has no upstream primary key — `(program, payment_level,
offer_id)` is verified unique across all 15 rows (probe 2026-08-04) and is
used as the CI primary key (`id`, a deterministic composite string built by
the mapper).

Revision ID: e79cc79ec06b
Revises: c0d1e2f3a4b5
Create Date: 2026-08-04 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e79cc79ec06b"
down_revision: Union[str, None] = "c0d1e2f3a4b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "wgr_offers",
        sa.Column("offer_id", sa.String(128), primary_key=True),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("offer_type", sa.String(128), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("price", sa.Numeric(10, 2), nullable=True),
        sa.Column("status", sa.String(64), nullable=True),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "wgr_offer_mappings",
        sa.Column("id", sa.String(384), primary_key=True),
        sa.Column("program", sa.Text(), nullable=True),
        sa.Column("payment_level", sa.Text(), nullable=True),
        sa.Column("offer_id", sa.String(128), nullable=True),
        sa.Column("amount_collected", sa.Numeric(10, 2), nullable=True),
        sa.Column("revenue_earned", sa.Numeric(10, 2), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_wgr_offer_mappings_offer_id", "wgr_offer_mappings", ["offer_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_wgr_offer_mappings_offer_id", table_name="wgr_offer_mappings")
    op.drop_table("wgr_offer_mappings")
    op.drop_table("wgr_offers")
