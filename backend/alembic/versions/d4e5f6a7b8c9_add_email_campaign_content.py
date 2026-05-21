"""add audience_name, segment_text, body_html, archive_url to email_campaigns

The Mailchimp connector pulls additional read-only data per campaign:
- audience_name: list name the campaign was sent to
- segment_text: free-text description of the segment (when sent to a slice)
- body_html: rendered HTML body from /3.0/campaigns/{id}/content
- archive_url: public Mailchimp archive link for the campaign

Surfaced in the click-to-expand row on /marketing/email.

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-05-21 04:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "email_campaigns",
        sa.Column("audience_name", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "email_campaigns",
        sa.Column("segment_text", sa.Text(), nullable=True),
    )
    op.add_column(
        "email_campaigns",
        sa.Column("body_html", sa.Text(), nullable=True),
    )
    op.add_column(
        "email_campaigns",
        sa.Column("archive_url", sa.String(length=1024), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("email_campaigns", "archive_url")
    op.drop_column("email_campaigns", "body_html")
    op.drop_column("email_campaigns", "segment_text")
    op.drop_column("email_campaigns", "audience_name")
