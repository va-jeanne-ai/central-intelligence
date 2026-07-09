"""
Appointments endpoints — the Sales appointments directory + CRUD.

GET    /api/v1/appointments              — paginated list with filters
GET    /api/v1/appointments/stats        — KPIs, volume, status breakdown
GET    /api/v1/appointments/{id}         — detail (+ linked lead/member name)
GET    /api/v1/appointments/{id}/history — audit-log timeline
POST   /api/v1/appointments              — manual booking
PATCH  /api/v1/appointments/{id}         — partial update
DELETE /api/v1/appointments/{id}         — soft-cancel (status='cancelled')

Mirrors routes/members.py. Stats delegate to compute_appointment_stats.
Inbound GHL appointments arrive via the webhook (routes/webhooks.py), not here.
"""

import logging
import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser, get_current_user
from app.database import get_session
from app.repositories.appointment_stats import compute_appointment_stats
from app.schemas.appointments import (
    AppointmentDetailResponse,
    AppointmentHistoryEvent,
    AppointmentHistoryResponse,
    AppointmentKpiResponse,
    AppointmentListResponse,
    AppointmentRecord,
    AppointmentStatsResponse,
    AppointmentVolumePoint,
    CreateAppointmentRequest,
    StatusBreakdownItem,
    UpdateAppointmentRequest,
)
from app.services.audit import record_event

logger = logging.getLogger(__name__)

router = APIRouter(tags=["appointments"])

