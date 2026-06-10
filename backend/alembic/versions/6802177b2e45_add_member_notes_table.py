"""add member_notes table

Revision ID: 6802177b2e45
Revises: m4d5e6f7a8b9
Create Date: 2026-06-08 22:00:28.181635

Hand-trimmed: autogenerate also proposed dropping ~13 unrelated indexes and
altering integrations.status default (autogenerate drift — those objects exist
in the DB but aren't reflected in metadata the same way). Only the member_notes
table + its index are intended here.

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6802177b2e45'
down_revision: Union[str, None] = 'm4d5e6f7a8b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'member_notes',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('member_id', sa.UUID(), nullable=False),
        sa.Column('author_id', sa.UUID(), nullable=True),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['author_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['member_id'], ['members.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_member_notes_member_id'), 'member_notes', ['member_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_member_notes_member_id'), table_name='member_notes')
    op.drop_table('member_notes')
