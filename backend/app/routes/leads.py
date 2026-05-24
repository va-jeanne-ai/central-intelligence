"""
Leads endpoints.

GET /api/v1/leads         — paginated lead list with optional filters
GET /api/v1/leads/stats   — KPIs, lead-volume chart, source breakdown, funnel

All queries use raw SQL via sqlalchemy.text() with the AsyncSession dependency,
following the same pattern as dashboard.py.

Status mapping (DB → API)
--------------------------
  appointment-set  →  appointment_set
  sale             →  closed_won
  lost             →  closed_lost
  new / contacted / qualified / stale  →  unchanged

Score mapping (derived from mapped API status)
----------------------------------------------
  new             → 20
  contacted       → 40
  qualified       → 60
  appointment_set → 70
  closed_won      → 95
  closed_lost     → 10
  stale           →  5
  (unknown)       →  0

Column reference — leads table
-------------------------------
  id (uuid), name, email, phone, status, source, notes, created_at, deleted_at
"""

import logging
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser, get_current_user
from app.database import get_session
from app.schemas.leads import (
    CreateNoteRequest,
    FunnelStage,
    LeadCallSummary,
    LeadDetailResponse,
    LeadGoalSummary,
    LeadHistoryEvent,
    LeadHistoryResponse,
    LeadListResponse,
    LeadObjectionSummary,
    LeadPainPointSummary,
    LeadRecord,
    LeadsKpiResponse,
    LeadsStatsResponse,
    LeadVolumePoint,
    NoteRow,
    SourceBreakdownItem,
    UpdateLeadRequest,
)
from app.services.audit import record_event

logger = logging.getLogger(__name__)

router = APIRouter(tags=["leads"])

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Maps database status values to the API / frontend vocabulary.
_DB_TO_API_STATUS: dict[str, str] = {
    "appointment-set": "appointment_set",
    "sale": "closed_won",
    "lost": "closed_lost",
    # Pass-through statuses (listed explicitly for clarity)
    "new": "new",
    "contacted": "contacted",
    "qualified": "qualified",
    "stale": "stale",
}

# Score assigned per mapped API status.
_STATUS_SCORE: dict[str, int] = {
    "new": 20,
    "contacted": 40,
    "qualified": 60,
    "appointment_set": 70,
    "closed_won": 95,
    "closed_lost": 10,
    "stale": 5,
}

# Columns that are safe to use in ORDER BY (whitelist to prevent injection).
_SORTABLE_COLUMNS: frozenset[str] = frozenset(
    {"created_at", "name", "email", "status", "source"}
)

# Allowed sort directions.
_SORT_DIRS: frozenset[str] = frozenset({"asc", "desc"})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _int(value: object) -> int:
    """Return value as int, falling back to 0 for None or non-numeric values."""
    try:
        return int(value) if value is not None else 0
    except (TypeError, ValueError):
        return 0


def _float(value: object) -> float:
    """Return value as float, falling back to 0.0 for None or non-numeric values."""
    try:
        return float(value) if value is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def _map_status(db_status: str | None) -> str | None:
    """Convert a raw DB status to the API vocabulary."""
    if db_status is None:
        return None
    return _DB_TO_API_STATUS.get(db_status.lower(), db_status.lower())


def _score_for_status(api_status: str | None) -> int:
    """Return the deterministic lead score for a mapped API status."""
    if api_status is None:
        return 0
    return _STATUS_SCORE.get(api_status, 0)


def _week_label(weeks_ago: int) -> str:
    """Return a compact week label.

    weeks_ago=7 → 'Wk 1' (oldest), weeks_ago=0 → 'Now' (current).
    """
    if weeks_ago == 0:
        return "Now"
    return f"Wk {8 - weeks_ago}"


# ---------------------------------------------------------------------------
# DB-status filter helpers
# ---------------------------------------------------------------------------
# When the caller supplies a frontend-vocabulary status filter we must
# translate it back to all possible DB values before building the SQL.

