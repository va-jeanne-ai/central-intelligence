"""
Ad Analysis prompt — v1 (CI-MKT-ADS / M04-2).

Defines the system prompt, user prompt builder, and output schema for the
Ads Performance Analyst operator.  This module is consumed by the Marketing
Director when it needs a structured cross-platform paid advertising performance
analysis with cross-domain CI synthesis.
The Marketing Director pre-loads all enrichment data (ad stats, pain points,
ICP segments, content ideas, wins) before invoking this prompt; the specialist
does NOT query data itself.
"""

from __future__ import annotations

import json

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

AD_ANALYSIS_SYSTEM_PROMPT_V1 = """\
You are **CI-MKT-ADS**, the Ads Performance Analyst specialist of Central Intelligence — an AI-powered business intelligence platform for coaching and consulting businesses — operating in **analysis mode**.

## Role

You sit inside the Marketing department, reporting to the Marketing Director.  Your sole function is to analyse cross-platform paid advertising performance data and surface actionable, revenue-focused intelligence grounded in CI evidence.  You are NOT a chatbot.  You produce structured JSON output only — no prose, no markdown, no commentary outside the JSON envelope.

## Expertise

You combine three disciplines:

1. **Paid advertising diagnostics** — You read ROAS, CTR, CPC, CPM, conversion rate, and spend across Facebook, Instagram, and Google Ads.  You understand which metric diagnoses which layer of the funnel: CTR diagnoses creative and copy relevance (is the audience clicking?); CPC diagnoses audience targeting efficiency (is the right person seeing this ad?); conversion rate diagnoses landing page and offer alignment (does what they land on match what the ad promised?); ROAS diagnoses the campaign's overall commercial viability.  A campaign with great CTR and poor conversion rate is not a copy problem — it is a landing page and offer alignment problem.  You name the mechanism, not just the number.
2. **Campaign health stratification** — You evaluate every campaign against ROAS as the primary commercial signal, not spend or impression volume.  A £200 campaign with a 6.2x ROAS outperforms a £5,000 campaign with 0.8x ROAS.  You classify health as strong (ROAS ≥ 3.0), moderate (ROAS 1.5–2.9), or weak (ROAS < 1.5 or not converting).  You cross-reference campaign type (awareness / consideration / conversion / retargeting) when interpreting ROAS — awareness campaigns that generate zero conversions are not failing by design; conversion campaigns with sub-1.0 ROAS are losing money and require urgent attention.
3. **Cross-domain CI synthesis** — Your most distinctive value is connecting paid ad performance to what the audience is actually expressing on calls and in the CI pool.  Pain points with high frequency counts that appear in no active ad creative are missed revenue opportunities — the audience is telling you what they want to buy but you are not selling it to them in ads.  Client wins and success stories not used as social proof in any active campaign represent untapped conversion signals.  ICP segments whose specific buying triggers are absent from any ad angle indicate a fundamental audience-message mismatch.  You name all of these connections explicitly.

## Data Inputs

The Marketing Director provides all data pre-loaded.  You receive:

- **ad_stats** — Per-platform/campaign paid advertising metrics: platform (Facebook/Instagram/Google Ads), campaign_name, campaign_type (awareness/consideration/conversion/retargeting), spend, impressions, reach, clicks, ctr (%), conversions, conversion_rate (%), roas, cpc, cpm, status (active/paused/ended), date_range.
- **pain_points** — The most frequently expressed client and prospect pain points from the shared CI intelligence pool: text, category, frequency_count.
- **icp_segments** — Validated ICP profiles: segment, description, demographics, pain_summary, buying_triggers, is_primary.
- **content_ideas** — Validated content angles from the CI intelligence pool: content_angle, content_format, idea_score, status, best_platform, hook_opening_line.
- **wins** — Client wins and success stories from the CI pool: text, category, frequency_count.
- **date_range_days** — The number of days covered by the analysis period.

You must use ALL of these inputs together.  An analysis that only reads ad_stats without cross-referencing CI data is incomplete and will be rejected.

## Analysis Mandate

- **Never return raw data verbatim.**  Interpret, synthesise, and draw conclusions.
- **ROAS is the primary signal** for campaign health, not spend, impressions, or click volume.  Classify every active campaign as strong, moderate, or weak using the ROAS thresholds above.  State the ROAS figure in every diagnosis.
- **Diagnose the layer, not just the metric.**  CTR identifies the creative/copy layer; CPC identifies the audience targeting layer; conversion rate identifies the landing page/offer layer.  A campaign with high CTR but low conversion rate has a landing page problem — say so explicitly and name the fix.
- **Top and underperforming campaigns must be named explicitly** — campaign_name, platform, ROAS, and a clear verdict on which specific funnel layer is responsible for performance or failure.
- **Cross-domain alerts are revenue signals.**  For every high-frequency pain point (freq ≥ 5) not addressed in any ad creative, raise an alert naming the exact pain point text and frequency.  For every client win category not used as social proof in any active campaign, raise an alert.  These are direct money-on-the-table observations.
- **ICP alignment is non-negotiable.**  Evaluate whether active ads speak to the primary ICP's named buying triggers.  If ads target generic interests instead of the psychographic profile of the primary segment, name that gap.
- **Campaign type context matters.**  Awareness campaigns at negative ROAS are not automatically failing — they build top-of-funnel volume.  But retargeting and conversion campaigns at negative ROAS are burning budget and must be flagged as urgent.

## Output Contract

You MUST return a single JSON object.  No prose before or after.  No markdown fences.  No explanations.  Only the JSON object.

The object must conform exactly to the output schema described below.  Every field is required.  If a list field has no entries, return an empty array — do not omit the field.

## Example Output

The following illustrates the expected structure and writing quality.  All values are fabricated for illustration only — replace every field with real synthesised content:

```json
{
  "summary": "The retargeting campaign on Facebook is the clear ROAS leader at 4.8x, converting warm audiences efficiently using a specific client outcome story. Google Ads conversion campaigns are burning budget at 0.6x ROAS — the high CTR (3.4%) combined with sub-1% conversion rate indicates a fundamental mismatch between ad promise and landing page delivery. Three of the top five CI pain points have no corresponding ad creative, representing the largest untapped revenue opportunity in the current campaign set.",
  "overall_roas": 2.1,
  "top_performing_campaign": {
    "name": "FB — Client Results Retargeting",
    "platform": "Facebook",
    "roas": 4.8,
    "diagnosis": "Strong ROAS driven by a specific success story (coach from £4k to £18k/month in 90 days) deployed against a warm lookalike audience. The social proof angle eliminates the trust barrier for prospects who have already seen the brand — this is the correct use of retargeting creative."
  },
  "underperforming_campaigns": [
    {
      "name": "Google — Business Coaching Keywords",
      "platform": "Google Ads",
      "roas": 0.6,
      "ctr": 3.4,
      "diagnosis": "High CTR confirms the search intent and ad copy are relevant — people are clicking. The 0.4% conversion rate is a landing page and offer alignment failure. The ad promises 'scale your coaching business' but the landing page leads with a generic brand story rather than a specific outcome tied to the search query. The offer (free 15-minute call) has insufficient perceived value for the cost-per-click paid.",
      "recommendation": "Rewrite the landing page to mirror the specific outcome language in the search ad. Upgrade the CTA from a 15-minute call to a 45-minute business diagnostic — higher perceived value with the same commitment barrier. A/B test a landing page built around the CI pain point 'I don't know how to get consistent clients' (freq=17) against the current brand-story page."
    }
  ],
  "campaign_breakdown": [
    {
      "platform": "Facebook",
      "campaign_name": "FB — Client Results Retargeting",
      "roas": 4.8,
      "ctr": 2.1,
      "conversion_rate": 4.3,
      "health": "strong",
      "diagnosis": "Social proof creative against warm audience is converting above benchmark. All three funnel layers (creative relevance, targeting efficiency, landing page alignment) are working in concert.",
      "recommendation": "Scale budget by 30% and test a second social proof creative using a different win category (revenue growth rather than client acquisition) to identify which outcome resonates most with the retargeting audience."
    },
    {
      "platform": "Google Ads",
      "campaign_name": "Google — Business Coaching Keywords",
      "roas": 0.6,
      "ctr": 3.4,
      "conversion_rate": 0.4,
      "health": "weak",
      "diagnosis": "Creative and targeting layers are functioning — CTR is healthy. Landing page alignment is the failure point. The ad-to-landing-page message match is broken.",
      "recommendation": "Pause until landing page is rebuilt to mirror ad messaging. Prioritise page rebuild using the top CI pain point angle before resuming spend."
    }
  ],
  "cross_domain_alerts": [
    "Pain point 'I don't know how to price my services confidently' (freq=13) has no corresponding ad creative across any active campaign.",
    "Pain point 'I'm fully booked but not profitable' (freq=11) has no corresponding ad creative — this is a high-conversion retargeting angle for warm audiences.",
    "Client win category 'Revenue doubled within 6 months' (freq=8) is not used as social proof in any active ad — this is the highest-converting proof category available and should be the next retargeting creative tested."
  ],
  "audience_fit_assessment": "Active ads are targeting broad interest categories (business, entrepreneurship, self-improvement) rather than the psychographic profile of the primary ICP (established coaches, 3-7 years in, revenue plateau, seeking scalable systems). No campaign copy addresses the primary ICP's named buying trigger of 'proof that the method works for someone at my stage'. The retargeting campaign is the only one implicitly reaching this segment — all other campaigns are speaking to a generic entrepreneur audience.",
  "recommended_focus": "Pause the Google Ads conversion campaign immediately to stop ROAS-negative spend, and use the saved budget to launch a Facebook conversion campaign targeting the primary ICP with a pain-agitation creative built around 'fully booked but not profitable' (freq=11) — the highest-frequency unaddressed pain point in the CI pool."
}
```\
"""

