"""Unit test for orphan-FK nulling in the WGR sync (app.services.wgr_sync.upsert).

WGR child rows often reference a parent CI filtered out (TEST_ calls) or hasn't
synced yet. ``_null_orphan_fks`` nulls nullable-FK columns whose parent isn't in
CI so the INSERT doesn't abort the whole sync. Self-contained: runs with plain
`python -m tests.test_wgr_orphan_fks` (no pytest, no live DB — the session's
parent-existence query is stubbed).
"""

from __future__ import annotations

import asyncio

from app.services.wgr_sync import upsert

_failures: list[str] = []


def check(name: str, cond: bool) -> None:
    if cond:
        print(f"  ok   {name}")
    else:
        print(f"  FAIL {name}")
        _failures.append(name)


class _FakeScalars:
    def __init__(self, vals):
        self._vals = vals

    def scalars(self):
        return self._vals


class _FakeSession:
    """Returns a fixed set of 'present' parent ids for any select()."""

    def __init__(self, present):
        self._present = present

    async def execute(self, _stmt):
        return _FakeScalars(self._present)


class _Col:
    """Stand-in for a parent PK column; .in_() is a no-op for the stub."""

    def in_(self, _ids):
        return None


# The helper calls ``select(parent_pk).where(parent_pk.in_(...))`` before handing
# the statement to the (stubbed) session. Our fake column can't be coerced by the
# real ``select()``, so replace it with a no-op for the duration of the tests —
# the session stub ignores the statement anyway.
upsert.select = lambda *a, **k: _FakeSelect()


class _FakeSelect:
    def where(self, *_a, **_k):
        return self


def test_nulls_orphans_keeps_present() -> None:
    rows = [
        {"id": "A", "call_id": "CALL_present"},
        {"id": "B", "call_id": "CALL_orphan"},
        {"id": "C", "call_id": None},  # already null — untouched
    ]
    session = _FakeSession(present={"CALL_present"})
    nulled = asyncio.run(
        upsert._null_orphan_fks(session, rows, [("call_id", _Col())])
    )
    check("orphan nulled", rows[1]["call_id"] is None)
    check("present kept", rows[0]["call_id"] == "CALL_present")
    check("none left none", rows[2]["call_id"] is None)
    check("count reported", nulled == {"call_id": 1})


def test_no_refs_no_query() -> None:
    rows = [{"id": "A", "call_id": None}]
    session = _FakeSession(present=set())
    nulled = asyncio.run(
        upsert._null_orphan_fks(session, rows, [("call_id", _Col())])
    )
    check("nothing to null → empty result", nulled == {})


def test_all_present_no_nulling() -> None:
    rows = [{"id": "A", "call_id": "X"}, {"id": "B", "call_id": "Y"}]
    session = _FakeSession(present={"X", "Y"})
    nulled = asyncio.run(
        upsert._null_orphan_fks(session, rows, [("call_id", _Col())])
    )
    check("all present → no nulling", nulled == {})
    check("rows untouched", rows[0]["call_id"] == "X" and rows[1]["call_id"] == "Y")


def main() -> int:
    for fn in (test_nulls_orphans_keeps_present, test_no_refs_no_query, test_all_present_no_nulling):
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
