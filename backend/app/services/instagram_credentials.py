"""Instagram (Meta Graph API) integration credential loading.

Mirrors ``ghl_credentials.py``: decrypt the ``integrations.credentials_encrypted``
blob for the Instagram provider and extract ``(access_token, ig_user_id)``.

Returns None when credentials are missing or unparseable so callers can stamp
the integration as misconfigured (or simply skip it) rather than crashing.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from app.models.integration import Integration
from app.services import secrets as app_secrets

logger = logging.getLogger(__name__)

# Refresh an OAuth long-lived token when it's within this window of expiry.
# Meta long-lived tokens last ~60 days; 7 days of slack means a weekly sync
# always re-extends well before expiry.
_REFRESH_WINDOW_SECONDS = 7 * 24 * 3600


def _load_blob(integration: Integration) -> dict | None:
    """Decrypt the integration's credentials blob, or None on any failure."""
    if not integration.credentials_encrypted:
        return None
    try:
        return json.loads(app_secrets.decrypt(integration.credentials_encrypted))
    except (ValueError, json.JSONDecodeError) as exc:
        logger.warning("instagram credentials: decrypt failed — %s", exc)
        return None


def load_instagram_credentials(integration: Integration) -> tuple[str, str] | None:
    """Decrypt + extract ``(access_token, ig_user_id)`` from the blob.

    Works for BOTH the manual-token connector and the OAuth flow — they
    write the same ``access_token`` + ``ig_user_id`` keys. Returns ``None``
    on empty/unparseable blob or missing fields.
    """
    blob = _load_blob(integration)
    if blob is None:
        return None
    access_token = blob.get("access_token")
    ig_user_id = blob.get("ig_user_id")
    if not access_token or not ig_user_id:
        return None
    return str(access_token), str(ig_user_id)


def ensure_fresh_token(session, integration: Integration) -> None:
    """Re-extend an OAuth long-lived token in place when near expiry.

    No-op for manual-token rows (no ``auth_method='oauth'`` / no
    ``expires_at``) — they're rotated by hand. Only OAuth rows within the
    refresh window are re-exchanged via Meta's ``fb_exchange_token``. The
    refreshed token + new ``expires_at`` are persisted back to the row
    (``session.add``; the caller owns the commit). Never raises — on
    failure it logs and leaves the existing token, so the sync can still
    try (and surface its own error if the token is truly dead).
    """
    blob = _load_blob(integration)
    if blob is None:
        return
    if blob.get("auth_method") != "oauth":
        return  # manual-token row — nothing to refresh

    expires_at_str = blob.get("expires_at")
    try:
        expires_at = datetime.fromisoformat(expires_at_str) if expires_at_str else None
    except (ValueError, TypeError):
        expires_at = None
    if expires_at is None:
        return
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    remaining = (expires_at - datetime.now(timezone.utc)).total_seconds()
    if remaining > _REFRESH_WINDOW_SECONDS:
        return  # still fresh — no refresh needed

    # Within the window — re-extend the long-lived token.
    from app.services import meta_oauth

    try:
        refreshed = meta_oauth.refresh_long_lived(blob["access_token"])
        new_token = refreshed.get("access_token")
        if not new_token:
            logger.warning("instagram token refresh: no access_token in response")
            return
        blob["access_token"] = new_token
        blob["expires_at"] = meta_oauth.compute_expiry(
            refreshed.get("expires_in")
        ).isoformat()
        integration.credentials_encrypted = app_secrets.encrypt(json.dumps(blob))
        session.add(integration)
        logger.info("instagram token refreshed — new expiry %s", blob["expires_at"])
    except Exception as exc:  # noqa: BLE001 — refresh is best-effort
        logger.warning("instagram token refresh failed: %s", exc)
