"""Unit tests for the pure freshness verdict logic (app.services.freshness).

Self-contained: runs with plain `python -m tests.test_freshness_classify`
(pytest is not installed in this env). Covers ``classify`` (the fresh/stale/
unknown decision) and the route's ``_roll_up`` — both pure, no DB.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.routes.freshness import _roll_up
from app.services.freshness import GRACE_MULTIPLE, classify

_failures: list[str] = []

NOW = datetime(2026, 6, 28, 12, 0, 0, tzinfo=timezone.utc)


def check(name: str, cond: bool) -> None:
    if cond:
        print(f"  ok   {name}")
    else:
        print(f"  FAIL {name}")
        _failures.append(name)


def test_never_run_is_unknown() -> None:
    verdict, age = classify(None, 60, NOW)
    check("never-run verdict", verdict == "unknown")
    check("never-run age is None", age is None)


def test_recent_is_fresh() -> None:
    # 30 min ago, hourly cadence → well within grace.
    verdict, age = classify(NOW - timedelta(minutes=30), 60, NOW)
    check("recent verdict", verdict == "fresh")
    check("recent age", age is not None and abs(age - 30) < 0.01)


def test_at_grace_boundary_is_fresh() -> None:
    # Exactly GRACE_MULTIPLE intervals old → still fresh (inclusive).
    age_min = 60 * GRACE_MULTIPLE
    verdict, _ = classify(NOW - timedelta(minutes=age_min), 60, NOW)
    check("boundary is fresh (inclusive)", verdict == "fresh")


def test_just_past_grace_is_stale() -> None:
    age_min = 60 * GRACE_MULTIPLE + 1
    verdict, _ = classify(NOW - timedelta(minutes=age_min), 60, NOW)
    check("just past grace is stale", verdict == "stale")


def test_six_hour_cadence_tolerates_longer() -> None:
    # 10h old on a 6h cadence → within 3× (18h), fresh. The same age on an
    # hourly cadence would be stale — proving cadence is respected.
    ten_h = timedelta(hours=10)
    check("10h fresh on 6h cadence", classify(NOW - ten_h, 360, NOW)[0] == "fresh")
    check("10h stale on 1h cadence", classify(NOW - ten_h, 60, NOW)[0] == "stale")


def test_naive_timestamp_treated_as_utc() -> None:
    # A naive datetime must not raise on subtraction.
    naive = (NOW - timedelta(minutes=10)).replace(tzinfo=None)
    verdict, age = classify(naive, 60, NOW)
    check("naive verdict", verdict == "fresh")
    check("naive age ~10", age is not None and abs(age - 10) < 0.01)


def test_roll_up_worst_wins() -> None:
    check("stale dominates", _roll_up(["fresh", "stale", "unknown"]) == "stale")
    check("unknown over fresh", _roll_up(["fresh", "unknown"]) == "unknown")
    check("all fresh", _roll_up(["fresh", "fresh"]) == "fresh")
    check("empty is unknown", _roll_up([]) == "unknown")


def main() -> int:
    for fn in (
        test_never_run_is_unknown,
        test_recent_is_fresh,
        test_at_grace_boundary_is_fresh,
        test_just_past_grace_is_stale,
        test_six_hour_cadence_tolerates_longer,
        test_naive_timestamp_treated_as_utc,
        test_roll_up_worst_wins,
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
