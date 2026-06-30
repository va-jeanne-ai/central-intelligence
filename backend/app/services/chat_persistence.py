"""Chat session + message persistence helpers.

Used by both the SSE and WebSocket chat handlers in
``routes/central_intelligence.py``. The functions here are the only
place that read or write ``chat_sessions`` / ``chat_messages`` outside
the CRUD endpoints — keeps the persistence shape in one file.

Three public functions:

  * :func:`ensure_session` — creates the row + title on the first
    user message of a fresh session; no-op when the row already exists.
  * :func:`append_message` — INSERTs one ``chat_messages`` row and
    bumps the parent's ``last_message_at`` so the sidebar list-sort
    stays cheap.
  * :func:`load_history_for_agent` — pulls every message in
    ``created_at`` order and returns an Anthropic-API-shape list
    ready to assign to ``BaseAgent.conversation_history``.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat import ChatMessage, ChatSession

logger = logging.getLogger(__name__)


# First-message title truncation. ~60 chars catches the natural width
# of a sidebar row without forcing a tooltip on every entry.
_TITLE_MAX_CHARS = 60


def derive_title(first_user_message: str) -> str:
    """Build a sidebar title from the first user message."""
    text = (first_user_message or "").strip().replace("\n", " ")
    if not text:
        return "New chat"
    if len(text) <= _TITLE_MAX_CHARS:
        return text
    return text[:_TITLE_MAX_CHARS].rstrip() + "…"


async def ensure_session(
    db: AsyncSession,
    *,
    session_id: str,
    user_id: str,
    first_user_message: str,
    agent_slug: str | None = None,
) -> ChatSession:
    """Find-or-create a ``chat_sessions`` row.

    Idempotent — safe to call on every user message. The title is set
    on creation only; subsequent calls don't rename. The caller already
    holds the canonical ``session_id`` (minted client-side or by the
    route layer), so we pass it through here rather than letting the
    DB generate it.

    ``agent_slug`` records which surface owns the session — None for Central
    Intelligence, a director slug for a department chat — and is set on
    creation only (it never changes for a given session_id).
    """
    try:
        session_uuid = uuid.UUID(session_id)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid session_id: {session_id!r}") from exc
    try:
        user_uuid = uuid.UUID(user_id)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid user_id: {user_id!r}") from exc

    existing = (await db.execute(
        select(ChatSession).where(ChatSession.id == session_uuid)
    )).scalar_one_or_none()
    if existing is not None:
        return existing

    row = ChatSession(
        id=session_uuid,
        user_id=user_uuid,
        title=derive_title(first_user_message),
        agent_slug=agent_slug,
    )
    db.add(row)
    await db.flush()
    return row


async def append_message(
    db: AsyncSession,
    *,
    session_id: str,
    role: str,
    content: str,
    content_blocks: list[dict[str, Any]] | None = None,
) -> ChatMessage:
    """Insert one chat_messages row and bump the session's recency clock."""
    try:
        session_uuid = uuid.UUID(session_id)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid session_id: {session_id!r}") from exc
    if role not in ("user", "assistant"):
        raise ValueError(f"role must be 'user' or 'assistant', got {role!r}")

    now = datetime.now(timezone.utc)
    msg = ChatMessage(
        id=uuid.uuid4(),
        session_id=session_uuid,
        role=role,
        content=content or "",
        content_blocks=content_blocks,
        created_at=now,
    )
    db.add(msg)

    # Bump last_message_at on the parent row in the same transaction.
    parent = (await db.execute(
        select(ChatSession).where(ChatSession.id == session_uuid)
    )).scalar_one_or_none()
    if parent is not None:
        parent.last_message_at = now
        db.add(parent)
    else:
        logger.warning(
            "append_message: parent session %s not found; orphan message",
            session_id,
        )
    return msg


async def load_history_for_agent(
    db: AsyncSession,
    *,
    session_id: str,
) -> list[dict[str, Any]]:
    """Return Anthropic-API-shape conversation history for replay.

    Each row becomes one ``{"role": str, "content": ...}`` dict. When
    ``content_blocks`` is populated we hand back the structured block
    list (tool_use + tool_result + text) so the agent's next turn sees
    the full prior context, including any tool results. Otherwise the
    plain ``content`` string is used.
    """
    try:
        session_uuid = uuid.UUID(session_id)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid session_id: {session_id!r}") from exc

    rows = (await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_uuid)
        .order_by(ChatMessage.created_at.asc())
    )).scalars().all()

    history: list[dict[str, Any]] = []
    for r in rows:
        if r.content_blocks:
            history.append({"role": r.role, "content": r.content_blocks})
        else:
            history.append({"role": r.role, "content": r.content})
    return history
