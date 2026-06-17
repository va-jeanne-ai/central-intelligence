"""
Inbound webhook receivers for push-based integrations.

All routes here run WITHOUT a JWT — third parties (GHL, future Stripe /
Calendly, etc.) have no Supabase session. The path is exempted from
``AuthMiddleware`` via ``_EXEMPT_PREFIXES`` in ``app/middleware/auth.py``.
Per-integration tokens in the URL path are the auth mechanism; tokens
live in the encrypted credential blob on the matching ``integrations``
row.

Current routes:
  - POST /api/v1/webhooks/ghl/{webhook_token}/leads — accept a contact
    payload from a GHL Custom Webhook workflow action.

Adding a new webhook route:
  1. Make sure the path falls under ``/api/v1/webhooks/`` (already
     exempted from auth).
  2. Generate the token via the integrations-page connect flow
     (``_upsert_webhook_only`` in ``app/routes/integrations.py``).
  3. In the route handler, look up the integration row, compare the
     path token with ``secrets.compare_digest``, return 404 on mismatch
     so the URL never confirms its own shape.
  4. Stamp ``last_synced_at`` / ``last_sync_status`` on success so the
     integration page surfaces "Last seen 2 min ago".
"""

from __future__ import annotations

import json
import logging
import secrets as _stdlib_secrets
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_session
from app.models.integration import Integration
from app.services import secrets as app_secrets
from app.services.ghl_upsert import upsert_ghl_appointment, upsert_ghl_lead

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


async def _resolve_ghl_integration(
    session: AsyncSession, webhook_token: str
) -> Integration:
    """Return the connected GHL integration row IFF the path token matches.

    Constant-time token compare against the encrypted blob's webhook_token.
    Raises 404 on any mismatch / missing row / decrypt failure — never 401,
    so a probing attacker can't confirm a token-shaped URL is valid.
    """
    result = await session.execute(
        select(Integration).where(
            Integration.provider == "ghl",
            Integration.status == "connected",
        )
    )
    row = result.scalar_one_or_none()
    if row is None or not row.credentials_encrypted:
        raise HTTPException(status_code=404, detail="Not found")

    try:
        blob = json.loads(app_secrets.decrypt(row.credentials_encrypted))
        stored_token = str(blob.get("webhook_token") or "")
    except (ValueError, json.JSONDecodeError) as exc:
        logger.warning("ghl webhook: decrypt failed — %s", exc)
        raise HTTPException(status_code=404, detail="Not found") from exc

    if not stored_token or not _stdlib_secrets.compare_digest(
        stored_token.encode("utf-8"), webhook_token.encode("utf-8")
    ):
        raise HTTPException(status_code=404, detail="Not found")

    return row


# ---------------------------------------------------------------------------
# GHL lead webhook
# ---------------------------------------------------------------------------
# Field-name normalization + the dedup-and-upsert logic itself live in
# ``app/services/ghl_upsert.py`` so the nightly sync task can reuse them.


@router.post("/ghl/{webhook_token}/leads")
async def ghl_lead_webhook(
    webhook_token: str,
    payload: dict[str, Any] = Body(...),
    session: AsyncSession = Depends(get_session),
):
    """Receive a contact pushed from GHL's Custom Webhook workflow action.

    Auth model: the path token is compared (constant-time) against the
    token stored in the matching ``integrations`` row's encrypted blob.
    On mismatch we return 404, never 401 — we don't want a probing
    attacker to confirm a token-shaped URL is valid.

    Idempotency: dedup tries ``(source='ghl', external_id=contact_id)``
    first, then falls back to ``email`` lookup. The full raw payload
    lands in ``lead.notes`` as JSON so nothing is lost across GHL trigger
    types (form vs workflow vs tag-added all have different field shapes).

    Error tolerance: parse failures stamp ``last_sync_error`` on the
    integration row but still return 200 — GHL retries aggressively on
    non-2xx and we don't want a malformed payload to retry-storm us.
    """
    # 0. Direct GHL ingestion is disabled in favour of the WGR mirror upstream.
    #    Validate the token first (so a bad token still 404s and reveals nothing),
    #    then refuse with 410 Gone.
    row = await _resolve_ghl_integration(session, webhook_token)
    if not settings.ghl_inbound_enabled:
        raise HTTPException(
            status_code=410,
            detail="Direct GHL ingestion is disabled; CI sources this data from the WGR mirror.",
        )

    # 2. Upsert the lead, swallow errors so GHL doesn't retry-storm.
    now = datetime.now(timezone.utc)
    try:
        await upsert_ghl_lead(session, payload)
        row.last_synced_at = now
        row.last_sync_status = "ok"
        row.last_sync_error = None
    except Exception as exc:  # noqa: BLE001 — broad on purpose
        logger.exception("ghl_lead_webhook: upsert failed — %s", exc)
        row.last_sync_status = "error"
        row.last_sync_error = str(exc)[:500]

    session.add(row)
    await session.commit()
    return {"ok": True}


# ---------------------------------------------------------------------------
# GHL appointment webhook
# ---------------------------------------------------------------------------
# Book / reschedule / cancel events from GHL's calendar triggers. Same token
# validation as the lead webhook; upsert + dedup live in ghl_upsert.py.


@router.post("/ghl/{webhook_token}/appointments")
async def ghl_appointment_webhook(
    webhook_token: str,
    payload: dict[str, Any] = Body(...),
    session: AsyncSession = Depends(get_session),
):
    """Receive an appointment pushed from a GHL calendar webhook trigger.

    Same auth model as the lead webhook (constant-time path-token compare →
    404 on mismatch). Dedup on ``(source='ghl', external_id=<appointment id>)``
    so book → reschedule → cancel on the same appointment update one row. The
    raw payload lands in ``appointment.notes`` as JSON. Parse failures stamp
    ``last_sync_error`` but still return 200 to avoid GHL retry-storms.
    """
    row = await _resolve_ghl_integration(session, webhook_token)
    if not settings.ghl_inbound_enabled:
        raise HTTPException(
            status_code=410,
            detail="Direct GHL ingestion is disabled; CI sources this data from the WGR mirror.",
        )

    now = datetime.now(timezone.utc)
    try:
        await upsert_ghl_appointment(session, payload)
        row.last_synced_at = now
        row.last_sync_status = "ok"
        row.last_sync_error = None
    except Exception as exc:  # noqa: BLE001 — broad on purpose
        logger.exception("ghl_appointment_webhook: upsert failed — %s", exc)
        row.last_sync_status = "error"
        row.last_sync_error = str(exc)[:500]

    session.add(row)
    await session.commit()
    return {"ok": True}
