"""Unit tests for the recommendation lifecycle logic (app.analytics.recommend).

Self-contained: runs with plain `python -m tests.test_recommend` (pytest is not
installed in this env). ``generate_recommendations`` executes raw Postgres SQL
(jsonb casts, ``ALL(:active_keys)``) directly against a ``Session``, so a real
DB (or a generic sqlite fixture) can't stand in for it. Instead we drive it with
a fake session that records the executed statements/params, and monkeypatch
``all_trends`` so no DB read happens either — this covers the pure decision
logic (open on declining, auto-resolve on recovery, re-open on re-trigger)
without touching Postgres. ``_phrase`` / ``_severity`` are pure and tested
directly.
"""

from __future__ import annotations

from dataclasses import replace

from app.analytics import recommend
from app.analytics.recommend import (
    DECLINE_CRITICAL,
    DECLINE_FLAG,
    IMPROVE_HIGHLIGHT,
    _phrase,
    _severity,
    generate_recommendations,
)
from app.analytics.trends import TrendResult

_failures: list[str] = []


def check(name: str, cond: bool) -> None:
    if cond:
        print(f"  ok   {name}")
    else:
        print(f"  FAIL {name}")
        _failures.append(name)


def make_trend(
    *,
    metric_key: str = "sales.lead_to_close_rate",
    verdict: str = "declining",
    rel_change: float | None = -0.10,
    higher_is_better: bool = True,
    area: str = "sales",
    window: str = "30d",
) -> TrendResult:
    return TrendResult(
        metric_key=metric_key,
        area=area,
        label="Lead to Close Rate",
        unit="ratio",
        window=window,
        verdict=verdict,
        latest_value=0.45,
        baseline_value=0.50,
        latest_sample=100,
        baseline_sample=100,
        rel_change=rel_change,
        higher_is_better=higher_is_better,
        latest_date="2026-06-30",
        baseline_date="2026-06-01",
        reason="synthetic test trend",
    )


# ─── Pure phrasing / severity helpers ─────────────────────────────────────────


def test_phrase_declining_mentions_adverse() -> None:
    t = make_trend(verdict="declining", rel_change=-0.15)
    title, body = _phrase(t)
    check("declining title mentions declining", "declining" in title)
    check("declining title has pct", "15%" in title)
    check("declining body mentions adverse", "adverse" in body)


def test_phrase_improving_mentions_reinforcing() -> None:
    t = make_trend(verdict="improving", rel_change=0.15)
    title, body = _phrase(t)
    check("improving title mentions improving", "improving" in title)
    check("improving body mentions reinforcing", "reinforce" in body)


def test_severity_scales_with_magnitude() -> None:
    small_decline = make_trend(verdict="declining", rel_change=-(DECLINE_FLAG))
    big_decline = make_trend(verdict="declining", rel_change=-(DECLINE_CRITICAL))
    improving = make_trend(verdict="improving", rel_change=IMPROVE_HIGHLIGHT)
    check("small decline is warn", _severity(small_decline) == "warn")
    check("decline at critical threshold is critical", _severity(big_decline) == "critical")
    check("improving is always info", _severity(improving) == "info")


# ─── Fake session driving generate_recommendations ───────────────────────────


class _FakeSession:
    """Records every executed statement + params; no real SQL engine involved.

    ``generate_recommendations`` only ever calls ``execute`` (upsert or
    auto-resolve) and ``commit`` — nothing reads back a result set, so a bare
    recorder is a faithful stand-in.
    """

    def __init__(self) -> None:
        self.executed: list[tuple[str, dict]] = []
        self.committed = False

    def execute(self, stmt, params=None):
        # stmt is a sqlalchemy TextClause; str() renders the SQL for matching.
        self.executed.append((str(stmt), dict(params or {})))
        return None

    def commit(self) -> None:
        self.committed = True


def _upserted_keys(session: _FakeSession) -> list[str]:
    return [p["metric_key"] for sql, p in session.executed if "INSERT INTO recommendations" in sql]


def _auto_resolve_call(session: _FakeSession) -> dict | None:
    for sql, p in session.executed:
        if "UPDATE recommendations" in sql and "resolved" in sql:
            return p
    return None


