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
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.schemas.leads import (
    FunnelStage,
    LeadListResponse,
    LeadRecord,
    LeadsKpiResponse,
    LeadsStatsResponse,
    LeadVolumePoint,
    SourceBreakdownItem,
)

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
