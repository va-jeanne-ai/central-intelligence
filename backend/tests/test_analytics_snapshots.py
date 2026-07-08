"""Unit tests for the snapshot fan-out logic (app.analytics.snapshots).

Self-contained: runs with plain `python -m tests.test_analytics_snapshots` (pytest
is not installed in this env, per the sibling suites' convention). ``compute_snapshots``
executes raw SQL directly against a ``Session`` (global upsert + per-rep upsert +
terminated-reps lookup), so a real DB isn't needed to cover the *fan-out decision
logic* — only that the right statements/params get issued for the right rows. We
drive it with a fake session that serves canned result rows keyed off the SQL text,
and a synthetic single-metric registry (via monkeypatch) so the test doesn't depend
on the live catalog's exact shape.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import text

from app.analytics import snapshots
from app.analytics.registry import Metric
from app.analytics.snapshots import WINDOWS, compute_snapshots

_failures: list[str] = []


def check(name: str, cond: bool) -> None:
    if cond:
        print(f"  ok   {name}")
    else:
        print(f"  FAIL {name}")
        _failures.append(name)


# ─── Fake session ────────────────────────────────────────────────────────────


class _Result:
    def __init__(self, rows: list[dict] | list[tuple]) -> None:
        self._rows = rows

    def mappings(self):
        return self

    def first(self):
        return self._rows[0] if self._rows else None

    def all(self):
        return self._rows


class _FakeSession:
    """Routes ``execute`` based on the SQL text so one fake can serve the global
    metric SQL, the rep_sql, and the terminated-reps lookup with different canned
    results. Records every upsert call for assertions."""

    def __init__(
        self,
        *,
        global_row: dict,
        rep_rows: list[dict],
        terminated_reps: set[str],
    ) -> None:
        self._global_row = global_row
        self._rep_rows = rep_rows
        self._terminated_reps = terminated_reps
        self.upserts: list[dict] = []
        self.committed = False

    def execute(self, stmt, params=None):
        sql = str(stmt)
        params = params or {}
        if "FROM sales_reps WHERE status = 'terminated'" in sql:
            return _Result([(r,) for r in self._terminated_reps])
        if "INSERT INTO metric_snapshots" in sql:
            self.upserts.append(dict(params))
            return _Result([])
        if "rep_id" in sql and "GROUP BY" in sql.upper():
            # A metric's rep_sql — return the canned per-rep rows.
            return _Result(self._rep_rows)
        # Anything else (the metric's global `sql`) → the canned single row.
        return _Result([self._global_row])

    def commit(self) -> None:
        self.committed = True


def _make_metric(*, with_rep_sql: bool) -> Metric:
    base_sql = text("SELECT 1 AS value, 1 AS sample_size")
    rep_sql = (
        text("SELECT rep_id, 1 AS value, 1 AS sample_size FROM t WHERE 1=1 GROUP BY rep_id")
        if with_rep_sql
        else None
    )
    return Metric(
        key="test.synthetic_metric",
        area="sales",
        label="Synthetic Metric",
        unit="count",
        higher_is_better=True,
        sql=base_sql,
        rep_sql=rep_sql,
    )


def _patch_metrics(monkeypatch, metric: Metric) -> None:
    monkeypatch.setattr(snapshots, "all_metrics", lambda: [metric])
    monkeypatch.setattr(snapshots, "metrics_for_area", lambda area: [metric])


# ─── Tests ───────────────────────────────────────────────────────────────────


def test_metric_without_rep_sql_emits_only_global_rows(monkeypatch) -> None:
    metric = _make_metric(with_rep_sql=False)
    _patch_metrics(monkeypatch, metric)
    session = _FakeSession(
        global_row={"value": 10, "sample_size": 5},
        rep_rows=[],
        terminated_reps=set(),
    )

    summary = compute_snapshots(session)

    scoped = [u["scope"] for u in session.upserts]
    check("only 'global' scope rows written", set(scoped) == {"global"})
    check("one row per window", len(session.upserts) == len(WINDOWS))
    check("session committed", session.committed is True)
    check("summary has no rep_rows_by_window key", "rep_rows_by_window" not in summary["summary"][0])


def test_metric_with_rep_sql_fans_out_scoped_rows(monkeypatch) -> None:
    metric = _make_metric(with_rep_sql=True)
    _patch_metrics(monkeypatch, metric)
    session = _FakeSession(
        global_row={"value": 100, "sample_size": 50},
        rep_rows=[
            {"rep_id": "REP_A", "value": 60, "sample_size": 30},
            {"rep_id": "REP_B", "value": 40, "sample_size": 20},
        ],
        terminated_reps=set(),
    )

    summary = compute_snapshots(session)

    scoped = sorted({u["scope"] for u in session.upserts})
    check("global + both rep scopes present", scoped == ["global", "rep:REP_A", "rep:REP_B"])
    # One global row + two rep rows per window.
    check(
        "3 upsert rows per window",
        len(session.upserts) == 3 * len(WINDOWS),
    )
    rep_a_rows = [u for u in session.upserts if u["scope"] == "rep:REP_A"]
    check("REP_A rows carry its own value/sample_size", all(u["value"] == 60 and u["sample_size"] == 30 for u in rep_a_rows))
    check(
        "summary reports rep row counts per window",
        summary["summary"][0]["rep_rows_by_window"] == {w: 2 for w in WINDOWS},
    )
    check("rep_rows_written totals 2 per window", summary["rep_rows_written"] == 2 * len(WINDOWS))


def test_terminated_reps_filtered_from_fan_out(monkeypatch) -> None:
    metric = _make_metric(with_rep_sql=True)
    _patch_metrics(monkeypatch, metric)
    session = _FakeSession(
        global_row={"value": 100, "sample_size": 50},
        rep_rows=[
            {"rep_id": "REP_ACTIVE", "value": 60, "sample_size": 30},
            {"rep_id": "REP_TERMINATED", "value": 5, "sample_size": 2},
        ],
        terminated_reps={"REP_TERMINATED"},
    )

    summary = compute_snapshots(session)

    scoped = sorted({u["scope"] for u in session.upserts})
    check("terminated rep excluded from upserts", "rep:REP_TERMINATED" not in scoped)
    check("active rep still included", "rep:REP_ACTIVE" in scoped)
    check(
        "rep row count reflects the filter (1, not 2)",
        summary["summary"][0]["rep_rows_by_window"] == {w: 1 for w in WINDOWS},
    )


def test_terminated_reps_loaded_once_per_call(monkeypatch) -> None:
    """The terminated-reps set is loaded once per compute_snapshots call, not once
    per metric/window — assert the lookup SQL runs exactly once even across two
    windows' worth of rep fan-out (WINDOWS has 4 entries)."""
    metric = _make_metric(with_rep_sql=True)
    _patch_metrics(monkeypatch, metric)

    call_count = {"n": 0}
    session = _FakeSession(
        global_row={"value": 1, "sample_size": 1},
        rep_rows=[{"rep_id": "REP_A", "value": 1, "sample_size": 1}],
        terminated_reps=set(),
    )
    _orig_execute = session.execute

    def counting_execute(stmt, params=None):
        if "FROM sales_reps WHERE status = 'terminated'" in str(stmt):
            call_count["n"] += 1
        return _orig_execute(stmt, params)

    session.execute = counting_execute
    compute_snapshots(session)
    check("terminated-reps query ran exactly once", call_count["n"] == 1)


