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
from datetime import date, datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser, get_current_user
from app.database import get_session
from app.repositories.sales_stats import compute_lead_stats
from app.schemas.appointments import AppointmentRecord, LeadAppointmentsResponse
from app.schemas.leads import (
    CreateNoteRequest,
    DocumentRow,
    DocumentsResponse,
    EmailAttachmentMeta,
    EmailMessageRow,
    EmailThreadRow,
    EmailThreadsResponse,
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
from app.schemas.calendar import (
    CalendarAttendee,
    CalendarEventRow,
    CalendarEventsResponse,
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
    {"created_at", "entry_date", "name", "email", "status", "source"}
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


def _parse_date(value: str | None) -> date | None:
    """Parse a YYYY-MM-DD string to a date; return None for empty/invalid input.

    Invalid dates are swallowed (not raised) so a half-typed date-range filter
    degrades to "no filter" rather than 422-ing the whole list request."""
    if not value:
        return None
    try:
        return date.fromisoformat(value.strip())
    except (TypeError, ValueError):
        return None


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
    entry_from: str | None = Query(
        default=None, description="Filter: entry_date on/after this date (YYYY-MM-DD)"
    ),
    entry_to: str | None = Query(
        default=None, description="Filter: entry_date on/before this date (YYYY-MM-DD)"
    ),
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

    # Date-range filter on the upstream funnel-entry date. Invalid dates are
    # ignored rather than erroring, so a half-typed range never breaks the list.
    entry_lo = _parse_date(entry_from)
    if entry_lo is not None:
        where_parts.append("entry_date >= :entry_from")
        params["entry_from"] = entry_lo
    entry_hi = _parse_date(entry_to)
    if entry_hi is not None:
        where_parts.append("entry_date <= :entry_to")
        params["entry_to"] = entry_hi

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
            entry_date,
            created_at
        FROM leads
        WHERE {where_sql}
        ORDER BY {sort_by} {sort_dir} NULLS LAST, id ASC
        LIMIT :limit OFFSET :offset
        """  # noqa: S608
    )
    rows = (await session.execute(data_sql, params)).fetchall()

    # ---- Map rows to response models ----------------------------------------
    leads: list[LeadRecord] = []
    for r in rows:
        raw_id, name, email, phone, raw_status, source_val, entry_date, created_at = r
        api_status = _map_status(raw_status)
        score = _score_for_status(api_status)
        # The lead's date in the UI is the true funnel-entry date when known;
        # fall back to created_at (sync time) for leads with no upstream date.
        lead_date = entry_date or created_at
        leads.append(
            LeadRecord(
                id=str(raw_id),
                name=name,
                email=email,
                phone=phone,
                status=api_status,
                source=source_val,
                notes=None,
                createdAt=lead_date.isoformat() if lead_date is not None else None,
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
    """Compute and return aggregated lead statistics.

    Delegates to ``compute_lead_stats`` (app.repositories.sales_stats) so the
    KPI / volume / source / funnel aggregation has a single source of truth
    shared with the Sales department surfaces. This route just adapts the
    plain dict into the ``LeadsStatsResponse`` schema the frontend expects.
    """
    data = await compute_lead_stats(session)

    kpis = LeadsKpiResponse(**data["kpis"])
    lead_volume = [LeadVolumePoint(**p) for p in data["lead_volume"]]
    source_breakdown = [SourceBreakdownItem(**s) for s in data["source_breakdown"]]
    funnel = [FunnelStage(**f) for f in data["funnel"]]

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
                   notes, external_id, entry_date, created_at
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
        entry_date=lead_row["entry_date"].isoformat() if lead_row["entry_date"] else None,
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
# Lead email threads — GET /api/v1/leads/{id}/emails
# ===========================================================================


@router.get("/leads/{lead_id}/emails", response_model=EmailThreadsResponse)
async def get_lead_emails(
    lead_id: str,
    session: AsyncSession = Depends(get_session),
) -> EmailThreadsResponse:
    """Return Gmail threads linked to this lead, with messages nested.

    The thread/message rows are populated by the Gmail sync task (see
    ``tasks/gmail_sync.py``). Threads are ordered newest-first by
    ``last_message_at`` so the lead detail page renders them in the
    order staff expect. Messages inside each thread are ordered oldest-
    first so reading top-to-bottom matches conversation flow.
    """
    uid = _parse_lead_uuid(lead_id)

    # Confirm the lead exists (helps surface 404 vs empty thread list).
    exists = (await session.execute(
        text("SELECT 1 FROM leads WHERE id = :id AND deleted_at IS NULL"),
        {"id": str(uid)},
    )).scalar_one_or_none()
    if exists is None:
        raise HTTPException(status_code=404, detail="Lead not found")

    thread_rows = (await session.execute(
        text("""
            SELECT id::text AS id, subject, last_message_at, message_count
            FROM email_threads
            WHERE lead_id = :id
            ORDER BY last_message_at DESC NULLS LAST
        """),
        {"id": str(uid)},
    )).mappings().all()

    if not thread_rows:
        return EmailThreadsResponse(threads=[])

    thread_ids = [r["id"] for r in thread_rows]
    message_rows = (await session.execute(
        text("""
            SELECT
                id::text AS id,
                thread_id::text AS thread_id,
                from_address,
                to_addresses,
                cc_addresses,
                subject,
                body_text,
                sent_at,
                has_attachments,
                attachments_meta
            FROM email_messages
            WHERE thread_id = ANY(:ids)
            ORDER BY sent_at NULLS FIRST
        """),
        {"ids": thread_ids},
    )).mappings().all()

    # Group messages by thread_id for fast lookup.
    by_thread: dict[str, list[EmailMessageRow]] = {tid: [] for tid in thread_ids}
    for m in message_rows:
        by_thread[m["thread_id"]].append(EmailMessageRow(
            id=m["id"],
            from_address=m["from_address"],
            to_addresses=m["to_addresses"] or [],
            cc_addresses=m["cc_addresses"] or [],
            subject=m["subject"],
            body_text=m["body_text"],
            sent_at=m["sent_at"].isoformat() if m["sent_at"] else None,
            has_attachments=bool(m["has_attachments"]),
            attachments_meta=[
                EmailAttachmentMeta(
                    filename=a.get("filename", ""),
                    size=int(a.get("size") or 0),
                    mime_type=a.get("mime_type"),
                )
                for a in (m["attachments_meta"] or [])
            ],
        ))

    threads = [
        EmailThreadRow(
            id=t["id"],
            subject=t["subject"],
            last_message_at=t["last_message_at"].isoformat() if t["last_message_at"] else None,
            message_count=int(t["message_count"] or 0),
            messages=by_thread.get(t["id"]) or [],
        )
        for t in thread_rows
    ]

    return EmailThreadsResponse(threads=threads)


# ===========================================================================
# Lead documents — GET /api/v1/leads/{id}/documents
# Lists Google Drive files where the lead's email appears in the file's
# sharing permissions. Populated by the Drive sync task; dedupes the
# same file appearing in multiple connected users' Drives.
# ===========================================================================


@router.get("/leads/{lead_id}/documents", response_model=DocumentsResponse)
async def get_lead_documents(
    lead_id: str,
    session: AsyncSession = Depends(get_session),
) -> DocumentsResponse:
    """Return Drive files shared with this lead's email address.

    Containment query on the JSONB ``shared_with`` array (GIN-indexed).
    The same Drive file can appear in multiple connected users'
    mailboxes — we DISTINCT ON ``provider_file_id`` to surface one
    row per real file.
    """
    uid = _parse_lead_uuid(lead_id)

    row = (await session.execute(
        text(
            "SELECT email FROM leads "
            "WHERE id = :id AND deleted_at IS NULL"
        ),
        {"id": str(uid)},
    )).mappings().first()
    if row is None:
        raise HTTPException(status_code=404, detail="Lead not found")

    lead_email = (row.get("email") or "").strip().lower()
    if not lead_email:
        return DocumentsResponse(files=[])

    file_rows = (await session.execute(
        text("""
            SELECT DISTINCT ON (provider_file_id)
                id::text AS id,
                name,
                mime_type,
                owner_email,
                modified_time,
                web_view_link,
                parent_folder_name,
                size_bytes
            FROM google_drive_files
            WHERE shared_with @> CAST(:email_json AS jsonb)
              AND is_trashed = FALSE
            ORDER BY provider_file_id, modified_time DESC NULLS LAST
        """),
        {"email_json": f'["{lead_email}"]'},
    )).mappings().all()

    # Re-sort by modified_time desc for the response — the DISTINCT ON
    # forces an intermediate ORDER BY on provider_file_id.
    file_rows_sorted = sorted(
        file_rows,
        key=lambda r: r["modified_time"] or "",
        reverse=True,
    )

    files = [
        DocumentRow(
            id=r["id"],
            name=r["name"],
            mime_type=r["mime_type"],
            owner_email=r["owner_email"],
            modified_time=(
                r["modified_time"].isoformat() if r["modified_time"] else None
            ),
            web_view_link=r["web_view_link"],
            parent_folder_name=r["parent_folder_name"],
            size_bytes=r["size_bytes"],
        )
        for r in file_rows_sorted
    ]
    return DocumentsResponse(files=files)


@router.post("/leads/{lead_id}/sync-documents", status_code=202)
async def sync_lead_documents(
    lead_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),  # noqa: ARG001
) -> dict:
    """Enqueue a Drive sweep for every connected user.

    Drive's sharing model means we can't filter by "files shared with
    this lead" at fetch time — the relevant files might live in any
    connected user's mailbox. We re-sweep all connected users; the
    upsert is cheap (content_hash short-circuits unchanged files).
    """
    uid = _parse_lead_uuid(lead_id)

    exists = (await session.execute(
        text("SELECT 1 FROM leads WHERE id = :id AND deleted_at IS NULL"),
        {"id": str(uid)},
    )).scalar_one_or_none()
    if exists is None:
        raise HTTPException(status_code=404, detail="Lead not found")

    user_ids = (await session.execute(
        text(
            "SELECT user_id::text FROM user_integration_credentials "
            "WHERE provider = 'google_workspace'"
        ),
    )).scalars().all()
    if not user_ids:
        return {"task_ids": [], "reason": "no_connected_users"}

    task_ids: list[str] = []
    try:
        from app.tasks.drive_sync import sync_drive_files_for_user
        for u in user_ids:
            task = sync_drive_files_for_user.delay(u)
            task_ids.append(task.id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("sync_lead_documents: enqueue failed — %s", exc)
        raise HTTPException(
            status_code=503,
            detail="Failed to enqueue document sync. Try again in a minute.",
        ) from exc

    return {"task_ids": task_ids, "lead_id": str(uid)}


# ===========================================================================
# Lead calendar events — GET /api/v1/leads/{id}/events
# JSONB containment on google_calendar_events.attendees — any event
# where this lead's email appears in the attendees array shows here.
# ===========================================================================


@router.get("/leads/{lead_id}/events", response_model=CalendarEventsResponse)
async def get_lead_events(
    lead_id: str,
    session: AsyncSession = Depends(get_session),
) -> CalendarEventsResponse:
    """Return calendar events the lead is invited to.

    Sorted with future events first (start_time DESC NULLS LAST), so
    the lead-detail card opens to upcoming meetings. The lead's email
    is matched case-insensitively against every attendee's email.
    """
    uid = _parse_lead_uuid(lead_id)

    row = (await session.execute(
        text(
            "SELECT email FROM leads "
            "WHERE id = :id AND deleted_at IS NULL"
        ),
        {"id": str(uid)},
    )).mappings().first()
    if row is None:
        raise HTTPException(status_code=404, detail="Lead not found")

    lead_email = (row.get("email") or "").strip().lower()
    if not lead_email:
        return CalendarEventsResponse(events=[], total=0)

    event_rows = (await session.execute(
        text("""
            SELECT DISTINCT ON (provider_event_id)
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
                status,
                provider_event_id
            FROM google_calendar_events
            WHERE EXISTS (
                SELECT 1
                FROM jsonb_array_elements(coalesce(attendees, '[]'::jsonb)) a
                WHERE lower(a->>'email') = :email
            )
            ORDER BY provider_event_id, start_time DESC NULLS LAST
        """),
        {"email": lead_email},
    )).mappings().all()

    # Re-sort by start_time DESC for the response — DISTINCT ON forces
    # an intermediate ORDER BY on provider_event_id.
    rows_sorted = sorted(
        event_rows,
        key=lambda r: r["start_time"] or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )

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
        for r in rows_sorted
    ]
    return CalendarEventsResponse(events=events, total=len(events))


@router.get("/leads/{lead_id}/appointments", response_model=LeadAppointmentsResponse)
async def get_lead_appointments(
    lead_id: str,
    session: AsyncSession = Depends(get_session),
) -> LeadAppointmentsResponse:
    """Return appointments booked for this lead, soonest-scheduled first."""
    uid = _parse_lead_uuid(lead_id)

    exists = (await session.execute(
        text("SELECT 1 FROM leads WHERE id = :id AND deleted_at IS NULL"),
        {"id": str(uid)},
    )).scalar_one_or_none()
    if exists is None:
        raise HTTPException(status_code=404, detail="Lead not found")

    rows = (await session.execute(
        text(
            """
            SELECT id::text AS id, contact_name, contact_email,
                   lead_id::text AS lead_id, member_id::text AS member_id,
                   status, appointment_type, scheduled_at, source
            FROM appointments
            WHERE lead_id = :id AND deleted_at IS NULL
            ORDER BY scheduled_at DESC NULLS LAST
            """
        ),
        {"id": str(uid)},
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
            source=r["source"],
        )
        for r in rows
    ]
    return LeadAppointmentsResponse(appointments=appointments, total=len(appointments))


@router.post("/leads/{lead_id}/sync-events", status_code=202)
async def sync_lead_events(
    lead_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),  # noqa: ARG001
) -> dict:
    """Enqueue a Calendar sweep for every connected user.

    Same model as ``sync_lead_documents`` — the relevant event might
    live in any connected user's calendar, so we re-sweep all of them.
    The upsert is cheap (content_hash short-circuits unchanged events).
    """
    uid = _parse_lead_uuid(lead_id)

    exists = (await session.execute(
        text("SELECT 1 FROM leads WHERE id = :id AND deleted_at IS NULL"),
        {"id": str(uid)},
    )).scalar_one_or_none()
    if exists is None:
        raise HTTPException(status_code=404, detail="Lead not found")

    user_ids = (await session.execute(
        text(
            "SELECT user_id::text FROM user_integration_credentials "
            "WHERE provider = 'google_workspace'"
        ),
    )).scalars().all()
    if not user_ids:
        return {"task_ids": [], "reason": "no_connected_users"}

    task_ids: list[str] = []
    try:
        from app.tasks.calendar_sync import sync_calendar_events_for_user
        for u in user_ids:
            task = sync_calendar_events_for_user.delay(u)
            task_ids.append(task.id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("sync_lead_events: enqueue failed — %s", exc)
        raise HTTPException(
            status_code=503,
            detail="Failed to enqueue event sync. Try again in a minute.",
        ) from exc

    return {"task_ids": task_ids, "lead_id": str(uid)}


@router.post("/leads/{lead_id}/sync-emails", status_code=202)
async def sync_lead_emails(
    lead_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),  # noqa: ARG001
) -> dict:
    """Enqueue a per-lead Gmail sync.

    Used by the "Sync emails now" button on the lead detail page.
    Validates the lead exists, then fires the Celery task with the
    lead_id. Returns immediately — the UI polls the emails endpoint
    after a short delay.
    """
    uid = _parse_lead_uuid(lead_id)

    exists = (await session.execute(
        text("SELECT 1 FROM leads WHERE id = :id AND deleted_at IS NULL"),
        {"id": str(uid)},
    )).scalar_one_or_none()
    if exists is None:
        raise HTTPException(status_code=404, detail="Lead not found")

    try:
        from app.tasks.gmail_sync import sync_gmail_threads_for_lead
        task = sync_gmail_threads_for_lead.delay(str(uid))
        return {"task_id": task.id, "lead_id": str(uid)}
    except Exception as exc:  # noqa: BLE001
        logger.warning("sync_lead_emails: enqueue failed — %s", exc)
        raise HTTPException(
            status_code=503,
            detail="Failed to enqueue sync. Try again in a minute.",
        ) from exc


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
        RETURNING id::text AS id, name, email, phone, status, source,
                  entry_date, created_at
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
    score = _score_for_status(api_status)

    # CI → GHL reverse-sync push. Fire-and-forget from the staff user's
    # perspective: their PATCH already committed. Push runs inline so the
    # happy path lands in GHL within a couple seconds; on failure we
    # enqueue a Celery retry task and continue. Never let push outcomes
    # block or rollback the staff-facing response.
    push_status: str = "skipped_not_attempted"
    push_details: dict[str, object] = {}
    try:
        from app.services.ghl_push import push_lead_update
        push_status, push_details = await push_lead_update(
            session,
            str(uid),
            api_status=api_status,
            score=score,
        )
    except Exception as exc:  # noqa: BLE001 — never let push crash the route
        logger.exception("update_lead: ghl push raised — lead_id=%s", uid)
        push_status = "error"
        push_details = {"reason": "helper_raised", "detail": str(exc)[:300]}

    # On transient errors, schedule a Celery retry. Skipped statuses are
    # terminal (lead isn't ghl-linked, kill switch on, etc.).
    if push_status == "error":
        try:
            from app.tasks.ghl_push import push_lead_to_ghl_async
            push_lead_to_ghl_async.delay(str(uid))
        except Exception as exc:  # noqa: BLE001
            logger.warning("update_lead: enqueue retry failed — %s", exc)

    # Audit-log the push outcome. One row per PATCH (not per-field) so
    # the history card stays scannable. Skipped statuses still emit so
    # the user can see "no push because not GHL-linked" rather than
    # silence.
    await record_event(
        session,
        user_id=actor_id,
        action="lead.pushed_to_ghl",
        table_name="leads",
        record_id=str(uid),
        after={"status": push_status, **push_details},
    )

    return LeadRecord(
        id=row["id"],
        name=row["name"],
        email=row["email"],
        phone=row["phone"],
        status=api_status or "new",
        source=row["source"] or "other",
        score=score,
        createdAt=(row["entry_date"] or row["created_at"]).isoformat()
        if (row["entry_date"] or row["created_at"])
        else "",
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
