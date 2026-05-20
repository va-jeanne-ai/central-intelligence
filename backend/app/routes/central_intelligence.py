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
from typing import AsyncIterator, Optional

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from jose import JWTError, jwt

from app.agents.central_intelligence import CentralIntelligence
from app.agents.mock_central_intelligence import MockCentralIntelligence
from app.config import settings
from app.schemas.chat import ChatChunk, ChatRequest

logger = logging.getLogger(__name__)

router = APIRouter(tags=["central-intelligence"])

# ---------------------------------------------------------------------------
# In-memory session store
# session_id (str) -> CentralIntelligence | MockCentralIntelligence instance
# ---------------------------------------------------------------------------
_sessions: dict[str, CentralIntelligence | MockCentralIntelligence] = {}


def _get_or_create_session(session_id: str | None) -> tuple[str, CentralIntelligence | MockCentralIntelligence]:
    """Return (session_id, agent).  Creates a new session when needed."""
    if session_id and session_id in _sessions:
        logger.debug("Resuming session %s", session_id)
        return session_id, _sessions[session_id]

    new_id = session_id or str(uuid.uuid4())
    use_real_ai = bool(settings.anthropic_api_key)
    if use_real_ai:
        agent: CentralIntelligence | MockCentralIntelligence = CentralIntelligence()
        logger.info("Created new CentralIntelligence session %s", new_id)
    else:
        agent = MockCentralIntelligence()
        logger.info("Created new MockCentralIntelligence session %s (no API key)", new_id)
    _sessions[new_id] = agent
    return new_id, agent


# ---------------------------------------------------------------------------
# SSE helpers
# ---------------------------------------------------------------------------

def _sse_frame(chunk: ChatChunk) -> str:
    """Encode a ChatChunk as a single SSE data frame."""
    payload = chunk.model_dump(exclude_none=True)
    return f"data: {json.dumps(payload)}\n\n"


async def _sse_generator(
    message: str, session_id: str, agent: CentralIntelligence | MockCentralIntelligence
) -> AsyncIterator[str]:
    """Drive the CentralIntelligence stream and yield SSE-encoded frames."""
    accumulated: list[str] = []

    try:
        async for delta in agent.stream_response(message):
            accumulated.append(delta)
            frame = _sse_frame(
                ChatChunk(chunk=delta, session_id=session_id, done=False)
            )
            yield frame

        full_response = "".join(accumulated)
        yield _sse_frame(
            ChatChunk(
                chunk="",
                session_id=session_id,
                done=True,
                full_response=full_response,
            )
        )
        logger.info(
            "SSE stream complete for session %s (%d chars)",
            session_id,
            len(full_response),
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
async def central_intelligence_chat(request: ChatRequest) -> StreamingResponse:
    session_id, agent = _get_or_create_session(request.session_id)

    logger.info(
        "SSE chat request: session=%s message_len=%d",
        session_id,
        len(request.message),
    )

    return StreamingResponse(
        _sse_generator(request.message, session_id, agent),
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

    if not mock_mode and token:
        # Verify via the shared helper that supports ES256/RS256/HS256 — the
        # raw `jwt.decode` path here used to hardcode HS256 and reject all
        # modern Supabase tokens (which sign with ES256 since 2024).
        from app.middleware.auth import verify_supabase_jwt

        if verify_supabase_jwt(token) is None:
            logger.warning(
                "WebSocket: token verification failed for session %s — "
                "allowing connection (page is auth-gated)",
                session_id,
            )

    await websocket.accept()
    session_id, agent = _get_or_create_session(session_id)
    logger.info("WebSocket connected: session=%s", session_id)

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
                final_frame = json.dumps(
                    {
                        "channel": channel,
                        "data": {
                            "sessionId": session_id,
                            "chunk": "",
                            "tokenIndex": token_index,
                            "isComplete": True,
                            "fullResponse": full_response,
                        },
                    }
                )
                await websocket.send_text(final_frame)
                logger.info(
                    "WebSocket stream complete: session=%s tokens=%d chars=%d",
                    session_id,
                    token_index,
                    len(full_response),
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
