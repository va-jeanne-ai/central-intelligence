"""
Tech SOS (support ticket) endpoints.

GET    /api/v1/tech-sos              — paginated list with filters
GET    /api/v1/tech-sos/stats        — KPIs, category + status breakdown, volume
GET    /api/v1/tech-sos/{id}         — detail (+ member name)
GET    /api/v1/tech-sos/{id}/history — audit timeline
POST   /api/v1/tech-sos              — staff create a ticket (member optional)
POST   /api/v1/tech-sos/submit       — PUBLIC member submit (no auth; best-effort member link)
PATCH  /api/v1/tech-sos/{id}         — update status/category/priority/resolution/subject/description
DELETE /api/v1/tech-sos/{id}         — soft-delete

Mirrors routes/appointments.py. Stats delegate to compute_ticket_stats.

NOTE: the whole /api/v1/tech-sos prefix is auth-exempt (so the public submit
works). The admin GET/PATCH/DELETE are used by the staff frontend's authed
client — same convention as /members, /goals, /appointments.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser, get_current_user
from app.database import get_session
from app.repositories.tech_sos_stats import compute_ticket_stats
from app.schemas.tech_sos import (
    CategoryBreakdownItem,
    CreateTicketRequest,
    StatusBreakdownItem,
    SubmitTicketRequest,
    SubmitTicketResponse,
    TicketDetailResponse,
    TicketHistoryEvent,
    TicketHistoryResponse,
    TicketKpiResponse,
    TicketListResponse,
    TicketRecord,
    TicketStatsResponse,
    TicketVolumePoint,
    UpdateTicketRequest,
)
from app.services.audit import record_event

logger = logging.getLogger(__name__)

router = APIRouter(tags=["tech-sos"])

_SORTABLE_COLUMNS: frozenset[str] = frozenset({"created_at", "status", "category"})
_SORT_DIRS: frozenset[str] = frozenset({"asc", "desc"})
_PATCH_FIELDS: frozenset[str] = frozenset(
    {"subject", "description", "category", "status", "priority", "resolution"}
)
_RESOLVED_STATUSES: frozenset[str] = frozenset({"resolved", "closed"})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _int(value: object) -> int:
    try:
        return int(value) if value is not None else 0
    except (TypeError, ValueError):
        return 0


def _parse_ticket_uuid(ticket_id: str) -> uuid.UUID:
    try:
        return uuid.UUID(ticket_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Ticket not found") from exc


def _coerce_author_uuid(user_id: str | uuid.UUID | None) -> uuid.UUID | None:
    if user_id is None:
        return None
    if isinstance(user_id, uuid.UUID):
        return user_id
    try:
        return uuid.UUID(str(user_id))
    except ValueError:
        return None


async def _resolve_member_by_email(session: AsyncSession, email: str | None) -> uuid.UUID | None:
    if not email:
        return None
    return (await session.execute(
        text("SELECT id FROM members WHERE LOWER(email) = :email AND deleted_at IS NULL"),
        {"email": email.lower().strip()},
    )).scalar_one_or_none()


# ---------------------------------------------------------------------------
# GET /tech-sos
# ---------------------------------------------------------------------------


@router.get("/tech-sos", response_model=TicketListResponse, summary="Paginated ticket list")
async def list_tickets(
    status: str | None = Query(default=None),
    category: str | None = Query(default=None),
    member_id: str | None = Query(default=None),
    search: str | None = Query(default=None, description="Search subject/contact"),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=200),
    sort_by: str = Query(default="created_at"),
    sort_dir: Literal["asc", "desc"] = Query(default="desc"),
    session: AsyncSession = Depends(get_session),
) -> TicketListResponse:
    if sort_by not in _SORTABLE_COLUMNS:
        sort_by = "created_at"
    if sort_dir not in _SORT_DIRS:
        sort_dir = "desc"

    where_parts: list[str] = ["t.deleted_at IS NULL"]
    params: dict[str, object] = {}
    if status:
        where_parts.append("LOWER(t.status) = :status_filter")
        params["status_filter"] = status.lower()
    if category:
        where_parts.append("LOWER(t.category) = :category_filter")
        params["category_filter"] = category.lower()
    if member_id:
        try:
            params["member_filter"] = str(uuid.UUID(member_id))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid member_id") from exc
        where_parts.append("t.member_id = :member_filter")
    if search:
        where_parts.append("(LOWER(t.subject) LIKE :search OR LOWER(t.contact_name) LIKE :search)")
        params["search"] = f"%{search.lower()}%"

    where_sql = " AND ".join(where_parts)

    total = _int((await session.execute(
        text(f"SELECT COUNT(*) FROM support_tickets t WHERE {where_sql}"),  # noqa: S608
        params,
    )).scalar())

    params["limit"] = per_page
    params["offset"] = (page - 1) * per_page
    rows = (await session.execute(
        text(
            f"""
            SELECT t.id::text AS id, t.member_id::text AS member_id, m.name AS member_name,
                   t.contact_name, t.contact_email, t.subject, t.category, t.status,
                   t.priority, t.source, t.created_at, t.resolved_at
            FROM support_tickets t
            LEFT JOIN members m ON m.id = t.member_id
            WHERE {where_sql}
            ORDER BY t.{sort_by} {sort_dir} NULLS LAST
            LIMIT :limit OFFSET :offset
            """  # noqa: S608 — sort_by/sort_dir whitelisted, where_sql parametrised
        ),
        params,
    )).mappings().all()

    tickets = [
        TicketRecord(
            id=r["id"], member_id=r["member_id"], member_name=r["member_name"],
            contact_name=r["contact_name"], contact_email=r["contact_email"],
            subject=r["subject"], category=r["category"], status=r["status"],
            priority=r["priority"], source=r["source"],
            createdAt=r["created_at"].isoformat() if r["created_at"] else None,
            resolvedAt=r["resolved_at"].isoformat() if r["resolved_at"] else None,
        )
        for r in rows
    ]
    return TicketListResponse(tickets=tickets, total=total, page=page, per_page=per_page)


# ---------------------------------------------------------------------------
# GET /tech-sos/stats
# ---------------------------------------------------------------------------


@router.get("/tech-sos/stats", response_model=TicketStatsResponse)
async def get_tickets_stats(
    session: AsyncSession = Depends(get_session),
) -> TicketStatsResponse:
    data = await compute_ticket_stats(session)
    return TicketStatsResponse(
        kpis=TicketKpiResponse(**data["kpis"]),
        category_breakdown=[CategoryBreakdownItem(**c) for c in data["category_breakdown"]],
        status_breakdown=[StatusBreakdownItem(**s) for s in data["status_breakdown"]],
        ticket_volume=[TicketVolumePoint(**v) for v in data["ticket_volume"]],
    )


# ---------------------------------------------------------------------------
# POST /tech-sos/submit — PUBLIC member submit (declared before /{id} routes)
# ---------------------------------------------------------------------------


@router.post("/tech-sos/submit", response_model=SubmitTicketResponse, status_code=201)
async def submit_ticket(
    body: SubmitTicketRequest,
    session: AsyncSession = Depends(get_session),
) -> SubmitTicketResponse:
    """Public ticket submission (no auth). Best-effort member link by email."""
    subject = body.subject.strip()
    description = body.description.strip()
    if not subject or not description:
        raise HTTPException(status_code=400, detail="subject and description are required")

    contact_email = (body.contact_email or "").lower().strip() or None
    member_uuid = await _resolve_member_by_email(session, contact_email)
    ticket_id = uuid.uuid4()

    await session.execute(
        text(
            """
            INSERT INTO support_tickets
                (id, member_id, contact_name, contact_email, subject, description,
                 category, status, priority, source)
            VALUES
                (:id, :member_id, :contact_name, :contact_email, :subject, :description,
                 :category, 'open', 'normal', 'submit')
            """
        ),
        {
            "id": str(ticket_id),
            "member_id": str(member_uuid) if member_uuid else None,
            "contact_name": body.contact_name,
            "contact_email": contact_email,
            "subject": subject,
            "description": description,
            "category": (body.category or "").strip().lower() or None,
        },
    )
    await record_event(
        session, user_id=None, action="ticket.created",
        table_name="support_tickets", record_id=str(ticket_id),
        after={"subject": subject, "source": "submit"},
    )
    await session.commit()
    return SubmitTicketResponse(id=str(ticket_id))


# ---------------------------------------------------------------------------
# POST /tech-sos — staff create
# ---------------------------------------------------------------------------


async def _ticket_detail(session: AsyncSession, r) -> TicketDetailResponse:
    member_name = None
    if r["member_id"]:
        member_name = (await session.execute(
            text("SELECT name FROM members WHERE id = :id"), {"id": r["member_id"]}
        )).scalar_one_or_none()
    return TicketDetailResponse(
        id=r["id"], member_id=r["member_id"], member_name=member_name,
        contact_name=r["contact_name"], contact_email=r["contact_email"],
        subject=r["subject"], description=r["description"], category=r["category"],
        status=r["status"], priority=r["priority"], resolution=r["resolution"],
        source=r["source"],
        created_at=r["created_at"].isoformat() if r["created_at"] else None,
        resolved_at=r["resolved_at"].isoformat() if r["resolved_at"] else None,
    )


@router.post("/tech-sos", response_model=TicketDetailResponse, status_code=201)
async def create_ticket(
    body: CreateTicketRequest,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> TicketDetailResponse:
    """Staff-create a ticket on a member's behalf (member optional)."""
    subject = body.subject.strip()
    if not subject:
        raise HTTPException(status_code=400, detail="subject is required")

    member_uuid: uuid.UUID | None = None
    if body.member_id:
        try:
            member_uuid = uuid.UUID(body.member_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid member_id") from exc
        exists = (await session.execute(
            text("SELECT 1 FROM members WHERE id = :id AND deleted_at IS NULL"),
            {"id": str(member_uuid)},
        )).scalar_one_or_none()
        if exists is None:
            raise HTTPException(status_code=400, detail="member_id not found")

    ticket_id = uuid.uuid4()
    actor_id = _coerce_author_uuid(current_user.id)

    r = (await session.execute(
        text(
            """
            INSERT INTO support_tickets
                (id, member_id, contact_name, contact_email, subject, description,
                 category, status, priority, source, created_by)
            VALUES
                (:id, :member_id, :contact_name, :contact_email, :subject, :description,
                 :category, 'open', :priority, 'staff', :created_by)
            RETURNING id::text AS id, member_id::text AS member_id, contact_name, contact_email,
                      subject, description, category, status, priority, resolution, source,
                      created_at, resolved_at
            """
        ),
        {
            "id": str(ticket_id),
            "member_id": str(member_uuid) if member_uuid else None,
            "contact_name": body.contact_name,
            "contact_email": (body.contact_email or "").lower().strip() or None,
            "subject": subject,
            "description": body.description,
            "category": (body.category or "").strip().lower() or None,
            "priority": (body.priority or "normal").strip().lower(),
            "created_by": str(actor_id) if actor_id else None,
        },
    )).mappings().one()

    await record_event(
        session, user_id=actor_id, action="ticket.created",
        table_name="support_tickets", record_id=r["id"],
        after={"subject": subject, "member_id": r["member_id"], "source": "staff"},
    )
    await session.commit()
    return await _ticket_detail(session, r)


# ---------------------------------------------------------------------------
# GET /tech-sos/{id}
# ---------------------------------------------------------------------------


@router.get("/tech-sos/{ticket_id}", response_model=TicketDetailResponse)
async def get_ticket_detail(
    ticket_id: str,
    session: AsyncSession = Depends(get_session),
) -> TicketDetailResponse:
    uid = _parse_ticket_uuid(ticket_id)
    r = (await session.execute(
        text(
            """
            SELECT id::text AS id, member_id::text AS member_id, contact_name, contact_email,
                   subject, description, category, status, priority, resolution, source,
                   created_at, resolved_at
            FROM support_tickets
            WHERE id = :id AND deleted_at IS NULL
            """
        ),
        {"id": str(uid)},
    )).mappings().one_or_none()
    if r is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return await _ticket_detail(session, r)


# ---------------------------------------------------------------------------
# GET /tech-sos/{id}/history
# ---------------------------------------------------------------------------


@router.get("/tech-sos/{ticket_id}/history", response_model=TicketHistoryResponse)
async def get_ticket_history(
    ticket_id: str,
    session: AsyncSession = Depends(get_session),
) -> TicketHistoryResponse:
    uid = _parse_ticket_uuid(ticket_id)
    exists = (await session.execute(
        text("SELECT 1 FROM support_tickets WHERE id = :id AND deleted_at IS NULL"),
        {"id": str(uid)},
    )).scalar_one_or_none()
    if exists is None:
        raise HTTPException(status_code=404, detail="Ticket not found")

    rows = (await session.execute(
        text(
            """
            SELECT al.id::text AS id, al.action,
                   al.before_value AS before, al.after_value AS after,
                   al.user_id::text AS author_id, u.email AS author_email, al.created_at
            FROM audit_log al
            LEFT JOIN users u ON u.id = al.user_id
            WHERE al.table_name = 'support_tickets' AND al.record_id = :record_id
            ORDER BY al.created_at DESC
            """
        ),
        {"record_id": str(uid)},
    )).mappings().all()
    return TicketHistoryResponse(events=[
        TicketHistoryEvent(
            id=r["id"], action=r["action"], before=r["before"], after=r["after"],
            author_id=r["author_id"], author_email=r["author_email"],
            created_at=r["created_at"].isoformat(),
        )
        for r in rows
    ])


# ---------------------------------------------------------------------------
# PATCH /tech-sos/{id}
# ---------------------------------------------------------------------------


@router.patch("/tech-sos/{ticket_id}", response_model=TicketDetailResponse)
async def update_ticket(
    ticket_id: str,
    body: UpdateTicketRequest,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> TicketDetailResponse:
    """Update a ticket. Setting status to resolved/closed stamps resolved_at;
    reopening clears it."""
    uid = _parse_ticket_uuid(ticket_id)
    updates = {k: v for k, v in body.model_dump(exclude_unset=True).items() if k in _PATCH_FIELDS}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    before = (await session.execute(
        text("SELECT status, category, priority FROM support_tickets WHERE id = :id AND deleted_at IS NULL"),
        {"id": str(uid)},
    )).mappings().one_or_none()
    if before is None:
        raise HTTPException(status_code=404, detail="Ticket not found")

    set_parts: list[str] = []
    params: dict[str, object] = {"id": str(uid)}
    for field in ("subject", "description", "resolution"):
        if field in updates:
            set_parts.append(f"{field} = :{field}")
            params[field] = updates[field]
    if "category" in updates:
        set_parts.append("category = :category")
        params["category"] = (updates["category"] or "").strip().lower() or None
    if "priority" in updates:
        set_parts.append("priority = :priority")
        params["priority"] = (updates["priority"] or "").strip().lower() or None
    new_status: str | None = None
    if "status" in updates:
        new_status = (updates["status"] or "").strip().lower()
        set_parts.append("status = :status")
        params["status"] = new_status
        # Stamp / clear resolved_at based on the new status.
        if new_status in _RESOLVED_STATUSES:
            set_parts.append("resolved_at = COALESCE(resolved_at, NOW())")
        else:
            set_parts.append("resolved_at = NULL")

    r = (await session.execute(
        text(
            f"""
            UPDATE support_tickets SET {', '.join(set_parts)}
            WHERE id = :id AND deleted_at IS NULL
            RETURNING id::text AS id, member_id::text AS member_id, contact_name, contact_email,
                      subject, description, category, status, priority, resolution, source,
                      created_at, resolved_at
            """  # noqa: S608 — set_parts keys whitelisted via _PATCH_FIELDS
        ),
        params,
    )).mappings().one()

    actor_id = _coerce_author_uuid(current_user.id)
    if new_status is not None and new_status != before["status"]:
        await record_event(
            session, user_id=actor_id, action="ticket.status_changed",
            table_name="support_tickets", record_id=str(uid),
            before={"status": before["status"]}, after={"status": new_status},
        )
    if "category" in params and params["category"] != before["category"]:
        await record_event(
            session, user_id=actor_id, action="ticket.category_changed",
            table_name="support_tickets", record_id=str(uid),
            before={"category": before["category"]}, after={"category": params["category"]},
        )

    await session.commit()
    return await _ticket_detail(session, r)


# ---------------------------------------------------------------------------
# DELETE /tech-sos/{id} — soft-delete
# ---------------------------------------------------------------------------


@router.delete("/tech-sos/{ticket_id}", status_code=204)
async def delete_ticket(
    ticket_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> Response:
    uid = _parse_ticket_uuid(ticket_id)
    r = (await session.execute(
        text(
            """
            UPDATE support_tickets SET deleted_at = NOW()
            WHERE id = :id AND deleted_at IS NULL
            RETURNING subject
            """
        ),
        {"id": str(uid)},
    )).mappings().one_or_none()
    if r is None:
        raise HTTPException(status_code=404, detail="Ticket not found")

    await record_event(
        session, user_id=_coerce_author_uuid(current_user.id), action="ticket.deleted",
        table_name="support_tickets", record_id=str(uid),
        before={"subject": (r["subject"] or "")[:120]},
    )
    await session.commit()
    return Response(status_code=204)
