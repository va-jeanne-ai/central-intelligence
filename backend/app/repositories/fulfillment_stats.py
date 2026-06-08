"""Shared fulfillment aggregation helpers.

Single source of truth for the member KPI / enrollment-volume / status /
goal-funnel aggregation. Both the ``GET /api/v1/fulfillment/summary`` route and
the Fulfillment Director agent's ``get_fulfillment_summary`` tool consume
``compute_member_stats`` so the numbers can't drift between them.

Mirrors ``sales_stats.py``. Pain-point + recent-insight helpers are reused from
that module rather than duplicated.

Member status vocabulary (DB values, lowercased), observed:
  active / paused / graduated / churned
Goal status vocabulary:
  active / completed / abandoned
"""

from __future__ import annotations

import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Private numeric coercion + labelling helpers (copied from sales_stats.py)
# ---------------------------------------------------------------------------


def _int(value: object) -> int:
    """Return value as int, falling back to 0 for None or non-numeric values."""
    try:
        return int(value) if value is not None else 0
    except (TypeError, ValueError):
        return 0


def _week_label(weeks_ago: int) -> str:
    """Return a compact week label.

    weeks_ago=7 → 'Wk 1' (oldest), weeks_ago=0 → 'Now' (current).
    """
    if weeks_ago == 0:
        return "Now"
    return f"Wk {8 - weeks_ago}"


# ---------------------------------------------------------------------------
# Member stats aggregation
# ---------------------------------------------------------------------------


