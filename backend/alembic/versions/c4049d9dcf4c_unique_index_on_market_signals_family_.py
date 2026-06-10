"""unique index on market_signals (signal_family, signal)

Revision ID: c4049d9dcf4c
Revises: 5310f9ce275a
Create Date: 2026-06-10

Hand-trimmed: autogenerate also proposed dropping ~13 unrelated indexes and
altering integrations.status default (autogenerate drift). Only the
market_signals unique constraint is intended here — it's the aggregation key the
market-signals recompute job upserts on (INSERT ... ON CONFLICT).

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'c4049d9dcf4c'
down_revision: Union[str, None] = '5310f9ce275a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_unique_constraint(
        'uq_market_signals_family_signal', 'market_signals', ['signal_family', 'signal']
    )


def downgrade() -> None:
    op.drop_constraint('uq_market_signals_family_signal', 'market_signals', type_='unique')
