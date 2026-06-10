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
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.models.audit import AuditLog
from app.models.operational import Appointment, Lead, Member
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


def _pick_from(
    payload: dict[str, Any], variants: dict[str, tuple[str, ...]], key: str
) -> str | None:
    """Return the first non-empty value from ``variants[key]`` in payload."""
    for variant in variants.get(key, ()):
        value = payload.get(variant)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _pick(payload: dict[str, Any], key: str) -> str | None:
    """Return the first non-empty value from GHL_FIELD_VARIANTS[key] in payload."""
    return _pick_from(payload, GHL_FIELD_VARIANTS, key)


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


# ---------------------------------------------------------------------------
# Appointment upsert (inbound GHL appointment webhook)
# ---------------------------------------------------------------------------
#
# GHL's appointment/calendar webhook payload shape isn't pinned (varies by
# trigger). Same tolerant field-variant approach as leads. Dedup is on
# (source='ghl', external_id) ONLY — a contact can have many appointments, so
# there is no email fallback. lead_id/member_id are best-effort links and stay
# nullable when no match is found.

GHL_APPT_FIELD_VARIANTS: dict[str, tuple[str, ...]] = {
    "external_id": ("appointment_id", "appointmentId", "id", "calendar_event_id", "eventId"),
    "contact_id": ("contact_id", "contactId", "Contact Id"),
    "contact_email": ("email", "contact_email", "Email"),
    "contact_name": ("full_name", "fullName", "name", "contact_name", "Full Name"),
    "contact_phone": ("phone", "contact_phone", "phoneNumber", "Phone"),
    "status": ("appointmentStatus", "appointment_status", "status", "Status"),
    "appointment_type": ("calendar_name", "calendarName", "title", "appointment_type", "calendar"),
    "scheduled_at": ("start_time", "startTime", "selectedSlot", "scheduled_at", "startAt"),
    "end_at": ("end_time", "endTime", "endAt"),
}

# Normalize GHL status strings → our vocabulary. Default 'booked'.
_GHL_APPT_STATUS_MAP: dict[str, str] = {
    "booked": "booked",
    "confirmed": "confirmed",
    "showed": "showed",
    "show": "showed",
    "noshow": "no-show",
    "no-show": "no-show",
    "no_show": "no-show",
    "cancelled": "cancelled",
    "canceled": "cancelled",
    "rescheduled": "rescheduled",
    "invalid": "cancelled",
}


def _normalize_appt_status(raw: str | None) -> str:
    if not raw:
        return "booked"
    key = raw.strip().lower().replace(" ", "")
    return _GHL_APPT_STATUS_MAP.get(key, raw.strip().lower())


def _parse_dt(value: str | None) -> datetime | None:
    """Tolerant datetime parse: ISO string, or epoch-ms/epoch-s numeric."""
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    # Numeric epoch (GHL sometimes sends ms).
    if text.isdigit():
        ts = int(text)
        if ts > 1_000_000_000_000:  # milliseconds
            ts //= 1000
        try:
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        except (ValueError, OSError, OverflowError):
            return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


