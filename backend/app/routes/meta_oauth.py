"""Meta (Facebook/Instagram) OAuth flow routes — single shared business account.

Endpoints:

  GET    /api/v1/integrations/instagram/oauth/start
      Auth required. Mints a tamper-proof state token (CSRF nonce + TTL),
      returns the Facebook consent URL. The frontend redirects the browser.

  GET    /api/v1/integrations/instagram/oauth/callback
      Auth-exempt (Facebook hits this). Validates state, exchanges the code
      for a short-lived token, upgrades it to a long-lived (~60-day) token,
      resolves the Instagram Business account ID, and stores everything in
      the shared ``integrations`` row (provider='instagram') — the same blob
      the manual-token connector reads. Redirects to the frontend with
      ?connected=ok|err.

  DELETE /api/v1/integrations/instagram/oauth/disconnect
      Auth required. Clears the Instagram integration credentials.

Unlike Google's per-user flow, Instagram is ONE shared brand account, so the
state carries only a CSRF nonce (no user_id) and the token lands in the
single ``integrations`` row rather than ``user_integration_credentials``.
"""

from __future__ import annotations

import json
import logging
import secrets as _stdlib_secrets
from datetime import datetime, timezone
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser, get_current_user
from app.config import settings
from app.database import get_session
from app.models.integration import Integration
from app.services import meta_oauth
from app.services import secrets as app_secrets

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/integrations/instagram/oauth", tags=["oauth"])

_STATE_TTL_SECONDS = 600  # 10 minutes — enough for the OAuth round-trip
_PROVIDER = "instagram"


# ---------------------------------------------------------------------------
# Tamper-proof state token (CSRF nonce + TTL; no user_id — shared account)
# ---------------------------------------------------------------------------


def _encode_state() -> str:
    payload = {
        "nonce": _stdlib_secrets.token_urlsafe(16),
        "issued_at": datetime.now(timezone.utc).isoformat(),
    }
    return app_secrets.encrypt(json.dumps(payload))


def _validate_state(state: str) -> None:
    """Decrypt + validate the state token. Raises HTTPException(400) on
    decrypt failure or expiry. Returns nothing (no user_id to recover)."""
    try:
        payload = json.loads(app_secrets.decrypt(state))
    except (ValueError, json.JSONDecodeError) as exc:
        logger.warning("meta oauth callback: state decrypt failed — %s", exc)
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


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/start")
async def meta_oauth_start(
    request: Request,  # noqa: ARG001
    current_user: CurrentUser = Depends(get_current_user),  # noqa: ARG001
) -> dict:
    """Return the Facebook consent URL the frontend should redirect to."""
    if not meta_oauth.is_configured():
        raise HTTPException(
            status_code=503,
            detail="Meta OAuth is not configured on this deployment.",
        )
    state = _encode_state()
    return {"redirect_url": meta_oauth.build_authorize_url(state)}


def _frontend_callback_target(status: str, error: str | None = None) -> str:
    """Build the browser redirect target after the OAuth round-trip."""
    base = settings.public_api_base_url.rstrip("/")
    frontend_origin = base.replace(":8000", ":3000")
    qs = {"connected": status}
    if error:
        qs["error"] = error
    return f"{frontend_origin}/integrations/instagram?{urlencode(qs)}"


@router.get("/callback")
async def meta_oauth_callback(
    request: Request,  # noqa: ARG001 — required by FastAPI
    code: str = Query(default=""),
    state: str = Query(default=""),
    error: str = Query(default=""),
    session: AsyncSession = Depends(get_session),
) -> RedirectResponse:
    """Handle Facebook's redirect. Auth-exempt; state carries the CSRF nonce."""
    if error:
        logger.info("meta oauth callback: user denied or error=%s", error)
        return RedirectResponse(
            _frontend_callback_target("err", error=error), status_code=303
        )

    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code or state in callback")

    _validate_state(state)

    # 1. Exchange code → short-lived token, 2. upgrade → long-lived token.
    try:
        short = meta_oauth.exchange_code_for_token(code)
        short_token = short.get("access_token")
        if not short_token:
            raise RuntimeError("no access_token in code exchange")
        long = meta_oauth.exchange_for_long_lived(short_token)
    except Exception as exc:  # noqa: BLE001
        logger.warning("meta oauth callback: token exchange failed — %s", exc)
        return RedirectResponse(
            _frontend_callback_target("err", error="token_exchange_failed"),
            status_code=303,
        )

    access_token = long.get("access_token")
    if not access_token:
        return RedirectResponse(
            _frontend_callback_target("err", error="no_long_lived_token"),
            status_code=303,
        )
    expires_at = meta_oauth.compute_expiry(long.get("expires_in"))

    # 3. Resolve the Instagram Business account ID reachable by this token.
    ig_user_id = meta_oauth.resolve_ig_user_id(access_token)
    if not ig_user_id:
        # Token is valid but no Page has a linked IG Business account — the
        # admin must link one in Facebook Page settings, then reconnect.
        return RedirectResponse(
            _frontend_callback_target("err", error="no_ig_business_account"),
            status_code=303,
        )

    # 4. Store in the shared integrations row (same blob the manual
    #    connector + instagram_credentials read). auth_method='oauth' lets
    #    the refresh-on-sync gate know this token can be auto-extended.
    blob = {
        "access_token": access_token,
        "ig_user_id": ig_user_id,
        "expires_at": expires_at.isoformat(),
        "auth_method": "oauth",
    }
    ciphertext = app_secrets.encrypt(json.dumps(blob))

    row = (await session.execute(
        select(Integration).where(Integration.provider == _PROVIDER)
    )).scalar_one_or_none()

    if row is None:
        session.add(Integration(
            provider=_PROVIDER,
            status="connected",
            credentials_encrypted=ciphertext,
            config={"ig_user_id": ig_user_id, "auth_method": "oauth"},
        ))
        logger.info("meta oauth callback: INSERT instagram integration ig=%s", ig_user_id)
    else:
        row.status = "connected"
        row.credentials_encrypted = ciphertext
        row.config = {"ig_user_id": ig_user_id, "auth_method": "oauth"}
        row.last_sync_error = None  # clear stale errors on reconnect
        session.add(row)
        logger.info("meta oauth callback: UPDATE instagram integration ig=%s", ig_user_id)

    await session.commit()
    return RedirectResponse(_frontend_callback_target("ok"), status_code=303)


@router.delete("/disconnect")
async def meta_oauth_disconnect(
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),  # noqa: ARG001
) -> dict:
    """Disconnect the Instagram integration (clear stored credentials)."""
    row = (await session.execute(
        select(Integration).where(Integration.provider == _PROVIDER)
    )).scalar_one_or_none()

    if row is None or row.status != "connected":
        return {"disconnected": False, "reason": "not_connected"}

    row.status = "disconnected"
    row.credentials_encrypted = None
    row.config = None
    session.add(row)
    await session.commit()
    logger.info("meta oauth disconnect: cleared instagram integration")
    return {"disconnected": True}
