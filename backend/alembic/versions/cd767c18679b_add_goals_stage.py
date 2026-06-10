"""add goals.stage

Revision ID: cd767c18679b
Revises: ca825332c707
Create Date: 2026-06-10 15:01:21.884477

Hand-trimmed: autogenerate also proposed dropping ~13 unrelated indexes and
altering integrations.status default (autogenerate drift). Only the goals.stage
column + its index are intended here.

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cd767c18679b'
down_revision: Union[str, None] = 'ca825332c707'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('goals', sa.Column('stage', sa.String(length=32), nullable=True))
    op.create_index(op.f('ix_goals_stage'), 'goals', ['stage'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_goals_stage'), table_name='goals')
    op.drop_column('goals', 'stage')
