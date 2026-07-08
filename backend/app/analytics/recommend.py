"""Recommendation generator — data-cited, threshold-triggered.

Runs the trend layer (``trends.py``) and emits a recommendation ONLY when the data
crosses a defined threshold. The conclusion is the statistical verdict; this layer
never invents advice. Each recommendation stores its ``evidence`` (the exact numbers),
so it is fully auditable — the "must cite" contract.

  - declining metric, |change| ≥ threshold → a recommendation (severity scales with size)
  - improving metric, |change| ≥ a higher threshold → a positive "what's working" note
  - flat / insufficient_data → NOTHING emitted (we don't manufacture findings)

Upserts on (metric_key, window, scope): a standing finding refreshes rather than
duplicating, and once the metric recovers the stale recommendation is auto-resolved
(the feedback loop).

Scopes: after the global pass, every metric that declares ``rep_sql`` (see
``registry.py``) is additionally evaluated per rep — one independent trend/finding
per ``"rep:<rep_id>"`` scope, using exactly the reps that have snapshot data for that
metric (``trends.rep_scopes_for_metric``). Rep-scoped findings are phrased with the
rep's display name and are capped at 'warn' severity (never 'critical') — a single
rep's numbers should never read as loudly as a company-wide critical finding.
"""

from __future__ import annotations

import json
import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.analytics.registry import all_metrics
from app.analytics.trends import DEFAULT_WINDOW, TrendResult, all_trends, rep_scopes_for_metric

logger = logging.getLogger(__name__)

# Thresholds (relative change). Declining is flagged sooner than improving is celebrated.
DECLINE_FLAG = 0.05      # ≥5% adverse move → recommendation
DECLINE_CRITICAL = 0.20  # ≥20% adverse move → critical
IMPROVE_HIGHLIGHT = 0.10  # ≥10% favourable move → "what's working" note

# Rep-scoped findings never exceed this severity — a single rep's numbers are never
# as loud as a company-wide critical finding, however large the move.
REP_SEVERITY_CAP = "warn"
_SEVERITY_RANK = {"info": 0, "warn": 1, "critical": 2}


def _rep_display_name(rep_id: str, names: dict[str, str]) -> str:
    """Best-effort human name for a "rep:<rep_id>" scope's rep_id, falling back to
    the raw id if the roster lookup didn't find it (e.g. a rep row deleted since)."""
    return names.get(rep_id, rep_id)


def _phrase(t: TrendResult, *, rep_display_name: str | None = None) -> tuple[str, str]:
    """Plain-language title + body, built ONLY from the data in the verdict.

    No LLM here — deterministic phrasing of the numbers. (An LLM may later re-phrase
    from the same evidence for the chat surface, but must not change the conclusion.)
    ``rep_display_name`` prefixes the title with "<Name>'s " for rep-scoped findings;
    the numbers themselves are unchanged and still come exclusively from ``t``.
    """
    pct = abs(t.rel_change or 0)
    subject = f"{rep_display_name}'s {t.label}" if rep_display_name else t.label
    if t.verdict == "declining":
        title = f"{subject} is declining ({pct:.0%} over {t.window})"
        body = (
            f"{t.label} moved from {t.baseline_value:.4g} to {t.latest_value:.4g} "
            f"between {t.baseline_date} and {t.latest_date} "
            f"({(t.rel_change or 0):+.0%}). Sample sizes {t.baseline_sample}→{t.latest_sample}. "
            f"This metric is {'higher' if t.higher_is_better else 'lower'}-is-better, so the "
            f"move is adverse — worth investigating what changed in this window."
        )
    else:  # improving
        title = f"{subject} is improving ({pct:.0%} over {t.window})"
        body = (
            f"{t.label} moved from {t.baseline_value:.4g} to {t.latest_value:.4g} "
            f"between {t.baseline_date} and {t.latest_date} "
            f"({(t.rel_change or 0):+.0%}). Whatever changed in this window is working — "
            f"worth identifying and reinforcing."
        )
    return title, body