def test_declining_above_threshold_opens_recommendation(monkeypatch) -> None:
    trend = make_trend(verdict="declining", rel_change=-(DECLINE_FLAG + 0.01))
    monkeypatch.setattr(recommend, "all_trends", lambda db, window=None: [trend])

    session = _FakeSession()
    summary = generate_recommendations(session, window="30d")

    check("summary reports 1 active", summary["active"] == 1)
    check("metric upserted", trend.metric_key in _upserted_keys(session))
    check("session committed", session.committed is True)
    resolve_call = _auto_resolve_call(session)
    check("auto-resolve ran with the active key excluded", resolve_call is not None and trend.metric_key in resolve_call["active_keys"])


def test_declining_below_threshold_emits_nothing() -> None:
    trend = make_trend(verdict="declining", rel_change=-(DECLINE_FLAG - 0.01))
    _orig = recommend.all_trends
    recommend.all_trends = lambda db, window=None: [trend]
    try:
        session = _FakeSession()
        summary = generate_recommendations(session, window="30d")
        check("below-threshold decline: nothing emitted", summary["active"] == 0)
        check("below-threshold decline: no upsert executed", _upserted_keys(session) == [])
        resolve_call = _auto_resolve_call(session)
        check("auto-resolve still runs with empty active_keys sentinel", resolve_call is not None and resolve_call["active_keys"] == [""])
    finally:
        recommend.all_trends = _orig


def test_flat_emits_nothing() -> None:
    trend = make_trend(verdict="flat", rel_change=0.01)
    _orig = recommend.all_trends
    recommend.all_trends = lambda db, window=None: [trend]
    try:
        session = _FakeSession()
        summary = generate_recommendations(session, window="30d")
        check("flat: nothing emitted", summary["active"] == 0)
    finally:
        recommend.all_trends = _orig


def test_insufficient_data_emits_nothing() -> None:
    trend = make_trend(verdict="insufficient_data", rel_change=None)
    _orig = recommend.all_trends
    recommend.all_trends = lambda db, window=None: [trend]
    try:
        session = _FakeSession()
        summary = generate_recommendations(session, window="30d")
        check("insufficient_data: nothing emitted", summary["active"] == 0)
    finally:
        recommend.all_trends = _orig


def test_improving_above_highlight_threshold_emits_info_note() -> None:
    trend = make_trend(verdict="improving", rel_change=IMPROVE_HIGHLIGHT + 0.01)
    _orig = recommend.all_trends
    recommend.all_trends = lambda db, window=None: [trend]
    try:
        session = _FakeSession()
        summary = generate_recommendations(session, window="30d")
        check("improving above threshold emits", summary["active"] == 1)
        check("improving emitted has info severity", summary["recommendations"][0]["severity"] == "info")
    finally:
        recommend.all_trends = _orig


def test_improving_below_highlight_threshold_emits_nothing() -> None:
    trend = make_trend(verdict="improving", rel_change=IMPROVE_HIGHLIGHT - 0.01)
    _orig = recommend.all_trends
    recommend.all_trends = lambda db, window=None: [trend]
    try:
        session = _FakeSession()
        summary = generate_recommendations(session, window="30d")
        check("improving below threshold emits nothing", summary["active"] == 0)
    finally:
        recommend.all_trends = _orig


def test_recovery_auto_resolves_by_excluding_key_from_active() -> None:
    """Simulates the two-run lifecycle: declining metric opens a finding, then on a
    later run (once recovered/flat) the same metric no longer appears in
    ``active_keys`` passed to the auto-resolve statement — which is exactly the
    SQL's trigger to flip a standing 'open' row to 'resolved' (metric_key <> ALL(:active_keys)).
    """
    declining = make_trend(verdict="declining", rel_change=-0.10)
    _orig = recommend.all_trends

    # Run 1: metric is declining -> opens.
    recommend.all_trends = lambda db, window=None: [declining]
    try:
        session1 = _FakeSession()
        generate_recommendations(session1, window="30d")
        check("run1: opened", declining.metric_key in _upserted_keys(session1))
    finally:
        recommend.all_trends = _orig

    # Run 2: same metric recovered -> now flat, no longer flagged.
    recovered = make_trend(verdict="flat", rel_change=0.01)
    recommend.all_trends = lambda db, window=None: [recovered]
    try:
        session2 = _FakeSession()
        generate_recommendations(session2, window="30d")
        resolve_call = _auto_resolve_call(session2)
        check("run2: nothing upserted (recovered)", _upserted_keys(session2) == [])
        check(
            "run2: auto-resolve excludes the now-recovered metric from active_keys "
            "(so the SQL's <> ALL(...) predicate matches it and resolves it)",
            resolve_call is not None and declining.metric_key not in resolve_call["active_keys"],
        )
    finally:
        recommend.all_trends = _orig


