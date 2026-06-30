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
    "sales-director": "app.agents.directors.sales.SalesDirector",
    "fulfillment-director": "app.agents.directors.fulfillment.FulfillmentDirector",
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
# Persistence helpers — mirror routes/central_intelligence.py but stamp the
# director slug as agent_slug so each director's history is its own surface.
# Each runs in a short-lived session and never aborts the chat on failure.
# ---------------------------------------------------------------------------


def _user_id_from_token(token: str | None) -> str | None:
    """Extract ``sub`` from a Supabase JWT (None when missing/invalid)."""
    if not token:
        return None
    try:
        from app.middleware.auth import verify_supabase_jwt
        claims = verify_supabase_jwt(token)
        if claims is None:
            return None
        return str(claims.get("sub") or "") or None
    except Exception as exc:  # noqa: BLE001
        logger.warning("Director WS: failed to extract sub from token — %s", exc)
        return None


def _last_assistant_blocks(agent) -> list | None:
    """Most recent assistant turn's content_blocks (for full-state replay)."""
    history = getattr(agent, "conversation_history", None) or []
    for entry in reversed(history):
        if entry.get("role") == "assistant":
            content = entry.get("content")
            return content if isinstance(content, list) else None
    return None


async def _persist_user_turn(
    *, session_id: str, user_id: str, agent_slug: str, message: str,
) -> None:
    from app.services import chat_persistence

    try:
        async with AsyncSessionLocal() as db:
            await chat_persistence.ensure_session(
                db,
                session_id=session_id,
                user_id=user_id,
                first_user_message=message,
                agent_slug=agent_slug,
            )
            await chat_persistence.append_message(
                db, session_id=session_id, role="user", content=message,
            )
            await db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Director persist_user_turn failed (%s): %s", session_id, exc)


async def _persist_assistant_turn(
    *, session_id: str, content: str, content_blocks: list | None,
) -> None:
    from app.services import chat_persistence

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
        logger.warning("Director persist_assistant_turn failed (%s): %s", session_id, exc)


async def _rehydrate_history(agent, session_id: str) -> None:
    """Replay a persisted transcript into the agent before the next turn.

    Lets a resumed director session continue with full prior context, exactly
    like Central Intelligence. No-op (and silent) if nothing is stored yet.
    """
    if not hasattr(agent, "set_conversation_history"):
        return
    if getattr(agent, "conversation_history", None):
        return  # already has in-memory context for this process
    from app.services import chat_persistence

    try:
        async with AsyncSessionLocal() as db:
            history = await chat_persistence.load_history_for_agent(
                db, session_id=session_id,
            )
        if history:
            agent.set_conversation_history(history)
            logger.info(
                "Director WS: rehydrated %d turn(s) for session %s",
                len(history), session_id,
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Director WS: history rehydrate failed (%s): %s", session_id, exc)


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

        # Who is this (for persistence) + replay any stored transcript so a
        # resumed session keeps full context. user_id is None in mock/no-auth
        # mode, in which case we simply don't persist.
        user_id = _user_id_from_token(token)
        await _rehydrate_history(agent, session_id)

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

            # Persist the user's turn BEFORE streaming so a mid-stream
            # disconnect still leaves it in the transcript (stamped with this
            # director's slug). Skipped in mock/no-auth mode (user_id is None).
            if user_id:
                await _persist_user_turn(
                    session_id=session_id,
                    user_id=user_id,
                    agent_slug=director_slug,
                    message=message,
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

                # Why the turn ended. On anything other than a clean finish the
                # streamed text is partial — tell the frontend so it can flag it
                # and offer a reload instead of treating it as a finished answer.
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
                    "Director WebSocket stream complete: %s/%s tokens=%d chars=%d finish=%s",
                    director_slug, session_id, token_index, len(full_response), finish_reason,
                )

                # Persist the assistant turn once the stream finishes cleanly.
                # Truncated/incomplete responses are NOT saved — the user will
                # reload and re-ask, and we don't want a cut-off answer in the
                # replayed history.
                if user_id and not is_incomplete and full_response:
                    await _persist_assistant_turn(
                        session_id=session_id,
                        content=full_response,
                        content_blocks=_last_assistant_blocks(agent),
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
