"""Analytics API — the data-intelligence engine's read surface.

Serves the shared engine to BOTH the Insights dashboard and CI chat:
  GET  /analytics/metrics          — latest snapshot per metric (current values)
  GET  /analytics/trends           — verdict per metric (improving/declining/flat/…)
  GET  /analytics/recommendations  — active data-cited recommendations
  GET  /analytics/team             — per-rep metric blocks + trend verdicts + open findings
  GET  /analytics/metrics/{key}/history — a metric's snapshot timeseries (for charts)
  GET  /analytics/metrics/{key}/history-asof — rolling history derived live from source
                                     tables (no snapshots needed; read-only)
  POST /analytics/refresh          — recompute snapshots + recommendations on demand
  PATCH /analytics/recommendations/{id} — advance a recommendation's lifecycle status

Everything here is data-derived. The numbers come from metric_snapshots /
recommendations (populated by the snapshot task) and the registry — no heuristics.

``scope`` on /trends and /recommendations: optional, defaults to "global" (byte-
identical to the pre-scope behavior). Pass "rep:<rep_id>" to scope either endpoint
to one rep's series/findings instead. Validated via ``team.validate_scope`` — a
malformed value 422s rather than silently matching nothing.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.asof import build_asof_history_sql
from app.analytics.registry import all_metrics, get_metric
from app.analytics.team import LatestSnapshot, RepRow, assemble_team_snapshot, validate_scope
from app.database import get_session

logger = logging.getLogger(__name__)

router = APIRouter(tags=["analytics"], prefix="/analytics")

_VALID_WINDOWS = {"7d", "30d", "90d", "all"}
_VALID_STATUS = {"open", "ack", "acted", "resolved"}


# ─── Response models ────────────────────────────────────────────────────────────

class MetricValue(BaseModel):
    metric_key: str
    area: str
    label: str
    unit: str
    higher_is_better: bool
    window: str
    value: float | None
    sample_size: int | None
    captured_date: str | None


class TrendItem(BaseModel):
    metric_key: str
    area: str
    label: str
    unit: str
    window: str
    verdict: str
    latest_value: float | None
    baseline_value: float | None
    rel_change: float | None
    higher_is_better: bool
    reason: str


class RecommendationItem(BaseModel):
    id: int
    metric_key: str
    area: str
    window: str
    verdict: str
    severity: str
    title: str
    body: str
    evidence: dict
    status: str
    updated_at: str | None


class RepMetricBlock(BaseModel):
    """One rep's latest value + trend verdict for one rep-scoped metric.

    ``value``/``sample_size`` are ``None`` when the rep has no snapshot row for
    this metric/window yet — paired with ``verdict="insufficient_data"``. Never
    a fabricated 0.
    """

    metric_key: str
    label: str
    area: str
    unit: str
    higher_is_better: bool
    value: float | None
    sample_size: int | None
    verdict: str
    rel_change: float | None
    baseline_value: float | None
    reason: str


class TeamRepEntry(BaseModel):
    rep_id: str
    full_name: str
    role: str | None
    status: str
    metrics: dict[str, RepMetricBlock]
    recommendations: list[RecommendationItem]


class TeamRollup(BaseModel):
    total_outbound: float
    open_strikes: float
    active_reps: int
    total_reps: int


class TeamAnalyticsResponse(BaseModel):
    window: str
    reps: list[TeamRepEntry]
    rollup: TeamRollup


class OverallInsightResponse(BaseModel):
    """The latest company-level health assessment (see analytics/overall_insight.py)."""

    insight_date: str
    health_verdict: str  # healthy | watch | at_risk
    narrative: str
    key_shifts: list[str]
    previous_date: str | None
    model: str
    generated_at: str


class WeeklyDigestResponse(BaseModel):
    """The latest weekly digest (see analytics/weekly_digest.py) — shares the
    ``overall_insights`` table with the daily assessment, distinguished by
    ``period='weekly'``."""

    week_start: str
    week_end: str | None
    health_verdict: str  # healthy | watch | at_risk
    narrative: str
    key_shifts: list[str]
    previous_week_start: str | None
    model: str
    generated_at: str


# ─── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("/metrics", response_model=list[MetricValue], summary="Latest value per metric")
async def list_metrics(
    window: str = Query("30d"),
    area: str | None = Query(None),
    session: AsyncSession = Depends(get_session),
):
    """The current value of every registered metric (latest snapshot in the window)."""
    if window not in _VALID_WINDOWS:
        raise HTTPException(422, f"window must be one of {sorted(_VALID_WINDOWS)}")

    metrics = [m for m in all_metrics() if area is None or m.area == area]
    out: list[MetricValue] = []
    for m in metrics:
        row = (await session.execute(text(
            """
            SELECT value, sample_size, captured_date
            FROM metric_snapshots
            WHERE metric_key = :k AND "window" = :w AND scope = 'global'
            ORDER BY captured_date DESC LIMIT 1
            """
        ), {"k": m.key, "w": window})).mappings().first()
        out.append(MetricValue(
            metric_key=m.key, area=m.area, label=m.label, unit=m.unit,
            higher_is_better=m.higher_is_better, window=window,
            value=(float(row["value"]) if row else None),
            sample_size=(int(row["sample_size"]) if row else None),
            captured_date=(row["captured_date"].isoformat() if row else None),
        ))
    return out


@router.get("/trends", response_model=list[TrendItem], summary="Verdict per metric")
async def list_trends(
    window: str = Query("30d"),
    area: str | None = Query(None),
    scope: str = Query("global", description="'global' (default) or 'rep:<rep_id>'."),
    session: AsyncSession = Depends(get_session),
):
    """Compute the trend verdict for each metric from its snapshot history (pure stats).

    ``scope`` defaults to "global" — identical behavior to before this param existed.
    """
    if window not in _VALID_WINDOWS:
        raise HTTPException(422, f"window must be one of {sorted(_VALID_WINDOWS)}")
    if not validate_scope(scope):
        raise HTTPException(422, "scope must be 'global' or 'rep:<rep_id>'")

    # Reuse the engine's evaluation logic over rows we fetch via the async session.
    from app.analytics.trends import evaluate  # local import: engine is sync-first

    metrics = [m for m in all_metrics() if area is None or m.area == area]
    out: list[TrendItem] = []
    for m in metrics:
        rows = (await session.execute(text(
            """
            SELECT value, sample_size, captured_date
            FROM metric_snapshots
            WHERE metric_key = :k AND "window" = :w AND scope = :scope
            ORDER BY captured_date ASC
            """
        ), {"k": m.key, "w": window, "scope": scope})).mappings().all()
        t = evaluate(m, [dict(r) for r in rows], window)
        out.append(TrendItem(
            metric_key=t.metric_key, area=t.area, label=t.label, unit=t.unit,
            window=t.window, verdict=t.verdict, latest_value=t.latest_value,
            baseline_value=t.baseline_value, rel_change=t.rel_change,
            higher_is_better=t.higher_is_better, reason=t.reason,
        ))
    return out


@router.get("/recommendations", response_model=list[RecommendationItem], summary="Active recommendations")
async def list_recommendations(
    status: str | None = Query(None, description="Filter by lifecycle status."),
    area: str | None = Query(None),
    scope: str = Query("global", description="'global' (default) or 'rep:<rep_id>'."),
    session: AsyncSession = Depends(get_session),
):
    """Data-cited recommendations. Defaults to the non-resolved, global findings —
    identical behavior to before ``scope`` existed. Pass ``scope='rep:<rep_id>'`` to
    see one rep's findings instead."""
    from app.analytics.recommend import fetch_recommendation_rows

    if not validate_scope(scope):
        raise HTTPException(422, "scope must be 'global' or 'rep:<rep_id>'")

    rows = await fetch_recommendation_rows(session, status=status, area=area, scope=scope)
    return [
        RecommendationItem(
            id=r["id"], metric_key=r["metric_key"], area=r["area"], window=r["window"],
            verdict=r["verdict"], severity=r["severity"], title=r["title"], body=r["body"],
            evidence=r["evidence"], status=r["status"],
            updated_at=r["updated_at"].isoformat() if r["updated_at"] else None,
        )
        for r in rows
    ]


