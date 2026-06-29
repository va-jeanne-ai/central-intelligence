"""add overall_insights table

Revision ID: s0d1e2f3a4b5
Revises: r9c0d1e2f3a4
Create Date: 2026-06-30

Daily, LLM-synthesized company-level health assessment (data-intelligence engine).
Unlike per-metric recommendations, this is a holistic narrative that compounds day
over day via a self-referential ``previous_insight_id``. One row per ``insight_date``
(idempotent: a regenerate upserts the same day). Hand-written to avoid autogenerate
drift on this DB.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "s0d1e2f3a4b5"
down_revision: Union[str, None] = "r9c0d1e2f3a4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "overall_insights",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("insight_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="published"),
        sa.Column("health_verdict", sa.String(length=16), nullable=False),
        sa.Column("narrative", sa.Text(), nullable=False),
        sa.Column("key_shifts", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("model", sa.String(length=64), nullable=False),
        sa.Column("previous_insight_id", sa.Integer(), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["previous_insight_id"],
            ["overall_insights.id"],
            name="fk_overall_insights_previous",
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint("insight_date", name="uq_overall_insights_date"),
    )
    op.create_index(
        op.f("ix_overall_insights_insight_date"), "overall_insights", ["insight_date"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_overall_insights_insight_date"), table_name="overall_insights")
    op.drop_table("overall_insights")