def test_empty_rep_rows_writes_no_rep_scoped_snapshot(monkeypatch) -> None:
    """A rep_sql metric with zero rows in-window (no rep has data) writes only the
    global row — absent rep = no snapshot that day, never a fabricated zero."""
    metric = _make_metric(with_rep_sql=True)
    _patch_metrics(monkeypatch, metric)
    session = _FakeSession(
        global_row={"value": 0, "sample_size": 0},
        rep_rows=[],
        terminated_reps=set(),
    )

    compute_snapshots(session)

    scoped = {u["scope"] for u in session.upserts}
    check("no rep-scoped rows written when rep_sql returns nothing", scoped == {"global"})


def main() -> int:
    class _Monkeypatch:
        def __init__(self) -> None:
            self._sets: list[tuple[object, str, object]] = []

        def setattr(self, obj, name, value):
            self._sets.append((obj, name, getattr(obj, name, None)))
            setattr(obj, name, value)

        def undo(self) -> None:
            for obj, name, value in reversed(self._sets):
                setattr(obj, name, value)

    for fn in (
        test_metric_without_rep_sql_emits_only_global_rows,
        test_metric_with_rep_sql_fans_out_scoped_rows,
        test_terminated_reps_filtered_from_fan_out,
        test_terminated_reps_loaded_once_per_call,
        test_empty_rep_rows_writes_no_rep_scoped_snapshot,
    ):
        print(fn.__name__)
        mp = _Monkeypatch()
        try:
            fn(mp)
        finally:
            mp.undo()
    if _failures:
        print(f"\n{len(_failures)} FAILED: {_failures}")
        return 1
    print("\nALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
