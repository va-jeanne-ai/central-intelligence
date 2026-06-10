"""Shared Tech SOS (support ticket) aggregation helpers.

Single source of truth for ticket KPIs / category + status breakdown / volume.
Consumed by GET /api/v1/tech-sos/stats, the /fulfillment/summary block, and the
members specialist's get_tech_sos tool. Mirrors appointment_stats.py.

Status vocabulary: open / in_progress / resolved / closed.
Category vocabulary (staff-set): login / billing / video / portal / access / other.
"""

from __future__ import annotations

import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


def _int(value: object) -> int:
    try:
        return int(value) if value is not None else 0
    except (TypeError, ValueError):
        return 0


def _week_label(weeks_ago: int) -> str:
    if weeks_ago == 0:
        return "Now"
    return f"Wk {8 - weeks_ago}"


async def compute_ticket_stats(session: AsyncSession) -> dict:
    """Aggregate support tickets into KPIs, category + status breakdowns, and an
    8-week volume series.

    Returns:
        {
          "kpis": {total, open, in_progress, resolved, avg_resolution_hours},
          "category_breakdown": [{"category": str, "count": int, "percentage": float}, ...],
          "status_breakdown": [{"status": str, "count": int, "percentage": float}, ...],
          "ticket_volume": [{"label": str, "value": int}, ...],   # 8 points
        }
    """

    # ---- KPIs --------------------------------------------------------------
    row = await session.execute(
        text(
            """
            SELECT
                SUM(CASE WHEN deleted_at IS NULL THEN 1 ELSE 0 END)                        AS total,
                SUM(CASE WHEN deleted_at IS NULL AND LOWER(status) = 'open'
                         THEN 1 ELSE 0 END)                                                 AS open_cnt,
                SUM(CASE WHEN deleted_at IS NULL AND LOWER(status) = 'in_progress'
                         THEN 1 ELSE 0 END)                                                 AS in_progress,
                SUM(CASE WHEN deleted_at IS NULL AND LOWER(status) IN ('resolved', 'closed')
                         THEN 1 ELSE 0 END)                                                 AS resolved
            FROM support_tickets
            """
        )
    )
    r = row.fetchone()
    total = _int(r[0]) if r else 0
    open_cnt = _int(r[1]) if r else 0
    in_progress = _int(r[2]) if r else 0
    resolved = _int(r[3]) if r else 0

    # Average resolution time (hours) over resolved tickets.
    avg_row = await session.execute(
        text(
            """
            SELECT AVG(EXTRACT(EPOCH FROM (resolved_at - created_at)) / 3600.0)
            FROM support_tickets
            WHERE deleted_at IS NULL AND resolved_at IS NOT NULL
            """
        )
    )
    avg_val = avg_row.scalar()
    avg_resolution_hours = round(float(avg_val), 1) if avg_val is not None else 0.0

    kpis = {
        "total": total,
        "open": open_cnt,
        "in_progress": in_progress,
        "resolved": resolved,
        "avg_resolution_hours": avg_resolution_hours,
    }

    # ---- Category breakdown (patterns) ------------------------------------
    cat_rows = (await session.execute(
        text(
            """
            SELECT COALESCE(LOWER(category), 'other') AS cat, COUNT(*) AS cnt
            FROM support_tickets
            WHERE deleted_at IS NULL
            GROUP BY cat
            ORDER BY cnt DESC
            """
        )
    )).fetchall()
    cat_total = sum(_int(x[1]) for x in cat_rows)
    category_breakdown = [
        {
            "category": x[0],
            "count": _int(x[1]),
            "percentage": round(_int(x[1]) / cat_total * 100, 1) if cat_total > 0 else 0.0,
        }
        for x in cat_rows
    ]

    # ---- Status breakdown -------------------------------------------------
    st_rows = (await session.execute(
        text(
            """
            SELECT COALESCE(LOWER(status), 'open') AS st, COUNT(*) AS cnt
            FROM support_tickets
            WHERE deleted_at IS NULL
            GROUP BY st
            ORDER BY cnt DESC
            """
        )
    )).fetchall()
    st_total = sum(_int(x[1]) for x in st_rows)
    status_breakdown = [
        {
            "status": x[0],
            "count": _int(x[1]),
            "percentage": round(_int(x[1]) / st_total * 100, 1) if st_total > 0 else 0.0,
        }
        for x in st_rows
    ]

    # ---- Volume — last 8 weeks --------------------------------------------
    vol = await session.execute(
        text(
            """
            SELECT
                FLOOR(EXTRACT(EPOCH FROM (NOW() - created_at)) / 604800)::int AS weeks_ago,
                COUNT(*) AS cnt
            FROM support_tickets
            WHERE deleted_at IS NULL
              AND created_at >= NOW() - INTERVAL '8 weeks'
            GROUP BY weeks_ago
            ORDER BY weeks_ago DESC
            """
        )
    )
    volume_map: dict[int, int] = {x[0]: _int(x[1]) for x in vol.fetchall()}
    ticket_volume = [
        {"label": _week_label(w), "value": volume_map.get(w, 0)}
        for w in range(7, -1, -1)
    ]

    logger.debug(
        "compute_ticket_stats — total=%d open=%d in_progress=%d resolved=%d",
        total, open_cnt, in_progress, resolved,
    )

    return {
        "kpis": kpis,
        "category_breakdown": category_breakdown,
        "status_breakdown": status_breakdown,
        "ticket_volume": ticket_volume,
    }


async def get_open_tickets(session: AsyncSession, limit: int = 20) -> list[dict]:
    """Return the most recent open/in-progress tickets, newest first."""
    rows = (await session.execute(
        text(
            """
            SELECT id::text AS id, member_id::text AS member_id, contact_name,
                   subject, category, status, priority, created_at
            FROM support_tickets
            WHERE deleted_at IS NULL AND LOWER(status) IN ('open', 'in_progress')
            ORDER BY created_at DESC
            LIMIT :limit
            """
        ),
        {"limit": limit},
    )).mappings().all()
    return [
        {
            "id": r["id"],
            "member_id": r["member_id"],
            "contact_name": r["contact_name"],
            "subject": r["subject"],
            "category": r["category"],
            "status": r["status"],
            "priority": r["priority"],
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
        }
        for r in rows
    ]
