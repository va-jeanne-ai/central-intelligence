"""CI → GHL push — Celery retry task.

Fires when the inline push from ``PATCH /leads`` failed (network blip,
GHL hiccup). Mirrors ``services/ghl_push.push_lead_update`` against a
sync SQLAlchemy session so it runs cleanly inside a Celery worker.

Retry policy: 3 attempts, 120s base delay (Celery handles backoff).
After max retries, the failure is logged + a final audit event is
written, then the task gives up — the staff edit stays in CI and the
nightly pull sync will resurface the GHL ↔ CI divergence on its next
run.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any

from celery.exceptions import MaxRetriesExceededError
from sqlalchemy import select, text

from app.models.audit import AuditLog
from app.models.integration import Integration
from app.services import ghl_client
from app.services.ghl_credentials import load_ghl_credentials
from app.services.ghl_push import DEFAULT_CUSTOM_FIELD_KEYS, _build_payload, _parse_iso
from app.tasks.celery_app import celery_app
from app.tasks.db import make_sync_session

logger = logging.getLogger(__name__)


def _emit_audit_sync(
    session: Any,
    *,
    lead_id: str,
    status: str,
    details: dict[str, Any],
) -> None:
    """Inline AuditLog row construction. The async record_event helper
    can't run from a sync session — we mirror it here."""
    session.add(AuditLog(
        id=uuid.uuid4(),
        user_id=None,  # async retry has no acting user
        action="lead.pushed_to_ghl",
        table_name="leads",
        record_id=lead_id,
        after_value={"status": status, **details},
    ))


@celery_app.task(
    bind=True,
    name="app.tasks.ghl_push.push_lead_to_ghl_async",
    max_retries=3,
    default_retry_delay=120,
)
def push_lead_to_ghl_async(self, lead_id: str) -> dict[str, Any]:
    """Retry the push for one lead. Returns the result tuple flattened."""
    with make_sync_session() as session:
        row = session.execute(
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
        ).mappings().one_or_none()

        if row is None:
            logger.info("ghl_push_retry: lead %s not found", lead_id)
            return {"status": "skipped_not_ghl", "reason": "lead_not_found"}

        if row["source"] != "ghl" or not row["external_id"]:
            return {"status": "skipped_not_ghl", "external_id": row["external_id"]}

        integration = session.execute(
            select(Integration).where(
                Integration.provider == "ghl",
                Integration.status == "connected",
            )
        ).scalar_one_or_none()
        if integration is None:
            _emit_audit_sync(session, lead_id=lead_id, status="skipped_no_integration", details={})
            session.commit()
            return {"status": "skipped_no_integration"}

        config = integration.config or {}
        if config.get("push_enabled") is False:
            _emit_audit_sync(session, lead_id=lead_id, status="skipped_kill_switch", details={})
            session.commit()
            return {"status": "skipped_kill_switch"}

        creds = load_ghl_credentials(integration)
        if creds is None:
            _emit_audit_sync(
                session, lead_id=lead_id, status="error",
                details={"reason": "missing_credentials"},
            )
            session.commit()
            return {"status": "error", "reason": "missing_credentials"}
        access_token, _location_id = creds

        custom_field_keys: dict[str, str] = {
            **DEFAULT_CUSTOM_FIELD_KEYS,
            **(config.get("ghl_custom_field_keys") or {}),
        }

        # --- conflict check + push -------------------------------------
        try:
            contact = ghl_client.get_contact(access_token, str(row["external_id"]))
        except Exception as exc:  # noqa: BLE001
            logger.warning("ghl_push_retry: get_contact failed — %s", exc)
            try:
                raise self.retry(exc=exc)
            except MaxRetriesExceededError:
                logger.error("ghl_push_retry: max retries exceeded for lead=%s", lead_id)
                _emit_audit_sync(
                    session, lead_id=lead_id, status="error",
                    details={"reason": "get_contact_failed_final", "detail": str(exc)[:300]},
                )
                session.commit()
                return {"status": "error", "reason": "get_contact_failed_final"}

        ghl_updated = _parse_iso(
            (contact.get("contact") or contact).get("dateUpdated")
        )
        last_synced = integration.last_synced_at
        if (
            ghl_updated is not None
            and last_synced is not None
            and ghl_updated > last_synced
        ):
            _emit_audit_sync(
                session, lead_id=lead_id, status="conflict_refused",
                details={
                    "ghl_date_updated": ghl_updated.isoformat(),
                    "last_synced_at": last_synced.isoformat(),
                },
            )
            session.commit()
            return {"status": "conflict_refused"}

        api_status_from_db = _api_status_for(row["status"])
        score = _score_for_db_status(row["status"])

        latest_call_date = row["latest_call_date"]
        if isinstance(latest_call_date, str):
            latest_call_date = _parse_iso(latest_call_date)
        elif not isinstance(latest_call_date, datetime):
            latest_call_date = None

        payload = _build_payload(
            api_status=api_status_from_db,
            score=score,
            latest_note=row["latest_note_body"],
            latest_call_date=latest_call_date,
            custom_field_keys=custom_field_keys,
        )

        try:
            ghl_client.update_contact(access_token, str(row["external_id"]), payload)
        except Exception as exc:  # noqa: BLE001
            logger.warning("ghl_push_retry: update_contact failed — %s", exc)
            try:
                raise self.retry(exc=exc)
            except MaxRetriesExceededError:
                logger.error("ghl_push_retry: max retries exceeded for lead=%s", lead_id)
                _emit_audit_sync(
                    session, lead_id=lead_id, status="error",
                    details={
                        "reason": "update_contact_failed_final",
                        "detail": str(exc)[:300],
                    },
                )
                session.commit()
                return {"status": "error", "reason": "update_contact_failed_final"}

        _emit_audit_sync(
            session, lead_id=lead_id, status="ok",
            details={
                "external_id": str(row["external_id"]),
                "fields": [f["key"] for f in payload.get("customFields", [])],
                "retried_async": True,
            },
        )
        session.commit()
        return {"status": "ok"}


# --- DB↔API status helpers (duplicated to keep this task standalone) -----
# routes/leads.py owns the canonical _map_status + _score_for_status, but
# those are async-context-only and pulling them here would force a route
# import inside a task. Keep these small mirrors instead.

_DB_TO_API: dict[str, str] = {
    "appointment-set": "appointment_set",
    "sale": "closed_won",
    "lost": "closed_lost",
    "new": "new",
    "contacted": "contacted",
    "qualified": "qualified",
    "stale": "stale",
}

_STATUS_SCORE: dict[str, int] = {
    "new": 20,
    "contacted": 40,
    "qualified": 60,
    "appointment_set": 70,
    "closed_won": 95,
    "closed_lost": 10,
    "stale": 5,
}


def _api_status_for(db_status: str | None) -> str | None:
    if db_status is None:
        return None
    return _DB_TO_API.get(db_status.lower(), db_status.lower())


def _score_for_db_status(db_status: str | None) -> int:
    api = _api_status_for(db_status)
    if api is None:
        return 0
    return _STATUS_SCORE.get(api, 0)
