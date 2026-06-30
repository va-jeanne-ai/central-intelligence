"""Chat session + message models for persistent chat history.

The chat surface was in-memory only until this module landed; refreshes
and backend restarts erased every conversation. These two tables back
the sidebar history list, the CRUD endpoints, and the full-context
replay when a user reopens an old chat.

Hard-delete by design — no ``SoftDeleteMixin``. Users prune their own
history, and chat data isn't audit-load-bearing the way leads are.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class ChatSession(Base, TimestampMixin):
    """One chat conversation belonging to one user.

    The agent's in-memory ``conversation_history`` mirrors this row's
    messages — but the DB is the source of truth. On session reload we
    SELECT messages by ``session_id`` ORDER BY ``created_at`` and feed
    the list into ``BaseAgent.set_conversation_history`` before the
    next user turn.
    """

    __tablename__ = "chat_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Which agent surface owns this session. NULL = Central Intelligence (the
    # original /chat surface); a director slug (e.g. 'marketing-director') for a
    # department-director chat. Scopes the history sidebar per surface so
    # directors don't share CI's list. See routes/chat_sessions.list filter.
    agent_slug: Mapped[str | None] = mapped_column(
        String(64), nullable=True,
    )
    # First ~60 chars of the user's first message + '…' if truncated.
    # User-editable later via PATCH /chat/sessions/{id}.
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    # Denormalised newest-message timestamp so the sidebar list-sort
    # doesn't JOIN messages on every refresh.
    last_message_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    messages: Mapped[list["ChatMessage"]] = relationship(
        "ChatMessage",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ChatMessage.created_at",
        lazy="select",
    )


class ChatMessage(Base):
    """One user or assistant turn inside a ChatSession.

    ``content`` is the plain-text rendering shown in the UI.
    ``content_blocks`` carries the full Anthropic-API-shape serialised
    message (text + tool_use + tool_result blocks) and is only populated
    for assistant turns that involved tool calls — so we can replay the
    full agent state, not just the visible text.
    """

    __tablename__ = "chat_messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_blocks: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    session: Mapped["ChatSession"] = relationship(
        "ChatSession", back_populates="messages",
    )
