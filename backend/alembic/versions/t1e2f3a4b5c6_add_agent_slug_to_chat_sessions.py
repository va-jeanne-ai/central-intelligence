"""add agent_slug to chat_sessions for per-director history scoping

Chat history was Central-Intelligence-only. To give each department director
(marketing / sales / fulfillment) its own history sidebar without bleeding
sessions across surfaces, every chat session now records which agent it
belongs to.

``agent_slug`` is NULL for Central Intelligence sessions (the original
surface — keeps every existing row valid and unchanged) and the director slug
(e.g. ``marketing-director``) for a director session. The list endpoint filters
with ``agent_slug IS NOT DISTINCT FROM :slug`` so NULL ⇒ CI-only and a slug ⇒
that director only.

Revision ID: t1e2f3a4b5c6
Revises: s0d1e2f3a4b5
Create Date: 2026-06-30 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "t1e2f3a4b5c6"
down_revision: Union[str, None] = "s0d1e2f3a4b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Nullable: existing CI sessions stay NULL and keep working untouched.
    op.add_column(
        "chat_sessions",
        sa.Column("agent_slug", sa.String(64), nullable=True),
    )
    # The sidebar query is "this user's sessions for this surface, newest
    # first." Index (user_id, agent_slug) so that filter stays cheap; the
    # existing ix_chat_sessions_user_recent still serves the recency sort.
    op.create_index(
        "ix_chat_sessions_user_agent",
        "chat_sessions",
        ["user_id", "agent_slug"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_chat_sessions_user_agent", table_name="chat_sessions")
    op.drop_column("chat_sessions", "agent_slug")