_API_TO_DB_STATUSES: dict[str, list[str]] = {
    "appointment_set": ["appointment-set"],
    "closed_won": ["sale"],
    "closed_lost": ["lost"],
    "new": ["new"],
    "contacted": ["contacted"],
    "qualified": ["qualified"],
    "stale": ["stale"],
}


# ---------------------------------------------------------------------------
# Endpoint: GET /api/v1/leads
# ---------------------------------------------------------------------------


@router.get(
    "/leads",
    response_model=LeadListResponse,
    summary="Paginated lead list",
    description=(
        "Returns a paginated, filterable list of leads. "
        "Status values in the response use the API vocabulary "
        "(appointment_set, closed_won, closed_lost) regardless of how they "
        "are stored in the database."
    ),
)
async def list_leads(
    status: str | None = Query(default=None, description="Filter by API status"),
    source: str | None = Query(default=None, description="Filter by source"),
    search: str | None = Query(default=None, description="Search name or email"),
    page: int = Query(default=1, ge=1, description="Page number (1-based)"),
    per_page: int = Query(default=50, ge=1, le=200, description="Results per page"),
    sort_by: str = Query(default="created_at", description="Column to sort by"),
    sort_dir: Literal["asc", "desc"] = Query(default="desc", description="Sort direction"),
    session: AsyncSession = Depends(get_session),
) -> LeadListResponse:
    """Return a paginated list of leads with optional filtering and sorting."""

    # ---- Validate / sanitise sort parameters (prevent SQL injection) -------
    if sort_by not in _SORTABLE_COLUMNS:
        sort_by = "created_at"
    if sort_dir not in _SORT_DIRS:
        sort_dir = "desc"

    # ---- Build WHERE clauses ------------------------------------------------
    where_parts: list[str] = ["deleted_at IS NULL"]
    params: dict[str, object] = {}

    if status:
        db_statuses = _API_TO_DB_STATUSES.get(status.lower())
        if db_statuses:
            if len(db_statuses) == 1:
                where_parts.append("LOWER(status) = :status_filter")
                params["status_filter"] = db_statuses[0]
            else:
                placeholders = ", ".join(
                    f":status_{i}" for i in range(len(db_statuses))
                )
                where_parts.append(f"LOWER(status) IN ({placeholders})")
                for i, s in enumerate(db_statuses):
                    params[f"status_{i}"] = s
        else:
            # Unknown status — return empty result set.
            where_parts.append("1 = 0")

    if source:
        where_parts.append("LOWER(source) = :source_filter")
        params["source_filter"] = source.lower()

    if search:
        where_parts.append(
            "(LOWER(name) LIKE :search_pattern OR LOWER(email) LIKE :search_pattern)"
        )
        params["search_pattern"] = f"%{search.lower()}%"

    where_sql = " AND ".join(where_parts)

    # ---- COUNT total matching rows ------------------------------------------
    count_sql = text(f"SELECT COUNT(*) FROM leads WHERE {where_sql}")  # noqa: S608
    row = await session.execute(count_sql, params)
    total: int = _int(row.scalar())

    # ---- Fetch page ---------------------------------------------------------
    offset = (page - 1) * per_page
    params["limit"] = per_page
    params["offset"] = offset

    data_sql = text(
        f"""
        SELECT
            id::text,
            name,
            email,
            phone,
            status,
            source,
            created_at
        FROM leads
        WHERE {where_sql}
        ORDER BY {sort_by} {sort_dir}
        LIMIT :limit OFFSET :offset
        """  # noqa: S608
    )
    rows = (await session.execute(data_sql, params)).fetchall()

    # ---- Map rows to response models ----------------------------------------
    leads: list[LeadRecord] = []
    for r in rows:
        raw_id, name, email, phone, raw_status, source_val, created_at = r
        api_status = _map_status(raw_status)
        score = _score_for_status(api_status)
        leads.append(
            LeadRecord(
                id=str(raw_id),
                name=name,
                email=email,
                phone=phone,
                status=api_status,
                source=source_val,
                notes=None,
                createdAt=created_at.isoformat() if created_at is not None else None,
                score=score,
            )
        )

    logger.debug(
        "list_leads — total=%d page=%d per_page=%d returned=%d",
        total,
        page,
        per_page,
        len(leads),
    )

    return LeadListResponse(leads=leads, total=total, page=page, per_page=per_page)