@router.get("/team", response_model=TeamAnalyticsResponse, summary="Per-rep metric blocks + trends")
async def team_analytics(
    window: str = Query("30d"),
    session: AsyncSession = Depends(get_session),
):
    """Every non-terminated rep, with a per-metric block (latest value + trend
    verdict) for each rep-scoped metric, plus their open recommendations and a
    small team-level rollup.

    Reads the roster + latest snapshots via this (async) session, then reuses
    ``trends.trend_for`` — which is sync — over a short-lived sync session, the
    same pattern ``POST /analytics/refresh`` already uses for the sync engine.
    """
    if window not in _VALID_WINDOWS:
        raise HTTPException(422, f"window must be one of {sorted(_VALID_WINDOWS)}")

    from app.analytics.recommend import fetch_recommendation_rows
    from app.analytics.team import rep_scoped_metrics
    from app.tasks.db import make_sync_session

    rep_rows = (await session.execute(text(
        """
        SELECT rep_id, full_name, role, status
        FROM sales_reps
        WHERE status <> 'terminated'
        ORDER BY full_name
        """
    ))).mappings().all()
    reps = [
        RepRow(rep_id=r["rep_id"], full_name=r["full_name"], role=r["role"], status=r["status"])
        for r in rep_rows
    ]

    metrics = rep_scoped_metrics()
    snapshots_by_rep_and_metric: dict[tuple[str, str], LatestSnapshot] = {}
    if metrics:
        metric_keys = [m.key for m in metrics]
        snap_rows = (await session.execute(text(
            """
            SELECT DISTINCT ON (metric_key, scope) metric_key, scope, value, sample_size
            FROM metric_snapshots
            WHERE metric_key = ANY(:keys) AND "window" = :w AND scope LIKE 'rep:%'
            ORDER BY metric_key, scope, captured_date DESC
            """
        ), {"keys": metric_keys, "w": window})).mappings().all()
        for r in snap_rows:
            rep_id = r["scope"].removeprefix("rep:")
            snapshots_by_rep_and_metric[(rep_id, r["metric_key"])] = LatestSnapshot(
                value=float(r["value"]), sample_size=int(r["sample_size"])
            )

    recommendations_by_rep: dict[str, list[dict]] = {}
    for rep in reps:
        rec_rows = await fetch_recommendation_rows(session, scope=f"rep:{rep.rep_id}")
        recommendations_by_rep[rep.rep_id] = [
            {
                "id": r["id"], "metric_key": r["metric_key"], "area": r["area"],
                "window": r["window"], "verdict": r["verdict"], "severity": r["severity"],
                "title": r["title"], "body": r["body"], "evidence": r["evidence"],
                "status": r["status"],
                "updated_at": r["updated_at"].isoformat() if r["updated_at"] else None,
            }
            for r in rec_rows
        ]

    db = make_sync_session()
    try:
        payload = assemble_team_snapshot(
            db,
            reps=reps,
            window=window,
            snapshots_by_rep_and_metric=snapshots_by_rep_and_metric,
            recommendations_by_rep=recommendations_by_rep,
        )
    finally:
        db.close()

    return TeamAnalyticsResponse(**payload)


