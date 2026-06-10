"""add appointments table

Revision ID: ca825332c707
Revises: 6802177b2e45
Create Date: 2026-06-09 02:49:08.125870

Hand-trimmed: autogenerate also proposed dropping ~13 unrelated indexes and
altering integrations.status default (autogenerate drift — those objects exist
in the DB but aren't reflected in metadata the same way). Only the appointments
table + its indexes are intended here.

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ca825332c707'
down_revision: Union[str, None] = '6802177b2e45'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'appointments',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('lead_id', sa.UUID(), nullable=True),
        sa.Column('member_id', sa.UUID(), nullable=True),
        sa.Column('contact_name', sa.String(length=255), nullable=True),
        sa.Column('contact_email', sa.String(length=255), nullable=True),
        sa.Column('contact_phone', sa.String(length=50), nullable=True),
        sa.Column('status', sa.String(length=64), nullable=True),
        sa.Column('appointment_type', sa.String(length=128), nullable=True),
        sa.Column('scheduled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('end_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('source', sa.String(length=128), nullable=True),
        sa.Column('external_id', sa.String(length=128), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_by', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['lead_id'], ['leads.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['member_id'], ['members.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_appointments_contact_email'), 'appointments', ['contact_email'], unique=False)
    op.create_index(op.f('ix_appointments_external_id'), 'appointments', ['external_id'], unique=False)
    op.create_index(op.f('ix_appointments_lead_id'), 'appointments', ['lead_id'], unique=False)
    op.create_index(op.f('ix_appointments_member_id'), 'appointments', ['member_id'], unique=False)
    op.create_index(op.f('ix_appointments_scheduled_at'), 'appointments', ['scheduled_at'], unique=False)
    op.create_index(op.f('ix_appointments_status'), 'appointments', ['status'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_appointments_status'), table_name='appointments')
    op.drop_index(op.f('ix_appointments_scheduled_at'), table_name='appointments')
    op.drop_index(op.f('ix_appointments_member_id'), table_name='appointments')
    op.drop_index(op.f('ix_appointments_lead_id'), table_name='appointments')
    op.drop_index(op.f('ix_appointments_external_id'), table_name='appointments')
    op.drop_index(op.f('ix_appointments_contact_email'), table_name='appointments')
    op.drop_table('appointments')
