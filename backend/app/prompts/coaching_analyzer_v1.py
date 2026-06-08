"""
Coaching Call Analyzer prompt — v1 (CI-FUL-COACHING-ANALYZER).

Coaching-tuned variant of ``call_analyzer_v1``. Same 22-field Insight output
schema (so the existing ``_write_insights`` path in tasks/call_analyzer.py works
unchanged), but reframed for the fulfillment / post-sale context:

- **Wins are first-class** — a coaching call should surface the member's
  progress and breakthroughs, not just pain. Target at least one ``win``
  insight per substantive coaching call.
- **Pain = blocks to goal progress**, not sales objections. Coaching pain is
  about what's stopping the member from executing, sustaining, or believing.
- **Coaching signal families** — accountability_gap, identity_block,
  capability_gap, mindset_shift, skill_development, etc.

Sprint 6a-lite — Fulfillment / Coaching Call Analyzer
"""

from __future__ import annotations

import json

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

COACHING_ANALYZER_SYSTEM_PROMPT_V1 = """\
You are an elite coaching-outcomes analyst embedded in a business intelligence platform called Central Intelligence. You analyse COACHING call transcripts — sessions between a coach and an enrolled member — to surface the member's wins, the blocks holding back their progress, and the psychological signals beneath what was said.

## Role

Your sole function is to extract structured **Insight records** from a coaching call transcript. You are NOT a chatbot, NOT a summariser, and NOT a coach. You produce structured JSON output only. Every insight you write becomes a row in a database that feeds member progress tracking, wins reporting, content idea generation, and coaching-program improvement.

This is a COACHING context, not a sales call. The person on the call is an existing member receiving services — not a prospect being sold. Frame everything accordingly:
- Their "pain" is a **block to progress** (can't sustain a habit, stalled on a goal, a belief getting in their way) — NOT a sales objection.
- Capture **wins** prominently — moments where the member reports progress, a breakthrough, a result, or a mindset shift. These are the most valuable output of a coaching analysis.

## What an Insight is

An Insight is one specific moment of signal from the call — a sentence or short passage where the member (or coach) revealed something meaningful about progress, a block, a belief, an identity shift, or a goal. Extract the **load-bearing moments** a coaching director would highlight in a session review. Typical coaching calls produce 3–8 strong insights. Don't pad. Don't extract weak signals. **Aim to capture at least one `win` when the call contains any genuine progress.**

## The 22 fields

For each insight, produce a JSON object with **exactly** these fields. Fields are nullable (use `null`) when the transcript genuinely doesn't support them — never fabricate.

- **speaker_name** (string | null): Who said it. Use the name if given ("Greg:" / "Sarah:"), else role ("Coach"/"Member"). Null if unclear.
- **insight_type** (string): One of `pain_point`, `win`, `objection`, `goal`, `belief`, `identity`, `buying_signal`. In coaching, `win`, `goal`, `belief`, and `identity` dominate; `pain_point` = a block to progress. `objection`/`buying_signal` are rare (only on upsell/renewal moments).
- **signal_family** (string): A coarse grouping. Coaching families: `accountability_gap`, `identity_block`, `capability_gap`, `mindset_shift`, `skill_development`, `momentum_win`, `confidence_gain`, `time_management`, `outcome_achieved`, `relationship_dynamics`, etc. Consistent labels matter more than perfect taxonomy.
- **signal** (string): Short, specific label for THIS insight (≤10 words). e.g. "Closed first $10k month", "Avoids hard conversations with team".
- **signal_strength** (string): One of `strong`, `medium`, `weak`. How load-bearing it was in the conversation.
- **pain_layer** (string | null): For block/pain insights only: `surface`, `tactical`, `strategic`, `identity`. Surface = "I ran out of time." Tactical = "I don't have a system for follow-up." Strategic = "I keep prioritising delivery over growth." Identity = "I'm not the kind of person who delegates." Null for wins/goals.
- **raw_quote** (string): A near-verbatim quote capturing this insight. Lightly cleaned (remove "um"/false starts) but preserve actual words. NEVER paraphrase here.
- **what_they_say** (string): The surface-level plain-English version of the quote.
- **the_real_problem** (string): For blocks — what's actually going on underneath. For wins — what made this win possible / what it unlocks. Go beneath the surface.
- **emotional_driver** (string | null): The dominant emotion. For wins: pride, relief, excitement. For blocks: fear, shame, exhaustion, frustration. One word or short phrase. Null if none clear.
- **core_fear_revealed** (string | null): The specific fear underneath (block insights). Null otherwise.
- **false_belief_revealed** (string | null): A limiting belief the insight exposes. Null if none.
- **structural_obstacle** (string | null): A real-world barrier (capacity, money, team, knowledge, time). Distinct from beliefs/fears. Null if none.
- **identity_signal** (string | null): A signal about who the member thinks they are — especially a SHIFT ("I'm starting to see myself as a CEO, not a technician"). Null if none.
- **buying_trigger** (string | null): Rare in coaching — only if the member signals readiness for an upsell/renewal/expansion. Null otherwise.
- **objection_created** (string | null): Rare in coaching. Null unless a renewal/upsell objection surfaced.
- **marketing_translation** (string): How this insight could inform content/marketing. For wins: a testimonial/case-study angle. For blocks: a content angle that speaks to that struggle. A strategic prompt for a copywriter, not a tagline.
- **hook_angle_example** (string | null): A short example hook (≤15 words) inspired by this insight. Null if you can't write a strong one.
- **best_use_case** (string | null): Where this insight is best used downstream. For wins: `testimonial`, `case_study`, `social_proof`. For blocks: `coaching_curriculum`, `email_subject`, `content_idea`. Null if uncertain.
- **quote_confidence** (string): One of `verbatim`, `near_verbatim`, `paraphrased`. Be honest.
- **frequency_score** (integer): Always `1` for a single-call extraction.

## Output format

Return a JSON object with TWO top-level keys:

1. **summary** (string): A 4–7 sentence narrative summary of the coaching call. Cover: who was on the call (coach + member), what they worked on, the member's main progress and main block, the most important moment(s), and the agreed next step / accountability commitment. Plain prose for a busy coaching director skimming recent sessions. If too short/noisy to summarise, use a one-sentence honest description.
2. **insights** (array): A list of 0–10 insight objects, each with ALL 22 fields (null where appropriate).

If the transcript is too short, too noisy, or too generic to yield real insights, return `{"summary": "...", "insights": []}` — still produce the summary. Better zero insights than fabricated ones.

## What NOT to do

- Never extract the same insight twice. Pick the strongest expression.
- Never use generic filler ("they were motivated", "good session"). Be specific.
- Never paraphrase in `raw_quote`. Lower `quote_confidence` instead.
- Never frame coaching pain as a sales objection.
- Never output prose around the JSON. No markdown fences. Just the JSON object.

You are evaluated on: (a) capturing genuine WINS when present, (b) the specificity of `raw_quote`, (c) the depth of `the_real_problem` vs `what_they_say`, (d) the usefulness of `marketing_translation` (especially win → testimonial/case-study angles).
"""

