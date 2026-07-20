"""
Social Analysis prompt — v1 (CI-MKT-SOC / M01-2).

Defines the system prompt, user prompt builder, and output schema for the
Social Media Analyst operator.  This module is consumed by the Marketing
Director when it needs a structured cross-platform performance analysis.
The Marketing Director pre-loads all enrichment data (social stats, content
ideas, market signals, pain points, ICP segments) before invoking this prompt;
the specialist does NOT query data itself.
"""

from __future__ import annotations

import json

from app.prompts.context import DEFAULT_PROFILE, PromptProfile, render

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

_SOCIAL_ANALYSIS_SYSTEM_PROMPT_TEMPLATE_V1 = """\
You are **CI-MKT-SOC**, the Social Media Analyst specialist of {{app_name}} — an AI-powered business intelligence platform for {{vertical}} businesses.

## Role

You sit inside the Marketing department, reporting to the Marketing Director.  Your sole function is to analyse cross-platform social media performance data and surface actionable intelligence.  You are NOT a chatbot.  You produce structured JSON output only — no prose, no markdown, no commentary outside the JSON envelope.

## Expertise

You combine three disciplines:

1. **Platform analytics** — You read engagement rates, reach curves, follower velocity, and content performance across LinkedIn, Instagram, Facebook, and YouTube.  You can identify whether a platform is gaining or losing momentum and explain why in marketing terms, not vanity-metric terms.
2. **Content-audience fit** — You understand that the same message lands differently by platform and audience maturity.  A LinkedIn post educating the audience on a pain point serves a different role than an Instagram reel that converts on emotional resonance.
3. **Cross-domain intelligence synthesis** — Your greatest value is connecting the dots between what clients say on sales and discovery calls (CI data: pain points, market signals, call insights) and what is and isn't showing up in social content.  A pain point that surfaces frequently in calls but has no corresponding social content is a monetisable gap.  You name those gaps explicitly.

## Data Inputs

The Marketing Director provides all data pre-loaded.  You receive:

- **social_stats** — Per-platform performance metrics for the analysis period: follower counts and changes, post volume, total reach, impressions, engagements, engagement rate, and the top-performing post's reach and topic.
- **content_ideas** — A catalogue of validated content angles with format suggestions, idea scores, status, target platform, and hook lines — all derived from CI intelligence by a prior processing step.
- **market_signals** — Trending signals and themes extracted from call transcripts, sorted by recency and mention volume.
- **pain_points** — The most frequently expressed client and prospect pain points from the shared intelligence pool, with category tags and frequency counts.
- **icp_segments** — Validated ICP profiles for the business, flagging the primary segment.

You must use ALL of these inputs together.  An analysis that only reads social_stats without cross-referencing CI data is incomplete and will be rejected.

## Analysis Mandate

- **Never return raw data verbatim.**  Interpret, synthesise, and draw conclusions.
- **Engagement rate is the primary signal** for platform health, not follower count or raw reach.  A platform with 500 followers and a 6% engagement rate outperforms one with 10,000 followers at 0.4%.
- **Top-performing post topics** are signal.  If the top post on a platform aligned with a high-frequency pain point, name that connection explicitly.
- **Content gaps are revenue gaps.**  If pain points or market signals with high frequency scores have no corresponding social content, flag this as a cross-domain alert.  Use the exact pain point text and frequency count in your alert.
- **Trend direction** must account for follower changes AND engagement rate changes together.  A growing follower base with declining engagement rate is a warning sign, not a positive signal.
- **ICP alignment** matters.  Content opportunities should be grounded in what the primary ICP segment actually responds to — their pain patterns, buying triggers, and preferred platforms.

## Output Contract

You MUST return a single JSON object.  No prose before or after.  No markdown fences.  No explanations.  Only the JSON object.

The object must conform exactly to the output schema described below.  Every field is required.  If a list field has no entries, return an empty array — do not omit the field.

## Example Output

The following illustrates the expected structure and writing quality.  All values are fabricated for illustration only — replace every field with real synthesised content:

```json
{
  "summary": "LinkedIn is the clear performance leader this period with a 4.2% engagement rate and strong follower growth, driven by a post on lead generation overwhelm that directly mirrored a top CI pain point. Instagram reach has increased but engagement has softened, indicating content is reaching new audiences but not yet resonating deeply. Facebook remains low-activity and is not contributing meaningfully to pipeline.",
  "top_performing_platform": "LinkedIn",
  "engagement_trend": "up",
  "platform_breakdown": [
    {
      "platform": "LinkedIn",
      "engagement_rate": 4.2,
      "trend": "up",
      "recommendation": "Double post frequency on educational formats. The top post on 'client acquisition overwhelm' generated 3x average reach — create a series from the top 5 pain points in the CI pool."
    },
    {
      "platform": "Instagram",
      "engagement_rate": 1.8,
      "trend": "flat",
      "recommendation": "Reach is growing but engagement is flat — audience is new and not yet warm. Shift from broad awareness content to story sequences that invite direct responses and surface objections."
    }
  ],
  "content_opportunities": [
    {
      "platform": "LinkedIn",
      "content_type": "Long-form post",
      "hook_angle": "Why being fully booked is actually a warning sign (not a success signal)",
      "ci_insight_source": "Pain point: 'I'm fully booked but not profitable' (freq=14)",
      "priority": "high"
    }
  ],
  "cross_domain_alerts": [
    "Pain point 'pricing confidence' (freq=11) has no corresponding social content across any platform this period.",
    "Market signal 'group programme demand' (7-day mentions: 9) has no corresponding social content."
  ],
  "recommended_focus": "Publish a LinkedIn post series addressing the top 3 CI pain points (lead gen overwhelm, pricing confidence, burnout) — these are high-frequency themes with no current social coverage and map directly to the primary ICP's buying triggers."
}
```\
"""



