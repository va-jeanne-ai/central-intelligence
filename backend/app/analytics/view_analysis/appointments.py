"""Analyze-view aggregator: appointments (mirrors GET /appointments filters)."""

from __future__ import annotations

from collections.abc import Mapping

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.view_analysis import Surface, register
from app.repositories.list_filters import APPOINTMENTS_FROM_SQL, build_appointment_where

_DESCRIBE = (
    "Appointments booked with sales reps. Each row has a status (e.g. booked, "
    "completed, cancelled, no-show), a scheduled date/time, the rep it belongs to, "
    "and a source. 'unassigned' means no rep is linked."
)


def _parse_filters(qp: Mapping[str, str]) -> dict:
    return {
        "status": qp.get("status") or None,
        "search": qp.get("search") or None,
        "window": qp.get("window") or "all",
        "from_date": qp.get("from") or None,
        "to_date": qp.get("to") or None,
        "start": qp.get("start") or None,
        "end": qp.get("end") or None,
        "rep": qp.get("rep") or None,
    }


def _echo(f: dict) -> str:
    parts: list[str] = []
    if f["status"]:
        parts.append(f"status = {f['status']}")
    if f["window"] != "all":
        parts.append(f"window = {f['window']}")
    if f["start"] or f["end"]:
        parts.append(f"scheduled {f['start'] or '…'} to {f['end'] or '…'}")
    if f["rep"]:
        parts.append(f"rep = {f['rep']}")
    if f["search"]:
        parts.append(f"search '{f['search']}'")
    return "Appointments — " + ("; ".join(parts) if parts else "no filters (all)")


def _pct(count: int, total: int) -> float:
    return round(100.0 * count / total, 1) if total else 0.0


async def _breakdown(
    session: AsyncSession, label_expr: str, where_sql: str, params: dict, total: int
) -> list[dict]:
    rows = (await session.execute(text(
        f"SELECT {label_expr} AS label, COUNT(*) AS n "
        f"{APPOINTMENTS_FROM_SQL} WHERE {where_sql} "
        f"GROUP BY 1 ORDER BY n DESC LIMIT 15"  # noqa: S608 — label_expr is a code constant
    ), params)).mappings().all()
    return [{"label": r["label"], "count": int(r["n"]), "pct": _pct(int(r["n"]), total)} for r in rows]


async def _aggregate(session: AsyncSession, f: dict) -> dict:
    where_sql, params = build_appointment_where(**f)
    total = int((await session.execute(text(
        f"SELECT COUNT(*) {APPOINTMENTS_FROM_SQL} WHERE {where_sql}"  # noqa: S608
    ), params)).scalar() or 0)
    if total == 0:
        return {"row_count": 0, "breakdowns": {}, "series": None, "extras": {}}

    by_status = await _breakdown(
        session, "COALESCE(LOWER(a.status), 'unknown')", where_sql, params, total)
    by_rep = await _breakdown(
        session, "COALESCE(r.full_name, a.appointment_owner, 'unassigned')",
        where_sql, params, total)
    by_source = await _breakdown(
        session, "COALESCE(LOWER(a.source), 'unknown')", where_sql, params, total)

    series_rows = (await session.execute(text(
        f"SELECT date_trunc('week', a.scheduled_at)::date AS week_start, COUNT(*) AS n "
        f"{APPOINTMENTS_FROM_SQL} WHERE {where_sql} GROUP BY 1 ORDER BY 1"  # noqa: S608
    ), params)).mappings().all()
    series = {
        "bucket": "week",
        "points": [
            {"week_start": r["week_start"].isoformat(), "count": int(r["n"])}
            for r in series_rows if r["week_start"] is not None
        ],
    }

    return {
        "row_count": total,
        "breakdowns": {"status": by_status, "rep": by_rep, "source": by_source},
        "series": series,
        "extras": {},
    }


register(Surface(
    key="appointments",
    label="appointments",
    describe=_DESCRIBE,
    parse_filters=_parse_filters,
    echo=_echo,
    aggregate=_aggregate,
))
