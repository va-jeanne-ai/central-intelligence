"""Weekly Digest — a once-a-week, LLM-synthesized synthesis of the week's analytics.

Sibling to ``overall_insight.py`` (the daily company-health verdict) rather than a
parallel system: it reuses that module's client construction, evidence-gathering
helpers, and output validation (``coerce_health_assessment``) so there is exactly one
place that knows how to talk to Claude and exactly one place that validates the
``{health_verdict, narrative, key_shifts}`` shape.

Where the daily insight looks at "today's snapshot + yesterday's narrative", the weekly
digest looks at the last 7 days as a whole:
  - every daily ``OverallInsight`` (period='daily') published in the window — so the
    week's compounding day-over-day story is available verbatim, not re-derived,
  - the CURRENT trend verdicts (30d/90d) — same statistical layer, no re-computation,
  - every recommendation that was open OR resolved during the week — so the digest can
    speak to both standing issues and things that got fixed.

Same contract as the daily insight: the LLM only PHRASES this recorded evidence. It
never originates a number. ``mock_mode`` (default on) returns a canned digest so the
pipeline is testable for free before any paid call, and the task no-ops (no LLM call)
entirely when there is no evidence for the week at all.
"""

from __future__ import annotations

import json
import logging
from datetime import date, timedelta

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.analytics.overall_insight import (
    MODEL,
    _active_recommendations,
    _latest_metric_values,
    call_claude_for_json,
    coerce_health_assessment,
)
from app.analytics.trends import all_trends
from app.config import settings

logger = logging.getLogger(__name__)

# A canned digest used when no API key is set or mock_mode is on — shaped exactly like
# the real LLM output so the parse/validate/upsert path is exercised for free.
MOCK_WEEKLY_DIGEST = {
    "health_verdict": "watch",
    "narrative": (
        "This is a mock weekly digest generated without an LLM call (mock_mode is "
        "on). The week's daily assessments, trend verdicts, and recommendation "
        "activity are gathered and would be sent to Claude here.\n\n"
        "Once mock_mode is disabled and an Anthropic key is configured, this "
        "paragraph is replaced by a real synthesis of the week across sales, "
        "marketing, and fulfillment."
    ),
    "key_shifts": [
        "Mock mode — no real shifts computed.",
        "Set MOCK_MODE=false and ANTHROPIC_API_KEY to generate a live digest.",
    ],
}


# ─── Input gathering ──────────────────────────────────────────────────────────


def _week_range(today: date | None = None) -> tuple[date, date]:
    """The 7-day window the digest covers: [today - 6 days, today], inclusive."""
    end = today or date.today()
    start = end - timedelta(days=6)
    return start, end


def _daily_insights_for_week(db: Session, start: date, end: date) -> list[dict]:
    """Every published daily ``OverallInsight`` in [start, end], oldest first."""
    rows = db.execute(
        text(
            """
            SELECT insight_date, health_verdict, narrative, key_shifts
            FROM overall_insights
            WHERE period = 'daily' AND insight_date BETWEEN :start AND :end
            ORDER BY insight_date ASC
            """
        ),
        {"start": start, "end": end},
    ).mappings().all()
    return [
        {
            "insight_date": r["insight_date"].isoformat(),
            "health_verdict": r["health_verdict"],
            "narrative": r["narrative"],
            "key_shifts": list(r["key_shifts"] or []),
        }
        for r in rows
    ]


def _recommendation_activity_for_week(db: Session, start: date, end: date) -> dict:
    """Recommendations touched during the week — currently open, and resolved-in-week.

    Distinct from ``_active_recommendations`` (a live snapshot): the digest also wants
    to speak to what got *resolved* this week, which a point-in-time "active" query
    can't see once it's resolved.
    """
    still_open = _active_recommendations(db)
    resolved_in_week = db.execute(
        text(
            """
            SELECT metric_key, area, "window", verdict, severity, title, body
            FROM recommendations
            WHERE status = 'resolved'
              AND updated_at::date BETWEEN :start AND :end
            ORDER BY updated_at DESC
            """
        ),
        {"start": start, "end": end},
    ).mappings().all()
    return {
        "still_open": still_open,
        "resolved_this_week": [dict(r) for r in resolved_in_week],
    }


