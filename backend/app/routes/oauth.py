"""Google OAuth flow routes for per-user Gmail integration.

Two endpoints:

  GET  /api/v1/integrations/google_workspace/oauth/start
      Auth required. Generates a tamper-proof state token encoding the
      current user_id, returns the Google consent URL. The frontend
      redirects the browser there.

  GET  /api/v1/integrations/google_workspace/oauth/callback
      Auth-exempt (Google hits this). Validates the state, recovers
      the user_id, exchanges the code for a refresh+access token pair,
      encrypts + stores in user_integration_credentials, redirects to
      the frontend with ?connected=ok|err.

The `state` parameter doubles as both CSRF protection and a way to
remember "which user initiated this flow" without a session store.
We Fernet-encrypt `{user_id, nonce, issued_at}` so an attacker can't
forge a state that targets a different user.
"""

from __future__ import annotations

import json
import logging
import secrets as _stdlib_secrets
import uuid
from datetime import datetime, timezone
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser, get_current_user
from app.config import settings
from app.database import get_session
from app.models.operational import UserIntegrationCredential
from app.services import google_oauth
from app.services import secrets as app_secrets

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/integrations/google_workspace/oauth", tags=["oauth"])


_STATE_TTL_SECONDS = 600  # 10 minutes — enough for the OAuth round-trip


# ---------------------------------------------------------------------------
# Tamper-proof state token
# ---------------------------------------------------------------------------


def _encode_state(user_id: str) -> str:
    """Fernet-encrypt {user_id, nonce, issued_at} into the state param."""
    payload = {
        "user_id": user_id,
        "nonce": _stdlib_secrets.token_urlsafe(16),
        "issued_at": datetime.now(timezone.utc).isoformat(),
    }
    return app_secrets.encrypt(json.dumps(payload))


def _decode_state(state: str) -> str:
    """Decrypt + validate the state token; return the encoded user_id.

    Raises HTTPException(400) on decrypt failure or expired token.
    """
    try:
        payload = json.loads(app_secrets.decrypt(state))
    except (ValueError, json.JSONDecodeError) as exc:
        logger.warning("oauth callback: state decrypt failed — %s", exc)
        raise HTTPException(status_code=400, detail="Invalid OAuth state") from exc

    issued_at_str = payload.get("issued_at")
    try:
        issued_at = datetime.fromisoformat(issued_at_str) if issued_at_str else None
    except (ValueError, TypeError):
        issued_at = None

    if issued_at is None or (
        datetime.now(timezone.utc) - issued_at
    ).total_seconds() > _STATE_TTL_SECONDS:
        raise HTTPException(status_code=400, detail="OAuth state expired — try again")

    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(status_code=400, detail="Invalid OAuth state")
    return str(user_id)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/start")
