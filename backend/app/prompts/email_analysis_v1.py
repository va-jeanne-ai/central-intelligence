"""
Email Analysis prompt — v1 (CI-MKT-EMAIL / M02-2).

Defines the system prompt, user prompt builder, and output schema for the
Email Specialist in analysis mode.  This module is consumed by the Marketing
Director when it needs a structured email campaign performance analysis with
cross-domain CI synthesis.
The Marketing Director pre-loads all enrichment data (email stats, content
ideas, market signals, pain points, ICP segments) before invoking this prompt;
the specialist does NOT query data itself.
"""

from __future__ import annotations

import json

from app.prompts.context import DEFAULT_PROFILE, PromptProfile, render

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

_EMAIL_ANALYSIS_SYSTEM_PROMPT_TEMPLATE_V1 = """\
You are **CI-MKT-EMAIL**, the Email Specialist of {{app_name}} — an AI-powered business intelligence platform for {{vertical}} businesses — operating in **analysis mode**.

## Role

You sit inside the Marketing department, reporting to the Marketing Director.  Your sole function is to analyse email campaign performance data and surface actionable intelligence grounded in CI evidence.  You are NOT a chatbot.  You produce structured JSON output only — no prose, no markdown, no commentary outside the JSON envelope.

## Expertise

You combine three disciplines:

1. **Email metrics interpretation** — You read open rates, click-through rates, conversion rates, and unsubscribe rates across campaign types.  You distinguish between a deliverability problem (low open rate despite strong list hygiene), a subject line problem (low open rate with healthy deliverability), and a content or offer relevance problem (strong open rate but low click and conversion rates).  You name the mechanism behind each pattern — never the number in isolation.
2. **Audience engagement psychology** — You understand the causal chain behind each metric: open rate reflects subject line strength combined with sender trust; click rate reflects offer relevance and body copy clarity; conversion rate reflects landing page alignment and offer specificity; unsubscribe rate reflects audience-message fit and send frequency.  When a metric underperforms, you name the specific mechanism responsible — not a generic best-practice note.
3. **Cross-domain CI synthesis** — Your greatest value is connecting email performance patterns to what the audience is actually saying on calls.  Pain points, market signals, and ICP profiles explain why segments engage or disengage.  A campaign type with persistently low click rates combined with a high-frequency unresolved pain point is not a coincidence — it signals an audience speaking a language the email content has not yet matched.  You make that connection explicit and name it as a revenue gap.

## Data Inputs

The Marketing Director provides all data pre-loaded.  You receive:

- **email_stats** — Per-campaign-type performance metrics: campaign_type, campaigns_sent, total_recipients, avg_open_rate, avg_click_rate, avg_conversion_rate, avg_unsubscribe_rate, top_performing_subject (the subject line with the highest open rate within that campaign type).
- **content_ideas** — Validated content angles from the CI intelligence pool: content_angle, content_format, idea_score, status, best_platform, hook_opening_line.
- **market_signals** — Trending signals and themes extracted from call transcripts: signal_family, signal, last_7_days, total_mentions, best_marketing_angle.
- **pain_points** — The most frequently expressed client and prospect pain points from the shared intelligence pool: text, category, frequency_count.
- **icp_segments** — Validated ICP profiles for the business, flagging the primary segment.

You must use ALL of these inputs together.  An analysis that only reads email_stats without cross-referencing CI data is incomplete and will be rejected.

## Analysis Mandate

- **Never return raw data verbatim.**  Interpret, synthesise, and draw conclusions.
- **Engagement rate is the primary signal** for campaign health, not send volume or total recipient count.  A campaign type with 200 recipients and a 48% open rate outperforms one with 5,000 recipients at 14%.
- **Top-performing subject lines are signal — name the pattern.**  If a subject line in a campaign type outperforms all others, identify what rhetorical device or emotional trigger it uses (curiosity gap, named pain, specific outcome, contrarian framing) and recommend how to replicate the pattern across other campaign types.
- **Content gaps are revenue gaps.**  If high-frequency pain points or trending market signals have no corresponding email campaign content, flag this explicitly with the exact pain point text and frequency count.
- **Diagnose the layer, not just the metric.**  A low click rate on a high-open-rate campaign means the subject line is working but the body copy or offer is failing.  State which layer of the email is the problem, and why.
- **ICP alignment matters.**  Campaign performance should be evaluated in the context of whether the content speaks to the primary ICP's specific pain patterns and buying triggers.

## Output Contract

You MUST return a single JSON object.  No prose before or after.  No markdown fences.  No explanations.  Only the JSON object.

The object must conform exactly to the output schema described below.  Every field is required.  If a list field has no entries, return an empty array — do not omit the field.

## Example Output

The following illustrates the expected structure and writing quality.  All values are fabricated for illustration only — replace every field with real synthesised content:

```json
{
  "summary": "Nurture emails are the clear performance leader with a 46% average open rate and a subject line pattern built around naming specific client fears — a direct mirror of the top CI pain points. Broadcast campaigns are underperforming at 1.2% click rate despite healthy opens, indicating a disconnect between subject line promise and body copy delivery. Re-engagement campaigns show a dangerously high 3.4% unsubscribe rate, suggesting the segment is being contacted too frequently or with content that no longer matches their situation.",
  "top_performing_campaign_type": "nurture",
  "overall_health": "moderate",
  "campaign_breakdown": [
    {
      "campaign_type": "nurture",
      "avg_open_rate": 46.2,
      "avg_click_rate": 8.7,
      "avg_conversion_rate": 3.1,
      "health": "strong",
      "diagnosis": "Strong performance across all three primary metrics. The top subject line 'The real reason your revenue has plateaued' mirrors the CI pain point on business stagnation (freq=19) — the audience recognises themselves in the subject and opens at high rates. Click and conversion rates confirm that body copy is delivering on the subject line's implicit promise.",
      "recommendation": "Extract the naming-the-fear subject line formula from this campaign type and apply it systematically to broadcast and re-engagement campaigns. Create a nurture series built explicitly from the top 5 CI pain points — each email in the sequence addresses one pain point and soft-CTAs to a free diagnostic resource."
    },
    {
      "campaign_type": "broadcast",
      "avg_open_rate": 38.4,
      "avg_click_rate": 1.2,
      "avg_conversion_rate": 0.4,
      "health": "weak",
      "diagnosis": "The 38% open rate confirms subject lines are compelling — the audience is interested enough to open. The collapse to 1.2% click rate is a body copy and offer relevance failure. The body is not delivering the specific value the subject line implied, creating a trust deficit that manifests as click-through abandonment. The market signal 'group programme demand' (7-day mentions: 11) has no corresponding broadcast content, indicating a missed revenue opportunity.",
      "recommendation": "Audit the top 3 broadcast emails with the open-click gap. Rewrite body copy to open with a direct hook that mirrors the subject line's emotional frame before pivoting to the offer. Test a broadcast email built around the group programme demand signal — address the audience's desire for peer learning directly in the body."
    }
  ],
  "subject_line_insights": [
    {
      "campaign_type": "nurture",
      "top_subject": "The real reason your revenue has plateaued",
      "pattern_identified": "Contrarian diagnosis — names a hidden cause behind a known symptom. Creates curiosity by implying the reader's current explanation is wrong, which is irresistible to an audience actively trying to solve the problem.",
      "replication_advice": "Apply this pattern to broadcast campaigns by pairing a visible symptom with a non-obvious cause: 'Why posting more content is making your pipeline worse' or 'The thing your discovery call is missing (it's not your close rate)'."
    }
  ],
  "content_gaps": [
    "Market signal 'group programme demand' (7-day mentions: 11) has no corresponding email campaign content across any campaign type.",
    "Pain point 'I don't know how to price my offer confidently' (freq=16) has no corresponding email campaign content.",
    "Content idea 'From employee to entrepreneur — the identity shift nobody talks about' (score=91) has not been deployed in any email campaign."
  ],
  "cross_domain_insights": [
    "The nurture campaign's top subject line directly mirrors CI pain point 'my business growth has stalled and I don't know why' (freq=19) — confirming that naming audience fears in the subject line drives open rates above the coaching-industry average of 28%.",
    "Broadcast click rates have collapsed despite healthy opens — the CI content ideas pool contains 7 high-scoring angles (score > 80) that have never appeared in a broadcast email, indicating the content strategy is disconnected from validated audience intelligence.",
    "The re-engagement campaign's 3.4% unsubscribe rate aligns with CI market signal 'audience fatigue with generic content' (7-day mentions: 6) — the segment is self-selecting out because the emails do not address their current stage of awareness or their evolving pain profile.",
    "Primary ICP (established coaches, 3-7 years in business) has 'ROI clarity' as a primary buying trigger — no current email campaign type leads with ROI-framed subject lines or body copy, creating a systematic mismatch between content and the decision-making lens of the highest-value audience segment."
  ],
  "recommended_focus": "Rewrite the top 3 broadcast email bodies this week to honour the subject line's emotional promise — open with the exact fear or curiosity the subject names, deliver a concrete insight before asking for a click, and close with a single CTA linked to the highest-scoring CI content idea in the pool."
}
```\
"""



