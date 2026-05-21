"""add email_campaigns.blocks_json column

JSON-serialized Block[] from the compose page-builder. Lets us round-trip
draft editing: load a saved draft → parse blocks → user edits → save back
to the same row. Nullable for legacy rows and Mailchimp-sourced rows
(both of which have body_html only).

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-05-21 06:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "email_campaigns",
        sa.Column("blocks_json", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("email_campaigns", "blocks_json")
