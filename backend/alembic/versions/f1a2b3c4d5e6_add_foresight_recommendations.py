"""Add foresight_recommendations table (P1 statistics engine).

Nightly full-overwrite snapshot of computed Foresight cards (published_lift/
published_warning/gated) — see docs/superpowers/plans/
2026-08-06-foresight-layer-prototype.md "P1 architecture (as built)". This is
OUR table (computed from a nightly Celery task), not a WGR mirror, so no
snapshot-reconcile machinery is needed — delete+insert in one transaction is
fine at this size (5 candidate rows).

Revision ID: f1a2b3c4d5e6
Revises: c2df94038d03
Create Date: 2026-08-07 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, None] = "c2df94038d03"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "foresight_recommendations",
        sa.Column("id", sa.String(64), primary_key=True),  # candidate slug, e.g. "live_watch"
        sa.Column("status", sa.String(32), nullable=False),  # published_lift/published_warning/gated
        sa.Column("confidence", sa.String(16), nullable=True),  # High/Medium, null when gated
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("department", sa.String(32), nullable=False),
        sa.Column("hindsight_headline", sa.Text(), nullable=False),
        sa.Column("hindsight_detail", sa.Text(), nullable=False),
        sa.Column("evidence_href", sa.Text(), nullable=False),
        sa.Column("evidence_label", sa.Text(), nullable=False),
        sa.Column("insight_text", sa.Text(), nullable=False),
        sa.Column("action_text", sa.Text(), nullable=False),
        sa.Column("lift_text", sa.Text(), nullable=False),
        sa.Column("hold_reason", sa.Text(), nullable=True),
        sa.Column("baseline_label", sa.Text(), nullable=False),
        sa.Column("baseline_rate", sa.Float(), nullable=False),
        sa.Column("baseline_low", sa.Float(), nullable=False),
        sa.Column("baseline_high", sa.Float(), nullable=False),
        sa.Column("variant_label", sa.Text(), nullable=False),
        sa.Column("variant_rate", sa.Float(), nullable=False),
        sa.Column("variant_low", sa.Float(), nullable=False),
        sa.Column("variant_high", sa.Float(), nullable=False),
        sa.Column("n_label", sa.Text(), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_foresight_recommendations_status", "foresight_recommendations", ["status"]
    )


def downgrade() -> None:
    op.drop_index(
        "ix_foresight_recommendations_status", table_name="foresight_recommendations"
    )
    op.drop_table("foresight_recommendations")
