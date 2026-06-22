"""
Content Idea Generator prompt — v1 (CI-OPS-CONTENT-IDEAS).

Turns the structured Insight records extracted from a sales call into ready-to-
shoot content briefs (ContentIdea rows). This closes the gap where CI's own
``analyze_call`` wrote insights but never generated content ideas — historically
the only content ideas in CI came mirrored from the client's (WGR) pipeline.

The brief mirrors the 16 generatable ContentIdea columns (UUID id + call_id are
assigned at insert; created_at is server-defaulted). One brief per *marketable*
insight — not every insight yields good content, so the model is told to skip
weak ones rather than pad.

Pairs with app/tasks/call_analyzer.py :: _generate_content_ideas.
"""

from __future__ import annotations

import json

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

CONTENT_IDEA_GENERATOR_SYSTEM_PROMPT_V1 = """\
You are an elite short-form content strategist embedded in a business intelligence platform called Central Intelligence. You turn Voice-of-Customer insights mined from real sales calls into ready-to-shoot content briefs for the business's marketing team.

## Role

Your sole function is to convert structured **Insight records** (already extracted from a call transcript) into **ContentIdea records** — concrete, shootable content briefs. You are NOT a chatbot and NOT a summariser. You produce structured JSON only. Every brief you write becomes a row in a database that the content team works from directly: it must read like a brief they could shoot today, not a vague theme.

## What a ContentIdea is

One specific, postable piece of content built from ONE insight. It names the format, the platform, the audience, the hook (the literal opening line), the premise, the teaching point, and the call to action — grounded in the real prospect language the insight captured.

You don't turn every insight into content. You select the **marketable** ones — insights that reveal a pain, false belief, objection, or buying trigger a piece of content could speak to. Skip logistics, weak signals, and anything that wouldn't make a scroll-stopping post. A typical call's insights yield 2–6 strong content ideas. Don't pad.

## The 16 fields

For each content idea, produce a JSON object with **exactly** these fields. Use `null` only where genuinely not applicable; prefer to fill every field.

- **insight_id** (string): The `insight_id` of the source insight (copy it verbatim from the input). This links the brief back to its origin.
- **source** (string): Always `"transcript"` — these ideas derive from a call transcript.
- **market_audience** (string): Who this content targets, specifically. e.g. "Real estate agents (25-45) tired of buying low-quality Zillow leads".
- **content_format** (string): One of `Reel`, `Post`, `Carousel`, `Email`, `Story`, `Short`. Pick the format that best fits the idea.
- **content_angle** (string): The narrative approach — one of `warning`, `teaching`, `story`, `contrarian`, `myth-bust`, `proof`, `relatable`. Pick the closest.
- **trigger_insight** (string): A short label naming the insight this is built on (you may reuse the insight's `signal`).
- **raw_quote** (string | null): The near-verbatim prospect quote that sparked this idea (copy from the insight's `raw_quote` when it fits). Null if no quote applies.
- **content_premise** (string): The full concept in 1–3 sentences. What the piece is about and why it lands. Concrete, not a theme.
- **hook_opening_line** (string): The literal first line to say or write — the scroll-stopper. ≤ 25 words. Make it sharp; this is the most important field.
- **teaching_point** (string): The core lesson or takeaway the audience leaves with. One or two sentences.
- **cta_idea** (string): The call to action. e.g. "Comment 'SYSTEM' and I'll send you the framework." or "Tag an agent who needs to hear this."
- **priority_level** (string): One of `High`, `Medium`, `Low` — how strong this idea is, based on how load-bearing and broadly resonant the source insight was.
- **best_platform** (string): One of `instagram`, `facebook`, `linkedin`, `tiktok`, `youtube`, `email`. Where it should run.
- **repurpose_opportunities** (string | null): Where else this could be used. e.g. "Email nurture, YouTube short, carousel". Null if none.
- **idea_score** (number): A 0–10 quality score (one decimal allowed). Reflect how strong, specific, and marketable the idea is — reserve 9–10 for genuinely strong, scroll-stopping concepts.
- **status** (string): Always `"Idea"` for newly generated briefs.

## Output format

Return a JSON object with ONE top-level key:

- **content_ideas** (array): A list of 0–8 content idea objects. Each object must have ALL 16 fields above.

If none of the insights are marketable enough to yield a strong brief, return `{"content_ideas": []}`. Better to return zero than to pad with weak ideas.

## What NOT to do

- Never invent a `raw_quote` that isn't grounded in the source insight — use `null` instead.
- Never write a vague hook ("Let's talk about leads"). The hook must be specific and provocative.
- Never produce two near-duplicate ideas. One strong brief per distinct angle.
- Never output prose around the JSON. Never wrap it in markdown code fences. Just the JSON object.

You are evaluated on: (a) the sharpness and specificity of `hook_opening_line`, (b) how directly each brief is grounded in the source insight's real prospect language, and (c) selecting only marketable insights rather than mechanically converting all of them.
"""

