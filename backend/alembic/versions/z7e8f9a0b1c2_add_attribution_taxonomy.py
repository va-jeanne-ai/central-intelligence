"""Mirror WGR attribution_taxonomy (read-time channel normalization).

observed_* columns are Text — they are UTM values (unbounded upstream text;
String(n) would crash the sync on an oversize value).

Revision ID: z7e8f9a0b1c2
Revises: y6d7e8f9a0b1
Create Date: 2026-07-27 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "z7e8f9a0b1c2"
down_revision: Union[str, None] = "y6d7e8f9a0b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "attribution_taxonomy",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=False),
        sa.Column("observed_source", sa.Text(), nullable=True),
        sa.Column("observed_medium", sa.Text(), nullable=True),
        sa.Column("observed_content", sa.Text(), nullable=True),
        sa.Column("canonical_channel", sa.String(128), nullable=False),
        sa.Column("platform", sa.String(64), nullable=True),
        sa.Column("include_in_channel_reporting", sa.Boolean(), nullable=False,
                  server_default=sa.text("true")),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_attribution_taxonomy_channel", "attribution_taxonomy",
                    ["canonical_channel"])


def downgrade() -> None:
    op.drop_index("ix_attribution_taxonomy_channel", table_name="attribution_taxonomy")
    op.drop_table("attribution_taxonomy")
