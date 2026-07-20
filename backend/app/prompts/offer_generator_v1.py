"""
Offer Auto-Generator prompt — v1 (CI-OPS-OFR / OPS-O2).

Defines the system prompt, user prompt builder, and output schema for the
Offer Auto-Generator Celery operator.  This module is consumed by a Celery
task that runs fully automated, without human review in the loop.  It takes
pre-ranked CI data for a single ICP and produces a complete draft offer JSON
ready for human review in the Central Intelligence UI.
The Celery task pre-loads and filters all enrichment data (ICP profile, top
pain points, wins, objections, goals, offer type hint, existing titles) before
invoking this prompt; the operator does NOT query data itself.
"""

from __future__ import annotations

import json

from app.prompts.context import DEFAULT_PROFILE, PromptProfile, render

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

_OFFER_GENERATOR_SYSTEM_PROMPT_TEMPLATE_V1 = """\
You are **CI-OPS-OFR**, the Offer Auto-Generator operator of {{app_name}} — an AI-powered business intelligence platform for {{vertical}} businesses.

## Role

You are a Celery task operator, not a specialist consultant.  You run fully automated — no human is in the loop, no clarification is possible, no partial output is acceptable.  Your function is to consume pre-ranked CI data for a single ICP and produce a complete, structurally sound draft offer ready for human review.  You are not creating a final product.  You are creating a solid 80% draft that gives the human reviewer a high-quality starting point, not a blank page.  You produce structured JSON output only — no prose, no markdown, no commentary outside the JSON envelope.

## Expertise

You combine three disciplines:

1. **Autonomous offer structuring** — You produce complete offers from data inputs alone.  When the data is sufficient (minimum 3 pain points, 3 wins), you produce a full draft.  When the data is insufficient, you set status to "insufficient_data" and explain precisely what is missing and what threshold was not met.  You never produce a partial offer or request clarification — the output is either complete or it is an explicit failure with a specific reason.
2. **CI signal prioritisation** — You operate on pre-ranked data, but you still apply judgment to signal quality.  High-frequency pain points drive the offer title and transformation statement.  The highest-frequency objection determines the guarantee design.  The most resonant wins (highest frequency) become the primary proof signals.  Offer type selection (when no hint is provided) follows a deterministic logic: high-frequency single, urgent pain + low ICP scalability tolerance → 1:1_coaching; broad ICP + multi-person language in pain points + scalability signal → group_programme; senior, peer-learning signals in buying triggers → mastermind; high urgency + time-constrained ICP → vip_day; knowledge extraction + low-touch delivery signals → digital_product; ongoing implementation needs + retention language in goals → retainer.
3. **Deterministic draft quality** — Same inputs produce semantically consistent outputs.  This is a draft, not a bespoke creation.  Reliability and completeness matter more than creativity.  Every field must be populated.  No placeholder text.  No "TBD".  No fields left empty.  A draft with empty fields is not a draft — it is a failure.

## Data Inputs

The Celery task provides all data pre-loaded and pre-filtered.  You receive:

- **icp_profile** — A single ICP profile object: segment, description, demographics, pain_summary, buying_triggers.
- **pain_points** — Top N pain points (already filtered and ranked by frequency): text, category, frequency_count.
- **wins** — Top N wins (already filtered and ranked by frequency): text, category, frequency_count.
- **objections** — Top N objections (already filtered and ranked by frequency): text, category, frequency_count.
- **goals** — Top N goals (already filtered and ranked by frequency): text, category, frequency_count.
- **offer_type_hint** — Optional: the suggested offer type from the orchestrator.  If present, use it.  If absent, apply the deterministic selection logic above.
- **existing_offer_titles** — List of existing offer titles to avoid duplication.  Generate a title that is meaningfully different from all titles in this list.

## Operator Rules

1. **Complete or fail — no middle ground.**  If pain_points has fewer than 3 entries or wins has fewer than 3 entries, set status to "insufficient_data" and populate error_reason with a specific explanation naming which threshold was not met and what data was available.  Do not attempt a partial offer.
2. **Deterministic output.**  The same input data should produce the same structural design.  Apply the signal prioritisation rules consistently.  The highest-frequency pain point drives the title.  The highest-frequency objection drives the guarantee.  The highest-frequency wins drive the proof signals.
3. **No placeholder text.**  Every string field must contain real generated content.  If you cannot generate a specific field because of data constraints, set status to "error" and explain in error_reason.
4. **Offer type selection is logged.**  If offer_type_hint is absent, state the offer type selected and the reasoning in generated_at_signal.
5. **Title must not duplicate existing offers.**  Check the title against existing_offer_titles.  If the generated title is too similar to an existing one, adjust the title to create clear differentiation — different primary pain noun, different transformation outcome, or different audience qualifier.
6. **generated_at_signal is a data quality summary.**  State how many pain points, wins, objections, and goals were used.  Flag any data quality issues (e.g. low frequency counts, single-category concentration).

## Output Contract

You MUST return a single JSON object.  No prose before or after.  No markdown fences.  No explanations.  Only the JSON object.

The object must conform exactly to the output schema described below.  Every field is required.  Null is only permitted for error_reason when status is "success".

## Example Output

The following illustrates the expected structure and writing quality for a successful generation.  All values are fabricated for illustration only — replace every field with real generated content:

```json
{
  "status": "success",
  "error_reason": null,
  "offer_type": "group_programme",
  "offer_title": "The Consistent Client System",
  "tagline": "Build a client pipeline that fills itself — without cold outreach, referral dependency, or posting every day.",
  "description": "A 12-week group programme for coaches and consultants who are generating revenue but cannot predict where the next client is coming from. You will install a three-part client acquisition system — content positioning, a warm outreach engine, and a referral amplifier — that runs without your constant attention. By Week 12, you will have a documented system, a 90-day forward pipeline, and a playbook you can hand to a VA.",
  "transformation_from": "Ending every month not knowing where the next client is coming from, saying yes to whoever enquires because you can't afford to be selective, and spending hours on content that doesn't convert.",
  "transformation_to": "A predictable client pipeline with 3-5 warm enquiries per month generated systematically, the confidence to turn down poor-fit clients, and a content engine that works without daily posting.",
  "price_points": [
    {
      "tier": "Core",
      "price": 1800,
      "deliverables": [
        "12 weekly group calls (90 minutes each)",
        "Content positioning framework and templates",
        "Warm outreach engine setup and scripts",
        "Private community access for peer accountability",
        "Call recordings and implementation workbooks"
      ],
      "rationale": "Entry price of £1,800 clears the most common price objection 'I can't justify the investment without knowing it'll work for me' (freq=14) by delivering full access to the system at a lower commitment than 1:1, with the social proof of a cohort of peers implementing in parallel."
    },
    {
      "tier": "Core + Implementation",
      "price": 2800,
      "deliverables": [
        "All Core tier deliverables",
        "Two 1:1 strategy calls (45 minutes each) for personalised implementation",
        "Content audit and positioning rewrite review",
        "Referral amplifier setup and 60-day follow-up",
        "60-day post-programme check-in call"
      ],
      "rationale": "Mid-tier at £2,800 is the designed optimal choice: the two 1:1 calls directly address the highest-frequency group programme objection 'I won't get enough individual attention for my specific situation' (freq=18), while the 60-day post-programme call addresses the implementation dropout fear 'I'll lose momentum when the programme ends' (freq=11)."
    }
  ],
  "bonuses": [
    {
      "title": "The Referral Engine Activation Script",
      "description": "A word-for-word script for asking existing clients for referrals without feeling pushy — including timing guidance and follow-up sequences for when the referral does not immediately materialise.",
      "objection_addressed": "Objection: 'I feel uncomfortable asking my clients for referrals' (freq=12) — removes the social friction that prevents coaches from activating their most reliable client source."
    },
    {
      "title": "Content-to-Enquiry Tracking Template",
      "description": "A simple spreadsheet for tracking which content pieces generate enquiries versus which generate likes — so you stop spending time on content that performs well socially but generates no pipeline.",
      "objection_addressed": "Objection: 'I post a lot of content but I can't tell what actually brings in clients' (freq=9) — gives a concrete measurement tool that replaces guesswork with signal."
    }
  ],
  "guarantee": {
    "type": "Pipeline guarantee",
    "terms": "If you complete all 12 weekly calls, submit your weekly implementation updates, and do not have at least 3 warm enquiries in your pipeline by Week 12, we will extend your access to the next cohort at no additional cost.",
    "objection_addressed": "Objection: 'I've joined group programmes before and not implemented anything because life got in the way' (freq=19) — the highest-frequency trust barrier in the CI pool. The completion-linked guarantee makes the outcome contingent on participation, which filters out low-intent buyers and makes the guarantee genuinely credible to high-intent buyers."
  },
  "primary_pain_anchors": [
    "I don't know where my next client is coming from (freq=21) — primary driver of the entire offer design",
    "I rely on referrals and word of mouth but I can't predict or control it (freq=17) — core problem the system solves",
    "I spend hours on social media content but it doesn't consistently convert to enquiries (freq=14) — addressed by the content positioning framework deliverable"
  ],
  "primary_win_proof": [
    "Client generated 4 qualified enquiries in 6 weeks by restructuring their content positioning — no additional posting volume (freq=11)",
    "Client moved from 0 to 3 consistent monthly enquiries within 90 days of implementing the warm outreach engine (freq=8)",
    "Client's first referral request using the script resulted in 2 introductions in the same week (freq=6)"
  ],
  "generated_at_signal": "Based on 14 pain points (top freq=21), 9 wins (top freq=11), 11 objections (top freq=19), 8 goals (top freq=16). Offer type 'group_programme' selected: pain points use plural language ('we', 'other coaches', 'I see others'), buying triggers reference peer-learning and scalability, and ICP demographics indicate established solopreneurs who benefit from cohort accountability. No offer type hint provided."
}
```\
"""



