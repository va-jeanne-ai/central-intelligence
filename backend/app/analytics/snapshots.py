"""Snapshot compute — run every registered metric and persist a timeseries point.

Generalizes the ``tasks/market_signals.py`` pattern: recompute each metric from the
real tables (no heuristics), then upsert one ``metric_snapshots`` row per
(metric, window) for today. Idempotent per day via the unique constraint.

Pure-data contract: a snapshot's ``value`` is whatever the metric's SQL returns over
the window; ``sample_size`` is the row count it rests on (so the trend/recommendation
layer can refuse to draw conclusions from tiny samples).

Sync (SQLAlchemy Session) so it runs both inside Celery and in scripts/tests.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.analytics.registry import Metric, all_metrics, metrics_for_area

logger = logging.getLogger(__name__)

# The lookback windows every metric is captured over. "all" → :since is NULL.
WINDOWS: dict[str, int | None] = {
    "7d": 7,
    "30d": 30,
    "90d": 90,
    "all": None,
}

# Upsert one snapshot row, idempotent per (metric_key, window, scope, captured_date).
# Re-running the same day UPDATES the value (a later run with more data wins).
# ``scope`` is parameterized (rather than a literal 'global') so the same statement
# serves both the global upsert and the per-rep fan-out below.
_UPSERT = text(
    # "window" is a reserved word in Postgres — must be quoted everywhere it appears.
    """
    INSERT INTO metric_snapshots
        (metric_key, area, "window", scope, value, sample_size, unit, captured_date, captured_at)
    VALUES
        (:metric_key, :area, :window, :scope, :value, :sample_size, :unit, CURRENT_DATE, now())
    ON CONFLICT (metric_key, "window", scope, captured_date) DO UPDATE SET
        value       = EXCLUDED.value,
        sample_size = EXCLUDED.sample_size,
        captured_at = EXCLUDED.captured_at
    """
)

# Reps to exclude from every rep-scoped fan-out (offboarded — no longer relevant to
# per-rep coaching/monitoring surfaces even if their historical rows still exist).
_TERMINATED_REPS = text(
    "SELECT rep_id FROM sales_reps WHERE status = 'terminated'"
)


def _compute_one(db: Session, metric: Metric, since: datetime | None) -> tuple[float, int]:
    """Run a metric's SQL for one window. Returns (value, sample_size)."""
    row = db.execute(metric.sql, {"since": since}).mappings().first()
    if row is None:
        return 0.0, 0
    return float(row["value"] or 0), int(row["sample_size"] or 0)


def _compute_rep_rows(
    db: Session, metric: Metric, since: datetime | None, excluded_reps: set[str]
) -> list[tuple[str, float, int]]:
    """Run a metric's ``rep_sql`` for one window. Returns [(rep_id, value, sample_size)].

    Rows for terminated reps are dropped here rather than in SQL, so the fan-out
    exclusion list is loaded once per ``compute_snapshots`` call (see caller) instead
    of re-querying ``sales_reps`` per metric/window.
    """
    if metric.rep_sql is None:
        return []
    rows = db.execute(metric.rep_sql, {"since": since}).mappings().all()
    return [
        (row["rep_id"], float(row["value"] or 0), int(row["sample_size"] or 0))
        for row in rows
        if row["rep_id"] not in excluded_reps
    ]


def _load_terminated_reps(db: Session) -> set[str]:
    return {row[0] for row in db.execute(_TERMINATED_REPS).all()}


def compute_snapshots(db: Session, area: str | None = None) -> dict:
    """Compute + upsert snapshots for every metric × window (+ per-rep, where declared).

    ``area`` optionally restricts to one area (e.g. "sales"). Returns a summary with
    per-metric values for the 30d window (handy for logs / verification), plus a
    per-rep row count for metrics that declare ``rep_sql``.

    Reps whose ``sales_reps.status == 'terminated'`` are excluded from every
    rep-scoped fan-out (loaded once here, not per metric/window).
    """
    metrics = metrics_for_area(area) if area else all_metrics()
    now = datetime.now(tz=timezone.utc)
    terminated_reps = _load_terminated_reps(db)

    written = 0
    rep_rows_written = 0
    summary: list[dict] = []
    for metric in metrics:
        per_window: dict[str, float] = {}
        rep_counts_by_window: dict[str, int] = {}
        for window, days in WINDOWS.items():
            since = None if days is None else now - timedelta(days=days)
            value, sample = _compute_one(db, metric, since)
            db.execute(
                _UPSERT,
                {
                    "metric_key": metric.key,
                    "area": metric.area,
                    "window": window,
                    "scope": "global",
                    "value": value,
                    "sample_size": sample,
                    "unit": metric.unit,
                },
            )
            written += 1
            per_window[window] = value

            if metric.rep_sql is not None:
                rep_rows = _compute_rep_rows(db, metric, since, terminated_reps)
                for rep_id, rep_value, rep_sample in rep_rows:
                    db.execute(
                        _UPSERT,
                        {
                            "metric_key": metric.key,
                            "area": metric.area,
                            "window": window,
                            "scope": f"rep:{rep_id}",
                            "value": rep_value,
                            "sample_size": rep_sample,
                            "unit": metric.unit,
                        },
                    )
                    written += 1
                    rep_rows_written += 1
                rep_counts_by_window[window] = len(rep_rows)

        summary_entry = {
            "metric": metric.key,
            "label": metric.label,
            "unit": metric.unit,
            "by_window": per_window,
        }
        if metric.rep_sql is not None:
            summary_entry["rep_rows_by_window"] = rep_counts_by_window
        summary.append(summary_entry)

    db.commit()
    logger.info(
        "compute_snapshots: wrote %d snapshot rows (%d rep-scoped) across %d metrics",
        written,
        rep_rows_written,
        len(metrics),
    )
    return {
        "metrics": len(metrics),
        "rows_written": written,
        "rep_rows_written": rep_rows_written,
        "computed_at": now.isoformat(),
        "summary": summary,
    }
