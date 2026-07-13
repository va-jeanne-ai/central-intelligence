"""Shared narrative step for view analysis — aggregates in, grounded JSON out."""

from __future__ import annotations

import asyncio
import json
import logging

from fastapi import HTTPException

from app.analytics.overall_insight import call_claude_for_json
from app.config import settings

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are the Central Intelligence analyst for a coaching/consulting business. "
    "The user is looking at a filtered list view; you are given the ONLY facts you "
    "may use: a JSON block of aggregates computed from that filtered dataset.\n\n"
    "Hard rules:\n"
    "1. Every number you write must appear verbatim in the aggregates JSON (counts, "
    "percentages, averages). Never derive, extrapolate, or invent numbers.\n"
    "2. Facts go in the narrative and highlights. Interpretations, guesses, and "
    "possible explanations go ONLY in hypotheses, phrased as hypotheses "
    "(e.g. 'One possible explanation is …').\n"
    "3. If row_count is small, say the data is too thin for strong conclusions "
    "rather than stretching.\n\n"
    "Respond with ONLY a JSON object, no prose around it, of exactly this shape:\n"
    "{\n"
    '  "narrative": "2-4 short paragraphs separated by a blank line (\\n\\n)",\n'
    '  "highlights": ["3-5 one-line factual takeaways"],\n'
    '  "hypotheses": ["0-3 clearly speculative interpretations"]\n'
    "}"
)


def _build_user_prompt(label: str, describe: str, filters_echo: str, aggregates: dict) -> str:
    return (
        f"Surface: {label}\n"
        f"What the fields mean: {describe}\n"
        f"Active filters: {filters_echo}\n\n"
        "=== Aggregates of the filtered dataset (JSON) ===\n"
        + json.dumps(aggregates, default=str, indent=2)
    )


async def synthesize_view_analysis(
    *, label: str, describe: str, filters_echo: str, aggregates: dict
) -> dict:
    """Return {narrative, highlights, hypotheses, model}. 503 when no API key.

    Deliberately NO mock_mode handling — every analyze call is a real LLM call
    (per the 2026-07-13 spec decision).
    """
    if not settings.anthropic_api_key:
        raise HTTPException(
            status_code=503,
            detail="Anthropic API key not configured — view analysis unavailable.",
        )
    user_prompt = _build_user_prompt(label, describe, filters_echo, aggregates)
    # call_claude_for_json is sync (used from Celery elsewhere) — off the event loop.
    parsed = await asyncio.to_thread(
        call_claude_for_json, _SYSTEM_PROMPT, user_prompt, max_tokens=1500
    )
    narrative = str(parsed.get("narrative", "")).strip()
    if not narrative:
        raise HTTPException(status_code=502, detail="Analysis came back empty — try again.")
    highlights = [str(x) for x in parsed.get("highlights", []) if str(x).strip()][:5]
    hypotheses = [str(x) for x in parsed.get("hypotheses", []) if str(x).strip()][:3]
    from app.analytics.overall_insight import MODEL  # single source for the model id
    return {
        "narrative": narrative,
        "highlights": highlights,
        "hypotheses": hypotheses,
        "model": MODEL,
    }
