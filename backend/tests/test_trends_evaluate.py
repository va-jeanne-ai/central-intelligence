"""Unit tests for the pure trend-verdict logic (app.analytics.trends.evaluate).

Self-contained: runs with plain `python -m tests.test_trends_evaluate` (pytest is
not installed in this env). Covers the verdict decision purely from synthetic
snapshot rows — no DB, no Postgres. ``evaluate`` (formerly ``_evaluate``) is the
public entry point; ``trend_for`` / ``all_trends`` just fetch rows and delegate
to it, so exercising it directly covers the arithmetic exhaustively.
"""

from __future__ import annotations

from datetime import date

from app.analytics.registry import Metric, all_metrics, get_metric
from app.analytics.trends import MIN_REL_CHANGE, MIN_SAMPLE, evaluate

_failures: list[str] = []


def check(name: str, cond: bool) -> None:
    if cond:
        print(f"  ok   {name}")
    else:
        print(f"  FAIL {name}")
        _failures.append(name)


# ─── Synthetic metrics (mirror the registry's shape without touching the DB) ────

HIGHER_IS_BETTER = Metric(
    key="test.higher_is_better",
    area="sales",
    label="Test Higher-Is-Better",
    unit="ratio",
    higher_is_better=True,
    sql=get_metric("sales.lead_to_close_rate").sql,  # reuse a real SQL clause; unused here
)

LOWER_IS_BETTER = Metric(
    key="test.lower_is_better",
    area="fulfillment",
    label="Test Lower-Is-Better",
    unit="count",
    higher_is_better=False,
    sql=get_metric("fulfillment.open_coaching_strikes").sql,
)


def row(value: float, sample_size: int, d: date) -> dict:
    return {"value": value, "sample_size": sample_size, "captured_date": d}


D1 = date(2026, 6, 1)
D2 = date(2026, 6, 30)


# ─── Empty / single-row series ───────────────────────────────────────────────


def test_empty_series_is_insufficient_data() -> None:
    t = evaluate(HIGHER_IS_BETTER, [], "30d")
    check("empty verdict", t.verdict == "insufficient_data")
    check("empty latest_value None", t.latest_value is None)
    check("empty baseline_value None", t.baseline_value is None)
    check("empty rel_change None", t.rel_change is None)
    check("empty latest_date None", t.latest_date is None)
    check("empty reason mentions count", "0" in t.reason)


def test_single_row_is_insufficient_data() -> None:
    rows = [row(0.5, MIN_SAMPLE, D1)]
    t = evaluate(HIGHER_IS_BETTER, rows, "30d")
    check("single-row verdict", t.verdict == "insufficient_data")
    check("single-row latest_value set", t.latest_value == 0.5)
    check("single-row baseline_value still None", t.baseline_value is None)
    check("single-row latest_sample set", t.latest_sample == MIN_SAMPLE)
    check("single-row baseline_sample None", t.baseline_sample is None)
    check("single-row latest_date set", t.latest_date == D1.isoformat())


# ─── Sample-size gating ───────────────────────────────────────────────────────


def test_small_sample_is_insufficient_data() -> None:
    rows = [row(0.3, MIN_SAMPLE - 1, D1), row(0.5, MIN_SAMPLE - 1, D2)]
    t = evaluate(HIGHER_IS_BETTER, rows, "30d")
    check("small-sample verdict", t.verdict == "insufficient_data")
    check("small-sample rel_change None (not computed)", t.rel_change is None)
    check("small-sample keeps both values", t.baseline_value == 0.3 and t.latest_value == 0.5)


def test_one_side_small_sample_is_insufficient_data() -> None:
    # Only the latest side is thin — still gated, since either side < MIN_SAMPLE fails.
    rows = [row(0.3, MIN_SAMPLE, D1), row(0.5, MIN_SAMPLE - 1, D2)]
    t = evaluate(HIGHER_IS_BETTER, rows, "30d")
    check("one-side-thin verdict", t.verdict == "insufficient_data")


