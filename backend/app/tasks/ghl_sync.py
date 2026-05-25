"""GHL contacts → leads sync — Celery task.

Runs in two modes, same task:
  - Beat-scheduled nightly at 02:30 UTC (see ``celery_app.beat_schedule``)
  - On-demand from ``POST /api/v1/integrations/ghl/sync`` (via
    ``_trigger_sync("ghl")`` in ``routes/integrations.py``)

Reads the GHL integration row, decrypts the credentials blob, paginates
``GET /contacts/`` against the location, and upserts each contact into
``leads`` via :func:`app.services.ghl_upsert.upsert_ghl_lead_sync`. Same
dedup keys as the webhook (`(source='ghl', external_id)` then email
fallback) so re-handling a webhook-pushed contact is a no-op.

Per-run metadata lands in ``sync_log`` (operation=``ghl_contacts_sync``).
The integration row's ``last_synced_at`` / ``last_sync_status`` /
``last_sync_error`` columns are stamped so the integrations page
surfaces the last run.
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from app.models.audit import SyncLog
from app.models.integration import Integration
from app.services import secrets as app_secrets
from app.services import ghl_client
from app.services.ghl_upsert import upsert_ghl_lead_sync
from app.tasks.celery_app import celery_app
from app.tasks.db import make_sync_session

logger = logging.getLogger(__name__)


_MAX_ERRORS_RECORDED = 50  # cap the per-run error list to keep details JSONB small


def _load_credentials(integration: Integration) -> tuple[str, str] | None:
    """Decrypt + extract (api_access_token, location_id) from the blob.

    Returns None when credentials are missing — caller stamps the
    integration as misconfigured rather than crashing.
    """
    if not integration.credentials_encrypted:
        return None
    try:
        blob = json.loads(app_secrets.decrypt(integration.credentials_encrypted))
    except (ValueError, json.JSONDecodeError) as exc:
        logger.warning("ghl_sync: credential decrypt failed — %s", exc)
        return None
    access_token = blob.get("api_access_token")
    location_id = blob.get("location_id")
    if not access_token or not location_id:
        return None
    return str(access_token), str(location_id)


@celery_app.task(bind=True, name="app.tasks.ghl_sync.sync_ghl_contacts")
def sync_ghl_contacts(self) -> dict[str, Any]:
    """Pull every contact from GHL and upsert into leads.

    Returns a small summary dict so callers (and Celery's result backend)
    can log "inserted X, updated Y, errors Z". Errors per contact are
    counted but never abort the run — one bad contact shouldn't sink
    5000 good ones.
    """
    started_at = datetime.now(timezone.utc)
    inserted = 0
    updated = 0
    errors: list[dict[str, Any]] = []

    with make_sync_session() as session:
        integration = session.execute(
            select(Integration).where(
                Integration.provider == "ghl",
                Integration.status == "connected",
            )
        ).scalar_one_or_none()

        if integration is None:
            logger.warning("ghl_sync: no connected GHL integration row")
            return {"status": "skipped", "reason": "no_connected_integration"}

        creds = _load_credentials(integration)
        if creds is None:
            logger.warning("ghl_sync: GHL integration missing api_access_token/location_id")
            integration.last_synced_at = started_at
            integration.last_sync_status = "error"
            integration.last_sync_error = (
                "Missing api_access_token or location_id in credentials"
            )
            session.add(integration)
            session.commit()
            return {"status": "skipped", "reason": "missing_credentials"}

        access_token, location_id = creds

        try:
            for contact in ghl_client.fetch_contacts(access_token, location_id):
                try:
                    _, was_inserted = upsert_ghl_lead_sync(session, contact)
                    if was_inserted:
                        inserted += 1
                    else:
                        updated += 1
                except Exception as exc:  # noqa: BLE001 — per-contact resilience
                    if len(errors) < _MAX_ERRORS_RECORDED:
                        errors.append({
                            "contact_id": contact.get("id") or contact.get("contact_id"),
                            "error": str(exc)[:200],
                        })
                    logger.exception(
                        "ghl_sync: contact upsert failed (count=%d)", len(errors),
                    )
        except Exception as exc:  # noqa: BLE001
            # Pagination or API-level failure — partial run.
            logger.exception("ghl_sync: fetch_contacts aborted — %s", exc)
            integration.last_sync_status = "error"
            integration.last_sync_error = str(exc)[:500]
            session.add(integration)
            session.add(SyncLog(
                id=uuid.uuid4(),
                operation="ghl_contacts_sync",
                table_name="leads",
                record_count=inserted + updated,
                status="error",
                details={
                    "inserted": inserted,
                    "updated": updated,
                    "errors": errors,
                    "fatal": str(exc)[:500],
                },
            ))
            session.commit()
            return {
                "status": "error",
                "inserted": inserted,
                "updated": updated,
                "errors": len(errors),
            }

        # Happy path — successful drain.
        run_status = "partial" if errors else "ok"
        integration.last_synced_at = datetime.now(timezone.utc)
        integration.last_sync_status = "ok" if not errors else "error"
        integration.last_sync_error = (
            f"{len(errors)} per-contact errors; see sync_log" if errors else None
        )
        session.add(integration)
        session.add(SyncLog(
            id=uuid.uuid4(),
            operation="ghl_contacts_sync",
            table_name="leads",
            record_count=inserted + updated,
            status=run_status,
            details={
                "inserted": inserted,
                "updated": updated,
                "errors": errors,
            },
        ))
        session.commit()

    logger.info(
        "ghl_sync: done — inserted=%d updated=%d errors=%d status=%s",
        inserted, updated, len(errors), run_status,
    )
    return {
        "status": run_status,
        "inserted": inserted,
        "updated": updated,
        "errors": len(errors),
    }
