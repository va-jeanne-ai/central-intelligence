"""Add consecutive_clear_nights to foresight_recommendations (gate-integrity fix).

Persists the hysteresis state machine's streak counter (see
app.services.foresight.apply_hysteresis): a candidate must clear the raw
statistical verdict on 2 CONSECUTIVE nightly runs before its DISPLAYED
status flips gated -> published; published -> gated flips immediately
(fail-toward-gated, no grace period). Nullable + defaulted to 0 so existing
rows (if any survive a prior run) don't need backfilling — they're treated
as "no streak yet" on the next compute, which is the safe (gated) direction.

Revision ID: 158699f25a23
Revises: f1a2b3c4d5e6
Create Date: 2026-08-07 12:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "158699f25a23"
down_revision: Union[str, None] = "f1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "foresight_recommendations",
        sa.Column(
            "consecutive_clear_nights",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    op.drop_column("foresight_recommendations", "consecutive_clear_nights")
