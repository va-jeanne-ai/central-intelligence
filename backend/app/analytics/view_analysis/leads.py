"""Analyze-view aggregator: leads (mirrors GET /leads filters)."""

from __future__ import annotations

from collections.abc import Mapping

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.view_analysis import Surface, register
from app.repositories.list_filters import build_lead_where

_DESCRIBE = (
    "Sales leads (prospects). Each row has a pipeline status (raw DB vocabulary: new, "
    "contacted, qualified, appointment-set, sale, lost, stale), a source (where the "
    "lead came from), and an entry_date (when it entered the funnel)."
)


def _parse_filters(qp: Mapping[str, str]) -> dict:
    return {
        "status": qp.get("status") or None,
        "source": qp.get("source") or None,
        "search": qp.get("search") or None,
        "entry_from": qp.get("entry_from") or None,
        "entry_to": qp.get("entry_to") or None,
    }


def _echo(f: dict) -> str:
    parts: list[str] = []
    if f["status"]:
        parts.append(f"status = {f['status']}")
    if f["source"]:
        parts.append(f"source = {f['source']}")
    if f["entry_from"] or f["entry_to"]:
        parts.append(f"entered {f['entry_from'] or '…'} to {f['entry_to'] or '…'}")
    if f["search"]:
        parts.append(f"search '{f['search']}'")
    return "Leads — " + ("; ".join(parts) if parts else "no filters (all)")


def _pct(count: int, total: int) -> float:
    return round(100.0 * count / total, 1) if total else 0.0


async def _breakdown(
    session: AsyncSession, label_expr: str, where_sql: str, params: dict, total: int
) -> list[dict]:
    rows = (await session.execute(text(
        f"SELECT {label_expr} AS label, COUNT(*) AS n FROM leads "
        f"WHERE {where_sql} GROUP BY 1 ORDER BY n DESC LIMIT 15"  # noqa: S608
    ), params)).mappings().all()
    return [{"label": r["label"], "count": int(r["n"]), "pct": _pct(int(r["n"]), total)} for r in rows]


async def _aggregate(session: AsyncSession, f: dict) -> dict:
    where_sql, params = build_lead_where(**f)
    total = int((await session.execute(text(
        f"SELECT COUNT(*) FROM leads WHERE {where_sql}"  # noqa: S608
    ), params)).scalar() or 0)
    if total == 0:
        return {"row_count": 0, "breakdowns": {}, "series": None, "extras": {}}

    by_status = await _breakdown(session, "COALESCE(LOWER(status), 'unknown')", where_sql, params, total)
    by_source = await _breakdown(session, "COALESCE(LOWER(source), 'unknown')", where_sql, params, total)

    series_rows = (await session.execute(text(
        f"SELECT date_trunc('week', entry_date)::date AS week_start, COUNT(*) AS n "
        f"FROM leads WHERE {where_sql} GROUP BY 1 ORDER BY 1"  # noqa: S608
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
        "breakdowns": {"status": by_status, "source": by_source},
        "series": series,
        "extras": {},
    }


register(Surface(
    key="leads",
    label="leads",
    describe=_DESCRIBE,
    parse_filters=_parse_filters,
    echo=_echo,
    aggregate=_aggregate,
))
