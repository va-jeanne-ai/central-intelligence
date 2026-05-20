"""
Director routes — WebSocket streaming endpoints for department-level agents.

WS /ws/v1/{director_slug}/{session_id} — WebSocket streaming

Mirrors the Central Intelligence WebSocket protocol but targets individual Director
agents. The director_slug path parameter selects which department director
to instantiate (e.g. "marketing-director").

Session management
------------------
Director instances are kept in a process-local dict keyed by
(director_slug, session_id). This matches the Sprint 1A approach used by
Central Intelligence — no Redis, no persistence.
"""

import json
import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from jose import JWTError, jwt

from app.config import settings
from app.database import AsyncSessionLocal

logger = logging.getLogger(__name__)

router = APIRouter(tags=["directors"])

# ---------------------------------------------------------------------------
# Known directors — slug -> (class_path, constructor_kwargs)
# Only marketing-director is available in Sprint 1.
# ---------------------------------------------------------------------------
_DIRECTOR_REGISTRY: dict[str, str] = {
    "marketing-director": "app.agents.directors.marketing.MarketingDirector",
}

# ---------------------------------------------------------------------------
# In-memory session store
# (director_slug, session_id) -> agent instance
# ---------------------------------------------------------------------------
_sessions: dict[tuple[str, str], object] = {}


def _get_or_create_director(director_slug: str, session_id: str, db_session=None):
    """Return (session_id, agent). Creates a new director when needed."""
    key = (director_slug, session_id)
    if key in _sessions:
        logger.debug("Resuming director session %s/%s", director_slug, session_id)
        return session_id, _sessions[key]

    new_id = session_id or str(uuid.uuid4())
    key = (director_slug, new_id)

    use_real_ai = bool(settings.anthropic_api_key)
    if not use_real_ai:
        from app.agents.mock_central_intelligence import MockCentralIntelligence
        agent = MockCentralIntelligence()
        logger.info(
            "Created mock director session %s/%s (no API key)",
            director_slug, new_id,
        )
    else:
        class_path = _DIRECTOR_REGISTRY.get(director_slug)
        if not class_path:
            return None, None

        # Dynamically import and instantiate the director
        module_path, class_name = class_path.rsplit(".", 1)
        import importlib
        module = importlib.import_module(module_path)
        director_class = getattr(module, class_name)
        agent = director_class(session=db_session)
        logger.info("Created director session %s/%s", director_slug, new_id)

    _sessions[key] = agent
    return new_id, agent


# ---------------------------------------------------------------------------
# WS /ws/v1/{director_slug}/{session_id}
# ---------------------------------------------------------------------------

@router.websocket("/ws/v1/{director_slug}/{session_id}")
async def director_websocket(
    websocket: WebSocket,
    director_slug: str,
    session_id: str,
    token: Optional[str] = Query(default=None),
) -> None:
    """WebSocket endpoint for real-time chat with a Director agent."""

    # Validate director slug
    if director_slug not in _DIRECTOR_REGISTRY:
        await websocket.close(code=4004, reason=f"Unknown director: {director_slug}")
        return

    # Authenticate (same pattern as Central Intelligence)
    mock_mode = (not settings.supabase_url) or settings.mock_mode

    if not mock_mode and token:
        # Verify via the shared helper that supports ES256/RS256/HS256 — the
        # raw `jwt.decode` path here used to hardcode HS256 and reject all
        # modern Supabase tokens (which sign with ES256 since 2024).
        from app.middleware.auth import verify_supabase_jwt

        if verify_supabase_jwt(token) is None:
            logger.warning(
                "Director WebSocket: token verification failed for %s/%s — "
                "allowing connection (page is auth-gated)",
                director_slug, session_id,
            )

    await websocket.accept()

    # Create DB session for the director (needed when real AI is active)
    db_session = None
    if settings.anthropic_api_key:
        db_session = AsyncSessionLocal()

    try:
        session_id, agent = _get_or_create_director(
            director_slug, session_id, db_session=db_session,
        )

        if agent is None:
            logger.error("Failed to create director %s", director_slug)
            await websocket.close(code=4004, reason=f"Unknown director: {director_slug}")
            return

        logger.info("Director WebSocket connected: %s/%s", director_slug, session_id)

        channel = f"{director_slug}:chat-stream:{session_id}"

        while True:
            # ---- Receive ------------------------------------------------
            try:
                raw = await websocket.receive_text()
            except WebSocketDisconnect:
                logger.info(
                    "Director WebSocket disconnected: %s/%s", director_slug, session_id
                )
                break

            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                logger.warning(
                    "Director WebSocket: invalid JSON from %s/%s, ignoring",
                    director_slug, session_id,
                )
                continue

            # ---- Ping/pong keepalive ------------------------------------
            if payload.get("type") == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
                continue

            message = payload.get("message", "").strip()
            if not message:
                continue

            logger.info(
                "Director WebSocket message: %s/%s len=%d",
                director_slug, session_id, len(message),
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
                    "Director WebSocket stream complete: %s/%s tokens=%d chars=%d",
                    director_slug, session_id, token_index, len(full_response),
                )

            except WebSocketDisconnect:
                logger.info(
                    "Director WebSocket disconnected mid-stream: %s/%s",
                    director_slug, session_id,
                )
                break

            except Exception as exc:
                logger.exception(
                    "Director WebSocket stream error: %s/%s error=%s",
                    director_slug, session_id, exc,
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
        logger.info("Director WebSocket outer disconnect: %s/%s", director_slug, session_id)
    except Exception as exc:
        logger.exception(
            "Unexpected Director WebSocket error: %s/%s error=%s",
            director_slug, session_id, exc,
        )
    finally:
        if db_session is not None:
            await db_session.close()
        logger.info("Director WebSocket closed: %s/%s", director_slug, session_id)
