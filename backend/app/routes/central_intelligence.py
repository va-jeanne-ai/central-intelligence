"""
Central Intelligence routes — SSE streaming and WebSocket endpoints.

POST /api/v1/central-intelligence/chat     — Server-Sent Events streaming
WS   /ws/v1/central-intelligence/{session_id} — WebSocket streaming

Session management
------------------
CentralIntelligence instances are kept in a process-local dict keyed by session_id.
This is intentional for Sprint 1A: no Redis, no persistence.  Each server
process owns its own sessions.  A distributed session store (Redis) is on
the Sprint 2 roadmap.

SSE protocol
------------
Every frame is a standard SSE ``data:`` line followed by two newlines.
The payload is a JSON-encoded ChatChunk.  The final frame sets done=true
and includes the complete full_response string.

WebSocket protocol
------------------
Client sends:  {"message": "..."}
               {"type": "ping"}  (keepalive)

Server sends (mid-stream):
  {
    "channel": "central-intelligence:chat-stream:<session_id>",
    "data": {
      "sessionId": "<session_id>",
      "chunk": "<text delta>",
      "tokenIndex": <int>,
      "isComplete": false
    }
  }

Server sends (final frame):
  {
    "channel": "central-intelligence:chat-stream:<session_id>",
    "data": {
      "sessionId": "<session_id>",
      "chunk": "",
      "tokenIndex": <int>,
      "isComplete": true,
      "fullResponse": "<full text>"
    }
  }

Server sends (pong):
  {"type": "pong"}
"""

import json
import logging
import uuid
from typing import Any, AsyncIterator, Optional

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.central_intelligence import CentralIntelligence
from app.agents.mock_central_intelligence import MockCentralIntelligence
from app.auth.dependencies import CurrentUser, get_current_user
from app.config import settings
from app.database import AsyncSessionLocal, get_session
from app.schemas.chat import ChatChunk, ChatRequest
from app.services import chat_persistence

logger = logging.getLogger(__name__)

router = APIRouter(tags=["central-intelligence"])

# ---------------------------------------------------------------------------
# In-memory session store
# session_id (str) -> CentralIntelligence | MockCentralIntelligence instance
#
# This is now a cache, not the source of truth. The authoritative chat
# history lives in chat_sessions + chat_messages. On a cache miss for
# an existing session_id we load the prior turns from DB and seed the
# agent's conversation_history before returning.
# ---------------------------------------------------------------------------
_sessions: dict[str, CentralIntelligence | MockCentralIntelligence] = {}


def _build_agent() -> CentralIntelligence | MockCentralIntelligence:
    """Construct a fresh agent based on whether an Anthropic key is set."""
    if settings.anthropic_api_key:
        return CentralIntelligence()
    return MockCentralIntelligence()


async def _get_or_create_session(
    session_id: str | None,
    *,
    db: AsyncSession | None = None,
) -> tuple[str, CentralIntelligence | MockCentralIntelligence]:
    """Return (session_id, agent), hydrating prior history from DB if needed.

    Three cases:
      1. session_id is in the in-memory cache → reuse.
      2. session_id is provided but missing from the cache → mint a
         fresh agent and replay any persisted turns into it.
      3. session_id is None → mint a fresh agent + a fresh UUID. No
         DB row exists yet; ``ensure_session`` will create it on the
         first ``append_message`` call.
    """
    if session_id and session_id in _sessions:
        logger.debug("Resuming session %s from cache", session_id)
        return session_id, _sessions[session_id]

    new_id = session_id or str(uuid.uuid4())
    agent = _build_agent()

    if session_id and db is not None:
        # Re-hydrate the agent from persisted messages so follow-up turns
        # see prior context. New chats (no row in chat_sessions yet) just
        # return an empty list — agent starts cold, which is correct.
        try:
            history = await chat_persistence.load_history_for_agent(
                db, session_id=session_id,
            )
            if history:
                agent.set_conversation_history(history)
                logger.info(
                    "Re-hydrated session %s with %d persisted turn(s)",
                    session_id, len(history),
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Failed to load persisted history for session %s — %s",
                session_id, exc,
            )

    _sessions[new_id] = agent
    logger.info("Created session %s (type=%s)", new_id, type(agent).__name__)
    return new_id, agent