async def oauth_start(
    request: Request,  # noqa: ARG001
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Return the Google consent URL the frontend should redirect to.

    The frontend handles the actual redirect (rather than us returning
    a 302) so the API stays JSON-only and the browser sees a single
    user-initiated navigation.
    """
    if not settings.google_oauth_client_id:
        raise HTTPException(
            status_code=503,
            detail="Google OAuth is not configured on this deployment.",
        )

    state = _encode_state(str(current_user.id))
    redirect_url = google_oauth.build_authorize_url(state)
    return {"redirect_url": redirect_url}


def _frontend_callback_target(status: str, error: str | None = None) -> str:
    """Build the URL we redirect the browser to after the OAuth round-trip.

    Uses the frontend origin derived from the configured redirect URI
    by stripping the API path. For local dev that gives us
    http://localhost:3000/integrations/google_workspace?connected=<status>.
    """
    # The redirect URI is on the backend; the frontend is on a sibling
    # host (typically port 3000 in dev). Compose by stripping the
    # API path and swapping ports if needed.
    base = settings.public_api_base_url.rstrip("/")
    # Default frontend URL derived heuristically — works for the
    # typical localhost setup. Prod deployments override via
    # public_api_base_url or a future setting.
    frontend_origin = base.replace(":8000", ":3000")
    qs = {"connected": status}
    if error:
        qs["error"] = error
    return f"{frontend_origin}/integrations/google_workspace?{urlencode(qs)}"


@router.get("/callback")
async def oauth_callback(
    request: Request,  # noqa: ARG001 — required by FastAPI
    code: str = Query(default=""),
    state: str = Query(default=""),
    error: str = Query(default=""),
    session: AsyncSession = Depends(get_session),
) -> RedirectResponse:
    """Handle Google's redirect back to us.

    Auth-exempt (Google hits this with no JWT). The user_id is
    encoded in the ``state`` parameter we minted in /start.
    """
    if error:
        logger.info("oauth callback: user denied or Google returned error=%s", error)
        return RedirectResponse(
            _frontend_callback_target("err", error=error),
            status_code=303,
        )

    if not code or not state:
        raise HTTPException(
            status_code=400,
            detail="Missing code or state in callback",
        )

    user_id_str = _decode_state(state)
    try:
        user_uuid = uuid.UUID(user_id_str)
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail="State carries invalid user_id",
        ) from exc

    # Exchange the code for tokens.
    try:
        tokens = google_oauth.exchange_code_for_tokens(code)
    except Exception as exc:  # noqa: BLE001
        logger.warning("oauth callback: token exchange failed — %s", exc)
        return RedirectResponse(
            _frontend_callback_target("err", error="token_exchange_failed"),
            status_code=303,
        )

    refresh_token = tokens.get("refresh_token")
    access_token = tokens.get("access_token")
    if not refresh_token or not access_token:
        # First-time consent should always include refresh_token. If
        # it's missing, the user previously consented and Google didn't
        # issue a new one. Force re-consent by surfacing an error.
        logger.warning(
            "oauth callback: no refresh_token in response (user_id=%s) — "
            "user may have already consented; pass prompt=consent to force",
            user_uuid,
        )
        return RedirectResponse(
            _frontend_callback_target("err", error="no_refresh_token"),
            status_code=303,
        )

    granted_scopes = (tokens.get("scope") or "").split() or None
    connected_email = google_oauth.decode_id_token_email(tokens.get("id_token"))
    expires_at = google_oauth.compute_expiry(tokens.get("expires_in"))

    blob = {
        "refresh_token": refresh_token,
        "access_token": access_token,
        "token_uri": google_oauth.TOKEN_URL,
        "client_id": settings.google_oauth_client_id,
        "client_secret": settings.google_oauth_client_secret,
        "expires_at": expires_at.isoformat(),
        "scopes": google_oauth.SCOPES,
    }
    ciphertext = app_secrets.encrypt(json.dumps(blob))

    # Upsert the per-user credential row.
    existing = (await session.execute(
        select(UserIntegrationCredential).where(
            UserIntegrationCredential.user_id == user_uuid,
            UserIntegrationCredential.provider == "google_workspace",
        )
    )).scalar_one_or_none()

    if existing is None:
        session.add(UserIntegrationCredential(
            id=uuid.uuid4(),
            user_id=user_uuid,
            provider="google_workspace",
            credentials_encrypted=ciphertext,
            scopes=granted_scopes,
            connected_email=connected_email,
        ))
        logger.info(
            "oauth callback: INSERT user_integration_credentials user_id=%s email=%s",
            user_uuid, connected_email,
        )
    else:
        existing.credentials_encrypted = ciphertext
        if granted_scopes:
            existing.scopes = granted_scopes
        if connected_email:
            existing.connected_email = connected_email
        existing.last_sync_error = None  # clear stale errors on reconnect
        session.add(existing)
        logger.info(
            "oauth callback: REFRESH user_integration_credentials user_id=%s email=%s",
            user_uuid, connected_email,
        )

    await session.commit()

    return RedirectResponse(
        _frontend_callback_target("ok"),
        status_code=303,
    )


# ---------------------------------------------------------------------------
# List + disconnect — used by the frontend Connected Users panel
# ---------------------------------------------------------------------------


@router.get("/connected-users")
async def list_connected_users(
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),  # noqa: ARG001
) -> dict:
    """Return every user currently connected via Google Workspace.

    Surfaces connected_email + last_sync_status so the integrations
    page can render "Connected as jane@… · last synced 2h ago".
    """
    rows = (await session.execute(
        select(UserIntegrationCredential).where(
            UserIntegrationCredential.provider == "google_workspace",
        )
    )).scalars().all()
    return {
        "users": [
            {
                "user_id": str(r.user_id),
                "connected_email": r.connected_email,
                "last_synced_at": r.last_synced_at.isoformat() if r.last_synced_at else None,
                "last_sync_status": r.last_sync_status,
                "last_sync_error": r.last_sync_error,
            }
            for r in rows
        ],
    }


@router.delete("/disconnect")
async def disconnect_self(
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Remove the calling user's Google Workspace credential row.

    Each user can only disconnect themselves. To disconnect another
    user, an admin would use a separate endpoint (not yet built).
    """
    try:
        user_uuid = uuid.UUID(str(current_user.id))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid user id") from exc

    row = (await session.execute(
        select(UserIntegrationCredential).where(
            UserIntegrationCredential.user_id == user_uuid,
            UserIntegrationCredential.provider == "google_workspace",
        )
    )).scalar_one_or_none()

    if row is None:
        return {"disconnected": False, "reason": "not_connected"}

    await session.delete(row)
    await session.commit()
    logger.info("oauth disconnect: removed user_id=%s", user_uuid)
    return {"disconnected": True}