def test_sample_exactly_at_threshold_is_sufficient() -> None:
    # Exactly MIN_SAMPLE on both sides should NOT be gated (>= MIN_SAMPLE passes).
    rows = [row(0.30, MIN_SAMPLE, D1), row(0.50, MIN_SAMPLE, D2)]
    t = evaluate(HIGHER_IS_BETTER, rows, "30d")
    check("at-threshold verdict is not insufficient_data", t.verdict != "insufficient_data")


# ─── Material-change threshold (flat vs. moved) ──────────────────────────────


def test_small_change_reads_flat() -> None:
    # (0.52 - 0.50) / 0.50 = 4% < MIN_REL_CHANGE (5%) → flat.
    rows = [row(0.50, MIN_SAMPLE, D1), row(0.52, MIN_SAMPLE, D2)]
    t = evaluate(HIGHER_IS_BETTER, rows, "30d")
    check("small change verdict", t.verdict == "flat")
    check("small change rel_change computed", t.rel_change is not None and abs(t.rel_change - 0.04) < 1e-9)


def test_change_just_above_threshold_is_not_flat() -> None:
    # (0.551 - 0.50) / 0.50 = 10.2% >= MIN_REL_CHANGE → moved (improving, higher-is-better).
    rows = [row(0.50, MIN_SAMPLE, D1), row(0.551, MIN_SAMPLE, D2)]
    t = evaluate(HIGHER_IS_BETTER, rows, "30d")
    check("above-threshold verdict is not flat", t.verdict != "flat")


def test_change_exactly_at_threshold_is_not_flat() -> None:
    # abs(rel) < MIN_REL_CHANGE is the flat gate, so exactly MIN_REL_CHANGE is NOT flat.
    rows = [row(0.50, MIN_SAMPLE, D1), row(0.525, MIN_SAMPLE, D2)]  # +5% exactly
    t = evaluate(HIGHER_IS_BETTER, rows, "30d")
    check("exactly-at-threshold is not flat", t.verdict == "improving")


# ─── Direction semantics ─────────────────────────────────────────────────────


def test_higher_is_better_rise_is_improving() -> None:
    rows = [row(0.40, MIN_SAMPLE, D1), row(0.60, MIN_SAMPLE, D2)]  # +50%
    t = evaluate(HIGHER_IS_BETTER, rows, "30d")
    check("higher-is-better rise → improving", t.verdict == "improving")


def test_higher_is_better_fall_is_declining() -> None:
    rows = [row(0.60, MIN_SAMPLE, D1), row(0.40, MIN_SAMPLE, D2)]  # -33%
    t = evaluate(HIGHER_IS_BETTER, rows, "30d")
    check("higher-is-better fall → declining", t.verdict == "declining")


def test_lower_is_better_fall_is_improving() -> None:
    # e.g. open coaching strikes dropping is GOOD.
    rows = [row(10, MIN_SAMPLE, D1), row(4, MIN_SAMPLE, D2)]  # -60%
    t = evaluate(LOWER_IS_BETTER, rows, "30d")
    check("lower-is-better fall → improving", t.verdict == "improving")
    check("lower-is-better reason mentions lower-is-better", "lower is better" in t.reason)


def test_lower_is_better_rise_is_declining() -> None:
    rows = [row(4, MIN_SAMPLE, D1), row(10, MIN_SAMPLE, D2)]  # +150%
    t = evaluate(LOWER_IS_BETTER, rows, "30d")
    check("lower-is-better rise → declining", t.verdict == "declining")


# ─── Zero-baseline edge cases ─────────────────────────────────────────────────


def test_zero_baseline_zero_latest_is_flat() -> None:
    rows = [row(0.0, MIN_SAMPLE, D1), row(0.0, MIN_SAMPLE, D2)]
    t = evaluate(HIGHER_IS_BETTER, rows, "30d")
    check("zero→zero rel_change is 0.0", t.rel_change == 0.0)
    check("zero→zero verdict is flat", t.verdict == "flat")


