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

import json
from dataclasses import replace

from app.analytics import recommend
from app.analytics.recommend import (
    DECLINE_CRITICAL,
    DECLINE_FLAG,
    IMPROVE_HIGHLIGHT,
    REP_SEVERITY_CAP,
    _phrase,
    _severity,
    generate_recommendations,
)
from app.analytics.trends import TrendResult

_failures: list[str] = []


def _no_rep_metrics(monkeypatch) -> None:
    """Most tests below exercise only the global pass; stub `all_metrics` so the
    rep-scoped fan-out (which needs a real `rep_scopes_for_metric`/`sales_reps`
    query) is a no-op rather than hitting the fake session with unexpected SQL."""
    monkeypatch.setattr(recommend, "all_metrics", lambda: [])


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
    monkeypatch.setattr(recommend, "all_trends", lambda db, window=None, scope=None: [trend])
    _no_rep_metrics(monkeypatch)

    session = _FakeSession()
    summary = generate_recommendations(session, window="30d")

    check("summary reports 1 active", summary["active"] == 1)
    check("metric upserted", trend.metric_key in _upserted_keys(session))
    check("session committed", session.committed is True)
    resolve_call = _auto_resolve_call(session)
    check("auto-resolve ran with the active key excluded", resolve_call is not None and trend.metric_key in resolve_call["active_keys"])
    check("auto-resolve scoped to global", resolve_call is not None and resolve_call["scope"] == "global")


def test_declining_below_threshold_emits_nothing(monkeypatch) -> None:
    trend = make_trend(verdict="declining", rel_change=-(DECLINE_FLAG - 0.01))
    monkeypatch.setattr(recommend, "all_trends", lambda db, window=None, scope=None: [trend])
    _no_rep_metrics(monkeypatch)
    session = _FakeSession()
    summary = generate_recommendations(session, window="30d")
    check("below-threshold decline: nothing emitted", summary["active"] == 0)
    check("below-threshold decline: no upsert executed", _upserted_keys(session) == [])
    resolve_call = _auto_resolve_call(session)
    check("auto-resolve still runs with empty active_keys sentinel", resolve_call is not None and resolve_call["active_keys"] == [""])


def test_flat_emits_nothing(monkeypatch) -> None:
    trend = make_trend(verdict="flat", rel_change=0.01)
    monkeypatch.setattr(recommend, "all_trends", lambda db, window=None, scope=None: [trend])
    _no_rep_metrics(monkeypatch)
    session = _FakeSession()
    summary = generate_recommendations(session, window="30d")
    check("flat: nothing emitted", summary["active"] == 0)


def test_insufficient_data_emits_nothing(monkeypatch) -> None:
    trend = make_trend(verdict="insufficient_data", rel_change=None)
    monkeypatch.setattr(recommend, "all_trends", lambda db, window=None, scope=None: [trend])
    _no_rep_metrics(monkeypatch)
    session = _FakeSession()
    summary = generate_recommendations(session, window="30d")
    check("insufficient_data: nothing emitted", summary["active"] == 0)


def test_improving_above_highlight_threshold_emits_info_note(monkeypatch) -> None:
    trend = make_trend(verdict="improving", rel_change=IMPROVE_HIGHLIGHT + 0.01)
    monkeypatch.setattr(recommend, "all_trends", lambda db, window=None, scope=None: [trend])
    _no_rep_metrics(monkeypatch)
    session = _FakeSession()
    summary = generate_recommendations(session, window="30d")
    check("improving above threshold emits", summary["active"] == 1)
    check("improving emitted has info severity", summary["recommendations"][0]["severity"] == "info")


def test_improving_below_highlight_threshold_emits_nothing(monkeypatch) -> None:
    trend = make_trend(verdict="improving", rel_change=IMPROVE_HIGHLIGHT - 0.01)
    monkeypatch.setattr(recommend, "all_trends", lambda db, window=None, scope=None: [trend])
    _no_rep_metrics(monkeypatch)
    session = _FakeSession()
    summary = generate_recommendations(session, window="30d")
    check("improving below threshold emits nothing", summary["active"] == 0)