@router.get("/metrics/{metric_key}/history", summary="A metric's snapshot timeseries")
async def metric_history(
    metric_key: str,
    window: str = Query("30d"),
    session: AsyncSession = Depends(get_session),
):
    """The full snapshot series for one metric/window — drives sparkline/trend charts."""
    if get_metric(metric_key) is None:
        raise HTTPException(404, "Unknown metric")
    if window not in _VALID_WINDOWS:
        raise HTTPException(422, f"window must be one of {sorted(_VALID_WINDOWS)}")
    rows = (await session.execute(text(
        """
        SELECT value, sample_size, captured_date
        FROM metric_snapshots
        WHERE metric_key = :k AND "window" = :w AND scope = 'global'
        ORDER BY captured_date ASC
        """
    ), {"k": metric_key, "w": window})).mappings().all()
    return {
        "metric_key": metric_key,
        "window": window,
        "points": [
            {
                "value": float(r["value"]),
                "sample_size": int(r["sample_size"]),
                "date": r["captured_date"].isoformat(),
            }
            for r in rows
        ],
    }


# Rolling-window width (days) per window label. "all" isn't a rolling concept, so
# a derived history falls back to the 30d roll for it.
_WINDOW_DAYS = {"7d": 7, "30d": 30, "90d": 90, "all": 30}


