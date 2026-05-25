"""Gmail thread sync — per-user OAuth fan-out.

Each staff member connects their own Google account via the OAuth
flow in ``routes/oauth.py``. Their refresh token lives in
``user_integration_credentials``. This task iterates every connected
user; for each, it builds a Credentials object and runs the lead
sweep against their mailbox.

Threads + messages dedup on ``provider_message_id`` (globally unique
in the email_messages table), so a single message that appears in
both User A's and User B's mailboxes is only inserted once.

Two Celery entry points:

  sync_gmail_threads()
      Nightly beat (02:45 UTC) + on-demand from
      ``POST /integrations/google_workspace/sync``. Sweeps every lead
      with an email against every connected user.

  sync_gmail_threads_for_lead(lead_id)
      Per-lead variant from the lead detail page's "Sync emails now"
      button. Same fan-out, scoped to one lead.

Failure model: per-user errors are captured + capped at 50 inside
``SyncLog.details["errors_by_user"]`` (object keyed by user_id) but
never abort the whole run. A user whose token is revoked won't crash
the rest of the sweep.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, text

from app.models.audit import SyncLog
from app.models.integration import Integration
from app.models.operational import UserIntegrationCredential
from app.services import gmail_client
from app.services.gmail_upsert import upsert_thread_and_message_sync
from app.services.google_oauth_credentials import load_user_oauth_credentials
from app.tasks.celery_app import celery_app
from app.tasks.db import make_sync_session

logger = logging.getLogger(__name__)


_MAX_ERRORS_RECORDED = 50


# ---------------------------------------------------------------------------
# Shared body — used by both Celery entry points
# ---------------------------------------------------------------------------


def _run_sync(session, lead_ids: list[uuid.UUID] | None) -> dict[str, Any]:
    """Drive the sync across every connected user.

    ``lead_ids=None`` → every lead with a non-null email. Otherwise
    scoped to the given lead set (used by the per-lead on-demand
    variant).
    """
    started_at = datetime.now(timezone.utc)

    # Deployment-wide integration row — keeps the existing "is this
    # provider connected at all" status surface for the integrations
    # list page. Per-user credentials live in user_integration_credentials.
    integration = session.execute(
        select(Integration).where(
            Integration.provider == "google_workspace",
            Integration.status == "connected",
        )
    ).scalar_one_or_none()
    if integration is None:
        # Auto-create the deployment-wide marker on the first sync run
        # after at least one user has connected — saves the user from
        # having to manually save an integration row first.
        any_user = session.execute(
            select(UserIntegrationCredential.id).where(
                UserIntegrationCredential.provider == "google_workspace",
            ).limit(1)
        ).scalar_one_or_none()
        if any_user is None:
            return {"status": "skipped", "reason": "no_connected_users"}
        integration = Integration(
            id=uuid.uuid4(),
            provider="google_workspace",
            status="connected",
            credentials_encrypted=None,  # per-user, not deployment-wide
            config=None,
        )
        session.add(integration)
        session.flush()

    user_rows = session.execute(
        select(UserIntegrationCredential).where(
            UserIntegrationCredential.provider == "google_workspace",
        )
    ).scalars().all()

    if not user_rows:
        integration.last_synced_at = started_at
        integration.last_sync_status = "ok"
        integration.last_sync_error = None
        session.add(integration)
        session.add(SyncLog(
            id=uuid.uuid4(),
            operation="gmail_thread_sync",
            table_name="email_messages",
            record_count=0,
            status="ok",
            details={"users_processed": 0, "reason": "no_connected_users"},
        ))
        session.commit()
        return {"status": "ok", "users_processed": 0, "inserted": 0, "errors": 0}

    # Resolve the lead set once — same list reused for every user.
    if lead_ids is None:
        lead_rows = session.execute(text("""
            SELECT id, email FROM leads
            WHERE email IS NOT NULL AND deleted_at IS NULL
        """)).mappings().all()
    elif not lead_ids:
        return {"status": "ok", "users_processed": 0, "inserted": 0, "errors": 0}
    else:
        # Cast :ids to uuid[] explicitly — psycopg2 (Celery worker
        # driver) doesn't auto-coerce a text array into uuid the way
        # asyncpg does. Without the cast PG raises
        # "operator does not exist: uuid = text".
        lead_rows = session.execute(
            text("""
                SELECT id, email FROM leads
                WHERE id = ANY(CAST(:ids AS uuid[])) AND email IS NOT NULL AND deleted_at IS NULL
            """),
            {"ids": [str(x) for x in lead_ids]},
        ).mappings().all()

    total_inserted = 0
    users_processed = 0
    errors_by_user: dict[str, list[dict[str, Any]]] = {}

    for user_row in user_rows:
        user_id = user_row.user_id
        user_key = str(user_id)
        users_processed += 1
        user_inserted = 0
        user_errors: list[dict[str, Any]] = []
        per_user_since = (
            user_row.last_synced_at.isoformat()
            if user_row.last_synced_at is not None
            else None
        )

        creds = load_user_oauth_credentials(session, user_id)
        if creds is None:
            user_errors.append({"error": "credentials_unavailable_or_revoked"})
            errors_by_user[user_key] = user_errors[:_MAX_ERRORS_RECORDED]
            user_row.last_sync_status = "error"
            user_row.last_sync_error = "Token unavailable — reconnect needed"
            session.add(user_row)
            continue

        for lead in lead_rows:
            lead_id = lead["id"]
            email = lead["email"]
            try:
                for msg in gmail_client.fetch_messages_for_email(
                    creds, email, since_iso=per_user_since,
                ):
                    try:
                        if upsert_thread_and_message_sync(session, lead_id, msg):
                            user_inserted += 1
                            total_inserted += 1
                    except Exception as exc:  # noqa: BLE001
                        if len(user_errors) < _MAX_ERRORS_RECORDED:
                            user_errors.append({
                                "lead_id": str(lead_id),
                                "provider_message_id": msg.get("provider_message_id"),
                                "error": str(exc)[:200],
                            })
                        logger.exception(
                            "gmail_sync: upsert failed user=%s lead=%s msg=%s",
                            user_id, lead_id, msg.get("provider_message_id"),
                        )
            except Exception as exc:  # noqa: BLE001
                if len(user_errors) < _MAX_ERRORS_RECORDED:
                    user_errors.append({
                        "lead_id": str(lead_id),
                        "email": email,
                        "error": str(exc)[:300],
                    })
                logger.exception(
                    "gmail_sync: fetch failed user=%s lead=%s email=%s",
                    user_id, lead_id, email,
                )

        # Stamp the per-user row.
        user_row.last_synced_at = datetime.now(timezone.utc)
        user_row.last_sync_status = "error" if user_errors else "ok"
        user_row.last_sync_error = (
            f"{len(user_errors)} error(s); see sync_log" if user_errors else None
        )
        session.add(user_row)

        if user_errors:
            errors_by_user[user_key] = user_errors

        logger.info(
            "gmail_sync: user %s done — inserted=%d errors=%d",
            user_id, user_inserted, len(user_errors),
        )

    # Deployment-wide stamp.
    finished_at = datetime.now(timezone.utc)
    integration.last_synced_at = finished_at
    integration.last_sync_status = "error" if errors_by_user else "ok"
    integration.last_sync_error = (
        f"{len(errors_by_user)} user(s) with errors; see sync_log"
        if errors_by_user else None
    )
    session.add(integration)
    session.add(SyncLog(
        id=uuid.uuid4(),
        operation="gmail_thread_sync",
        table_name="email_messages",
        record_count=total_inserted,
        status="partial" if errors_by_user else "ok",
        details={
            "users_processed": users_processed,
            "leads_processed": len(lead_rows),
            "inserted": total_inserted,
            "errors_by_user": errors_by_user,
            "scoped_to_lead_ids": [str(x) for x in lead_ids] if lead_ids else None,
        },
    ))
    session.commit()

    logger.info(
        "gmail_sync: done — users=%d leads=%d inserted=%d errored_users=%d",
        users_processed, len(lead_rows), total_inserted, len(errors_by_user),
    )
    return {
        "status": "partial" if errors_by_user else "ok",
        "users_processed": users_processed,
        "leads_processed": len(lead_rows),
        "inserted": total_inserted,
        "errored_users": len(errors_by_user),
    }


# ---------------------------------------------------------------------------
# Celery entry points
# ---------------------------------------------------------------------------


@celery_app.task(bind=True, name="app.tasks.gmail_sync.sync_gmail_threads")
def sync_gmail_threads(self) -> dict[str, Any]:
    """Full-mailbox sweep — every connected user × every lead with email."""
    with make_sync_session() as session:
        return _run_sync(session, lead_ids=None)


@celery_app.task(
    bind=True, name="app.tasks.gmail_sync.sync_gmail_threads_for_lead",
)
def sync_gmail_threads_for_lead(self, lead_id: str) -> dict[str, Any]:
    """Per-lead sweep across every connected user — used by the
    lead detail page's Sync button."""
    try:
        uid = uuid.UUID(lead_id)
    except ValueError:
        logger.warning("sync_gmail_threads_for_lead: bad lead_id %r", lead_id)
        return {"status": "error", "reason": "bad_lead_id"}
    with make_sync_session() as session:
        return _run_sync(session, lead_ids=[uid])