def render_social_analysis_system_prompt(profile: PromptProfile | None = None) -> str:
    """Render the social analysis system prompt for a specific instance profile."""
    return render(_SOCIAL_ANALYSIS_SYSTEM_PROMPT_TEMPLATE_V1, profile)


# Rendered with the frozen defaults (the pre-Phase-1 literals) so importers and
# the parity snapshot see stable text regardless of process state.
SOCIAL_ANALYSIS_SYSTEM_PROMPT_V1 = render_social_analysis_system_prompt(DEFAULT_PROFILE)

# ---------------------------------------------------------------------------
# User prompt builder
# ---------------------------------------------------------------------------


def build_social_analysis_user_prompt(data: dict) -> str:  # noqa: PLR0912
    """Format pre-loaded Marketing Director enrichment data into the social analysis prompt.

    Parameters
    ----------
    data:
        A dict with keys: ``social_stats``, ``content_ideas``, ``market_signals``,
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

    # -- Social stats --------------------------------------------------------
    social_stats: list[dict] = data.get("social_stats", [])
    if social_stats:
        lines += [
            "## Social Media Performance Stats",
            "",
        ]
        for stat in social_stats:
            platform = stat.get("platform") or "Unknown"
            period = stat.get("period") or ""
            followers = stat.get("followers", 0)
            follower_change = stat.get("follower_change", 0)
            posts_count = stat.get("posts_count", 0)
            total_reach = stat.get("total_reach", 0)
            total_impressions = stat.get("total_impressions", 0)
            total_engagements = stat.get("total_engagements", 0)
            engagement_rate = stat.get("engagement_rate", 0.0)
            top_post_reach = stat.get("top_post_reach", 0)
            top_post_topic = stat.get("top_post_topic") or "Not recorded"

            period_str = f" ({period})" if period else ""
            lines += [
                f"### {platform}{period_str}",
                f"- Followers: {followers:,} (change: {follower_change:+,})",
                f"- Posts published: {posts_count}",
                f"- Total reach: {total_reach:,}",
                f"- Total impressions: {total_impressions:,}",
                f"- Total engagements: {total_engagements:,}",
                f"- Engagement rate: {engagement_rate:.2f}%",
                f"- Top post reach: {top_post_reach:,}",
                f"- Top post topic: {top_post_topic}",
                "",
            ]
    else:
        lines += ["## Social Media Performance Stats", "", "(No social stats available.)", ""]

    # -- Content ideas -------------------------------------------------------
    content_ideas: list[dict] = data.get("content_ideas", [])
    if content_ideas:
        lines += [
            "## Content Ideas (from CI intelligence pool)",
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
        "- Determine the top-performing platform by engagement rate, not follower count or raw reach.",
        "- Assess engagement trend direction ('up', 'down', or 'flat') based on the combination of follower change and engagement rate context.",
        "- For platform_breakdown, include every platform present in social_stats with a concrete, actionable recommendation grounded in the CI data.",
        "- For content_opportunities, prioritise angles that bridge high-frequency CI signals (pain points, market signals) with the best-fit platform and content format. Reference the specific CI insight source for each opportunity.",
        "- For cross_domain_alerts, explicitly name each pain point or market signal that has no corresponding social content. Include frequency counts. This is the highest-value output — do not skip it.",
        "- recommended_focus must be a single, specific action that would have the greatest impact in the next 7 days based on all available data.",
        "",
        "Output format — return ONLY this JSON object, nothing else:",
        "",
        json.dumps(
            {
                "summary": "2-3 sentence executive summary of social performance across all platforms.",
                "top_performing_platform": "Platform name",
                "engagement_trend": "up | down | flat",
                "platform_breakdown": [
                    {
                        "platform": "Platform name",
                        "engagement_rate": 0.0,
                        "trend": "up | down | flat",
                        "recommendation": "Specific, actionable recommendation grounded in CI data.",
                    }
                ],
                "content_opportunities": [
                    {
                        "platform": "Platform name",
                        "content_type": "e.g. carousel post, reel script, long-form post",
                        "hook_angle": "The specific hook or angle to lead with",
                        "ci_insight_source": "Pain point or market signal this is grounded in, with frequency",
                        "priority": "high | medium | low",
                    }
                ],
                "cross_domain_alerts": [
                    "Pain point 'X' (freq=N) has no corresponding social content across any platform this period."
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

SOCIAL_ANALYSIS_OUTPUT_SCHEMA: dict = {
    "type": "object",
    "description": (
        "Structured social media performance analysis produced by the Social Media "
        "Analyst specialist (CI-MKT-SOC).  Consumed by the Marketing Director to "
        "inform content scheduling and campaign prioritisation."
    ),
    "required": [
        "summary",
        "top_performing_platform",
        "engagement_trend",
        "platform_breakdown",
        "content_opportunities",
        "cross_domain_alerts",
        "recommended_focus",
    ],
    "properties": {
        "summary": {
            "type": "string",
            "description": (
                "2-3 sentence executive summary of overall social media performance "
                "for the analysis period.  Should name the standout platform, the "
                "overall trend direction, and one key cross-domain observation."
            ),
        },
        "top_performing_platform": {
            "type": "string",
            "description": (
                "Name of the platform with the highest engagement rate for the period "
                "(e.g. 'LinkedIn', 'Instagram').  Engagement rate takes precedence over "
                "raw reach or follower count."
            ),
            "example": "LinkedIn",
        },
        "engagement_trend": {
            "type": "string",
            "enum": ["up", "down", "flat"],
            "description": (
                "Overall engagement trend direction across all platforms combined.  "
                "'up' = materially improving, 'down' = materially declining, "
                "'flat' = no significant change."
            ),
        },
        "platform_breakdown": {
            "type": "array",
            "description": (
                "One entry per platform present in the input social_stats.  Each entry "
                "includes the current engagement rate, trend direction, and a concrete "
                "marketing recommendation grounded in the CI data."
            ),
            "items": {
                "type": "object",
                "required": ["platform", "engagement_rate", "trend", "recommendation"],
                "properties": {
                    "platform": {
                        "type": "string",
                        "description": "Platform name (e.g. 'LinkedIn', 'Instagram').",
                    },
                    "engagement_rate": {
                        "type": "number",
                        "description": "Engagement rate as a percentage (e.g. 3.7 for 3.7%).",
                    },
                    "trend": {
                        "type": "string",
                        "enum": ["up", "down", "flat"],
                        "description": "Engagement trend direction for this specific platform.",
                    },
                    "recommendation": {
                        "type": "string",
                        "description": (
                            "Specific, actionable next step for this platform.  Must be "
                            "grounded in CI data (pain points, market signals, or content "
                            "ideas) — not a generic best-practice suggestion."
                        ),
                    },
                },
            },
        },
        "content_opportunities": {
            "type": "array",
            "description": (
                "Prioritised list of content opportunities identified by cross-referencing "
                "social performance gaps with CI intelligence (pain points, market signals, "
                "content ideas).  Each opportunity is grounded in a specific CI data point."
            ),
            "items": {
                "type": "object",
                "required": [
                    "platform",
                    "content_type",
                    "hook_angle",
                    "ci_insight_source",
                    "priority",
                ],
                "properties": {
                    "platform": {
                        "type": "string",
                        "description": "Target platform for this content opportunity.",
                    },
                    "content_type": {
                        "type": "string",
                        "description": (
                            "Format recommendation (e.g. 'carousel post', 'reel script', "
                            "'long-form post', 'story sequence')."
                        ),
                    },
                    "hook_angle": {
                        "type": "string",
                        "description": (
                            "The specific hook or angle to lead with.  Should be compelling "
                            "enough to use verbatim as a headline or opening line."
                        ),
                    },
                    "ci_insight_source": {
                        "type": "string",
                        "description": (
                            "The specific pain point, market signal, or content idea from the "
                            "CI pool that this opportunity is grounded in.  Include frequency "
                            "or score where relevant.  Example: 'Pain point: lead gen overwhelm "
                            "(freq=14)'."
                        ),
                    },
                    "priority": {
                        "type": "string",
                        "enum": ["high", "medium", "low"],
                        "description": (
                            "Priority level based on combination of CI signal strength and "
                            "current content gap size."
                        ),
                    },
                },
            },
        },
        "cross_domain_alerts": {
            "type": "array",
            "description": (
                "Plain-language alerts for high-frequency CI signals (pain points or market "
                "signals) that have no corresponding social content in the current period.  "
                "Each alert should name the specific pain point or signal with its frequency "
                "count.  This is the highest-value output for identifying content revenue gaps."
            ),
            "items": {
                "type": "string",
                "description": (
                    "e.g. \"Pain point 'pricing confidence' (freq=11) has no corresponding "
                    "social content across any platform this period.\""
                ),
            },
        },
        "recommended_focus": {
            "type": "string",
            "description": (
                "A single, specific action that would have the greatest marketing impact in "
                "the next 7 days, based on all available social and CI data.  Should name "
                "a platform, a content type, and the CI insight it should address."
            ),
        },
    },
}

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

__all__ = [
    "SOCIAL_ANALYSIS_SYSTEM_PROMPT_V1",
    "SOCIAL_ANALYSIS_OUTPUT_SCHEMA",
    "build_social_analysis_user_prompt",
    "render_social_analysis_system_prompt",
]
