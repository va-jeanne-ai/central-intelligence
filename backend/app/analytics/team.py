"""Per-rep team analytics — the roster × rep-scoped-metric assembly layer.

Backs ``GET /analytics/team`` and the CI chat tool's rep-scoping. Pulls together
three engine pieces that PR 1 already built:

  - the roster (``sales_reps``, non-terminated)
  - rep-scoped metric snapshots (``metric_snapshots`` where ``scope = 'rep:<id>'``)
  - rep-scoped trend verdicts (``trends.trend_for(..., scope=f"rep:{rep_id}")``)
  - rep-scoped open recommendations (``recommend.fetch_recommendation_rows``)

Pure-data contract, same as the rest of the engine: a rep with no snapshot row for
a metric gets ``value=None`` / ``verdict="insufficient_data"`` — never a fabricated
zero. Terminated reps never appear.

The assembly functions here are split so they're testable with plain dicts / fake
sessions (mirroring ``tests/test_recommend.py``'s style) rather than requiring a
live Postgres connection:

  - ``build_rep_metric_block`` — pure function, one rep × one metric → a dict.
  - ``build_team_rollup`` — pure function, the roster + per-rep metric blocks →
    the small team-level summary.
  - ``assemble_team_snapshot`` — the impure orchestrator: takes a sync ``Session``
    (for ``trend_for``) and the already-fetched rep rows / latest-snapshot rows /
    recommendation rows, and produces the full response payload. Fetching those
    rows is left to the caller (the route) so this function never has to know
    whether the caller is using a sync or async session for reads.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.analytics.registry import Metric, all_metrics
from app.analytics.trends import trend_for

# Reps in this status never show up in team-facing surfaces (offboarded).
_EXCLUDED_STATUSES = {"terminated"}

# "rep:<rep_id>" — validated wherever a caller-supplied scope string is accepted.
REP_SCOPE_RE = re.compile(r"^rep:.+$")
_VALID_SCOPE_LITERALS = {"global"}


@dataclass(frozen=True)
class RepRow:
    """A minimal view of one ``sales_reps`` row — only what the team surface +
    CI rep-resolution need. ``historical_aliases`` is the raw comma-separated,
    lowercase text column (``None`` when a rep has none) — used only by
    ``resolve_rep``; the team endpoint itself never surfaces it."""

    rep_id: str
    full_name: str
    role: str | None
    status: str
    historical_aliases: str | None = None


@dataclass(frozen=True)
class LatestSnapshot:
    """One rep-scoped metric's latest snapshot value, or absence thereof."""

    value: float | None
    sample_size: int | None


def is_active_rep(rep: RepRow) -> bool:
    """True unless the rep's status excludes them from team-facing surfaces."""
    return rep.status not in _EXCLUDED_STATUSES


def call_owner_match_values(rep: RepRow) -> list[str]:
    """Every raw ``call_owner`` string variant that should resolve to ``rep``.

    Combines ``full_name`` with each comma-split ``historical_aliases`` entry
    (title-cased back to a plausible display form, since aliases are stored
    lowercase) so a SQL ``call_owner IN (...)`` (case-insensitive) filter can
    match the messy variants WGR actually wrote ('Colton', 'Colton  Lindsay').
    Pure — no DB access — so it's unit-testable against fixed rep rows.
    """
    values = {rep.full_name.strip().lower()}
    if rep.historical_aliases:
        for alias in rep.historical_aliases.split(","):
            a = alias.strip().lower()
            if a:
                values.add(a)
    return sorted(values)


def validate_scope(scope: str) -> bool:
    """True if ``scope`` is a well-formed value for the ``scope`` query param —
    either the literal ``"global"`` or ``"rep:<anything non-empty>"``.

    Used by both ``/analytics/trends`` and ``/analytics/recommendations`` to 422
    on garbage rather than silently querying an unrecognized scope.
    """
    if scope in _VALID_SCOPE_LITERALS:
        return True
    return bool(REP_SCOPE_RE.match(scope))


def rep_scoped_metrics() -> list[Metric]:
    """Every registered metric that declares a per-rep breakdown (``rep_sql``)."""
    return [m for m in all_metrics() if m.rep_sql is not None]


def build_rep_metric_block(
    metric: Metric,
    *,
    snapshot: LatestSnapshot | None,
    trend: object | None,  # trends.TrendResult, kept loosely typed to avoid import cycles in tests
) -> dict:
    """One rep's block for one metric: latest value/sample_size + trend verdict.

    ``snapshot`` is ``None`` when the rep has no snapshot row at all for this
    metric/window — the block still gets emitted, just with ``value=None`` and
    an ``insufficient_data`` verdict (never an invented 0). ``trend`` is whatever
    ``trends.trend_for`` returned (also ``None``-safe: a metric with no rows uses
    the same insufficient-data fallback trend_for itself already returns).
    """
    value = snapshot.value if snapshot is not None else None
    sample_size = snapshot.sample_size if snapshot is not None else None

    if trend is not None:
        verdict = trend.verdict
        rel_change = trend.rel_change
        baseline_value = trend.baseline_value
        latest_value_from_trend = trend.latest_value
        reason = trend.reason
        # Prefer the trend's own latest_value when we have no separate snapshot
        # value (e.g. caller only fetched the trend series) — but never overwrite
        # a real snapshot-sourced value with something else.
        if value is None:
            value = latest_value_from_trend
    else:
        verdict = "insufficient_data"
        rel_change = None
        baseline_value = None
        reason = "No snapshot history for this rep/metric yet."

    return {
        "metric_key": metric.key,
        "label": metric.label,
        "area": metric.area,
        "unit": metric.unit,
        "higher_is_better": metric.higher_is_better,
        "value": value,
        "sample_size": sample_size,
        "verdict": verdict,
        "rel_change": rel_change,
        "baseline_value": baseline_value,
        "reason": reason,
    }


