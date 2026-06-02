"""Pydantic shapes for the calendar surfaces.

Used by:
  * ``GET /api/v1/calendar/events`` — the dedicated /calendar page.
  * ``GET /api/v1/leads/{lead_id}/events`` — the lead-detail card.

One shape for both — the lead variant just pre-filters by attendee
email server-side.
"""

from typing import Optional

from pydantic import BaseModel, Field


class CalendarAttendee(BaseModel):
    """One attendee on a calendar event."""

    email: str
    displayName: Optional[str] = None
    responseStatus: Optional[str] = None


class CalendarEventRow(BaseModel):
    """One calendar event row for the UI.

    Times are ISO 8601 strings rather than datetimes so the frontend
    can render them with its existing relativeTime/formatDate helpers
    without needing a Date parser injection.
    """

    id: str
    title: Optional[str] = None
    description: Optional[str] = None
    calendar_name: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    is_all_day: bool = False
    organizer_email: Optional[str] = None
    attendees: list[CalendarAttendee] = Field(default_factory=list)
    event_link: Optional[str] = None
    location: Optional[str] = None
    status: Optional[str] = None


class CalendarEventsResponse(BaseModel):
    """Payload for the events list endpoints."""

    events: list[CalendarEventRow] = Field(default_factory=list)
    total: int = 0


class CalendarSummary(BaseModel):
    """One distinct calendar a user has events from.

    Used by the source-filter dropdown on the ``/calendar`` page.
    """

    calendar_id: str
    calendar_name: Optional[str] = None


class CalendarListResponse(BaseModel):
    """Payload for ``GET /api/v1/calendar/calendars``."""

    calendars: list[CalendarSummary] = Field(default_factory=list)