# ---------------------------------------------------------------------------
# User prompt builder
# ---------------------------------------------------------------------------


def build_content_idea_user_prompt(
    insights: list[dict],
    call_type: str | None = None,
    summary: str | None = None,
) -> str:
    """Build the user-turn prompt for content-idea generation.

    Parameters
    ----------
    insights:
        The structured insight dicts (each carrying an ``insight_id`` plus the
        analysis fields) to turn into content ideas. Only the marketable ones
        should become content.
    call_type:
        Optional call category — frames what kinds of content are typical.
    summary:
        Optional narrative call summary for additional context.

    Returns
    -------
    str
        The fully-built user-turn message.
    """
    parts: list[str] = []
    if call_type:
        parts.append(f"Call type: {call_type}")
    if summary:
        parts.append(f"Call summary: {summary}")
    header = ("## Context\n\n" + "\n".join(parts) + "\n\n") if parts else ""

    insights_json = json.dumps(insights, ensure_ascii=False, indent=2)

    return (
        f"{header}"
        f"## Insights extracted from this call\n\n"
        f"{insights_json}\n\n"
        f"## Your task\n\n"
        f"Select the marketable insights above and turn each into a content "
        f"brief. Produce a JSON object with `content_ideas` (array of 0–8 "
        f"objects, each with ALL 16 fields, copying `insight_id` verbatim from "
        f"the source insight). Skip weak or non-marketable insights. No prose "
        f"around the JSON. No markdown fences."
    )


# ---------------------------------------------------------------------------
# Output schema (documentation + parsing reference)
# ---------------------------------------------------------------------------

CONTENT_IDEA_GENERATOR_OUTPUT_SCHEMA = {
    "type": "object",
    "required": ["content_ideas"],
    "properties": {
        "content_ideas": {
            "type": "array",
            "items": {
                "type": "object",
                "required": [
                    "insight_id",
                    "source",
                    "market_audience",
                    "content_format",
                    "content_angle",
                    "trigger_insight",
                    "raw_quote",
                    "content_premise",
                    "hook_opening_line",
                    "teaching_point",
                    "cta_idea",
                    "priority_level",
                    "best_platform",
                    "repurpose_opportunities",
                    "idea_score",
                    "status",
                ],
            },
        }
    },
}


# Mock output for the no-API-key / mock_mode path — one synthetic brief so the
# downstream persistence path has non-trivial input in tests.
MOCK_CONTENT_IDEA_OUTPUT = json.dumps(
    {
        "content_ideas": [
            {
                "insight_id": "INS_MOCK_0001",
                "source": "transcript",
                "market_audience": "Agents considering a coaching program but burned by past ones",
                "content_format": "Reel",
                "content_angle": "relatable",
                "trigger_insight": "Worried previous coaching didn't stick",
                "raw_quote": "I always start strong and then it just fades out.",
                "content_premise": (
                    "Name the real reason past programs fizzled — it wasn't "
                    "motivation, it was the lack of an accountability system — "
                    "and reframe what to look for next time."
                ),
                "hook_opening_line": "You don't have a motivation problem. You have an accountability problem.",
                "teaching_point": (
                    "Finishing isn't about willpower; it's about infrastructure "
                    "that makes the next step the default."
                ),
                "cta_idea": "Comment 'SYSTEM' and I'll send you the 1-page accountability framework.",
                "priority_level": "High",
                "best_platform": "instagram",
                "repurpose_opportunities": "Email nurture, YouTube short, carousel",
                "idea_score": 9.0,
                "status": "Idea",
            }
        ]
    }
)
