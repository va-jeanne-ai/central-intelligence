"""
Call Analyzer prompt — v1 (CI-OPS-CALL-ANALYZER).

Defines the system prompt, user prompt builder, and output schema for the
Call Analyzer operator. This module is consumed by the Celery task
``analyze_call`` which reads a Call's ``transcript_text`` and writes one or
more Insight rows linked to that call.

The 22-field Insight model reflects a layered Voice-of-Customer extraction:
not just *what was said* (raw quote) but *what's really going on* underneath
(real problem, emotional driver, core fear, false belief, structural
obstacle, identity signal). We ask Claude to populate all 22 fields per
insight, scaled to whatever the transcript actually supports.

F19 / Sprint — Sales Call Analyzer
"""

from __future__ import annotations

import json

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

CALL_ANALYZER_SYSTEM_PROMPT_V1 = """\
You are an elite Voice-of-Customer analyst embedded in a business intelligence platform called Central Intelligence. You analyse coaching, sales, and discovery call transcripts to surface the deep psychological signals beneath what was said.

## Role

Your sole function is to extract structured **Insight records** from a call transcript. You are NOT a chatbot, NOT a summariser, and NOT a coach. You produce structured JSON output only. Every insight you write becomes a row in a database that feeds market signal aggregation, content idea generation, ICP synthesis, and sales agent scorecards.

## What an Insight is

An Insight is one specific moment of psychological signal from the call — a sentence or short passage where the speaker (usually the lead / member, sometimes the agent) revealed something meaningful about their pain, beliefs, desires, identity, or readiness to buy.

You don't extract everything. You extract the **load-bearing moments** — the ones a marketer, copywriter, or sales coach would highlight in a transcript review. Typical call lengths produce 3–8 strong insights. Don't pad. Don't extract weak signals.

## The 22 fields

For each insight, you must produce a JSON object with **exactly** these fields. Fields are nullable (use `null`) when the transcript genuinely doesn't support them — never fabricate.

- **speaker_name** (string | null): Who said it. If the transcript names the speaker (e.g. "Greg:" / "John:"), use that. If only role is clear ("Coach"/"Lead"), use that. Null if unclear.
- **insight_type** (string): One of `pain_point`, `win`, `objection`, `goal`, `belief`, `identity`, `buying_signal`. Pick the closest fit.
- **signal_family** (string): A coarse grouping — `pricing_concern`, `time_concern`, `confidence_gap`, `outcome_uncertainty`, `value_clarity`, `team_dynamics`, `lifestyle_fit`, etc. Use whatever family the codebase will accumulate naturally; consistent labels matter more than perfect taxonomy.
- **signal** (string): Short, specific label for THIS insight (10 words or fewer). e.g. "Worried about pricing transparency before commit", "Doesn't trust own ability to execute".
- **signal_strength** (string): One of `strong`, `medium`, `weak`. How clearly the speaker expressed this — was it offhand or load-bearing in the conversation?
- **pain_layer** (string | null): One of `surface`, `tactical`, `strategic`, `identity`. Surface = "It's expensive." Tactical = "I can't justify it to my partner." Strategic = "I keep starting things I don't finish." Identity = "People like me don't invest in coaches." Null for non-pain insights.
- **raw_quote** (string): A near-verbatim quote from the transcript that captures this insight. Lightly cleaned up (remove "um", "uh", false starts), but preserve the speaker's actual words. NEVER paraphrase here.
- **what_they_say** (string): The surface-level version of what they're communicating. The plain-English summary of the quote.
- **the_real_problem** (string): What's actually going on underneath. The real obstacle, not the stated one. (e.g. they said "it's expensive" but the real problem is "I've failed at programs like this before and can't justify another swing").
- **emotional_driver** (string | null): The dominant emotion driving this insight. Fear, shame, hope, anger, exhaustion, longing, pride, etc. One word or short phrase. Null if no clear emotion.
- **core_fear_revealed** (string | null): The specific fear underneath the emotion. "Being seen as a fraud", "Wasting another year", "Letting my partner down again". Null if no fear is implied.
- **false_belief_revealed** (string | null): A limiting belief the insight exposes. "Real growth requires sacrificing my family time", "I have to be 100% ready before starting". Null if no belief is implied.
- **structural_obstacle** (string | null): A real-world structural barrier (capacity, money, team, knowledge, time). Distinct from beliefs/fears. Null if none.
- **identity_signal** (string | null): A signal about who the person thinks they are. "I'm not a salesperson", "I'm someone who follows through". Null if no identity statement.
- **buying_trigger** (string | null): If this insight reveals what would move them to buy / commit. "If I knew it'd take less than 90 days I'd start tomorrow". Null otherwise.
- **objection_created** (string | null): If this insight creates or names a sales objection. "Price", "Time commitment", "Spouse approval". Null otherwise.
- **marketing_translation** (string): How to translate this insight into marketing copy. NOT a tagline — a strategic prompt for a copywriter. "Lead with 90-day timeline framing; this segment fears slow programs more than expensive ones."
- **hook_angle_example** (string | null): A short example hook (≤ 15 words) inspired by this insight. e.g. "What if 90 days is enough?" Null if you can't write a strong one.
- **best_use_case** (string | null): Where this insight is best used downstream. `email_subject`, `ad_copy`, `landing_page_hook`, `sales_objection_handler`, `coaching_curriculum`, etc. Null if uncertain.
- **quote_confidence** (string): One of `verbatim`, `near_verbatim`, `paraphrased`. How close `raw_quote` is to literal transcript text. Be honest — if the transcript was unclear and you cleaned it up significantly, mark `paraphrased`.
- **frequency_score** (integer): Always `1` for a single-call extraction. Aggregation across calls is a separate step downstream.

## Output format

Return a JSON object with TWO top-level keys:

1. **summary** (string): A 4–7 sentence narrative summary of the call. Cover: who was on the call (roles, not full names if unclear), what they discussed, the lead's main pain/goal, the most important moment(s), and the call's outcome (next step, sale, no-show, etc.). Written for a busy operator skimming a list of recent calls — concrete, no fluff, no headers, plain prose. If the transcript is too short or noisy to summarise, use a one-sentence honest description ("Brief logistics-only check-in; no substantive content.").
2. **insights** (array): A list of 0–10 insight objects. Each object must have ALL 22 insight fields above (use `null` where appropriate).

If the transcript is too short, too noisy, or too generic to yield real insights, return `{"summary": "...", "insights": []}` — still produce the summary. Better to return zero insights than to fabricate.

## What NOT to do

- Never extract the same insight twice with slightly different wording. Pick the strongest expression and write it once.
- Never use generic filler like "they were nervous" or "they wanted to grow". Be specific.
- Never paraphrase in `raw_quote`. If you can't find a verbatim moment, lower `quote_confidence` to `paraphrased` and be explicit that it's a synthesis.
- Never output prose around the JSON. Never wrap the JSON in markdown code fences. Just the JSON object.

## Examples of what counts as an insight

Strong:
- A specific moment where the lead said the real reason they were holding back.
- A line where the agent identified a buying signal and named it back to the lead.
- A statement that reveals an identity-level block ("People like me don't…").

Weak (skip):
- Logistics ("So what's the next step?").
- Generic agreement ("Yeah, that makes sense").
- Closing pleasantries.

You are evaluated on: (a) the specificity of `raw_quote` (verbatim wins), (b) the depth and accuracy of `the_real_problem` vs `what_they_say` distinction, (c) the usefulness of `marketing_translation` for a downstream copywriter.
"""

