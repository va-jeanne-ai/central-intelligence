"""GHL integration credential loading.

Shared between the pull sync task (``tasks/ghl_sync``) and the push
helper (``services/ghl_push``). Both need the same decrypt + extract
flow against the ``integrations.credentials_encrypted`` blob.

Returns None when credentials are missing or unparseable so callers
can stamp the integration as misconfigured rather than crashing.
"""

from __future__ import annotations

import json
import logging

from app.models.integration import Integration
from app.services import secrets as app_secrets

logger = logging.getLogger(__name__)


def load_ghl_credentials(integration: Integration) -> tuple[str, str] | None:
    """Decrypt + extract ``(api_access_token, location_id)`` from the blob.

    Returns ``None`` on any of: empty blob, decrypt failure, JSON parse
    failure, missing fields. The caller decides whether to set
    ``integration.last_sync_status = "error"`` and abort.
    """
    if not integration.credentials_encrypted:
        return None
    try:
        blob = json.loads(app_secrets.decrypt(integration.credentials_encrypted))
    except (ValueError, json.JSONDecodeError) as exc:
        logger.warning("load_ghl_credentials: decrypt failed — %s", exc)
        return None
    access_token = blob.get("api_access_token")
    location_id = blob.get("location_id")
    if not access_token or not location_id:
        return None
    return str(access_token), str(location_id)
