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

from app.database import get_session
from app.models.integration import Integration
from app.models.operational import Lead
from app.services import secrets as app_secrets

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


# ---------------------------------------------------------------------------
# GHL — payload field-name variants
# ---------------------------------------------------------------------------
# GHL's workflow Custom Webhook action sends whatever the user mapped, and
# field names vary across triggers (Form Submitted vs Contact Created vs
# Tag Added). The values here are tried in order; first hit wins.

GHL_FIELD_VARIANTS: dict[str, tuple[str, ...]] = {
    "email": ("email", "contact_email", "Email"),
    "external_id": ("contact_id", "contactId", "id", "Contact Id"),
    "first_name": ("first_name", "firstName", "First Name"),
    "last_name": ("last_name", "lastName", "Last Name"),
    "full_name": ("full_name", "fullName", "name", "contact_name", "Full Name"),
    "phone": ("phone", "contact_phone", "phoneNumber", "Phone"),
    "status": ("status", "lead_status", "Status"),
    "source": ("source", "contact_source", "Source"),
}


def _pick(payload: dict[str, Any], key: str) -> str | None:
    """Return the first non-empty value from GHL_FIELD_VARIANTS[key] in payload."""
    for variant in GHL_FIELD_VARIANTS.get(key, ()):
        value = payload.get(variant)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _derive_name(payload: dict[str, Any]) -> str | None:
    """Build a single name string from common GHL shapes."""
    full = _pick(payload, "full_name")
    if full:
        return full
    first = _pick(payload, "first_name") or ""
    last = _pick(payload, "last_name") or ""
    combined = f"{first} {last}".strip()
    return combined or None


# ---------------------------------------------------------------------------
# GHL lead webhook
# ---------------------------------------------------------------------------


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
    # 1. Find the GHL integration row, validate the path token.
    result = await session.execute(
        select(Integration).where(
            Integration.provider == "ghl",
            Integration.status == "connected",
        )
    )
    row = result.scalar_one_or_none()
    if row is None or not row.credentials_encrypted:
        # No integration row → URL was guessed. 404 to avoid confirming
        # that a token-shaped URL exists.
        raise HTTPException(status_code=404, detail="Not found")

    try:
        blob = json.loads(app_secrets.decrypt(row.credentials_encrypted))
        stored_token = str(blob.get("webhook_token") or "")
    except (ValueError, json.JSONDecodeError) as exc:
        logger.warning("ghl_lead_webhook: decrypt failed — %s", exc)
        raise HTTPException(status_code=404, detail="Not found") from exc

    if not stored_token or not _stdlib_secrets.compare_digest(
        stored_token.encode("utf-8"), webhook_token.encode("utf-8")
    ):
        # Constant-time compare so the timing of mismatched tokens leaks
        # nothing about the real token's prefix length.
        raise HTTPException(status_code=404, detail="Not found")

    # 2. Upsert the lead, swallow errors so GHL doesn't retry-storm.
    now = datetime.now(timezone.utc)
    try:
        await _upsert_ghl_lead(session, payload)
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


async def _upsert_ghl_lead(
    session: AsyncSession, payload: dict[str, Any]
) -> Lead:
    """Insert-or-update a Lead from a normalised GHL payload.

    Dedup order:
      1. ``(source='ghl', external_id=<contact_id>)`` — survives email
         changes and rename storms upstream.
      2. ``email`` (lowercased + stripped) — catches contacts the user
         imported without a stable contact_id mapping.

    Either branch updates the existing row in place. New contacts insert.
    The full raw payload is JSON-stringified into ``lead.notes`` so
    downstream queries can still recover anything we didn't normalise.
    """
    email = _pick(payload, "email")
    if email:
        email = email.lower().strip()
    external_id = _pick(payload, "external_id")
    name = _derive_name(payload)
    phone = _pick(payload, "phone")
    upstream_source = _pick(payload, "source")
    upstream_status = _pick(payload, "status")

    # --- Lookup ----------------------------------------------------------
    row: Lead | None = None
    if external_id:
        result = await session.execute(
            select(Lead).where(
                Lead.source == "ghl",
                Lead.external_id == external_id,
                Lead.deleted_at.is_(None),
            )
        )
        row = result.scalar_one_or_none()
    if row is None and email:
        result = await session.execute(
            select(Lead).where(
                Lead.email == email,
                Lead.deleted_at.is_(None),
            )
        )
        row = result.scalar_one_or_none()

    notes_json = json.dumps(payload, default=str)

    if row is None:
        # Insert.
        row = Lead(
            name=name,
            email=email,
            phone=phone,
            status=upstream_status or "new",
            source="ghl",
            external_id=external_id,
            notes=notes_json,
        )
        session.add(row)
        logger.info(
            "ghl_lead_webhook: INSERT email=%s external_id=%s",
            email, external_id,
        )
    else:
        # Update — only overwrite non-empty fields so a partial GHL
        # payload (e.g. tag-added trigger) doesn't blank our enrichment.
        if name:
            row.name = name
        if phone:
            row.phone = phone
        if email and not row.email:
            # Email is unique-indexed; only fill it if we didn't have one.
            # Mid-life email changes are rare and dangerous to auto-apply.
            row.email = email
        if upstream_status:
            row.status = upstream_status
        # Always set source + external_id so future dedups land on path 1.
        row.source = "ghl"
        if external_id:
            row.external_id = external_id
        row.notes = notes_json
        logger.info(
            "ghl_lead_webhook: UPDATE id=%s email=%s external_id=%s",
            row.id, email, external_id,
        )

    return row
