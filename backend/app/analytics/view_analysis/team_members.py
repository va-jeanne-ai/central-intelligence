"""Analyze-view aggregator: team directory (mirrors GET /members/team filters)."""

from __future__ import annotations

from collections.abc import Mapping

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.view_analysis import Surface, register
from app.repositories.list_filters import TEAM_FROM_SQL, build_team_where

_DESCRIBE = (
    "The sales team roster (the Members page). Each row is a rep with a role, a "
    "status (active/probation/terminated), a hire date, and calls_count — how many "
    "calls in the system are attributed to them."
)


def _parse_filters(qp: Mapping[str, str]) -> dict:
    return {
        "search": qp.get("search") or None,
        "status": qp.get("status") or None,
    }


def _echo(f: dict) -> str:
    parts: list[str] = []
    if f["status"]:
        parts.append(f"status = {f['status']}")
    if f["search"]:
        parts.append(f"search '{f['search']}'")
    return "Team members — " + ("; ".join(parts) if parts else "no filters (all)")


def _pct(count: int, total: int) -> float:
    return round(100.0 * count / total, 1) if total else 0.0


async def _aggregate(session: AsyncSession, f: dict) -> dict:
    where_sql, params = build_team_where(**f)
    # Roster is small — fetch effective rows once, aggregate in Python.
    rows = (await session.execute(text(
        f"""
        SELECT
            COALESCE(ro.full_name, sr.full_name) AS name,
            LOWER(COALESCE(ro.role, sr.role, 'unknown'))     AS role,
            LOWER(COALESCE(ro.status, sr.status, 'unknown')) AS status,
            (SELECT COUNT(*) FROM calls c
             WHERE c.deleted_at IS NULL AND c.call_owner = sr.full_name) AS calls_count
        {TEAM_FROM_SQL}
        WHERE {where_sql}
        """  # noqa: S608 — where_sql parametrised
    ), params)).mappings().all()

    total = len(rows)
    if total == 0:
        return {"row_count": 0, "breakdowns": {}, "series": None, "extras": {}}

    def _count_by(field: str) -> list[dict]:
        counts: dict[str, int] = {}
        for r in rows:
            counts[r[field]] = counts.get(r[field], 0) + 1
        return [
            {"label": k, "count": v, "pct": _pct(v, total)}
            for k, v in sorted(counts.items(), key=lambda kv: -kv[1])
        ]

    top_reps = sorted(rows, key=lambda r: -int(r["calls_count"]))[:5]
    return {
        "row_count": total,
        "breakdowns": {"status": _count_by("status"), "role": _count_by("role")},
        "series": None,
        "extras": {
            "total_calls": sum(int(r["calls_count"]) for r in rows),
            "top_reps_by_calls": [
                {"name": r["name"], "calls": int(r["calls_count"])} for r in top_reps
            ],
        },
    }


register(Surface(
    key="team",
    label="team members",
    describe=_DESCRIBE,
    parse_filters=_parse_filters,
    echo=_echo,
    aggregate=_aggregate,
))
