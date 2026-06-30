"""CRUD endpoints for persisted chat sessions.

Powers the sidebar on ``/chat``:

  * ``GET    /api/v1/chat/sessions``        — current user's sessions, newest first
  * ``GET    /api/v1/chat/sessions/{id}``   — one session + full transcript
  * ``PATCH  /api/v1/chat/sessions/{id}``   — rename the session
  * ``DELETE /api/v1/chat/sessions/{id}``   — hard delete (CASCADEs messages)

All endpoints scope by ``current_user.id`` — fetching a session owned
by another user returns 404 (not 403), so we don't leak whether the ID
exists.

The chat streaming endpoints (SSE + WebSocket) live in
``routes/central_intelligence.py`` and call into ``chat_persistence``
directly — they're the *write* path that creates sessions + messages
as the conversation happens. This module is the read/edit/delete side.
"""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser, get_current_user
from app.database import get_session
from app.schemas.chat import (
    ChatMessageRow,
    ChatSessionDetailResponse,
    ChatSessionListResponse,
    ChatSessionRow,
    UpdateChatSessionRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat-sessions"])


def _parse_session_uuid(session_id: str) -> uuid.UUID:
    """Path-param UUID parse with 404 on garbage."""
    try:
        return uuid.UUID(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Chat session not found") from exc


def _parse_user_uuid(user_id: str) -> uuid.UUID | None:
    """Best-effort current_user.id parse. Returns ``None`` for the
    mock-mode synthetic user so we can short-circuit empty responses
    without hitting the DB FK constraint."""
    try:
        return uuid.UUID(user_id)
    except (TypeError, ValueError):
        return None


@router.get(
    "/api/v1/chat/sessions", response_model=ChatSessionListResponse,
)
async def list_chat_sessions(
    agent_slug: str | None = Query(
        default=None,
        description=(
            "Scope the list to one chat surface. Omit for Central Intelligence "
            "(agent_slug IS NULL); pass a director slug (e.g. 'marketing-director') "
            "for that director's sessions only."
        ),
    ),
    db: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> ChatSessionListResponse:
    """Return the calling user's chat sessions for one surface, newest first.

    `last_message_at` is the sort key; sessions with no messages yet
    (created but never written to) sort last via NULLS LAST. Each row
    carries a denormalised ``message_count`` for the sidebar's
    "12 messages" trailing label.

    ``agent_slug`` scopes by surface: ``IS NOT DISTINCT FROM`` treats NULL as a
    matchable value, so no query param ⇒ Central Intelligence sessions only,
    and a director slug ⇒ that director only. The two never bleed together.
    """
    user_uuid = _parse_user_uuid(current_user.id)
    if user_uuid is None:
        return ChatSessionListResponse(sessions=[])

    rows = (await db.execute(
        text("""
            SELECT
                cs.id::text         AS id,
                cs.title            AS title,
                cs.created_at       AS created_at,
                cs.updated_at       AS updated_at,
                cs.last_message_at  AS last_message_at,
                (
                    SELECT count(*) FROM chat_messages cm
                    WHERE cm.session_id = cs.id
                )                   AS message_count
            FROM chat_sessions cs
            WHERE cs.user_id = :user_id
              AND cs.agent_slug IS NOT DISTINCT FROM :agent_slug
            ORDER BY cs.last_message_at DESC NULLS LAST, cs.created_at DESC
        """),
        {"user_id": str(user_uuid), "agent_slug": agent_slug},
    )).mappings().all()

    sessions = [
        ChatSessionRow(
            id=r["id"],
            title=r["title"],
            created_at=r["created_at"].isoformat(),
            updated_at=r["updated_at"].isoformat(),
            last_message_at=(
                r["last_message_at"].isoformat() if r["last_message_at"] else None
            ),
            message_count=int(r["message_count"] or 0),
        )
        for r in rows
    ]
    return ChatSessionListResponse(sessions=sessions)


@router.get(
    "/api/v1/chat/sessions/{session_id}",
    response_model=ChatSessionDetailResponse,
)
async def get_chat_session(
    session_id: str,
    db: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> ChatSessionDetailResponse:
    """Return the session row + every message in chronological order.

    Returns 404 (not 403) when the session belongs to another user so
    we don't leak the existence of the id.
    """
    sid = _parse_session_uuid(session_id)
    user_uuid = _parse_user_uuid(current_user.id)
    if user_uuid is None:
        raise HTTPException(status_code=404, detail="Chat session not found")

    session_row = (await db.execute(
        text("""
            SELECT
                id::text           AS id,
                title              AS title,
                created_at         AS created_at,
                updated_at         AS updated_at,
                last_message_at    AS last_message_at
            FROM chat_sessions
            WHERE id = :sid AND user_id = :user_id
        """),
        {"sid": str(sid), "user_id": str(user_uuid)},
    )).mappings().first()
    if session_row is None:
        raise HTTPException(status_code=404, detail="Chat session not found")

    message_rows = (await db.execute(
        text("""
            SELECT id::text AS id, role, content, created_at
            FROM chat_messages
            WHERE session_id = :sid
            ORDER BY created_at ASC
        """),
        {"sid": str(sid)},
    )).mappings().all()

    return ChatSessionDetailResponse(
        session=ChatSessionRow(
            id=session_row["id"],
            title=session_row["title"],
            created_at=session_row["created_at"].isoformat(),
            updated_at=session_row["updated_at"].isoformat(),
            last_message_at=(
                session_row["last_message_at"].isoformat()
                if session_row["last_message_at"] else None
            ),
            message_count=len(message_rows),
        ),
        messages=[
            ChatMessageRow(
                id=m["id"],
                role=m["role"],
                content=m["content"],
                created_at=m["created_at"].isoformat(),
            )
            for m in message_rows
        ],
    )


@router.patch(
    "/api/v1/chat/sessions/{session_id}",
    response_model=ChatSessionRow,
)
async def update_chat_session(
    session_id: str,
    body: UpdateChatSessionRequest,
    db: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> ChatSessionRow:
    """Rename a chat session. The title field is the only thing the
    user can mutate today — everything else is system-managed."""
    sid = _parse_session_uuid(session_id)
    user_uuid = _parse_user_uuid(current_user.id)
    if user_uuid is None:
        raise HTTPException(status_code=404, detail="Chat session not found")

    new_title = body.title.strip()
    if not new_title:
        raise HTTPException(status_code=400, detail="Title cannot be empty")

    result = await db.execute(
        text("""
            UPDATE chat_sessions
            SET title = :title
            WHERE id = :sid AND user_id = :user_id
            RETURNING
                id::text           AS id,
                title              AS title,
                created_at         AS created_at,
                updated_at         AS updated_at,
                last_message_at    AS last_message_at,
                (
                    SELECT count(*) FROM chat_messages cm
                    WHERE cm.session_id = chat_sessions.id
                )                  AS message_count
        """),
        {"sid": str(sid), "user_id": str(user_uuid), "title": new_title},
    )
    row = result.mappings().first()
    if row is None:
        raise HTTPException(status_code=404, detail="Chat session not found")
    await db.commit()

    return ChatSessionRow(
        id=row["id"],
        title=row["title"],
        created_at=row["created_at"].isoformat(),
        updated_at=row["updated_at"].isoformat(),
        last_message_at=(
            row["last_message_at"].isoformat() if row["last_message_at"] else None
        ),
        message_count=int(row["message_count"] or 0),
    )


@router.delete("/api/v1/chat/sessions/{session_id}", status_code=204)
async def delete_chat_session(
    session_id: str,
    db: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> None:
    """Hard delete. CASCADE on the FK wipes the chat_messages rows too.

    Idempotent at the user's level — deleting a session that's already
    gone returns 404 (so the frontend can show a "session no longer
    exists" toast if two tabs race). The in-memory ``_sessions`` cache
    in ``routes/central_intelligence.py`` is invalidated separately
    (or just gracefully misses on the next lookup; it never holds
    authoritative state).
    """
    sid = _parse_session_uuid(session_id)
    user_uuid = _parse_user_uuid(current_user.id)
    if user_uuid is None:
        raise HTTPException(status_code=404, detail="Chat session not found")

    result = await db.execute(
        text("""
            DELETE FROM chat_sessions
            WHERE id = :sid AND user_id = :user_id
        """),
        {"sid": str(sid), "user_id": str(user_uuid)},
    )
    if (result.rowcount or 0) == 0:
        raise HTTPException(status_code=404, detail="Chat session not found")
    await db.commit()
