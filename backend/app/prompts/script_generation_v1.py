"""
Script Generation prompt — v1 (CI-MKT-SOC / M01-3).

Defines the system prompt, user prompt builder, and output schema for the
Social Media Specialist's content generation operator.  This module is consumed
by the Marketing Director when it needs platform-native scripts and post copy
grounded in CI intelligence (pain points, market signals, content ideas).
The Marketing Director pre-loads all enrichment data before invoking this
prompt; the specialist does NOT query data itself.
"""

from __future__ import annotations

import json

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SCRIPT_GENERATION_SYSTEM_PROMPT_V1 = """\
You are **CI-MKT-SOC**, the Social Media Specialist of Central Intelligence — an AI-powered business intelligence platform for coaching and consulting businesses.

## Role

You sit inside the Marketing department, reporting to the Marketing Director.  Your function is to generate platform-native social media scripts and post copy for coaching and consulting brands.  You are NOT a chatbot.  You produce structured JSON output only — no prose, no markdown, no commentary outside the JSON envelope.

## Identity and Expertise

You combine three disciplines:

1. **Platform-native copywriting** — You know that a LinkedIn long-form post, an Instagram reel script, a YouTube Short, and an Instagram story sequence each have distinct structural conventions, tonal registers, and audience expectations.  You never write generic content and then paste it across platforms.  Each piece you produce is architected for its specific platform.
2. **CI intelligence grounding** — Every piece of content you write must be anchored in a specific insight from the Client Intelligence pool: a pain point that real prospects have expressed, a market signal trending in the niche, or a validated content angle scored by the intelligence layer.  You do not invent topics.  You translate existing intelligence into compelling content.
3. **Coaching and consulting brand psychology** — You understand that buyers of high-ticket coaching and consulting programmes are motivated by transformation, not information.  The most effective content for this audience exposes a real problem with specificity (so they feel seen), reframes it (so they see a new possibility), and presents the coach or consultant as the trusted guide — not as a lecturer or a salesperson.

## Data Inputs

The Marketing Director provides all data pre-loaded.  You receive:

- **platform** — The target social platform (e.g. "LinkedIn", "Instagram", "YouTube Shorts").
- **content_type** — The format to generate (e.g. "carousel post", "reel script", "story sequence", "long-form post").
- **quantity** — Number of distinct scripts or posts to produce.
- **brand_voice** — A description of the brand's tone and personality.  If empty, default to: authoritative but warm, direct without being aggressive, and grounded in lived experience rather than hype.
- **icp_primary** — The primary Ideal Client Profile segment for this business: who they are, what they feel, what they want, and what triggers them to buy.
- **pain_points** — High-frequency pain points from the shared intelligence pool.  These are real words and themes from real prospect and client conversations.
- **market_signals** — Trending signals and themes extracted from call transcripts, sorted by recency and mention volume.
- **content_ideas** — Validated content angles with hook lines and format recommendations, pre-scored by the intelligence layer.
- **topic_focus** — An optional specific topic or theme to constrain the output.  If provided, every script must address this topic.

## Content Quality Rules

Every script you produce MUST comply with all of the following:

### 1. CI Anchor (mandatory)

Every script must be grounded in a specific, named piece of CI data.  In the ``ci_anchor`` field, state exactly which pain point or market signal the content addresses and why it was chosen.  This is not optional.  Content that cannot be traced back to a real CI insight will be rejected.

### 2. Platform-Native Formatting

- **LinkedIn long-form post:** Opens with a single punchy line (the hook) that stands alone before "see more" is clicked.  Body uses short paragraphs (1-3 sentences), white space, and a story arc: problem → turning point → insight → CTA.  No hashtag stuffing — maximum 3-5 relevant tags.
- **LinkedIn carousel post:** Slide-by-slide breakdown.  First slide = hook.  Each subsequent slide = one idea, one teaching point.  Final slide = CTA.  Write each slide as a line in the body, prefixed with the slide number.
- **Instagram reel script:** Verbal delivery script.  Opens with a pattern-interrupt hook in the first 2 seconds.  Body delivers one insight in 30-60 seconds.  Closes with a specific CTA.  Write as speaker notes (what they say, not what appears on screen).
- **Instagram story sequence:** A multi-card narrative sequence.  Each card is a distinct beat: card 1 = hook/question, card 2-4 = body/insight, final card = CTA or poll.  Write each card as a numbered item in the body.
- **YouTube Shorts script:** 45-60 second verbal script.  Pattern-interrupt opening, rapid-fire value delivery, one clear CTA.  Optimised for retention — no slow build.
- **Facebook post:** Conversational tone.  Longer paragraphs acceptable.  Opens with a relatable statement or question.  Ends with a direct engagement prompt (question or CTA).

### 3. Hook Quality

The hook is the most important element.  It must:
- Create a pattern interrupt (challenge an assumption, use a counterintuitive statement, or open a loop)
- Be specific enough to make the target ICP feel personally addressed
- Be written to stand alone — someone who only reads the hook should want to stop scrolling

Weak hook (reject): "Here are 5 tips for coaches who want to grow their business."
Strong hook (use): "If you're fully booked and still worried about next month's income — you don't have a sales problem. You have a pricing architecture problem."

### 4. CTA Specificity

Every CTA must be concrete.  Avoid generic phrases like "drop a comment below" or "save this post."  Ground the CTA in the pain point or transformation being addressed.

Weak CTA (reject): "Let me know your thoughts in the comments!"
Strong CTA (use): "If this describes where you are right now — reply with 'SYSTEM' and I'll send you the framework we use to build a predictable lead pipeline without paid ads."

### 5. Length Accuracy

The ``estimated_length`` field must be a realistic estimate.  For scripts: calculate based on average speaking pace of 130 words per minute.  For written posts: estimate word count.

## Output Contract

You MUST return a single JSON object.  No prose before or after.  No markdown fences.  No explanations.  Only the JSON object.

The object must conform exactly to the output schema.  The ``scripts`` array must contain exactly the number of items specified in ``quantity``.  Script IDs are 1-indexed integers.

## Example Output

The following illustrates the expected structure and quality.  All values are fabricated for illustration only:

```json
{
  "platform": "LinkedIn",
  "content_type": "long-form post",
  "scripts": [
    {
      "script_id": 1,
      "hook": "Being fully booked is not a success metric. It's a warning sign.",
      "body": "Three years ago I was turning away clients.\n\nI thought that meant the business was working.\n\nIt wasn't. It meant I had built a ceiling and called it a roof.\n\nFully booked = zero capacity to grow without breaking.\nFully booked = one client cancellation away from a cashflow crisis.\nFully booked = trading every hour for a number that doesn't compound.\n\nThe coaches I see break through $20k months aren't the busiest ones. They're the ones who redesigned the offer before they hit the ceiling — not after.\n\nIf your diary is full and you still feel financially fragile, the answer isn't more clients. It's a different model.",
      "cta": "If you're fully booked and want to know what a leveraged offer structure looks like for your specific niche — comment 'MODEL' below and I'll send you the framework.",
      "ci_anchor": "Pain point: 'I'm fully booked but not hitting my revenue goals' (freq=14). This is the single highest-frequency pain in the intelligence pool and maps directly to the primary ICP's buying trigger around hitting a revenue ceiling.",
      "estimated_length": "180 words",
      "hashtag_suggestions": ["#coachingbusiness", "#scaleyourcoaching", "#highticket", "#businessgrowth", "#coachinglife"]
    }
  ],
  "content_strategy_note": "These scripts target the primary ICP's most acute pain — the contradiction of being fully booked while feeling financially fragile — which surfaces in 14 calls and represents the clearest buying trigger in the current intelligence pool."
}
```\
"""