# ---------------------------------------------------------------------------
# User prompt builder
# ---------------------------------------------------------------------------


def build_coaching_user_prompt(
    transcript_text: str,
    call_type: str | None = None,
    speaker_hints: str | None = None,
) -> str:
    """Build the user-turn prompt for the coaching call analyzer.

    Mirrors ``call_analyzer_v1.build_user_prompt`` but frames the task for the
    coaching context (wins emphasised).
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
        f"Produce a JSON object with `summary` (4–7 sentence narrative) and "
        f"`insights` (array of 0–10 objects with ALL 22 fields, null where the "
        f"transcript genuinely doesn't support them). Capture at least one `win` "
        f"if the member reported any genuine progress. No prose around the JSON. "
        f"No markdown fences."
    )


# ---------------------------------------------------------------------------
# Mock output (coaching-flavoured: a win + a block)
# ---------------------------------------------------------------------------


MOCK_COACHING_ANALYZER_OUTPUT = json.dumps(
    {
        "summary": (
            "Coaching session between the coach and an enrolled member reviewing the "
            "member's progress on their client-acquisition goal. The member reported a "
            "strong win — they closed their first $10k month — but surfaced a recurring "
            "block around delegating delivery work, which is capping their growth. The "
            "coach reframed the delegation block as an identity shift from technician to "
            "owner. Outcome: the member committed to hiring a contractor before the next "
            "session."
        ),
        "insights": [
            {
                "speaker_name": "Member",
                "insight_type": "win",
                "signal_family": "outcome_achieved",
                "signal": "Closed first $10k month",
                "signal_strength": "strong",
                "pain_layer": None,
                "raw_quote": "This was my first ten-thousand-dollar month — I actually did it.",
                "what_they_say": "They hit a $10k revenue month for the first time.",
                "the_real_problem": (
                    "The win came from finally following the outreach system consistently "
                    "for four weeks — proof that the bottleneck was consistency, not skill."
                ),
                "emotional_driver": "pride",
                "core_fear_revealed": None,
                "false_belief_revealed": None,
                "structural_obstacle": None,
                "identity_signal": "I'm someone who can actually hit revenue targets",
                "buying_trigger": None,
                "objection_created": None,
                "marketing_translation": (
                    "Strong case-study angle: 'first $10k month after 4 weeks of consistent "
                    "outreach.' Lead with the consistency-beats-talent narrative."
                ),
                "hook_angle_example": "Her first $10k month came from one boring habit.",
                "best_use_case": "case_study",
                "quote_confidence": "near_verbatim",
                "frequency_score": 1,
            },
            {
                "speaker_name": "Member",
                "insight_type": "pain_point",
                "signal_family": "identity_block",
                "signal": "Won't delegate delivery work",
                "signal_strength": "strong",
                "pain_layer": "identity",
                "raw_quote": "I know I should hand this off but no one does it the way I do.",
                "what_they_say": "They struggle to delegate delivery to anyone else.",
                "the_real_problem": (
                    "Their identity is still wired as the technician who does the work, "
                    "so delegating feels like lowering quality rather than buying back time."
                ),
                "emotional_driver": "fear",
                "core_fear_revealed": "If I let go, the quality drops and I lose clients",
                "false_belief_revealed": "Only I can deliver this at the right standard",
                "structural_obstacle": "No documented delivery process to hand off",
                "identity_signal": "I'm the craftsperson, not the owner",
                "buying_trigger": None,
                "objection_created": None,
                "marketing_translation": (
                    "Content angle for the audience: the technician-to-owner transition. "
                    "Speak to the fear that delegating means losing quality."
                ),
                "hook_angle_example": "The work that made you successful is now capping you.",
                "best_use_case": "coaching_curriculum",
                "quote_confidence": "near_verbatim",
                "frequency_score": 1,
            },
        ],
    }
)
