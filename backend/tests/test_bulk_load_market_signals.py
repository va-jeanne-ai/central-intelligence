"""Unit test for orphan-FK nulling in the WGR *bulk-load* path
(app.services.wgr_sync.bulk_load._null_orphan_example_call_id).

market_signals.example_call_id FKs calls (ON DELETE SET NULL). WGR signals can
reference a call CI filtered out (TEST_) or hasn't synced yet; left as-is the FK
violation aborts the whole execute_values batch and silently drops those rows.
The bulk loader nulls the orphan ref before insert — this test covers that
decision (the async path's equivalent is covered by test_wgr_orphan_fks).

Self-contained: runs with plain `python -m tests.test_bulk_load_market_signals`
(no pytest, no live DB — the helper is pure).
"""

from __future__ import annotations

from app.services.wgr_sync.bulk_load import _null_orphan_example_call_id

_failures: list[str] = []


def check(name: str, cond: bool) -> None:
    if cond:
        print(f"  ok   {name}")
    else:
        print(f"  FAIL {name}")
        _failures.append(name)


def test_orphan_nulled() -> None:
    present = {"CALL_present"}
    m = {"signal": "s", "example_call_id": "CALL_orphan_20260623"}
    _null_orphan_example_call_id(m, present)
    check("orphan ref nulled", m["example_call_id"] is None)


def test_present_kept() -> None:
    present = {"CALL_present"}
    m = {"signal": "s", "example_call_id": "CALL_present"}
    _null_orphan_example_call_id(m, present)
    check("present ref kept", m["example_call_id"] == "CALL_present")


def test_already_null_untouched() -> None:
    m = {"signal": "s", "example_call_id": None}
    _null_orphan_example_call_id(m, set())
    check("already-null stays null", m["example_call_id"] is None)


def test_missing_key_no_crash() -> None:
    m = {"signal": "s"}  # no example_call_id at all
    _null_orphan_example_call_id(m, {"X"})
    check("absent key is a no-op", "example_call_id" not in m or m.get("example_call_id") is None)


def test_empty_call_id_pool() -> None:
    # No calls in CI yet → every non-null ref is orphan.
    m = {"signal": "s", "example_call_id": "CALL_anything"}
    _null_orphan_example_call_id(m, set())
    check("orphan against empty pool nulled", m["example_call_id"] is None)


def main() -> int:
    for fn in (
        test_orphan_nulled, test_present_kept, test_already_null_untouched,
        test_missing_key_no_crash, test_empty_call_id_pool,
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