async def upsert_ghl_appointment(
    session: AsyncSession, payload: dict[str, Any]
) -> tuple[Appointment, bool]:
    """Insert-or-update an Appointment from a normalised GHL payload.

    Returns ``(appointment, inserted)``. Dedup on (source='ghl',
    external_id). Best-effort links to a Lead (by source+external_id then
    email) and a Member (by email); both stay nullable when unmatched.
    Stores the raw payload JSON in ``notes``. Never commits.

    INSERT → ``appointment.created`` audit event. UPDATE → emits
    ``appointment.status_changed`` / ``appointment.rescheduled`` only when the
    status or scheduled time actually changes (so book→reschedule→cancel shows
    on the timeline without spamming it).
    """
    external_id = _pick_from(payload, GHL_APPT_FIELD_VARIANTS, "external_id")
    contact_id = _pick_from(payload, GHL_APPT_FIELD_VARIANTS, "contact_id")
    contact_email = _pick_from(payload, GHL_APPT_FIELD_VARIANTS, "contact_email")
    if contact_email:
        contact_email = contact_email.lower().strip()
    contact_name = _pick_from(payload, GHL_APPT_FIELD_VARIANTS, "contact_name")
    contact_phone = _pick_from(payload, GHL_APPT_FIELD_VARIANTS, "contact_phone")
    status = _normalize_appt_status(_pick_from(payload, GHL_APPT_FIELD_VARIANTS, "status"))
    appt_type = _pick_from(payload, GHL_APPT_FIELD_VARIANTS, "appointment_type")
    scheduled_at = _parse_dt(_pick_from(payload, GHL_APPT_FIELD_VARIANTS, "scheduled_at"))
    end_at = _parse_dt(_pick_from(payload, GHL_APPT_FIELD_VARIANTS, "end_at"))
    notes_json = json.dumps(payload, default=str)

    # --- Best-effort lead link -------------------------------------------
    lead_id: uuid.UUID | None = None
    if contact_id:
        res = await session.execute(
            select(Lead.id).where(
                Lead.source == "ghl",
                Lead.external_id == contact_id,
                Lead.deleted_at.is_(None),
            )
        )
        lead_id = res.scalar_one_or_none()
    if lead_id is None and contact_email:
        res = await session.execute(
            select(Lead.id).where(
                Lead.email == contact_email,
                Lead.deleted_at.is_(None),
            )
        )
        lead_id = res.scalar_one_or_none()

    # --- Best-effort member link -----------------------------------------
    member_id: uuid.UUID | None = None
    if contact_email:
        res = await session.execute(
            select(Member.id).where(
                Member.email == contact_email,
                Member.deleted_at.is_(None),
            )
        )
        member_id = res.scalar_one_or_none()

    # --- Lookup (dedup on source+external_id only) -----------------------
    row: Appointment | None = None
    if external_id:
        res = await session.execute(
            select(Appointment).where(
                Appointment.source == "ghl",
                Appointment.external_id == external_id,
                Appointment.deleted_at.is_(None),
            )
        )
        row = res.scalar_one_or_none()

    if row is None:
        row = Appointment(
            lead_id=lead_id,
            member_id=member_id,
            contact_name=contact_name,
            contact_email=contact_email,
            contact_phone=contact_phone,
            status=status,
            appointment_type=appt_type,
            scheduled_at=scheduled_at,
            end_at=end_at,
            source="ghl",
            external_id=external_id,
            notes=notes_json,
        )
        session.add(row)
        await session.flush()
        await record_event(
            session,
            user_id=None,
            action="appointment.created",
            table_name="appointments",
            record_id=str(row.id),
            after={
                "contact_name": contact_name,
                "contact_email": contact_email,
                "status": status,
                "scheduled_at": scheduled_at.isoformat() if scheduled_at else None,
                "external_id": external_id,
            },
        )
        logger.info(
            "upsert_ghl_appointment: INSERT external_id=%s status=%s", external_id, status
        )
        return row, True

    # UPDATE — partial-merge; detect meaningful changes for the audit trail.
    prev_status = row.status
    prev_scheduled = row.scheduled_at

    if contact_name:
        row.contact_name = contact_name
    if contact_email:
        row.contact_email = contact_email
    if contact_phone:
        row.contact_phone = contact_phone
    if appt_type:
        row.appointment_type = appt_type
    if scheduled_at:
        row.scheduled_at = scheduled_at
    if end_at:
        row.end_at = end_at
    if lead_id and not row.lead_id:
        row.lead_id = lead_id
    if member_id and not row.member_id:
        row.member_id = member_id
    row.status = status
    row.notes = notes_json

    if scheduled_at and prev_scheduled and scheduled_at != prev_scheduled:
        await record_event(
            session,
            user_id=None,
            action="appointment.rescheduled",
            table_name="appointments",
            record_id=str(row.id),
            before={"scheduled_at": prev_scheduled.isoformat()},
            after={"scheduled_at": scheduled_at.isoformat()},
        )
    if status != prev_status:
        await record_event(
            session,
            user_id=None,
            action="appointment.status_changed",
            table_name="appointments",
            record_id=str(row.id),
            before={"status": prev_status},
            after={"status": status},
        )

    logger.info(
        "upsert_ghl_appointment: UPDATE id=%s external_id=%s status=%s",
        row.id, external_id, status,
    )
    return row, False
