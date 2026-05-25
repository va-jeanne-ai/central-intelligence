"""CI → GHL reverse-sync push helper.

Called inline from ``PATCH /leads/{id}`` (and from the Celery retry task
when the inline path fails). For a single lead, this:

1. Confirms the lead is GHL-linked (source='ghl', external_id set).
2. Loads the GHL integration row + credentials (shared with the pull sync).
3. GETs the GHL contact and compares ``dateUpdated`` against our
   ``integration.last_synced_at`` — if GHL is newer, refuses to push.
4. Builds a custom-fields payload with the CI-side values we want GHL
   to see (status, score, latest note preview, last call date).
5. PUTs it.

Returns a result tuple ``(status, details_dict)`` that the caller turns
into an audit event:

  - ``("ok", {...})``
  - ``("conflict_refused", {...})``
  - ``("error", {...})``
  - ``("skipped_not_ghl", {})``
  - ``("skipped_no_integration", {})``
  - ``("skipped_kill_switch", {})``

Never raises — the caller is on the request hot path and shouldn't see
exceptions from a side-effect.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.integration import Integration
from app.services import ghl_client
from app.services.ghl_credentials import load_ghl_credentials

logger = logging.getLogger(__name__)


# CI-side field keys → GHL custom-field keys. Defaults match the field
# names documented in the verification steps. If GHL deployments use a
# different key naming convention, override via integration.config
# (key: "ghl_custom_field_keys").
DEFAULT_CUSTOM_FIELD_KEYS: dict[str, str] = {
    "status": "ci_status",
    "score": "ci_score",
    "last_note_preview": "ci_last_note_preview",
    "last_call_date": "ci_last_call_date",
}

_NOTE_PREVIEW_CHARS = 200


PushResult = tuple[str, dict[str, Any]]


async def _fetch_lead_context(
    session: AsyncSession, lead_id: str
) -> dict[str, Any] | None:
    """Pull the per-push payload pieces in one round trip.

    Returns None if the lead doesn't exist or has no GHL linkage. The
    caller turns None into a ``skipped_not_ghl`` result.
    """
    row = (await session.execute(
        text("""
            SELECT
                l.id::text AS id,
                l.external_id,
                l.source,
                l.status,
                l.updated_at,
                (
                    SELECT body FROM lead_notes
                    WHERE lead_id = l.id
                    ORDER BY created_at DESC
                    LIMIT 1
                ) AS latest_note_body,
                (
                    SELECT date FROM calls
                    WHERE lead_id = l.id AND deleted_at IS NULL
                    ORDER BY date DESC NULLS LAST, created_at DESC
                    LIMIT 1
                ) AS latest_call_date
            FROM leads l
            WHERE l.id = :id AND l.deleted_at IS NULL
        """),
        {"id": lead_id},
    )).mappings().one_or_none()
    if row is None:
        return None
    return dict(row)


def _build_payload(
    *,
    api_status: str | None,
    score: int,
    latest_note: str | None,
    latest_call_date: datetime | None,
    custom_field_keys: dict[str, str],
) -> dict[str, Any]:
    """Compose GHL v2 customFields update payload."""
    fields = []
    if api_status is not None:
        fields.append({
            "key": custom_field_keys.get("status", "ci_status"),
            "value": api_status,
        })
    fields.append({
        "key": custom_field_keys.get("score", "ci_score"),
        "value": str(score),
    })
    if latest_note:
        preview = latest_note[:_NOTE_PREVIEW_CHARS].rstrip()
        fields.append({
            "key": custom_field_keys.get("last_note_preview", "ci_last_note_preview"),
            "value": preview,
        })
    if latest_call_date:
        fields.append({
            "key": custom_field_keys.get("last_call_date", "ci_last_call_date"),
            "value": latest_call_date.isoformat(),
        })
    return {"customFields": fields}


def _parse_iso(value: str | None) -> datetime | None:
    """Tolerant ISO parse — GHL returns dates in a few formats."""
    if not value:
        return None
    # Normalize trailing Z → +00:00 (Python <3.11 doesn't accept Z directly).
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


async def push_lead_update(
    session: AsyncSession,
    lead_id: str,
    *,
    api_status: str | None,
    score: int,
) -> PushResult:
    """Push CI-side state for one lead to its matching GHL contact.

    Caller passes the freshly-derived ``api_status`` + ``score`` (post-
    PATCH state) so we don't refetch the lead row just for those.
    Returns one of the documented result tuples; never raises.
    """
    try:
        ctx = await _fetch_lead_context(session, lead_id)
    except Exception as exc:  # noqa: BLE001 — defensive on a side-effect
        logger.exception("ghl_push: lead context fetch failed for %s", lead_id)
        return ("error", {"reason": "context_fetch_failed", "detail": str(exc)[:300]})

    if ctx is None:
        return ("skipped_not_ghl", {"reason": "lead_not_found"})
    external_id = ctx.get("external_id")
    if ctx.get("source") != "ghl" or not external_id:
        return ("skipped_not_ghl", {
            "source": ctx.get("source"),
            "external_id": external_id,
        })

    integration = (await session.execute(
        select(Integration).where(
            Integration.provider == "ghl",
            Integration.status == "connected",
        )
    )).scalar_one_or_none()
    if integration is None:
        return ("skipped_no_integration", {})

    # Kill switch: integration.config["push_enabled"] = False disables.
    # Default is on. Saves having to disconnect the integration when the
    # GHL custom fields aren't set up yet.
    config = integration.config or {}
    if config.get("push_enabled") is False:
        return ("skipped_kill_switch", {})

    creds = load_ghl_credentials(integration)
    if creds is None:
        return ("error", {"reason": "missing_credentials"})
    access_token, _location_id = creds

    custom_field_keys: dict[str, str] = {
        **DEFAULT_CUSTOM_FIELD_KEYS,
        **(config.get("ghl_custom_field_keys") or {}),
    }

    # 1. Conflict check — fetch the contact, compare dateUpdated.
    try:
        contact = ghl_client.get_contact(access_token, str(external_id))
    except Exception as exc:  # noqa: BLE001
        logger.warning("ghl_push: get_contact failed lead=%s — %s", lead_id, exc)
        return ("error", {"reason": "get_contact_failed", "detail": str(exc)[:300]})

    ghl_updated = _parse_iso(
        (contact.get("contact") or contact).get("dateUpdated")
    )
    last_synced = integration.last_synced_at
    if (
        ghl_updated is not None
        and last_synced is not None
        and ghl_updated > last_synced
    ):
        return ("conflict_refused", {
            "ghl_date_updated": ghl_updated.isoformat(),
            "last_synced_at": last_synced.isoformat(),
        })

    # 2. Build + PUT.
    payload = _build_payload(
        api_status=api_status,
        score=score,
        latest_note=ctx.get("latest_note_body"),
        latest_call_date=ctx.get("latest_call_date"),
        custom_field_keys=custom_field_keys,
    )
    try:
        ghl_client.update_contact(access_token, str(external_id), payload)
    except Exception as exc:  # noqa: BLE001
        logger.warning("ghl_push: update_contact failed lead=%s — %s", lead_id, exc)
        return ("error", {
            "reason": "update_contact_failed",
            "detail": str(exc)[:300],
            "fields": [f["key"] for f in payload.get("customFields", [])],
        })

    return ("ok", {
        "external_id": str(external_id),
        "fields": [f["key"] for f in payload.get("customFields", [])],
    })