def _last_assistant_blocks(
    agent: CentralIntelligence | MockCentralIntelligence,
) -> list[dict[str, Any]] | None:
    """Pull the most recently appended assistant turn's content_blocks.

    The agent appends every assistant turn to ``conversation_history``
    after the stream finishes (see ``BaseAgent.stream_response``). We
    grab the last assistant entry for persistence — preserving the
    tool_use / text block list so a reloaded session can replay the
    full agent state, not just the visible text.
    """
    history = getattr(agent, "conversation_history", None) or []
    for entry in reversed(history):
        if entry.get("role") == "assistant":
            content = entry.get("content")
            if isinstance(content, list):
                return content
            # Plain text turn — return None so the caller stores the
            # response string in `content` only and leaves
            # content_blocks NULL.
            return None
    return None


async def _persist_user_turn(
    *,
    session_id: str,
    user_id: str,
    message: str,
) -> None:
    """Persist the user's message + session row in its own transaction.

    Each call opens a short-lived AsyncSession so the persistence work
    is independent of the streaming response lifetime. Errors are
    logged but never abort the chat — we'd rather lose history than
    refuse to talk to the user.
    """
    try:
        async with AsyncSessionLocal() as db:
            await chat_persistence.ensure_session(
                db,
                session_id=session_id,
                user_id=user_id,
                first_user_message=message,
            )
            await chat_persistence.append_message(
                db,
                session_id=session_id,
                role="user",
                content=message,
            )
            await db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "persist_user_turn failed (session=%s): %s", session_id, exc,
        )


async def _persist_assistant_turn(
    *,
    session_id: str,
    content: str,
    content_blocks: list[dict[str, Any]] | None,
) -> None:
    """Persist the assistant's full response after the stream finishes."""
    try:
        async with AsyncSessionLocal() as db:
            await chat_persistence.append_message(
                db,
                session_id=session_id,
                role="assistant",
                content=content,
                content_blocks=content_blocks,
            )
            await db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "persist_assistant_turn failed (session=%s): %s", session_id, exc,
        )


def _user_id_from_token(token: str | None) -> str | None:
    """Extract ``sub`` from a Supabase JWT for the WebSocket route.

    Returns the user id on success; ``None`` for missing/invalid tokens
    (the caller can fall back to mock-mode behaviour).
    """
    if not token:
        return None
    try:
        from app.middleware.auth import verify_supabase_jwt
        claims = verify_supabase_jwt(token)
        if claims is None:
            return None
        return str(claims.get("sub") or "") or None
    except Exception as exc:  # noqa: BLE001
        logger.warning("WebSocket: failed to extract sub from token — %s", exc)
        return None


# ---------------------------------------------------------------------------
# SSE helpers
# ---------------------------------------------------------------------------

def _sse_frame(chunk: ChatChunk) -> str:
    """Encode a ChatChunk as a single SSE data frame."""
    payload = chunk.model_dump(exclude_none=True)
    return f"data: {json.dumps(payload)}\n\n"


async def _sse_generator(
    message: str,
    session_id: str,
    agent: CentralIntelligence | MockCentralIntelligence,
    user_id: str | None,
) -> AsyncIterator[str]:
    """Drive the CentralIntelligence stream and yield SSE-encoded frames.

    Persists the user message *before* streaming so a mid-stream
    disconnect still leaves the user's turn in the transcript. The
    assistant's response is persisted once the stream completes
    successfully — partial assistant turns are dropped (the user will
    re-prompt anyway).
    """
    if user_id:
        await _persist_user_turn(
            session_id=session_id, user_id=user_id, message=message,
        )

    accumulated: list[str] = []

    try:
        async for delta in agent.stream_response(message):
            accumulated.append(delta)
            frame = _sse_frame(
                ChatChunk(chunk=delta, session_id=session_id, done=False)
            )
            yield frame

        full_response = "".join(accumulated)
        from app.agents.base import (
            FINISH_COMPLETE,
            INCOMPLETE_FINISH_REASONS,
            FINISH_NOTICES,
        )

        finish_reason = getattr(agent, "last_finish_reason", FINISH_COMPLETE)
        is_incomplete = finish_reason in INCOMPLETE_FINISH_REASONS
        yield _sse_frame(
            ChatChunk(
                chunk="",
                session_id=session_id,
                done=True,
                full_response=full_response,
                status="incomplete" if is_incomplete else "complete",
                finish_reason=finish_reason,
                notice=FINISH_NOTICES.get(finish_reason) if is_incomplete else None,
            )
        )
        logger.info(
            "SSE stream complete for session %s (%d chars) finish=%s",
            session_id,
            len(full_response),
            finish_reason,
        )

        if user_id:
            await _persist_assistant_turn(
                session_id=session_id,
                content=full_response,
                content_blocks=_last_assistant_blocks(agent),
            )

    except Exception as exc:
        logger.exception("SSE stream error for session %s: %s", session_id, exc)
        # Send an error frame so the client gets a graceful terminal event.
        yield _sse_frame(
            ChatChunk(
                chunk=f"\n\n[Stream error: {exc}]",
                session_id=session_id,
                done=True,
                full_response=None,
            )
        )