# ---------------------------------------------------------------------------
# Endpoint: GET /api/v1/leads/stats
# ---------------------------------------------------------------------------


@router.get(
    "/leads/stats",
    response_model=LeadsStatsResponse,
    summary="Lead KPIs, volume chart, source breakdown, and funnel",
    description=(
        "Aggregates lead data from the database into four sections: "
        "top-level KPIs, an 8-week volume series, source distribution, "
        "and a four-stage sales funnel."
    ),
)
async def get_leads_stats(
    session: AsyncSession = Depends(get_session),
) -> LeadsStatsResponse:
    """Compute and return aggregated lead statistics."""

    # ---- 1. Total leads (non-deleted) ---------------------------------------
    row = await session.execute(
        text("SELECT COUNT(*) FROM leads WHERE deleted_at IS NULL")
    )
    total_leads: int = _int(row.scalar())

    # ---- 2. Leads created in the last 7 days --------------------------------
    row = await session.execute(
        text(
            "SELECT COUNT(*) FROM leads "
            "WHERE deleted_at IS NULL "
            "  AND created_at >= NOW() - INTERVAL '7 days'"
        )
    )
    leads_this_week: int = _int(row.scalar())

    # ---- 3. Conversion rate — status 'sale' in DB ---------------------------
    row = await session.execute(
        text(
            "SELECT COUNT(*) FROM leads "
            "WHERE deleted_at IS NULL "
            "  AND LOWER(status) = 'sale'"
        )
    )
    sold_count: int = _int(row.scalar())

    conversion_rate: float = 0.0
    if total_leads > 0:
        conversion_rate = round((sold_count / total_leads) * 100, 2)

    # ---- 4. Active applications — qualified + appointment-set ---------------
    row = await session.execute(
        text(
            "SELECT COUNT(*) FROM leads "
            "WHERE deleted_at IS NULL "
            "  AND LOWER(status) IN ('qualified', 'appointment-set')"
        )
    )
    active_applications: int = _int(row.scalar())

    kpis = LeadsKpiResponse(
        total_leads=total_leads,
        leads_this_week=leads_this_week,
        conversion_rate=conversion_rate,
        active_applications=active_applications,
    )

    # ---- 5. Lead volume — last 8 calendar weeks -----------------------------
    row = await session.execute(
        text(
            """
            SELECT
                FLOOR(EXTRACT(EPOCH FROM (NOW() - created_at)) / 604800)::int AS weeks_ago,
                COUNT(*) AS cnt
            FROM leads
            WHERE deleted_at IS NULL
              AND created_at >= NOW() - INTERVAL '8 weeks'
            GROUP BY weeks_ago
            ORDER BY weeks_ago DESC
            """
        )
    )
    volume_map: dict[int, int] = {r[0]: _int(r[1]) for r in row.fetchall()}

    lead_volume: list[LeadVolumePoint] = [
        LeadVolumePoint(
            label=_week_label(w),
            value=volume_map.get(w, 0),
        )
        for w in range(7, -1, -1)  # oldest (Wk 1) → newest (Now)
    ]

    # ---- 6. Source breakdown ------------------------------------------------
    row = await session.execute(
        text(
            """
            SELECT
                COALESCE(LOWER(source), 'other') AS src,
                COUNT(*) AS cnt
            FROM leads
            WHERE deleted_at IS NULL
            GROUP BY src
            ORDER BY cnt DESC
            """
        )
    )
    source_rows = row.fetchall()

    source_total: int = sum(_int(r[1]) for r in source_rows)
    source_breakdown: list[SourceBreakdownItem] = []
    for r in source_rows:
        src, cnt = r[0], _int(r[1])
        pct = round((cnt / source_total * 100), 1) if source_total > 0 else 0.0
        source_breakdown.append(
            SourceBreakdownItem(source=src, count=cnt, percentage=pct)
        )

    # ---- 7. Sales funnel ----------------------------------------------------
    # Four stages, each counting a progressively narrower group of statuses:
    #   Leads        — all non-deleted
    #   Appointments — appointment-set
    #   Applications — qualified + appointment-set  (everyone who qualified)
    #   Sales        — sale (closed_won in API vocabulary)

    row = await session.execute(
        text(
            """
            SELECT
                SUM(CASE WHEN deleted_at IS NULL THEN 1 ELSE 0 END)                        AS all_leads,
                SUM(CASE WHEN deleted_at IS NULL AND LOWER(status) = 'appointment-set'
                         THEN 1 ELSE 0 END)                                                 AS appointments,
                SUM(CASE WHEN deleted_at IS NULL AND LOWER(status) IN ('qualified', 'appointment-set')
                         THEN 1 ELSE 0 END)                                                 AS applications,
                SUM(CASE WHEN deleted_at IS NULL AND LOWER(status) = 'sale'
                         THEN 1 ELSE 0 END)                                                 AS sales
            FROM leads
            """
        )
    )
    funnel_row = row.fetchone()
    f_all = _int(funnel_row[0]) if funnel_row else 0
    f_appts = _int(funnel_row[1]) if funnel_row else 0
    f_apps = _int(funnel_row[2]) if funnel_row else 0
    f_sales = _int(funnel_row[3]) if funnel_row else 0

    def _funnel_pct(count: int, base: int) -> float:
        if base == 0:
            return 0.0
        return round(count / base * 100, 1)

    funnel: list[FunnelStage] = [
        FunnelStage(
            stage="Leads",
            count=f_all,
            percentage=100.0,
        ),
        FunnelStage(
            stage="Appointments",
            count=f_appts,
            percentage=_funnel_pct(f_appts, f_all),
        ),
        FunnelStage(
            stage="Applications",
            count=f_apps,
            percentage=_funnel_pct(f_apps, f_all),
        ),
        FunnelStage(
            stage="Sales",
            count=f_sales,
            percentage=_funnel_pct(f_sales, f_all),
        ),
    ]

    logger.debug(
        "get_leads_stats — total=%d this_week=%d conversion=%.2f%% active_apps=%d",
        total_leads,
        leads_this_week,
        conversion_rate,
        active_applications,
    )

    return LeadsStatsResponse(
        kpis=kpis,
        lead_volume=lead_volume,
        source_breakdown=source_breakdown,
        funnel=funnel,
    )