# ---------------------------------------------------------------------------
# User prompt builder
# ---------------------------------------------------------------------------


def build_ad_analysis_user_prompt(data: dict) -> str:  # noqa: PLR0912
    """Format pre-loaded Marketing Director enrichment data into the ad analysis prompt.

    Parameters
    ----------
    data:
        A dict with keys: ``ad_stats``, ``pain_points``, ``icp_segments``,
        ``content_ideas``, ``wins``, ``date_range_days``.

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

    # -- Ad stats ------------------------------------------------------------
    ad_stats: list[dict] = data.get("ad_stats", [])
    if ad_stats:
        lines += [
            "## Ad Campaign Performance Stats (sorted by ROAS, highest first)",
            "",
        ]
        sorted_stats = sorted(
            ad_stats, key=lambda a: a.get("roas", 0.0), reverse=True
        )
        for stat in sorted_stats:
            platform = stat.get("platform") or "Unknown"
            campaign_name = stat.get("campaign_name") or "Unnamed Campaign"
            campaign_type = stat.get("campaign_type") or "unknown"
            spend = stat.get("spend", 0.0)
            impressions = stat.get("impressions", 0)
            reach = stat.get("reach", 0)
            clicks = stat.get("clicks", 0)
            ctr = stat.get("ctr", 0.0)
            conversions = stat.get("conversions", 0)
            conversion_rate = stat.get("conversion_rate", 0.0)
            roas = stat.get("roas", 0.0)
            cpc = stat.get("cpc", 0.0)
            cpm = stat.get("cpm", 0.0)
            status = stat.get("status") or "unknown"
            date_range_label = stat.get("date_range") or ""

            date_str = f" ({date_range_label})" if date_range_label else ""
            lines += [
                f"### {campaign_name} — {platform}{date_str}",
                f"- Campaign type: {campaign_type}",
                f"- Status: {status}",
                f"- Spend: £{spend:,.2f}",
                f"- Impressions: {impressions:,}",
                f"- Reach: {reach:,}",
                f"- Clicks: {clicks:,}",
                f"- CTR: {ctr:.2f}%",
                f"- Conversions: {conversions}",
                f"- Conversion rate: {conversion_rate:.2f}%",
                f"- ROAS: {roas:.2f}x",
                f"- CPC: £{cpc:.2f}",
                f"- CPM: £{cpm:.2f}",
                "",
            ]
    else:
        lines += ["## Ad Campaign Performance Stats", "", "(No ad stats available.)", ""]

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
        "- summary must name the top-performing campaign by ROAS, identify the most critical underperformer, and state at least one cross-domain CI observation in 2-3 sentences.",
        "- overall_roas is the blended ROAS across all active campaigns — calculate it as total conversions value divided by total spend, or estimate from the available ROAS and spend figures.",
        "- top_performing_campaign must be identified by ROAS (not spend or impressions). Include campaign name, platform, ROAS, and a specific diagnosis of WHY it is performing well — which creative strategy, audience, or offer alignment is driving results.",
        "- underperforming_campaigns are any active campaigns with ROAS < 1.5. For each, name the specific funnel layer that is failing (creative/copy, audience targeting, landing page/offer alignment) and provide a concrete, CI-grounded recommendation.",
        "- campaign_breakdown includes every campaign present in ad_stats. Assign health: strong (ROAS ≥ 3.0), moderate (ROAS 1.5–2.9), weak (ROAS < 1.5). The diagnosis must name the specific layer and mechanism. Recommendations must reference CI data.",
        "- cross_domain_alerts must name every high-frequency pain point (freq ≥ 5) with no corresponding ad creative, and every win category not used as social proof in any active campaign. Include exact text and frequency counts. This is the highest-value output — do not skip it.",
        "- audience_fit_assessment evaluates how well the targeting of active campaigns maps to the primary ICP's psychographic profile and buying triggers. Be specific — name the gaps, not a generic observation.",
        "- recommended_focus is the single highest-impact action for the next 7 days, grounded in the data. It must name a campaign type, platform, creative angle, and the CI data point supporting it.",
        "",
        "Output format — return ONLY this JSON object, nothing else:",
        "",
        json.dumps(
            {
                "summary": "2-3 sentence executive summary naming the top ROAS campaign, the most critical underperformer, and one CI cross-domain observation.",
                "overall_roas": 0.0,
                "top_performing_campaign": {
                    "name": "Campaign name",
                    "platform": "Platform name",
                    "roas": 0.0,
                    "diagnosis": "Why this campaign is performing well — specific creative, audience, or offer alignment reason.",
                },
                "underperforming_campaigns": [
                    {
                        "name": "Campaign name",
                        "platform": "Platform name",
                        "roas": 0.0,
                        "ctr": 0.0,
                        "diagnosis": "Which funnel layer is failing and the mechanism behind it.",
                        "recommendation": "Specific, CI-grounded corrective action.",
                    }
                ],
                "campaign_breakdown": [
                    {
                        "platform": "Platform name",
                        "campaign_name": "Campaign name",
                        "roas": 0.0,
                        "ctr": 0.0,
                        "conversion_rate": 0.0,
                        "health": "strong | moderate | weak",
                        "diagnosis": "Which layers are working or failing and why.",
                        "recommendation": "Specific next step grounded in CI data.",
                    }
                ],
                "cross_domain_alerts": [
                    "Pain point or win with frequency count that has no corresponding ad creative."
                ],
                "audience_fit_assessment": "How well active ad targeting aligns with the primary ICP's psychographic profile and buying triggers.",
                "recommended_focus": "Single highest-impact action for the next 7 days, naming platform, creative angle, and supporting CI data point.",
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

AD_ANALYSIS_OUTPUT_SCHEMA: dict = {
    "type": "object",
    "description": (
        "Structured paid advertising performance analysis produced by the Ads "
        "Performance Analyst specialist (CI-MKT-ADS) in analysis mode.  Consumed "
        "by the Marketing Director to inform budget allocation, creative strategy, "
        "and campaign optimisation prioritisation."
    ),
    "required": [
        "summary",
        "overall_roas",
        "top_performing_campaign",
        "underperforming_campaigns",
        "campaign_breakdown",
        "cross_domain_alerts",
        "audience_fit_assessment",
        "recommended_focus",
    ],
    "properties": {
        "summary": {
            "type": "string",
            "description": (
                "2-3 sentence executive summary of overall paid advertising performance "
                "for the analysis period.  Must name the top-performing campaign by ROAS, "
                "identify the most critical underperformer, and include at least one "
                "cross-domain CI observation connecting ad behaviour to audience intelligence."
            ),
        },
        "overall_roas": {
            "type": "number",
            "description": (
                "Blended ROAS across all active campaigns for the analysis period.  "
                "Calculated as total attributed revenue divided by total spend.  "
                "If raw revenue figures are not available, estimated from the weighted "
                "average of individual campaign ROAS figures weighted by spend."
            ),
            "example": 2.1,
        },
        "top_performing_campaign": {
            "type": "object",
            "description": (
                "The single campaign with the highest ROAS for the period.  Includes "
                "the campaign name, platform, ROAS, and a specific diagnosis of the "
                "creative, audience, or offer strategy driving strong performance."
            ),
            "required": ["name", "platform", "roas", "diagnosis"],
            "properties": {
                "name": {
                    "type": "string",
                    "description": "The campaign name exactly as it appears in the ad stats.",
                },
                "platform": {
                    "type": "string",
                    "description": "The platform this campaign runs on (Facebook, Instagram, Google Ads).",
                },
                "roas": {
                    "type": "number",
                    "description": "Return on ad spend as a multiplier (e.g. 4.8 means £4.80 returned per £1 spent).",
                    "example": 4.8,
                },
                "diagnosis": {
                    "type": "string",
                    "description": (
                        "Specific explanation of why this campaign is performing well.  "
                        "Must reference the creative angle, audience targeting approach, "
                        "or offer-landing page alignment that is driving the strong ROAS.  "
                        "Cross-reference CI data where applicable."
                    ),
                },
            },
        },
        "underperforming_campaigns": {
            "type": "array",
            "description": (
                "All active campaigns with ROAS < 1.5.  Each entry names the specific "
                "funnel layer that is failing and provides a concrete, CI-grounded "
                "recommendation.  Empty array if all active campaigns are above the "
                "moderate threshold."
            ),
            "items": {
                "type": "object",
                "required": ["name", "platform", "roas", "ctr", "diagnosis", "recommendation"],
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Campaign name.",
                    },
                    "platform": {
                        "type": "string",
                        "description": "Platform (Facebook, Instagram, Google Ads).",
                    },
                    "roas": {
                        "type": "number",
                        "description": "ROAS for this campaign.",
                    },
                    "ctr": {
                        "type": "number",
                        "description": "Click-through rate as a percentage.",
                    },
                    "diagnosis": {
                        "type": "string",
                        "description": (
                            "Names the specific funnel layer failing: creative/copy "
                            "(low CTR), audience targeting (high CPM, low reach efficiency), "
                            "or landing page/offer (high CTR, low conversion rate).  "
                            "Explains the mechanism — not just the metric."
                        ),
                    },
                    "recommendation": {
                        "type": "string",
                        "description": (
                            "Specific, actionable corrective step grounded in CI data.  "
                            "Must name the change to make and the CI data point supporting it."
                        ),
                    },
                },
            },
        },
        "campaign_breakdown": {
            "type": "array",
            "description": (
                "One entry per campaign present in ad_stats.  Each entry includes "
                "key performance metrics, a health classification, a layer-level "
                "diagnosis, and a CI-grounded recommendation."
            ),
            "items": {
                "type": "object",
                "required": [
                    "platform",
                    "campaign_name",
                    "roas",
                    "ctr",
                    "conversion_rate",
                    "health",
                    "diagnosis",
                    "recommendation",
                ],
                "properties": {
                    "platform": {"type": "string", "description": "Platform name."},
                    "campaign_name": {"type": "string", "description": "Campaign name."},
                    "roas": {
                        "type": "number",
                        "description": "ROAS as a multiplier.",
                    },
                    "ctr": {
                        "type": "number",
                        "description": "Click-through rate as a percentage.",
                    },
                    "conversion_rate": {
                        "type": "number",
                        "description": "Conversion rate as a percentage.",
                    },
                    "health": {
                        "type": "string",
                        "enum": ["strong", "moderate", "weak"],
                        "description": (
                            "Health classification: strong = ROAS ≥ 3.0; "
                            "moderate = ROAS 1.5–2.9; weak = ROAS < 1.5."
                        ),
                    },
                    "diagnosis": {
                        "type": "string",
                        "description": (
                            "Identifies which funnel layers are working or failing "
                            "and explains the mechanism behind the performance pattern.  "
                            "Must name specific CTR, CPC, or conversion rate observations "
                            "and connect them to a specific layer."
                        ),
                    },
                    "recommendation": {
                        "type": "string",
                        "description": (
                            "Specific, actionable next step grounded in CI data (pain points, "
                            "wins, ICP insights, or content ideas).  Not a generic best practice."
                        ),
                    },
                },
            },
        },
        "cross_domain_alerts": {
            "type": "array",
            "description": (
                "Plain-language alerts for high-frequency CI pain points (freq ≥ 5) "
                "with no corresponding ad creative, and for client win categories not "
                "deployed as social proof in any active campaign.  Each alert must name "
                "the exact pain point or win with its frequency count.  This is the "
                "highest-value output for identifying paid advertising revenue gaps — "
                "do not return an empty array without genuinely checking all CI inputs."
            ),
            "items": {
                "type": "string",
                "description": (
                    "e.g. \"Pain point 'I don't know how to price my services confidently' "
                    "(freq=13) has no corresponding ad creative across any active campaign.\""
                ),
            },
        },
        "audience_fit_assessment": {
            "type": "string",
            "description": (
                "A specific assessment of how well the targeting of active campaigns "
                "maps to the primary ICP's psychographic profile and buying triggers.  "
                "Must name specific gaps (e.g. targeting broad interest categories rather "
                "than ICP-specific psychographics) and reference the primary ICP's buying "
                "triggers from the ICP data.  Not a generic observation."
            ),
        },
        "recommended_focus": {
            "type": "string",
            "description": (
                "The single highest-impact action for the next 7 days based on all "
                "available ad and CI data.  Must name a specific campaign action "
                "(pause, scale, create), the platform, the creative angle to test or "
                "the budget reallocation to make, and the CI data point supporting the "
                "recommendation.  Maximum two sentences."
            ),
        },
    },
}

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

__all__ = [
    "AD_ANALYSIS_SYSTEM_PROMPT_V1",
    "AD_ANALYSIS_OUTPUT_SCHEMA",
    "build_ad_analysis_user_prompt",
]
