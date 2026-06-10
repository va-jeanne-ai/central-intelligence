"""
Members endpoints — the fulfillment-side directory + CRUD.

GET    /api/v1/members              — paginated member list with filters
GET    /api/v1/members/stats        — KPIs, enrollment volume, status, goal funnel
GET    /api/v1/members/{id}         — full detail (calls/goals/wins/pain/notes)
GET    /api/v1/members/{id}/history — audit-log timeline
PATCH  /api/v1/members/{id}         — partial update (name/email/status/coach_id)
POST   /api/v1/members/{id}/notes   — append staff note
DELETE /api/v1/members/{id}/notes/{note_id}

Mirrors routes/leads.py. Stats delegate to ``compute_member_stats`` so the
aggregation has a single source of truth shared with the Fulfillment surfaces.
No GHL push (fulfillment members aren't CRM-synced in this pass).
"""

import logging
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser, get_current_user
from app.database import get_session
from app.repositories.fulfillment_stats import compute_member_stats
from app.schemas.members import (
    CreateMemberNoteRequest,
    CreateMemberRequest,
    EnrollmentVolumePoint,
    GoalFunnelStage,
    MemberCallSummary,
    MemberDetailResponse,
    MemberGoalSummary,
    MemberHistoryEvent,
    MemberHistoryResponse,
    MemberKpiResponse,
    MemberListResponse,
    MemberNoteRow,
    MemberPainPointSummary,
    MemberRecord,
    MemberStatsResponse,
    MemberWinSummary,
    StatusBreakdownItem,
    UpdateMemberRequest,
)
from app.services.audit import record_event

logger = logging.getLogger(__name__)

router = APIRouter(tags=["members"])

# Columns safe to use in ORDER BY (whitelist to prevent injection).
_SORTABLE_COLUMNS: frozenset[str] = frozenset(
    {"created_at", "enrollment_date", "name", "email", "status"}
)
_SORT_DIRS: frozenset[str] = frozenset({"asc", "desc"})

# Whitelisted editable fields for PATCH.
_PATCH_FIELDS: frozenset[str] = frozenset({"name", "email", "status", "coach_id"})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _int(value: object) -> int:
    try:
        return int(value) if value is not None else 0
    except (TypeError, ValueError):
        return 0


def _parse_member_uuid(member_id: str) -> uuid.UUID:
    """Coerce the path param to UUID, 404 on garbage."""
    try:
        return uuid.UUID(member_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Member not found") from exc


def _coerce_author_uuid(user_id: str | uuid.UUID | None) -> uuid.UUID | None:
    """Best-effort UUID coercion for the CurrentUser id (mock-mode → None)."""
    if user_id is None:
        return None
    if isinstance(user_id, uuid.UUID):
        return user_id
    try:
        return uuid.UUID(str(user_id))
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# GET /members — paginated list
# ---------------------------------------------------------------------------


@router.get("/members", response_model=MemberListResponse, summary="Paginated member list")
async def list_members(
    status: str | None = Query(default=None, description="Filter by status"),
    search: str | None = Query(default=None, description="Search name or email"),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=200),
    sort_by: str = Query(default="enrollment_date"),
    sort_dir: Literal["asc", "desc"] = Query(default="desc"),
    session: AsyncSession = Depends(get_session),
) -> MemberListResponse:
    """Return a paginated, filterable list of members."""

    if sort_by not in _SORTABLE_COLUMNS:
        sort_by = "enrollment_date"
    if sort_dir not in _SORT_DIRS:
        sort_dir = "desc"

    where_parts: list[str] = ["deleted_at IS NULL"]
    params: dict[str, object] = {}

    if status:
        where_parts.append("LOWER(status) = :status_filter")
        params["status_filter"] = status.lower()
    if search:
        where_parts.append(
            "(LOWER(name) LIKE :search_pattern OR LOWER(email) LIKE :search_pattern)"
        )
        params["search_pattern"] = f"%{search.lower()}%"

    where_sql = " AND ".join(where_parts)

    count_sql = text(f"SELECT COUNT(*) FROM members WHERE {where_sql}")  # noqa: S608
    total = _int((await session.execute(count_sql, params)).scalar())

    offset = (page - 1) * per_page
    params["limit"] = per_page
    params["offset"] = offset

    data_sql = text(
        f"""
        SELECT
            id::text AS id,
            name,
            email,
            status,
            coach_id::text AS coach_id,
            enrollment_date
        FROM members
        WHERE {where_sql}
        ORDER BY {sort_by} {sort_dir} NULLS LAST
        LIMIT :limit OFFSET :offset
        """  # noqa: S608 — sort_by/sort_dir whitelisted, where_sql parametrised
    )
    rows = (await session.execute(data_sql, params)).mappings().all()

    members = [
        MemberRecord(
            id=r["id"],
            name=r["name"],
            email=r["email"],
            status=r["status"],
            coach_id=r["coach_id"],
            enrollmentDate=r["enrollment_date"].isoformat() if r["enrollment_date"] else None,
        )
        for r in rows
    ]
    return MemberListResponse(members=members, total=total, page=page, per_page=per_page)


