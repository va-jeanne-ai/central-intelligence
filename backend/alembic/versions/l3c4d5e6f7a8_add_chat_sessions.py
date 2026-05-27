"""add chat_sessions + chat_messages for persistent chat history

Today the chat surface holds every conversation in an in-memory dict
inside ``routes/central_intelligence.py``. Refreshing the page or
restarting the backend wipes every session. This migration lands the
storage layer so:

  * The /chat sidebar can list a user's past sessions.
  * The agent's conversation_history can be replayed from the DB when
    a user re-opens an old chat (the agent then has full context for
    follow-up turns).
  * Hard delete (no SoftDeleteMixin) — the explicit goal is letting
    users prune their own history to free up space.

``chat_messages.content_blocks`` carries the Anthropic-API-shape
serialised message (tool_use + tool_result + text blocks) for any
assistant turn that involved tool calls. Plain user turns + plain
assistant text leave it NULL.

Revision ID: l3c4d5e6f7a8
Revises: k2b3c4d5e6f7
Create Date: 2026-05-28 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "l3c4d5e6f7a8"
down_revision: Union[str, None] = "k2b3c4d5e6f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "chat_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # First ~60 chars of the user's first message, with '…' if
        # truncated. PATCH /chat/sessions/{id} can rewrite it later.
        sa.Column("title", sa.String(120), nullable=False),
        # Denormalised so the sidebar's "newest first" sort doesn't
        # JOIN against chat_messages on every refresh. Set on every
        # append_message() call.
        sa.Column(
            "last_message_at", sa.DateTime(timezone=True), nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )
    # Sidebar query: "all of this user's sessions, newest first" is
    # the dominant access pattern. Composite index keeps the LIMIT
    # cheap as a user accumulates sessions.
    op.create_index(
        "ix_chat_sessions_user_recent",
        "chat_sessions",
        ["user_id", sa.text("last_message_at DESC")],
        unique=False,
    )

    op.create_table(
        "chat_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("chat_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # 'user' or 'assistant'. Anthropic also has 'tool_result' on
        # the API but those are nested inside an assistant turn; we
        # capture them via content_blocks rather than a separate role.
        sa.Column("role", sa.String(16), nullable=False),
        # Plain-text rendering for the UI. For assistant turns with
        # tool_use blocks this is just the visible text portion.
        sa.Column("content", sa.Text(), nullable=False),
        # Anthropic-API-shape serialised content blocks — populated when
        # the assistant turn involves tool_use / tool_result so we can
        # replay the full agent state into conversation_history on
        # session reload. NULL for plain text turns.
        sa.Column("content_blocks", postgresql.JSONB, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_chat_messages_session_order",
        "chat_messages",
        ["session_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_chat_messages_session_order", table_name="chat_messages")
    op.drop_table("chat_messages")
    op.drop_index("ix_chat_sessions_user_recent", table_name="chat_sessions")
    op.drop_table("chat_sessions")
