"""Trend + significance layer — "what works / what needs to change", from the data only.

Reads the ``metric_snapshots`` timeseries and, for each metric, compares the latest
captured value against an earlier baseline. Emits a verdict — purely statistical, no
LLM, no heuristics:

  - improving / declining / flat — direction-aware (a drop in a lower-is-better metric
    like open strikes is *improving*), and gated by a material-change threshold so noise
    reads as ``flat``.
  - insufficient_data — when there isn't enough history, or the sample size behind the
    numbers is too small to trust. We say so rather than guess.

This layer draws the conclusion; downstream the LLM may only *phrase* it.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, asdict
from datetime import date

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.analytics.registry import Metric, all_metrics, get_metric

logger = logging.getLogger(__name__)

# Significance knobs. Conservative on purpose — better to say "insufficient" than guess.
MIN_SAMPLE = 30          # both baseline and latest must rest on ≥ this many rows
MIN_REL_CHANGE = 0.05    # < 5% relative move from baseline → "flat" (noise)
DEFAULT_WINDOW = "30d"   # which metric window to trend (the snapshot's lookback)

Verdict = str  # "improving" | "declining" | "flat" | "insufficient_data"


@dataclass(frozen=True)
class TrendResult:
    metric_key: str
    area: str
    label: str
    unit: str
    window: str
    verdict: Verdict
    latest_value: float | None
    baseline_value: float | None
    latest_sample: int | None
    baseline_sample: int | None
    rel_change: float | None        # signed relative change (latest-baseline)/|baseline|
    higher_is_better: bool
    latest_date: str | None
    baseline_date: str | None
    reason: str                     # plain-language trace of WHY this verdict (data only)

    def as_dict(self) -> dict:
        return asdict(self)


# Latest + earliest snapshot for a metric/window/scope within an optional lookback.
_SERIES = text(
    """
    SELECT value, sample_size, captured_date
    FROM metric_snapshots
    WHERE metric_key = :metric_key
      AND "window"   = :window
      AND scope      = 'global'
    ORDER BY captured_date ASC
    """
)


def _evaluate(metric: Metric, rows: list[dict], window: str) -> TrendResult:
    """Turn a metric's snapshot series into a verdict. Pure arithmetic."""
    base_kwargs = dict(
        metric_key=metric.key,
        area=metric.area,
        label=metric.label,
        unit=metric.unit,
        window=window,
        higher_is_better=metric.higher_is_better,
    )

    # Need at least two distinct days to have a trend.
    if len(rows) < 2:
        return TrendResult(
            **base_kwargs,
            verdict="insufficient_data",
            latest_value=(float(rows[-1]["value"]) if rows else None),
            baseline_value=None,
            latest_sample=(int(rows[-1]["sample_size"]) if rows else None),
            baseline_sample=None,
            rel_change=None,
            latest_date=(rows[-1]["captured_date"].isoformat() if rows else None),
            baseline_date=None,
            reason="Need at least two days of snapshots to compute a trend; "
            f"have {len(rows)}.",
        )

    baseline, latest = rows[0], rows[-1]
    b_val, l_val = float(baseline["value"]), float(latest["value"])
    b_n, l_n = int(baseline["sample_size"]), int(latest["sample_size"])
    b_date = baseline["captured_date"].isoformat()
    l_date = latest["captured_date"].isoformat()

    # Significance gate — refuse to trust thin samples.
    if b_n < MIN_SAMPLE or l_n < MIN_SAMPLE:
        return TrendResult(
            **base_kwargs,
            verdict="insufficient_data",
            latest_value=l_val,
            baseline_value=b_val,
            latest_sample=l_n,
            baseline_sample=b_n,
            rel_change=None,
            latest_date=l_date,
            baseline_date=b_date,
            reason=f"Sample too small to trust (baseline n={b_n}, latest n={l_n}; "
            f"need ≥{MIN_SAMPLE}).",
        )

    # Relative change vs baseline. Guard divide-by-zero (baseline 0 → use absolute move).
    if b_val == 0:
        rel = 0.0 if l_val == 0 else 1.0 * (1 if l_val > 0 else -1)
    else:
        rel = (l_val - b_val) / abs(b_val)

    if abs(rel) < MIN_REL_CHANGE:
        verdict = "flat"
    else:
        rising = l_val > b_val
        # Direction-aware: for lower-is-better metrics, a fall is an improvement.
        improving = rising if metric.higher_is_better else (not rising)
        verdict = "improving" if improving else "declining"

    arrow = "↑" if l_val > b_val else ("↓" if l_val < b_val else "→")
    reason = (
        f"{metric.label} {arrow} from {b_val:.4g} ({b_date}) to {l_val:.4g} ({l_date}), "
        f"{rel:+.1%} over the {window} window "
        f"(n {b_n}→{l_n}; {'higher' if metric.higher_is_better else 'lower'} is better)."
    )
    return TrendResult(
        **base_kwargs,
        verdict=verdict,
        latest_value=l_val,
        baseline_value=b_val,
        latest_sample=l_n,
        baseline_sample=b_n,
        rel_change=rel,
        latest_date=l_date,
        baseline_date=b_date,
        reason=reason,
    )


def trend_for(db: Session, metric_key: str, window: str = DEFAULT_WINDOW) -> TrendResult | None:
    """Compute the verdict for one metric. None if the metric_key is unknown."""
    metric = get_metric(metric_key)
    if metric is None:
        return None
    rows = db.execute(_SERIES, {"metric_key": metric_key, "window": window}).mappings().all()
    return _evaluate(metric, list(rows), window)


def all_trends(db: Session, window: str = DEFAULT_WINDOW, area: str | None = None) -> list[TrendResult]:
    """Verdicts for every registered metric (optionally one area)."""
    metrics = [m for m in all_metrics() if area is None or m.area == area]
    results: list[TrendResult] = []
    for m in metrics:
        rows = db.execute(_SERIES, {"metric_key": m.key, "window": window}).mappings().all()
        results.append(_evaluate(m, list(rows), window))
    return results
