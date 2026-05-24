"""add composite index on audit_log (table_name, record_id, created_at DESC)

The audit_log table predates this change (it shipped with the Sprint 3
schema clean-up) but nothing wrote to it until the lead-history feature
landed. Per-column indexes on table_name / created_at / user_id already
exist and would force a bitmap-or for the dominant query:

    SELECT * FROM audit_log
    WHERE table_name = 'leads' AND record_id = :lead_id
    ORDER BY created_at DESC

A single composite index keyed in the same order is a clean B-tree scan
and lets the planner walk the index in reverse for newest-first ordering.

Revision ID: h8c9d0e1f2g3
Revises: g7b8c9d0e1f2
Create Date: 2026-05-21 23:00:00.000000
"""

from typing import Sequence, Union

from alembic import op

revision: str = "h8c9d0e1f2g3"
down_revision: Union[str, None] = "g7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE INDEX ix_audit_log_record_lookup
        ON audit_log (table_name, record_id, created_at DESC)
        """
    )


def downgrade() -> None:
    op.drop_index("ix_audit_log_record_lookup", table_name="audit_log")
