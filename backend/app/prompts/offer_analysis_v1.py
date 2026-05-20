"""
Offer Analysis prompt — v1 (CI-OFR / M06-2).

Defines the system prompt, user prompt builder, and output schema for the
Offer Analyst specialist.  This module is consumed by the Marketing Director
when it needs a structured offer performance analysis with cross-domain CI
synthesis across pain points, objections, wins, goals, and ICP segments.
The Marketing Director pre-loads all enrichment data (offers, pain points,
ICP segments, wins, objections, goals) before invoking this prompt; the
specialist does NOT query data itself.
"""

from __future__ import annotations

import json

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

OFFER_ANALYSIS_SYSTEM_PROMPT_V1 = """\
You are **CI-OFR**, the Offer Analyst specialist of Central Intelligence — an AI-powered business intelligence platform for coaching and consulting businesses — operating in **analysis and optimisation mode**.

## Role

You sit inside the Marketing department, reporting to the Marketing Director.  Your sole function is to analyse the performance and structural integrity of every active offer in the portfolio, surface conversion leaks and misalignment against CI intelligence, and produce a ranked set of optimisation priorities grounded in real prospect data.  You are NOT a chatbot.  You produce structured JSON output only — no prose, no markdown, no commentary outside the JSON envelope.

## Expertise

You combine three disciplines:

1. **Offer performance diagnostics** — Conversion rate is the primary signal for offer performance, but you never report it in isolation.  A 12% conversion rate on a £5k programme and a 12% conversion rate on a £500 product are not equivalent outcomes — you contextualise performance against the offer's price point, target audience, and delivery model.  You distinguish between an offer that converts well despite structural weaknesses (carried by brand trust or referral traffic) and an offer that fails to convert because of design flaws that CI data could have caught.  Every performance assessment must name the structural reason behind the number.
2. **Pain-to-promise alignment analysis** — The offer's title, description, and deliverables constitute a promise.  That promise must be traceable, word for word, to the highest-frequency pain points and goals in the CI pool.  When a prospect reads an offer description and does not recognise their own language, situation, or desired outcome in it, they disengage — not because the offer lacks value, but because the offer failed to demonstrate that its creator understands their problem.  You audit every offer against the CI pain pool and name every alignment gap explicitly — because every gap is a potential conversion failure.
3. **Objection and trust architecture** — Objections are not random — they are predictable, patterned, and available in the CI pool.  An offer's guarantee, pricing tiers, and bonus structure should be deliberately engineered to address the highest-frequency objections before the prospect raises them.  A guarantee that does not address the most common fear in the CI pool is a missed trust signal.  Bonuses that do not reduce a specific friction point are decorative, not functional.  You audit each offer's objection coverage exhaustively and name every unaddressed objection as a conversion leak.

## Data Inputs

The Marketing Director provides all data pre-loaded.  You receive:

- **offers** — The full portfolio of active, draft, and archived offers, each containing: title, description, price_points (list of {tier, price, deliverables}), bonuses (list), guarantee, target_audience, created_at, status, conversion_rate (%), revenue_attributed.
- **pain_points** — CI pain points with text, category, and frequency_count — sorted by frequency.
- **icp_segments** — Validated ICP profiles for the business, flagging the primary segment.
- **wins** — Client wins and success stories with text, category, and frequency_count — used to assess whether social proof is embedded in the offer.
- **objections** — Common sales objections from the CI pool with text, category, and frequency_count — the primary lens for auditing offer trust architecture.
- **goals** — Stated client goals with text, category, and frequency_count — used to assess whether offer deliverables map to desired outcomes.
- **date_range_days** — The analysis period in days.

You must use ALL of these inputs together.  An offer analysis that does not cross-reference objections against the guarantee structure, or does not map deliverables to stated goals, is incomplete and will be rejected.

## Analysis Mandate

- **Conversion rate is the primary signal, not the full story.**  Diagnose WHY each offer is converting or failing to convert.  The answer is almost always in the CI data — in the pain points that are not addressed, the objections that are not handled, the goals that are not reflected in the deliverable list.
- **Pain-to-promise alignment must be explicit.**  For each offer, audit the description and deliverables against the top pain points by frequency.  Name the pain points that are addressed and the ones that are missing.  A high-frequency pain point not present in any offer is a cross-domain alert.
- **Objection coverage is a structural audit, not a guess.**  Read each offer's guarantee, pricing tiers, and bonus list against the top objections from the CI pool.  For every high-frequency objection, determine whether the offer structure addresses it directly.  Name the gaps as conversion leaks.
- **Wins as proof signals.**  The best client wins in the CI pool should be reflected in the offer's social proof narrative.  An offer that does not incorporate the most resonant wins is leaving trust on the table.  Name any wins that are high-frequency but absent from the offer structure.
- **Goals-to-outcomes alignment.**  Every offer's deliverables should map to the stated goals of the primary ICP.  Deliverables that address a goal the ICP does not hold add cost without adding perceived value.  Deliverables that miss a high-frequency goal create a perceived value gap.
- **Pricing gap analysis.**  The primary ICP's buying decision framework (buying triggers, pain intensity, outcome urgency) determines whether the pricing tier structure is appropriate.  A pricing structure designed for price-sensitive buyers applied to a high-urgency ICP is leaving revenue on the table.  The reverse creates friction and reduces conversion.

## Output Contract

You MUST return a single JSON object.  No prose before or after.  No markdown fences.  No explanations.  Only the JSON object.

The object must conform exactly to the output schema described below.  Every field is required.  If a list field has no entries, return an empty array — do not omit the field.

## Example Output

The following illustrates the expected structure and writing quality.  All values are fabricated for illustration only — replace every field with real synthesised content:

```json
{
  "summary": "The offer portfolio has one clear performer — the 90-Day Revenue Accelerator converts at 18% — but the remaining three offers are underperforming relative to the quality of the underlying CI data, primarily because their descriptions fail to use the prospect's own language and their guarantee structures do not address the highest-frequency objection ('I've tried coaching before and it didn't work', freq=19). The most urgent intervention is the Group Mastermind, which has the highest revenue potential but a conversion rate of 3.1% driven by a near-total absence of objection handling.",
  "top_performing_offer": {
    "title": "90-Day Revenue Accelerator",
    "conversion_rate": 18.2,
    "strength_diagnosis": "This offer converts because the headline and description directly mirror the language of the primary ICP's highest-frequency pain ('I'm working constantly but my income has plateaued') and the guarantee ('Full refund if you don't achieve a measurable revenue increase in 90 days') directly counters the most common purchase barrier. The three pricing tiers also align well with the ICP's buying pattern — the mid-tier at £3,500 captures the majority of sales, which reflects the primary ICP's willingness to invest at the £3k-£5k range when outcome certainty is high."
  },
  "offer_breakdown": [
    {
      "title": "90-Day Revenue Accelerator",
      "conversion_rate": 18.2,
      "health": "strong",
      "pain_alignment_score": 8,
      "objection_coverage": [
        "Addressed: 'I've tried coaching before and it didn't work' — via outcome-linked guarantee",
        "Addressed: 'I don't have time for another programme' — via async delivery model named in deliverables",
        "Missed: 'I don't know if this will work for my specific niche' — no niche-specific case study referenced"
      ],
      "missing_value_props": [
        "No mention of the revenue-doubling win story from the CI pool (freq=8) — highest social proof signal available",
        "Deliverables do not reference the ICP goal 'build a client base that doesn't depend on referrals' (freq=11) — a high-frequency goal absent from the outcome list"
      ],
      "optimization_recommendations": [
        "Add one niche-specific case study to the offer page to address the 'will this work for my niche' objection (freq=14)",
        "Incorporate the revenue-doubling win story as a featured testimonial — it matches the primary ICP's outcome aspiration precisely",
        "Rewrite the deliverables list to explicitly name 'independent client acquisition system' as an outcome, mapping to the ICP goal (freq=11)"
      ]
    },
    {
      "title": "Group Mastermind",
      "conversion_rate": 3.1,
      "health": "weak",
      "pain_alignment_score": 3,
      "objection_coverage": [
        "Missed: 'I've tried group programmes before and don't get enough individual attention' — no personalisation mechanism named in deliverables",
        "Missed: 'The price is too high for a group format' — no tier structure to lower the entry point",
        "Missed: 'I don't know if the cohort will be the right fit for me' — no cohort qualification criteria described"
      ],
      "missing_value_props": [
        "Description uses generic coaching language ('accelerate your growth', 'surround yourself with like-minded entrepreneurs') — none of the primary ICP's actual pain vocabulary appears in the copy",
        "No wins from the CI pool are referenced — highest available social proof score (freq=9) is entirely absent",
        "Deliverables do not map to any of the top 5 ICP goals in the CI pool"
      ],
      "optimization_recommendations": [
        "Rewrite the entire offer description using the top 3 pain point phrases verbatim from the CI pool — the current copy could apply to any group programme for any audience",
        "Add a mid-tier pricing option at £1,800 to address the price sensitivity objection and give prospects an entry point that feels lower-risk",
        "Name a 'hot seat' or individual attention mechanism in the deliverables to directly counter the 'no individual attention' objection (freq=16)"
      ]
    }
  ],
  "cross_domain_alerts": [
    "Pain point 'I don't know how to price my services without losing clients' (freq=13) is not addressed in any current offer — this is the fourth highest-frequency pain in the CI pool and represents an entirely unserved need in the portfolio",
    "Objection 'I need to see results from someone in my exact situation before I invest' (freq=11) is present in the CI pool but zero offers include a niche-matched case study in their structure",
    "Goal 'build recurring revenue that doesn't depend on constant client acquisition' (freq=14) appears in the CI pool but is not named as a deliverable or outcome in any active offer"
  ],
  "pricing_gap_analysis": "The primary ICP (established solopreneurs, 3-7 years in business, generating £3k-£8k/month) has 'ROI certainty before committing' as the dominant buying trigger. The current portfolio has three offers priced above £3,000 with no mid-tier entry point between £500 and £3,000 — this gap forces a high-commitment decision as the first available step after the free audit, which is a conversion barrier for prospects who are not yet certain of ROI. Adding a £1,200-£1,500 intensive or diagnostic product would capture conversion from ICP-matched prospects who need an experience of the methodology before committing to a full programme.",
  "recommended_focus": "Rewrite the Group Mastermind offer description this week using the top 5 pain point phrases from the CI pool and add a personalised attention mechanism to the deliverables — this single intervention targets the offer with the highest revenue potential and the most correctable structural weaknesses."
}
```\
"""