def _severity(t: TrendResult, *, is_rep_scope: bool = False) -> str:
    if t.verdict == "declining":
        severity = "critical" if abs(t.rel_change or 0) >= DECLINE_CRITICAL else "warn"
    else:
        severity = "info"
    if is_rep_scope and _SEVERITY_RANK[severity] > _SEVERITY_RANK[REP_SEVERITY_CAP]:
        return REP_SEVERITY_CAP
    return severity


_UPSERT = text(
    """
    INSERT INTO recommendations
        (metric_key, area, "window", scope, verdict, severity, title, body, evidence, status,
         created_at, updated_at)
    VALUES
        (:metric_key, :area, :window, :scope, :verdict, :severity, :title, :body,
         CAST(:evidence AS jsonb), 'open', now(), now())
    ON CONFLICT (metric_key, "window", scope) DO UPDATE SET
        verdict    = EXCLUDED.verdict,
        severity   = EXCLUDED.severity,
        title      = EXCLUDED.title,
        body       = EXCLUDED.body,
        evidence   = EXCLUDED.evidence,
        -- a previously-resolved finding that re-triggers re-opens; otherwise keep status
        status     = CASE WHEN recommendations.status = 'resolved' THEN 'open'
                          ELSE recommendations.status END,
        updated_at = now()
    """
)

# When a metric no longer warrants a recommendation (recovered / went flat), close the
# standing one instead of leaving a stale finding. The feedback loop. Scoped per
# (window, scope) — each scope's fan-out iteration runs this with its own active_keys,
# so a rep's recovered finding doesn't get compared against another rep's active keys.
_AUTO_RESOLVE = text(
    """
    UPDATE recommendations
    SET status = 'resolved', updated_at = now()
    WHERE "window" = :window
      AND scope = :scope
      AND status <> 'resolved'
      AND metric_key <> ALL(:active_keys)
    """
)

_REP_NAMES = text("SELECT rep_id, full_name FROM sales_reps")


def _load_rep_names(db: Session) -> dict[str, str]:
    """rep_id -> full_name, one query, cached per ``generate_recommendations`` run."""
    return {row[0]: row[1] for row in db.execute(_REP_NAMES).all()}


def _evaluate_scope(
    db: Session,
    window: str,
    scope: str,
    trends: list[TrendResult],
    *,
    rep_display_name: str | None = None,
) -> list[dict]:
    """Upsert active findings for one scope's trends, auto-resolve the rest.

    Shared by the global pass and each rep-scoped pass — the only difference is which
    trends are fed in, whether severity is capped, and how the title is phrased.
    """
    is_rep_scope = rep_display_name is not None
    active_keys: list[str] = []
    emitted: list[dict] = []

    for t in trends:
        change = abs(t.rel_change or 0)
        flag = (
            (t.verdict == "declining" and change >= DECLINE_FLAG)
            or (t.verdict == "improving" and change >= IMPROVE_HIGHLIGHT)
        )
        if not flag:
            continue

        title, body = _phrase(t, rep_display_name=rep_display_name)
        severity = _severity(t, is_rep_scope=is_rep_scope)
        evidence = t.as_dict()  # the exact numbers — the audit trail
        evidence["scope"] = scope
        if rep_display_name is not None:
            evidence["rep_display_name"] = rep_display_name
        db.execute(
            _UPSERT,
            {
                "metric_key": t.metric_key,
                "area": t.area,
                "window": t.window,
                "scope": scope,
                "verdict": t.verdict,
                "severity": severity,
                "title": title,
                "body": body,
                "evidence": json.dumps(evidence),
            },
        )
        active_keys.append(t.metric_key)
        emitted.append(
            {
                "metric_key": t.metric_key,
                "scope": scope,
                "verdict": t.verdict,
                "severity": severity,
                "title": title,
            }
        )

    db.execute(
        _AUTO_RESOLVE, {"window": window, "scope": scope, "active_keys": active_keys or [""]}
    )
    return emitted


