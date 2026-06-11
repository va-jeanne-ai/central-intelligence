"""Meta (Facebook/Instagram) OAuth 2.0 flow primitives.

Used by the Instagram OAuth routes to mint a consent URL, exchange the
authorization code for a token, upgrade it to a long-lived token, and
resolve the connected Instagram Business account ID.

We hit Meta's Graph endpoints directly via ``httpx`` — mirrors
``services/google_oauth.py`` and ``services/instagram_client.py``.

Token model (differs from Google):
  - Meta has NO refresh token. The flow returns a SHORT-lived token
    (~1h), which we exchange for a LONG-lived token (~60 days).
  - "Refreshing" means re-exchanging the long-lived token for a fresh
    long-lived token (``grant_type=fb_exchange_token``) before it
    expires — done on sync by ``instagram_credentials.ensure_fresh_token``.

The resulting ``(access_token, ig_user_id, expires_at)`` is stored in the
shared ``integrations`` row (provider='instagram'), the same blob the
manual-token connector writes — so downstream code is unchanged.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# Meta's OAuth 2.0 + Graph endpoints (Facebook Login for Instagram Graph API).
GRAPH_VERSION = "v19.0"
AUTHORIZE_URL = f"https://www.facebook.com/{GRAPH_VERSION}/dialog/oauth"
TOKEN_URL = f"https://graph.facebook.com/{GRAPH_VERSION}/oauth/access_token"
GRAPH_BASE = f"https://graph.facebook.com/{GRAPH_VERSION}"

# Scopes needed to read organic Instagram Business metrics. Each requires
# Meta App Review before non-test users can grant them; app admins/testers
# can grant them in development mode without review.
SCOPES = [
    "instagram_basic",
    "instagram_manage_insights",
    "pages_show_list",
    "pages_read_engagement",
    "business_management",
]

_DEFAULT_TIMEOUT = 15.0


def is_configured() -> bool:
    """True when the Meta app credentials are present in settings."""
    return bool(settings.meta_oauth_client_id and settings.meta_oauth_client_secret)


def build_authorize_url(state: str, redirect_uri: str | None = None) -> str:
    """Construct the Facebook consent URL the admin gets redirected to."""
    if not settings.meta_oauth_client_id:
        raise RuntimeError(
            "META_OAUTH_CLIENT_ID is not set. Configure it in backend/.env.",
        )
    params = {
        "client_id": settings.meta_oauth_client_id,
        "redirect_uri": redirect_uri or settings.meta_oauth_redirect_uri,
        "response_type": "code",
        "scope": ",".join(SCOPES),  # Meta uses comma-separated scopes
        "state": state,
    }
    return f"{AUTHORIZE_URL}?{urlencode(params)}"


def exchange_code_for_token(
    code: str, redirect_uri: str | None = None,
) -> dict[str, Any]:
    """Exchange the authorization code for a SHORT-lived access token.

    Returns the raw token JSON: ``{access_token, token_type, expires_in?}``.
    """
    if not is_configured():
        raise RuntimeError("Meta OAuth client credentials are not configured.")
    params = {
        "client_id": settings.meta_oauth_client_id,
        "client_secret": settings.meta_oauth_client_secret,
        "redirect_uri": redirect_uri or settings.meta_oauth_redirect_uri,
        "code": code,
    }
    with httpx.Client(timeout=_DEFAULT_TIMEOUT) as client:
        # Token endpoint is a GET on Meta (unlike Google's POST).
        response = client.get(TOKEN_URL, params=params)
        response.raise_for_status()
        return response.json()


def exchange_for_long_lived(short_lived_token: str) -> dict[str, Any]:
    """Upgrade a short-lived token to a long-lived (~60-day) token.

    Returns ``{access_token, token_type, expires_in}`` where expires_in is
    typically ~5184000 (60 days).
    """
    if not is_configured():
        raise RuntimeError("Meta OAuth client credentials are not configured.")
    params = {
        "grant_type": "fb_exchange_token",
        "client_id": settings.meta_oauth_client_id,
        "client_secret": settings.meta_oauth_client_secret,
        "fb_exchange_token": short_lived_token,
    }
    with httpx.Client(timeout=_DEFAULT_TIMEOUT) as client:
        response = client.get(TOKEN_URL, params=params)
        response.raise_for_status()
        return response.json()


def refresh_long_lived(long_lived_token: str) -> dict[str, Any]:
    """Re-exchange a long-lived token for a fresh long-lived token.

    Meta has no refresh token; you extend a long-lived token by passing it
    back through ``fb_exchange_token`` before it expires. Same call as
    :func:`exchange_for_long_lived` — kept as a distinct name for clarity at
    the call site (refresh-on-sync vs. initial-connect).
    """
    return exchange_for_long_lived(long_lived_token)


def resolve_ig_user_id(access_token: str) -> str | None:
    """Discover the Instagram Business account ID reachable by this token.

    Walks ``/me/accounts`` (the Pages the user manages) and returns the
    first Page's linked ``instagram_business_account.id``. Returns None when
    no Page has a linked IG Business account (the admin must link one in
    Facebook Page settings first).
    """
    try:
        with httpx.Client(timeout=_DEFAULT_TIMEOUT) as client:
            resp = client.get(
                f"{GRAPH_BASE}/me/accounts",
                params={
                    "fields": "id,name,instagram_business_account",
                    "access_token": access_token,
                },
            )
            resp.raise_for_status()
            pages = resp.json().get("data", [])
        for page in pages:
            iba = page.get("instagram_business_account")
            if iba and iba.get("id"):
                return str(iba["id"])
        logger.warning("resolve_ig_user_id: no Page has a linked IG Business account")
        return None
    except Exception as exc:  # noqa: BLE001 — caller treats None as "unresolved"
        logger.warning("resolve_ig_user_id failed: %s", exc)
        return None


def compute_expiry(expires_in_seconds: int | None) -> datetime:
    """Convert an ``expires_in`` (seconds) into an absolute UTC datetime.

    Defaults to 60 days ahead when the field is omitted (long-lived tokens
    are ~60 days). The stored ``expires_at`` drives the refresh-on-sync gate.
    """
    sixty_days = 60 * 24 * 3600
    seconds = (
        expires_in_seconds
        if expires_in_seconds and expires_in_seconds > 0
        else sixty_days
    )
    return datetime.now(timezone.utc) + timedelta(seconds=seconds)