def build_team_rollup(rep_entries: list[dict]) -> dict:
    """Small team-level rollup computed from the already-assembled per-rep blocks —
    no new SQL. Sums outbound volume + open strikes across reps with a real value,
    and counts active reps (status == 'active', already filtered to non-terminated
    upstream).

    ``rep_entries`` is the list of per-rep dicts this module builds in
    ``assemble_team_snapshot`` (each has ``status`` and ``metrics``).
    """
    total_outbound = 0.0
    total_open_strikes = 0.0
    active_reps = 0

    for entry in rep_entries:
        if entry.get("status") == "active":
            active_reps += 1
        for block in entry.get("metrics", {}).values():
            if block["metric_key"] == "sales.outbound_volume" and block["value"] is not None:
                total_outbound += block["value"]
            elif block["metric_key"] == "fulfillment.open_coaching_strikes" and block["value"] is not None:
                total_open_strikes += block["value"]

    return {
        "total_outbound": total_outbound,
        "open_strikes": total_open_strikes,
        "active_reps": active_reps,
        "total_reps": len(rep_entries),
    }


def assemble_team_snapshot(
    db: Session,
    *,
    reps: list[RepRow],
    window: str,
    snapshots_by_rep_and_metric: dict[tuple[str, str], LatestSnapshot],
    recommendations_by_rep: dict[str, list[dict]],
) -> dict:
    """Build the full ``/analytics/team`` payload.

    ``db`` is a sync ``Session`` used only to call ``trends.trend_for`` (which is
    itself sync). All other data — the roster, the latest snapshot per
    (rep_id, metric_key), and each rep's open recommendations — is fetched by the
    caller and passed in, so this function is testable with a fake/no-op session
    plus plain dicts (mirroring ``tests/test_recommend.py``).

    Terminated reps must already be filtered out of ``reps`` by the caller (the
    roster query itself excludes them, same as ``snapshots.py``'s fan-out).
    """
    metrics = rep_scoped_metrics()
    rep_entries: list[dict] = []

    for rep in reps:
        metric_blocks: dict[str, dict] = {}
        for metric in metrics:
            snapshot = snapshots_by_rep_and_metric.get((rep.rep_id, metric.key))
            trend = trend_for(db, metric.key, window=window, scope=f"rep:{rep.rep_id}")
            metric_blocks[metric.key] = build_rep_metric_block(
                metric, snapshot=snapshot, trend=trend
            )

        rep_entries.append(
            {
                "rep_id": rep.rep_id,
                "full_name": rep.full_name,
                "role": rep.role,
                "status": rep.status,
                "metrics": metric_blocks,
                "recommendations": recommendations_by_rep.get(rep.rep_id, []),
            }
        )

    rollup = build_team_rollup(rep_entries)

    return {
        "window": window,
        "reps": rep_entries,
        "rollup": rollup,
    }


# ─── Rep resolution — used by the CI chat tool's optional `rep` input ───────────


def _normalize_name(s: str) -> str:
    return " ".join(s.strip().lower().split())


def resolve_rep(query: str, reps: list[RepRow]) -> RepRow | None:
    """Resolve a free-text ``rep`` input (from the CI chat tool) against the roster.

    Match order (first hit wins), all against the full (including terminated)
    roster passed in — the caller decides whether to also allow resolving a
    terminated rep by name; matching itself doesn't special-case status:

      1. Exact ``rep_id`` match (case-sensitive — rep_ids are already a stable key).
      2. Case-insensitive ``full_name`` match — exact match first, then containment
         (either direction) so a bare first name like "Makyla" resolves to "Makyla
         Thompson" even when that rep has no ``historical_aliases`` row at all.
      3. Containment in ``historical_aliases`` (comma-separated, lowercase) — an
         alias entry matches if the normalized query equals one of the comma-split
         aliases, OR the query is a substring of one alias / an alias is a
         substring of the query (handles "colton" matching "colton lindsay").

    Ambiguous containment matches (query matches more than one rep at the same
    match tier) are treated as unresolved — never guess between two reps.

    Returns ``None`` if nothing matches (or a match is ambiguous) — callers must
    not guess.
    """
    if not query or not query.strip():
        return None

    q = query.strip()
    q_norm = _normalize_name(q)

    # 1. Exact rep_id.
    for rep in reps:
        if rep.rep_id == q:
            return rep

    # 2a. Exact full_name (case-insensitive).
    for rep in reps:
        if _normalize_name(rep.full_name) == q_norm:
            return rep

    # 2b. full_name containment (either direction) — e.g. "Makyla" -> "Makyla Thompson".
    name_hits = [
        rep for rep in reps
        if q_norm in _normalize_name(rep.full_name) or _normalize_name(rep.full_name) in q_norm
    ]
    if len(name_hits) == 1:
        return name_hits[0]

    # 3. historical_aliases containment.
    alias_hits: list[RepRow] = []
    for rep in reps:
        aliases_raw = rep.historical_aliases
        if not aliases_raw:
            continue
        aliases = [_normalize_name(a) for a in aliases_raw.split(",") if a.strip()]
        if any(q_norm == alias or q_norm in alias or alias in q_norm for alias in aliases):
            alias_hits.append(rep)
    if len(alias_hits) == 1:
        return alias_hits[0]

    return None
