"""
Pydantic schemas for chat request/response contracts.

These models are the public API surface — keep them stable across
minor releases and version-bump when breaking changes are required.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Inbound message payload from the client."""

    message: str = Field(..., min_length=1, max_length=10_000)
    session_id: Optional[str] = Field(
        default=None,
        description=(
            "Opaque session identifier.  Pass the value returned by a previous "
            "response to continue an existing conversation.  Omit (or pass null) "
            "to start a new session."
        ),
    )


class ChatResponse(BaseModel):
    """Non-streaming response envelope (used by the execute() code-path)."""

    session_id: str
    response: str
    workers_called: list[str] = Field(
        default_factory=list,
        description="Agent IDs of any sub-agents invoked during this turn.",
    )


class ChatChunk(BaseModel):
    """A single SSE / WebSocket frame carrying a streamed text delta."""

    chunk: str = ""
    session_id: str = ""
    done: bool = False
    full_response: Optional[str] = Field(
        default=None,
        description="Present only on the final frame (done=true).",
    )


class HealthResponse(BaseModel):
    """Health-check response body."""

    status: str
    database: str
    version: str
    timestamp: datetime
    auth: str = "not_configured"
    redis: str = "not_configured"
    uptime: float = 0.0


# ─── Persistent chat history ──────────────────────────────────────────────


class ChatSessionRow(BaseModel):
    """One row in the user's chat-history sidebar."""

    id: str
    title: str
    created_at: str
    updated_at: str
    last_message_at: Optional[str] = None
    message_count: int = 0


class ChatSessionListResponse(BaseModel):
    """Payload for ``GET /api/v1/chat/sessions``.

    Sessions are ordered newest-first by ``last_message_at`` so the
    sidebar can render them in display order without re-sorting.
    """

    sessions: list[ChatSessionRow] = Field(default_factory=list)


class ChatMessageRow(BaseModel):
    """One persisted message inside a chat session."""

    id: str
    role: str
    content: str
    created_at: str


class ChatSessionDetailResponse(BaseModel):
    """Payload for ``GET /api/v1/chat/sessions/{id}``.

    Messages are oldest-first so the frontend can render the transcript
    top-to-bottom directly.
    """

    session: ChatSessionRow
    messages: list[ChatMessageRow] = Field(default_factory=list)


class UpdateChatSessionRequest(BaseModel):
    """PATCH body for renaming a chat session."""

    title: str = Field(..., min_length=1, max_length=120)
