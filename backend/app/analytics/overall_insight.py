"""Overall Insight — a daily, LLM-synthesized company-level health assessment.

Where the rest of the analytics engine is purely statistical (snapshots → trends →
recommendations), this layer adds a *narrative* on top: it hands the already-distilled
analytics (trend verdicts, active recommendations, latest metric values) to Claude and
asks for a holistic read of the business — a health verdict, a short narrative, and the
key shifts since yesterday.

It compounds. The genesis assessment is generated from the full analytics picture; every
later day is generated from today's analytics PLUS the previous day's narrative, so the
story carries forward via ``OverallInsight.previous_insight_id``.

Sync, like ``compute_snapshots`` / ``generate_recommendations`` — it runs over a sync
SQLAlchemy session and uses the sync ``anthropic.Anthropic`` client (mirroring
``app/tasks/call_analyzer.py``). ``mock_mode`` (default on) returns a canned assessment
so the whole pipeline is testable for free before any paid call.
"""

from __future__ import annotations

import json
import logging
from datetime import date

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.analytics._json import extract_json_object
from app.analytics.registry import all_metrics
from app.analytics.trends import all_trends
from app.config import settings

logger = logging.getLogger(__name__)

MODEL = settings.anthropic_model_default
_VALID_VERDICTS = {"healthy", "watch", "at_risk"}

# A canned assessment used when no API key is set or mock_mode is on. Shaped exactly
# like the real LLM output so the parse/validate/upsert path is exercised for free.
MOCK_OVERALL_INSIGHT = {
    "health_verdict": "watch",
    "narrative": (
        "This is a mock overall assessment generated without an LLM call "
        "(mock_mode is on). The analytics engine has the data wired through — "
        "metric trends and active recommendations are gathered and would be sent "
        "to Claude here.\n\n"
        "Once mock_mode is disabled and an Anthropic key is configured, this "
        "paragraph is replaced by a real synthesis of the company's current health "
        "across sales, marketing, and fulfillment."
    ),
    "key_shifts": [
        "Mock mode — no real shifts computed.",
        "Set MOCK_MODE=false and ANTHROPIC_API_KEY to generate a live assessment.",
    ],
}


# ─── Input gathering ──────────────────────────────────────────────────────────
#
# ``_latest_metric_values`` / ``_active_recommendations`` / ``_gather_evidence`` are
# reused as-is by ``app.analytics.weekly_digest`` (same distilled-evidence shape); kept
# public-ish (module-level, no leading-underscore renaming) so that import stays a
# straight function reference rather than a copy-paste.


def _latest_metric_values(db: Session, window: str) -> list[dict]:
    """Latest snapshot value per registered metric for ``window`` (compact)."""
    out: list[dict] = []
    for m in all_metrics():
        row = db.execute(
            text(
                """
                SELECT value, sample_size, captured_date
                FROM metric_snapshots
                WHERE metric_key = :k AND "window" = :w AND scope = 'global'
                ORDER BY captured_date DESC LIMIT 1
                """
            ),
            {"k": m.key, "w": window},
        ).mappings().first()
        out.append(
            {
                "metric": m.key,
                "label": m.label,
                "area": m.area,
                "unit": m.unit,
                "higher_is_better": m.higher_is_better,
                "value": (float(row["value"]) if row else None),
                "sample_size": (int(row["sample_size"]) if row else None),
                "as_of": (row["captured_date"].isoformat() if row else None),
            }
        )
    return out


def _active_recommendations(db: Session) -> list[dict]:
    """The live (non-resolved) recommendations, severity-ordered — same as the API."""
    rows = db.execute(
        text(
            """
            SELECT metric_key, area, "window", verdict, severity, title, body
            FROM recommendations
            WHERE status <> 'resolved'
            ORDER BY CASE severity WHEN 'critical' THEN 0 WHEN 'warn' THEN 1 ELSE 2 END,
                     updated_at DESC
            """
        )
    ).mappings().all()
    return [dict(r) for r in rows]


def _gather_evidence(db: Session) -> dict:
    """Assemble the bounded analytics payload the LLM reasons over.

    Deliberately the *distilled* layer (verdicts + numbers + recommendations), not raw
    rows — small enough to fit comfortably and already grounded in the data.
    """
    trends_30d = [t.as_dict() for t in all_trends(db, window="30d")]
    trends_90d = [t.as_dict() for t in all_trends(db, window="90d")]
    return {
        "metrics_30d": _latest_metric_values(db, "30d"),
        "metrics_all": _latest_metric_values(db, "all"),
        "trends_30d": trends_30d,
        "trends_90d": trends_90d,
        "recommendations": _active_recommendations(db),
    }