_SORTABLE_COLUMNS: frozenset[str] = frozenset(
    {"scheduled_at", "created_at", "status", "contact_name"}
)
_SORT_DIRS: frozenset[str] = frozenset({"asc", "desc"})
_PATCH_FIELDS: frozenset[str] = frozenset(
    {"status", "scheduled_at", "end_at", "appointment_type", "notes"}
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _int(value: object) -> int:
    try:
        return int(value) if value is not None else 0
    except (TypeError, ValueError):
        return 0


def _parse_appointment_uuid(appointment_id: str) -> uuid.UUID:
    try:
        return uuid.UUID(appointment_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Appointment not found") from exc


def _coerce_author_uuid(user_id: str | uuid.UUID | None) -> uuid.UUID | None:
    if user_id is None:
        return None
    if isinstance(user_id, uuid.UUID):
        return user_id
    try:
        return uuid.UUID(str(user_id))
    except ValueError:
        return None


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid datetime: {value!r}") from exc


def _parse_date_boundary(value: str | None, *, end_of_day: bool) -> datetime | None:
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


# ---------------------------------------------------------------------------
# GET /appointments
# ---------------------------------------------------------------------------


@router.get("/appointments", response_model=AppointmentListResponse, summary="Paginated appointment list")
async def list_appointments(
    status: str | None = Query(default=None),
    search: str | None = Query(default=None, description="Search contact name/email"),
    window: Literal["all", "upcoming", "this_week"] = Query(default="all"),
    from_date: str | None = Query(default=None, alias="from"),
    to_date: str | None = Query(default=None, alias="to"),
    start: str | None = Query(default=None, description="scheduled_at >= (ISO date/datetime)"),
    end: str | None = Query(default=None, description="scheduled_at <= (ISO date/datetime)"),
    rep: str | None = Query(default=None, description="Filter by rep_id"),
    page: int = Query(default=1, ge=1),
    # Capped at 1000 (not the historical 200) so calendar month views can
    # request a full month of appointments (~<400 typical) in one page
    # instead of paginating through several requests just to paint a grid.
    per_page: int = Query(default=50, ge=1, le=1000),
    sort_by: str = Query(default="scheduled_at"),
    sort_dir: Literal["asc", "desc"] = Query(default="desc"),
    session: AsyncSession = Depends(get_session),
) -> AppointmentListResponse:
    """Return a paginated, filterable list of appointments."""

    if sort_by not in _SORTABLE_COLUMNS:
        sort_by = "scheduled_at"
    if sort_dir not in _SORT_DIRS:
        sort_dir = "desc"

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
    # start/end — date-range filter (client-facing name for the Appointments +
    # Sales Calls filter bars). Additive with the legacy from/to aliases above.
    # Parsed into real datetimes (not raw strings) — asyncpg rejects a bare
    # string against a timestamptz column.
    start_dt = _parse_date_boundary(start, end_of_day=False)
    end_dt = _parse_date_boundary(end, end_of_day=True)
    if start_dt:
        where_parts.append("a.scheduled_at >= :start_date")
        params["start_date"] = start_dt
    if end_dt:
        where_parts.append("a.scheduled_at <= :end_date")
        params["end_date"] = end_dt
    if rep:
        where_parts.append("a.rep_id = :rep_id")
        params["rep_id"] = rep

    where_sql = " AND ".join(where_parts)
    # contact_name / member_id / lead_id / sort columns are unqualified in
    # _SORTABLE_COLUMNS; the join is left outer so appointments without a
    # linked lead still appear. `a.` prefix keeps the appointments table
    # columns unambiguous against `leads.name`.
    from_sql = "FROM appointments a LEFT JOIN leads l ON l.id = a.lead_id LEFT JOIN sales_reps r ON r.rep_id = a.rep_id"

    total = _int((await session.execute(
        text(f"SELECT COUNT(*) {from_sql} WHERE {where_sql}"),  # noqa: S608
        params,
    )).scalar())

    params["limit"] = per_page
    params["offset"] = (page - 1) * per_page
    sort_col = f"a.{sort_by}" if sort_by != "contact_name" else "COALESCE(a.contact_name, l.name)"
    rows = (await session.execute(
        text(
            f"""
            SELECT a.id::text AS id,
                   COALESCE(a.contact_name, l.name) AS contact_name,
                   a.contact_email,
                   a.lead_id::text AS lead_id, a.member_id::text AS member_id,
                   a.status, a.appointment_type, a.scheduled_at, a.end_at, a.source,
                   a.rep_id, r.full_name AS roster_rep_name, a.appointment_owner
            {from_sql}
            WHERE {where_sql}
            ORDER BY {sort_col} {sort_dir} NULLS LAST
            LIMIT :limit OFFSET :offset
            """  # noqa: S608 — sort_by/sort_dir whitelisted, where_sql parametrised
        ),
        params,
    )).mappings().all()

    appointments = [
        AppointmentRecord(
            id=r["id"],
            contact_name=r["contact_name"],
            contact_email=r["contact_email"],
            lead_id=r["lead_id"],
            member_id=r["member_id"],
            status=r["status"],
            appointment_type=r["appointment_type"],
            scheduledAt=r["scheduled_at"].isoformat() if r["scheduled_at"] else None,
            end_at=r["end_at"].isoformat() if r["end_at"] else None,
            source=r["source"],
            rep_id=r["rep_id"],
            # Roster full_name wins when rep_id resolves; otherwise fall back to
            # the raw WGR appointment_owner display string (covers former reps
            # no longer on the roster, e.g. "Ryan Verey").
            rep_name=r["roster_rep_name"] or r["appointment_owner"],
        )
        for r in rows
    ]
    return AppointmentListResponse(appointments=appointments, total=total, page=page, per_page=per_page)


# ---------------------------------------------------------------------------
# GET /appointments/stats
# ---------------------------------------------------------------------------


@router.get("/appointments/stats", response_model=AppointmentStatsResponse)
async def get_appointments_stats(
    session: AsyncSession = Depends(get_session),
) -> AppointmentStatsResponse:
    data = await compute_appointment_stats(session)
    return AppointmentStatsResponse(
        kpis=AppointmentKpiResponse(**data["kpis"]),
        appointment_volume=[AppointmentVolumePoint(**p) for p in data["appointment_volume"]],
        status_breakdown=[StatusBreakdownItem(**s) for s in data["status_breakdown"]],
    )


# ---------------------------------------------------------------------------
# POST /appointments — manual booking
# ---------------------------------------------------------------------------


@router.post("/appointments", response_model=AppointmentDetailResponse, status_code=201)
async def create_appointment(
    body: CreateAppointmentRequest,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> AppointmentDetailResponse:
    """Manually book an appointment (source='manual')."""
    scheduled_at = _parse_dt(body.scheduled_at)
    end_at = _parse_dt(body.end_at)
    status = (body.status or "booked").strip().lower()

    lead_uuid: uuid.UUID | None = None
    if body.lead_id:
        lead_uuid = _parse_appointment_uuid(body.lead_id)
        exists = (await session.execute(
            text("SELECT 1 FROM leads WHERE id = :id AND deleted_at IS NULL"),
            {"id": str(lead_uuid)},
        )).scalar_one_or_none()
        if exists is None:
            raise HTTPException(status_code=400, detail="lead_id not found")

    member_uuid: uuid.UUID | None = None
    if body.member_id:
        member_uuid = _parse_appointment_uuid(body.member_id)
        exists = (await session.execute(
            text("SELECT 1 FROM members WHERE id = :id AND deleted_at IS NULL"),
            {"id": str(member_uuid)},
        )).scalar_one_or_none()
        if exists is None:
            raise HTTPException(status_code=400, detail="member_id not found")

    appt_id = uuid.uuid4()
    actor_id = _coerce_author_uuid(current_user.id)

    row = (await session.execute(
        text(
            """
            INSERT INTO appointments
                (id, lead_id, member_id, contact_name, contact_email, contact_phone,
                 status, appointment_type, scheduled_at, end_at, source, notes, created_by)
            VALUES
                (:id, :lead_id, :member_id, :contact_name, :contact_email, :contact_phone,
                 :status, :appointment_type, :scheduled_at, :end_at, 'manual', :notes, :created_by)
            RETURNING id::text AS id, contact_name, contact_email, contact_phone,
                      lead_id::text AS lead_id, member_id::text AS member_id,
                      status, appointment_type, scheduled_at, end_at, source,
                      external_id, notes, created_at
            """
        ),
        {
            "id": str(appt_id),
            "lead_id": str(lead_uuid) if lead_uuid else None,
            "member_id": str(member_uuid) if member_uuid else None,
            "contact_name": body.contact_name,
            "contact_email": (body.contact_email or "").lower().strip() or None,
            "contact_phone": body.contact_phone,
            "status": status,
            "appointment_type": body.appointment_type,
            "scheduled_at": scheduled_at,
            "end_at": end_at,
            "notes": body.notes,
            "created_by": str(actor_id) if actor_id else None,
        },
    )).mappings().one()

    await record_event(
        session,
        user_id=actor_id,
        action="appointment.created",
        table_name="appointments",
        record_id=row["id"],
        after={
            "contact_name": body.contact_name,
            "status": status,
            "scheduled_at": scheduled_at.isoformat() if scheduled_at else None,
            "source": "manual",
        },
    )
    await session.commit()
    return await _detail_from_row(session, row)


# ---------------------------------------------------------------------------
# GET /appointments/{id}
# ---------------------------------------------------------------------------


async def _detail_from_row(session: AsyncSession, r) -> AppointmentDetailResponse:
    """Build a detail response, resolving lead/member display names."""
    lead_name: str | None = None
    member_name: str | None = None
    if r["lead_id"]:
        lead_name = (await session.execute(
            text("SELECT name FROM leads WHERE id = :id"), {"id": r["lead_id"]}
        )).scalar_one_or_none()
    if r["member_id"]:
        member_name = (await session.execute(
            text("SELECT name FROM members WHERE id = :id"), {"id": r["member_id"]}
        )).scalar_one_or_none()
    return AppointmentDetailResponse(
        id=r["id"],
        contact_name=r["contact_name"],
        contact_email=r["contact_email"],
        contact_phone=r["contact_phone"],
        lead_id=r["lead_id"],
        lead_name=lead_name,
        member_id=r["member_id"],
        member_name=member_name,
        status=r["status"],
        appointment_type=r["appointment_type"],
        scheduled_at=r["scheduled_at"].isoformat() if r["scheduled_at"] else None,
        end_at=r["end_at"].isoformat() if r["end_at"] else None,
        source=r["source"],
        external_id=r["external_id"],
        notes=r["notes"],
        created_at=r["created_at"].isoformat() if r["created_at"] else None,
    )


@router.get("/appointments/{appointment_id}", response_model=AppointmentDetailResponse)
async def get_appointment_detail(
    appointment_id: str,
    session: AsyncSession = Depends(get_session),
) -> AppointmentDetailResponse:
    uid = _parse_appointment_uuid(appointment_id)
    r = (await session.execute(
        text(
            """
            SELECT id::text AS id, contact_name, contact_email, contact_phone,
                   lead_id::text AS lead_id, member_id::text AS member_id,
                   status, appointment_type, scheduled_at, end_at, source,
                   external_id, notes, created_at
            FROM appointments
            WHERE id = :id AND deleted_at IS NULL
            """
        ),
        {"id": str(uid)},
    )).mappings().one_or_none()
    if r is None:
        raise HTTPException(status_code=404, detail="Appointment not found")
    return await _detail_from_row(session, r)


# ---------------------------------------------------------------------------
# GET /appointments/{id}/history
# ---------------------------------------------------------------------------


@router.get("/appointments/{appointment_id}/history", response_model=AppointmentHistoryResponse)
async def get_appointment_history(
    appointment_id: str,
    session: AsyncSession = Depends(get_session),
) -> AppointmentHistoryResponse:
    uid = _parse_appointment_uuid(appointment_id)
    exists = (await session.execute(
        text("SELECT 1 FROM appointments WHERE id = :id AND deleted_at IS NULL"),
        {"id": str(uid)},
    )).scalar_one_or_none()
    if exists is None:
        raise HTTPException(status_code=404, detail="Appointment not found")

    rows = (await session.execute(
        text(
            """
            SELECT al.id::text AS id, al.action,
                   al.before_value AS before, al.after_value AS after,
                   al.user_id::text AS author_id, u.email AS author_email,
                   al.created_at
            FROM audit_log al
            LEFT JOIN users u ON u.id = al.user_id
            WHERE al.table_name = 'appointments' AND al.record_id = :record_id
            ORDER BY al.created_at DESC
            """
        ),
        {"record_id": str(uid)},
    )).mappings().all()

    return AppointmentHistoryResponse(events=[
        AppointmentHistoryEvent(
            id=r["id"], action=r["action"], before=r["before"], after=r["after"],
            author_id=r["author_id"], author_email=r["author_email"],
            created_at=r["created_at"].isoformat(),
        )
        for r in rows
    ])


# ---------------------------------------------------------------------------
# PATCH /appointments/{id}
# ---------------------------------------------------------------------------


@router.patch("/appointments/{appointment_id}", response_model=AppointmentDetailResponse)
async def update_appointment(
    appointment_id: str,
    body: UpdateAppointmentRequest,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> AppointmentDetailResponse:
    """Partial-update an appointment (status / scheduled_at / end_at / type / notes)."""
    uid = _parse_appointment_uuid(appointment_id)
    updates = {k: v for k, v in body.model_dump(exclude_unset=True).items() if k in _PATCH_FIELDS}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    before_row = (await session.execute(
        text("SELECT status, scheduled_at FROM appointments WHERE id = :id AND deleted_at IS NULL"),
        {"id": str(uid)},
    )).mappings().one_or_none()
    if before_row is None:
        raise HTTPException(status_code=404, detail="Appointment not found")

    set_parts: list[str] = []
    params: dict[str, object] = {"id": str(uid)}
    if "status" in updates:
        set_parts.append("status = :status")
        params["status"] = (updates["status"] or "").strip().lower()
    if "scheduled_at" in updates:
        set_parts.append("scheduled_at = :scheduled_at")
        params["scheduled_at"] = _parse_dt(updates["scheduled_at"])
    if "end_at" in updates:
        set_parts.append("end_at = :end_at")
        params["end_at"] = _parse_dt(updates["end_at"])
    if "appointment_type" in updates:
        set_parts.append("appointment_type = :appointment_type")
        params["appointment_type"] = updates["appointment_type"]
    if "notes" in updates:
        set_parts.append("notes = :notes")
        params["notes"] = updates["notes"]

    r = (await session.execute(
        text(
            f"""
            UPDATE appointments SET {', '.join(set_parts)}
            WHERE id = :id AND deleted_at IS NULL
            RETURNING id::text AS id, contact_name, contact_email, contact_phone,
                      lead_id::text AS lead_id, member_id::text AS member_id,
                      status, appointment_type, scheduled_at, end_at, source,
                      external_id, notes, created_at
            """  # noqa: S608 — set_parts keys whitelisted via _PATCH_FIELDS
        ),
        params,
    )).mappings().one()

    actor_id = _coerce_author_uuid(current_user.id)
    new_status = params.get("status")
    if new_status is not None and new_status != before_row["status"]:
        await record_event(
            session, user_id=actor_id, action="appointment.status_changed",
            table_name="appointments", record_id=str(uid),
            before={"status": before_row["status"]}, after={"status": new_status},
        )
    if "scheduled_at" in params and params["scheduled_at"] != before_row["scheduled_at"]:
        await record_event(
            session, user_id=actor_id, action="appointment.rescheduled",
            table_name="appointments", record_id=str(uid),
            before={"scheduled_at": before_row["scheduled_at"].isoformat() if before_row["scheduled_at"] else None},
            after={"scheduled_at": params["scheduled_at"].isoformat() if params["scheduled_at"] else None},
        )

    await session.commit()
    return await _detail_from_row(session, r)


# ---------------------------------------------------------------------------
# DELETE /appointments/{id} — soft-cancel
# ---------------------------------------------------------------------------


@router.delete("/appointments/{appointment_id}", response_model=AppointmentDetailResponse)
async def cancel_appointment(
    appointment_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> AppointmentDetailResponse:
    """Soft-cancel: set status='cancelled' (row stays visible as history)."""
    uid = _parse_appointment_uuid(appointment_id)
    before = (await session.execute(
        text("SELECT status FROM appointments WHERE id = :id AND deleted_at IS NULL"),
        {"id": str(uid)},
    )).mappings().one_or_none()
    if before is None:
        raise HTTPException(status_code=404, detail="Appointment not found")

    r = (await session.execute(
        text(
            """
            UPDATE appointments SET status = 'cancelled'
            WHERE id = :id AND deleted_at IS NULL
            RETURNING id::text AS id, contact_name, contact_email, contact_phone,
                      lead_id::text AS lead_id, member_id::text AS member_id,
                      status, appointment_type, scheduled_at, end_at, source,
                      external_id, notes, created_at
            """
        ),
        {"id": str(uid)},
    )).mappings().one()

    await record_event(
        session,
        user_id=_coerce_author_uuid(current_user.id),
        action="appointment.cancelled",
        table_name="appointments",
        record_id=str(uid),
        before={"status": before["status"]},
        after={"status": "cancelled"},
    )
    await session.commit()
    return await _detail_from_row(session, r)
