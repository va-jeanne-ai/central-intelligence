"""Shared list-filter builders.

Single source of truth for the WHERE semantics of the filterable list
endpoints (appointments, leads, team directory, calls). Both the list
routes and the analyze-view aggregators (app.analytics.view_analysis)
build their filters here, so "analyze this view" aggregates exactly the
dataset the list shows — by construction, not by parallel maintenance.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException

# FROM clause the appointments WHERE parts are written against (aliases a/l/r).
APPOINTMENTS_FROM_SQL = (
    "FROM appointments a "
    "LEFT JOIN leads l ON l.id = a.lead_id "
    "LEFT JOIN sales_reps r ON r.rep_id = a.rep_id"
)


def parse_date_boundary(value: str | None, *, end_of_day: bool) -> datetime | None:
    """Parse a `start`/`end` query param into a timezone-aware datetime.

    Accepts either a bare date (native ``<input type="date">`` sends
    'YYYY-MM-DD') or a full ISO datetime. asyncpg requires an actual
    date/datetime object for a timestamptz comparison — a raw string errors
    with 'expected a datetime.date or datetime.datetime instance' — so this
    must run before the value reaches the query params. A bare date's `end`
    boundary is pushed to 23:59:59 so the whole day is included.
    """
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid date: {value!r}") from exc
    if end_of_day and len(str(value)) <= 10:  # bare 'YYYY-MM-DD', no time component
        dt = dt.replace(hour=23, minute=59, second=59, microsecond=999999)
    return dt


def build_appointment_where(
    *,
    status: str | None = None,
    search: str | None = None,
    window: str = "all",
    from_date: str | None = None,
    to_date: str | None = None,
    start: str | None = None,
    end: str | None = None,
    rep: str | None = None,
) -> tuple[str, dict]:
    """(where_sql, params) for the appointments list — see APPOINTMENTS_FROM_SQL."""
    where_parts: list[str] = ["a.deleted_at IS NULL"]
    params: dict[str, object] = {}

    if status:
        where_parts.append("LOWER(a.status) = :status_filter")
        params["status_filter"] = status.lower()
    if search:
        where_parts.append(
            "(LOWER(COALESCE(a.contact_name, l.name)) LIKE :search "
            "OR LOWER(a.contact_email) LIKE :search)"
        )
        params["search"] = f"%{search.lower()}%"
    if window == "upcoming":
        where_parts.append("a.scheduled_at >= NOW() AND LOWER(a.status) <> 'cancelled'")
    elif window == "this_week":
        where_parts.append(
            "a.scheduled_at >= NOW() AND a.scheduled_at < NOW() + INTERVAL '7 days' "
            "AND LOWER(a.status) <> 'cancelled'"
        )
    if from_date:
        where_parts.append("a.scheduled_at >= :from_date")
        params["from_date"] = from_date
    if to_date:
        where_parts.append("a.scheduled_at <= :to_date")
        params["to_date"] = to_date
    start_dt = parse_date_boundary(start, end_of_day=False)
    end_dt = parse_date_boundary(end, end_of_day=True)
    if start_dt:
        where_parts.append("a.scheduled_at >= :start_date")
        params["start_date"] = start_dt
    if end_dt:
        where_parts.append("a.scheduled_at <= :end_date")
        params["end_date"] = end_dt
    if rep:
        where_parts.append("a.rep_id = :rep_id")
        params["rep_id"] = rep

    return " AND ".join(where_parts), params
