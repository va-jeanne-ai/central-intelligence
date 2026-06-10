"""
Goals (accountability) endpoints — cross-member goal tracking + CRUD.

GET    /api/v1/goals              — paginated list with filters
GET    /api/v1/goals/stats        — KPIs, funnel, status breakdown
GET    /api/v1/goals/{id}         — detail (+ member name)
GET    /api/v1/goals/{id}/history — audit-log timeline
POST   /api/v1/goals              — create a goal for a member
PATCH  /api/v1/goals/{id}         — update goal_text/status/target_date
DELETE /api/v1/goals/{id}         — soft-delete (deleted_at)

Mirrors routes/members.py. Stats delegate to compute_goal_stats. Goals are
member-scoped here (accountability is a fulfillment surface); lead goals still
render on the lead detail page elsewhere.
"""

import logging
import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser, get_current_user
from app.database import get_session
from app.repositories.goal_stats import compute_goal_stats
from app.schemas.goals import (
    CreateGoalRequest,
    GoalDetailResponse,
    GoalFunnelStage,
    GoalHistoryEvent,
    GoalHistoryResponse,
    GoalKpiResponse,
    GoalListResponse,
    GoalRecord,
    GoalStatsResponse,
    StatusBreakdownItem,
    UpdateGoalRequest,
)
from app.services.audit import record_event

logger = logging.getLogger(__name__)

router = APIRouter(tags=["goals"])

_SORTABLE_COLUMNS: frozenset[str] = frozenset({"created_at", "target_date", "status"})
_SORT_DIRS: frozenset[str] = frozenset({"asc", "desc"})
_PATCH_FIELDS: frozenset[str] = frozenset({"goal_text", "status", "stage", "target_date"})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _int(value: object) -> int:
    try:
        return int(value) if value is not None else 0
    except (TypeError, ValueError):
        return 0


def _parse_goal_uuid(goal_id: str) -> uuid.UUID:
    try:
        return uuid.UUID(goal_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Goal not found") from exc


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
        raise HTTPException(status_code=400, detail=f"Invalid date: {value!r}") from exc


# ---------------------------------------------------------------------------
# GET /goals
# ---------------------------------------------------------------------------


@router.get("/goals", response_model=GoalListResponse, summary="Paginated goal list")
async def list_goals(
    member_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    stage: str | None = Query(default=None),
    overdue: bool = Query(default=False),
    search: str | None = Query(default=None, description="Search goal text"),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=200),
    sort_by: str = Query(default="created_at"),
    sort_dir: Literal["asc", "desc"] = Query(default="desc"),
    session: AsyncSession = Depends(get_session),
) -> GoalListResponse:
    """Return a paginated, filterable list of member goals."""

    if sort_by not in _SORTABLE_COLUMNS:
        sort_by = "created_at"
    if sort_dir not in _SORT_DIRS:
        sort_dir = "desc"

    # Accountability is member-scoped.
    where_parts: list[str] = ["g.member_id IS NOT NULL", "g.deleted_at IS NULL"]
    params: dict[str, object] = {}

    if member_id:
        try:
            params["member_filter"] = str(uuid.UUID(member_id))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid member_id") from exc
        where_parts.append("g.member_id = :member_filter")
    if status:
        where_parts.append("LOWER(g.status) = :status_filter")
        params["status_filter"] = status.lower()
    if stage:
        where_parts.append("LOWER(g.stage) = :stage_filter")
        params["stage_filter"] = stage.lower()
    if overdue:
        where_parts.append(
            "LOWER(g.status) = 'active' AND g.target_date IS NOT NULL AND g.target_date < NOW()"
        )
    if search:
        where_parts.append("LOWER(g.goal_text) LIKE :search")
        params["search"] = f"%{search.lower()}%"

    where_sql = " AND ".join(where_parts)

    total = _int((await session.execute(
        text(f"SELECT COUNT(*) FROM goals g WHERE {where_sql}"),  # noqa: S608
        params,
    )).scalar())

    params["limit"] = per_page
    params["offset"] = (page - 1) * per_page
    rows = (await session.execute(
        text(
            f"""
            SELECT g.id::text AS id, g.member_id::text AS member_id, m.name AS member_name,
                   g.goal_text, g.status, g.stage, g.target_date, g.created_at,
                   (LOWER(g.status) = 'active' AND g.target_date IS NOT NULL AND g.target_date < NOW()) AS overdue
            FROM goals g
            LEFT JOIN members m ON m.id = g.member_id
            WHERE {where_sql}
            ORDER BY g.{sort_by} {sort_dir} NULLS LAST
            LIMIT :limit OFFSET :offset
            """  # noqa: S608 — sort_by/sort_dir whitelisted, where_sql parametrised
        ),
        params,
    )).mappings().all()

    goals = [
        GoalRecord(
            id=r["id"],
            member_id=r["member_id"],
            member_name=r["member_name"],
            goal_text=r["goal_text"],
            status=r["status"],
            stage=r["stage"],
            targetDate=r["target_date"].isoformat() if r["target_date"] else None,
            created_at=r["created_at"].isoformat() if r["created_at"] else None,
            overdue=bool(r["overdue"]),
        )
        for r in rows
    ]
    return GoalListResponse(goals=goals, total=total, page=page, per_page=per_page)


