"""Per-user OAuth credential loader for Google APIs.

Reads ``user_integration_credentials`` for a given user_id, decrypts
the blob, refreshes the access token if expired, and returns a
``google.oauth2.credentials.Credentials`` object that any Google API
client (Gmail, Drive, Calendar) can use.

Returns ``None`` when the user hasn't connected — callers treat that
as "skip this user" rather than an error.

The Google client library auto-refreshes on 401, but doing it here
lets us re-persist the new access token + expiry on disk so the next
sync run doesn't pay the refresh cost again.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone

from google.oauth2.credentials import Credentials
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.operational import UserIntegrationCredential
from app.services import secrets as app_secrets
from app.services import google_oauth

logger = logging.getLogger(__name__)


_REFRESH_SKEW_SECONDS = 60  # refresh slightly before expiry to avoid mid-call expirations


def _parse_iso(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        # Tolerate trailing Z and naive datetimes
        v = s.replace("Z", "+00:00") if s.endswith("Z") else s
        dt = datetime.fromisoformat(v)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


def load_user_oauth_credentials(
    session: Session,
    user_id: uuid.UUID,
    provider: str = "google_workspace",
) -> Credentials | None:
    """Return a ready-to-use ``Credentials`` object or ``None``.

    On a successful refresh, the new access token + expiry are written
    back to the row so subsequent runs see the freshest token.
    """
    row = session.execute(
        select(UserIntegrationCredential).where(
            UserIntegrationCredential.user_id == user_id,
            UserIntegrationCredential.provider == provider,
        )
    ).scalar_one_or_none()

    if row is None or not row.credentials_encrypted:
        return None

    try:
        blob = json.loads(app_secrets.decrypt(row.credentials_encrypted))
    except (ValueError, json.JSONDecodeError) as exc:
        logger.warning(
            "load_user_oauth_credentials: decrypt failed for user_id=%s — %s",
            user_id, exc,
        )
        return None

    refresh_token = blob.get("refresh_token")
    access_token = blob.get("access_token")
    if not refresh_token:
        logger.warning(
            "load_user_oauth_credentials: no refresh_token for user_id=%s", user_id,
        )
        return None

    expires_at = _parse_iso(blob.get("expires_at"))
    now = datetime.now(timezone.utc)
    needs_refresh = (
        access_token is None
        or expires_at is None
        or (expires_at - now).total_seconds() < _REFRESH_SKEW_SECONDS
    )

    if needs_refresh:
        try:
            fresh = google_oauth.refresh_access_token(refresh_token)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "load_user_oauth_credentials: refresh failed user_id=%s — %s",
                user_id, exc,
            )
            # Stamp the row so the UI surfaces "Reconnect needed".
            row.last_sync_status = "error"
            row.last_sync_error = f"Token refresh failed: {str(exc)[:300]}"
            session.add(row)
            return None

        access_token = fresh.get("access_token") or access_token
        new_expiry = google_oauth.compute_expiry(fresh.get("expires_in"))
        blob["access_token"] = access_token
        blob["expires_at"] = new_expiry.isoformat()
        # Google occasionally rotates the refresh token; honor that.
        if fresh.get("refresh_token"):
            blob["refresh_token"] = fresh["refresh_token"]
            refresh_token = blob["refresh_token"]

        row.credentials_encrypted = app_secrets.encrypt(json.dumps(blob))
        session.add(row)
        # Don't commit here — the caller (Celery task / route handler)
        # owns the transaction.

    return Credentials(
        token=access_token,
        refresh_token=refresh_token,
        token_uri=blob.get("token_uri") or google_oauth.TOKEN_URL,
        client_id=blob.get("client_id"),
        client_secret=blob.get("client_secret"),
        scopes=blob.get("scopes") or google_oauth.SCOPES,
    )