@router.get(
    "/metrics/{metric_key}/history-asof",
    summary="A metric's rolling history derived as-of each past day",
)
async def metric_history_asof(
    metric_key: str,
    window: str = Query("30d", description="Default rolling width when `roll` is omitted: 7d | 30d | 90d | all."),
    days: int = Query(90, ge=2, le=730, description="How many days back the series spans (the X-axis range)."),
    roll: int | None = Query(
        None, ge=1, le=365,
        description="Rolling-window width in days per point. Overrides the `window`-derived default.",
    ),
    session: AsyncSession = Depends(get_session),
):
    """A true rolling timeseries computed live from the source tables — no snapshots.

    Two independent knobs:
      • ``days`` — the span shown (how far back the X-axis goes).
      • ``roll`` — the rolling-window width each point averages over. If omitted it
        falls back to the width implied by ``window`` (7d→7, 30d→30, 90d→90, all→30).

    For each of the last ``days`` calendar days, the metric is recomputed over the
    ``roll``-day window ending that day. Read-only: nothing is written. This lets the
    charts show a real multi-month trend even when the snapshot job has rarely run.

    Metrics whose computation spans multiple tables (no single date column) don't
    support derived history and return an empty series rather than an error.
    """
    metric = get_metric(metric_key)
    if metric is None:
        raise HTTPException(404, "Unknown metric")
    if window not in _VALID_WINDOWS:
        raise HTTPException(422, f"window must be one of {sorted(_VALID_WINDOWS)}")

    if not metric.has_asof:
        # Honest empty series — the frontend already renders a clear empty state.
        return {"metric_key": metric_key, "window": window, "points": []}

    window_days = roll if roll is not None else _WINDOW_DAYS[window]

    rows = (
        await session.execute(
            build_asof_history_sql(metric),
            {
                "days": days,
                "window_days": window_days,
            },
        )
    ).mappings().all()

    return {
        "metric_key": metric_key,
        "window": window,
        "points": [
            {
                "value": float(r["value"]),
                "sample_size": int(r["sample_size"]),
                "date": r["captured_date"].isoformat(),
            }
            for r in rows
        ],
    }


@router.patch("/recommendations/{rec_id}", response_model=RecommendationItem, summary="Advance status")
async def update_recommendation(
    rec_id: int,
    status: str = Query(..., description="open | ack | acted | resolved"),
    session: AsyncSession = Depends(get_session),
):
    """Move a recommendation along its lifecycle (open → acknowledged → acted → resolved)."""
    if status not in _VALID_STATUS:
        raise HTTPException(422, f"status must be one of {sorted(_VALID_STATUS)}")
    row = (await session.execute(text(
        """
        UPDATE recommendations SET status = :s, updated_at = now()
        WHERE id = :id
        RETURNING id, metric_key, area, "window", verdict, severity, title, body,
                  evidence, status, updated_at
        """
    ), {"s": status, "id": rec_id})).mappings().first()
    await session.commit()
    if row is None:
        raise HTTPException(404, "Recommendation not found")
    return RecommendationItem(
        id=row["id"], metric_key=row["metric_key"], area=row["area"], window=row["window"],
        verdict=row["verdict"], severity=row["severity"], title=row["title"], body=row["body"],
        evidence=row["evidence"], status=row["status"],
        updated_at=row["updated_at"].isoformat() if row["updated_at"] else None,
    )


@router.post("/refresh", summary="Recompute snapshots + recommendations now")
async def refresh(session: AsyncSession = Depends(get_session)):
    """On-demand recompute (the daily task does this automatically). Sync engine over a
    short-lived sync session so the dashboard can force a refresh."""
    from app.analytics.recommend import generate_recommendations
    from app.analytics.snapshots import compute_snapshots
    from app.tasks.db import make_sync_session

    db = make_sync_session()
    try:
        snap = compute_snapshots(db)
        recs = generate_recommendations(db)
    finally:
        db.close()
    return {"snapshots_written": snap["rows_written"], "active_recommendations": recs["active"]}