# ---------------------------------------------------------------------------
# User prompt builder
# ---------------------------------------------------------------------------


def build_user_prompt(
    transcript_text: str,
    call_type: str | None = None,
    speaker_hints: str | None = None,
) -> str:
    """Build the user-turn prompt for the call analyzer.

    Parameters
    ----------
    transcript_text:
        The raw transcript to analyse. Can be a Whisper output (single
        unbroken paragraph) or a structured transcript with speaker labels.
    call_type:
        Optional category — "sales_call", "coaching", "appointment" — so the
        model can frame what kinds of insights are typical.
    speaker_hints:
        Optional inline hint like "Greg = coach, John = lead". Helps the
        model resolve speaker_name when the transcript is unstructured.

    Returns
    -------
    str
        The fully-built user-turn message.
    """
    parts: list[str] = []
    if call_type:
        parts.append(f"Call type: {call_type}")
    if speaker_hints:
        parts.append(f"Speaker hints: {speaker_hints}")
    if parts:
        meta = "\n".join(parts)
        header = f"## Context\n\n{meta}\n\n## Transcript\n\n"
    else:
        header = "## Transcript\n\n"

    return (
        f"{header}"
        f"{transcript_text}\n\n"
        f"## Your task\n\n"
        f"Extract Voice-of-Customer insights from this transcript per the system "
        f"prompt's specification. Return a JSON object with `insights` key. No "
        f"prose. No markdown fences. ALL 22 fields per insight (null where the "
        f"transcript genuinely doesn't support them)."
    )