def test_retrigger_after_recovery_reopens_via_upsert_case() -> None:
    """A metric that recovers (auto-resolved) and later re-declines must be upserted
    again with 'open'-eligible data; the re-open semantics live in the SQL's
    ``CASE WHEN recommendations.status = 'resolved' THEN 'open' ELSE ...`` clause,
    which we can't execute without Postgres — but we assert the upsert statement
    the second run issues is unconditional (always re-upserts on any active trigger,
    which is what lets the ON CONFLICT clause do the re-open).
    """
    _orig = recommend.all_trends

    declining = make_trend(verdict="declining", rel_change=-0.10)
    recommend.all_trends = lambda db, window=None: [declining]
    try:
        session = _FakeSession()
        generate_recommendations(session, window="30d")
        upsert_sql = next(sql for sql, _ in session.executed if "INSERT INTO recommendations" in sql)
        check("upsert has ON CONFLICT", "ON CONFLICT" in upsert_sql)
        check(
            "upsert re-opens a resolved row on re-trigger",
            "WHEN recommendations.status = 'resolved' THEN 'open'" in upsert_sql,
        )
    finally:
        recommend.all_trends = _orig


def test_multiple_metrics_mixed_verdicts() -> None:
    declining = make_trend(metric_key="sales.a", verdict="declining", rel_change=-0.10)
    improving = make_trend(metric_key="sales.b", verdict="improving", rel_change=0.20)
    flat = make_trend(metric_key="sales.c", verdict="flat", rel_change=0.01)
    insufficient = make_trend(metric_key="sales.d", verdict="insufficient_data", rel_change=None)

    _orig = recommend.all_trends
    recommend.all_trends = lambda db, window=None: [declining, improving, flat, insufficient]
    try:
        session = _FakeSession()
        summary = generate_recommendations(session, window="30d")
        keys = _upserted_keys(session)
        check("only declining + improving flagged", sorted(keys) == ["sales.a", "sales.b"])
        check("flat/insufficient excluded", "sales.c" not in keys and "sales.d" not in keys)
        resolve_call = _auto_resolve_call(session)
        check(
            "auto-resolve active_keys matches the flagged set",
            resolve_call is not None and sorted(resolve_call["active_keys"]) == ["sales.a", "sales.b"],
        )
    finally:
        recommend.all_trends = _orig


class _FakeMonkeypatch:
    """Minimal stand-in for pytest's monkeypatch fixture for the one test above
    that declares it as a parameter (kept dependency-free from pytest internals)."""

    def setattr(self, obj, name, value):
        setattr(obj, name, value)


def main() -> int:
    mp = _FakeMonkeypatch()
    for fn in (
        test_phrase_declining_mentions_adverse,
        test_phrase_improving_mentions_reinforcing,
        test_severity_scales_with_magnitude,
        lambda: test_declining_above_threshold_opens_recommendation(mp),
        test_declining_below_threshold_emits_nothing,
        test_flat_emits_nothing,
        test_insufficient_data_emits_nothing,
        test_improving_above_highlight_threshold_emits_info_note,
        test_improving_below_highlight_threshold_emits_nothing,
        test_recovery_auto_resolves_by_excluding_key_from_active,
        test_retrigger_after_recovery_reopens_via_upsert_case,
        test_multiple_metrics_mixed_verdicts,
    ):
        name = getattr(fn, "__name__", "test_declining_above_threshold_opens_recommendation")
        print(name)
        fn()
    if _failures:
        print(f"\n{len(_failures)} FAILED: {_failures}")
        return 1
    print("\nALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
