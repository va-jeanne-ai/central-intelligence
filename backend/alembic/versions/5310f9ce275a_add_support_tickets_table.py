"""add support_tickets table

Revision ID: 5310f9ce275a
Revises: cd767c18679b
Create Date: 2026-06-10

Hand-trimmed: autogenerate also proposed dropping ~13 unrelated indexes and
altering integrations.status default (autogenerate drift). Only the
support_tickets table + its indexes are intended here.

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5310f9ce275a'
down_revision: Union[str, None] = 'cd767c18679b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'support_tickets',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('member_id', sa.UUID(), nullable=True),
        sa.Column('contact_name', sa.String(length=255), nullable=True),
        sa.Column('contact_email', sa.String(length=255), nullable=True),
        sa.Column('subject', sa.String(length=255), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('category', sa.String(length=64), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('priority', sa.String(length=16), nullable=True),
        sa.Column('resolution', sa.Text(), nullable=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('source', sa.String(length=32), nullable=True),
        sa.Column('created_by', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['member_id'], ['members.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_support_tickets_category'), 'support_tickets', ['category'], unique=False)
    op.create_index(op.f('ix_support_tickets_contact_email'), 'support_tickets', ['contact_email'], unique=False)
    op.create_index(op.f('ix_support_tickets_member_id'), 'support_tickets', ['member_id'], unique=False)
    op.create_index(op.f('ix_support_tickets_status'), 'support_tickets', ['status'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_support_tickets_status'), table_name='support_tickets')
    op.drop_index(op.f('ix_support_tickets_member_id'), table_name='support_tickets')
    op.drop_index(op.f('ix_support_tickets_contact_email'), table_name='support_tickets')
    op.drop_index(op.f('ix_support_tickets_category'), table_name='support_tickets')
    op.drop_table('support_tickets')