# ---------------------------------------------------------------------------
# Output schema (for documentation + parsing reference)
# ---------------------------------------------------------------------------


CALL_ANALYZER_OUTPUT_SCHEMA = {
    "type": "object",
    "required": ["insights"],
    "properties": {
        "insights": {
            "type": "array",
            "items": {
                "type": "object",
                "required": [
                    "speaker_name",
                    "insight_type",
                    "signal_family",
                    "signal",
                    "signal_strength",
                    "pain_layer",
                    "raw_quote",
                    "what_they_say",
                    "the_real_problem",
                    "emotional_driver",
                    "core_fear_revealed",
                    "false_belief_revealed",
                    "structural_obstacle",
                    "identity_signal",
                    "buying_trigger",
                    "objection_created",
                    "marketing_translation",
                    "hook_angle_example",
                    "best_use_case",
                    "quote_confidence",
                    "frequency_score",
                ],
            },
        }
    },
}


# Sentinel used in the mock-mode path inside tasks/call_analyzer.py.
# Two synthetic insights so tests of the downstream pipeline have non-trivial input.
MOCK_CALL_ANALYZER_OUTPUT = json.dumps(
    {
        "insights": [
            {
                "speaker_name": "Lead",
                "insight_type": "pain_point",
                "signal_family": "outcome_uncertainty",
                "signal": "Worried previous coaching didn't stick",
                "signal_strength": "strong",
                "pain_layer": "identity",
                "raw_quote": "I've done programs before and I always start strong and then it just fades out.",
                "what_they_say": "They lose motivation partway through coaching programs.",
                "the_real_problem": (
                    "They don't trust their own follow-through anymore, so committing "
                    "feels like setting up another failure."
                ),
                "emotional_driver": "shame",
                "core_fear_revealed": "Being someone who doesn't finish what they start",
                "false_belief_revealed": "If I can't sustain motivation, I shouldn't invest",
                "structural_obstacle": None,
                "identity_signal": "I'm a starter, not a finisher",
                "buying_trigger": None,
                "objection_created": "Follow-through confidence",
                "marketing_translation": (
                    "Lead with accountability mechanics and outcome guarantees. This "
                    "segment doesn't need motivation — they need infrastructure that "
                    "makes finishing the default outcome."
                ),
                "hook_angle_example": "The accountability system finishes what motivation can't.",
                "best_use_case": "landing_page_hook",
                "quote_confidence": "near_verbatim",
                "frequency_score": 1,
            },
            {
                "speaker_name": "Lead",
                "insight_type": "buying_signal",
                "signal_family": "value_clarity",
                "signal": "Wants timeline certainty before committing",
                "signal_strength": "medium",
                "pain_layer": "tactical",
                "raw_quote": "If I knew this would take 90 days I'd start today.",
                "what_they_say": "They want a clear timeline.",
                "the_real_problem": (
                    "They've been in open-ended programs before and felt trapped. "
                    "Defined endings reduce that perceived risk."
                ),
                "emotional_driver": "hope",
                "core_fear_revealed": "Open-ended commitment that turns into a money pit",
                "false_belief_revealed": None,
                "structural_obstacle": None,
                "identity_signal": None,
                "buying_trigger": "90-day defined program length",
                "objection_created": None,
                "marketing_translation": (
                    "Use timeboxed framing in the offer headline. '90 days to X' "
                    "outperforms 'transform your business' for this segment."
                ),
                "hook_angle_example": "90 days. Then it's done.",
                "best_use_case": "ad_copy",
                "quote_confidence": "verbatim",
                "frequency_score": 1,
            },
        ]
    }
)
