"""add instance_profile table

Revision ID: x5c6d7e8f9a0
Revises: w4b5c6d7e8f9
Create Date: 2026-07-15 00:00:00.000000

Productization Phase 1: per-instance company profile (vertical, terminology,
benchmarks, white-label branding, currency/locale) that AI prompts and the
frontend read instead of hardcoded literals. CI-owned — deliberately separate
from the synced business_profile table, which the client source sync
overwrites. Not seeded here: each deployment seeds its own row via
scripts/seed_instance_profile.py (Greg's instance seeds today's literals so
behavior is unchanged).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = 'x5c6d7e8f9a0'
down_revision: Union[str, None] = 'w4b5c6d7e8f9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'instance_profile',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column('business_name', sa.String(length=255), nullable=True),
        sa.Column('vertical', sa.String(length=255), nullable=True),
        sa.Column('business_description', sa.Text(), nullable=True),
        sa.Column('target_audience', sa.Text(), nullable=True),
        sa.Column('brand_voice', sa.Text(), nullable=True),
        sa.Column('vertical_context', JSONB(), nullable=True),
        sa.Column('terminology', JSONB(), nullable=True),
        sa.Column('benchmarks', JSONB(), nullable=True),
        sa.Column('app_name', sa.String(length=255), nullable=True),
        sa.Column('tagline', sa.String(length=255), nullable=True),
        sa.Column('logo_url', sa.String(length=1024), nullable=True),
        sa.Column('colors', JSONB(), nullable=True),
        sa.Column('currency_code', sa.String(length=8), nullable=True),
        sa.Column('currency_symbol', sa.String(length=8), nullable=True),
        sa.Column('timezone', sa.String(length=64), nullable=True),
        sa.Column('locale', sa.String(length=16), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('instance_profile')
