"""Calendar page endpoints.

  * ``GET  /api/v1/calendar/events`` — list events for the current
    user with optional window + attendee filters.
  * ``POST /api/v1/calendar/sync``   — enqueue a single-user calendar
    sweep (no fan-out; the integrations page is the place for
    cross-user syncs).

The lead-detail Events card has its own route under ``/leads/{id}/events``
that does the JSONB containment lookup; this module is the first-class
calendar surface only.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser, get_current_user
from app.database import get_session
from app.schemas.calendar import (
    CalendarAttendee,
    CalendarEventRow,
    CalendarEventsResponse,
    CalendarListResponse,
    CalendarSummary,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["calendar"])


def _parse_user_uuid(user_id: str) -> uuid.UUID | None:
    """Best-effort current_user.id parse. Returns None for non-UUID
    mock IDs so we can short-circuit empty responses cleanly."""
    try:
        return uuid.UUID(user_id)
    except (TypeError, ValueError):
        return None


def _parse_iso(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        # Tolerate trailing Z
        v = s.replace("Z", "+00:00") if s.endswith("Z") else s
        dt = datetime.fromisoformat(v)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


@router.get("/api/v1/calendar/events", response_model=CalendarEventsResponse)
async def list_calendar_events(
    db: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
    start: Optional[str] = Query(
        default=None,
        description="ISO timestamp lower bound (default: now).",
    ),
    end: Optional[str] = Query(
        default=None,
        description="ISO timestamp upper bound (default: now + 14 days).",
    ),
    attendee_email_contains: Optional[str] = Query(
        default=None,
        description="Case-insensitive substring match on any attendee email.",
    ),
    calendar_name: Optional[str] = Query(
        default=None,
        description="Exact-match filter on the source calendar's display name.",
    ),
    only_lead_events: bool = Query(
        default=False,
        description=(
            "When true, restrict to events with at least one attendee whose "
            "email matches a row in the `leads` table (case-insensitive). "
            "Lets the UI show 'meetings with leads only' across all calendars."
        ),
    ),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> CalendarEventsResponse:
    """List the calling user's events within a time window.

    Default window: now → +14 days, ordered by ``start_time ASC``.
    Supports source filters (single calendar OR lead-events-only) plus
    the attendee-email substring search.
    """
    user_uuid = _parse_user_uuid(current_user.id)
    if user_uuid is None:
        return CalendarEventsResponse(events=[], total=0)

    now = datetime.now(timezone.utc)
    start_dt = _parse_iso(start) or now
    end_dt = _parse_iso(end) or (now + timedelta(days=14))

    if end_dt < start_dt:
        raise HTTPException(
            status_code=400, detail="`end` must be greater than or equal to `start`.",
        )

    # We allow "past" windows too — the frontend's "Show recent" toggle
    # passes start in the past. Ordering keeps newest-first when the
    # window is in the past, oldest-first when it spans the future.
    # Simpler rule: always ASC. Frontend sections + groups by day.
    params: dict = {
        "user_id": str(user_uuid),
        "start": start_dt,
        "end": end_dt,
        "limit": limit,
        "offset": offset,
    }

    attendee_clause = ""
    if attendee_email_contains and attendee_email_contains.strip():
        params["addr"] = f"%{attendee_email_contains.strip().lower()}%"
        attendee_clause = """
            AND EXISTS (
                SELECT 1
                FROM jsonb_array_elements(coalesce(attendees, '[]'::jsonb)) a
                WHERE a->>'email' ILIKE :addr
            )
        """

    # Optional source filter — pin to one calendar by display name.
    calendar_clause = ""
    if calendar_name and calendar_name.strip():
        params["cal_name"] = calendar_name.strip()
        calendar_clause = "AND calendar_name = :cal_name"

    # Optional lead-attendees filter — restrict to events with at least
    # one attendee whose lowercased email matches a lead row. The GIN
    # index on attendees + the leads.email index keep this fast.
    lead_clause = ""
    if only_lead_events:
        lead_clause = """
            AND EXISTS (
                SELECT 1
                FROM jsonb_array_elements(coalesce(attendees, '[]'::jsonb)) a
                JOIN leads l ON lower(l.email) = lower(a->>'email')
                WHERE l.deleted_at IS NULL
            )
        """

    rows = (await db.execute(
        text(f"""
            SELECT
                id::text                          AS id,
                title,
                description,
                calendar_name,
                start_time,
                end_time,
                is_all_day,
                organizer_email,
                attendees,
                event_link,
                location,
                status
            FROM google_calendar_events
            WHERE connected_via_user_id = :user_id
              AND start_time IS NOT NULL
              AND start_time >= :start
              AND start_time <= :end
              {attendee_clause}
              {calendar_clause}
              {lead_clause}
            ORDER BY start_time ASC
            LIMIT :limit OFFSET :offset
        """),
        params,
    )).mappings().all()

    # Single-query total for paging — when window is large this could
    # be expensive but is bounded by the GIN + start_time indices.
    total_row = (await db.execute(
        text(f"""
            SELECT count(*) AS total
            FROM google_calendar_events
            WHERE connected_via_user_id = :user_id
              AND start_time IS NOT NULL
              AND start_time >= :start
              AND start_time <= :end
              {attendee_clause}
              {calendar_clause}
              {lead_clause}
        """),
        params,
    )).mappings().first()
    total = int(total_row["total"] or 0) if total_row else 0

    events = [
        CalendarEventRow(
            id=r["id"],
            title=r["title"],
            description=r["description"],
            calendar_name=r["calendar_name"],
            start_time=r["start_time"].isoformat() if r["start_time"] else None,
            end_time=r["end_time"].isoformat() if r["end_time"] else None,
            is_all_day=bool(r["is_all_day"]),
            organizer_email=r["organizer_email"],
            attendees=[
                CalendarAttendee(
                    email=a.get("email", ""),
                    displayName=a.get("displayName"),
                    responseStatus=a.get("responseStatus"),
                )
                for a in (r["attendees"] or [])
                if a.get("email")
            ],
            event_link=r["event_link"],
            location=r["location"],
            status=r["status"],
        )
        for r in rows
    ]
    return CalendarEventsResponse(events=events, total=total)


@router.post("/api/v1/calendar/sync", status_code=202)
async def trigger_calendar_sync(
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Enqueue a calendar sync for the calling user.

    The dedicated /calendar page invokes this when the user clicks
    "Sync now". Cross-user syncs go through the integrations page.
    """
    user_uuid = _parse_user_uuid(current_user.id)
    if user_uuid is None:
        raise HTTPException(
            status_code=400,
            detail="Calendar sync requires a real signed-in user.",
        )

    try:
        from app.tasks.calendar_sync import sync_calendar_events_for_user
        task = sync_calendar_events_for_user.delay(str(user_uuid))
        return {"task_id": task.id, "user_id": str(user_uuid)}
    except Exception as exc:  # noqa: BLE001
        logger.warning("trigger_calendar_sync: enqueue failed — %s", exc)
        raise HTTPException(
            status_code=503,
            detail="Failed to enqueue calendar sync. Try again in a minute.",
        ) from exc


@router.get("/api/v1/calendar/calendars", response_model=CalendarListResponse)
async def list_user_calendars(
    db: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> CalendarListResponse:
    """Return the distinct calendars the calling user has events from.

    Populates the source-filter dropdown on the `/calendar` page. We
    derive it from the events table (not a separate ``google_calendars``
    table) because the events themselves carry calendar_id + name on
    every row — no second table needed for this small UI affordance.
    """
    user_uuid = _parse_user_uuid(current_user.id)
    if user_uuid is None:
        return CalendarListResponse(calendars=[])

    rows = (await db.execute(
        text("""
            SELECT DISTINCT calendar_id, calendar_name
            FROM google_calendar_events
            WHERE connected_via_user_id = :user_id
              AND calendar_id IS NOT NULL
            ORDER BY calendar_name NULLS LAST
        """),
        {"user_id": str(user_uuid)},
    )).mappings().all()

    return CalendarListResponse(
        calendars=[
            CalendarSummary(
                calendar_id=r["calendar_id"],
                calendar_name=r["calendar_name"],
            )
            for r in rows
        ],
    )