def test_zero_baseline_positive_latest_is_improving_for_higher_is_better() -> None:
    rows = [row(0.0, MIN_SAMPLE, D1), row(5.0, MIN_SAMPLE, D2)]
    t = evaluate(HIGHER_IS_BETTER, rows, "30d")
    check("zero→positive rel_change is +1.0 (full move)", t.rel_change == 1.0)
    check("zero→positive verdict improving (higher-is-better + rise)", t.verdict == "improving")


def test_zero_baseline_positive_latest_is_declining_for_lower_is_better() -> None:
    # e.g. strikes go from 0 to some positive count — adverse for a lower-is-better metric.
    rows = [row(0.0, MIN_SAMPLE, D1), row(5.0, MIN_SAMPLE, D2)]
    t = evaluate(LOWER_IS_BETTER, rows, "30d")
    check("zero→positive verdict declining (lower-is-better + rise)", t.verdict == "declining")


def test_zero_baseline_negative_latest_direction() -> None:
    rows = [row(0.0, MIN_SAMPLE, D1), row(-5.0, MIN_SAMPLE, D2)]
    t = evaluate(HIGHER_IS_BETTER, rows, "30d")
    check("zero→negative rel_change is -1.0", t.rel_change == -1.0)
    check("zero→negative verdict declining (higher-is-better + fall)", t.verdict == "declining")


# ─── Multi-row series: only first vs. last matter (baseline/latest) ──────────


def test_uses_first_and_last_row_not_middle() -> None:
    rows = [
        row(0.30, MIN_SAMPLE, date(2026, 6, 1)),
        row(999.0, MIN_SAMPLE, date(2026, 6, 15)),  # middle row must be ignored
        row(0.60, MIN_SAMPLE, date(2026, 6, 30)),
    ]
    t = evaluate(HIGHER_IS_BETTER, rows, "30d")
    check("baseline is first row", t.baseline_value == 0.30)
    check("latest is last row", t.latest_value == 0.60)
    check("middle row ignored", t.verdict == "improving")


# ─── Result shape / metadata passthrough ─────────────────────────────────────


def test_result_carries_metric_metadata() -> None:
    rows = [row(0.30, MIN_SAMPLE, D1), row(0.60, MIN_SAMPLE, D2)]
    t = evaluate(HIGHER_IS_BETTER, rows, "7d")
    check("metric_key passthrough", t.metric_key == HIGHER_IS_BETTER.key)
    check("area passthrough", t.area == HIGHER_IS_BETTER.area)
    check("label passthrough", t.label == HIGHER_IS_BETTER.label)
    check("unit passthrough", t.unit == HIGHER_IS_BETTER.unit)
    check("window passthrough", t.window == "7d")
    check("higher_is_better passthrough", t.higher_is_better is True)
    check("as_dict works", t.as_dict()["verdict"] == t.verdict)


def main() -> int:
    for fn in (
        test_empty_series_is_insufficient_data,
        test_single_row_is_insufficient_data,
        test_small_sample_is_insufficient_data,
        test_one_side_small_sample_is_insufficient_data,
        test_sample_exactly_at_threshold_is_sufficient,
        test_small_change_reads_flat,
        test_change_just_above_threshold_is_not_flat,
        test_change_exactly_at_threshold_is_not_flat,
        test_higher_is_better_rise_is_improving,
        test_higher_is_better_fall_is_declining,
        test_lower_is_better_fall_is_improving,
        test_lower_is_better_rise_is_declining,
        test_zero_baseline_zero_latest_is_flat,
        test_zero_baseline_positive_latest_is_improving_for_higher_is_better,
        test_zero_baseline_positive_latest_is_declining_for_lower_is_better,
        test_zero_baseline_negative_latest_direction,
        test_uses_first_and_last_row_not_middle,
        test_result_carries_metric_metadata,
    ):
        print(fn.__name__)
        fn()
    if _failures:
        print(f"\n{len(_failures)} FAILED: {_failures}")
        return 1
    print("\nALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