def render_email_analysis_system_prompt(profile: PromptProfile | None = None) -> str:
    """Render the email analysis system prompt for a specific instance profile."""
    return render(_EMAIL_ANALYSIS_SYSTEM_PROMPT_TEMPLATE_V1, profile)


# Rendered with the frozen defaults (the pre-Phase-1 literals) so importers and
# the parity snapshot see stable text regardless of process state.
EMAIL_ANALYSIS_SYSTEM_PROMPT_V1 = render_email_analysis_system_prompt(DEFAULT_PROFILE)

# ---------------------------------------------------------------------------
# User prompt builder
# ---------------------------------------------------------------------------


def build_email_analysis_user_prompt(data: dict) -> str:  # noqa: PLR0912
    """Format pre-loaded Marketing Director enrichment data into the email analysis prompt.

    Parameters
    ----------
    data:
        A dict with keys: ``email_stats``, ``content_ideas``, ``market_signals``,
        ``pain_points``, ``icp_segments``, ``date_range_days``.

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

    # -- Email campaign performance stats ------------------------------------
    email_stats: list[dict] = data.get("email_stats", [])
    if email_stats:
        lines += [
            "## Email Campaign Performance Stats (sorted by open rate, highest first)",
            "",
        ]
        sorted_stats = sorted(
            email_stats, key=lambda e: e.get("avg_open_rate", 0.0), reverse=True
        )
        for stat in sorted_stats:
            campaign_type = stat.get("campaign_type") or "Unknown"
            campaigns_sent = stat.get("campaigns_sent", 0)
            total_recipients = stat.get("total_recipients", 0)
            avg_open_rate = stat.get("avg_open_rate", 0.0)
            avg_click_rate = stat.get("avg_click_rate", 0.0)
            avg_conversion_rate = stat.get("avg_conversion_rate", 0.0)
            avg_unsubscribe_rate = stat.get("avg_unsubscribe_rate", 0.0)
            top_subject = stat.get("top_performing_subject") or "Not recorded"

            lines += [
                f"### {campaign_type}",
                f"- Campaigns sent: {campaigns_sent}",
                f"- Total recipients: {total_recipients:,}",
                f"- Avg open rate: {avg_open_rate:.1f}%",
                f"- Avg click rate: {avg_click_rate:.1f}%",
                f"- Avg conversion rate: {avg_conversion_rate:.1f}%",
                f"- Avg unsubscribe rate: {avg_unsubscribe_rate:.2f}%",
                f"- Top performing subject: {top_subject}",
                "",
            ]
    else:
        lines += [
            "## Email Campaign Performance Stats",
            "",
            "(No email stats available.)",
            "",
        ]

    # -- Content ideas -------------------------------------------------------
    content_ideas: list[dict] = data.get("content_ideas", [])
    if content_ideas:
        lines += [
            "## Content Ideas (from CI intelligence pool, sorted by score descending)",
            "",
        ]
        sorted_ideas = sorted(
            content_ideas, key=lambda c: c.get("idea_score", 0), reverse=True
        )
        for i, idea in enumerate(sorted_ideas, start=1):
            angle = idea.get("content_angle") or ""
            fmt = idea.get("content_format") or ""
            score = idea.get("idea_score", 0)
            status = idea.get("status") or "pending"
            platform = idea.get("best_platform") or ""
            hook = idea.get("hook_opening_line") or ""
            lines.append(
                f"{i}. [{fmt} | {platform} | score={score} | {status}] {angle}"
            )
            if hook:
                lines.append(f"   Hook: {hook}")
        lines.append("")
    else:
        lines += ["## Content Ideas", "", "(No content ideas available.)", ""]

    # -- Market signals ------------------------------------------------------
    market_signals: list[dict] = data.get("market_signals", [])
    if market_signals:
        lines += [
            "## Market Signals (sorted by recent mention volume, highest first)",
            "",
        ]
        sorted_signals = sorted(
            market_signals, key=lambda s: s.get("last_7_days", 0), reverse=True
        )
        for i, sig in enumerate(sorted_signals, start=1):
            family = sig.get("signal_family") or ""
            signal = sig.get("signal") or ""
            last_7 = sig.get("last_7_days", 0)
            total = sig.get("total_mentions", 0)
            angle = sig.get("best_marketing_angle") or ""
            lines.append(
                f"{i}. [{family} | 7-day mentions={last_7} | total={total}] {signal}"
            )
            if angle:
                lines.append(f"   Best angle: {angle}")
        lines.append("")
    else:
        lines += ["## Market Signals", "", "(No market signals available.)", ""]

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
            lines += [
                f"### {segment}{primary_tag}",
            ]
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

    # -- Output instructions -------------------------------------------------
    lines += [
        "---",
        "",
        "## Your Task",
        "",
        "Using all of the intelligence above, produce a single JSON object conforming to the output schema.",
        "",
        "Analysis requirements:",
        "- summary must name the top-performing campaign type, the overall health assessment, and at least one cross-domain CI observation in 2-3 sentences.",
        "- top_performing_campaign_type is the campaign type with the highest avg_open_rate.",
        "- overall_health is 'strong' if the majority of campaign types are healthy, 'weak' if the majority are underperforming, and 'moderate' otherwise. Apply coaching-industry email benchmarks: open rate > 35% is strong, 20-35% is moderate, < 20% is weak.",
        "- For campaign_breakdown, include every campaign type present in email_stats. Assign health using the same benchmark thresholds. The diagnosis must name the specific layer of the email that is failing (subject line, body copy, offer, landing page alignment) and the psychological mechanism. The recommendation must be grounded in CI data.",
        "- For subject_line_insights, identify the rhetorical pattern or emotional trigger behind each campaign type's top_performing_subject (curiosity gap, named pain, specific outcome, contrarian framing, social proof, etc.). The replication_advice must give a concrete, usable template or example.",
        "- For content_gaps, explicitly name each high-frequency pain point, trending market signal, or high-scoring content idea that has no corresponding email campaign content. Include frequency counts and scores. This is high-value output — do not skip it.",
        "- For cross_domain_insights, connect CI data (pain points, market signals, ICP profiles) to specific campaign performance patterns. Name exact CI signals with frequency counts. Minimum 3 insights required.",
        "- recommended_focus must be a single, specific action that would have the greatest email revenue impact in the next 7 days based on all available data.",
        "",
        "Output format — return ONLY this JSON object, nothing else:",
        "",
        json.dumps(
            {
                "summary": "2-3 sentence executive summary naming the top-performing campaign type, overall health, and one CI observation.",
                "top_performing_campaign_type": "campaign type name",
                "overall_health": "strong | moderate | weak",
                "campaign_breakdown": [
                    {
                        "campaign_type": "campaign type name",
                        "avg_open_rate": 0.0,
                        "avg_click_rate": 0.0,
                        "avg_conversion_rate": 0.0,
                        "health": "strong | moderate | weak",
                        "diagnosis": "Which email layer is failing and the psychological mechanism behind it.",
                        "recommendation": "Specific, actionable next step grounded in CI data.",
                    }
                ],
                "subject_line_insights": [
                    {
                        "campaign_type": "campaign type name",
                        "top_subject": "The subject line text",
                        "pattern_identified": "The rhetorical device or emotional trigger this subject line uses.",
                        "replication_advice": "Concrete template or example for applying this pattern to other campaign types.",
                    }
                ],
                "content_gaps": [
                    "Pain point or market signal with frequency/score that has no corresponding email content."
                ],
                "cross_domain_insights": [
                    "CI signal (pain point or market signal with frequency) that explains a specific email performance pattern."
                ],
                "recommended_focus": "Single most impactful action for the next 7 days.",
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

EMAIL_ANALYSIS_OUTPUT_SCHEMA: dict = {
    "type": "object",
    "description": (
        "Structured email campaign performance analysis produced by the Email "
        "Specialist (CI-MKT-EMAIL) in analysis mode.  Consumed by the Marketing "
        "Director to inform campaign strategy, subject line testing, and content "
        "gap prioritisation."
    ),
    "required": [
        "summary",
        "top_performing_campaign_type",
        "overall_health",
        "campaign_breakdown",
        "subject_line_insights",
        "content_gaps",
        "cross_domain_insights",
        "recommended_focus",
    ],
    "properties": {
        "summary": {
            "type": "string",
            "description": (
                "2-3 sentence executive summary of overall email performance for the "
                "analysis period.  Must name the top-performing campaign type, state "
                "the overall health assessment, and include at least one cross-domain "
                "CI observation connecting email behaviour to audience intelligence."
            ),
        },
        "top_performing_campaign_type": {
            "type": "string",
            "description": (
                "The campaign type with the highest average open rate for the period "
                "(e.g. 'nurture', 'broadcast', 'launch_announcement').  Open rate takes "
                "precedence as the primary reach signal; click and conversion rates are "
                "used to distinguish between strong and merely popular campaign types."
            ),
            "example": "nurture",
        },
        "overall_health": {
            "type": "string",
            "enum": ["strong", "moderate", "weak"],
            "description": (
                "Overall health assessment of the email programme across all campaign types.  "
                "'strong' = majority of campaign types performing above coaching-industry "
                "benchmarks (open > 35%, click > 3%); 'moderate' = mixed performance with "
                "clear improvement levers; 'weak' = majority underperforming benchmarks with "
                "systemic issues requiring urgent attention."
            ),
        },
        "campaign_breakdown": {
            "type": "array",
            "description": (
                "One entry per campaign type present in the input email_stats.  Each entry "
                "diagnoses the specific email layer responsible for performance and provides "
                "a concrete, CI-grounded recommendation."
            ),
            "items": {
                "type": "object",
                "required": [
                    "campaign_type",
                    "avg_open_rate",
                    "avg_click_rate",
                    "avg_conversion_rate",
                    "health",
                    "diagnosis",
                    "recommendation",
                ],
                "properties": {
                    "campaign_type": {
                        "type": "string",
                        "description": "Campaign type name (e.g. 'nurture', 'broadcast', 're_engagement').",
                    },
                    "avg_open_rate": {
                        "type": "number",
                        "description": "Average open rate as a percentage (e.g. 38.4 for 38.4%).",
                    },
                    "avg_click_rate": {
                        "type": "number",
                        "description": "Average click-through rate as a percentage.",
                    },
                    "avg_conversion_rate": {
                        "type": "number",
                        "description": "Average conversion rate as a percentage.",
                    },
                    "health": {
                        "type": "string",
                        "enum": ["strong", "moderate", "weak"],
                        "description": (
                            "Health assessment for this campaign type relative to "
                            "coaching-industry email benchmarks."
                        ),
                    },
                    "diagnosis": {
                        "type": "string",
                        "description": (
                            "Identifies the specific email layer failing (subject line, preview "
                            "text, body copy, offer clarity, landing page alignment) and names "
                            "the psychological or messaging mechanism behind the performance.  "
                            "Must go beyond restating the metric — explain why the audience is "
                            "or is not engaging at each stage.  Cross-reference CI data where "
                            "applicable."
                        ),
                    },
                    "recommendation": {
                        "type": "string",
                        "description": (
                            "Specific, actionable next step to improve this campaign type.  "
                            "Must be grounded in CI data (pain points, market signals, content "
                            "ideas, or ICP insights) — not a generic best-practice suggestion."
                        ),
                    },
                },
            },
        },
        "subject_line_insights": {
            "type": "array",
            "description": (
                "One entry per campaign type with a recorded top_performing_subject.  "
                "Each entry names the rhetorical pattern or emotional trigger the subject "
                "line uses and provides concrete replication advice for other campaign types."
            ),
            "items": {
                "type": "object",
                "required": [
                    "campaign_type",
                    "top_subject",
                    "pattern_identified",
                    "replication_advice",
                ],
                "properties": {
                    "campaign_type": {
                        "type": "string",
                        "description": "The campaign type this subject line belongs to.",
                    },
                    "top_subject": {
                        "type": "string",
                        "description": "The exact subject line text of the top-performing email in this campaign type.",
                    },
                    "pattern_identified": {
                        "type": "string",
                        "description": (
                            "The rhetorical device or emotional trigger this subject line uses.  "
                            "Examples: curiosity gap, named pain point, specific outcome promise, "
                            "contrarian framing, social proof reference, time urgency.  Explain "
                            "WHY this pattern works for this audience."
                        ),
                    },
                    "replication_advice": {
                        "type": "string",
                        "description": (
                            "Concrete, usable guidance for applying this pattern to other campaign "
                            "types.  Should include a template structure or 1-2 example subject "
                            "lines that could be deployed immediately."
                        ),
                    },
                },
            },
        },
        "content_gaps": {
            "type": "array",
            "description": (
                "Plain-language statements identifying high-frequency CI signals (pain "
                "points, market signals) or high-scoring content ideas that have no "
                "corresponding email campaign content in the current period.  Each gap "
                "must name the specific signal with its frequency count or score.  "
                "These are revenue gaps — do not omit this field or return an empty array "
                "without genuinely checking all CI inputs against email content."
            ),
            "items": {
                "type": "string",
                "description": (
                    "e.g. \"Pain point 'I don't know how to price my offer confidently' "
                    "(freq=16) has no corresponding email campaign content.\""
                ),
            },
        },
        "cross_domain_insights": {
            "type": "array",
            "description": (
                "Plain-language insights connecting CI data (pain points, market signals, "
                "ICP profiles) to specific email campaign performance patterns.  Each insight "
                "must name the exact CI signal with its frequency count and link it explicitly "
                "to a campaign-level observation.  Minimum 3 insights required.  This is the "
                "highest-value output for explaining WHY the email programme performs as it does."
            ),
            "items": {
                "type": "string",
                "description": (
                    "e.g. \"The nurture campaign's top subject line directly mirrors CI pain "
                    "point 'my business growth has stalled' (freq=19) — confirming that naming "
                    "audience fears in the subject drives above-benchmark open rates.\""
                ),
            },
            "minItems": 1,
        },
        "recommended_focus": {
            "type": "string",
            "description": (
                "A single, specific action that would have the greatest email revenue impact "
                "in the next 7 days, based on all available email and CI data.  Should name "
                "a campaign type, the specific email layer to address, and the CI insight that "
                "supports the action.  This is the executive takeaway — one sentence, maximum two."
            ),
        },
    },
}

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

__all__ = [
    "EMAIL_ANALYSIS_SYSTEM_PROMPT_V1",
    "EMAIL_ANALYSIS_OUTPUT_SCHEMA",
    "build_email_analysis_user_prompt",
    "render_email_analysis_system_prompt",
]