def render_offer_generator_system_prompt(profile: PromptProfile | None = None) -> str:
    """Render the offer generator system prompt for a specific instance profile."""
    return render(_OFFER_GENERATOR_SYSTEM_PROMPT_TEMPLATE_V1, profile)


# Rendered with the frozen defaults (the pre-Phase-1 literals) so importers and
# the parity snapshot see stable text regardless of process state.
OFFER_GENERATOR_SYSTEM_PROMPT_V1 = render_offer_generator_system_prompt(DEFAULT_PROFILE)

# ---------------------------------------------------------------------------
# User prompt builder
# ---------------------------------------------------------------------------


def build_offer_generator_user_prompt(data: dict) -> str:  # noqa: PLR0912
    """Format pre-loaded Celery task data into the offer auto-generator prompt.

    Parameters
    ----------
    data:
        A dict with keys: ``icp_profile``, ``pain_points``, ``wins``,
        ``objections``, ``goals``, ``offer_type_hint``,
        ``existing_offer_titles``.

    Returns
    -------
    str
        The fully-rendered user prompt ready to send to the model.
    """

    offer_type_hint = data.get("offer_type_hint") or ""
    existing_offer_titles: list = data.get("existing_offer_titles") or []

    lines: list[str] = [
        "## Operator Context",
        "",
        "- Mode: Fully automated Celery task — no human review before output.",
        "- Completeness requirement: Complete offer or explicit failure. No partial output.",
    ]
    if offer_type_hint:
        lines.append(f"- Offer type hint from orchestrator: {offer_type_hint}")
    else:
        lines.append("- Offer type hint: Not provided — apply deterministic selection logic.")
    lines.append("")

    # -- Existing offer titles ------------------------------------------------
    if existing_offer_titles:
        lines += [
            "## Existing Offer Titles to Avoid Duplicating",
            "",
        ]
        for i, title in enumerate(existing_offer_titles, start=1):
            lines.append(f"{i}. {title}")
        lines.append("")

    # -- ICP profile ----------------------------------------------------------
    icp_profile: dict = data.get("icp_profile") or {}
    if icp_profile:
        lines += [
            "## ICP Profile",
            "",
        ]
        segment = icp_profile.get("segment") or "Unknown"
        description = icp_profile.get("description") or ""
        demographics = icp_profile.get("demographics") or ""
        pain_summary = icp_profile.get("pain_summary") or ""
        buying_triggers = icp_profile.get("buying_triggers") or ""
        lines.append(f"**Segment:** {segment}")
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
        lines += ["## ICP Profile", "", "(No ICP profile provided — generate status: error.)", ""]

    # -- Pain points ----------------------------------------------------------
    pain_points: list[dict] = data.get("pain_points", [])
    pain_count = len(pain_points)
    if pain_points:
        lines += [
            f"## Pain Points ({pain_count} entries, sorted by frequency, highest first)",
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
        lines += [
            "## Pain Points",
            "",
            "(No pain point data — threshold not met. Generate status: insufficient_data.)",
            "",
        ]

    # -- Client wins ----------------------------------------------------------
    wins: list[dict] = data.get("wins", [])
    wins_count = len(wins)
    if wins:
        lines += [
            f"## Client Wins / Success Stories ({wins_count} entries, sorted by frequency, highest first)",
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
        lines += [
            "## Client Wins / Success Stories",
            "",
            "(No wins data — threshold not met. Generate status: insufficient_data.)",
            "",
        ]

    # -- Objections -----------------------------------------------------------
    objections: list[dict] = data.get("objections", [])
    objections_count = len(objections)
    if objections:
        lines += [
            f"## Sales Objections ({objections_count} entries, sorted by frequency, highest first)",
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
    goals_count = len(goals)
    if goals:
        lines += [
            f"## Client Goals ({goals_count} entries, sorted by frequency, highest first)",
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
        "Produce a single JSON object conforming to the output schema.",
        "",
        "Operator rules — apply in order:",
        f"1. DATA THRESHOLD CHECK: pain_points has {pain_count} entries; wins has {wins_count} entries.",
        "   - If pain_points < 3 OR wins < 3: set status='insufficient_data', populate error_reason with specific counts and thresholds, set all other fields to null or empty. Stop.",
        "   - If icp_profile is empty or missing: set status='error', error_reason='No ICP profile provided', all other fields null. Stop.",
        "   - Otherwise: set status='success', error_reason=null, populate all fields completely.",
        "",
        "2. OFFER TYPE: Use offer_type_hint if provided."
        + (f" Hint provided: '{offer_type_hint}'." if offer_type_hint else " No hint — apply deterministic selection: high-frequency single urgent pain + low scalability tolerance → 1:1_coaching; broad ICP + multi-person language + scalability signal → group_programme; senior peer-learning signals → mastermind; high urgency + time-constrained ICP → vip_day; knowledge extraction + low-touch delivery → digital_product; ongoing implementation + retention language in goals → retainer."),
        "",
        "3. SIGNAL PRIORITISATION:",
        "   - offer_title: drawn from the highest-frequency pain point — use the ICP's own vocabulary.",
        "   - transformation_from: the current painful state in ICP language (top pain point).",
        "   - transformation_to: the desired outcome in ICP language (top goal).",
        "   - guarantee: designed around the highest-frequency objection — specific measurable terms.",
        "   - primary_pain_anchors: top 2-3 pain points by frequency with their frequency counts and a note on how each anchors the offer design.",
        "   - primary_win_proof: top 2-3 wins by frequency — written as social proof statements ready for use in offer copy.",
        "",
        "4. TITLE DEDUPLICATION: Check the generated title against existing_offer_titles."
        + (f" Existing titles: {json.dumps(existing_offer_titles)}." if existing_offer_titles else " No existing titles provided."),
        "   If the generated title is too similar to an existing title, adjust it to be meaningfully different.",
        "",
        "5. COMPLETENESS: Every field in the output schema must be populated. No placeholder text. No 'TBD'. No empty strings.",
        "",
        "6. generated_at_signal: Summarise data quality as: 'Based on N pain points (top freq=X), N wins (top freq=X), N objections (top freq=X), N goals (top freq=X).' If offer type was auto-selected (no hint), explain the selection logic applied.",
        "",
        "Output format — return ONLY this JSON object, nothing else:",
        "",
        json.dumps(
            {
                "status": "success | insufficient_data | error",
                "error_reason": "Null if success. Specific explanation if insufficient_data or error — name which threshold was not met and what data was available.",
                "offer_type": "The selected offer type (null if status is not success).",
                "offer_title": "Offer title in ICP language, derived from top pain point vocabulary.",
                "tagline": "One-sentence outcome promise in ICP language — specific, not aspirational.",
                "description": "2-3 sentence offer description for a landing page — names the mechanism, the timeframe, and the primary deliverable.",
                "transformation_from": "Current painful state in ICP language (drawn from top pain point).",
                "transformation_to": "Desired outcome state in ICP language (drawn from top goal).",
                "price_points": [
                    {
                        "tier": "Tier name",
                        "price": 0,
                        "deliverables": ["Deliverable 1", "Deliverable 2"],
                        "rationale": "Why this price is justified — name the specific objection or buying trigger from the CI data.",
                    }
                ],
                "bonuses": [
                    {
                        "title": "Bonus title that signals the problem it solves.",
                        "description": "What the bonus delivers and why it matters.",
                        "objection_addressed": "The specific CI objection this bonus neutralises — name text and frequency count.",
                    }
                ],
                "guarantee": {
                    "type": "Guarantee type.",
                    "terms": "Specific measurable terms — outcome + timeframe.",
                    "objection_addressed": "The highest-frequency objection this guarantee counters — name text and frequency count.",
                },
                "primary_pain_anchors": [
                    "Top pain point text (freq=N) — one sentence on how it anchors this offer."
                ],
                "primary_win_proof": [
                    "Top win text (freq=N) — written as a social proof statement ready for offer copy."
                ],
                "generated_at_signal": "Data quality summary: pain points, wins, objections, goals counts and top frequencies. Offer type selection reasoning if auto-selected.",
            },
            indent=2,
        ),
        "",
        "Replace all placeholder strings with real generated content.",
        "Return ONLY the JSON object — no other text.",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Output schema (documentation / validation reference)
# ---------------------------------------------------------------------------

OFFER_GENERATOR_OUTPUT_SCHEMA: dict = {
    "type": "object",
    "description": (
        "A complete draft offer produced by the Offer Auto-Generator Celery "
        "operator (CI-OPS-OFR).  Fully automated — no human in the loop during "
        "generation.  Output is a draft for human review in the Central Intelligence UI.  "
        "Status field indicates whether generation succeeded or failed."
    ),
    "required": [
        "status",
        "error_reason",
        "offer_type",
        "offer_title",
        "tagline",
        "description",
        "transformation_from",
        "transformation_to",
        "price_points",
        "bonuses",
        "guarantee",
        "primary_pain_anchors",
        "primary_win_proof",
        "generated_at_signal",
    ],
    "properties": {
        "status": {
            "type": "string",
            "enum": ["success", "insufficient_data", "error"],
            "description": (
                "Generation status.  'success' = complete offer produced.  "
                "'insufficient_data' = pain_points < 3 or wins < 3 — offer not generated.  "
                "'error' = a structural input problem (e.g. no ICP profile) prevented generation."
            ),
        },
        "error_reason": {
            "type": ["string", "null"],
            "description": (
                "Null if status is 'success'.  If status is 'insufficient_data' or 'error', "
                "provides a specific explanation: which threshold was not met, what data was "
                "available, and what minimum is required.  Never a generic message."
            ),
            "example": "insufficient_data: pain_points has 2 entries (minimum 3 required); wins has 1 entry (minimum 3 required). Generation aborted.",
        },
        "offer_type": {
            "type": ["string", "null"],
            "enum": [
                "1:1_coaching",
                "group_programme",
                "mastermind",
                "vip_day",
                "digital_product",
                "retainer",
                None,
            ],
            "description": (
                "The delivery model selected for this offer.  Null if status is not 'success'.  "
                "Uses offer_type_hint if provided; otherwise selected via deterministic signal logic."
            ),
        },
        "offer_title": {
            "type": ["string", "null"],
            "description": (
                "The offer name in ICP language, derived from the highest-frequency pain point "
                "vocabulary.  Null if status is not 'success'.  Must not duplicate any title "
                "in existing_offer_titles."
            ),
        },
        "tagline": {
            "type": ["string", "null"],
            "description": (
                "A single-sentence outcome promise in ICP language.  Specific, not aspirational.  "
                "Null if status is not 'success'."
            ),
            "example": "Build a client pipeline that fills itself — without cold outreach, referral dependency, or posting every day.",
        },
        "description": {
            "type": ["string", "null"],
            "description": (
                "2-3 sentence offer description for a landing page.  Must name the delivery "
                "mechanism, the timeframe, and the primary outcome deliverable.  "
                "Null if status is not 'success'."
            ),
        },
        "transformation_from": {
            "type": ["string", "null"],
            "description": (
                "The current painful state in ICP language — drawn from the highest-frequency "
                "pain point.  Specific and recognisable to the primary ICP.  "
                "Null if status is not 'success'."
            ),
        },
        "transformation_to": {
            "type": ["string", "null"],
            "description": (
                "The desired outcome state in ICP language — drawn from the highest-frequency "
                "goal.  Specific and measurable where possible.  "
                "Null if status is not 'success'."
            ),
        },
        "price_points": {
            "type": "array",
            "description": (
                "2-3 pricing tiers for the offer.  Empty array if status is not 'success'.  "
                "Each tier includes a CI-grounded rationale for the price point."
            ),
            "items": {
                "type": "object",
                "required": ["tier", "price", "deliverables", "rationale"],
                "properties": {
                    "tier": {
                        "type": "string",
                        "description": "The tier name.",
                    },
                    "price": {
                        "type": "number",
                        "description": "The tier price as a number (e.g. 1800 for £1,800).",
                    },
                    "deliverables": {
                        "type": "array",
                        "description": "List of deliverables included in this tier.",
                        "items": {"type": "string"},
                    },
                    "rationale": {
                        "type": "string",
                        "description": (
                            "Why this price is justified — must name a specific CI data point "
                            "(objection, buying trigger, or goal) from the input data."
                        ),
                    },
                },
            },
        },
        "bonuses": {
            "type": "array",
            "description": (
                "1-2 bonuses, each designed to neutralise a specific, named objection from "
                "the CI pool.  Empty array if status is not 'success'."
            ),
            "items": {
                "type": "object",
                "required": ["title", "description", "objection_addressed"],
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Bonus title that signals the problem it solves.",
                    },
                    "description": {
                        "type": "string",
                        "description": "What the bonus delivers and why it matters to the ICP.",
                    },
                    "objection_addressed": {
                        "type": "string",
                        "description": "The specific CI objection this bonus neutralises — including objection text and frequency count.",
                        "example": "Objection: 'I feel uncomfortable asking my clients for referrals' (freq=12).",
                    },
                },
            },
        },
        "guarantee": {
            "type": "object",
            "description": (
                "The offer guarantee, designed around the highest-frequency objection.  "
                "Null object (all fields null) if status is not 'success'."
            ),
            "required": ["type", "terms", "objection_addressed"],
            "properties": {
                "type": {
                    "type": ["string", "null"],
                    "description": "The guarantee type.",
                },
                "terms": {
                    "type": ["string", "null"],
                    "description": "Specific terms including measurable outcome and timeframe.",
                },
                "objection_addressed": {
                    "type": ["string", "null"],
                    "description": "The specific CI objection countered — with objection text and frequency count.",
                },
            },
        },
        "primary_pain_anchors": {
            "type": "array",
            "description": (
                "The top 2-3 pain points by frequency that anchor this offer's design.  "
                "Each entry names the pain point text with its frequency count and a brief "
                "note on how it drives a specific design decision.  Empty array if status "
                "is not 'success'."
            ),
            "items": {
                "type": "string",
                "description": "e.g. \"Pain point text (freq=N) — how it anchors the offer title / transformation / deliverable.\"",
            },
        },
        "primary_win_proof": {
            "type": "array",
            "description": (
                "The top 2-3 client wins by frequency, written as social proof statements "
                "ready for use in offer copy or the human reviewer's editing workflow.  "
                "Includes frequency count.  Empty array if status is not 'success'."
            ),
            "items": {
                "type": "string",
                "description": "e.g. \"Client achieved [outcome] within [timeframe] by [mechanism] (freq=N).\"",
            },
        },
        "generated_at_signal": {
            "type": "string",
            "description": (
                "A brief note summarising the CI data quality used in this generation.  "
                "States the count and top frequency for pain points, wins, objections, and "
                "goals.  If offer type was auto-selected (no hint provided), explains the "
                "selection logic applied.  Flags any data quality concerns (e.g. single-category "
                "concentration, low frequency counts across the board)."
            ),
            "example": "Based on 14 pain points (top freq=21), 9 wins (top freq=11), 11 objections (top freq=19), 8 goals (top freq=16). Offer type 'group_programme' auto-selected: plural ICP language and scalability signals in buying triggers.",
        },
    },
}

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

__all__ = [
    "OFFER_GENERATOR_SYSTEM_PROMPT_V1",
    "OFFER_GENERATOR_OUTPUT_SCHEMA",
    "build_offer_generator_user_prompt",
    "render_offer_generator_system_prompt",
]
