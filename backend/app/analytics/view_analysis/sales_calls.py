"""Analyze-view aggregator: sales calls (mirrors GET /ci/calls filters)."""

from __future__ import annotations

from collections.abc import Mapping

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.team import RepRow
from app.analytics.view_analysis import Surface, register
from app.models.operational import Call
from app.models.sales import SalesRep
from app.repositories.list_filters import build_call_filters

_DESCRIBE = (
    "Processed sales calls. Each row has a call_type (Sales/Discovery/Outbound), a "
    "call_result (e.g. Booked, Pending, No Show), the rep who took it (call_owner), "
    "a source ('wgr' synced vs 'ci_upload' manual), a date, and a duration in minutes."
)


def _parse_filters(qp: Mapping[str, str]) -> dict:
    return {
        "call_type": qp.get("call_type") or None,
        "call_result": qp.get("call_result") or None,
        "call_owner": qp.get("call_owner") or None,
        "source": qp.get("source") or None,
        "search": qp.get("search") or None,
        "date_from": qp.get("date_from") or None,
        "date_to": qp.get("date_to") or None,
        "start": qp.get("start") or None,
        "end": qp.get("end") or None,
        "rep": qp.get("rep") or None,
    }


def _echo(f: dict) -> str:
    parts: list[str] = []
    if f["call_type"]:
        parts.append(f"type in [{f['call_type']}]")
    if f["call_result"]:
        parts.append(f"result in [{f['call_result']}]")
    if f["start"] or f["end"]:
        parts.append(f"date {f['start'] or '…'} to {f['end'] or '…'}")
    if f["rep"]:
        parts.append(f"rep = {f['rep']}")
    if f["source"]:
        parts.append(f"source = {f['source']}")
    if f["search"]:
        parts.append(f"search '{f['search']}'")
    return "Sales calls — " + ("; ".join(parts) if parts else "no filters (all)")


def _pct(count: int, total: int) -> float:
    return round(100.0 * count / total, 1) if total else 0.0


async def _fetch_roster(session: AsyncSession) -> list[RepRow]:
    rows = (await session.execute(
        select(SalesRep.rep_id, SalesRep.full_name, SalesRep.role, SalesRep.status,
               SalesRep.historical_aliases)
    )).all()
    return [RepRow(rep_id=r[0], full_name=r[1], role=r[2], status=r[3],
                   historical_aliases=r[4]) for r in rows]


async def _group(session: AsyncSession, col, clauses: list, total: int) -> list[dict]:
    rows = (await session.execute(
        select(func.coalesce(col, "unknown").label("label"), func.count().label("n"))
        .select_from(Call).where(*clauses).group_by("label")
        .order_by(func.count().desc()).limit(15)
    )).all()
    return [{"label": r[0], "count": int(r[1]), "pct": _pct(int(r[1]), total)} for r in rows]


async def _aggregate(session: AsyncSession, f: dict) -> dict:
    roster = await _fetch_roster(session)
    clauses = build_call_filters(**f, roster=roster)
    total = int((await session.execute(
        select(func.count()).select_from(Call).where(*clauses)
    )).scalar_one())
    if total == 0:
        return {"row_count": 0, "breakdowns": {}, "series": None, "extras": {}}

    by_result = await _group(session, Call.call_result, clauses, total)
    by_type = await _group(session, Call.call_type, clauses, total)
    by_owner = await _group(session, Call.call_owner, clauses, total)
    by_source = await _group(session, Call.source, clauses, total)

    series_rows = (await session.execute(
        select(func.date_trunc("week", Call.date).label("w"), func.count().label("n"))
        .select_from(Call).where(*clauses).group_by("w").order_by("w")
    )).all()
    series = {
        "bucket": "week",
        "points": [
            {"week_start": r[0].date().isoformat(), "count": int(r[1])}
            for r in series_rows if r[0] is not None
        ],
    }

    avg_duration = (await session.execute(
        select(func.avg(Call.call_duration_minutes)).select_from(Call).where(*clauses)
    )).scalar()

    return {
        "row_count": total,
        "breakdowns": {
            "call_result": by_result, "call_type": by_type,
            "rep": by_owner, "source": by_source,
        },
        "series": series,
        "extras": {
            "avg_duration_minutes": round(float(avg_duration), 1) if avg_duration else None,
        },
    }


register(Surface(
    key="sales_calls",
    label="sales calls",
    describe=_DESCRIBE,
    parse_filters=_parse_filters,
    echo=_echo,
    aggregate=_aggregate,
))