async def compute_member_stats(session: AsyncSession) -> dict:
    """Aggregate member data into KPIs, an 8-week enrollment-volume series,
    a status breakdown, and a goal-status funnel.

    Returns a plain dict (not a Pydantic model) so both the members/fulfillment
    routes and the agent tooling can consume it:

        {
          "kpis": {total_members, members_this_week, active_members, goals_completed},
          "enrollment_volume": [{"label": str, "value": int}, ...],     # 8 points
          "status_breakdown": [{"status": str, "count": int, "percentage": float}, ...],
          "goal_funnel": [{"stage": str, "count": int, "percentage": float}, ...],
        }

    ``members.enrollment_date`` is the enrollment timestamp where set; rows
    without it fall back to ``created_at`` for the volume series.
    """

    # ---- 1. Total members (non-deleted) ------------------------------------
    row = await session.execute(
        text("SELECT COUNT(*) FROM members WHERE deleted_at IS NULL")
    )
    total_members: int = _int(row.scalar())

    # ---- 2. Members enrolled in the last 7 days ----------------------------
    row = await session.execute(
        text(
            "SELECT COUNT(*) FROM members "
            "WHERE deleted_at IS NULL "
            "  AND COALESCE(enrollment_date, created_at) >= NOW() - INTERVAL '7 days'"
        )
    )
    members_this_week: int = _int(row.scalar())

    # ---- 3. Active members -------------------------------------------------
    row = await session.execute(
        text(
            "SELECT COUNT(*) FROM members "
            "WHERE deleted_at IS NULL "
            "  AND LOWER(status) = 'active'"
        )
    )
    active_members: int = _int(row.scalar())

    # ---- 4. Goals completed ------------------------------------------------
    row = await session.execute(
        text(
            "SELECT COUNT(*) FROM goals "
            "WHERE deleted_at IS NULL "
            "  AND member_id IS NOT NULL "
            "  AND LOWER(status) = 'completed'"
        )
    )
    goals_completed: int = _int(row.scalar())

    kpis = {
        "total_members": total_members,
        "members_this_week": members_this_week,
        "active_members": active_members,
        "goals_completed": goals_completed,
    }

    # ---- 5. Enrollment volume — last 8 calendar weeks ----------------------
    row = await session.execute(
        text(
            """
            SELECT
                FLOOR(EXTRACT(EPOCH FROM (NOW() - COALESCE(enrollment_date, created_at))) / 604800)::int AS weeks_ago,
                COUNT(*) AS cnt
            FROM members
            WHERE deleted_at IS NULL
              AND COALESCE(enrollment_date, created_at) >= NOW() - INTERVAL '8 weeks'
            GROUP BY weeks_ago
            ORDER BY weeks_ago DESC
            """
        )
    )
    volume_map: dict[int, int] = {r[0]: _int(r[1]) for r in row.fetchall()}

    enrollment_volume: list[dict] = [
        {"label": _week_label(w), "value": volume_map.get(w, 0)}
        for w in range(7, -1, -1)  # oldest (Wk 1) → newest (Now)
    ]

    # ---- 6. Status breakdown -----------------------------------------------
    row = await session.execute(
        text(
            """
            SELECT
                COALESCE(LOWER(status), 'unknown') AS st,
                COUNT(*) AS cnt
            FROM members
            WHERE deleted_at IS NULL
            GROUP BY st
            ORDER BY cnt DESC
            """
        )
    )
    status_rows = row.fetchall()

    status_total: int = sum(_int(r[1]) for r in status_rows)
    status_breakdown: list[dict] = []
    for r in status_rows:
        st, cnt = r[0], _int(r[1])
        pct = round((cnt / status_total * 100), 1) if status_total > 0 else 0.0
        status_breakdown.append({"status": st, "count": cnt, "percentage": pct})

    # ---- 7. Goal funnel ----------------------------------------------------
    # Three stages over member-linked goals:
    #   Goals Set   — all non-deleted member goals
    #   In Progress — status = active
    #   Completed   — status = completed
    row = await session.execute(
        text(
            """
            SELECT
                SUM(CASE WHEN deleted_at IS NULL THEN 1 ELSE 0 END)                       AS all_goals,
                SUM(CASE WHEN deleted_at IS NULL AND LOWER(status) = 'active'
                         THEN 1 ELSE 0 END)                                                AS in_progress,
                SUM(CASE WHEN deleted_at IS NULL AND LOWER(status) = 'completed'
                         THEN 1 ELSE 0 END)                                                AS completed
            FROM goals
            WHERE member_id IS NOT NULL
            """
        )
    )
    funnel_row = row.fetchone()
    g_all = _int(funnel_row[0]) if funnel_row else 0
    g_active = _int(funnel_row[1]) if funnel_row else 0
    g_done = _int(funnel_row[2]) if funnel_row else 0

    def _funnel_pct(count: int, base: int) -> float:
        if base == 0:
            return 0.0
        return round(count / base * 100, 1)

    goal_funnel: list[dict] = [
        {"stage": "Goals Set", "count": g_all, "percentage": 100.0},
        {"stage": "In Progress", "count": g_active, "percentage": _funnel_pct(g_active, g_all)},
        {"stage": "Completed", "count": g_done, "percentage": _funnel_pct(g_done, g_all)},
    ]

    logger.debug(
        "compute_member_stats — total=%d this_week=%d active=%d goals_completed=%d",
        total_members,
        members_this_week,
        active_members,
        goals_completed,
    )

    return {
        "kpis": kpis,
        "enrollment_volume": enrollment_volume,
        "status_breakdown": status_breakdown,
        "goal_funnel": goal_funnel,
    }


# ---------------------------------------------------------------------------
# Recent wins — shared by the Fulfillment Director + Coaching specialist
# ---------------------------------------------------------------------------


async def get_recent_wins(session: AsyncSession, limit: int = 10) -> list[dict]:
    """Return the most recent member wins, newest first."""
    from app.models.operational import Win
    from app.repositories.operational import WinRepository

    repo = WinRepository(session)
    stmt = (
        repo._base_select()
        .order_by(Win.win_date.desc().nullslast())
        .limit(limit)
    )
    result = await session.execute(stmt)
    wins = list(result.scalars().all())

    return [
        {
            "id": str(w.id),
            "win_text": w.win_text,
            "impact_area": w.impact_area,
            "win_date": w.win_date.isoformat() if w.win_date else None,
            "member_id": str(w.member_id) if w.member_id else None,
        }
        for w in wins
    ]