# ---------------------------------------------------------------------------
# GET /goals/stats
# ---------------------------------------------------------------------------


@router.get("/goals/stats", response_model=GoalStatsResponse)
async def get_goals_stats(
    session: AsyncSession = Depends(get_session),
) -> GoalStatsResponse:
    data = await compute_goal_stats(session)
    return GoalStatsResponse(
        kpis=GoalKpiResponse(**data["kpis"]),
        goal_funnel=[GoalFunnelStage(**g) for g in data["goal_funnel"]],
        status_breakdown=[StatusBreakdownItem(**s) for s in data["status_breakdown"]],
    )


# ---------------------------------------------------------------------------
# POST /goals
# ---------------------------------------------------------------------------


@router.post("/goals", response_model=GoalDetailResponse, status_code=201)
async def create_goal(
    body: CreateGoalRequest,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> GoalDetailResponse:
    """Create a goal for a member."""
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

    goal_text = body.goal_text.strip()
    if not goal_text:
        raise HTTPException(status_code=400, detail="goal_text is required")
    status = (body.status or "active").strip().lower()
    stage = (body.stage or "todo").strip().lower()
    target_date = _parse_dt(body.target_date)
    goal_id = uuid.uuid4()
    actor_id = _coerce_author_uuid(current_user.id)

    r = (await session.execute(
        text(
            """
            INSERT INTO goals (id, member_id, goal_text, target_date, status, stage)
            VALUES (:id, :member_id, :goal_text, :target_date, :status, :stage)
            RETURNING id::text AS id, member_id::text AS member_id, goal_text, status, stage,
                      target_date, created_at,
                      (LOWER(status) = 'active' AND target_date IS NOT NULL AND target_date < NOW()) AS overdue
            """
        ),
        {
            "id": str(goal_id),
            "member_id": str(member_uuid),
            "goal_text": goal_text,
            "target_date": target_date,
            "status": status,
            "stage": stage,
        },
    )).mappings().one()

    member_name = (await session.execute(
        text("SELECT name FROM members WHERE id = :id"), {"id": r["member_id"]}
    )).scalar_one_or_none()

    await record_event(
        session, user_id=actor_id, action="goal.created",
        table_name="goals", record_id=r["id"],
        after={"member_id": r["member_id"], "goal_text": goal_text, "status": status, "stage": stage},
    )
    await session.commit()

    return GoalDetailResponse(
        id=r["id"], member_id=r["member_id"], member_name=member_name,
        goal_text=r["goal_text"], status=r["status"], stage=r["stage"],
        target_date=r["target_date"].isoformat() if r["target_date"] else None,
        created_at=r["created_at"].isoformat() if r["created_at"] else None,
        overdue=bool(r["overdue"]),
    )


# ---------------------------------------------------------------------------
# GET /goals/{id}
# ---------------------------------------------------------------------------


@router.get("/goals/{goal_id}", response_model=GoalDetailResponse)
async def get_goal_detail(
    goal_id: str,
    session: AsyncSession = Depends(get_session),
) -> GoalDetailResponse:
    uid = _parse_goal_uuid(goal_id)
    r = (await session.execute(
        text(
            """
            SELECT g.id::text AS id, g.member_id::text AS member_id, m.name AS member_name,
                   g.goal_text, g.status, g.stage, g.target_date, g.created_at,
                   (LOWER(g.status) = 'active' AND g.target_date IS NOT NULL AND g.target_date < NOW()) AS overdue
            FROM goals g
            LEFT JOIN members m ON m.id = g.member_id
            WHERE g.id = :id AND g.deleted_at IS NULL
            """
        ),
        {"id": str(uid)},
    )).mappings().one_or_none()
    if r is None:
        raise HTTPException(status_code=404, detail="Goal not found")
    return GoalDetailResponse(
        id=r["id"], member_id=r["member_id"], member_name=r["member_name"],
        goal_text=r["goal_text"], status=r["status"], stage=r["stage"],
        target_date=r["target_date"].isoformat() if r["target_date"] else None,
        created_at=r["created_at"].isoformat() if r["created_at"] else None,
        overdue=bool(r["overdue"]),
    )


# ---------------------------------------------------------------------------
# GET /goals/{id}/history
# ---------------------------------------------------------------------------


@router.get("/goals/{goal_id}/history", response_model=GoalHistoryResponse)
async def get_goal_history(
    goal_id: str,
    session: AsyncSession = Depends(get_session),
) -> GoalHistoryResponse:
    uid = _parse_goal_uuid(goal_id)
    exists = (await session.execute(
        text("SELECT 1 FROM goals WHERE id = :id AND deleted_at IS NULL"),
        {"id": str(uid)},
    )).scalar_one_or_none()
    if exists is None:
        raise HTTPException(status_code=404, detail="Goal not found")

    rows = (await session.execute(
        text(
            """
            SELECT al.id::text AS id, al.action,
                   al.before_value AS before, al.after_value AS after,
                   al.user_id::text AS author_id, u.email AS author_email,
                   al.created_at
            FROM audit_log al
            LEFT JOIN users u ON u.id = al.user_id
            WHERE al.table_name = 'goals' AND al.record_id = :record_id
            ORDER BY al.created_at DESC
            """
        ),
        {"record_id": str(uid)},
    )).mappings().all()

    return GoalHistoryResponse(events=[
        GoalHistoryEvent(
            id=r["id"], action=r["action"], before=r["before"], after=r["after"],
            author_id=r["author_id"], author_email=r["author_email"],
            created_at=r["created_at"].isoformat(),
        )
        for r in rows
    ])


# ---------------------------------------------------------------------------
# PATCH /goals/{id}
# ---------------------------------------------------------------------------


@router.patch("/goals/{goal_id}", response_model=GoalDetailResponse)
async def update_goal(
    goal_id: str,
    body: UpdateGoalRequest,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> GoalDetailResponse:
    """Update a goal (goal_text / status / target_date). Completing = status='completed'."""
    uid = _parse_goal_uuid(goal_id)
    updates = {k: v for k, v in body.model_dump(exclude_unset=True).items() if k in _PATCH_FIELDS}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    before = (await session.execute(
        text("SELECT goal_text, status, stage, target_date FROM goals WHERE id = :id AND deleted_at IS NULL"),
        {"id": str(uid)},
    )).mappings().one_or_none()
    if before is None:
        raise HTTPException(status_code=404, detail="Goal not found")

    set_parts: list[str] = []
    params: dict[str, object] = {"id": str(uid)}
    if "goal_text" in updates:
        set_parts.append("goal_text = :goal_text")
        params["goal_text"] = updates["goal_text"]
    if "status" in updates:
        set_parts.append("status = :status")
        params["status"] = (updates["status"] or "").strip().lower()
    if "stage" in updates:
        set_parts.append("stage = :stage")
        params["stage"] = (updates["stage"] or "").strip().lower() or None
    if "target_date" in updates:
        set_parts.append("target_date = :target_date")
        params["target_date"] = _parse_dt(updates["target_date"])

    r = (await session.execute(
        text(
            f"""
            UPDATE goals SET {', '.join(set_parts)}
            WHERE id = :id AND deleted_at IS NULL
            RETURNING id::text AS id, member_id::text AS member_id, goal_text, status, stage,
                      target_date, created_at,
                      (LOWER(status) = 'active' AND target_date IS NOT NULL AND target_date < NOW()) AS overdue
            """  # noqa: S608 — set_parts keys whitelisted via _PATCH_FIELDS
        ),
        params,
    )).mappings().one()

    actor_id = _coerce_author_uuid(current_user.id)
    new_status = params.get("status")
    if new_status is not None and new_status != before["status"]:
        await record_event(
            session, user_id=actor_id, action="goal.status_changed",
            table_name="goals", record_id=str(uid),
            before={"status": before["status"]}, after={"status": new_status},
        )
    if "stage" in params and params["stage"] != before["stage"]:
        await record_event(
            session, user_id=actor_id, action="goal.stage_changed",
            table_name="goals", record_id=str(uid),
            before={"stage": before["stage"]}, after={"stage": params["stage"]},
        )
    if "target_date" in params and params["target_date"] != before["target_date"]:
        await record_event(
            session, user_id=actor_id, action="goal.target_date_changed",
            table_name="goals", record_id=str(uid),
            before={"target_date": before["target_date"].isoformat() if before["target_date"] else None},
            after={"target_date": params["target_date"].isoformat() if params["target_date"] else None},
        )
    if "goal_text" in updates and updates["goal_text"] != before["goal_text"]:
        await record_event(
            session, user_id=actor_id, action="goal.text_changed",
            table_name="goals", record_id=str(uid),
            before={"goal_text": before["goal_text"]}, after={"goal_text": updates["goal_text"]},
        )

    member_name = (await session.execute(
        text("SELECT name FROM members WHERE id = :id"), {"id": r["member_id"]}
    )).scalar_one_or_none()
    await session.commit()

    return GoalDetailResponse(
        id=r["id"], member_id=r["member_id"], member_name=member_name,
        goal_text=r["goal_text"], status=r["status"], stage=r["stage"],
        target_date=r["target_date"].isoformat() if r["target_date"] else None,
        created_at=r["created_at"].isoformat() if r["created_at"] else None,
        overdue=bool(r["overdue"]),
    )


# ---------------------------------------------------------------------------
# DELETE /goals/{id} — soft-delete
# ---------------------------------------------------------------------------


@router.delete("/goals/{goal_id}", status_code=204)
async def delete_goal(
    goal_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> Response:
    """Soft-delete a goal (sets deleted_at)."""
    uid = _parse_goal_uuid(goal_id)
    r = (await session.execute(
        text(
            """
            UPDATE goals SET deleted_at = NOW()
            WHERE id = :id AND deleted_at IS NULL
            RETURNING goal_text
            """
        ),
        {"id": str(uid)},
    )).mappings().one_or_none()
    if r is None:
        raise HTTPException(status_code=404, detail="Goal not found")

    await record_event(
        session, user_id=_coerce_author_uuid(current_user.id), action="goal.deleted",
        table_name="goals", record_id=str(uid),
        before={"goal_text": (r["goal_text"] or "")[:120]},
    )
    await session.commit()
    return Response(status_code=204)
