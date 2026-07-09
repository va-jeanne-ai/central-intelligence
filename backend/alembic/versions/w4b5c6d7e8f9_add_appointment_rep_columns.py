"""add rep_id and appointment_owner to appointments

Revision ID: w4b5c6d7e8f9
Revises: v3a4b5c6d7e8
Create Date: 2026-07-09 00:00:00.000000

Client feedback (Greg): Appointments/Sales Calls need rep filtering + display.
The upstream WGR mirror's appointments table carries rep_id + appointment_owner
(display name) that our sync previously dropped. This adds the two columns so
the WGR sync mapping can populate them and the /appointments endpoint can
filter/join on rep_id, falling back to the raw appointment_owner display name
for reps not in the sales_reps roster (e.g. former reps like Ryan Verey).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'w4b5c6d7e8f9'
down_revision: Union[str, None] = 'v3a4b5c6d7e8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('appointments', sa.Column('rep_id', sa.String(length=64), nullable=True))
    op.add_column('appointments', sa.Column('appointment_owner', sa.String(length=255), nullable=True))
    op.create_index(op.f('ix_appointments_rep_id'), 'appointments', ['rep_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_appointments_rep_id'), table_name='appointments')
    op.drop_column('appointments', 'appointment_owner')
    op.drop_column('appointments', 'rep_id')
