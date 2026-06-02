"""Upsert helper for Calendar events → google_calendar_events + embed_pending.

Called once per event dict yielded by ``calendar_client.fetch_events_for_calendar``.
Find-or-create on ``(provider_event_id, connected_via_user_id)``, then on
content change writes an ``embed_pending`` row so the embed worker
picks it up. Sync session only — caller owns the transaction.
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.operational import EmbedPending, GoogleCalendarEvent

logger = logging.getLogger(__name__)


SOURCE_TABLE = "google_calendar_events"


def _format_attendees(attendees: list[dict[str, Any]] | None) -> str:
    """Render the attendee list as a single comma-separated line.

    Used inside the embed payload — the chat agent benefits from seeing
    "Attendees: jane@example.com, bob@partner.com" as plain prose so
    queries like "meetings with bob" hit on the actual email tokens.
    """
    if not attendees:
        return ""
    parts: list[str] = []
    for a in attendees:
        email = (a.get("email") or "").strip()
        name = (a.get("displayName") or "").strip()
        if name and email:
            parts.append(f"{name} <{email}>")
        elif email:
            parts.append(email)
        elif name:
            parts.append(name)
    return ", ".join(parts)


def _format_when(start: datetime | None, end: datetime | None, is_all_day: bool) -> str:
    """Human-readable time string for the embed payload."""
    if start is None:
        return ""
    if is_all_day:
        return f"All-day on {start.date().isoformat()}"
    if end is None:
        return start.isoformat()
    return f"{start.isoformat()} to {end.isoformat()}"


def build_embedding_text(
    *,
    title: str | None,
    calendar_name: str | None,
    description: str | None,
    location: str | None,
    organizer_email: str | None,
    attendees: list[dict[str, Any]] | None,
    start: datetime | None,
    end: datetime | None,
    is_all_day: bool,
) -> str:
    """Prepend metadata headers to a calendar event's body text.

    Same three-form pattern that fixed filename retrieval on Drive:

      * Bracket headers ``[Event: ...]`` / ``[Calendar: ...]`` /
        ``[When: ...]`` carry structured tags.
      * ``Document: <title>`` + ``This document is titled "..."``
        repeat the title as natural prose so vector search has dense
        semantic mass for title-keyword queries.
      * Body restates when + attendees + description so semantic
        queries like "meetings with bob" or "anything Friday afternoon"
        have something to hit on inside the body.

    The header is plain text so the agent can strip it back out when
    surfacing chunks to the LLM.
    """
    title_text = (title or "(untitled event)").strip()
    cal_text = (calendar_name or "").strip()
    when = _format_when(start, end, is_all_day)
    attendees_line = _format_attendees(attendees)

    header_lines: list[str] = [f"[Event: {title_text}]"]
    if cal_text:
        header_lines.append(f"[Calendar: {cal_text}]")
    if when:
        header_lines.append(f"[When: {when}]")
    if location:
        header_lines.append(f"[Location: {location}]")

    title_block = (
        f"Document: {title_text}\n"
        f"This document is titled \"{title_text}\".\n"
    )

    body_lines: list[str] = []
    if when:
        body_lines.append(f"Scheduled: {when}.")
    if organizer_email:
        body_lines.append(f"Organized by: {organizer_email}.")
    if attendees_line:
        body_lines.append(f"Attendees: {attendees_line}.")
    if location:
        body_lines.append(f"Location: {location}.")
    if description and description.strip():
        body_lines.append("")
        body_lines.append(description.strip())

    return (
        "\n".join(header_lines)
        + "\n\n"
        + title_block
        + "\n"
        + "\n".join(body_lines)
    )


def _compute_content_hash(text: str | None, fallback: str | None = None) -> str:
    """sha256(text or fallback)[:64]."""
    src = text if (text and text.strip()) else (fallback or "")
    return hashlib.sha256(src.encode("utf-8", errors="replace")).hexdigest()[:64]


def upsert_calendar_event_sync(
    session: Session,
    user_id: uuid.UUID,
    event_dict: dict[str, Any],
    calendar_name: str | None,
) -> tuple[bool, bool]:
    """Upsert one calendar event. Returns ``(inserted, content_changed)``.

    ``content_changed`` is True when the row is new or when its
    ``content_hash`` differs from the stored value. The caller uses
    this to decide whether to enqueue an ``embed_pending`` row.
    """
    provider_event_id = event_dict.get("provider_event_id")
    if not provider_event_id:
        logger.warning("calendar_upsert: missing provider_event_id; skipping")
        return False, False

    title = event_dict.get("title")
    description = event_dict.get("description")
    location = event_dict.get("location")
    organizer_email = event_dict.get("organizer_email")
    attendees = event_dict.get("attendees") or []
    start = event_dict.get("start_time")
    end = event_dict.get("end_time")
    is_all_day = bool(event_dict.get("is_all_day"))

    extracted_text = build_embedding_text(
        title=title,
        calendar_name=calendar_name,
        description=description,
        location=location,
        organizer_email=organizer_email,
        attendees=attendees,
        start=start,
        end=end,
        is_all_day=is_all_day,
    )
    # Strip NUL just in case (Google's API doesn't emit them, but we
    # have the rule from the Drive ingest and it costs nothing).
    if extracted_text and "\x00" in extracted_text:
        extracted_text = extracted_text.replace("\x00", "")

    new_hash = _compute_content_hash(extracted_text, fallback=title)

    row = session.execute(
        select(GoogleCalendarEvent).where(
            GoogleCalendarEvent.provider_event_id == provider_event_id,
            GoogleCalendarEvent.connected_via_user_id == user_id,
        )
    ).scalar_one_or_none()

    now = datetime.now(timezone.utc)
    inserted = False
    content_changed = False

    if row is None:
        row = GoogleCalendarEvent(
            id=uuid.uuid4(),
            connected_via_user_id=user_id,
            provider_event_id=provider_event_id,
            calendar_id=event_dict.get("calendar_id"),
            calendar_name=calendar_name,
            title=title,
            description=description,
            location=location,
            organizer_email=organizer_email,
            attendees=attendees,
            start_time=start,
            end_time=end,
            is_all_day=is_all_day,
            event_link=event_dict.get("event_link"),
            status=event_dict.get("status"),
            recurring_event_id=event_dict.get("recurring_event_id"),
            extracted_text=extracted_text,
            content_hash=new_hash,
            last_extracted_at=now,
        )
        session.add(row)
        session.flush()
        inserted = True
        content_changed = True
    else:
        # Refresh metadata that can drift between syncs (response status
        # changes, descriptions edited, time bumped). Don't lose old
        # data if the new fetch returns None.
        row.calendar_name = calendar_name or row.calendar_name
        row.title = title if title is not None else row.title
        row.description = description if description is not None else row.description
        row.location = location if location is not None else row.location
        row.organizer_email = organizer_email or row.organizer_email
        if attendees is not None:
            row.attendees = attendees
        if start is not None:
            row.start_time = start
        if end is not None:
            row.end_time = end
        row.is_all_day = is_all_day
        row.event_link = event_dict.get("event_link") or row.event_link
        row.status = event_dict.get("status") or row.status
        row.recurring_event_id = (
            event_dict.get("recurring_event_id") or row.recurring_event_id
        )

        if new_hash != (row.content_hash or ""):
            row.extracted_text = extracted_text
            row.content_hash = new_hash
            row.last_extracted_at = now
            content_changed = True

    # Embed only when there's content worth embedding.
    if content_changed and extracted_text and extracted_text.strip():
        session.add(EmbedPending(
            id=uuid.uuid4(),
            source_table=SOURCE_TABLE,
            source_id=str(row.id),
            text_to_embed=extracted_text,
            content_hash=new_hash,
        ))

    return inserted, content_changed
