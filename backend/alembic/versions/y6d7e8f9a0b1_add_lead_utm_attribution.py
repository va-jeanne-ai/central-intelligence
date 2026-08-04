"""Add lead UTM attribution columns + ghl_contact_id (WGR mirror).

Mirrors Greg's webhook-captured first/last-touch UTMs so CI can resolve
canonical channel at read time (deliverable 9). Hand-written per project rule.
UTM columns are Text — upstream is unbounded text; String(n) would crash the
sync on an oversize value (audit r5 #9).

Revision ID: y6d7e8f9a0b1
Revises: x5c6d7e8f9a0
Create Date: 2026-07-27 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "y6d7e8f9a0b1"
down_revision: Union[str, None] = "x5c6d7e8f9a0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_COLS = [
    ("ghl_contact_id", sa.String(128)),   # fixed-format GHL id
    ("utm_source_first", sa.Text()),      # upstream is unbounded text
    ("utm_medium_first", sa.Text()),
    ("utm_campaign_first", sa.Text()),
    ("utm_content_first", sa.Text()),
    ("utm_source_last", sa.Text()),
    ("utm_medium_last", sa.Text()),
    ("utm_campaign_last", sa.Text()),
    ("utm_content_last", sa.Text()),
]


def upgrade() -> None:
    for name, type_ in _COLS:
        op.add_column("leads", sa.Column(name, type_, nullable=True))
    op.create_index("ix_leads_ghl_contact_id", "leads", ["ghl_contact_id"])
    op.create_index("ix_leads_utm_source_first", "leads", ["utm_source_first"])


def downgrade() -> None:
    op.drop_index("ix_leads_utm_source_first", table_name="leads")
    op.drop_index("ix_leads_ghl_contact_id", table_name="leads")
    for name, _ in reversed(_COLS):
        op.drop_column("leads", name)
