"""GHL contact → Lead upsert helpers.

Shared between two callers:
  - ``routes/webhooks.py`` — handles push-mode (GHL Custom Webhook action)
  - ``tasks/ghl_sync.py`` — handles pull-mode (paginated API sweep)

Both feed the same dict-shape into ``upsert_ghl_lead(session, payload)``.
The function never commits — the caller owns the transaction.

Dedup keys (in order):
  1. ``(source='ghl', external_id=<contact_id>)`` — survives upstream
     email changes and rename storms.
  2. ``email`` lowercased + stripped — fallback for imports without a
     stable contact id.

Field-variant handling: GHL's payload shape differs across trigger types
(Form Submitted vs Tag Added vs API list) and our cron + webhook both
land here. ``GHL_FIELD_VARIANTS`` enumerates the synonyms; ``_pick``
returns the first non-empty match.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.models.audit import AuditLog
from app.models.operational import Lead
from app.services.audit import record_event

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Payload field-name variants
# ---------------------------------------------------------------------------

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
# Upsert
# ---------------------------------------------------------------------------


async def upsert_ghl_lead(
    session: AsyncSession, payload: dict[str, Any]
) -> tuple[Lead, bool]:
    """Insert-or-update a Lead from a normalised GHL payload.

    Returns ``(lead, inserted)`` where ``inserted`` is True for a fresh
    INSERT, False for an UPDATE. The caller uses this to drive counters
    (e.g. the sync task's "inserted X / updated Y" stats).

    Never blanks fields. ``lead.notes`` always carries the raw payload as
    JSON so downstream parsing (the "Initial Submission" card) works for
    both webhook and sync sources. ``staff_notes`` is a separate table
    and is never touched here.

    Emits ``lead.created`` to the audit log on the INSERT path. UPDATE
    path stays quiet — field-level audit events come from PATCH /leads,
    not from out-of-band syncs (they'd otherwise spam the history feed
    every nightly run).
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
        # Flush so row.id is populated before referenced in the audit
        # event. The caller still owns the commit.
        await session.flush()
        await record_event(
            session,
            user_id=None,  # Sync + webhook are both unauthenticated.
            action="lead.created",
            table_name="leads",
            record_id=str(row.id),
            after={
                "name": name,
                "email": email,
                "source": "ghl",
                "external_id": external_id,
            },
        )
        logger.info(
            "upsert_ghl_lead: INSERT email=%s external_id=%s",
            email, external_id,
        )
        return row, True

    # UPDATE — partial-merge so a sparse payload doesn't blank our data.
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
    # Reference upstream_source to silence unused-var warnings; we keep
    # it parsed for future use (e.g. discriminating tag-add vs form-fill).
    _ = upstream_source
    logger.info(
        "upsert_ghl_lead: UPDATE id=%s email=%s external_id=%s",
        row.id, email, external_id,
    )
    return row, False


# ---------------------------------------------------------------------------
# Sync sibling — used by the Celery sync task
# ---------------------------------------------------------------------------
#
# Celery workers use a synchronous SQLAlchemy session (psycopg2). The
# async upsert above can't be awaited from inside a sync worker without
# spinning a per-call event loop. Easier to mirror the logic against a
# sync Session and inline the audit-row construction here. Both
# implementations key on the same dedup rules and write to the same
# columns — diverge with care.


def upsert_ghl_lead_sync(
    session: Session, payload: dict[str, Any]
) -> tuple[Lead, bool]:
    """Sync mirror of :func:`upsert_ghl_lead` for Celery tasks.

    Returns ``(lead, inserted)``. Same dedup, same merge rules, same
    audit emit on INSERT. Caller owns the transaction (no commit here).
    """
    email = _pick(payload, "email")
    if email:
        email = email.lower().strip()
    external_id = _pick(payload, "external_id")
    name = _derive_name(payload)
    phone = _pick(payload, "phone")
    upstream_source = _pick(payload, "source")
    upstream_status = _pick(payload, "status")

    row: Lead | None = None
    if external_id:
        result = session.execute(
            select(Lead).where(
                Lead.source == "ghl",
                Lead.external_id == external_id,
                Lead.deleted_at.is_(None),
            )
        )
        row = result.scalar_one_or_none()
    if row is None and email:
        result = session.execute(
            select(Lead).where(
                Lead.email == email,
                Lead.deleted_at.is_(None),
            )
        )
        row = result.scalar_one_or_none()

    notes_json = json.dumps(payload, default=str)

    if row is None:
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
        session.flush()  # populate row.id before referencing in audit
        # Inline the audit row instead of calling record_event — that
        # helper is async-only. Cheaper to duplicate the 6 lines than
        # to bridge sync/async here.
        session.add(AuditLog(
            id=uuid.uuid4(),
            user_id=None,
            action="lead.created",
            table_name="leads",
            record_id=str(row.id),
            after_value={
                "name": name,
                "email": email,
                "source": "ghl",
                "external_id": external_id,
            },
        ))
        logger.info(
            "upsert_ghl_lead_sync: INSERT email=%s external_id=%s",
            email, external_id,
        )
        return row, True

    if name:
        row.name = name
    if phone:
        row.phone = phone
    if email and not row.email:
        row.email = email
    if upstream_status:
        row.status = upstream_status
    row.source = "ghl"
    if external_id:
        row.external_id = external_id
    row.notes = notes_json
    _ = upstream_source
    logger.info(
        "upsert_ghl_lead_sync: UPDATE id=%s email=%s external_id=%s",
        row.id, email, external_id,
    )
    return row, False