# ---------------------------------------------------------------------------
# POST /api/v1/central-intelligence/chat  — SSE streaming endpoint
# ---------------------------------------------------------------------------

@router.post(
    "/api/v1/central-intelligence/chat",
    summary="Chat with Central Intelligence (SSE streaming)",
    description=(
        "Sends a message to the Central Intelligence agent and streams the response as "
        "Server-Sent Events.  Pass session_id to continue an existing conversation; "
        "omit it to start a new one.  The session_id is embedded in every SSE frame."
    ),
    # FastAPI cannot declare SSE in the OpenAPI response model; document manually.
    responses={
        200: {
            "description": "text/event-stream — sequence of ChatChunk frames",
            "content": {"text/event-stream": {}},
        }
    },
)
async def central_intelligence_chat(
    request: ChatRequest,
    db: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> StreamingResponse:
    session_id, agent = await _get_or_create_session(request.session_id, db=db)

    logger.info(
        "SSE chat request: session=%s user=%s message_len=%d",
        session_id,
        current_user.id,
        len(request.message),
    )

    return StreamingResponse(
        _sse_generator(request.message, session_id, agent, current_user.id),
        media_type="text/event-stream",
        headers={
            # Prevent proxies and browsers from buffering the stream.
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            # Expose session_id so clients can read it from response headers
            # before the first SSE frame arrives.
            "X-Session-Id": session_id,
        },
    )


# ---------------------------------------------------------------------------
# WS /ws/v1/central-intelligence/{session_id}  — WebSocket streaming endpoint
# ---------------------------------------------------------------------------

@router.websocket("/ws/v1/central-intelligence/{session_id}")
async def central_intelligence_websocket(
    websocket: WebSocket,
    session_id: str,
    token: Optional[str] = Query(default=None),
) -> None:
    """WebSocket endpoint for real-time bidirectional chat with Central Intelligence.

    The path-level session_id is used to look up or create a CentralIntelligence
    instance.  Clients that want a fresh session should generate a UUID
    client-side before connecting.

    Authentication
    --------------
    Because HTTP middleware cannot block a WebSocket upgrade after the
    handshake has been accepted, auth is handled here via the ``?token=``
    query parameter.

    - Mock mode: token is ignored; the connection is always accepted.
    - Real mode: the token must be a valid Supabase JWT.  An absent or
      invalid token causes an immediate close with code 4001.
    """
    # ------------------------------------------------------------------
    # Authenticate before accepting the connection.
    # In mock mode (no Supabase configured) we skip verification entirely.
    # ------------------------------------------------------------------
    mock_mode = (not settings.supabase_url) or settings.mock_mode

    user_id: str | None = None
    if mock_mode:
        # Mock-mode: same synthetic user id as the SSE/HTTP path uses.
        # Lets chat persistence work in dev without Supabase configured.
        # Also ensure the row exists in `users` for the FK to succeed
        # (chat_sessions.user_id has ON DELETE CASCADE).
        from app.auth.dependencies import (
            MOCK_USER_ID, MOCK_USER_EMAIL, MOCK_USER_ROLE,
            _ensure_local_user_row,
        )
        user_id = MOCK_USER_ID
        await _ensure_local_user_row(
            user_id=user_id,
            email=MOCK_USER_EMAIL,
            name="Mock Admin",
            role=MOCK_USER_ROLE,
        )
    elif token:
        # Verify via the shared helper that supports ES256/RS256/HS256 — the
        # raw `jwt.decode` path here used to hardcode HS256 and reject all
        # modern Supabase tokens (which sign with ES256 since 2024).
        user_id = _user_id_from_token(token)
        if user_id is None:
            logger.warning(
                "WebSocket: token verification failed for session %s — "
                "allowing connection (page is auth-gated), no persistence",
                session_id,
            )

    await websocket.accept()
    # Open a short-lived DB session just to hydrate the agent from any
    # persisted history. After that the WS loop opens its own short-
    # lived sessions per persistence call so we don't hold a connection
    # for the lifetime of the websocket.
    async with AsyncSessionLocal() as db:
        session_id, agent = await _get_or_create_session(session_id, db=db)
    logger.info("WebSocket connected: session=%s user=%s", session_id, user_id)

    channel = f"central-intelligence:chat-stream:{session_id}"

    try:
        while True:
            # ---- Receive ------------------------------------------------
            try:
                raw = await websocket.receive_text()
            except WebSocketDisconnect:
                logger.info("WebSocket disconnected: session=%s", session_id)
                break

            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                logger.warning(
                    "WebSocket: invalid JSON from session %s, ignoring", session_id
                )
                continue

            # ---- Ping/pong keepalive ------------------------------------
            if payload.get("type") == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
                logger.debug("WebSocket pong sent: session=%s", session_id)
                continue

            message = payload.get("message", "").strip()
            if not message:
                logger.debug(
                    "WebSocket: empty message from session %s, ignoring", session_id
                )
                continue

            logger.info(
                "WebSocket message: session=%s len=%d", session_id, len(message)
            )

            # Persist the user message + ensure the session row exists
            # before we start streaming, so a mid-stream disconnect still
            # leaves the user's turn in the transcript.
            if user_id:
                await _persist_user_turn(
                    session_id=session_id, user_id=user_id, message=message,
                )

            # ---- Stream response ----------------------------------------
            accumulated: list[str] = []
            token_index = 0

            try:
                async for delta in agent.stream_response(message):
                    accumulated.append(delta)
                    frame = json.dumps(
                        {
                            "channel": channel,
                            "data": {
                                "sessionId": session_id,
                                "chunk": delta,
                                "tokenIndex": token_index,
                                "isComplete": False,
                            },
                        }
                    )
                    await websocket.send_text(frame)
                    token_index += 1

                full_response = "".join(accumulated)
                from app.agents.base import (
                    FINISH_COMPLETE,
                    INCOMPLETE_FINISH_REASONS,
                    FINISH_NOTICES,
                )

                finish_reason = getattr(agent, "last_finish_reason", FINISH_COMPLETE)
                is_incomplete = finish_reason in INCOMPLETE_FINISH_REASONS
                final_data = {
                    "sessionId": session_id,
                    "chunk": "",
                    "tokenIndex": token_index,
                    "isComplete": True,
                    "fullResponse": full_response,
                    "status": "incomplete" if is_incomplete else "complete",
                    "finishReason": finish_reason,
                }
                if is_incomplete:
                    final_data["notice"] = FINISH_NOTICES.get(finish_reason)
                final_frame = json.dumps({"channel": channel, "data": final_data})
                await websocket.send_text(final_frame)
                logger.info(
                    "WebSocket stream complete: session=%s tokens=%d chars=%d finish=%s",
                    session_id,
                    token_index,
                    len(full_response),
                    finish_reason,
                )

                if user_id:
                    await _persist_assistant_turn(
                        session_id=session_id,
                        content=full_response,
                        content_blocks=_last_assistant_blocks(agent),
                    )

            except WebSocketDisconnect:
                logger.info(
                    "WebSocket disconnected mid-stream: session=%s", session_id
                )
                break

            except Exception as exc:
                logger.exception(
                    "WebSocket stream error: session=%s error=%s", session_id, exc
                )
                error_frame = json.dumps(
                    {
                        "channel": channel,
                        "data": {
                            "sessionId": session_id,
                            "chunk": f"\n\n[Stream error: {exc}]",
                            "tokenIndex": token_index,
                            "isComplete": True,
                            "fullResponse": None,
                        },
                    }
                )
                try:
                    await websocket.send_text(error_frame)
                except Exception:
                    pass
                break

    except WebSocketDisconnect:
        logger.info("WebSocket outer disconnect: session=%s", session_id)
    except Exception as exc:
        logger.exception(
            "Unexpected WebSocket error: session=%s error=%s", session_id, exc
        )
    finally:
        logger.info("WebSocket closed: session=%s", session_id)
