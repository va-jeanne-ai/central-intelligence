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


# ─── Follow-up chat (deliverable 8) ─────────────────────────────────────────
#
# Sibling of synthesize_view_analysis: same grounding contract (aggregates
# JSON is the ONLY source of numbers), but free-text conversational output
# instead of the structured narrative/highlights/hypotheses JSON, and it
# carries the running message history so follow-ups can reference earlier
# turns. call_claude_for_json doesn't fit here — it's single-turn and forces
# a JSON-object response — so this builds the messages list directly and
# calls the Anthropic SDK the same way call_claude_for_json does.

_CHAT_SYSTEM_PROMPT_TEMPLATE = (
    "You are the Central Intelligence analyst for a coaching/consulting business. "
    "The user is looking at a filtered view of \"{label}\" and asked an initial "
    "analysis; now they are asking follow-up questions in a chat. You are given "
    "the ONLY facts you may use: a JSON block of aggregates computed from that "
    "SAME filtered dataset.\n\n"
    "Active filters: {filters_echo}\n\n"
    "=== Aggregates of the filtered dataset (JSON) ===\n"
    "{aggregates_json}\n\n"
    "Hard rules:\n"
    "1. Every number you write must appear verbatim in the aggregates JSON above "
    "(counts, percentages, averages). Never derive, extrapolate, or invent numbers.\n"
    "2. Answer ONLY from this data and the prior conversation. If the data doesn't "
    "contain what's needed to answer, say so plainly instead of guessing.\n"
    "3. Speculative interpretations are allowed but must be clearly flagged as "
    "hypotheses (e.g. 'One possible explanation is …'), never stated as fact.\n"
    "4. Be concise — a few sentences, not a report. This is a chat, not a narrative."
)


def build_chat_system_prompt(*, label: str, filters_echo: str, aggregates: dict) -> str:
    """Pure prompt-assembly — factored out so it's unit-testable with no LLM/DB."""
    return _CHAT_SYSTEM_PROMPT_TEMPLATE.format(
        label=label,
        filters_echo=filters_echo,
        aggregates_json=json.dumps(aggregates, default=str, indent=2),
    )


def _call_claude_chat(system_prompt: str, messages: list[dict], *, max_tokens: int) -> str:
    """Sync Anthropic call for free-text chat replies (no JSON extraction).

    Maps the SDK's own exception types to a 502 (upstream failure) — never lets
    a raw APIConnectionError/APIStatusError escape as an unhandled 500, and
    never swallows them into a misleading empty reply.
    """
    import anthropic  # lazy import — large module, same convention as call_claude_for_json

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    try:
        response = client.messages.create(
            model=settings.anthropic_model_default,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=messages,
        )
    except anthropic.APIConnectionError as exc:
        raise HTTPException(
            status_code=502, detail="Could not reach Anthropic — try again.",
        ) from exc
    except anthropic.APIStatusError as exc:
        raise HTTPException(
            status_code=502, detail="Analysis request failed upstream — try again.",
        ) from exc
    return response.content[0].text


async def chat_view_analysis(
    *, label: str, filters_echo: str, aggregates: dict, messages: list[dict]
) -> dict:
    """Answer a follow-up question grounded in the CURRENT filtered aggregates.

    ``messages`` is the running [{role, content}, ...] history (already
    validated/capped by the route). Returns {reply, model}. 503 when no API
    key — same posture as synthesize_view_analysis (no mock_mode fallback;
    every chat turn is a real LLM call).
    """
    if not settings.anthropic_api_key:
        raise HTTPException(
            status_code=503,
            detail="Anthropic API key not configured — view analysis unavailable.",
        )
    if not messages:
        raise HTTPException(status_code=400, detail="messages must not be empty.")

    system_prompt = build_chat_system_prompt(
        label=label, filters_echo=filters_echo, aggregates=aggregates
    )
    reply = await asyncio.to_thread(
        _call_claude_chat, system_prompt, messages, max_tokens=1000
    )
    reply = reply.strip()
    if not reply:
        raise HTTPException(status_code=502, detail="Reply came back empty — try again.")

    from app.analytics.overall_insight import MODEL  # single source for the model id
    return {"reply": reply, "model": MODEL}
