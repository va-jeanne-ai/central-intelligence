"""Shared appointment aggregation helpers.

Single source of truth for appointment KPIs / volume / status breakdown.
Consumed by GET /api/v1/appointments/stats, the /sales/summary block, and the
LeadsSpecialist get_appointments tool. Mirrors fulfillment_stats.py.

Status vocabulary (DB values, lowercased):
  booked / confirmed / showed / no-show / cancelled / rescheduled
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


async def compute_appointment_stats(session: AsyncSession) -> dict:
    """Aggregate appointments into KPIs, an 8-week volume series, and a status
    breakdown.

    Returns a plain dict:
        {
          "kpis": {total, upcoming_this_week, showed, no_show, show_rate, no_show_rate},
          "appointment_volume": [{"label": str, "value": int}, ...],   # 8 points
          "status_breakdown": [{"status": str, "count": int, "percentage": float}, ...],
        }

    Volume buckets on COALESCE(scheduled_at, created_at). show_rate /
    no_show_rate are over (showed + no_show); divide-by-zero guarded.
    """

    # ---- KPIs --------------------------------------------------------------
    total = _int((await session.execute(
        text("SELECT COUNT(*) FROM appointments WHERE deleted_at IS NULL")
    )).scalar())

    upcoming_this_week = _int((await session.execute(
        text(
            "SELECT COUNT(*) FROM appointments "
            "WHERE deleted_at IS NULL "
            "  AND LOWER(status) <> 'cancelled' "
            "  AND scheduled_at >= NOW() "
            "  AND scheduled_at < NOW() + INTERVAL '7 days'"
        )
    )).scalar())

    showed = _int((await session.execute(
        text("SELECT COUNT(*) FROM appointments WHERE deleted_at IS NULL AND LOWER(status) = 'showed'")
    )).scalar())

    no_show = _int((await session.execute(
        text("SELECT COUNT(*) FROM appointments WHERE deleted_at IS NULL AND LOWER(status) = 'no-show'")
    )).scalar())

    attended_base = showed + no_show
    show_rate = round(showed / attended_base * 100, 1) if attended_base > 0 else 0.0
    no_show_rate = round(no_show / attended_base * 100, 1) if attended_base > 0 else 0.0

    kpis = {
        "total": total,
        "upcoming_this_week": upcoming_this_week,
        "showed": showed,
        "no_show": no_show,
        "show_rate": show_rate,
        "no_show_rate": no_show_rate,
    }

    # ---- Volume — last 8 weeks --------------------------------------------
    row = await session.execute(
        text(
            """
            SELECT
                FLOOR(EXTRACT(EPOCH FROM (NOW() - COALESCE(scheduled_at, created_at))) / 604800)::int AS weeks_ago,
                COUNT(*) AS cnt
            FROM appointments
            WHERE deleted_at IS NULL
              AND COALESCE(scheduled_at, created_at) >= NOW() - INTERVAL '8 weeks'
              AND COALESCE(scheduled_at, created_at) < NOW() + INTERVAL '1 week'
            GROUP BY weeks_ago
            ORDER BY weeks_ago DESC
            """
        )
    )
    volume_map: dict[int, int] = {r[0]: _int(r[1]) for r in row.fetchall()}
    appointment_volume: list[dict] = [
        {"label": _week_label(w), "value": volume_map.get(w, 0)}
        for w in range(7, -1, -1)
    ]

    # ---- Status breakdown -------------------------------------------------
    row = await session.execute(
        text(
            """
            SELECT COALESCE(LOWER(status), 'unknown') AS st, COUNT(*) AS cnt
            FROM appointments
            WHERE deleted_at IS NULL
            GROUP BY st
            ORDER BY cnt DESC
            """
        )
    )
    status_rows = row.fetchall()
    status_total = sum(_int(r[1]) for r in status_rows)
    status_breakdown: list[dict] = []
    for r in status_rows:
        st, cnt = r[0], _int(r[1])
        pct = round((cnt / status_total * 100), 1) if status_total > 0 else 0.0
        status_breakdown.append({"status": st, "count": cnt, "percentage": pct})

    logger.debug(
        "compute_appointment_stats — total=%d upcoming=%d show_rate=%.1f%%",
        total, upcoming_this_week, show_rate,
    )

    return {
        "kpis": kpis,
        "appointment_volume": appointment_volume,
        "status_breakdown": status_breakdown,
    }


async def get_upcoming_appointments(session: AsyncSession, limit: int = 20) -> list[dict]:
    """Return upcoming (next 7 days, non-cancelled) appointments, soonest first."""
    row = await session.execute(
        text(
            """
            SELECT id::text AS id, contact_name, contact_email,
                   lead_id::text AS lead_id, member_id::text AS member_id,
                   status, appointment_type, scheduled_at
            FROM appointments
            WHERE deleted_at IS NULL
              AND LOWER(status) <> 'cancelled'
              AND scheduled_at >= NOW()
              AND scheduled_at < NOW() + INTERVAL '7 days'
            ORDER BY scheduled_at ASC
            LIMIT :limit
            """
        ),
        {"limit": limit},
    )
    return [
        {
            "id": r["id"],
            "contact_name": r["contact_name"],
            "contact_email": r["contact_email"],
            "lead_id": r["lead_id"],
            "member_id": r["member_id"],
            "status": r["status"],
            "appointment_type": r["appointment_type"],
            "scheduled_at": r["scheduled_at"].isoformat() if r["scheduled_at"] else None,
        }
        for r in row.mappings().all()
    ]
