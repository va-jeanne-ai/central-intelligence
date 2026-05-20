"""add call.summary column

Stores the analyzer-generated narrative summary of each call. Populated by
the Sales Call Analyzer alongside the structured Insight rows so the call
detail page can show a human-readable overview without iterating insights.

Revision ID: a1b2c3d4e5f6
Revises: ccffed696e99
Create Date: 2026-05-20 23:40:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "ccffed696e99"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("calls", sa.Column("summary", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("calls", "summary")
