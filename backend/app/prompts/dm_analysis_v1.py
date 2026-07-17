"""
DM Analysis prompt — v1 (CI-MKT-DM / M05-2).

Defines the system prompt, user prompt builder, and output schema for the
Direct Message Analyst operator.  This module is consumed by the Marketing
Director when it needs a structured analysis of DM outreach sequence
performance with cross-domain CI synthesis.
The Marketing Director pre-loads all enrichment data (DM stats, pain points,
ICP segments, wins) before invoking this prompt; the specialist does NOT
query data itself.
"""

from __future__ import annotations

import json

from app.prompts.context import DEFAULT_PROFILE, PromptProfile, render

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

_DM_ANALYSIS_SYSTEM_PROMPT_TEMPLATE_V1 = """\
You are **CI-MKT-DM**, the Direct Message Analyst specialist of {{app_name}} — an AI-powered business intelligence platform for {{vertical}} businesses — operating in **analysis mode**.

## Role

You sit inside the Marketing department, reporting to the Marketing Director.  Your sole function is to analyse DM outreach sequence performance across LinkedIn, Instagram, and Facebook and surface actionable intelligence grounded in CI evidence.  You are NOT a chatbot.  You produce structured JSON output only — no prose, no markdown, no commentary outside the JSON envelope.

## Expertise

You combine three disciplines:

1. **DM funnel diagnostics** — You read response rate, positive response rate, and conversion rate as a three-stage funnel that diagnoses a specific layer of the outreach system at each step.  Response rate measures opener quality — does the message earn a reply at all?  Positive response rate distinguishes genuine interest from polite brush-offs — are people replying because they are curious or because they feel obligated to say no politely?  Conversion rate measures the full sequence's ability to move from first contact to a booked call or sale — does the sequence sustain interest and create the conditions for a decision?  A gap between response rate and positive response rate reveals an opener that generates social replies but fails to create genuine intent.  A gap between positive response rate and conversion rate reveals a sequence that warms people up but does not close them.  You name the exact gap and the mechanism behind it.
2. **Opener pattern analysis** — You understand that effective DM openers are fundamentally acts of recognition, not introduction.  The best openers make the recipient feel seen — that the sender noticed something specific about them, shares a relevant context with them, or holds knowledge they care about.  Generic openers that could be copied and pasted to 500 people are indistinguishable from spam to a sophisticated coaching or consulting prospect.  When you see a top-performing opener, you name precisely what makes it work: is it a specific observation about the recipient's situation? A shared identity signal (we both navigated the same transition)? A curiosity trigger (naming something the recipient didn't know they didn't know)? A community or event context that creates legitimate shared ground?  You extract the structural DNA of high-performing openers so it can be replicated, not just celebrated.
3. **Cross-domain CI synthesis** — Your highest-value output connects DM outreach patterns to what the target audience is expressing in the CI pool.  Pain points with high frequency counts that no DM sequence addresses represent outreach opportunity gaps — the audience is experiencing a specific, nameable problem and nobody in the outreach programme is opening a conversation about it.  ICP segments whose specific pain profile is not reflected in any sequence type represent systematic audience-message mismatch.  Client wins not used as social proof in any follow-up sequence are untapped credibility signals for warming cold or re-engagement threads.  You name all of these connections explicitly.

## Data Inputs

The Marketing Director provides all data pre-loaded.  You receive:

- **dm_stats** — Per-sequence DM performance metrics: sequence_type (cold_outreach/follow_up/re_engagement), platform (LinkedIn/Instagram/Facebook), messages_sent, response_rate (%), positive_response_rate (%), conversion_rate (%), avg_response_time_hours, top_performing_opener (the best opening message text for this sequence type), date_range.
- **pain_points** — The most frequently expressed client and prospect pain points from the shared CI intelligence pool: text, category, frequency_count.
- **icp_segments** — Validated ICP profiles: segment, description, demographics, pain_summary, buying_triggers, is_primary.
- **wins** — Client wins and success stories from the CI pool: text, category, frequency_count.
- **date_range_days** — The number of days covered by the analysis period.

You must use ALL of these inputs together.  An analysis that only reads dm_stats without cross-referencing CI data is incomplete and will be rejected.

## Analysis Mandate

- **Never return raw data verbatim.**  Interpret, synthesise, and draw conclusions.
- **Response rate is the primary signal** for opener quality.  Industry benchmarks for cold outreach in {{vertical}}: LinkedIn response rate > 20% is strong; 10-20% is moderate; < 10% is weak.  Instagram and Facebook cold DM response rates are typically lower due to lower perceived legitimacy — adjust benchmarks accordingly.
- **Positive response rate is the quality filter.**  A 40% response rate with 5% positive response rate means most replies are deflections or polite rejections — the opener is generating activity without generating interest.  Name this pattern explicitly when you see it.
- **Conversion rate reveals sequence depth.**  A high positive response rate with low conversion rate means the sequence warms people up but does not move them to a decision.  This is a mid-sequence or closing failure, not an opener failure — diagnose it at the correct layer.
- **Sequence type comparison is mandatory.**  Which sequence type converts best overall?  Is cold outreach or re-engagement generating better ROI per message sent?  Name the efficiency leader and explain why.
- **Opener pattern analysis must be structural.**  Do not describe what a top-performing opener says — describe WHY it works at a psychological level.  What structural element (specificity, shared identity, curiosity, observation) is driving the response rate?  What would a message writer need to replicate to get the same result?
- **Cross-domain gaps are outreach opportunities.**  For every high-frequency pain point (freq ≥ 5) with no corresponding DM sequence angle, raise an alert.  These are conversations the market is having that the outreach programme is not joining.

## Output Contract

You MUST return a single JSON object.  No prose before or after.  No markdown fences.  No explanations.  Only the JSON object.

The object must conform exactly to the output schema described below.  Every field is required.  If a list field has no entries, return an empty array — do not omit the field.

## Example Output

The following illustrates the expected structure and writing quality.  All values are fabricated for illustration only — replace every field with real synthesised content:

```json
{
  "summary": "LinkedIn cold outreach is the sequence type efficiency leader with a 24% response rate and 7.3% conversion rate, driven by an opener that names a specific transition the recipient recently made. Re-engagement sequences on Instagram are generating replies but failing to convert — a 31% response rate with 1.8% conversion rate indicates the sequence is generating social engagement rather than genuine commercial intent. Three of the top CI pain points have no corresponding DM sequence angle, representing the clearest opportunity to increase outreach relevance and response quality.",
  "top_performing_sequence": "cold_outreach",
  "overall_health": "moderate",
  "sequence_breakdown": [
    {
      "sequence_type": "cold_outreach",
      "platform": "LinkedIn",
      "response_rate": 24.0,
      "positive_response_rate": 14.2,
      "conversion_rate": 7.3,
      "health": "strong",
      "opener_diagnosis": "The top-performing opener ('Noticed you recently transitioned from agency to independent consulting — I work specifically with people at that inflection point') works because it names a specific, verifiable life event the recipient just experienced. It signals that the sender paid attention rather than running a blast sequence. The transition framing also activates the recipient's current problem-awareness — they are mid-transition and actively navigating the challenges that come with it.",
      "recommendation": "Extract the 'named recent transition' formula and apply it systematically across the sequence. Build a variant that opens with a different verifiable event (recently launched a programme, recently crossed a milestone) to test whether the transition angle outperforms milestone recognition."
    },
    {
      "sequence_type": "re_engagement",
      "platform": "Instagram",
      "response_rate": 31.0,
      "positive_response_rate": 8.4,
      "conversion_rate": 1.8,
      "health": "weak",
      "opener_diagnosis": "The 31% response rate looks healthy in isolation but the 8.4% positive response rate reveals that most replies are social noise — 'haha yeah it's been a while!' responses rather than genuine interest in continuing the conversation. The opener is triggering social reciprocity (it would feel rude not to reply to a friendly re-engagement message) rather than business curiosity. The re-engagement message is too informal — it reads as reconnecting with a friend rather than re-opening a business conversation.",
      "recommendation": "Reframe the re-engagement opener away from social warmth toward a new, specific value offer. Instead of 'Hey, it's been a while — hope you're well', try 'I've been working on something you specifically mentioned struggling with when we last spoke — thought it might be relevant now. Worth a quick conversation?' — this shifts from social reconnection to credible, timely relevance."
    }
  ],
  "opener_pattern_analysis": [
    {
      "sequence_type": "cold_outreach",
      "top_opener": "Noticed you recently transitioned from agency to independent consulting — I work specifically with people at that inflection point and wanted to reach out.",
      "pattern_identified": "Named transition + shared-terrain signal. The opener identifies a specific, recent life event (transition from employment to independence) and positions the sender as someone who navigates that exact terrain professionally. The phrase 'at that inflection point' signals that the sender understands the nuance of the transition, not just the surface label. This creates immediate relevance without a pitch.",
      "replication_advice": "Identify the top 3-5 verifiable transitions your ICP makes (agency to independent, corporate to coach, group programme to 1:1 or vice versa) and write a distinct opener template for each. The key is that the transition must be verifiable from the recipient's public profile — LinkedIn 'Open to Work', a recent post announcing a launch, a profile update changing their title. Openers built on publicly verifiable signals feel like genuine observation; openers built on assumptions feel like guesses."
    }
  ],
  "cross_domain_alerts": [
    "Pain point 'I don't know how to position myself to attract higher-ticket clients' (freq=14) has no corresponding DM sequence angle — this is the most common pre-purchase question in the CI pool and an obvious cold outreach opening context.",
    "Pain point 'I'm spending more time on delivery than on sales and it's stalling my growth' (freq=10) has no corresponding DM sequence — a re-engagement angle built around this pain point would directly address the reason warm prospects went quiet.",
    "Client win 'Signed first £5k+ client within 8 weeks' (freq=9) is not referenced in any follow-up sequence — this is the most compelling social proof available for warming prospects who have gone cold after initial interest."
  ],
  "recommended_focus": "Build a cold outreach variant on LinkedIn using the 'I don't know how to position myself for higher-ticket clients' pain point (freq=14) as the observation anchor — open with a specific observation about the recipient's current positioning, signal awareness of that exact pain, and invite a 15-minute conversation on how others at their stage have navigated it."
}
```\
"""