def test_recovery_auto_resolves_by_excluding_key_from_active(monkeypatch) -> None:
    """Simulates the two-run lifecycle: declining metric opens a finding, then on a
    later run (once recovered/flat) the same metric no longer appears in
    ``active_keys`` passed to the auto-resolve statement — which is exactly the
    SQL's trigger to flip a standing 'open' row to 'resolved' (metric_key <> ALL(:active_keys)).
    """
    declining = make_trend(verdict="declining", rel_change=-0.10)
    _no_rep_metrics(monkeypatch)

    # Run 1: metric is declining -> opens.
    monkeypatch.setattr(recommend, "all_trends", lambda db, window=None, scope=None: [declining])
    session1 = _FakeSession()
    generate_recommendations(session1, window="30d")
    check("run1: opened", declining.metric_key in _upserted_keys(session1))

    # Run 2: same metric recovered -> now flat, no longer flagged.
    recovered = make_trend(verdict="flat", rel_change=0.01)
    monkeypatch.setattr(recommend, "all_trends", lambda db, window=None, scope=None: [recovered])
    session2 = _FakeSession()
    generate_recommendations(session2, window="30d")
    resolve_call = _auto_resolve_call(session2)
    check("run2: nothing upserted (recovered)", _upserted_keys(session2) == [])
    check(
        "run2: auto-resolve excludes the now-recovered metric from active_keys "
        "(so the SQL's <> ALL(...) predicate matches it and resolves it)",
        resolve_call is not None and declining.metric_key not in resolve_call["active_keys"],
    )


def test_retrigger_after_recovery_reopens_via_upsert_case(monkeypatch) -> None:
    """A metric that recovers (auto-resolved) and later re-declines must be upserted
    again with 'open'-eligible data; the re-open semantics live in the SQL's
    ``CASE WHEN recommendations.status = 'resolved' THEN 'open' ELSE ...`` clause,
    which we can't execute without Postgres — but we assert the upsert statement
    the second run issues is unconditional (always re-upserts on any active trigger,
    which is what lets the ON CONFLICT clause do the re-open).
    """
    _no_rep_metrics(monkeypatch)

    declining = make_trend(verdict="declining", rel_change=-0.10)
    monkeypatch.setattr(recommend, "all_trends", lambda db, window=None, scope=None: [declining])
    session = _FakeSession()
    generate_recommendations(session, window="30d")
    upsert_sql = next(sql for sql, _ in session.executed if "INSERT INTO recommendations" in sql)
    check("upsert has ON CONFLICT", "ON CONFLICT" in upsert_sql)
    check("upsert conflict target includes scope", "ON CONFLICT (metric_key, \"window\", scope)" in upsert_sql)
    check(
        "upsert re-opens a resolved row on re-trigger",
        "WHEN recommendations.status = 'resolved' THEN 'open'" in upsert_sql,
    )


def test_multiple_metrics_mixed_verdicts(monkeypatch) -> None:
    declining = make_trend(metric_key="sales.a", verdict="declining", rel_change=-0.10)
    improving = make_trend(metric_key="sales.b", verdict="improving", rel_change=0.20)
    flat = make_trend(metric_key="sales.c", verdict="flat", rel_change=0.01)
    insufficient = make_trend(metric_key="sales.d", verdict="insufficient_data", rel_change=None)

    monkeypatch.setattr(
        recommend, "all_trends",
        lambda db, window=None, scope=None: [declining, improving, flat, insufficient],
    )
    _no_rep_metrics(monkeypatch)
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


# ─── Rep-scoped fan-out ────────────────────────────────────────────────────────


class _FakeRepMetric:
    """Minimal stand-in for a registry.Metric that declares rep_sql (only the
    ``.key`` attribute is read by the rep-scoped fan-out in generate_recommendations)."""

    def __init__(self, key: str) -> None:
        self.key = key
        self.rep_sql = object()  # any non-None sentinel — only truthiness is checked


