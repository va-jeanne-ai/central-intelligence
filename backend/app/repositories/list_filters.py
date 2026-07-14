"""Shared list-filter builders.

Single source of truth for the WHERE semantics of the filterable list
endpoints (appointments, leads, team directory, calls). Both the list
routes and the analyze-view aggregators (app.analytics.view_analysis)
build their filters here, so "analyze this view" aggregates exactly the
dataset the list shows — by construction, not by parallel maintenance.
"""

from __future__ import annotations

from datetime import date, datetime

from fastapi import HTTPException
from sqlalchemy import func, or_, select

from app.analytics.team import RepRow, call_owner_match_values
from app.models.operational import Call, Lead

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


# ── Leads ────────────────────────────────────────────────────────────────────

API_TO_DB_STATUSES: dict[str, list[str]] = {
    # ← moved verbatim from app/routes/leads.py::_API_TO_DB_STATUSES,
    #    including the "applications" composite entry and its comment
    "appointment_set": ["appointment-set"],
    "closed_won": ["sale"],
    "closed_lost": ["lost"],
    "new": ["new"],
    "contacted": ["contacted"],
    "qualified": ["qualified"],
    "stale": ["stale"],
    # Composite filter for the funnel's "Applications" stage — matches the
    # funnel definition in sales_stats.py (qualified + appointment-set). The
    # list endpoint already handles multi-value via an IN clause.
    "applications": ["qualified", "appointment-set"],
}


def parse_plain_date(value: str | None) -> date | None:
    """Parse a YYYY-MM-DD string to a date; return None for empty/invalid input.

    Invalid dates are swallowed (not raised) so a half-typed date-range filter
    degrades to "no filter" rather than 422-ing the whole list request.
    """
    if not value:
        return None
    try:
        return date.fromisoformat(value.strip())
    except (TypeError, ValueError):
        return None


def build_lead_where(
    *,
    status: str | None = None,
    source: str | None = None,
    search: str | None = None,
    entry_from: str | None = None,
    entry_to: str | None = None,
) -> tuple[str, dict]:
    """(where_sql, params) for the leads list — FROM leads, unqualified columns."""
    where_parts: list[str] = ["deleted_at IS NULL"]
    params: dict[str, object] = {}

    if status:
        db_statuses = API_TO_DB_STATUSES.get(status.lower())
        if db_statuses:
            if len(db_statuses) == 1:
                where_parts.append("LOWER(status) = :status_filter")
                params["status_filter"] = db_statuses[0]
            else:
                placeholders = ", ".join(f":status_{i}" for i in range(len(db_statuses)))
                where_parts.append(f"LOWER(status) IN ({placeholders})")
                for i, s in enumerate(db_statuses):
                    params[f"status_{i}"] = s
        else:
            where_parts.append("1 = 0")
    if source:
        where_parts.append("LOWER(source) = :source_filter")
        params["source_filter"] = source.lower()
    if search:
        where_parts.append(
            "(LOWER(name) LIKE :search_pattern OR LOWER(email) LIKE :search_pattern)"
        )
        params["search_pattern"] = f"%{search.lower()}%"
    entry_lo = parse_plain_date(entry_from)
    if entry_lo is not None:
        where_parts.append("entry_date >= :entry_from")
        params["entry_from"] = entry_lo
    entry_hi = parse_plain_date(entry_to)
    if entry_hi is not None:
        where_parts.append("entry_date <= :entry_to")
        params["entry_to"] = entry_hi

    return " AND ".join(where_parts), params


# ── Team directory (the /members page) ──────────────────────────────────────

TEAM_FROM_SQL = "FROM sales_reps sr LEFT JOIN rep_overrides ro ON ro.rep_id = sr.rep_id"

_EFF_NAME = "COALESCE(ro.full_name, sr.full_name)"
_EFF_EMAIL = "COALESCE(ro.email, sr.email)"
_EFF_STATUS = "COALESCE(ro.status, sr.status)"


def build_team_where(
    *, search: str | None = None, status: str | None = None
) -> tuple[str, dict]:
    """(where_sql, params) for the team directory — see TEAM_FROM_SQL."""
    where = ["1 = 1"]
    params: dict[str, object] = {}
    if search:
        where.append(f"({_EFF_NAME} ILIKE :q OR {_EFF_EMAIL} ILIKE :q)")
        params["q"] = f"%{search.strip()}%"
    if status and status != "all":
        where.append(f"LOWER({_EFF_STATUS}) = :status")
        params["status"] = status.lower()
    return " AND ".join(where), params


# ── Calls ────────────────────────────────────────────────────────────────────


def build_call_filters(
    *,
    call_type: str | None = None,
    call_result: str | None = None,
    call_owner: str | None = None,
    source: str | None = None,
    search: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    start: str | None = None,
    end: str | None = None,
    rep: str | None = None,
    roster: list[RepRow],
) -> list:
    """SQLAlchemy filter clauses for the calls list — apply with .where(*clauses)."""
    clauses: list = []
    if call_type:
        types = [t.strip() for t in call_type.split(",") if t.strip()]
        if types:
            clauses.append(Call.call_type.in_(types))
    if call_result:
        results = [r.strip() for r in call_result.split(",") if r.strip()]
        if len(results) == 1:
            clauses.append(Call.call_result == results[0])
        elif results:
            clauses.append(Call.call_result.in_(results))
    if call_owner:
        clauses.append(Call.call_owner == call_owner)
    if source:
        clauses.append(Call.source == source)
    if search:
        like = f"%{search.strip()}%"
        lead_match = select(Lead.id).where(
            or_(Lead.name.ilike(like), Lead.email.ilike(like))
        )
        clauses.append(or_(
            Call.id.ilike(like),
            Call.call_owner.ilike(like),
            Call.lead_id.in_(lead_match),
        ))
    if date_from:
        clauses.append(Call.date >= datetime.fromisoformat(date_from))
    if date_to:
        clauses.append(Call.date <= datetime.fromisoformat(date_to))
    if start:
        clauses.append(Call.date >= datetime.fromisoformat(start))
    if end:
        end_dt = datetime.fromisoformat(end)
        if len(end) <= 10:
            end_dt = end_dt.replace(hour=23, minute=59, second=59, microsecond=999999)
        clauses.append(Call.date <= end_dt)
    if rep:
        rep_row = next((r for r in roster if r.rep_id == rep), None)
        if rep_row is None:
            clauses.append(Call.id.is_(None))
        else:
            match_values = call_owner_match_values(rep_row)
            clauses.append(func.lower(func.trim(Call.call_owner)).in_(match_values))
    return clauses