def render_dm_analysis_system_prompt(profile: PromptProfile | None = None) -> str:
    """Render the DM analysis system prompt for a specific instance profile."""
    return render(_DM_ANALYSIS_SYSTEM_PROMPT_TEMPLATE_V1, profile)


# Rendered with the frozen defaults (the pre-Phase-1 literals) so importers and
# the parity snapshot see stable text regardless of process state.
DM_ANALYSIS_SYSTEM_PROMPT_V1 = render_dm_analysis_system_prompt(DEFAULT_PROFILE)

# ---------------------------------------------------------------------------
# User prompt builder
# ---------------------------------------------------------------------------


def build_dm_analysis_user_prompt(data: dict) -> str:  # noqa: PLR0912
    """Format pre-loaded Marketing Director enrichment data into the DM analysis prompt.

    Parameters
    ----------
    data:
        A dict with keys: ``dm_stats``, ``pain_points``, ``icp_segments``,
        ``wins``, ``date_range_days``.

    Returns
    -------
    str
        The fully-rendered user prompt ready to send to the model.
    """

    date_range = data.get("date_range_days", 0)

    lines: list[str] = [
        "## Analysis Context",
        "",
        f"- Analysis period: {date_range} days",
        "",
    ]

    # -- DM sequence stats ---------------------------------------------------
    dm_stats: list[dict] = data.get("dm_stats", [])
    if dm_stats:
        lines += [
            "## DM Sequence Performance Stats (sorted by conversion rate, highest first)",
            "",
        ]
        sorted_stats = sorted(
            dm_stats, key=lambda d: d.get("conversion_rate", 0.0), reverse=True
        )
        for stat in sorted_stats:
            sequence_type = stat.get("sequence_type") or "Unknown"
            platform = stat.get("platform") or "Unknown"
            messages_sent = stat.get("messages_sent", 0)
            response_rate = stat.get("response_rate", 0.0)
            positive_response_rate = stat.get("positive_response_rate", 0.0)
            conversion_rate = stat.get("conversion_rate", 0.0)
            avg_response_time = stat.get("avg_response_time_hours", 0.0)
            top_opener = stat.get("top_performing_opener") or "Not recorded"
            date_range_label = stat.get("date_range") or ""

            date_str = f" ({date_range_label})" if date_range_label else ""
            lines += [
                f"### {sequence_type} — {platform}{date_str}",
                f"- Messages sent: {messages_sent:,}",
                f"- Response rate: {response_rate:.1f}%",
                f"- Positive response rate: {positive_response_rate:.1f}%",
                f"- Conversion rate: {conversion_rate:.1f}%",
                f"- Avg response time: {avg_response_time:.1f} hours",
                f"- Top performing opener: {top_opener}",
                "",
            ]
    else:
        lines += ["## DM Sequence Performance Stats", "", "(No DM stats available.)", ""]

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

    # -- ICP segments --------------------------------------------------------
    icp_segments: list[dict] = data.get("icp_segments", [])
    if icp_segments:
        lines += [
            "## ICP Segments",
            "",
        ]
        for seg in icp_segments:
            segment = seg.get("segment") or "Unknown"
            description = seg.get("description") or ""
            demographics = seg.get("demographics") or ""
            pain_summary = seg.get("pain_summary") or ""
            buying_triggers = seg.get("buying_triggers") or ""
            is_primary = seg.get("is_primary", False)
            primary_tag = " [PRIMARY]" if is_primary else ""
            lines += [f"### {segment}{primary_tag}"]
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
        lines += ["## ICP Segments", "", "(No ICP segment data available.)", ""]

    # -- Wins ----------------------------------------------------------------
    wins: list[dict] = data.get("wins", [])
    if wins:
        lines += [
            "## Client Wins / Success Stories (sorted by frequency, highest first)",
            "",
        ]
        sorted_wins = sorted(
            wins, key=lambda w: w.get("frequency_count", 0), reverse=True
        )
        for i, win in enumerate(sorted_wins, start=1):
            text = win.get("text") or ""
            category = win.get("category") or "Uncategorised"
            freq = win.get("frequency_count", 1)
            lines.append(f"{i}. [{category} | freq={freq}] {text}")
        lines.append("")
    else:
        lines += ["## Client Wins / Success Stories", "", "(No wins data available.)", ""]

    # -- Output instructions -------------------------------------------------
    lines += [
        "---",
        "",
        "## Your Task",
        "",
        "Using all of the intelligence above, produce a single JSON object conforming to the output schema.",
        "",
        "Analysis requirements:",
        "- summary must name the top-performing sequence type by conversion rate, identify the most critical underperformer, and state at least one cross-domain CI observation in 2-3 sentences.",
        "- top_performing_sequence is the sequence_type with the highest conversion_rate across all entries in dm_stats.",
        "- overall_health is 'strong' if the majority of sequences are healthy by conversion rate (> 5%), 'weak' if the majority are underperforming (< 2%), and 'moderate' otherwise.",
        "- sequence_breakdown must include every sequence present in dm_stats. Assign health: strong (conversion > 5%), moderate (conversion 2-5%), weak (conversion < 2%). The opener_diagnosis must explain WHY the top opener works at a structural/psychological level — not just what it says. Recommendations must be grounded in CI data.",
        "- opener_pattern_analysis must name the structural DNA of each top_performing_opener — the specific psychological mechanism (shared identity, named transition, curiosity trigger, observation anchor) that is driving the response rate. The replication_advice must give a concrete, actionable template or system for replicating the pattern.",
        "- cross_domain_alerts must name every high-frequency pain point (freq ≥ 5) with no corresponding DM sequence angle. Include exact text and frequency counts. This is the highest-value output for identifying outreach relevance gaps — do not skip it.",
        "- recommended_focus is the single highest-impact action for the next 7 days, grounded in the data. Must name a sequence type, platform, opener angle, and the CI data point supporting it.",
        "",
        "Output format — return ONLY this JSON object, nothing else:",
        "",
        json.dumps(
            {
                "summary": "2-3 sentence executive summary naming the top-performing sequence type, the overall health, and one CI cross-domain observation.",
                "top_performing_sequence": "sequence_type with the best conversion rate",
                "overall_health": "strong | moderate | weak",
                "sequence_breakdown": [
                    {
                        "sequence_type": "cold_outreach | follow_up | re_engagement",
                        "platform": "LinkedIn | Instagram | Facebook",
                        "response_rate": 0.0,
                        "positive_response_rate": 0.0,
                        "conversion_rate": 0.0,
                        "health": "strong | moderate | weak",
                        "opener_diagnosis": "Why the top opener works at a structural/psychological level — not just what it says.",
                        "recommendation": "Specific, CI-grounded next step to improve this sequence.",
                    }
                ],
                "opener_pattern_analysis": [
                    {
                        "sequence_type": "cold_outreach | follow_up | re_engagement",
                        "top_opener": "The exact text of the top performing opener.",
                        "pattern_identified": "The structural/psychological mechanism driving the response rate.",
                        "replication_advice": "Concrete, actionable template or system for replicating this pattern.",
                    }
                ],
                "cross_domain_alerts": [
                    "Pain point or win with frequency count that has no corresponding DM sequence angle."
                ],
                "recommended_focus": "Single highest-impact action for the next 7 days, naming sequence type, platform, opener angle, and supporting CI data point.",
            },
            indent=2,
        ),
        "",
        "Replace all placeholder strings with real synthesised content derived from the data above.",
        "Return ONLY the JSON object — no other text.",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Output schema (documentation / validation reference)
# ---------------------------------------------------------------------------

DM_ANALYSIS_OUTPUT_SCHEMA: dict = {
    "type": "object",
    "description": (
        "Structured DM outreach sequence performance analysis produced by the "
        "Direct Message Analyst (CI-MKT-DM) in analysis mode.  Consumed by the "
        "Marketing Director to inform outreach sequence strategy, opener testing, "
        "and CI-grounded content gap prioritisation."
    ),
    "required": [
        "summary",
        "top_performing_sequence",
        "overall_health",
        "sequence_breakdown",
        "opener_pattern_analysis",
        "cross_domain_alerts",
        "recommended_focus",
    ],
    "properties": {
        "summary": {
            "type": "string",
            "description": (
                "2-3 sentence executive summary of overall DM outreach performance for "
                "the analysis period.  Must name the top-performing sequence type by "
                "conversion rate, the overall health assessment, and at least one "
                "cross-domain CI observation connecting outreach behaviour to audience intelligence."
            ),
        },
        "top_performing_sequence": {
            "type": "string",
            "enum": ["cold_outreach", "follow_up", "re_engagement"],
            "description": (
                "The sequence type with the highest conversion rate across all entries "
                "in dm_stats.  Conversion rate takes precedence over response rate as "
                "the primary commercial efficiency signal."
            ),
            "example": "cold_outreach",
        },
        "overall_health": {
            "type": "string",
            "enum": ["strong", "moderate", "weak"],
            "description": (
                "Overall health assessment of the DM outreach programme.  "
                "'strong' = majority of sequences converting above 5%; "
                "'moderate' = mixed performance with clear improvement levers; "
                "'weak' = majority converting below 2% with systemic issues requiring urgent attention."
            ),
        },
        "sequence_breakdown": {
            "type": "array",
            "description": (
                "One entry per sequence present in dm_stats.  Each entry diagnoses "
                "the specific funnel layer responsible for performance and provides "
                "a concrete, CI-grounded recommendation."
            ),
            "items": {
                "type": "object",
                "required": [
                    "sequence_type",
                    "platform",
                    "response_rate",
                    "positive_response_rate",
                    "conversion_rate",
                    "health",
                    "opener_diagnosis",
                    "recommendation",
                ],
                "properties": {
                    "sequence_type": {
                        "type": "string",
                        "description": "Sequence type: cold_outreach, follow_up, or re_engagement.",
                    },
                    "platform": {
                        "type": "string",
                        "description": "Platform: LinkedIn, Instagram, or Facebook.",
                    },
                    "response_rate": {
                        "type": "number",
                        "description": "Total response rate as a percentage.",
                    },
                    "positive_response_rate": {
                        "type": "number",
                        "description": "Positive (genuine interest) response rate as a percentage.",
                    },
                    "conversion_rate": {
                        "type": "number",
                        "description": "Full-sequence conversion rate as a percentage.",
                    },
                    "health": {
                        "type": "string",
                        "enum": ["strong", "moderate", "weak"],
                        "description": (
                            "Health classification: strong = conversion > 5%; "
                            "moderate = conversion 2-5%; weak = conversion < 2%."
                        ),
                    },
                    "opener_diagnosis": {
                        "type": "string",
                        "description": (
                            "Explains WHY the top_performing_opener works at a structural "
                            "and psychological level — not just what it says.  Names the "
                            "specific mechanism (shared identity, named transition, curiosity "
                            "trigger, observation anchor, specificity of reference) that is "
                            "driving the response rate.  Cross-references CI data where "
                            "applicable."
                        ),
                    },
                    "recommendation": {
                        "type": "string",
                        "description": (
                            "Specific, actionable next step to improve this sequence.  "
                            "Must be grounded in CI data (pain points, wins, or ICP insights).  "
                            "Not a generic best-practice note."
                        ),
                    },
                },
            },
        },
        "opener_pattern_analysis": {
            "type": "array",
            "description": (
                "One entry per sequence type with a recorded top_performing_opener.  "
                "Each entry extracts the structural DNA of the opener and provides "
                "concrete, actionable replication guidance."
            ),
            "items": {
                "type": "object",
                "required": [
                    "sequence_type",
                    "top_opener",
                    "pattern_identified",
                    "replication_advice",
                ],
                "properties": {
                    "sequence_type": {
                        "type": "string",
                        "description": "The sequence type this opener belongs to.",
                    },
                    "top_opener": {
                        "type": "string",
                        "description": "The exact text of the top-performing opener for this sequence type.",
                    },
                    "pattern_identified": {
                        "type": "string",
                        "description": (
                            "The structural or psychological mechanism driving the high response "
                            "rate.  Examples: named recent transition, shared identity signal, "
                            "curiosity trigger naming an unknown unknown, specific public "
                            "observation, community or event context.  Must explain WHY the "
                            "pattern works for this audience — not just label it."
                        ),
                    },
                    "replication_advice": {
                        "type": "string",
                        "description": (
                            "Concrete, actionable guidance for writing new openers using the "
                            "same structural pattern.  Should include a template or system — "
                            "e.g. 'Identify [signal type] from the recipient's [profile element], "
                            "then open with [structure]'.  Specific enough for a message writer "
                            "to apply immediately."
                        ),
                    },
                },
            },
        },
        "cross_domain_alerts": {
            "type": "array",
            "description": (
                "Plain-language alerts for high-frequency CI pain points (freq ≥ 5) "
                "with no corresponding DM sequence angle, and for client wins not "
                "referenced in any follow-up or re-engagement sequence.  Each alert "
                "must name the exact pain point or win with its frequency count.  "
                "These are outreach opportunity gaps — do not return an empty array "
                "without genuinely checking all CI inputs against the dm_stats data."
            ),
            "items": {
                "type": "string",
                "description": (
                    "e.g. \"Pain point 'I don't know how to position myself for "
                    "higher-ticket clients' (freq=14) has no corresponding DM sequence "
                    "angle.\""
                ),
            },
        },
        "recommended_focus": {
            "type": "string",
            "description": (
                "A single, specific action that would have the greatest outreach impact "
                "in the next 7 days, based on all available DM and CI data.  Must name "
                "a sequence type, platform, opener angle, and the CI data point supporting "
                "the recommendation.  Maximum two sentences."
            ),
        },
    },
}

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

__all__ = [
    "DM_ANALYSIS_SYSTEM_PROMPT_V1",
    "DM_ANALYSIS_OUTPUT_SCHEMA",
    "build_dm_analysis_user_prompt",
    "render_dm_analysis_system_prompt",
]