def test_rep_scope_lifecycle_open_then_resolve(monkeypatch) -> None:
    """A rep-scoped metric opens a finding under scope='rep:X', independent of the
    global pass, and is auto-resolved independently once that rep recovers."""
    metric = _FakeRepMetric("sales.avg_call_score")
    monkeypatch.setattr(recommend, "all_metrics", lambda: [metric])
    monkeypatch.setattr(recommend, "rep_scopes_for_metric", lambda db, key: ["rep:REP_X"])
    monkeypatch.setattr(recommend, "all_trends", lambda db, window=None, scope=None: [])

    declining_rep = make_trend(metric_key="sales.avg_call_score", verdict="declining", rel_change=-0.10)
    monkeypatch.setattr(recommend, "_rep_trend", lambda db, m, window, scope: declining_rep)
    monkeypatch.setattr(recommend, "_load_rep_names", lambda db: {"REP_X": "Makyla Thompson"})

    session = _FakeSession()
    summary = generate_recommendations(session, window="30d")

    rep_upserts = [
        (sql, p) for sql, p in session.executed
        if "INSERT INTO recommendations" in sql and p.get("scope") == "rep:REP_X"
    ]
    check("rep scope opened a finding", len(rep_upserts) == 1)
    check("rep upsert carries scope", rep_upserts[0][1]["scope"] == "rep:REP_X")
    check("summary reports the rep-scoped active finding", summary["active"] == 1)

    # Now the rep recovers (flat) -> no upsert, auto-resolve fires for that scope.
    recovered_rep = make_trend(metric_key="sales.avg_call_score", verdict="flat", rel_change=0.0)
    monkeypatch.setattr(recommend, "_rep_trend", lambda db, m, window, scope: recovered_rep)
    session2 = _FakeSession()
    generate_recommendations(session2, window="30d")
    rep_resolve_calls = [
        p for sql, p in session2.executed
        if "UPDATE recommendations" in sql and p.get("scope") == "rep:REP_X"
    ]
    check("rep auto-resolve ran for that scope", len(rep_resolve_calls) == 1)
    check(
        "rep auto-resolve excludes the metric (now recovered)",
        rep_resolve_calls[0]["active_keys"] == [""],
    )


def test_rep_scope_severity_capped_at_warn(monkeypatch) -> None:
    """A rep-scoped critical-magnitude decline is still capped to 'warn' — never
    'critical' — per the rep-severity-cap rule."""
    metric = _FakeRepMetric("sales.avg_call_score")
    monkeypatch.setattr(recommend, "all_metrics", lambda: [metric])
    monkeypatch.setattr(recommend, "rep_scopes_for_metric", lambda db, key: ["rep:REP_X"])
    monkeypatch.setattr(recommend, "all_trends", lambda db, window=None, scope=None: [])
    monkeypatch.setattr(recommend, "_load_rep_names", lambda db: {"REP_X": "Makyla Thompson"})

    huge_decline = make_trend(
        metric_key="sales.avg_call_score", verdict="declining", rel_change=-(DECLINE_CRITICAL + 0.10)
    )
    monkeypatch.setattr(recommend, "_rep_trend", lambda db, m, window, scope: huge_decline)

    session = _FakeSession()
    summary = generate_recommendations(session, window="30d")

    check("rep-scoped finding emitted", summary["active"] == 1)
    check(
        "rep-scoped severity capped at warn despite critical-magnitude change",
        summary["recommendations"][0]["severity"] == REP_SEVERITY_CAP,
    )
    check("severity cap does not exceed 'critical' by construction", REP_SEVERITY_CAP != "critical")


def test_rep_scope_phrasing_uses_display_name(monkeypatch) -> None:
    """Rep-scoped titles are prefixed with the rep's display name, resolved from
    sales_reps — never a raw rep_id."""
    metric = _FakeRepMetric("sales.avg_call_score")
    monkeypatch.setattr(recommend, "all_metrics", lambda: [metric])
    monkeypatch.setattr(recommend, "rep_scopes_for_metric", lambda db, key: ["rep:REP_MAKYLA_THOMPSON"])
    monkeypatch.setattr(recommend, "all_trends", lambda db, window=None, scope=None: [])
    monkeypatch.setattr(recommend, "_load_rep_names", lambda db: {"REP_MAKYLA_THOMPSON": "Makyla Thompson"})

    declining_rep = make_trend(
        metric_key="sales.avg_call_score", verdict="declining", rel_change=-0.15
    )
    monkeypatch.setattr(recommend, "_rep_trend", lambda db, m, window, scope: declining_rep)

    session = _FakeSession()
    summary = generate_recommendations(session, window="30d")

    title = summary["recommendations"][0]["title"]
    check("title uses the rep's display name", title.startswith("Makyla Thompson's"))
    check("title does not leak the raw rep_id", "REP_MAKYLA_THOMPSON" not in title)