def _fetch_previous(db: Session) -> dict | None:
    """The most recent DAILY assessment from a strictly-earlier day (None if none).

    Strictly-earlier so a same-day regenerate never links to itself and never corrupts
    tomorrow's chain. Scoped to period='daily' so the weekly digest (which shares this
    table) is never mistaken for yesterday's daily assessment.
    """
    row = db.execute(
        text(
            """
            SELECT id, insight_date, health_verdict, narrative
            FROM overall_insights
            WHERE insight_date < CURRENT_DATE AND period = 'daily'
            ORDER BY insight_date DESC LIMIT 1
            """
        )
    ).mappings().first()
    return dict(row) if row else None


# ─── Prompt construction ──────────────────────────────────────────────────────

_SYSTEM_PROMPT = (
    "You are the Central Intelligence analyst for a coaching/consulting business. "
    "You write a concise, executive-level health assessment of the company strictly "
    "from the analytics provided — metric values, trend verdicts, and data-cited "
    "recommendations. Do not invent numbers or claims beyond the evidence. Be candid: "
    "if signals are thin or insufficient, say so rather than overstating.\n\n"
    "Respond with ONLY a JSON object, no prose around it, of exactly this shape:\n"
    "{\n"
    '  "health_verdict": "healthy" | "watch" | "at_risk",\n'
    '  "narrative": "2-3 short paragraphs separated by a blank line (\\n\\n)",\n'
    '  "key_shifts": ["short bullet", "..."]\n'
    "}\n"
    "Pick health_verdict by weighing the trend verdicts and the severity of active "
    "recommendations. key_shifts should name the most important changes (3-6 items); "
    "for the genesis assessment, summarize the current standout strengths and risks."
)


def _build_user_prompt(evidence: dict, previous: dict | None) -> str:
    parts: list[str] = []
    if previous is None:
        parts.append(
            "This is the GENESIS assessment — the first overall read of the company. "
            "Summarize where things stand across sales, marketing, and fulfillment."
        )
    else:
        parts.append(
            "This is a DAILY UPDATE. Below is yesterday's assessment, then today's "
            "analytics. Produce an updated assessment, noting what changed since "
            "yesterday. Carry forward continuity but reflect the latest data.\n\n"
            f"=== Yesterday ({previous['insight_date']}) — verdict: "
            f"{previous['health_verdict']} ===\n{previous['narrative']}"
        )
    parts.append("=== Today's analytics (JSON) ===")
    parts.append(json.dumps(evidence, default=str, indent=2))
    return "\n\n".join(parts)


# ─── LLM call ─────────────────────────────────────────────────────────────────
#
# ``call_claude_for_json`` is the shared "hit Claude, extract the JSON object" plumbing
# — reused by ``app.analytics.weekly_digest`` so the client construction / model choice
# / JSON-extraction path lives in exactly one place. Mock-mode / missing-key handling
# stays per-caller (each has its own MOCK_* constant shaped like its own output).


def call_claude_for_json(system_prompt: str, user_prompt: str, *, max_tokens: int = 2048) -> dict:
    """Call Claude with a system+user prompt pair and return the parsed JSON object.

    No mock handling here — callers check ``settings.anthropic_api_key`` /
    ``settings.mock_mode`` themselves first (they each have their own canned fallback
    shaped like their own output contract).
    """
    import anthropic  # lazy import — large module

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    message = client.messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )
    raw = message.content[0].text
    return json.loads(extract_json_object(raw))


def _synthesize(evidence: dict, previous: dict | None) -> tuple[dict, str]:
    """Return (parsed_assessment, model_used). Falls back to mock when configured."""
    if not settings.anthropic_api_key or settings.mock_mode:
        logger.warning(
            "overall_insight: Anthropic key missing or mock_mode=True — using mock output."
        )
        return dict(MOCK_OVERALL_INSIGHT), "mock"

    parsed = call_claude_for_json(_SYSTEM_PROMPT, _build_user_prompt(evidence, previous))
    return parsed, MODEL


