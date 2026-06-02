"""Google Calendar API client — read-only fetch for the calendar sync.

Mirror of ``services/gmail_client.py`` and ``services/drive_client.py``.
Two public functions:

  * :func:`fetch_all_calendars` — paginates ``calendarList.list`` to
    return every calendar the user can see (primary + secondary + shared).
  * :func:`fetch_events_for_calendar` — paginates ``events.list`` with
    ``singleEvents=true`` so recurring events come back as their
    individual instances. ``time_min`` / ``time_max`` bound the window;
    ``updated_min`` short-circuits incremental runs.

Cancelled events are filtered server-side by Google when
``showDeleted=false``; we keep the default.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Iterator

from google.auth.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)


# Tight field lists — Calendar's quota is per-field on list calls, same
# story as Drive. Keep only what the upsert + downstream surfaces use.
_CALENDAR_LIST_FIELDS = (
    "nextPageToken, items(id, summary, primary, accessRole)"
)
_EVENT_FIELDS = (
    "nextPageToken, items(id, summary, description, location, start, end, "
    "organizer(email, displayName), attendees(email, displayName, responseStatus), "
    "htmlLink, status, recurringEventId, updated)"
)


def _build_service(credentials: Credentials):
    """Construct a Calendar v3 service from a Credentials object."""
    return build("calendar", "v3", credentials=credentials, cache_discovery=False)


# ---------------------------------------------------------------------------
# Calendar list
# ---------------------------------------------------------------------------


def fetch_all_calendars(
    credentials: Credentials,
) -> Iterator[dict[str, Any]]:
    """Yield every calendar the connected user can see.

    Each dict: ``{"calendar_id": str, "name": str, "is_primary": bool,
    "access_role": str}``.

    ``access_role`` is one of ``owner``, ``writer``, ``reader``,
    ``freeBusyReader``. The free-busy variant only exposes start/end
    times, no titles or descriptions — we still sync those calendars
    but each event's title comes back as a placeholder.
    """
    service = _build_service(credentials)

    page_token: str | None = None
    while True:
        try:
            list_resp = service.calendarList().list(
                pageToken=page_token,
                fields=_CALENDAR_LIST_FIELDS,
                showDeleted=False,
                showHidden=False,
            ).execute()
        except HttpError as exc:
            logger.warning("calendar: calendarList.list failed — %s", exc)
            return

        for entry in list_resp.get("items") or []:
            cal_id = entry.get("id")
            if not cal_id:
                continue
            yield {
                "calendar_id": cal_id,
                "name": entry.get("summary") or cal_id,
                "is_primary": bool(entry.get("primary")),
                "access_role": entry.get("accessRole"),
            }

        page_token = list_resp.get("nextPageToken")
        if not page_token:
            break


# ---------------------------------------------------------------------------
# Events list
# ---------------------------------------------------------------------------


def fetch_events_for_calendar(
    credentials: Credentials,
    calendar_id: str,
    *,
    time_min: str | None = None,
    time_max: str | None = None,
    updated_min: str | None = None,
) -> Iterator[dict[str, Any]]:
    """Yield expanded event instances from one calendar.

    Parameters
    ----------
    time_min, time_max : RFC 3339 timestamps (e.g. "2020-01-01T00:00:00Z").
        Bound the window of events to consider. ``time_min`` is required
        when ``singleEvents=true`` is in effect for any meaningful run —
        the caller passes the desired history start.
    updated_min : RFC 3339 timestamp.
        Restrict to events created or modified after this point — used
        for incremental sync. When set, ``orderBy`` cannot be
        ``startTime`` (Google's API restriction), so we omit ordering;
        upsert is idempotent so order doesn't matter.

    Each yielded dict is shaped for direct ``google_calendar_events``
    upsert. Cancelled events are filtered by Google when
    ``showDeleted=false`` is set (default below).
    """
    service = _build_service(credentials)
    page_token: str | None = None
    page_count = 0

    while True:
        request_kwargs: dict[str, Any] = {
            "calendarId": calendar_id,
            "pageToken": page_token,
            "fields": _EVENT_FIELDS,
            "singleEvents": True,
            "showDeleted": False,
            "maxResults": 250,
        }
        if updated_min:
            request_kwargs["updatedMin"] = updated_min
        else:
            request_kwargs["orderBy"] = "startTime"
        if time_min:
            request_kwargs["timeMin"] = time_min
        if time_max:
            request_kwargs["timeMax"] = time_max

        try:
            list_resp = service.events().list(**request_kwargs).execute()
        except HttpError as exc:
            logger.warning(
                "calendar: events.list failed cal=%s — %s", calendar_id, exc,
            )
            return

        page_count += 1
        for item in list_resp.get("items") or []:
            parsed = _parse_event(item, calendar_id=calendar_id)
            if parsed is not None:
                yield parsed

        page_token = list_resp.get("nextPageToken")
        if not page_token:
            break

    logger.info(
        "calendar fetch_events_for_calendar: drained %d page(s) for %s",
        page_count, calendar_id,
    )


def _parse_event(item: dict, *, calendar_id: str) -> dict[str, Any] | None:
    """Translate Google's event payload into the upsert-ready dict.

    Returns ``None`` if the event has no id (defensive — shouldn't
    happen for non-deleted items).
    """
    event_id = item.get("id")
    if not event_id:
        return None

    start_block = item.get("start") or {}
    end_block = item.get("end") or {}
    is_all_day = "date" in start_block and "dateTime" not in start_block

    start_dt = _parse_event_datetime(start_block, is_all_day)
    end_dt = _parse_event_datetime(end_block, is_all_day)

    attendees_raw = item.get("attendees") or []
    attendees: list[dict[str, Any]] = []
    for a in attendees_raw:
        email = (a.get("email") or "").strip().lower()
        if not email:
            continue
        attendees.append({
            "email": email,
            "displayName": a.get("displayName"),
            "responseStatus": a.get("responseStatus"),
        })

    organizer_email = ((item.get("organizer") or {}).get("email") or "").strip().lower() or None

    return {
        "provider_event_id": event_id,
        "calendar_id": calendar_id,
        "title": item.get("summary"),
        "description": item.get("description"),
        "location": item.get("location"),
        "organizer_email": organizer_email,
        "attendees": attendees,
        "start_time": start_dt,
        "end_time": end_dt,
        "is_all_day": is_all_day,
        "event_link": item.get("htmlLink"),
        "status": item.get("status"),
        "recurring_event_id": item.get("recurringEventId"),
    }


def _parse_event_datetime(
    block: dict, is_all_day: bool,
) -> datetime | None:
    """Parse either ``date`` (all-day) or ``dateTime`` (timed) form."""
    if not block:
        return None
    if is_all_day:
        raw = block.get("date")
        if not raw:
            return None
        try:
            # "YYYY-MM-DD" with no time/zone — treat midnight UTC for storage.
            return datetime.fromisoformat(raw)
        except (ValueError, TypeError):
            return None
    raw = block.get("dateTime")
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