# ---------------------------------------------------------------------------
# User prompt builder
# ---------------------------------------------------------------------------


def build_offer_analysis_user_prompt(data: dict) -> str:  # noqa: PLR0912
    """Format pre-loaded Marketing Director enrichment data into the offer analysis prompt.

    Parameters
    ----------
    data:
        A dict with keys: ``offers``, ``pain_points``, ``icp_segments``,
        ``wins``, ``objections``, ``goals``, ``date_range_days``.

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

    # -- Offers ---------------------------------------------------------------
    offers: list[dict] = data.get("offers", [])
    if offers:
        lines += [
            "## Offers Portfolio (sorted by conversion rate, ascending — lowest performance first)",
            "",
        ]
        sorted_offers = sorted(
            offers, key=lambda o: o.get("conversion_rate", 0.0)
        )
        for offer in sorted_offers:
            title = offer.get("title") or "Untitled"
            status = offer.get("status") or "unknown"
            conversion_rate = offer.get("conversion_rate", 0.0)
            revenue_attributed = offer.get("revenue_attributed", 0.0)
            target_audience = offer.get("target_audience") or ""
            description = offer.get("description") or ""
            guarantee = offer.get("guarantee") or ""
            bonuses: list = offer.get("bonuses") or []
            price_points: list[dict] = offer.get("price_points") or []
            created_at = offer.get("created_at") or ""

            lines += [
                f"### {title}",
                f"- Status: {status}",
                f"- Conversion rate: {conversion_rate:.1f}%",
                f"- Revenue attributed: £{revenue_attributed:,.0f}",
            ]
            if created_at:
                lines.append(f"- Created: {created_at}")
            if target_audience:
                lines.append(f"- Target audience: {target_audience}")
            if description:
                lines.append(f"- Description: {description}")
            if guarantee:
                lines.append(f"- Guarantee: {guarantee}")
            if price_points:
                lines.append("- Price points:")
                sorted_tiers = sorted(
                    price_points, key=lambda t: t.get("price", 0)
                )
                for tier in sorted_tiers:
                    tier_name = tier.get("tier") or "Standard"
                    price = tier.get("price", 0)
                    deliverables: list = tier.get("deliverables") or []
                    deliverables_str = "; ".join(deliverables) if deliverables else "Not specified"
                    lines.append(
                        f"  - {tier_name}: £{price:,} — Deliverables: {deliverables_str}"
                    )
            if bonuses:
                bonuses_str = "; ".join(str(b) for b in bonuses)
                lines.append(f"- Bonuses: {bonuses_str}")
            lines.append("")
    else:
        lines += ["## Offers Portfolio", "", "(No offer data available.)", ""]

    # -- Pain points ----------------------------------------------------------
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

    # -- ICP segments ---------------------------------------------------------
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
            lines.append(f"### {segment}{primary_tag}")
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

    # -- Client wins ----------------------------------------------------------
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

    # -- Objections -----------------------------------------------------------
    objections: list[dict] = data.get("objections", [])
    if objections:
        lines += [
            "## Sales Objections (sorted by frequency, highest first)",
            "",
        ]
        sorted_obj = sorted(
            objections, key=lambda o: o.get("frequency_count", 0), reverse=True
        )
        for i, obj in enumerate(sorted_obj, start=1):
            text = obj.get("text") or ""
            category = obj.get("category") or "Uncategorised"
            freq = obj.get("frequency_count", 1)
            lines.append(f"{i}. [{category} | freq={freq}] {text}")
        lines.append("")
    else:
        lines += ["## Sales Objections", "", "(No objection data available.)", ""]

    # -- Goals ----------------------------------------------------------------
    goals: list[dict] = data.get("goals", [])
    if goals:
        lines += [
            "## Client Goals (sorted by frequency, highest first)",
            "",
        ]
        sorted_goals = sorted(
            goals, key=lambda g: g.get("frequency_count", 0), reverse=True
        )
        for i, goal in enumerate(sorted_goals, start=1):
            text = goal.get("text") or ""
            category = goal.get("category") or "Uncategorised"
            freq = goal.get("frequency_count", 1)
            lines.append(f"{i}. [{category} | freq={freq}] {text}")
        lines.append("")
    else:
        lines += ["## Client Goals", "", "(No goals data available.)", ""]

    # -- Output instructions --------------------------------------------------
    lines += [
        "---",
        "",
        "## Your Task",
        "",
        "Using all of the intelligence above, produce a single JSON object conforming to the output schema.",
        "",
        "Analysis requirements:",
        "- summary must be 2-3 sentences naming the best and worst performing offers by title, their conversion rates, and at least one cross-domain CI observation that explains performance.",
        "- top_performing_offer must identify the single highest-converting offer, name its conversion rate, and diagnose WHY it converts — name the specific structural or CI-alignment reason, not just that it 'performs well'.",
        "- offer_breakdown must include an entry for every offer in the portfolio regardless of status. For each offer:",
        "  - health: 'strong' = conversion rate above 12% for high-ticket (>£2k) or above 20% for low-ticket; 'moderate' = borderline for the price point; 'weak' = meaningfully below benchmark.",
        "  - pain_alignment_score (1-10): score how many of the top 5 CI pain points are explicitly addressed in the offer's description and deliverables. 8-10 = strong alignment; 5-7 = moderate; below 5 = weak.",
        "  - objection_coverage: for every top-5 objection by frequency, state whether it is 'Addressed' or 'Missed' in the offer structure (guarantee, pricing tiers, or bonuses) — and name the mechanism or the gap explicitly.",
        "  - missing_value_props: name specific wins from the CI pool that are not used as social proof, and specific ICP goals not reflected in the deliverables.",
        "  - optimization_recommendations: minimum 2 concrete, CI-grounded actions per offer. Each action must name the specific pain point, objection, or goal it targets.",
        "- cross_domain_alerts: identify pain points, objections, or goals with frequency >= 5 that are NOT addressed in any offer in the portfolio. These are structural gaps, not individual offer weaknesses.",
        "- pricing_gap_analysis: assess the overall pricing tier structure against the primary ICP's buying triggers and outcome urgency. Name specific price point gaps that create conversion friction.",
        "- recommended_focus: one sentence naming the single highest-impact offer optimisation for the next 30 days, with the CI data point that supports the prioritisation.",
        "",
        "Output format — return ONLY this JSON object, nothing else:",
        "",
        json.dumps(
            {
                "summary": "2-3 sentence executive summary naming best and worst performers by title and conversion rate, with a cross-domain CI observation.",
                "top_performing_offer": {
                    "title": "Offer title",
                    "conversion_rate": 0.0,
                    "strength_diagnosis": "Structural and CI-alignment explanation for why this offer converts at its rate.",
                },
                "offer_breakdown": [
                    {
                        "title": "Offer title",
                        "conversion_rate": 0.0,
                        "health": "strong | moderate | weak",
                        "pain_alignment_score": 0,
                        "objection_coverage": [
                            "Addressed: [objection text] — via [mechanism]",
                            "Missed: [objection text] — no [mechanism] present",
                        ],
                        "missing_value_props": [
                            "Win '[win text]' (freq=N) not referenced in offer social proof.",
                            "ICP goal '[goal text]' (freq=N) not named in deliverables.",
                        ],
                        "optimization_recommendations": [
                            "Specific, CI-grounded action targeting a named pain point, objection, or goal.",
                        ],
                    }
                ],
                "cross_domain_alerts": [
                    "Pain point/objection/goal with freq>=5 not addressed in any offer — with explanation of the portfolio gap it represents."
                ],
                "pricing_gap_analysis": "Assessment of the full pricing tier structure against primary ICP buying triggers and outcome urgency, naming specific price point gaps.",
                "recommended_focus": "Single highest-impact offer optimisation for the next 30 days, naming the CI data point that supports prioritisation.",
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

OFFER_ANALYSIS_OUTPUT_SCHEMA: dict = {
    "type": "object",
    "description": (
        "Structured offer portfolio analysis produced by the Offer Analyst "
        "specialist (CI-OFR) in analysis and optimisation mode.  Consumed by "
        "the Marketing Director to identify conversion leaks, structural "
        "weaknesses, and CI-grounded optimisation priorities across the full "
        "offer portfolio."
    ),
    "required": [
        "summary",
        "top_performing_offer",
        "offer_breakdown",
        "cross_domain_alerts",
        "pricing_gap_analysis",
        "recommended_focus",
    ],
    "properties": {
        "summary": {
            "type": "string",
            "description": (
                "2-3 sentence executive summary of offer portfolio performance for the "
                "analysis period.  Must name the best and worst performing offers by "
                "title and conversion rate, and include at least one cross-domain CI "
                "observation that explains portfolio-level behaviour."
            ),
        },
        "top_performing_offer": {
            "type": "object",
            "description": (
                "The single highest-converting offer in the portfolio, with a structural "
                "and CI-alignment diagnosis explaining why it outperforms."
            ),
            "required": ["title", "conversion_rate", "strength_diagnosis"],
            "properties": {
                "title": {
                    "type": "string",
                    "description": "The title of the top-performing offer.",
                },
                "conversion_rate": {
                    "type": "number",
                    "description": "Conversion rate as a percentage (e.g. 18.2 for 18.2%).",
                    "example": 18.2,
                },
                "strength_diagnosis": {
                    "type": "string",
                    "description": (
                        "Structural and CI-alignment explanation for why this offer converts "
                        "at its rate.  Must name the specific mechanisms — pain alignment, "
                        "objection handling via guarantee or pricing, win-as-proof integration, "
                        "or ICP goal reflection in deliverables — that drive performance."
                    ),
                },
            },
        },
        "offer_breakdown": {
            "type": "array",
            "description": (
                "One entry per offer in the portfolio, regardless of status.  Each entry "
                "audits the offer against the CI pool for pain alignment, objection coverage, "
                "missing value propositions, and provides CI-grounded optimisation recommendations."
            ),
            "items": {
                "type": "object",
                "required": [
                    "title",
                    "conversion_rate",
                    "health",
                    "pain_alignment_score",
                    "objection_coverage",
                    "missing_value_props",
                    "optimization_recommendations",
                ],
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "The offer title.",
                    },
                    "conversion_rate": {
                        "type": "number",
                        "description": "Conversion rate as a percentage for the analysis period.",
                    },
                    "health": {
                        "type": "string",
                        "enum": ["strong", "moderate", "weak"],
                        "description": (
                            "Overall health of the offer relative to its price point and "
                            "delivery model.  'strong' = conversion rate above benchmark for "
                            "price tier; 'moderate' = borderline; 'weak' = meaningfully below "
                            "benchmark or with critical structural gaps."
                        ),
                    },
                    "pain_alignment_score": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 10,
                        "description": (
                            "Score (1-10) for how many of the top 5 CI pain points are "
                            "explicitly addressed in the offer's description and deliverables.  "
                            "8-10 = strong alignment; 5-7 = moderate; below 5 = weak."
                        ),
                        "example": 8,
                    },
                    "objection_coverage": {
                        "type": "array",
                        "description": (
                            "One entry per top-frequency objection from the CI pool, stating "
                            "whether it is addressed or missed in the offer structure (guarantee, "
                            "pricing tiers, or bonuses), and naming the specific mechanism or gap.  "
                            "Format: 'Addressed: [objection] — via [mechanism]' or "
                            "'Missed: [objection] — no [mechanism] present'."
                        ),
                        "items": {"type": "string"},
                    },
                    "missing_value_props": {
                        "type": "array",
                        "description": (
                            "Specific wins from the CI pool not used as social proof in this "
                            "offer, and specific ICP goals not reflected in the deliverables.  "
                            "Each item names the win or goal text with its frequency count."
                        ),
                        "items": {"type": "string"},
                    },
                    "optimization_recommendations": {
                        "type": "array",
                        "description": (
                            "Minimum 2 concrete, CI-grounded actions to improve this offer's "
                            "conversion rate or structural integrity.  Each recommendation must "
                            "name the specific pain point, objection, win, or goal it targets — "
                            "with frequency count where available."
                        ),
                        "items": {"type": "string"},
                        "minItems": 2,
                    },
                },
            },
        },
        "cross_domain_alerts": {
            "type": "array",
            "description": (
                "High-frequency pain points, objections, or goals (frequency >= 5) that "
                "are not addressed in any offer in the portfolio.  These are structural "
                "portfolio gaps — unserved needs that represent either a new offer "
                "opportunity or a systemic messaging failure across the portfolio.  "
                "Each alert names the CI item, its frequency, and the gap it represents."
            ),
            "items": {"type": "string"},
        },
        "pricing_gap_analysis": {
            "type": "string",
            "description": (
                "Assessment of the full pricing tier structure across the portfolio "
                "against the primary ICP's buying triggers, pain intensity, and outcome "
                "urgency.  Must name specific price point gaps that create conversion "
                "friction (e.g. no entry-level product for prospects not yet ready for "
                "a high-ticket commitment) and suggest the price range where a new tier "
                "would capture currently lost conversion."
            ),
        },
        "recommended_focus": {
            "type": "string",
            "description": (
                "A single sentence naming the highest-impact offer optimisation action "
                "for the next 30 days.  Must name the specific offer, the change to make, "
                "and the CI data point (pain point, objection, or goal with frequency count) "
                "that justifies prioritising this action above all others."
            ),
        },
    },
}

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

__all__ = [
    "OFFER_ANALYSIS_SYSTEM_PROMPT_V1",
    "OFFER_ANALYSIS_OUTPUT_SCHEMA",
    "build_offer_analysis_user_prompt",
]
