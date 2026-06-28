"""add recommendations table

Revision ID: r9c0d1e2f3a4
Revises: q8b9c0d1e2f3
Create Date: 2026-06-29

Data-cited recommendations emitted by the trend layer (data-intelligence engine).
Each carries its evidence JSON (the numbers behind the conclusion) and a lifecycle
status. Hand-written to avoid autogenerate drift on this DB.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "r9c0d1e2f3a4"
down_revision: Union[str, None] = "q8b9c0d1e2f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "recommendations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("metric_key", sa.String(length=128), nullable=False),
        sa.Column("area", sa.String(length=32), nullable=False),
        sa.Column("window", sa.String(length=16), nullable=False),
        sa.Column("verdict", sa.String(length=24), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False, server_default="info"),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="open"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("metric_key", "window", name="uq_recommendations_metric_window"),
    )
    op.create_index(
        op.f("ix_recommendations_metric_key"), "recommendations", ["metric_key"], unique=False
    )
    op.create_index(op.f("ix_recommendations_area"), "recommendations", ["area"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_recommendations_area"), table_name="recommendations")
    op.drop_index(op.f("ix_recommendations_metric_key"), table_name="recommendations")
    op.drop_table("recommendations")
