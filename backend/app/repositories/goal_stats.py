"""Shared goal (accountability) aggregation helpers.

Single source of truth for goal KPIs / funnel / status breakdown. Consumed by
GET /api/v1/goals/stats and the members specialist's get_goal_progress tool.
Member-scoped (lead goals excluded) — consistent with the goal_funnel in
fulfillment_stats.compute_member_stats.

Goal status vocabulary (DB values, lowercased): active / completed / abandoned.
"Overdue" = active goals whose target_date has passed.
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


def _funnel_pct(count: int, base: int) -> float:
    if base == 0:
        return 0.0
    return round(count / base * 100, 1)


async def compute_goal_stats(session: AsyncSession) -> dict:
    """Aggregate member goals into KPIs, a 3-stage funnel, and a status breakdown.

    Returns a plain dict:
        {
          "kpis": {total, in_progress, completed, overdue},
          "goal_funnel": [{"stage": str, "count": int, "percentage": float}, ...],  # 3
          "status_breakdown": [{"status": str, "count": int, "percentage": float}, ...],
        }
    """

    # ---- KPIs + funnel (single pass) ---------------------------------------
    row = await session.execute(
        text(
            """
            SELECT
                SUM(CASE WHEN deleted_at IS NULL THEN 1 ELSE 0 END)                        AS all_goals,
                SUM(CASE WHEN deleted_at IS NULL AND LOWER(status) = 'active'
                         THEN 1 ELSE 0 END)                                                 AS in_progress,
                SUM(CASE WHEN deleted_at IS NULL AND LOWER(status) = 'completed'
                         THEN 1 ELSE 0 END)                                                 AS completed,
                SUM(CASE WHEN deleted_at IS NULL AND LOWER(status) = 'active'
                              AND target_date IS NOT NULL AND target_date < NOW()
                         THEN 1 ELSE 0 END)                                                 AS overdue
            FROM goals
            WHERE member_id IS NOT NULL
            """
        )
    )
    r = row.fetchone()
    g_all = _int(r[0]) if r else 0
    g_active = _int(r[1]) if r else 0
    g_done = _int(r[2]) if r else 0
    g_overdue = _int(r[3]) if r else 0

    kpis = {
        "total": g_all,
        "in_progress": g_active,
        "completed": g_done,
        "overdue": g_overdue,
    }

    goal_funnel: list[dict] = [
        {"stage": "Goals Set", "count": g_all, "percentage": 100.0},
        {"stage": "In Progress", "count": g_active, "percentage": _funnel_pct(g_active, g_all)},
        {"stage": "Completed", "count": g_done, "percentage": _funnel_pct(g_done, g_all)},
    ]

    # ---- Status breakdown --------------------------------------------------
    row = await session.execute(
        text(
            """
            SELECT COALESCE(LOWER(status), 'unknown') AS st, COUNT(*) AS cnt
            FROM goals
            WHERE member_id IS NOT NULL AND deleted_at IS NULL
            GROUP BY st
            ORDER BY cnt DESC
            """
        )
    )
    status_rows = row.fetchall()
    status_total = sum(_int(x[1]) for x in status_rows)
    status_breakdown: list[dict] = []
    for x in status_rows:
        st, cnt = x[0], _int(x[1])
        pct = round((cnt / status_total * 100), 1) if status_total > 0 else 0.0
        status_breakdown.append({"status": st, "count": cnt, "percentage": pct})

    logger.debug(
        "compute_goal_stats — total=%d in_progress=%d completed=%d overdue=%d",
        g_all, g_active, g_done, g_overdue,
    )

    return {
        "kpis": kpis,
        "goal_funnel": goal_funnel,
        "status_breakdown": status_breakdown,
    }