# ---------------------------------------------------------------------------
# User prompt builder
# ---------------------------------------------------------------------------


def build_script_generation_user_prompt(data: dict) -> str:  # noqa: PLR0912
    """Format pre-loaded Marketing Director enrichment data into the script generation prompt.

    Parameters
    ----------
    data:
        A dict with keys: ``platform``, ``content_type``, ``quantity``,
        ``brand_voice``, ``icp_primary``, ``pain_points``, ``market_signals``,
        ``content_ideas``, ``topic_focus``.

    Returns
    -------
    str
        The fully-rendered user prompt ready to send to the model.
    """

    platform = data.get("platform") or "LinkedIn"
    content_type = data.get("content_type") or "long-form post"
    quantity = data.get("quantity") or 3
    brand_voice = data.get("brand_voice") or ""
    topic_focus = data.get("topic_focus") or ""

    lines: list[str] = [
        "## Generation Request",
        "",
        f"- Platform: {platform}",
        f"- Content type: {content_type}",
        f"- Quantity: {quantity} script(s)",
    ]

    if topic_focus:
        lines.append(f"- Topic focus: {topic_focus}")
    lines.append("")

    # -- Brand voice ---------------------------------------------------------
    if brand_voice:
        lines += [
            "## Brand Voice",
            "",
            brand_voice,
            "",
        ]
    else:
        lines += [
            "## Brand Voice",
            "",
            "(Not specified — use default: authoritative but warm, direct without being aggressive, grounded in lived experience rather than hype.)",
            "",
        ]

    # -- Primary ICP ---------------------------------------------------------
    icp_primary: dict = data.get("icp_primary") or {}
    if icp_primary:
        lines += [
            "## Primary ICP Segment",
            "",
        ]
        segment = icp_primary.get("segment") or "Primary"
        description = icp_primary.get("description") or ""
        demographics = icp_primary.get("demographics") or ""
        pain_summary = icp_primary.get("pain_summary") or ""
        buying_triggers = icp_primary.get("buying_triggers") or ""

        lines.append(f"Segment: {segment}")
        if description:
            lines.append(f"Description: {description}")
        if demographics:
            lines.append(f"Demographics: {demographics}")
        if pain_summary:
            lines.append(f"Pain summary: {pain_summary}")
        if buying_triggers:
            lines.append(f"Buying triggers: {buying_triggers}")
        lines.append("")
    else:
        lines += ["## Primary ICP Segment", "", "(No ICP data available.)", ""]

    # -- Pain points ---------------------------------------------------------
    pain_points: list[dict] = data.get("pain_points", [])
    if pain_points:
        lines += [
            "## Pain Points (sorted by frequency, highest first)",
            "",
        ]
        sorted_pain = sorted(
            pain_points, key=lambda p: p.get("frequency_count", 0), reverse=True
        )
        for i, pp in enumerate(sorted_pain, start=1):
            text = pp.get("text") or ""
            category = pp.get("category") or "Uncategorised"
            freq = pp.get("frequency_count", 1)
            lines.append(f"{i}. [{category} | freq={freq}] {text}")
        lines.append("")
    else:
        lines += ["## Pain Points", "", "(No pain point data available.)", ""]

    # -- Market signals ------------------------------------------------------
    market_signals: list[dict] = data.get("market_signals", [])
    if market_signals:
        lines += [
            "## Market Signals (sorted by recent mention volume)",
            "",
        ]
        sorted_signals = sorted(
            market_signals, key=lambda s: s.get("last_7_days", 0), reverse=True
        )
        for i, sig in enumerate(sorted_signals, start=1):
            family = sig.get("signal_family") or ""
            signal = sig.get("signal") or ""
            last_7 = sig.get("last_7_days", 0)
            angle = sig.get("best_marketing_angle") or ""
            lines.append(f"{i}. [{family} | 7-day mentions={last_7}] {signal}")
            if angle:
                lines.append(f"   Best angle: {angle}")
        lines.append("")
    else:
        lines += ["## Market Signals", "", "(No market signals available.)", ""]

    # -- Content ideas -------------------------------------------------------
    content_ideas: list[dict] = data.get("content_ideas", [])
    if content_ideas:
        lines += [
            "## Content Ideas (from CI intelligence pool, sorted by score)",
            "",
        ]
        sorted_ideas = sorted(
            content_ideas, key=lambda c: c.get("idea_score", 0), reverse=True
        )
        for i, idea in enumerate(sorted_ideas, start=1):
            angle = idea.get("content_angle") or ""
            fmt = idea.get("content_format") or ""
            score = idea.get("idea_score", 0)
            hook = idea.get("hook_opening_line") or ""
            lines.append(f"{i}. [{fmt} | score={score}] {angle}")
            if hook:
                lines.append(f"   Hook: {hook}")
        lines.append("")
    else:
        lines += ["## Content Ideas", "", "(No content ideas available.)", ""]

    # -- Output instructions -------------------------------------------------
    lines += [
        "---",
        "",
        "## Your Task",
        "",
        f"Generate exactly {quantity} {content_type} script(s) for {platform}.",
        "",
        "Generation requirements:",
        "- Every script must have a CI anchor: state the specific pain point or market signal it addresses, with frequency count where available.",
        "- Every hook must create a pattern interrupt specific enough that the target ICP feels personally addressed.",
        "- Every CTA must be concrete and grounded in the pain point or transformation — no generic engagement prompts.",
        f"- Format each script for {platform} following the platform-native formatting rules in your instructions.",
        "- Vary the angle across the scripts — do not produce variations on the same theme.",
        "- If topic_focus is specified, all scripts must address that topic while drawing on different CI data points.",
        "- Script IDs must be 1-indexed integers matching the order of the scripts array.",
        "",
        "Output format — return ONLY this JSON object, nothing else:",
        "",
        json.dumps(
            {
                "platform": platform,
                "content_type": content_type,
                "scripts": [
                    {
                        "script_id": 1,
                        "hook": "The opening line / hook — should stand alone and create a pattern interrupt.",
                        "body": "The full body content formatted for the target platform.",
                        "cta": "Specific, grounded call to action — not generic.",
                        "ci_anchor": "Which CI insight (pain point or market signal) this is grounded in, and why it was chosen.",
                        "estimated_length": "e.g. '45 seconds' or '220 words'",
                        "hashtag_suggestions": ["#example1", "#example2"],
                    }
                ],
                "content_strategy_note": "1-2 sentences on why these scripts align with the current CI intelligence data.",
            },
            indent=2,
        ),
        "",
        f"Replace all placeholder strings with real content. Expand the scripts array to {quantity} items.",
        "Return ONLY the JSON object — no other text.",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Output schema (documentation / validation reference)
# ---------------------------------------------------------------------------

SCRIPT_GENERATION_OUTPUT_SCHEMA: dict = {
    "type": "object",
    "description": (
        "Structured batch of platform-native social media scripts produced by the "
        "Social Media Specialist (CI-MKT-SOC).  Every script is grounded in CI "
        "intelligence (pain points, market signals, or content ideas) from the "
        "shared intelligence pool.  Consumed by the Marketing Director for "
        "scheduling and publishing workflows."
    ),
    "required": [
        "platform",
        "content_type",
        "scripts",
        "content_strategy_note",
    ],
    "properties": {
        "platform": {
            "type": "string",
            "description": "The social platform these scripts are written for.",
            "example": "LinkedIn",
        },
        "content_type": {
            "type": "string",
            "description": (
                "The content format requested (e.g. 'carousel post', 'reel script', "
                "'story sequence', 'long-form post', 'YouTube Shorts script')."
            ),
        },
        "scripts": {
            "type": "array",
            "description": (
                "Array of generated scripts.  Length equals the ``quantity`` input.  "
                "Each script is fully production-ready and platform-native."
            ),
            "minItems": 1,
            "items": {
                "type": "object",
                "required": [
                    "script_id",
                    "hook",
                    "body",
                    "cta",
                    "ci_anchor",
                    "estimated_length",
                    "hashtag_suggestions",
                ],
                "properties": {
                    "script_id": {
                        "type": "integer",
                        "description": (
                            "1-indexed integer identifier for this script within the batch."
                        ),
                        "minimum": 1,
                    },
                    "hook": {
                        "type": "string",
                        "description": (
                            "The opening line or hook.  Must create a pattern interrupt "
                            "and be specific enough that the primary ICP feels personally "
                            "addressed.  Should stand alone before 'see more' or before the "
                            "audience scrolls past."
                        ),
                    },
                    "body": {
                        "type": "string",
                        "description": (
                            "The full body content formatted for the target platform and "
                            "content type.  For reel/Shorts scripts: verbal delivery copy "
                            "as speaker notes.  For carousel posts: slide-by-slide "
                            "breakdown with numbered slides.  For story sequences: "
                            "numbered cards.  For written posts: formatted post copy."
                        ),
                    },
                    "cta": {
                        "type": "string",
                        "description": (
                            "Call to action.  Must be specific and grounded in the pain "
                            "point or transformation addressed by the script.  Avoid "
                            "generic phrases like 'drop a comment below' or 'save this post'."
                        ),
                    },
                    "ci_anchor": {
                        "type": "string",
                        "description": (
                            "The specific CI insight this script is grounded in — the pain "
                            "point or market signal it addresses, with frequency count or "
                            "score where available, and a brief explanation of why it was "
                            "chosen.  Example: 'Pain point: pricing confidence (freq=11). "
                            "Chosen as the highest-frequency unaddressed pain in the "
                            "intelligence pool for this ICP.'."
                        ),
                    },
                    "estimated_length": {
                        "type": "string",
                        "description": (
                            "Realistic length estimate.  For video/audio scripts: duration "
                            "in seconds (calculated at ~130 wpm speaking pace).  For written "
                            "posts: approximate word count.  Examples: '45 seconds', "
                            "'60 seconds', '180 words', '320 words'."
                        ),
                    },
                    "hashtag_suggestions": {
                        "type": "array",
                        "description": (
                            "Up to 5 relevant hashtags for this specific script.  Should "
                            "mix niche-specific tags (smaller, higher-engagement) with "
                            "broader category tags.  Do not include the '#' character — "
                            "include it in the string value."
                        ),
                        "maxItems": 5,
                        "items": {
                            "type": "string",
                            "description": "Hashtag including the '#' prefix, e.g. '#coachingbusiness'.",
                        },
                    },
                },
            },
        },
        "content_strategy_note": {
            "type": "string",
            "description": (
                "1-2 sentences explaining why these scripts align with the current CI "
                "intelligence data and what strategic outcome they are designed to drive "
                "(e.g. building authority on a high-frequency pain point, bridging a "
                "content gap identified in the social analysis, or targeting a trending "
                "market signal before it peaks)."
            ),
        },
    },
}

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

__all__ = [
    "SCRIPT_GENERATION_SYSTEM_PROMPT_V1",
    "SCRIPT_GENERATION_OUTPUT_SCHEMA",
    "build_script_generation_user_prompt",
]
