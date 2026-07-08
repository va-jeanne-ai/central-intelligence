"""add period discriminator to overall_insights for the weekly digest

Reuses the ``overall_insights`` table for the new weekly digest rather than
introducing a parallel table: same shape (verdict + narrative + key_shifts +
evidence + model), same LLM-phrases-evidence contract, same compounding-via-
previous_insight_id pattern — the only real difference is cadence and the
date range summarized.

``period`` discriminates 'daily' (the existing per-day assessment, unchanged
behavior — existing rows backfill to 'daily') from 'weekly' (the new digest).
``period_end`` is NULL for daily rows (a single day needs no range) and holds
the last day of the covered week for weekly rows (``insight_date`` holds the
first day, i.e. the Monday the digest covers back from).

The old uniqueness on ``insight_date`` alone would collide a weekly digest
with whatever daily row happens to land on the same date, so it's replaced
with ``(insight_date, period)`` — one row per day per period-kind, which
still gives the daily task the exact idempotency it had before (period
defaults to 'daily' there) and gives the weekly task its own idempotent slot.

Revision ID: u2f3a4b5c6d7
Revises: t1e2f3a4b5c6
Create Date: 2026-07-08 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "u2f3a4b5c6d7"
down_revision: Union[str, None] = "t1e2f3a4b5c6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "overall_insights",
        sa.Column("period", sa.String(length=16), nullable=False, server_default="daily"),
    )
    op.add_column(
        "overall_insights",
        sa.Column("period_end", sa.Date(), nullable=True),
    )

    # Replace the date-only uniqueness with (insight_date, period) so a weekly
    # digest and a daily assessment can coexist on the same calendar date.
    op.drop_constraint("uq_overall_insights_date", "overall_insights", type_="unique")
    op.create_unique_constraint(
        "uq_overall_insights_date_period",
        "overall_insights",
        ["insight_date", "period"],
    )

    op.create_index(
        "ix_overall_insights_period",
        "overall_insights",
        ["period"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_overall_insights_period", table_name="overall_insights")
    op.drop_constraint("uq_overall_insights_date_period", "overall_insights", type_="unique")
    op.create_unique_constraint("uq_overall_insights_date", "overall_insights", ["insight_date"])
    op.drop_column("overall_insights", "period_end")
    op.drop_column("overall_insights", "period")
