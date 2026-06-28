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
_UPSERT = text(
    # "window" is a reserved word in Postgres — must be quoted everywhere it appears.
    """
    INSERT INTO metric_snapshots
        (metric_key, area, "window", scope, value, sample_size, unit, captured_date, captured_at)
    VALUES
        (:metric_key, :area, :window, 'global', :value, :sample_size, :unit, CURRENT_DATE, now())
    ON CONFLICT (metric_key, "window", scope, captured_date) DO UPDATE SET
        value       = EXCLUDED.value,
        sample_size = EXCLUDED.sample_size,
        captured_at = EXCLUDED.captured_at
    """
)


def _compute_one(db: Session, metric: Metric, since: datetime | None) -> tuple[float, int]:
    """Run a metric's SQL for one window. Returns (value, sample_size)."""
    row = db.execute(metric.sql, {"since": since}).mappings().first()
    if row is None:
        return 0.0, 0
    return float(row["value"] or 0), int(row["sample_size"] or 0)


def compute_snapshots(db: Session, area: str | None = None) -> dict:
    """Compute + upsert snapshots for every metric × window.

    ``area`` optionally restricts to one area (e.g. "sales"). Returns a summary with
    per-metric values for the 30d window (handy for logs / verification).
    """
    metrics = metrics_for_area(area) if area else all_metrics()
    now = datetime.now(tz=timezone.utc)

    written = 0
    summary: list[dict] = []
    for metric in metrics:
        per_window: dict[str, float] = {}
        for window, days in WINDOWS.items():
            since = None if days is None else now - timedelta(days=days)
            value, sample = _compute_one(db, metric, since)
            db.execute(
                _UPSERT,
                {
                    "metric_key": metric.key,
                    "area": metric.area,
                    "window": window,
                    "value": value,
                    "sample_size": sample,
                    "unit": metric.unit,
                },
            )
            written += 1
            per_window[window] = value
        summary.append(
            {
                "metric": metric.key,
                "label": metric.label,
                "unit": metric.unit,
                "by_window": per_window,
            }
        )

    db.commit()
    logger.info("compute_snapshots: wrote %d snapshot rows across %d metrics", written, len(metrics))
    return {
        "metrics": len(metrics),
        "rows_written": written,
        "computed_at": now.isoformat(),
        "summary": summary,
    }
