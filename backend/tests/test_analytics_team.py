"""Unit tests for the per-rep team analytics assembly (app.analytics.team).

Self-contained: runs with plain `python -m tests.test_analytics_team` (pytest is
not installed in this env, per this suite's existing convention). Covers:

  - ``resolve_rep`` — exact rep_id / case-insensitive full_name / alias / unknown.
  - ``validate_scope`` — the scope query-param format check shared by
    /analytics/trends and /analytics/recommendations.
  - ``build_rep_metric_block`` / ``build_team_rollup`` — the pure assembly
    helpers factored out of the /analytics/team endpoint.
  - ``assemble_team_snapshot`` — driven with a fake sync Session (mirroring
    tests/test_recommend.py's ``_FakeSession`` style) so ``trends.trend_for``'s
    real SQL never runs; only the wiring/shape is under test.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.analytics import team as team_mod
from app.analytics.registry import Metric, get_metric
from app.analytics.team import (
    LatestSnapshot,
    RepRow,
    assemble_team_snapshot,
    build_rep_metric_block,
    build_team_rollup,
    is_active_rep,
    resolve_rep,
    validate_scope,
)
from app.analytics.trends import TrendResult

_failures: list[str] = []


def check(name: str, cond: bool) -> None:
    if cond:
        print(f"  ok   {name}")
    else:
        print(f"  FAIL {name}")
        _failures.append(name)


# ─── resolve_rep ────────────────────────────────────────────────────────────────

_ROSTER = [
    RepRow(rep_id="REP_MAKYLA_THOMPSON", full_name="Makyla Thompson", role="salaried_rep",
           status="probation", historical_aliases=None),
    RepRow(rep_id="REP_COLTON_LINDSAY", full_name="Colton Lindsay", role="manager",
           status="active", historical_aliases="colton lindsay,colton  lindsay,colton"),
    RepRow(rep_id="REP_TATJANA_CRISTAL", full_name="Tatjana Cristal", role="discovery_setter",
           status="active", historical_aliases="tatjana cristal,tatjana,tatiana"),
    RepRow(rep_id="REP_JUAN_DU_PREEZ", full_name="Juan Du Preez", role="salaried_rep",
           status="terminated", historical_aliases=None),
]


def test_resolve_rep_exact_rep_id() -> None:
    rep = resolve_rep("REP_MAKYLA_THOMPSON", _ROSTER)
    check("exact rep_id resolves", rep is not None and rep.rep_id == "REP_MAKYLA_THOMPSON")


def test_resolve_rep_case_insensitive_full_name() -> None:
    rep = resolve_rep("makyla thompson", _ROSTER)
    check("case-insensitive full_name resolves", rep is not None and rep.rep_id == "REP_MAKYLA_THOMPSON")
    rep2 = resolve_rep("MAKYLA THOMPSON", _ROSTER)
    check("uppercase full_name resolves", rep2 is not None and rep2.rep_id == "REP_MAKYLA_THOMPSON")


def test_resolve_rep_first_name_containment() -> None:
    rep = resolve_rep("Makyla", _ROSTER)
    check("bare first name resolves via full_name containment", rep is not None and rep.rep_id == "REP_MAKYLA_THOMPSON")


def test_resolve_rep_via_alias() -> None:
    rep = resolve_rep("tatiana", _ROSTER)
    check("misspelled alias resolves", rep is not None and rep.rep_id == "REP_TATJANA_CRISTAL")

    rep2 = resolve_rep("colton", _ROSTER)
    check("alias substring resolves", rep2 is not None and rep2.rep_id == "REP_COLTON_LINDSAY")


def test_resolve_rep_unknown_returns_none() -> None:
    rep = resolve_rep("nobody", _ROSTER)
    check("unknown name returns None (no guessing)", rep is None)


def test_resolve_rep_empty_query_returns_none() -> None:
    check("empty string returns None", resolve_rep("", _ROSTER) is None)
    check("whitespace-only returns None", resolve_rep("   ", _ROSTER) is None)


def test_resolve_rep_can_match_terminated_rep_by_name() -> None:
    """Matching itself doesn't filter by status — callers (the CI tool / team
    endpoint) decide whether a terminated rep is in-scope for their surface."""
    rep = resolve_rep("Juan Du Preez", _ROSTER)
    check("terminated rep still resolvable by exact name", rep is not None and rep.status == "terminated")


def test_is_active_rep_excludes_terminated() -> None:
    terminated = _ROSTER[3]
    active = _ROSTER[1]
    check("terminated rep is not active", is_active_rep(terminated) is False)
    check("non-terminated rep is active for roster purposes", is_active_rep(active) is True)


# ─── validate_scope ─────────────────────────────────────────────────────────────


def test_validate_scope_global() -> None:
    check("'global' is valid", validate_scope("global") is True)


def test_validate_scope_rep_prefix() -> None:
    check("'rep:REP_X' is valid", validate_scope("rep:REP_X") is True)
    check("'rep:anything' is valid", validate_scope("rep:anything-goes-here") is True)


def test_validate_scope_rejects_garbage() -> None:
    check("empty string invalid", validate_scope("") is False)
    check("bare 'rep' invalid (missing colon+id)", validate_scope("rep") is False)
    check("'rep:' with nothing after invalid", validate_scope("rep:") is False)
    check("random string invalid", validate_scope("all") is False)
    check("case-sensitive: 'Global' invalid", validate_scope("Global") is False)


# ─── build_rep_metric_block ─────────────────────────────────────────────────────

_METRIC = get_metric("sales.outbound_volume")
assert _METRIC is not None, "sales.outbound_volume must be registered for this test"


def _trend(**overrides) -> TrendResult:
    base = dict(
        metric_key=_METRIC.key, area=_METRIC.area, label=_METRIC.label, unit=_METRIC.unit,
        window="30d", verdict="improving", latest_value=5000.0, baseline_value=4000.0,
        latest_sample=5000, baseline_sample=4000, rel_change=0.25,
        higher_is_better=_METRIC.higher_is_better, latest_date="2026-07-01",
        baseline_date="2026-06-01", reason="synthetic",
    )
    base.update(overrides)
    return TrendResult(**base)


def test_build_rep_metric_block_with_snapshot_and_trend() -> None:
    block = build_rep_metric_block(
        _METRIC, snapshot=LatestSnapshot(value=5000.0, sample_size=5000), trend=_trend()
    )
    check("value comes from snapshot", block["value"] == 5000.0)
    check("sample_size comes from snapshot", block["sample_size"] == 5000)
    check("verdict comes from trend", block["verdict"] == "improving")
    check("rel_change carried through", block["rel_change"] == 0.25)
    check("metric_key set", block["metric_key"] == _METRIC.key)


def test_build_rep_metric_block_no_snapshot_no_trend_is_insufficient_data() -> None:
    """The core 'never fabricate a value' contract: no snapshot row -> None value,
    insufficient_data verdict, regardless of what trend_for would have said."""
    block = build_rep_metric_block(_METRIC, snapshot=None, trend=None)
    check("value is None (never fabricated)", block["value"] is None)
    check("sample_size is None", block["sample_size"] is None)
    check("verdict is insufficient_data", block["verdict"] == "insufficient_data")
    check("rel_change is None", block["rel_change"] is None)


def test_build_rep_metric_block_no_snapshot_but_has_trend_uses_trend_latest_value() -> None:
    """If a snapshot lookup came back empty but trend_for still had series data
    (e.g. caller only wired up the trend path), fall back to the trend's own
    latest_value rather than reporting None when a real value is available."""
    block = build_rep_metric_block(_METRIC, snapshot=None, trend=_trend(latest_value=1234.0))
    check("falls back to trend latest_value when no snapshot given", block["value"] == 1234.0)
    check("verdict still comes from trend", block["verdict"] == "improving")


def test_build_rep_metric_block_snapshot_value_wins_over_trend() -> None:
    """A real snapshot value is never overwritten even if the trend's own
    latest_value differs slightly (e.g. different windows compared)."""
    block = build_rep_metric_block(
        _METRIC, snapshot=LatestSnapshot(value=42.0, sample_size=10), trend=_trend(latest_value=999.0)
    )
    check("snapshot value takes precedence over trend latest_value", block["value"] == 42.0)


# ─── build_team_rollup ──────────────────────────────────────────────────────────


def _entry(status: str, outbound: float | None, strikes: float | None) -> dict:
    return {
        "status": status,
        "metrics": {
            "sales.outbound_volume": {"metric_key": "sales.outbound_volume", "value": outbound},
            "fulfillment.open_coaching_strikes": {
                "metric_key": "fulfillment.open_coaching_strikes", "value": strikes,
            },
        },
    }


def test_build_team_rollup_sums_and_counts() -> None:
    entries = [
        _entry("active", 100.0, 2.0),
        _entry("active", 200.0, None),
        _entry("probation", None, 1.0),
    ]
    rollup = build_team_rollup(entries)
    check("total_outbound sums non-None values", rollup["total_outbound"] == 300.0)
    check("open_strikes sums non-None values", rollup["open_strikes"] == 3.0)
    check("active_reps counts only status=='active'", rollup["active_reps"] == 2)
    check("total_reps counts every entry", rollup["total_reps"] == 3)


def test_build_team_rollup_empty_roster() -> None:
    rollup = build_team_rollup([])
    check("empty roster gives zeroed rollup", rollup == {
        "total_outbound": 0.0, "open_strikes": 0.0, "active_reps": 0, "total_reps": 0,
    })


# ─── assemble_team_snapshot (fake session) ─────────────────────────────────────


class _FakeSession:
    """Stand-in sync Session — assemble_team_snapshot only ever needs one to hand
    to trends.trend_for, which we monkeypatch out entirely below (its own SQL
    correctness is covered by tests/test_trends_evaluate.py)."""


def test_assemble_team_snapshot_shape_and_no_fabrication(monkeypatch) -> None:
    reps = [
        RepRow(rep_id="REP_A", full_name="Rep A", role="salaried_rep", status="active"),
        RepRow(rep_id="REP_B", full_name="Rep B", role="salaried_rep", status="probation"),
    ]

    outbound_metric = get_metric("sales.outbound_volume")
    strikes_metric = get_metric("fulfillment.open_coaching_strikes")
    monkeypatch.setattr(team_mod, "rep_scoped_metrics", lambda: [outbound_metric, strikes_metric])

    def fake_trend_for(db, metric_key, window="30d", scope="global"):
        rep_id = scope.removeprefix("rep:")
        if rep_id == "REP_A" and metric_key == outbound_metric.key:
            return _trend(metric_key=metric_key, verdict="declining", rel_change=-0.10)
        return None  # REP_B / strikes metric: no history -> insufficient_data

    monkeypatch.setattr(team_mod, "trend_for", fake_trend_for)

    snapshots = {
        ("REP_A", outbound_metric.key): LatestSnapshot(value=900.0, sample_size=900),
        # REP_B has no snapshot row at all for outbound -> must stay None.
    }
    recs = {"REP_A": [{"id": 1, "title": "Rep A outbound declining"}]}

    payload = assemble_team_snapshot(
        _FakeSession(), reps=reps, window="30d",
        snapshots_by_rep_and_metric=snapshots, recommendations_by_rep=recs,
    )

    check("payload has window/reps/rollup", set(payload.keys()) == {"window", "reps", "rollup"})
    check("window echoed back", payload["window"] == "30d")
    check("both reps present", len(payload["reps"]) == 2)

    rep_a = next(r for r in payload["reps"] if r["rep_id"] == "REP_A")
    rep_b = next(r for r in payload["reps"] if r["rep_id"] == "REP_B")

    check("rep A outbound value from snapshot", rep_a["metrics"][outbound_metric.key]["value"] == 900.0)
    check("rep A outbound verdict declining", rep_a["metrics"][outbound_metric.key]["verdict"] == "declining")
    check("rep A recommendations attached", rep_a["recommendations"] == recs["REP_A"])

    check("rep B outbound value is None (no snapshot, never fabricated)", rep_b["metrics"][outbound_metric.key]["value"] is None)
    check("rep B outbound verdict insufficient_data", rep_b["metrics"][outbound_metric.key]["verdict"] == "insufficient_data")
    check("rep B strikes verdict insufficient_data", rep_b["metrics"][strikes_metric.key]["verdict"] == "insufficient_data")
    check("rep B has no recommendations (default empty list)", rep_b["recommendations"] == [])

    check("rollup total_outbound only counts rep A's real value", payload["rollup"]["total_outbound"] == 900.0)
    check("rollup active_reps counts only status=='active'", payload["rollup"]["active_reps"] == 1)
    check("rollup total_reps counts both", payload["rollup"]["total_reps"] == 2)


def test_assemble_team_snapshot_empty_roster(monkeypatch) -> None:
    monkeypatch.setattr(team_mod, "rep_scoped_metrics", lambda: [])
    payload = assemble_team_snapshot(
        _FakeSession(), reps=[], window="30d",
        snapshots_by_rep_and_metric={}, recommendations_by_rep={},
    )
    check("empty roster gives empty reps list", payload["reps"] == [])
    check("empty roster rollup is zeroed", payload["rollup"]["total_reps"] == 0)


def main() -> int:
    import inspect

    for fn in (
        test_resolve_rep_exact_rep_id,
        test_resolve_rep_case_insensitive_full_name,
        test_resolve_rep_first_name_containment,
        test_resolve_rep_via_alias,
        test_resolve_rep_unknown_returns_none,
        test_resolve_rep_empty_query_returns_none,
        test_resolve_rep_can_match_terminated_rep_by_name,
        test_is_active_rep_excludes_terminated,
        test_validate_scope_global,
        test_validate_scope_rep_prefix,
        test_validate_scope_rejects_garbage,
        test_build_rep_metric_block_with_snapshot_and_trend,
        test_build_rep_metric_block_no_snapshot_no_trend_is_insufficient_data,
        test_build_rep_metric_block_no_snapshot_but_has_trend_uses_trend_latest_value,
        test_build_rep_metric_block_snapshot_value_wins_over_trend,
        test_build_team_rollup_sums_and_counts,
        test_build_team_rollup_empty_roster,
        test_assemble_team_snapshot_shape_and_no_fabrication,
        test_assemble_team_snapshot_empty_roster,
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