# ===================================================================
# Overall Insight — company-level narrative health assessment
# ===================================================================

@router.get(
    "/overall-insight",
    response_model=OverallInsightResponse,
    summary="Latest company-level health assessment",
)
async def get_overall_insight(
    response: Response,
    session: AsyncSession = Depends(get_session),
):
    """The most recent overall insight, or 204 when none has been generated yet."""
    row = (await session.execute(text(
        """
        SELECT o.insight_date, o.health_verdict, o.narrative, o.key_shifts, o.model,
               o.generated_at, p.insight_date AS previous_date
        FROM overall_insights o
        LEFT JOIN overall_insights p ON p.id = o.previous_insight_id
        ORDER BY o.insight_date DESC
        LIMIT 1
        """
    ))).mappings().first()

    if row is None:
        response.status_code = 204
        return None

    return OverallInsightResponse(
        insight_date=row["insight_date"].isoformat(),
        health_verdict=row["health_verdict"],
        narrative=row["narrative"],
        key_shifts=list(row["key_shifts"] or []),
        previous_date=(row["previous_date"].isoformat() if row["previous_date"] else None),
        model=row["model"],
        generated_at=row["generated_at"].isoformat(),
    )


@router.post(
    "/overall-insight/refresh",
    response_model=OverallInsightResponse,
    summary="Generate (or regenerate) today's overall insight — one paid LLM call",
)
async def refresh_overall_insight(
    genesis: bool = Query(False, description="Ignore prior assessments; synthesize from scratch."),
):
    """Trigger a fresh synthesis. This makes ONE Claude call (unless mock_mode is on).

    Runs the sync generation over a short-lived sync session, mirroring POST /refresh.
    """
    from app.analytics.overall_insight import generate_overall_insight
    from app.tasks.db import make_sync_session

    db = make_sync_session()
    try:
        result = generate_overall_insight(db, force_genesis=genesis)
    finally:
        db.close()
    return OverallInsightResponse(**result)


# ===================================================================
# Weekly Digest — a weekly synthesis of the statistical engine's output
# ===================================================================

@router.get(
    "/weekly-digest",
    response_model=WeeklyDigestResponse,
    summary="Latest weekly digest",
)
async def get_weekly_digest(
    response: Response,
    session: AsyncSession = Depends(get_session),
):
    """The most recent weekly digest, or 204 when none has been generated yet."""
    row = (await session.execute(text(
        """
        SELECT o.insight_date AS week_start, o.period_end AS week_end, o.health_verdict,
               o.narrative, o.key_shifts, o.model, o.generated_at,
               p.insight_date AS previous_week_start
        FROM overall_insights o
        LEFT JOIN overall_insights p ON p.id = o.previous_insight_id
        WHERE o.period = 'weekly'
        ORDER BY o.insight_date DESC
        LIMIT 1
        """
    ))).mappings().first()

    if row is None:
        response.status_code = 204
        return None

    return WeeklyDigestResponse(
        week_start=row["week_start"].isoformat(),
        week_end=(row["week_end"].isoformat() if row["week_end"] else None),
        health_verdict=row["health_verdict"],
        narrative=row["narrative"],
        key_shifts=list(row["key_shifts"] or []),
        previous_week_start=(
            row["previous_week_start"].isoformat() if row["previous_week_start"] else None
        ),
        model=row["model"],
        generated_at=row["generated_at"].isoformat(),
    )


@router.post(
    "/weekly-digest/refresh",
    response_model=WeeklyDigestResponse,
    summary="Generate (or regenerate) this week's digest — at most one paid LLM call",
)
async def refresh_weekly_digest():
    """Trigger a fresh weekly synthesis. Makes at most ONE Claude call (unless
    mock_mode is on), and no-ops (204) if there's no data for the week at all.

    Runs the sync generation over a short-lived sync session, mirroring
    POST /overall-insight/refresh.
    """
    from app.analytics.weekly_digest import generate_weekly_digest
    from app.tasks.db import make_sync_session

    db = make_sync_session()
    try:
        result = generate_weekly_digest(db)
    finally:
        db.close()

    if result is None:
        return Response(status_code=204)
    return WeeklyDigestResponse(**result)
