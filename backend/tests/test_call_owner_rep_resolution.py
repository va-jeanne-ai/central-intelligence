"""Unit tests for call_owner → rep resolution (app.routes.ci).

Covers the pure helpers backing the Sales Calls page's `rep` filter + the
rep_id/rep_name columns on each call row:

  - ``call_owner_match_values`` — expands a roster rep into the set of raw
    call_owner strings (full_name + historical_aliases) a SQL filter should
    match. Pure, no DB.
  - ``resolve_call_owner`` — resolves a single messy call_owner string
    ('Colton', 'Colton  Lindsay', 'Colton Lindsay') against the roster,
    reusing app.analytics.team.resolve_rep's containment/alias matching.

Self-contained assert-based checks with a pass/fail summary, matching this
suite's existing convention (tests/test_wgr_mapping.py, tests/test_analytics_team.py).
"""

from __future__ import annotations

from app.analytics.team import RepRow, call_owner_match_values
from app.routes.ci import resolve_call_owner

_failures: list[str] = []


def check(name: str, cond: bool) -> None:
    if cond:
        print(f"  ok   {name}")
    else:
        print(f"  FAIL {name}")
        _failures.append(name)


_ROSTER = [
    RepRow(
        rep_id="REP_COLTON_LINDSAY", full_name="Colton Lindsay", role="manager",
        status="active", historical_aliases="colton lindsay,colton  lindsay,colton",
    ),
    RepRow(
        rep_id="REP_NELSON_FIGUERIA", full_name="Nelson Figueria", role="discovery_setter",
        status="probation", historical_aliases=None,
    ),
    RepRow(
        rep_id="REP_TATJANA_CRISTAL", full_name="Tatjana Cristal", role="discovery_setter",
        status="active", historical_aliases="tatjana cristal,tatjana,tatiana",
    ),
]


def test_call_owner_match_values() -> None:
    colton = _ROSTER[0]
    values = call_owner_match_values(colton)
    check("includes full_name lowercased", "colton lindsay" in values)
    check("includes double-space alias", "colton  lindsay" in values)
    check("includes bare first-name alias", "colton" in values)

    nelson = _ROSTER[1]
    values2 = call_owner_match_values(nelson)
    check("no aliases → just full_name", values2 == ["nelson figueria"])


def test_resolve_call_owner_variants() -> None:
    # Documented real WGR call_owner variants for Colton Lindsay.
    for raw in ("Colton Lindsay", "Colton", "Colton  Lindsay"):
        resolved = resolve_call_owner(raw, _ROSTER)
        check(f"resolves {raw!r} to Colton", resolved is not None and resolved.rep_id == "REP_COLTON_LINDSAY")

    check("resolves Nelson exact", resolve_call_owner("Nelson Figueria", _ROSTER).rep_id == "REP_NELSON_FIGUERIA")
    check("resolves Tatjana misspelling alias", resolve_call_owner("Tatiana", _ROSTER).rep_id == "REP_TATJANA_CRISTAL")

    check("unresolvable email → None", resolve_call_owner("someone@example.com", _ROSTER) is None)
    check("None call_owner → None", resolve_call_owner(None, _ROSTER) is None)
    check("empty call_owner → None", resolve_call_owner("", _ROSTER) is None)
    check("unknown name → None", resolve_call_owner("Random Person", _ROSTER) is None)


def main() -> int:
    for fn in (test_call_owner_match_values, test_resolve_call_owner_variants):
        print(f"\n{fn.__name__}:")
        fn()
    print(f"\n{'='*40}")
    if _failures:
        print(f"FAILED: {len(_failures)} check(s): {_failures}")
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