def _fetch_previous_digest(db: Session, before: date) -> dict | None:
    """The most recent weekly digest anchored strictly before ``before`` (None if none).

    Mirrors ``overall_insight._fetch_previous`` but scoped to period='weekly', so this
    week's digest can carry continuity from last week's without touching daily rows.
    """
    row = db.execute(
        text(
            """
            SELECT id, insight_date, period_end, health_verdict, narrative
            FROM overall_insights
            WHERE period = 'weekly' AND insight_date < :before
            ORDER BY insight_date DESC LIMIT 1
            """
        ),
        {"before": before},
    ).mappings().first()
    return dict(row) if row else None


def _gather_weekly_evidence(db: Session, start: date, end: date) -> dict:
    """Assemble the bounded weekly evidence payload the LLM reasons over."""
    trends_30d = [t.as_dict() for t in all_trends(db, window="30d")]
    trends_90d = [t.as_dict() for t in all_trends(db, window="90d")]
    return {
        "week_start": start.isoformat(),
        "week_end": end.isoformat(),
        "daily_insights": _daily_insights_for_week(db, start, end),
        "metrics_30d": _latest_metric_values(db, "30d"),
        "metrics_all": _latest_metric_values(db, "all"),
        "trends_30d": trends_30d,
        "trends_90d": trends_90d,
        "recommendation_activity": _recommendation_activity_for_week(db, start, end),
    }


def has_evidence(evidence: dict) -> bool:
    """True if there's anything at all for the LLM to synthesize this week.

    Deliberately conservative: if there isn't a single daily insight, metric value, or
    recommendation touched this week, the week is empty and the caller should no-op
    rather than spend a paid call summarizing nothing.
    """
    if evidence["daily_insights"]:
        return True
    if any(m["value"] is not None for m in evidence["metrics_30d"] + evidence["metrics_all"]):
        return True
    rec_activity = evidence["recommendation_activity"]
    if rec_activity["still_open"] or rec_activity["resolved_this_week"]:
        return True
    if any(t["verdict"] != "insufficient_data" for t in evidence["trends_30d"] + evidence["trends_90d"]):
        return True
    return False


# ─── Prompt construction ──────────────────────────────────────────────────────

_SYSTEM_PROMPT = (
    "You are the Central Intelligence analyst for a coaching/consulting business. "
    "You write a concise, executive-level WEEKLY DIGEST strictly from the analytics "
    "provided — the week's daily health assessments, current trend verdicts, and "
    "recommendation activity (what's still open, what got resolved). Do not invent "
    "numbers or claims beyond the evidence. Be candid: if signals are thin or "
    "insufficient, say so rather than overstating.\n\n"
    "Respond with ONLY a JSON object, no prose around it, of exactly this shape:\n"
    "{\n"
    '  "health_verdict": "healthy" | "watch" | "at_risk",\n'
    '  "narrative": "2-4 short paragraphs separated by a blank line (\\n\\n), '
    'synthesizing the WEEK as a whole rather than repeating each day",\n'
    '  "key_shifts": ["short bullet", "..."]\n'
    "}\n"
    "Pick health_verdict by weighing the week's daily verdicts, the current trend "
    "verdicts, and recommendation activity (open + resolved). key_shifts should name "
    "the most important changes over the WEEK (3-6 items), including anything "
    "resolved this week worth calling out as a win."
)


