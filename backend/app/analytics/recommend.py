"""Recommendation generator — data-cited, threshold-triggered.

Runs the trend layer (``trends.py``) and emits a recommendation ONLY when the data
crosses a defined threshold. The conclusion is the statistical verdict; this layer
never invents advice. Each recommendation stores its ``evidence`` (the exact numbers),
so it is fully auditable — the "must cite" contract.

  - declining metric, |change| ≥ threshold → a recommendation (severity scales with size)
  - improving metric, |change| ≥ a higher threshold → a positive "what's working" note
  - flat / insufficient_data → NOTHING emitted (we don't manufacture findings)

Upserts on (metric_key, window): a standing finding refreshes rather than duplicating,
and once the metric recovers the stale recommendation is auto-resolved (the feedback loop).
"""

from __future__ import annotations

import json
import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.analytics.trends import DEFAULT_WINDOW, TrendResult, all_trends

logger = logging.getLogger(__name__)

# Thresholds (relative change). Declining is flagged sooner than improving is celebrated.
DECLINE_FLAG = 0.05      # ≥5% adverse move → recommendation
DECLINE_CRITICAL = 0.20  # ≥20% adverse move → critical
IMPROVE_HIGHLIGHT = 0.10  # ≥10% favourable move → "what's working" note


def _phrase(t: TrendResult) -> tuple[str, str]:
    """Plain-language title + body, built ONLY from the data in the verdict.

    No LLM here — deterministic phrasing of the numbers. (An LLM may later re-phrase
    from the same evidence for the chat surface, but must not change the conclusion.)
    """
    pct = abs(t.rel_change or 0)
    if t.verdict == "declining":
        title = f"{t.label} is declining ({pct:.0%} over {t.window})"
        body = (
            f"{t.label} moved from {t.baseline_value:.4g} to {t.latest_value:.4g} "
            f"between {t.baseline_date} and {t.latest_date} "
            f"({(t.rel_change or 0):+.0%}). Sample sizes {t.baseline_sample}→{t.latest_sample}. "
            f"This metric is {'higher' if t.higher_is_better else 'lower'}-is-better, so the "
            f"move is adverse — worth investigating what changed in this window."
        )
    else:  # improving
        title = f"{t.label} is improving ({pct:.0%} over {t.window})"
        body = (
            f"{t.label} moved from {t.baseline_value:.4g} to {t.latest_value:.4g} "
            f"between {t.baseline_date} and {t.latest_date} "
            f"({(t.rel_change or 0):+.0%}). Whatever changed in this window is working — "
            f"worth identifying and reinforcing."
        )
    return title, body


def _severity(t: TrendResult) -> str:
    if t.verdict == "declining":
        return "critical" if abs(t.rel_change or 0) >= DECLINE_CRITICAL else "warn"
    return "info"


_UPSERT = text(
    """
    INSERT INTO recommendations
        (metric_key, area, "window", verdict, severity, title, body, evidence, status,
         created_at, updated_at)
    VALUES
        (:metric_key, :area, :window, :verdict, :severity, :title, :body,
         CAST(:evidence AS jsonb), 'open', now(), now())
    ON CONFLICT (metric_key, "window") DO UPDATE SET
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
# standing one instead of leaving a stale finding. The feedback loop.
_AUTO_RESOLVE = text(
    """
    UPDATE recommendations
    SET status = 'resolved', updated_at = now()
    WHERE "window" = :window
      AND status <> 'resolved'
      AND metric_key <> ALL(:active_keys)
    """
)


def generate_recommendations(db: Session, window: str = DEFAULT_WINDOW) -> dict:
    """Recompute recommendations from current trends. Returns a summary.

    Idempotent: upserts the active findings, auto-resolves the rest. Safe to run often.
    """
    trends = all_trends(db, window=window)
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

        title, body = _phrase(t)
        evidence = t.as_dict()  # the exact numbers — the audit trail
        db.execute(
            _UPSERT,
            {
                "metric_key": t.metric_key,
                "area": t.area,
                "window": t.window,
                "verdict": t.verdict,
                "severity": _severity(t),
                "title": title,
                "body": body,
                "evidence": json.dumps(evidence),
            },
        )
        active_keys.append(t.metric_key)
        emitted.append({"metric_key": t.metric_key, "verdict": t.verdict, "severity": _severity(t), "title": title})

    # Auto-resolve standing findings that no longer trigger.
    db.execute(_AUTO_RESOLVE, {"window": window, "active_keys": active_keys or [""]})
    db.commit()

    logger.info("generate_recommendations: %d active finding(s) for window=%s", len(emitted), window)
    return {"window": window, "active": len(emitted), "recommendations": emitted}


# ─── Shared read query ──────────────────────────────────────────────────────────
#
# Both `GET /analytics/recommendations` and `GET /dashboard/recommendations` need
# the same "active findings" query. Defined once here so the dashboard route never
# has to duplicate the SQL/ordering — it just adapts the rows to its own response
# shape.

_LIST_RECOMMENDATIONS_SQL = """
    SELECT id, metric_key, area, "window", verdict, severity, title, body,
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
    limit: int | None = None,
) -> list[dict]:
    """Fetch active (or filtered) recommendation rows as plain dicts.

    Defaults to the non-resolved findings, most severe first — identical semantics
    to ``GET /analytics/recommendations``. No fabrication, no padding: callers get
    back exactly however many rows match (possibly zero).
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

    sql = _LIST_RECOMMENDATIONS_SQL.format(where=" AND ".join(where))
    if limit is not None:
        sql += " LIMIT :limit"
        params["limit"] = limit

    rows = (await session.execute(text(sql), params)).mappings().all()
    return [dict(r) for r in rows]
