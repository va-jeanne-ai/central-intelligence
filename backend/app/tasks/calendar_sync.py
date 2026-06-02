"""Google Calendar sync — per-user OAuth fan-out.

Mirrors the shape of ``tasks/drive_sync.py``. For each connected user,
list every calendar they can see, then walk events in each calendar's
window. First run uses the full history window (since this user has
nothing in `google_calendar_events` yet) + 365 days forward. Subsequent
runs use ``updatedMin = user_row.last_synced_at`` for incremental
fetches.

Two Celery entry points:

  sync_calendar_events()
      Nightly beat (03:15 UTC) + on-demand from the integrations page.

  sync_calendar_events_for_user(user_id)
      Single-user variant — used by the lead detail page "Sync events
      now" button and the dedicated /calendar page.

Failure model matches Drive: per-user errors recorded in
``SyncLog.details["errors_by_user"]`` (capped at 50) but never abort
the whole run. Per-event errors are recorded inside the per-user list.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select

from app.models.audit import SyncLog
from app.models.integration import Integration
from app.models.operational import UserIntegrationCredential
from app.services import calendar_client
from app.services.calendar_upsert import upsert_calendar_event_sync
from app.services.google_oauth_credentials import load_user_oauth_credentials
from app.tasks.celery_app import celery_app
from app.tasks.db import make_sync_session

logger = logging.getLogger(__name__)


_MAX_ERRORS_RECORDED = 50

# Default history window for first-time syncs. The plan locked "all
# historical + 1 year forward" — we approximate "all historical" with
# 10 years back, which covers any realistic Greg-style account without
# making Google's API choke on epoch dates.
_HISTORY_BACKFILL_DAYS = 365 * 10
_FORWARD_WINDOW_DAYS = 365


def _iso(dt: datetime) -> str:
    """RFC 3339 with explicit Z suffix — Google's preferred format."""
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sweep_one_user(
    session, user_row: UserIntegrationCredential,
) -> tuple[int, int, list[dict[str, Any]]]:
    """Run the Calendar sweep for one connected user.

    Returns ``(inserted, content_changed, errors)``. Errors capped at
    ``_MAX_ERRORS_RECORDED``.
    """
    user_errors: list[dict[str, Any]] = []
    inserted_count = 0
    content_changed_count = 0

    user_id = user_row.user_id

    creds = load_user_oauth_credentials(session, user_id)
    if creds is None:
        user_errors.append({"error": "credentials_unavailable_or_revoked"})
        user_row.last_sync_status = "error"
        user_row.last_sync_error = "Token unavailable — reconnect needed"
        session.add(user_row)
        return 0, 0, user_errors

    # Window selection: first-ever sync → full historical + 1y forward.
    # Subsequent runs → updatedMin = last_synced_at so we only pull
    # events that changed since last time. Future events that exist
    # but didn't change are skipped (we already have them).
    now = datetime.now(timezone.utc)
    is_first_run = user_row.last_synced_at is None
    if is_first_run:
        time_min = _iso(now - timedelta(days=_HISTORY_BACKFILL_DAYS))
        time_max = _iso(now + timedelta(days=_FORWARD_WINDOW_DAYS))
        updated_min: str | None = None
    else:
        time_min = _iso(user_row.last_synced_at - timedelta(days=1))
        time_max = _iso(now + timedelta(days=_FORWARD_WINDOW_DAYS))
        updated_min = _iso(user_row.last_synced_at)

    # calendarList may itself fail (revoked token, scope drift). One
    # outer try so a list failure doesn't mask the per-event paths.
    try:
        calendars = list(calendar_client.fetch_all_calendars(creds))
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        user_errors.append({"error": f"calendar_list_failed: {str(exc)[:300]}"})
        logger.exception("calendar_sync: calendarList failed user=%s", user_id)
        calendars = []

    for cal in calendars:
        cal_id = cal["calendar_id"]
        cal_name = cal.get("name")
        try:
            for event_dict in calendar_client.fetch_events_for_calendar(
                creds, cal_id,
                time_min=time_min,
                time_max=time_max,
                updated_min=updated_min,
            ):
                try:
                    inserted, content_changed = upsert_calendar_event_sync(
                        session, user_id, event_dict, cal_name,
                    )
                    session.commit()
                    if inserted:
                        inserted_count += 1
                    if content_changed:
                        content_changed_count += 1
                except Exception as exc:  # noqa: BLE001
                    session.rollback()
                    if len(user_errors) < _MAX_ERRORS_RECORDED:
                        user_errors.append({
                            "calendar_id": cal_id,
                            "provider_event_id": event_dict.get("provider_event_id"),
                            "error": str(exc)[:300],
                        })
                    logger.exception(
                        "calendar_sync: upsert failed user=%s cal=%s event=%s",
                        user_id, cal_id, event_dict.get("provider_event_id"),
                    )
        except Exception as exc:  # noqa: BLE001
            session.rollback()
            if len(user_errors) < _MAX_ERRORS_RECORDED:
                user_errors.append({
                    "calendar_id": cal_id,
                    "error": f"events_list_failed: {str(exc)[:300]}",
                })
            logger.exception(
                "calendar_sync: events_list failed user=%s cal=%s",
                user_id, cal_id,
            )

    refreshed = session.get(UserIntegrationCredential, user_row.id)
    if refreshed is not None:
        refreshed.last_synced_at = datetime.now(timezone.utc)
        refreshed.last_sync_status = "error" if user_errors else "ok"
        refreshed.last_sync_error = (
            f"{len(user_errors)} error(s); see sync_log" if user_errors else None
        )
        session.add(refreshed)
        session.commit()

    logger.info(
        "calendar_sync: user %s done — calendars=%d inserted=%d changed=%d errors=%d",
        user_id, len(calendars), inserted_count, content_changed_count, len(user_errors),
    )
    return inserted_count, content_changed_count, user_errors


def _run_sync(session, user_ids: list[uuid.UUID] | None) -> dict[str, Any]:
    """Drive the sweep across every connected user (or the given subset)."""
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
            operation="calendar_event_sync",
            table_name="google_calendar_events",
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
            f"{len(errors_by_user)} user(s) with calendar errors; see sync_log"
            if errors_by_user else None
        )
        session.add(integration)

    session.add(SyncLog(
        id=uuid.uuid4(),
        operation="calendar_event_sync",
        table_name="google_calendar_events",
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
        "calendar_sync: done — users=%d inserted=%d changed=%d errored_users=%d",
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


@celery_app.task(bind=True, name="app.tasks.calendar_sync.sync_calendar_events")
def sync_calendar_events(self) -> dict[str, Any]:
    """Full Calendar sweep across every connected user."""
    with make_sync_session() as session:
        return _run_sync(session, user_ids=None)


@celery_app.task(
    bind=True, name="app.tasks.calendar_sync.sync_calendar_events_for_user",
)
def sync_calendar_events_for_user(self, user_id: str) -> dict[str, Any]:
    """Single-user Calendar sweep — for the lead detail + /calendar page buttons."""
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        logger.warning("sync_calendar_events_for_user: bad user_id %r", user_id)
        return {"status": "error", "reason": "bad_user_id"}
    with make_sync_session() as session:
        return _run_sync(session, user_ids=[uid])