def generate_recommendations(db: Session, window: str = DEFAULT_WINDOW) -> dict:
    """Recompute recommendations from current trends. Returns a summary.

    Idempotent: upserts the active findings, auto-resolves the rest. Safe to run often.

    Global pass first (scope="global", unchanged semantics), then a per-rep pass for
    every metric that declares ``rep_sql``: each rep with snapshot data for that
    metric gets its own independently-evaluated, independently-resolved finding.
    """
    emitted: list[dict] = []

    # ─── Global pass ──────────────────────────────────────────────────────────
    trends = all_trends(db, window=window, scope="global")
    emitted.extend(_evaluate_scope(db, window, "global", trends))

    # ─── Rep-scoped pass ──────────────────────────────────────────────────────
    rep_metrics = [m for m in all_metrics() if m.rep_sql is not None]
    if rep_metrics:
        rep_names = _load_rep_names(db)
        for metric in rep_metrics:
            for scope in rep_scopes_for_metric(db, metric.key):
                rep_id = scope.removeprefix("rep:")
                rep_trend = _rep_trend(db, metric, window, scope)
                if rep_trend is None:
                    continue
                emitted.extend(
                    _evaluate_scope(
                        db,
                        window,
                        scope,
                        [rep_trend],
                        rep_display_name=_rep_display_name(rep_id, rep_names),
                    )
                )

    db.commit()

    logger.info("generate_recommendations: %d active finding(s) for window=%s", len(emitted), window)
    return {"window": window, "active": len(emitted), "recommendations": emitted}


def _rep_trend(db: Session, metric, window: str, scope: str) -> TrendResult | None:
    """One metric's trend for one rep scope. Thin wrapper kept local so tests can
    monkeypatch it independently of the global ``trend_for``/``all_trends`` path."""
    from app.analytics.trends import trend_for

    return trend_for(db, metric.key, window=window, scope=scope)


# ─── Shared read query ──────────────────────────────────────────────────────────
#
# Both `GET /analytics/recommendations` and `GET /dashboard/recommendations` need
# the same "active findings" query. Defined once here so the dashboard route never
# has to duplicate the SQL/ordering — it just adapts the rows to its own response
# shape.

_LIST_RECOMMENDATIONS_SQL = """
    SELECT id, metric_key, area, "window", scope, verdict, severity, title, body,
           evidence, status, updated_at
    FROM recommendations
    WHERE {where}
    ORDER BY CASE severity WHEN 'critical' THEN 0 WHEN 'warn' THEN 1 ELSE 2 END,
             updated_at DESC
"""


async def fetch_recommendation_rows(
    session: AsyncSession,
    *,
    status: str | None = None,
    area: str | None = None,
    scope: str | None = None,
    limit: int | None = None,
) -> list[dict]:
    """Fetch active (or filtered) recommendation rows as plain dicts.

    Defaults to the non-resolved findings, most severe first — identical semantics
    to ``GET /analytics/recommendations``. No fabrication, no padding: callers get
    back exactly however many rows match (possibly zero).

    ``scope`` defaults to ``None`` (all scopes — global + every "rep:<rep_id>").
    Existing callers (the dashboard/analytics HTTP routes) must keep returning ONLY
    the global findings by default so the current UI doesn't suddenly surface
    per-rep findings — those call sites pass ``scope="global"`` explicitly. This
    function's own default stays "all scopes" for future rep-aware callers.
    """
    where = ["1 = 1"]
    params: dict[str, object] = {}
    if status:
        where.append("status = :status")
        params["status"] = status
    else:
        where.append("status <> 'resolved'")
    if area:
        where.append("area = :area")
        params["area"] = area
    if scope is not None:
        where.append("scope = :scope")
        params["scope"] = scope

    sql = _LIST_RECOMMENDATIONS_SQL.format(where=" AND ".join(where))
    if limit is not None:
        sql += " LIMIT :limit"
        params["limit"] = limit

    rows = (await session.execute(text(sql), params)).mappings().all()
    return [dict(r) for r in rows]
