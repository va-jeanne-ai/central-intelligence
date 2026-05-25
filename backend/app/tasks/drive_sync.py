"""Drive file sync — per-user OAuth fan-out.

Mirrors the shape of ``tasks/gmail_sync.py``: iterate every connected
user, build a Credentials object, sweep their Drive, upsert each file
into ``google_drive_files``, and (on content change) enqueue an
``embed_pending`` row for the embed worker to pick up.

Two Celery entry points:

  sync_drive_files()
      Nightly beat (03:00 UTC) + on-demand from the integrations page.
      Sweeps every connected user.

  sync_drive_files_for_user(user_id)
      Single-user variant — used by the lead detail page's
      "Sync documents now" button.

Failure model matches the Gmail sync: per-user errors are recorded
into ``SyncLog.details["errors_by_user"]`` (capped at 50) but never
abort the whole run.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from app.models.audit import SyncLog
from app.models.integration import Integration
from app.models.operational import UserIntegrationCredential
from app.services import drive_client
from app.services.drive_upsert import upsert_drive_file_sync
from app.services.google_oauth_credentials import load_user_oauth_credentials
from app.tasks.celery_app import celery_app
from app.tasks.db import make_sync_session

logger = logging.getLogger(__name__)


_MAX_ERRORS_RECORDED = 50


def _sweep_one_user(
    session, user_row: UserIntegrationCredential,
) -> tuple[int, int, list[dict[str, Any]]]:
    """Run the Drive sweep for one connected user.

    Returns ``(inserted, content_changed, errors)``. Errors are
    dicts capped at ``_MAX_ERRORS_RECORDED`` entries.
    """
    user_errors: list[dict[str, Any]] = []
    inserted_count = 0
    content_changed_count = 0

    # Cache the user_id locally — touching `user_row.user_id` after a
    # rollback triggers a lazy-load which raises PendingRollbackError
    # and masks the original failure.
    user_id = user_row.user_id

    creds = load_user_oauth_credentials(session, user_id)
    if creds is None:
        user_errors.append({"error": "credentials_unavailable_or_revoked"})
        user_row.last_sync_status = "error"
        user_row.last_sync_error = "Token unavailable — reconnect needed"
        session.add(user_row)
        return 0, 0, user_errors

    since_iso = (
        user_row.last_synced_at.isoformat()
        if user_row.last_synced_at is not None
        else None
    )

    # Folder-name cache so we don't issue files.get per row when many
    # files share the same parent.
    folder_cache: dict[str, str | None] = {}

    try:
        for file_dict in drive_client.fetch_all_files(creds, since_iso=since_iso):
            try:
                # Resolve parent folder name lazily.
                parent_id = file_dict.get("parent_folder_id")
                if parent_id and parent_id not in folder_cache:
                    folder_cache[parent_id] = drive_client.fetch_parent_folder_name(
                        creds, parent_id,
                    )
                parent_name = folder_cache.get(parent_id) if parent_id else None

                # Pull content for supported mime types only.
                extracted_text = drive_client.fetch_file_content(
                    creds,
                    file_dict["provider_file_id"],
                    file_dict.get("mime_type") or "",
                    size_bytes=file_dict.get("size_bytes"),
                )

                inserted, content_changed = upsert_drive_file_sync(
                    session,
                    user_id,
                    file_dict,
                    extracted_text,
                    parent_folder_name=parent_name,
                )
                # Commit per file so a downstream flush failure on the
                # next file can't poison this one's row.
                session.commit()
                if inserted:
                    inserted_count += 1
                if content_changed:
                    content_changed_count += 1
            except Exception as exc:  # noqa: BLE001
                # Rollback so the session is usable for the next file.
                session.rollback()
                if len(user_errors) < _MAX_ERRORS_RECORDED:
                    user_errors.append({
                        "provider_file_id": file_dict.get("provider_file_id"),
                        "name": file_dict.get("name"),
                        "error": str(exc)[:300],
                    })
                logger.exception(
                    "drive_sync: upsert failed user=%s file=%s",
                    user_id, file_dict.get("provider_file_id"),
                )
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        if len(user_errors) < _MAX_ERRORS_RECORDED:
            user_errors.append({"error": f"list_failed: {str(exc)[:300]}"})
        logger.exception("drive_sync: fetch_all_files failed user=%s", user_id)

    # Re-fetch the user_row in the (now-clean) session to stamp the
    # last_synced_at / status fields. The original object may be
    # detached after rollbacks.
    refreshed = session.get(UserIntegrationCredential, user_row.id)
    if refreshed is not None:
        refreshed.last_synced_at = datetime.now(timezone.utc)
        refreshed.last_sync_status = "error" if user_errors else "ok"
        refreshed.last_sync_error = (
            f"{len(user_errors)} error(s); see sync_log" if user_errors else None
        )
        session.add(refreshed)

    logger.info(
        "drive_sync: user %s done — inserted=%d changed=%d errors=%d",
        user_row.user_id, inserted_count, content_changed_count, len(user_errors),
    )

    return inserted_count, content_changed_count, user_errors


def _run_sync(session, user_ids: list[uuid.UUID] | None) -> dict[str, Any]:
    """Drive the sweep across the given user set (or all connected users)."""
    started_at = datetime.now(timezone.utc)

    integration = session.execute(
        select(Integration).where(
            Integration.provider == "google_workspace",
            Integration.status == "connected",
        )
    ).scalar_one_or_none()

    q = select(UserIntegrationCredential).where(
        UserIntegrationCredential.provider == "google_workspace",
    )
    if user_ids:
        q = q.where(UserIntegrationCredential.user_id.in_(user_ids))
    user_rows = session.execute(q).scalars().all()

    if not user_rows:
        session.add(SyncLog(
            id=uuid.uuid4(),
            operation="drive_file_sync",
            table_name="google_drive_files",
            record_count=0,
            status="ok",
            details={"users_processed": 0, "reason": "no_connected_users"},
        ))
        session.commit()
        return {"status": "ok", "users_processed": 0, "inserted": 0, "changed": 0}

    total_inserted = 0
    total_changed = 0
    errors_by_user: dict[str, list[dict[str, Any]]] = {}

    for user_row in user_rows:
        inserted, changed, errs = _sweep_one_user(session, user_row)
        total_inserted += inserted
        total_changed += changed
        if errs:
            errors_by_user[str(user_row.user_id)] = errs

    if integration is not None:
        integration.last_synced_at = datetime.now(timezone.utc)
        integration.last_sync_status = "error" if errors_by_user else "ok"
        integration.last_sync_error = (
            f"{len(errors_by_user)} user(s) with drive errors; see sync_log"
            if errors_by_user else None
        )
        session.add(integration)

    session.add(SyncLog(
        id=uuid.uuid4(),
        operation="drive_file_sync",
        table_name="google_drive_files",
        record_count=total_inserted,
        status="partial" if errors_by_user else "ok",
        details={
            "users_processed": len(user_rows),
            "inserted": total_inserted,
            "content_changed": total_changed,
            "errors_by_user": errors_by_user,
            "scoped_to_user_ids": [str(x) for x in user_ids] if user_ids else None,
        },
    ))
    session.commit()

    logger.info(
        "drive_sync: done — users=%d inserted=%d changed=%d errored_users=%d",
        len(user_rows), total_inserted, total_changed, len(errors_by_user),
    )
    return {
        "status": "partial" if errors_by_user else "ok",
        "users_processed": len(user_rows),
        "inserted": total_inserted,
        "changed": total_changed,
        "errored_users": len(errors_by_user),
    }


# ---------------------------------------------------------------------------
# Celery entry points
# ---------------------------------------------------------------------------


@celery_app.task(bind=True, name="app.tasks.drive_sync.sync_drive_files")
def sync_drive_files(self) -> dict[str, Any]:
    """Full Drive sweep across every connected user."""
    with make_sync_session() as session:
        return _run_sync(session, user_ids=None)


@celery_app.task(
    bind=True, name="app.tasks.drive_sync.sync_drive_files_for_user",
)
def sync_drive_files_for_user(self, user_id: str) -> dict[str, Any]:
    """Single-user Drive sweep — for the lead detail "Sync documents" button."""
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        logger.warning("sync_drive_files_for_user: bad user_id %r", user_id)
        return {"status": "error", "reason": "bad_user_id"}
    with make_sync_session() as session:
        return _run_sync(session, user_ids=[uid])
