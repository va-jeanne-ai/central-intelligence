"""
Funnel Analysis prompt — v1 (CI-MKT-FUN / M03-2).

Defines the system prompt, user prompt builder, and output schema for the
Funnels Analyst specialist.  This module is consumed by the Marketing
Director when it needs a structured funnel performance analysis with
cross-domain CI synthesis.
The Marketing Director pre-loads all enrichment data (funnel stage counts,
lead sources, pain points, ICP segments, market signals) before invoking
this prompt; the specialist does NOT query data itself.
"""

from __future__ import annotations

import json

from app.prompts.context import DEFAULT_PROFILE, PromptProfile, render

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

_FUNNEL_ANALYSIS_SYSTEM_PROMPT_TEMPLATE_V1 = """\
You are **CI-MKT-FUN**, the Funnels Analyst specialist of {{app_name}} — an AI-powered business intelligence platform for {{vertical}} businesses.

## Role

You sit inside the Marketing department, reporting to the Marketing Director.  Your sole function is to analyse sales funnel performance data and surface the bottlenecks, conversion failures, and CI-grounded explanations that drive pipeline outcomes.  You are NOT a chatbot.  You produce structured JSON output only — no prose, no markdown, no commentary outside the JSON envelope.

## Expertise

You combine three disciplines:

1. **Funnel metrics analysis** — You read stage-by-stage conversion rates and identify where momentum breaks down.  You distinguish between a top-of-funnel volume problem (not enough leads entering) and a mid-funnel friction problem (leads entering but not progressing).  You never report numbers in isolation — every metric is interpreted in the context of what it means for pipeline health and revenue.
2. **Conversion psychology** — You understand that conversion failures are rarely random.  A low leads-to-appointments rate signals a messaging or targeting problem.  A low appointments-to-applications rate signals a discovery call quality or trust problem.  A low applications-to-sales rate signals an offer clarity or objection-handling problem.  You name the psychological and behavioural mechanism behind each drop-off, not just the percentage.
3. **Cross-domain CI synthesis** — Your greatest value is connecting funnel drop-off patterns to what prospects are actually saying.  CI data — pain points, market signals, and ICP profiles — explain WHY leads stall or disengage.  A high appointment-no-show rate combined with a high-frequency pain point around time and overwhelm is not a coincidence.  You make these connections explicit and actionable.

## Data Inputs

The Marketing Director provides all data pre-loaded.  You receive:

- **funnel_stages** — Stage-by-stage counts and conversion rates for the analysis period: count at each stage, conversion rate from the previous stage, and conversion rate from the top of funnel (leads).
- **lead_sources** — Breakdown of pipeline by acquisition source: lead count, appointment count, sale count, and overall conversion rate per source.
- **pain_points** — The most frequently expressed client and prospect pain points from the shared intelligence pool, with category tags and frequency counts.
- **icp_segments** — Validated ICP profiles for the business, flagging the primary segment.
- **market_signals** — Trending signals and themes extracted from call transcripts, sorted by recency and mention volume.

You must use ALL of these inputs together.  An analysis that only reads funnel_stages without cross-referencing CI data is incomplete and will be rejected.

## Analysis Mandate

- **Never return raw data verbatim.**  Interpret, synthesise, and draw conclusions.
- **Name the bottleneck, not just the number.**  The critical bottleneck is the single stage with the worst conversion drop-off relative to what a healthy coaching funnel should achieve.  State which stage it is and why it is failing in behavioural or messaging terms.
- **Drop-off severity must be assessed in context.**  A 40% leads-to-appointments conversion is strong; a 40% appointments-to-sales conversion may be catastrophic depending on the business model.  Apply coaching-industry benchmarks when assessing severity.
- **Cross-reference CI data to explain funnel behaviour.**  Pain points that surface frequently in calls are conversion obstacles.  Market signals reveal what prospects are prioritising.  ICP profiles reveal whether the funnel is attracting the right audience.  Connect these explicitly to the stage-level data.
- **Lead source quality matters more than lead source volume.**  A source producing 200 leads at 0.5% overall conversion is worse than a source producing 20 leads at 8% conversion.  Rank sources by conversion rate, not volume.
- **ICP alignment is a diagnostic lens.**  If the funnel is underperforming, consider whether the lead mix matches the primary ICP profile.  A mismatch between who is entering the funnel and who the business is built to serve is a root cause, not a symptom.

## Output Contract

You MUST return a single JSON object.  No prose before or after.  No markdown fences.  No explanations.  Only the JSON object.

The object must conform exactly to the output schema described below.  Every field is required.  If a list field has no entries, return an empty array — do not omit the field.

## Example Output

The following illustrates the expected structure and writing quality.  All values are fabricated for illustration only — replace every field with real synthesised content:

```json
{
  "summary": "The funnel is generating adequate lead volume but is haemorrhaging opportunity at the appointments-to-applications stage, where only 31% of booked calls result in an application — well below the 55-65% benchmark for a high-ticket coaching offer. The lead-to-sale conversion rate of 3.1% is recoverable, but only by addressing the discovery call experience and the objection patterns surfaced in CI data. Organic search is the highest-quality source by conversion rate and warrants immediate investment.",
  "overall_conversion_rate": 3.1,
  "critical_bottleneck": "appointments_to_applications",
  "stage_analysis": [
    {
      "stage": "leads",
      "count": 320,
      "conversion_from_prev": null,
      "drop_off_severity": "low",
      "diagnosis": "Lead volume is healthy for the period. The mix of sources skews toward paid social, which historically produces higher volume but lower intent than organic or referral sources. No volume problem at this stage.",
      "recommendation": "Maintain current lead volume but audit targeting parameters on paid social to shift the mix toward higher-intent prospects who more closely match the primary ICP profile."
    },
    {
      "stage": "appointments",
      "count": 198,
      "conversion_from_prev": 61.9,
      "drop_off_severity": "medium",
      "diagnosis": "A 62% leads-to-appointments rate is within acceptable range, but 38% of leads are not booking. Given that the top CI pain point is 'I don't have time to add anything new right now', the barrier is likely a perceived time commitment on the call itself, not lack of interest.",
      "recommendation": "Reframe the call booking copy to emphasise the call as a diagnostic rather than a sales conversation. Reduce friction by shortening the pre-call questionnaire and adding a 'what to expect' sequence post-booking."
    },
    {
      "stage": "applications",
      "count": 61,
      "conversion_from_prev": 30.8,
      "drop_off_severity": "critical",
      "diagnosis": "This is the primary revenue leak. Only 31% of booked calls result in an application — indicating the discovery call is failing to create enough certainty or urgency for prospects to take the next step. The CI pain point 'I've tried programmes before and they didn't work' (freq=17) suggests trust and proof are the missing elements, not desire.",
      "recommendation": "Restructure the discovery call framework to lead with a diagnosis of the prospect's specific situation before presenting the offer. Add 3-5 client outcome stories to the pre-call nurture sequence that directly address the 'I've tried before and it didn't work' objection."
    },
    {
      "stage": "sales",
      "count": 10,
      "conversion_from_prev": 16.4,
      "drop_off_severity": "high",
      "diagnosis": "A 16% applications-to-sales close rate suggests the application step is not qualifying intent effectively, or the sales conversation is encountering unresolved objections around price and ROI certainty. Market signal 'pricing confidence' (7-day mentions: 8) confirms this is an active friction point.",
      "recommendation": "Introduce a short pre-sales video sent between application and sales call that pre-handles the top 3 objections. Revise the application form to include a question about investment readiness to qualify out low-intent applicants earlier."
    }
  ],
  "source_analysis": [
    {
      "source": "Organic Search",
      "lead_count": 44,
      "conversion_rate": 7.3,
      "assessment": "Highest-converting source by a significant margin. Organic leads arrive with pre-existing trust and problem awareness, making them far better matched to the offer than cold paid traffic.",
      "recommendation": "Prioritise SEO content investment. Produce at least two long-form articles per month targeting the top CI pain points — these will compound over time and reduce paid acquisition dependency."
    },
    {
      "source": "Paid Social",
      "lead_count": 189,
      "conversion_rate": 1.6,
      "assessment": "Highest volume but lowest conversion rate. Paid social is attracting leads who have not yet reached the pain-awareness or solution-awareness stage required to convert in a high-ticket funnel.",
      "recommendation": "Shift paid social creative strategy from offer-led ads (which attract low-intent clicks) to content-led ads that address the primary ICP's top pain points and warm leads before they enter the funnel."
    }
  ],
  "cross_domain_insights": [
    "Pain point 'I don't have time to add anything new right now' (freq=23) directly explains the 38% leads-to-appointments drop-off — perceived time commitment is the barrier, not interest.",
    "Pain point 'I've tried programmes before and they didn't work' (freq=17) maps precisely to the appointments-to-applications bottleneck — trust and proof deficits are preventing application commitment.",
    "Market signal 'pricing confidence' (7-day mentions: 8) aligns with the low applications-to-sales close rate — price objections are not being resolved before the sales conversation.",
    "Primary ICP segment (established solopreneurs, 3-7 years in business) has 'ROI certainty' as a primary buying trigger — the current sales process does not emphasise measurable outcomes, creating a misalignment with what this segment needs to make a decision."
  ],
  "optimization_priorities": [
    {
      "priority": 1,
      "stage": "appointments_to_applications",
      "action": "Restructure the discovery call framework to lead with a personalised diagnostic and add outcome-proof stories to the pre-call nurture sequence.",
      "expected_impact": "Improving the appointments-to-applications rate from 31% to 50% would add approximately 12 additional applications per period without changing lead volume.",
      "ci_grounding": "Directly addresses the 'I've tried before and it didn't work' objection (freq=17) — the highest-frequency unresolved trust barrier in the CI pool."
    },
    {
      "priority": 2,
      "stage": "applications_to_sales",
      "action": "Send a pre-sales objection-handling video between application and sales call, and revise application form to qualify investment readiness.",
      "expected_impact": "Improving close rate from 16% to 25% would deliver 4-5 additional sales per period from current application volume.",
      "ci_grounding": "Responds directly to the 'pricing confidence' market signal (7-day mentions: 8) and aligns the sales conversation with the primary ICP's ROI certainty buying trigger."
    },
    {
      "priority": 3,
      "stage": "leads_to_appointments",
      "action": "Reframe call booking copy and reduce pre-call friction to convert more time-constrained leads.",
      "expected_impact": "Increasing leads-to-appointments rate from 62% to 72% would add approximately 32 additional appointments per period.",
      "ci_grounding": "Directly addresses 'I don't have time' pain point (freq=23) — the most frequently cited barrier to engagement in the CI pool."
    }
  ],
  "recommended_action": "Restructure the discovery call framework this week: introduce a personalised diagnostic opening, and send 3 client outcome stories in the pre-call sequence that directly address 'I've tried programmes before and they didn't work' — this single change targets the critical bottleneck responsible for the majority of lost revenue in the current funnel."
}
```\
"""



