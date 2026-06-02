"""Google OAuth 2.0 flow primitives.

Used by ``routes/oauth.py`` to mint a consent URL, exchange the
authorization code for a token pair, and refresh expired access
tokens. Read-only Gmail scope only.

We hit Google's endpoints directly via ``httpx`` rather than the
``google-auth-oauthlib`` package — fewer moving parts, no second
HTTP client floating around, mirrors the pattern in
``services/ghl_client.py``.

The ``Credentials`` object that downstream callers (Gmail sync) need
is constructed in ``services/google_oauth_credentials.py``; this
module deals only with the raw token endpoint.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# Google's OAuth 2.0 endpoints.
AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"

# Read-only Gmail + Drive + Calendar. Adding more scopes here requires
# the user to re-consent — `drive.readonly` was added when the RAG
# layer landed, `calendar.readonly` was added when Calendar became a
# first-class data surface. Each scope add forces re-OAuth.
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/calendar.readonly",
]

# Some Google flows return userinfo only when openid + email are
# requested. We need the connected email address for the UI ("Connected
# as jane@example.com") and to disambiguate multiple Google accounts.
_USERINFO_SCOPES = ["openid", "email"]


_DEFAULT_TIMEOUT = 15.0


def _all_scopes() -> list[str]:
    return SCOPES + _USERINFO_SCOPES


def build_authorize_url(state: str, redirect_uri: str | None = None) -> str:
    """Construct the Google consent URL the user gets redirected to.

    ``access_type=offline`` + ``prompt=consent`` is the canonical
    combo for guaranteeing a refresh token in the callback response
    (without ``prompt=consent``, returning users only get an access
    token).
    """
    if not settings.google_oauth_client_id:
        raise RuntimeError(
            "GOOGLE_OAUTH_CLIENT_ID is not set. Configure it in backend/.env.",
        )
    params = {
        "client_id": settings.google_oauth_client_id,
        "redirect_uri": redirect_uri or settings.google_oauth_redirect_uri,
        "response_type": "code",
        "scope": " ".join(_all_scopes()),
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
        "state": state,
    }
    return f"{AUTHORIZE_URL}?{urlencode(params)}"


def exchange_code_for_tokens(
    code: str, redirect_uri: str | None = None,
) -> dict[str, Any]:
    """POST the authorization code to Google's token endpoint.

    Returns the raw token JSON (we don't strip fields here so the
    caller can decide what to persist):

        {
          "access_token": "...",
          "expires_in": 3599,
          "refresh_token": "...",       # only on first consent
          "scope": "...",
          "token_type": "Bearer",
          "id_token": "..."              # JWT containing the user's email
        }
    """
    if not settings.google_oauth_client_id or not settings.google_oauth_client_secret:
        raise RuntimeError(
            "Google OAuth client credentials are not configured.",
        )

    data = {
        "code": code,
        "client_id": settings.google_oauth_client_id,
        "client_secret": settings.google_oauth_client_secret,
        "redirect_uri": redirect_uri or settings.google_oauth_redirect_uri,
        "grant_type": "authorization_code",
    }
    with httpx.Client(timeout=_DEFAULT_TIMEOUT) as client:
        response = client.post(TOKEN_URL, data=data)
        response.raise_for_status()
        return response.json()


def refresh_access_token(refresh_token: str) -> dict[str, Any]:
    """Exchange a refresh token for a new access token.

    Returns ``{access_token, expires_in, scope, token_type, id_token?}``.
    Refresh tokens are long-lived but can be revoked; on revoke the
    response is HTTP 400 with ``{"error": "invalid_grant"}``. The
    caller surfaces that to the UI as "Reconnect needed".
    """
    if not settings.google_oauth_client_id or not settings.google_oauth_client_secret:
        raise RuntimeError(
            "Google OAuth client credentials are not configured.",
        )

    data = {
        "refresh_token": refresh_token,
        "client_id": settings.google_oauth_client_id,
        "client_secret": settings.google_oauth_client_secret,
        "grant_type": "refresh_token",
    }
    with httpx.Client(timeout=_DEFAULT_TIMEOUT) as client:
        response = client.post(TOKEN_URL, data=data)
        response.raise_for_status()
        return response.json()


def compute_expiry(expires_in_seconds: int | None) -> datetime:
    """Convert an ``expires_in`` (seconds-until-expiry) into an absolute
    UTC datetime we can persist + compare. Defaults to 1h ahead if the
    response omits the field (Google's tokens are always 1h-ish)."""
    seconds = expires_in_seconds if expires_in_seconds and expires_in_seconds > 0 else 3600
    return datetime.now(timezone.utc) + timedelta(seconds=seconds)


def decode_id_token_email(id_token: str | None) -> str | None:
    """Pull the ``email`` claim out of an OpenID id_token without
    verifying the JWT signature. Google's id_token signature is
    already verified by the token endpoint itself (we just received
    it over a TLS-protected connection); we only need to read the
    email claim to display "Connected as ...".

    Returns None on any parse failure — we'd rather degrade the UI
    label than crash the OAuth callback.
    """
    if not id_token:
        return None
    try:
        import base64
        import json
        # JWT: header.payload.signature — we only need the payload.
        parts = id_token.split(".")
        if len(parts) != 3:
            return None
        payload_b64 = parts[1]
        # Pad to a multiple of 4 for urlsafe_b64decode.
        padding = "=" * (-len(payload_b64) % 4)
        payload = json.loads(
            base64.urlsafe_b64decode(payload_b64 + padding).decode("utf-8"),
        )
        email = payload.get("email")
        return str(email) if email else None
    except Exception as exc:  # noqa: BLE001
        logger.warning("decode_id_token_email: parse failed — %s", exc)
        return None