def _build_user_prompt(evidence: dict, previous: dict | None) -> str:
    parts: list[str] = []
    if previous is None:
        parts.append(
            "This is the GENESIS weekly digest — the first weekly synthesis. "
            "Summarize the week across sales, marketing, and fulfillment."
        )
    else:
        parts.append(
            "This is a WEEKLY UPDATE. Below is last week's digest, then this week's "
            "analytics. Produce an updated digest, noting what changed since last "
            "week. Carry forward continuity but reflect this week's data.\n\n"
            f"=== Last week (ending {previous['insight_date']}) — verdict: "
            f"{previous['health_verdict']} ===\n{previous['narrative']}"
        )
    parts.append("=== This week's analytics (JSON) ===")
    parts.append(json.dumps(evidence, default=str, indent=2))
    return "\n\n".join(parts)


# ─── LLM call ─────────────────────────────────────────────────────────────────


def _synthesize(evidence: dict, previous: dict | None) -> tuple[dict, str]:
    """Return (parsed_digest, model_used). Falls back to mock when configured."""
    if not settings.anthropic_api_key or settings.mock_mode:
        logger.warning(
            "weekly_digest: Anthropic key missing or mock_mode=True — using mock output."
        )
        return dict(MOCK_WEEKLY_DIGEST), "mock"

    parsed = call_claude_for_json(_SYSTEM_PROMPT, _build_user_prompt(evidence, previous))
    return parsed, MODEL


# ─── Persistence ──────────────────────────────────────────────────────────────

_UPSERT = text(
    """
    INSERT INTO overall_insights
        (insight_date, period, period_end, status, health_verdict, narrative,
         key_shifts, evidence, model, previous_insight_id, generated_at)
    VALUES
        (:week_start, 'weekly', :week_end, 'published', :health_verdict, :narrative,
         :key_shifts, :evidence, :model, :previous_insight_id, now())
    ON CONFLICT (insight_date, period) DO UPDATE SET
        period_end          = EXCLUDED.period_end,
        status              = 'published',
        health_verdict      = EXCLUDED.health_verdict,
        narrative           = EXCLUDED.narrative,
        key_shifts          = EXCLUDED.key_shifts,
        evidence            = EXCLUDED.evidence,
        model               = EXCLUDED.model,
        previous_insight_id = EXCLUDED.previous_insight_id,
        generated_at        = now()
    RETURNING id, insight_date, period_end, health_verdict, narrative, key_shifts,
              model, previous_insight_id, generated_at
    """
)


def generate_weekly_digest(db: Session, *, today: date | None = None) -> dict | None:
    """Generate (or regenerate) this week's digest and upsert it.

    Returns a dict of the persisted row, or None if there was no evidence for the week
    at all (no-op: no LLM call, nothing written). One paid LLM call otherwise, unless
    mock_mode is on.
    """
    start, end = _week_range(today)
    evidence = _gather_weekly_evidence(db, start, end)

    if not has_evidence(evidence):
        logger.info("weekly_digest: no evidence for week %s..%s — no-op.", start, end)
        return None

    previous = _fetch_previous_digest(db, start)
    parsed, model_used = _synthesize(evidence, previous)
    digest = coerce_health_assessment(parsed)

    row = db.execute(
        _UPSERT,
        {
            "week_start": start,
            "week_end": end,
            "health_verdict": digest["health_verdict"],
            "narrative": digest["narrative"],
            "key_shifts": json.dumps(digest["key_shifts"]),
            "evidence": json.dumps(evidence, default=str),
            "model": model_used,
            "previous_insight_id": (previous["id"] if previous else None),
        },
    ).mappings().first()
    db.commit()

    logger.info(
        "weekly_digest: %s digest for week %s..%s (verdict=%s, model=%s)",
        "genesis" if previous is None else "weekly",
        row["insight_date"],
        row["period_end"],
        row["health_verdict"],
        model_used,
    )
    return {
        "week_start": row["insight_date"].isoformat(),
        "week_end": row["period_end"].isoformat() if row["period_end"] else None,
        "health_verdict": row["health_verdict"],
        "narrative": row["narrative"],
        "key_shifts": row["key_shifts"],
        "previous_week_start": (previous["insight_date"].isoformat() if previous else None),
        "model": row["model"],
        "generated_at": row["generated_at"].isoformat(),
    }