# ===========================================================================
# Lead detail — GET /api/v1/leads/{id}
# ===========================================================================


def _parse_lead_uuid(lead_id: str) -> uuid.UUID:
    """Coerce the path param to UUID, 404 on garbage."""
    try:
        return uuid.UUID(lead_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Lead not found") from exc


@router.get("/leads/{lead_id}", response_model=LeadDetailResponse)
async def get_lead_detail(
    lead_id: str,
    session: AsyncSession = Depends(get_session),
) -> LeadDetailResponse:
    """Return the full lead record plus FK-linked summaries + staff notes.

    Uses raw SQL throughout to stay consistent with the list endpoint and
    to explicitly project ``notes`` (the immutable upstream provider
    payload — used by the frontend to render the "Initial Submission"
    card). The eager-loaded ORM relationships on ``Lead`` would also
    work but mixing styles here would be noisier.
    """
    uid = _parse_lead_uuid(lead_id)

    # 1. Lead row
    lead_row = (await session.execute(
        text("""
            SELECT id::text AS id, name, email, phone, status, source,
                   notes, external_id, created_at
            FROM leads
            WHERE id = :id AND deleted_at IS NULL
        """),
        {"id": str(uid)},
    )).mappings().one_or_none()

    if lead_row is None:
        raise HTTPException(status_code=404, detail="Lead not found")

    api_status = _map_status(lead_row["status"])
    score = _score_for_status(api_status)

    # 2. Calls (with insight count via correlated subquery).
    # processed_date stays NULL until the analyzer finishes — the frontend
    # uses it to show an "in-progress" row variant + drive its poller.
    # ORDER BY puts newest first; pending calls land at the top because
    # their created_at is the most recent.
    calls_rows = (await session.execute(
        text("""
            SELECT c.id AS id,
                   c.date AS date,
                   c.call_type AS call_type,
                   c.processed_date AS processed_date,
                   COALESCE((
                       SELECT COUNT(*) FROM insights i
                       WHERE i.call_id = c.id
                   ), 0) AS insights_count
            FROM calls c
            WHERE c.lead_id = :id AND c.deleted_at IS NULL
            ORDER BY c.date DESC NULLS LAST, c.created_at DESC
        """),
        {"id": str(uid)},
    )).mappings().all()

    # 3. Goals
    goals_rows = (await session.execute(
        text("""
            SELECT id::text AS id, goal_text, status, target_date
            FROM goals
            WHERE lead_id = :id AND deleted_at IS NULL
            ORDER BY created_at DESC
        """),
        {"id": str(uid)},
    )).mappings().all()

    # 4. Pain points (column is named `text` — quote for safety)
    pain_rows = (await session.execute(
        text("""
            SELECT id::text AS id, "text" AS text, category
            FROM pain_points
            WHERE lead_id = :id AND deleted_at IS NULL
            ORDER BY created_at DESC
        """),
        {"id": str(uid)},
    )).mappings().all()

    # 5. Objections
    obj_rows = (await session.execute(
        text("""
            SELECT id::text AS id, objection_text, resolution_offered
            FROM objections
            WHERE lead_id = :id AND deleted_at IS NULL
            ORDER BY created_at DESC
        """),
        {"id": str(uid)},
    )).mappings().all()

    # 6. Staff notes joined to users for author_email
    notes_rows = (await session.execute(
        text("""
            SELECT ln.id::text AS id,
                   ln.body,
                   ln.author_id::text AS author_id,
                   u.email AS author_email,
                   ln.created_at
            FROM lead_notes ln
            LEFT JOIN users u ON u.id = ln.author_id
            WHERE ln.lead_id = :id
            ORDER BY ln.created_at DESC
        """),
        {"id": str(uid)},
    )).mappings().all()

    return LeadDetailResponse(
        id=lead_row["id"],
        name=lead_row["name"],
        email=lead_row["email"],
        phone=lead_row["phone"],
        status=api_status,
        source=lead_row["source"],
        score=score,
        external_id=lead_row["external_id"],
        created_at=lead_row["created_at"].isoformat() if lead_row["created_at"] else None,
        notes_raw=lead_row["notes"],
        calls=[
            LeadCallSummary(
                id=str(r["id"]),
                date=r["date"].isoformat() if r["date"] else None,
                call_type=r["call_type"],
                insights_count=int(r["insights_count"] or 0),
                processed_date=r["processed_date"].isoformat() if r["processed_date"] else None,
            )
            for r in calls_rows
        ],
        goals=[
            LeadGoalSummary(
                id=r["id"],
                goal_text=r["goal_text"],
                status=r["status"],
                target_date=r["target_date"].isoformat() if r["target_date"] else None,
            )
            for r in goals_rows
        ],
        pain_points=[
            LeadPainPointSummary(
                id=r["id"], text=r["text"], category=r["category"],
            )
            for r in pain_rows
        ],
        objections=[
            LeadObjectionSummary(
                id=r["id"],
                objection_text=r["objection_text"],
                resolution_offered=r["resolution_offered"],
            )
            for r in obj_rows
        ],
        staff_notes=[
            NoteRow(
                id=r["id"],
                body=r["body"],
                author_id=r["author_id"],
                author_email=r["author_email"],
                created_at=r["created_at"].isoformat(),
            )
            for r in notes_rows
        ],
    )


# ===========================================================================
# Lead history — GET /api/v1/leads/{id}/history
# ===========================================================================


@router.get("/leads/{lead_id}/history", response_model=LeadHistoryResponse)
async def get_lead_history(
    lead_id: str,
    session: AsyncSession = Depends(get_session),
) -> LeadHistoryResponse:
    """Return the audit-log timeline for one lead, newest first.

    Always appends a synthetic ``lead.created`` event derived from
    ``leads.created_at`` / ``leads.created_by`` as the oldest entry —
    pre-existing leads (whose audit rows were never written) still get a
    "Created" anchor on the UI.
    """
    uid = _parse_lead_uuid(lead_id)

    # Confirm the lead exists; also pull created_at / created_by / source
    # for the synthetic Created event.
    lead_row = (await session.execute(
        text("""
            SELECT created_at, created_by, source
            FROM leads
            WHERE id = :id AND deleted_at IS NULL
        """),
        {"id": str(uid)},
    )).mappings().one_or_none()
    if lead_row is None:
        raise HTTPException(status_code=404, detail="Lead not found")

    # Audit rows, newest first. Index ix_audit_log_record_lookup makes
    # this a single backward index scan.
    audit_rows = (await session.execute(
        text("""
            SELECT al.id::text AS id,
                   al.action,
                   al.before_value AS before,
                   al.after_value AS after,
                   al.user_id::text AS author_id,
                   u.email AS author_email,
                   al.created_at
            FROM audit_log al
            LEFT JOIN users u ON u.id = al.user_id
            WHERE al.table_name = 'leads' AND al.record_id = :record_id
            ORDER BY al.created_at DESC
        """),
        {"record_id": str(uid)},
    )).mappings().all()

    events: list[LeadHistoryEvent] = [
        LeadHistoryEvent(
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

    # Synthetic Created event — appended as the oldest. If the GHL
    # webhook path ever starts emitting a real lead.created audit row
    # for new leads, that row will already be in `events` above and the
    # synthetic one will sit beneath it; the frontend can show both or
    # filter — for now we always emit it as a reliable anchor.
    if lead_row["created_at"]:
        # Look up the author_email for created_by if present.
        created_email: str | None = None
        if lead_row["created_by"]:
            email_row = (await session.execute(
                text("SELECT email FROM users WHERE id = :id"),
                {"id": str(lead_row["created_by"])},
            )).scalar_one_or_none()
            created_email = email_row
        events.append(
            LeadHistoryEvent(
                id="synthetic-created",
                action="lead.created",
                before=None,
                after={"source": lead_row["source"]} if lead_row["source"] else None,
                author_id=str(lead_row["created_by"]) if lead_row["created_by"] else None,
                author_email=created_email,
                created_at=lead_row["created_at"].isoformat(),
            )
        )

    return LeadHistoryResponse(events=events)


# ===========================================================================
# Lead partial update — PATCH /api/v1/leads/{id}
# ===========================================================================


@router.patch("/leads/{lead_id}", response_model=LeadRecord)
async def update_lead(
    lead_id: str,
    body: UpdateLeadRequest,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> LeadRecord:
    """Partial-update a lead row (name / status / phone).

    Uses ``model_dump(exclude_unset=True)`` so absent fields stay
    untouched. Status arrives in API vocabulary ("appointment_set") and
    is translated to the DB form ("appointment-set") via
    ``_API_TO_DB_STATUSES``. None of the current API statuses map to
    multiple DB values, but we assert that defensively.

    Emits one ``lead.<field>_changed`` audit event per field that actually
    changed value (no-op updates produce no events). Audit rows share the
    UPDATE's transaction — a rollback drops them too.
    """
    uid = _parse_lead_uuid(lead_id)

    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    # Translate status if present.
    db_status_override: str | None = None
    api_status_after: str | None = None
    if "status" in updates:
        api_status_after = (updates.pop("status") or "").lower()
        db_statuses = _API_TO_DB_STATUSES.get(api_status_after)
        if not db_statuses:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown status: {api_status_after!r}",
            )
        if len(db_statuses) != 1:
            # Defensive — would mean the map gained a 1→many entry we
            # haven't designed for. Fail loudly so we notice.
            raise HTTPException(
                status_code=400,
                detail=f"Ambiguous status mapping for {api_status_after!r}",
            )
        db_status_override = db_statuses[0]

    # Read pre-update state so audit can record the before-value for any
    # field that actually changes. One extra SELECT, fine at this scale.
    before_row = (await session.execute(
        text("""
            SELECT name, phone, status
            FROM leads
            WHERE id = :id AND deleted_at IS NULL
        """),
        {"id": str(uid)},
    )).mappings().one_or_none()
    if before_row is None:
        raise HTTPException(status_code=404, detail="Lead not found")

    set_parts: list[str] = []
    params: dict[str, object] = {"id": str(uid)}
    if "name" in updates:
        set_parts.append("name = :name")
        params["name"] = updates["name"]
    if "phone" in updates:
        set_parts.append("phone = :phone")
        params["phone"] = updates["phone"]
    if db_status_override is not None:
        set_parts.append("status = :status")
        params["status"] = db_status_override

    if not set_parts:
        # Could happen if the only field provided was an empty status that
        # didn't translate. Defensive — should be unreachable given checks above.
        raise HTTPException(status_code=400, detail="No fields to update")

    sql = f"""
        UPDATE leads
        SET {', '.join(set_parts)}
        WHERE id = :id AND deleted_at IS NULL
        RETURNING id::text AS id, name, email, phone, status, source, created_at
    """  # noqa: S608 — set_parts is whitelisted above

    row = (await session.execute(text(sql), params)).mappings().one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Lead not found")

    # Emit audit events for fields that actually changed.
    actor_id = _coerce_author_uuid(current_user.id)
    if "name" in updates and updates["name"] != before_row["name"]:
        await record_event(
            session,
            user_id=actor_id,
            action="lead.name_changed",
            table_name="leads",
            record_id=str(uid),
            before={"name": before_row["name"]},
            after={"name": updates["name"]},
        )
    if "phone" in updates and updates["phone"] != before_row["phone"]:
        await record_event(
            session,
            user_id=actor_id,
            action="lead.phone_changed",
            table_name="leads",
            record_id=str(uid),
            before={"phone": before_row["phone"]},
            after={"phone": updates["phone"]},
        )
    if db_status_override is not None and db_status_override != before_row["status"]:
        await record_event(
            session,
            user_id=actor_id,
            action="lead.status_changed",
            table_name="leads",
            record_id=str(uid),
            # Store the API form so the frontend doesn't need to translate.
            before={"status": _map_status(before_row["status"])},
            after={"status": api_status_after},
        )

    await session.commit()

    api_status = _map_status(row["status"])
    return LeadRecord(
        id=row["id"],
        name=row["name"],
        email=row["email"],
        phone=row["phone"],
        status=api_status or "new",
        source=row["source"] or "other",
        score=_score_for_status(api_status),
        createdAt=row["created_at"].isoformat() if row["created_at"] else "",
        notes=None,
    )


# ===========================================================================
# Staff notes — POST + DELETE
# ===========================================================================


def _coerce_author_uuid(user_id: str | uuid.UUID | None) -> uuid.UUID | None:
    """Best-effort UUID coercion for the CurrentUser id.

    Mock-mode returns the literal string ``"mock-user-id"`` which isn't
    a UUID; fall back to None so the note still saves (author_email comes
    from CurrentUser separately).
    """
    if user_id is None:
        return None
    if isinstance(user_id, uuid.UUID):
        return user_id
    try:
        return uuid.UUID(str(user_id))
    except ValueError:
        return None


@router.post("/leads/{lead_id}/notes", response_model=NoteRow, status_code=201)
async def create_lead_note(
    lead_id: str,
    body: CreateNoteRequest,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> NoteRow:
    """Append a staff journal note to a lead. Author is the calling user."""
    uid = _parse_lead_uuid(lead_id)

    # Verify the lead exists (and isn't soft-deleted) before inserting.
    exists = (await session.execute(
        text("SELECT 1 FROM leads WHERE id = :id AND deleted_at IS NULL"),
        {"id": str(uid)},
    )).scalar_one_or_none()
    if exists is None:
        raise HTTPException(status_code=404, detail="Lead not found")

    note_id = uuid.uuid4()
    author_uuid = _coerce_author_uuid(current_user.id)

    # Only attach author_id if the user actually exists in the local
    # users table. Supabase auth users aren't auto-synced — when the
    # JWT carries a sub that we haven't seen yet (and on mock-mode),
    # the FK insert would 500. Fall back to NULL so the note still
    # saves; current_user.email still gets returned for display.
    if author_uuid is not None:
        user_exists = (await session.execute(
            text("SELECT 1 FROM users WHERE id = :id"),
            {"id": str(author_uuid)},
        )).scalar_one_or_none()
        if user_exists is None:
            logger.info(
                "create_lead_note: author_id %s not in users table, storing NULL",
                author_uuid,
            )
            author_uuid = None

    row = (await session.execute(
        text("""
            INSERT INTO lead_notes (id, lead_id, author_id, body)
            VALUES (:id, :lead_id, :author_id, :body)
            RETURNING id::text AS id, body, author_id::text AS author_id, created_at
        """),
        {
            "id": str(note_id),
            "lead_id": str(uid),
            "author_id": str(author_uuid) if author_uuid else None,
            "body": body.body,
        },
    )).mappings().one()

    # Emit audit row in the same transaction.
    await record_event(
        session,
        user_id=_coerce_author_uuid(current_user.id),
        action="lead.note_added",
        table_name="leads",
        record_id=str(uid),
        after={"note_id": row["id"], "preview": body.body[:80]},
    )

    await session.commit()

    return NoteRow(
        id=row["id"],
        body=row["body"],
        author_id=row["author_id"],
        # We trust the caller's email over a join (avoid the extra query;
        # the FK SET NULL guarantees author_id can be valid while the
        # users row gets renamed/deleted later — for the new-note case
        # the email is current_user.email by definition).
        author_email=current_user.email,
        created_at=row["created_at"].isoformat(),
    )


@router.delete("/leads/{lead_id}/notes/{note_id}", status_code=204)
async def delete_lead_note(
    lead_id: str,
    note_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> Response:
    """Hard-delete a staff note. No author check in v1 (single-tenant).

    The DELETE RETURNs the body so we can stash a preview in the audit
    row — once the row is gone the preview is the only memory of what
    was said.
    """
    lead_uid = _parse_lead_uuid(lead_id)
    note_uid = _parse_lead_uuid(note_id)  # same 404-on-garbage behaviour

    deleted = (await session.execute(
        text("""
            DELETE FROM lead_notes
            WHERE id = :note_id AND lead_id = :lead_id
            RETURNING id::text AS id, body
        """),
        {"note_id": str(note_uid), "lead_id": str(lead_uid)},
    )).mappings().one_or_none()
    if deleted is None:
        raise HTTPException(status_code=404, detail="Note not found")

    await record_event(
        session,
        user_id=_coerce_author_uuid(current_user.id),
        action="lead.note_deleted",
        table_name="leads",
        record_id=str(lead_uid),
        before={"note_id": deleted["id"], "preview": deleted["body"][:80]},
    )

    await session.commit()
    return Response(status_code=204)
