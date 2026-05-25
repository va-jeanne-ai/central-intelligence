"""
FastAPI authentication dependencies.

Provides two injectable dependencies:

- ``get_current_user`` — requires a valid Bearer token; raises HTTP 401
  when the token is absent or invalid.
- ``get_optional_user`` — same but returns ``None`` instead of raising,
  suitable for endpoints that behave differently for authenticated vs.
  anonymous callers.

When mock mode is active (``SUPABASE_URL`` is not configured) both
dependencies return a synthetic admin user without inspecting the
``Authorization`` header at all.  This keeps every protected endpoint
fully functional during local development.
"""

import logging
import uuid
from dataclasses import dataclass
from typing import Optional

from fastapi import Header, HTTPException, status
from sqlalchemy import text

from app.auth.supabase_client import get_supabase_client
from app.config import settings
from app.database import AsyncSessionLocal

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Synthetic user returned by both dependencies when Supabase is not
# configured.  Using a fixed ID makes it easy to seed database fixtures.
# ---------------------------------------------------------------------------
_MOCK_USER_ID = "mock-user-id"
_MOCK_USER_EMAIL = "admin@centralintelligence.ai"
_MOCK_USER_ROLE = "admin"


@dataclass
class CurrentUser:
    """Represents the authenticated principal attached to a request.

    Attributes
    ----------
    id:
        Supabase user UUID (or the fixed mock value in mock mode).
    email:
        User's email address.
    role:
        Application-level role string (e.g. ``"admin"``, ``"member"``).
    """

    id: str
    email: str
    role: str


def _extract_bearer_token(authorization: Optional[str]) -> Optional[str]:
    """Parse a raw ``Authorization`` header value and return the token part.

    Parameters
    ----------
    authorization:
        Raw header value, e.g. ``"Bearer eyJhbGc..."``.

    Returns
    -------
    str | None
        The token string, or ``None`` if the header is missing or
        malformed.
    """
    if not authorization:
        return None
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1].strip() or None


async def _ensure_local_user_row(
    *,
    user_id: str,
    email: str,
    name: str | None,
    role: str,
) -> None:
    """Insert a `users` row for the calling Supabase user if missing.

    Best-effort: any failure (bad UUID, DB hiccup, race with a parallel
    request) is logged at warning and swallowed — most endpoints don't
    actually need a users row to function. The endpoints that do (the
    ones with FKs into users.id) get a valid row on this user's first
    authenticated request.
    """
    if not user_id:
        return
    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        # Mock-mode sub like "mock-user-id" — nothing to mirror.
        return

    try:
        async with AsyncSessionLocal() as session:
            await session.execute(
                text("""
                    INSERT INTO users (id, email, name, role, is_active)
                    VALUES (:id, :email, :name, :role, TRUE)
                    ON CONFLICT (id) DO NOTHING
                """),
                {
                    "id": str(user_uuid),
                    # `email` is NOT NULL + UNIQUE on users; supply a
                    # synthetic when Supabase omitted it so the INSERT
                    # doesn't bounce on a NULL violation.
                    "email": email or f"user-{user_uuid}@unknown.local",
                    "name": name,
                    "role": role,
                },
            )
            await session.commit()
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "auth: ensure_local_user_row failed for %s — %s", user_id, exc,
        )


async def get_current_user(
    authorization: Optional[str] = Header(default=None),
) -> CurrentUser:
    """FastAPI dependency that resolves the authenticated user.

    In mock mode the ``Authorization`` header is ignored and a synthetic
    admin user is returned unconditionally.

    In real mode the header must be present and carry a valid Supabase
    JWT.  The token is verified against the Supabase project and the
    resulting user attributes are mapped onto a :class:`CurrentUser`.

    Raises
    ------
    HTTPException
        HTTP 401 when the ``Authorization`` header is missing, malformed,
        or contains an expired / invalid token (real mode only).
    """
    supabase = get_supabase_client()
    mock_mode = supabase is None or settings.mock_mode

    # ------------------------------------------------------------------
    # Mock mode — Supabase not configured or MOCK_MODE=true.
    # ------------------------------------------------------------------
    if mock_mode:
        logger.debug("Mock auth: returning synthetic admin user")
        return CurrentUser(id=_MOCK_USER_ID, email=_MOCK_USER_EMAIL, role=_MOCK_USER_ROLE)

    # ------------------------------------------------------------------
    # Real mode — validate the Bearer token with Supabase.
    # ------------------------------------------------------------------
    token = _extract_bearer_token(authorization)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or malformed Authorization header. Expected: Bearer <token>",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        response = supabase.auth.get_user(token)
        user = response.user
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Supabase stores application metadata in user_metadata; fall
        # back to "member" when the role key has not been set.
        role = (user.user_metadata or {}).get("role", "member")

        # Auto-mirror the Supabase user into our local `users` table so
        # any FK pointing at users.id (lead_notes.author_id,
        # audit_log.user_id, user_integration_credentials.user_id, …)
        # resolves on the first authenticated request. Best-effort:
        # failures here log and proceed — the request itself doesn't
        # need a users row for most endpoints.
        await _ensure_local_user_row(
            user_id=str(user.id),
            email=user.email or "",
            name=(user.user_metadata or {}).get("full_name"),
            role=role,
        )

        return CurrentUser(id=str(user.id), email=user.email or "", role=role)

    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.warning("Token validation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token validation failed",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


async def get_optional_user(
    authorization: Optional[str] = Header(default=None),
) -> Optional[CurrentUser]:
    """FastAPI dependency that resolves the user without requiring auth.

    Behaves identically to :func:`get_current_user` except that it
    returns ``None`` (instead of raising HTTP 401) when no valid
    credentials are supplied.

    Returns
    -------
    CurrentUser | None
        The authenticated user, or ``None`` for anonymous callers.
    """
    supabase = get_supabase_client()
    mock_mode = supabase is None or settings.mock_mode

    if mock_mode:
        # Mock mode: still return the synthetic user so that downstream
        # code that checks for None (anonymous) works predictably.
        return CurrentUser(id=_MOCK_USER_ID, email=_MOCK_USER_EMAIL, role=_MOCK_USER_ROLE)

    token = _extract_bearer_token(authorization)
    if not token:
        return None

    try:
        response = supabase.auth.get_user(token)
        user = response.user
        if user is None:
            return None

        role = (user.user_metadata or {}).get("role", "member")
        return CurrentUser(id=str(user.id), email=user.email or "", role=role)

    except Exception as exc:  # noqa: BLE001
        logger.debug("Optional auth token invalid, continuing as anonymous: %s", exc)
        return None