def coerce_health_assessment(parsed: dict) -> dict:
    """Validate/normalize an LLM assessment into the three stored fields.

    Shared by the daily overall insight AND the weekly digest — both ask Claude for
    the same ``{health_verdict, narrative, key_shifts}`` shape, so both validate it the
    same way. A neutral 'watch' default beats failing the whole generation on a
    malformed verdict.
    """
    verdict = str(parsed.get("health_verdict", "")).strip().lower()
    if verdict not in _VALID_VERDICTS:
        verdict = "watch"  # neutral default rather than fail the whole generation
    narrative = parsed.get("narrative")
    if not isinstance(narrative, str) or not narrative.strip():
        narrative = "No assessment text was produced."
    shifts = parsed.get("key_shifts", [])
    if not isinstance(shifts, list):
        shifts = []
    shifts = [str(s).strip() for s in shifts if str(s).strip()]
    return {"health_verdict": verdict, "narrative": narrative.strip(), "key_shifts": shifts}


# Back-compat alias — keep the original private name working for any existing callers
# / tests that import ``_coerce`` directly.
_coerce = coerce_health_assessment


# ─── Persistence ──────────────────────────────────────────────────────────────

_UPSERT = text(
    """
    INSERT INTO overall_insights
        (insight_date, period, status, health_verdict, narrative, key_shifts, evidence,
         model, previous_insight_id, generated_at)
    VALUES
        (CURRENT_DATE, 'daily', 'published', :health_verdict, :narrative, :key_shifts,
         :evidence, :model, :previous_insight_id, now())
    ON CONFLICT (insight_date, period) DO UPDATE SET
        status              = 'published',
        health_verdict      = EXCLUDED.health_verdict,
        narrative           = EXCLUDED.narrative,
        key_shifts          = EXCLUDED.key_shifts,
        evidence            = EXCLUDED.evidence,
        model               = EXCLUDED.model,
        previous_insight_id = EXCLUDED.previous_insight_id,
        generated_at        = now()
    RETURNING id, insight_date, health_verdict, narrative, key_shifts, model,
              previous_insight_id, generated_at
    """
)


def has_evidence(evidence: dict) -> bool:
    """True if there's anything at all for the LLM to assess.

    Mirrors ``weekly_digest.has_evidence``: a freshly provisioned instance (empty
    domain tables — snapshots exist but are all zero-sample) must no-op rather
    than spend a daily paid call assessing nothing and publishing a junk row.
    """
    if any(m["sample_size"] for m in evidence["metrics_30d"] + evidence["metrics_all"]):
        return True
    if any(t["verdict"] != "insufficient_data" for t in evidence["trends_30d"] + evidence["trends_90d"]):
        return True
    if evidence["recommendations"]:
        return True
    return False


def generate_overall_insight(db: Session, *, force_genesis: bool = False) -> dict:
    """Generate (or regenerate) today's overall insight and upsert it.

    ``force_genesis`` ignores any prior assessment and synthesizes from scratch.
    Returns a dict of the persisted row. One paid LLM call unless mock_mode is on.
    No-ops (no LLM call, nothing written) when the instance has no data at all.
    """
    evidence = _gather_evidence(db)
    if not has_evidence(evidence):
        logger.info("overall_insight: no evidence yet (fresh instance) — skipping synthesis")
        return {"status": "skipped_no_evidence"}
    previous = None if force_genesis else _fetch_previous(db)

    parsed, model_used = _synthesize(evidence, previous)
    assessment = _coerce(parsed)

    row = db.execute(
        _UPSERT,
        {
            "health_verdict": assessment["health_verdict"],
            "narrative": assessment["narrative"],
            "key_shifts": json.dumps(assessment["key_shifts"]),
            "evidence": json.dumps(evidence, default=str),
            "model": model_used,
            "previous_insight_id": (previous["id"] if previous else None),
        },
    ).mappings().first()
    db.commit()

    logger.info(
        "overall_insight: %s assessment for %s (verdict=%s, model=%s)",
        "genesis" if previous is None else "daily",
        row["insight_date"],
        row["health_verdict"],
        model_used,
    )
    return {
        "insight_date": row["insight_date"].isoformat(),
        "health_verdict": row["health_verdict"],
        "narrative": row["narrative"],
        "key_shifts": row["key_shifts"],
        "previous_date": (previous["insight_date"].isoformat() if previous else None),
        "model": row["model"],
        "generated_at": row["generated_at"].isoformat(),
    }