# ---------------------------------------------------------------------------
# GET /members/stats
# ---------------------------------------------------------------------------


@router.get(
    "/members/stats",
    response_model=MemberStatsResponse,
    summary="Member KPIs, enrollment volume, status breakdown, goal funnel",
)
async def get_members_stats(
    session: AsyncSession = Depends(get_session),
) -> MemberStatsResponse:
    """Aggregated member statistics (delegates to compute_member_stats)."""
    data = await compute_member_stats(session)
    return MemberStatsResponse(
        kpis=MemberKpiResponse(**data["kpis"]),
        enrollment_volume=[EnrollmentVolumePoint(**p) for p in data["enrollment_volume"]],
        status_breakdown=[StatusBreakdownItem(**s) for s in data["status_breakdown"]],
        goal_funnel=[GoalFunnelStage(**g) for g in data["goal_funnel"]],
    )


# ---------------------------------------------------------------------------
# POST /members — create
# ---------------------------------------------------------------------------


def _parse_enrollment_date(value: str | None) -> "datetime | None":
    """Best-effort ISO date/datetime parse; None on empty/garbage."""
    if not value:
        return None
    from datetime import datetime as _dt

    try:
        # Accept both "2026-06-08" and full ISO timestamps.
        return _dt.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


@router.post("/members", response_model=MemberRecord, status_code=201)
async def create_member(
    body: CreateMemberRequest,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> MemberRecord:
    """Create a new member. Name required; status defaults to 'active'.

    Rejects a duplicate email (members.email is unique-indexed). Emits a
    ``member.created`` audit event in the same transaction.
    """
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name is required")

    email = (body.email or "").strip() or None
    status = (body.status or "active").strip().lower()

    coach_uuid: uuid.UUID | None = None
    if body.coach_id:
        try:
            coach_uuid = uuid.UUID(body.coach_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid coach_id") from exc

    # Duplicate-email guard (friendly 409 rather than a raw DB IntegrityError).
    if email:
        dupe = (await session.execute(
            text("SELECT 1 FROM members WHERE LOWER(email) = :email AND deleted_at IS NULL"),
            {"email": email.lower()},
        )).scalar_one_or_none()
        if dupe is not None:
            raise HTTPException(status_code=409, detail="A member with that email already exists")

    member_id = uuid.uuid4()
    enrollment_dt = _parse_enrollment_date(body.enrollment_date)

    row = (await session.execute(
        text("""
            INSERT INTO members (id, name, email, status, coach_id, enrollment_date)
            VALUES (:id, :name, :email, :status, :coach_id, COALESCE(:enrollment_date, NOW()))
            RETURNING id::text AS id, name, email, status,
                      coach_id::text AS coach_id, enrollment_date
        """),
        {
            "id": str(member_id),
            "name": name,
            "email": email,
            "status": status,
            "coach_id": str(coach_uuid) if coach_uuid else None,
            "enrollment_date": enrollment_dt,
        },
    )).mappings().one()

    await record_event(
        session,
        user_id=_coerce_author_uuid(current_user.id),
        action="member.created",
        table_name="members",
        record_id=row["id"],
        after={"name": name, "email": email, "status": status},
    )

    await session.commit()

    return MemberRecord(
        id=row["id"],
        name=row["name"],
        email=row["email"],
        status=row["status"],
        coach_id=row["coach_id"],
        enrollmentDate=row["enrollment_date"].isoformat() if row["enrollment_date"] else None,
    )


# ---------------------------------------------------------------------------
# GET /members/{id} — detail
# ---------------------------------------------------------------------------


@router.get("/members/{member_id}", response_model=MemberDetailResponse)
async def get_member_detail(
    member_id: str,
    session: AsyncSession = Depends(get_session),
) -> MemberDetailResponse:
    """Return the full member record plus linked calls/goals/wins/pain/notes."""
    uid = _parse_member_uuid(member_id)

    m = (await session.execute(
        text("""
            SELECT id::text AS id, name, email, status, coach_id::text AS coach_id,
                   enrollment_date, created_at
            FROM members
            WHERE id = :id AND deleted_at IS NULL
        """),
        {"id": str(uid)},
    )).mappings().one_or_none()
    if m is None:
        raise HTTPException(status_code=404, detail="Member not found")

    calls = (await session.execute(
        text("""
            SELECT c.id, c.date, c.call_type, c.processed_date,
                   COUNT(i.id) AS insights_count
            FROM calls c
            LEFT JOIN insights i ON i.call_id = c.id
            WHERE c.member_id = :id AND c.deleted_at IS NULL
            GROUP BY c.id
            ORDER BY c.date DESC NULLS LAST
        """),
        {"id": str(uid)},
    )).mappings().all()

    goals = (await session.execute(
        text("""
            SELECT id::text AS id, goal_text, status, target_date
            FROM goals
            WHERE member_id = :id AND deleted_at IS NULL
            ORDER BY created_at DESC
        """),
        {"id": str(uid)},
    )).mappings().all()

    wins = (await session.execute(
        text("""
            SELECT id::text AS id, win_text, impact_area, win_date
            FROM wins
            WHERE member_id = :id AND deleted_at IS NULL
            ORDER BY win_date DESC NULLS LAST
        """),
        {"id": str(uid)},
    )).mappings().all()

    pain = (await session.execute(
        text("""
            SELECT id::text AS id, text, category
            FROM pain_points
            WHERE member_id = :id AND deleted_at IS NULL
            ORDER BY frequency_count DESC
        """),
        {"id": str(uid)},
    )).mappings().all()

    notes = (await session.execute(
        text("""
            SELECT mn.id::text AS id, mn.body, mn.author_id::text AS author_id,
                   u.email AS author_email, mn.created_at
            FROM member_notes mn
            LEFT JOIN users u ON u.id = mn.author_id
            WHERE mn.member_id = :id
            ORDER BY mn.created_at DESC
        """),
        {"id": str(uid)},
    )).mappings().all()

    return MemberDetailResponse(
        id=m["id"],
        name=m["name"],
        email=m["email"],
        status=m["status"],
        coach_id=m["coach_id"],
        enrollment_date=m["enrollment_date"].isoformat() if m["enrollment_date"] else None,
        created_at=m["created_at"].isoformat() if m["created_at"] else None,
        calls=[
            MemberCallSummary(
                id=c["id"],
                date=c["date"].isoformat() if c["date"] else None,
                call_type=c["call_type"],
                insights_count=_int(c["insights_count"]),
                processed_date=c["processed_date"].isoformat() if c["processed_date"] else None,
            )
            for c in calls
        ],
        goals=[
            MemberGoalSummary(
                id=g["id"],
                goal_text=g["goal_text"],
                status=g["status"],
                target_date=g["target_date"].isoformat() if g["target_date"] else None,
            )
            for g in goals
        ],
        wins=[
            MemberWinSummary(
                id=w["id"],
                win_text=w["win_text"],
                impact_area=w["impact_area"],
                win_date=w["win_date"].isoformat() if w["win_date"] else None,
            )
            for w in wins
        ],
        pain_points=[
            MemberPainPointSummary(id=p["id"], text=p["text"], category=p["category"])
            for p in pain
        ],
        staff_notes=[
            MemberNoteRow(
                id=n["id"],
                body=n["body"],
                author_id=n["author_id"],
                author_email=n["author_email"],
                created_at=n["created_at"].isoformat(),
            )
            for n in notes
        ],
    )


# ---------------------------------------------------------------------------
# GET /members/{id}/history
# ---------------------------------------------------------------------------


@router.get("/members/{member_id}/history", response_model=MemberHistoryResponse)
async def get_member_history(
    member_id: str,
    session: AsyncSession = Depends(get_session),
) -> MemberHistoryResponse:
    """Audit-log timeline for one member, newest first, with a synthetic
    ``member.created`` anchor."""
    uid = _parse_member_uuid(member_id)

    m = (await session.execute(
        text("""
            SELECT enrollment_date, created_at, coach_id::text AS coach_id
            FROM members
            WHERE id = :id AND deleted_at IS NULL
        """),
        {"id": str(uid)},
    )).mappings().one_or_none()
    if m is None:
        raise HTTPException(status_code=404, detail="Member not found")

    audit_rows = (await session.execute(
        text("""
            SELECT al.id::text AS id, al.action,
                   al.before_value AS before, al.after_value AS after,
                   al.user_id::text AS author_id, u.email AS author_email,
                   al.created_at
            FROM audit_log al
            LEFT JOIN users u ON u.id = al.user_id
            WHERE al.table_name = 'members' AND al.record_id = :record_id
            ORDER BY al.created_at DESC
        """),
        {"record_id": str(uid)},
    )).mappings().all()

    events: list[MemberHistoryEvent] = [
        MemberHistoryEvent(
            id=r["id"],
            action=r["action"],
            before=r["before"],
            after=r["after"],
            author_id=r["author_id"],
            author_email=r["author_email"],
            created_at=r["created_at"].isoformat(),
        )
        for r in audit_rows
    ]

    anchor = m["enrollment_date"] or m["created_at"]
    if anchor:
        events.append(
            MemberHistoryEvent(
                id="synthetic-created",
                action="member.created",
                before=None,
                after={"coach_id": m["coach_id"]} if m["coach_id"] else None,
                author_id=None,
                author_email=None,
                created_at=anchor.isoformat(),
            )
        )

    return MemberHistoryResponse(events=events)


# ---------------------------------------------------------------------------
# PATCH /members/{id}
# ---------------------------------------------------------------------------


@router.patch("/members/{member_id}", response_model=MemberRecord)
async def update_member(
    member_id: str,
    body: UpdateMemberRequest,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> MemberRecord:
    """Partial-update a member (name/email/status/coach_id).

    Emits one ``member.<field>_changed`` audit event per field that actually
    changed value. Audit rows share the UPDATE's transaction.
    """
    uid = _parse_member_uuid(member_id)

    updates = {k: v for k, v in body.model_dump(exclude_unset=True).items() if k in _PATCH_FIELDS}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    before_row = (await session.execute(
        text("""
            SELECT name, email, status, coach_id::text AS coach_id
            FROM members
            WHERE id = :id AND deleted_at IS NULL
        """),
        {"id": str(uid)},
    )).mappings().one_or_none()
    if before_row is None:
        raise HTTPException(status_code=404, detail="Member not found")

    set_parts: list[str] = []
    params: dict[str, object] = {"id": str(uid)}
    for field in ("name", "email", "status", "coach_id"):
        if field in updates:
            set_parts.append(f"{field} = :{field}")
            params[field] = updates[field]

    sql = f"""
        UPDATE members
        SET {', '.join(set_parts)}
        WHERE id = :id AND deleted_at IS NULL
        RETURNING id::text AS id, name, email, status, coach_id::text AS coach_id, enrollment_date
    """  # noqa: S608 — set_parts keys are whitelisted via _PATCH_FIELDS
    row = (await session.execute(text(sql), params)).mappings().one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Member not found")

    actor_id = _coerce_author_uuid(current_user.id)
    _ACTION = {
        "name": "member.name_changed",
        "email": "member.email_changed",
        "status": "member.status_changed",
        "coach_id": "member.coach_changed",
    }
    for field in ("name", "email", "status", "coach_id"):
        if field in updates and updates[field] != before_row[field]:
            await record_event(
                session,
                user_id=actor_id,
                action=_ACTION[field],
                table_name="members",
                record_id=str(uid),
                before={field: before_row[field]},
                after={field: updates[field]},
            )

    await session.commit()

    return MemberRecord(
        id=row["id"],
        name=row["name"],
        email=row["email"],
        status=row["status"],
        coach_id=row["coach_id"],
        enrollmentDate=row["enrollment_date"].isoformat() if row["enrollment_date"] else None,
    )


# ---------------------------------------------------------------------------
# POST /members/{id}/notes  +  DELETE /members/{id}/notes/{note_id}
# ---------------------------------------------------------------------------


@router.post("/members/{member_id}/notes", response_model=MemberNoteRow, status_code=201)
async def create_member_note(
    member_id: str,
    body: CreateMemberNoteRequest,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> MemberNoteRow:
    """Append a staff journal note to a member."""
    uid = _parse_member_uuid(member_id)

    exists = (await session.execute(
        text("SELECT 1 FROM members WHERE id = :id AND deleted_at IS NULL"),
        {"id": str(uid)},
    )).scalar_one_or_none()
    if exists is None:
        raise HTTPException(status_code=404, detail="Member not found")

    note_id = uuid.uuid4()
    author_uuid = _coerce_author_uuid(current_user.id)
    if author_uuid is not None:
        user_exists = (await session.execute(
            text("SELECT 1 FROM users WHERE id = :id"),
            {"id": str(author_uuid)},
        )).scalar_one_or_none()
        if user_exists is None:
            author_uuid = None

    row = (await session.execute(
        text("""
            INSERT INTO member_notes (id, member_id, author_id, body)
            VALUES (:id, :member_id, :author_id, :body)
            RETURNING id::text AS id, body, author_id::text AS author_id, created_at
        """),
        {
            "id": str(note_id),
            "member_id": str(uid),
            "author_id": str(author_uuid) if author_uuid else None,
            "body": body.body,
        },
    )).mappings().one()

    await record_event(
        session,
        user_id=_coerce_author_uuid(current_user.id),
        action="member.note_added",
        table_name="members",
        record_id=str(uid),
        after={"note_id": row["id"], "preview": body.body[:80]},
    )

    await session.commit()

    return MemberNoteRow(
        id=row["id"],
        body=row["body"],
        author_id=row["author_id"],
        author_email=current_user.email,
        created_at=row["created_at"].isoformat(),
    )


@router.delete("/members/{member_id}/notes/{note_id}", status_code=204)
async def delete_member_note(
    member_id: str,
    note_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> Response:
    """Hard-delete a staff note (single-tenant, no author check in v1)."""
    member_uid = _parse_member_uuid(member_id)
    note_uid = _parse_member_uuid(note_id)

    deleted = (await session.execute(
        text("""
            DELETE FROM member_notes
            WHERE id = :note_id AND member_id = :member_id
            RETURNING id::text AS id, body
        """),
        {"note_id": str(note_uid), "member_id": str(member_uid)},
    )).mappings().one_or_none()
    if deleted is None:
        raise HTTPException(status_code=404, detail="Note not found")

    await record_event(
        session,
        user_id=_coerce_author_uuid(current_user.id),
        action="member.note_deleted",
        table_name="members",
        record_id=str(member_uid),
        before={"note_id": deleted["id"], "preview": deleted["body"][:80]},
    )

    await session.commit()
    return Response(status_code=204)