def render_funnel_analysis_system_prompt(profile: PromptProfile | None = None) -> str:
    """Render the funnel analysis system prompt for a specific instance profile."""
    return render(_FUNNEL_ANALYSIS_SYSTEM_PROMPT_TEMPLATE_V1, profile)


# Rendered with the frozen defaults (the pre-Phase-1 literals) so importers and
# the parity snapshot see stable text regardless of process state.
FUNNEL_ANALYSIS_SYSTEM_PROMPT_V1 = render_funnel_analysis_system_prompt(DEFAULT_PROFILE)

# ---------------------------------------------------------------------------
# User prompt builder
# ---------------------------------------------------------------------------


def build_funnel_analysis_user_prompt(data: dict) -> str:  # noqa: PLR0912
    """Format pre-loaded Marketing Director enrichment data into the funnel analysis prompt.

    Parameters
    ----------
    data:
        A dict with keys: ``funnel_stages``, ``lead_sources``, ``pain_points``,
        ``icp_segments``, ``market_signals``, ``date_range_days``.

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

    # -- Funnel stages -------------------------------------------------------
    funnel_stages: list[dict] = data.get("funnel_stages", [])
    if funnel_stages:
        lines += [
            "## Funnel Stage Performance (sorted by conversion from previous stage, ascending)",
            "",
        ]
        # Sort ascending by conversion_rate_from_prev to surface bottlenecks first.
        # Stages with no previous stage (leads) have None — push them to the front.
        sorted_stages = sorted(
            funnel_stages,
            key=lambda s: (
                s.get("conversion_rate_from_prev") is not None,
                s.get("conversion_rate_from_prev") or 0.0,
            ),
        )
        for stage in sorted_stages:
            stage_name = stage.get("stage") or "Unknown"
            count = stage.get("count", 0)
            conv_prev = stage.get("conversion_rate_from_prev")
            conv_top = stage.get("conversion_rate_from_top")
            conv_prev_str = f"{conv_prev:.1f}%" if conv_prev is not None else "N/A (top of funnel)"
            conv_top_str = f"{conv_top:.1f}%" if conv_top is not None else "N/A"
            lines += [
                f"### {stage_name}",
                f"- Count: {count:,}",
                f"- Conversion from previous stage: {conv_prev_str}",
                f"- Conversion from top of funnel (leads): {conv_top_str}",
                "",
            ]
    else:
        lines += ["## Funnel Stage Performance", "", "(No funnel stage data available.)", ""]

    # -- Lead sources --------------------------------------------------------
    lead_sources: list[dict] = data.get("lead_sources", [])
    if lead_sources:
        lines += [
            "## Lead Sources (sorted by conversion rate, ascending — lowest quality first)",
            "",
        ]
        sorted_sources = sorted(
            lead_sources, key=lambda s: s.get("conversion_rate", 0.0)
        )
        for i, source in enumerate(sorted_sources, start=1):
            source_name = source.get("source") or "Unknown"
            lead_count = source.get("lead_count", 0)
            appt_count = source.get("appointment_count", 0)
            sale_count = source.get("sale_count", 0)
            conv_rate = source.get("conversion_rate", 0.0)
            lines += [
                f"{i}. **{source_name}**",
                f"   - Leads: {lead_count:,}",
                f"   - Appointments: {appt_count:,}",
                f"   - Sales: {sale_count:,}",
                f"   - Overall conversion rate (leads → sales): {conv_rate:.1f}%",
                "",
            ]
    else:
        lines += ["## Lead Sources", "", "(No lead source data available.)", ""]

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

    # -- Output instructions -------------------------------------------------
    lines += [
        "---",
        "",
        "## Your Task",
        "",
        "Using all of the intelligence above, produce a single JSON object conforming to the output schema.",
        "",
        "Analysis requirements:",
        "- Calculate overall_conversion_rate as the percentage of total leads that reached the sales stage.",
        "- Identify critical_bottleneck as the stage name with the single worst conversion drop-off relative to coaching-industry benchmarks — state the stage identifier string (e.g. 'appointments_to_applications'), not a display label.",
        "- For stage_analysis, include every stage present in funnel_stages. Assign drop_off_severity using coaching-industry context: 'critical' = far below benchmark and largest revenue impact, 'high' = below benchmark, 'medium' = borderline, 'low' = healthy. The diagnosis must name a behavioural or psychological mechanism, not just restate the number. The recommendation must be concrete and actionable.",
        "- For source_analysis, include every source present in lead_sources. Rank by conversion rate — call out the highest-quality source explicitly and explain why it outperforms. Flag low-quality high-volume sources as pipeline diluters.",
        "- For cross_domain_insights, explicitly connect CI data (pain points, market signals, ICP profiles) to specific funnel drop-off patterns. Name the exact pain point or signal text with its frequency count. This is the highest-value output — minimum 3 insights required.",
        "- For optimization_priorities, rank actions 1 through N by revenue impact. Each action must be grounded in a specific CI data point (ci_grounding) and include a quantified expected_impact where possible.",
        "- recommended_action must be a single, specific action for the next 7 days that targets the critical bottleneck, names the CI insight that supports it, and is concrete enough to execute without further clarification.",
        "",
        "Output format — return ONLY this JSON object, nothing else:",
        "",
        json.dumps(
            {
                "summary": "2-3 sentence executive summary naming the critical bottleneck, the overall conversion rate, and one cross-domain CI observation.",
                "overall_conversion_rate": 0.0,
                "critical_bottleneck": "stage identifier string, e.g. appointments_to_applications",
                "stage_analysis": [
                    {
                        "stage": "Stage name",
                        "count": 0,
                        "conversion_from_prev": 0.0,
                        "drop_off_severity": "critical | high | medium | low",
                        "diagnosis": "Behavioural or psychological explanation for performance at this stage.",
                        "recommendation": "Specific, actionable next step grounded in CI data.",
                    }
                ],
                "source_analysis": [
                    {
                        "source": "Source name",
                        "lead_count": 0,
                        "conversion_rate": 0.0,
                        "assessment": "Quality and intent assessment of this source relative to others.",
                        "recommendation": "Specific action to improve or leverage this source.",
                    }
                ],
                "cross_domain_insights": [
                    "CI signal (pain point or market signal with frequency) that explains a specific funnel behaviour."
                ],
                "optimization_priorities": [
                    {
                        "priority": 1,
                        "stage": "Stage this action targets",
                        "action": "Specific action to take.",
                        "expected_impact": "Quantified or directional impact on conversion or revenue.",
                        "ci_grounding": "The specific CI data point (pain point, signal, ICP insight) that supports this action.",
                    }
                ],
                "recommended_action": "Single most impactful action for the next 7 days, naming the bottleneck stage and the CI insight that drives it.",
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

FUNNEL_ANALYSIS_OUTPUT_SCHEMA: dict = {
    "type": "object",
    "description": (
        "Structured funnel performance analysis produced by the Funnels Analyst "
        "specialist (CI-MKT-FUN).  Consumed by the Marketing Director to identify "
        "conversion bottlenecks and prioritise pipeline optimisation actions."
    ),
    "required": [
        "summary",
        "overall_conversion_rate",
        "critical_bottleneck",
        "stage_analysis",
        "source_analysis",
        "cross_domain_insights",
        "optimization_priorities",
        "recommended_action",
    ],
    "properties": {
        "summary": {
            "type": "string",
            "description": (
                "2-3 sentence executive summary of overall funnel performance for the "
                "analysis period.  Must name the critical bottleneck stage, state the "
                "overall leads-to-sales conversion rate, and include at least one "
                "cross-domain CI observation that explains funnel behaviour."
            ),
        },
        "overall_conversion_rate": {
            "type": "number",
            "description": (
                "The percentage of leads that reached the sales (closed) stage.  "
                "Calculated as (sales count / leads count) * 100.  "
                "Expressed as a float, e.g. 3.1 for 3.1%."
            ),
            "example": 3.1,
        },
        "critical_bottleneck": {
            "type": "string",
            "description": (
                "The single stage transition with the worst conversion drop-off relative "
                "to coaching-industry benchmarks.  Expressed as a stage identifier "
                "string describing the transition, e.g. 'appointments_to_applications'. "
                "This is the primary lever for revenue improvement."
            ),
            "example": "appointments_to_applications",
        },
        "stage_analysis": {
            "type": "array",
            "description": (
                "One entry per funnel stage present in the input data.  Each entry "
                "diagnoses performance at that stage in behavioural terms and provides "
                "a concrete, CI-grounded recommendation."
            ),
            "items": {
                "type": "object",
                "required": [
                    "stage",
                    "count",
                    "conversion_from_prev",
                    "drop_off_severity",
                    "diagnosis",
                    "recommendation",
                ],
                "properties": {
                    "stage": {
                        "type": "string",
                        "description": "Stage name (e.g. 'leads', 'appointments', 'applications', 'sales').",
                    },
                    "count": {
                        "type": "integer",
                        "description": "Number of prospects at this stage for the analysis period.",
                    },
                    "conversion_from_prev": {
                        "type": ["number", "null"],
                        "description": (
                            "Conversion rate from the previous stage as a percentage.  "
                            "Null for the top-of-funnel stage (leads) which has no prior stage."
                        ),
                    },
                    "drop_off_severity": {
                        "type": "string",
                        "enum": ["critical", "high", "medium", "low"],
                        "description": (
                            "Severity of the drop-off at this stage relative to coaching-industry "
                            "benchmarks.  'critical' = far below benchmark and greatest revenue "
                            "impact; 'high' = below benchmark; 'medium' = borderline; "
                            "'low' = healthy or above benchmark."
                        ),
                    },
                    "diagnosis": {
                        "type": "string",
                        "description": (
                            "Behavioural or psychological explanation for why this stage is "
                            "performing as it is.  Must go beyond restating the number — name "
                            "the mechanism (e.g. trust deficit, perceived time cost, offer "
                            "clarity failure).  Cross-reference CI data where applicable."
                        ),
                    },
                    "recommendation": {
                        "type": "string",
                        "description": (
                            "Specific, actionable next step to improve conversion at this stage.  "
                            "Must be grounded in CI data (pain points, market signals, or ICP "
                            "insights) — not a generic best-practice suggestion."
                        ),
                    },
                },
            },
        },
        "source_analysis": {
            "type": "array",
            "description": (
                "One entry per lead source present in the input data.  Sources are "
                "assessed by conversion quality (leads-to-sales rate), not volume.  "
                "High-volume low-conversion sources are identified as pipeline diluters."
            ),
            "items": {
                "type": "object",
                "required": [
                    "source",
                    "lead_count",
                    "conversion_rate",
                    "assessment",
                    "recommendation",
                ],
                "properties": {
                    "source": {
                        "type": "string",
                        "description": "Lead source name (e.g. 'Organic Search', 'Paid Social', 'Referral').",
                    },
                    "lead_count": {
                        "type": "integer",
                        "description": "Number of leads generated by this source for the analysis period.",
                    },
                    "conversion_rate": {
                        "type": "number",
                        "description": (
                            "Overall conversion rate for this source (leads → sales) as a "
                            "percentage.  e.g. 7.3 for 7.3%."
                        ),
                    },
                    "assessment": {
                        "type": "string",
                        "description": (
                            "Quality and intent assessment of this source relative to others.  "
                            "Should explain why this source converts at its rate — audience "
                            "intent, awareness level, ICP match, etc."
                        ),
                    },
                    "recommendation": {
                        "type": "string",
                        "description": (
                            "Specific action to improve, scale, or rebalance investment in this "
                            "source.  High-converting sources should be scaled; low-converting "
                            "high-volume sources should have their strategy revised."
                        ),
                    },
                },
            },
        },
        "cross_domain_insights": {
            "type": "array",
            "description": (
                "Plain-language insights connecting CI data (pain points, market signals, "
                "ICP profiles) to specific funnel conversion behaviours.  Each insight must "
                "name the exact CI signal with its frequency count and link it explicitly "
                "to a stage-level observation.  Minimum 3 insights required.  This is the "
                "highest-value output for explaining WHY the funnel behaves as it does."
            ),
            "items": {
                "type": "string",
                "description": (
                    "e.g. \"Pain point 'I don't have time to add anything new' (freq=23) "
                    "directly explains the 38% leads-to-appointments drop-off — perceived "
                    "time commitment is the conversion barrier at the booking stage.\""
                ),
            },
            "minItems": 1,
        },
        "optimization_priorities": {
            "type": "array",
            "description": (
                "Ranked list of optimisation actions ordered by expected revenue impact.  "
                "Priority 1 is the single action with the greatest potential to improve "
                "overall funnel performance.  Each action targets a specific stage, is "
                "grounded in a specific CI data point, and includes a quantified or "
                "directional expected impact."
            ),
            "items": {
                "type": "object",
                "required": [
                    "priority",
                    "stage",
                    "action",
                    "expected_impact",
                    "ci_grounding",
                ],
                "properties": {
                    "priority": {
                        "type": "integer",
                        "description": "1-based rank by expected revenue impact (1 = highest impact).",
                    },
                    "stage": {
                        "type": "string",
                        "description": "The funnel stage this action targets.",
                    },
                    "action": {
                        "type": "string",
                        "description": (
                            "The specific action to take.  Concrete enough to assign to a "
                            "team member and execute within a 2-week sprint."
                        ),
                    },
                    "expected_impact": {
                        "type": "string",
                        "description": (
                            "Quantified or directional impact on conversion rate or revenue.  "
                            "Where possible, state the expected uplift in conversion percentage "
                            "points and the downstream effect on sales volume."
                        ),
                    },
                    "ci_grounding": {
                        "type": "string",
                        "description": (
                            "The specific CI data point — pain point text with frequency, market "
                            "signal with mention count, or ICP buying trigger — that provides the "
                            "evidence base for this action."
                        ),
                    },
                },
            },
        },
        "recommended_action": {
            "type": "string",
            "description": (
                "A single, specific action for the next 7 days that targets the critical "
                "bottleneck stage.  Must name the stage, the CI insight that supports the "
                "action, and be concrete enough to execute without further clarification.  "
                "This is the executive takeaway — one sentence, maximum two."
            ),
        },
    },
}

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

__all__ = [
    "FUNNEL_ANALYSIS_SYSTEM_PROMPT_V1",
    "FUNNEL_ANALYSIS_OUTPUT_SCHEMA",
    "build_funnel_analysis_user_prompt",
    "render_funnel_analysis_system_prompt",
]
