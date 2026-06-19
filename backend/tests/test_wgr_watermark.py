"""Unit tests for the WGR sync watermark resolution (app.tasks.wgr_sync).

Self-contained: runs with plain `python -m tests.test_wgr_watermark` (pytest is
not installed in this env). Covers the pure ``resolve_since`` decision — the
heart of incremental sync — without any DB or Celery.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.tasks.wgr_sync import FORCE_FULL, WATERMARK_LOOKBACK, resolve_since

_failures: list[str] = []


def check(name: str, cond: bool) -> None:
    if cond:
        print(f"  ok   {name}")
    else:
        print(f"  FAIL {name}")
        _failures.append(name)


def test_bootstrap_full() -> None:
    # First run ever: no stored watermark, no override → full pull.
    since, source = resolve_since(None, None)
    check("bootstrap since is None", since is None)
    check("bootstrap source", source == "bootstrap-full")


def test_incremental_applies_lookback() -> None:
    stored = datetime(2026, 6, 18, 12, 0, 0, tzinfo=timezone.utc)
    since, source = resolve_since(None, stored)
    expected = (stored - WATERMARK_LOOKBACK).isoformat()
    check("incremental source", source == "incremental")
    check("incremental subtracts lookback", since == expected)
    # the lookback must move the cursor BACK in time, never forward
    check("since is before stored", datetime.fromisoformat(since) < stored)


def test_forced_full_ignores_stored() -> None:
    stored = datetime(2026, 6, 18, 12, 0, 0, tzinfo=timezone.utc)
    since, source = resolve_since(FORCE_FULL, stored)
    check("forced-full since is None even with stored", since is None)
    check("forced-full source", source == "forced-full")


def test_manual_override_verbatim() -> None:
    stored = datetime(2026, 6, 18, 12, 0, 0, tzinfo=timezone.utc)
    manual = "2026-01-01T00:00:00+00:00"
    since, source = resolve_since(manual, stored)
    check("manual since verbatim (no lookback)", since == manual)
    check("manual source", source == "manual")


def test_manual_override_wins_over_no_stored() -> None:
    manual = "2026-05-01T00:00:00+00:00"
    since, source = resolve_since(manual, None)
    check("manual works with no stored watermark", since == manual)
    check("manual source (no stored)", source == "manual")


def main() -> int:
    for fn in (
        test_bootstrap_full,
        test_incremental_applies_lookback,
        test_forced_full_ignores_stored,
        test_manual_override_verbatim,
        test_manual_override_wins_over_no_stored,
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