def test_rep_scope_evidence_carries_scope_and_display_name(monkeypatch) -> None:
    """The evidence JSON for a rep-scoped finding records scope + rep display name,
    on top of the exact TrendResult numbers (the audit trail)."""
    metric = _FakeRepMetric("sales.avg_call_score")
    monkeypatch.setattr(recommend, "all_metrics", lambda: [metric])
    monkeypatch.setattr(recommend, "rep_scopes_for_metric", lambda db, key: ["rep:REP_X"])
    monkeypatch.setattr(recommend, "all_trends", lambda db, window=None, scope=None: [])
    monkeypatch.setattr(recommend, "_load_rep_names", lambda db: {"REP_X": "Makyla Thompson"})

    declining_rep = make_trend(metric_key="sales.avg_call_score", verdict="declining", rel_change=-0.10)
    monkeypatch.setattr(recommend, "_rep_trend", lambda db, m, window, scope: declining_rep)

    session = _FakeSession()
    generate_recommendations(session, window="30d")

    upsert_params = next(
        p for sql, p in session.executed
        if "INSERT INTO recommendations" in sql and p.get("scope") == "rep:REP_X"
    )
    evidence = json.loads(upsert_params["evidence"])
    check("evidence carries scope", evidence["scope"] == "rep:REP_X")
    check("evidence carries rep display name", evidence["rep_display_name"] == "Makyla Thompson")
    check("evidence still carries the exact metric_key", evidence["metric_key"] == "sales.avg_call_score")


def test_rep_scope_none_returned_skips_scope(monkeypatch) -> None:
    """If trend_for can't resolve a verdict for a rep scope (unknown metric_key,
    defensive edge case), the fan-out skips it rather than erroring."""
    metric = _FakeRepMetric("sales.avg_call_score")
    monkeypatch.setattr(recommend, "all_metrics", lambda: [metric])
    monkeypatch.setattr(recommend, "rep_scopes_for_metric", lambda db, key: ["rep:REP_X"])
    monkeypatch.setattr(recommend, "all_trends", lambda db, window=None, scope=None: [])
    monkeypatch.setattr(recommend, "_load_rep_names", lambda db: {"REP_X": "Makyla Thompson"})
    monkeypatch.setattr(recommend, "_rep_trend", lambda db, m, window, scope: None)

    session = _FakeSession()
    summary = generate_recommendations(session, window="30d")
    check("no rep finding emitted when trend is None", summary["active"] == 0)


def main() -> int:
    import inspect

    for fn in (
        test_phrase_declining_mentions_adverse,
        test_phrase_improving_mentions_reinforcing,
        test_severity_scales_with_magnitude,
        test_declining_above_threshold_opens_recommendation,
        test_declining_below_threshold_emits_nothing,
        test_flat_emits_nothing,
        test_insufficient_data_emits_nothing,
        test_improving_above_highlight_threshold_emits_info_note,
        test_improving_below_highlight_threshold_emits_nothing,
        test_recovery_auto_resolves_by_excluding_key_from_active,
        test_retrigger_after_recovery_reopens_via_upsert_case,
        test_multiple_metrics_mixed_verdicts,
        test_rep_scope_lifecycle_open_then_resolve,
        test_rep_scope_severity_capped_at_warn,
        test_rep_scope_phrasing_uses_display_name,
        test_rep_scope_evidence_carries_scope_and_display_name,
        test_rep_scope_none_returned_skips_scope,
    ):
        print(fn.__name__)
        mp = _Monkeypatch()
        try:
            if inspect.signature(fn).parameters:
                fn(mp)
            else:
                fn()
        finally:
            mp.undo()
    if _failures:
        print(f"\n{len(_failures)} FAILED: {_failures}")
        return 1
    print("\nALL CHECKS PASSED")
    return 0


class _Monkeypatch:
    """Minimal stand-in for pytest's monkeypatch fixture, used only by main()'s
    direct-script-execution path (pytest itself supplies the real fixture)."""

    def __init__(self) -> None:
        self._sets: list[tuple[object, str, object]] = []

    def setattr(self, obj, name, value):
        self._sets.append((obj, name, getattr(obj, name, None)))
        setattr(obj, name, value)

    def undo(self) -> None:
        for obj, name, value in reversed(self._sets):
            setattr(obj, name, value)


if __name__ == "__main__":
    import sys

    sys.exit(main())
