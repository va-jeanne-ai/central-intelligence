"""Instagram (Meta Graph API) integration credential loading.

Mirrors ``ghl_credentials.py``: decrypt the ``integrations.credentials_encrypted``
blob for the Instagram provider and extract ``(access_token, ig_user_id)``.

Returns None when credentials are missing or unparseable so callers can stamp
the integration as misconfigured (or simply skip it) rather than crashing.
"""

from __future__ import annotations

import json
import logging

from app.models.integration import Integration
from app.services import secrets as app_secrets

logger = logging.getLogger(__name__)


def load_instagram_credentials(integration: Integration) -> tuple[str, str] | None:
    """Decrypt + extract ``(access_token, ig_user_id)`` from the blob.

    Returns ``None`` on any of: empty blob, decrypt failure, JSON parse
    failure, missing fields. The caller decides whether to set
    ``integration.last_sync_status = "error"`` and abort/skip.
    """
    if not integration.credentials_encrypted:
        return None
    try:
        blob = json.loads(app_secrets.decrypt(integration.credentials_encrypted))
    except (ValueError, json.JSONDecodeError) as exc:
        logger.warning("load_instagram_credentials: decrypt failed — %s", exc)
        return None
    access_token = blob.get("access_token")
    ig_user_id = blob.get("ig_user_id")
    if not access_token or not ig_user_id:
        return None
    return str(access_token), str(ig_user_id)
