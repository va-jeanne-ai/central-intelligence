"""
Offer Creation prompt — v1 (CI-OFR / M06-3).

Defines the system prompt, user prompt builder, and output schema for the
Offer Creator specialist.  This module is consumed by the Marketing Director
when it needs a CI-grounded, structurally complete new offer designed around
a specific offer type and the highest-frequency CI signals in the pain,
objection, wins, and goals pools.
The Marketing Director pre-loads all enrichment data (offer type, brief, ICP
profile, pain points, wins, objections, goals, existing offers, brand voice)
before invoking this prompt; the specialist does NOT query data itself.
"""

from __future__ import annotations

import json

from app.prompts.context import DEFAULT_PROFILE, PromptProfile, render

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

_OFFER_CREATION_SYSTEM_PROMPT_TEMPLATE_V1 = """\
You are **CI-OFR**, the Offer Creator specialist of {{app_name}} — an AI-powered business intelligence platform for {{vertical}} businesses — operating in **creation mode**.

## Role

You sit inside the Marketing department, reporting to the Marketing Director.  Your sole function is to design structurally complete, CI-grounded {{vertical}} offers that are engineered to convert — not offers that are designed to impress the creator.  Every element of the offer you produce must be traceable to a named CI data point: a pain point, an objection, a win, or a stated goal.  You are NOT a chatbot.  You produce structured JSON output only — no prose, no markdown, no commentary outside the JSON envelope.

## Expertise

You combine three disciplines:

1. **Offer architecture** — An offer is not a list of features.  An offer is a structured promise: a named transformation (from a specific painful state to a specific desired outcome), delivered via a mechanism (the deliverables and format), at a price point justified by the value of the outcome relative to the cost of remaining in the painful state.  Every element of the offer — the title, the tagline, the pricing tiers, the bonuses, the guarantee — is a conversion asset, not a description.  A title that does not speak in the ICP's language is a missed connection.  A bonus that does not address a specific fear is decoration.  A guarantee that does not counter the highest-frequency objection is a missed trust signal.  You engineer every element deliberately.
2. **Conversion psychology** — Pricing tiers are not arbitrary segmentation.  Each tier must have a clear psychological rationale: the entry tier removes the price-risk barrier; the mid-tier is designed to be the obvious choice (it has the highest perceived value-to-price ratio); the premium tier exists for the segment that wants the most certainty and will pay for access or proximity.  Bonuses must address a specific fear or friction point — they are pre-emptive objection handling, not upsell add-ons.  Urgency elements must be genuine: cohort dates, limited spots, or real deadlines — not manufactured scarcity, which sophisticated buyers see through immediately and which destroys trust.  A guarantee that feels like a marketing tactic rather than a genuine risk reversal will be dismissed by the exact buyers who need the most reassurance.
3. **CI intelligence grounding** — Every naming, pricing, and structural decision must draw from the CI pool.  The offer title and tagline must use pain and goal vocabulary drawn directly from the ICP's own language — not clever wordplay or abstract outcome promises that obscure rather than clarify what the offer delivers.  Pricing rationale must reference the ICP's buying decision context (pain intensity, outcome urgency, investment readiness) rather than arbitrary market positioning.  Copy angles for marketing the offer must be anchored in the highest-frequency, highest-urgency CI signals — because the best marketing for an offer is a direct conversation with the prospect's own problem, in their own language.

## Data Inputs

The Marketing Director provides all data pre-loaded.  You receive:

- **offer_type** — One of: "1:1_coaching", "group_programme", "mastermind", "vip_day", "digital_product", "retainer".
- **offer_brief** — Optional: specific constraints, positioning direction, or context from the Marketing Director.  If absent, design the offer from the CI data alone.
- **icp_primary** — The primary ICP segment: segment name, description, demographics, pain summary, buying triggers.
- **pain_points** — CI pain points with text, category, and frequency_count.
- **wins** — Client wins and success stories with text, category, and frequency_count.
- **objections** — Common sales objections with text, category, and frequency_count.
- **goals** — Client goals with text, category, and frequency_count.
- **existing_offers** — Optional: list of existing offers (title, price_points) to differentiate from.  If provided, ensure the new offer is positioned distinctly — different entry point, different delivery mechanism, different primary promise, or different audience segment.
- **brand_voice** — Optional: brand tone description.  If absent, default to: direct, outcome-led, grounded in the client's experience rather than the coach's methodology.

## Creation Mandate

- **Every element is CI-anchored.**  Title, tagline, transformation statement, each pricing tier's rationale, each bonus's objection address, the guarantee's objection target, and each copy angle must cite a specific CI data point — or it fails quality review.  Generic offer design is rejected.
- **Pricing tiers require explicit rationale.**  Do not set prices arbitrarily.  Each tier's price must be justified by the value delivered relative to the ICP's pain intensity and outcome urgency.  The entry tier should remove the largest price-related objection.  The mid-tier should feel like the obvious choice.  The premium tier should serve the highest-intent, highest-urgency segment.
- **Bonuses are objection-handling tools, not random add-ons.**  Every bonus must address a specific, named fear or friction point from the objections pool that would otherwise prevent conversion.  A bonus that cannot be linked to a named objection is not included.
- **The guarantee directly counters the highest-frequency objection.**  Identify the most common fear in the CI objections pool and design a guarantee that makes that fear irrational.  The guarantee terms must be specific — not "100% satisfaction guaranteed" (which is meaningless), but "full refund if you do not achieve [specific measurable outcome] within [specific timeframe]".
- **The offer name speaks in ICP language.**  The title and tagline must use vocabulary drawn from the ICP's pain and goal language — the words they use in calls, applications, and messages — not the coach's internal framing or aspirational positioning language.  Test every word in the title: would the primary ICP recognise their own situation in it?
- **Copy angles are CI-grounded, not feature-led.**  Produce three headline angles for marketing this offer.  Each angle must be grounded in a distinct CI data point: a pain point, a client win, or an objection reframe.  The angle types are: pain-agitation (names the problem and makes it feel urgent), outcome-proof (leads with a specific client result), and objection-reframe (takes the most common hesitation and turns it into a reason to act).

## Output Contract

You MUST return a single JSON object.  No prose before or after.  No markdown fences.  No explanations.  Only the JSON object.

The object must conform exactly to the output schema described below.  Every field is required unless explicitly marked optional.

## Example Output

The following illustrates the expected structure and writing quality.  All values are fabricated for illustration only — replace every field with real generated content:

```json
{
  "offer_title": "The Client Clarity Intensive",
  "tagline": "Stop taking every client who'll pay you — and start attracting the ones who'll stay.",
  "offer_type": "vip_day",
  "ci_anchor": "Pain point: 'I keep taking on clients who drain me because I can't afford to say no' (freq=17) — the highest-frequency emotional and financial pain in the CI pool, present in the primary ICP's pain summary and buying triggers.",
  "transformation_statement": "From saying yes to every client and ending each month exhausted and underearning, to a clear client criteria, a premium positioning, and the confidence to charge what the work is worth.",
  "price_points": [
    {
      "tier": "Foundation",
      "price": 1200,
      "deliverables": [
        "4-hour virtual intensive with pre-work audit",
        "ICP clarity framework and ideal client filter",
        "Positioning statement rewrite (reviewed async within 48 hours)",
        "30-day action plan with accountability check-in"
      ],
      "rationale": "Entry tier is priced at £1,200 to clear the primary objection 'I can't justify a large investment right now' (freq=12) — it delivers the core transformation (clarity and positioning) without the commitment of an in-person day, giving the primary ICP a risk-adjusted first step."
    },
    {
      "tier": "Full Day",
      "price": 2800,
      "deliverables": [
        "7-hour in-person or virtual intensive (client's choice)",
        "Pre-work audit and discovery call (60 minutes)",
        "ICP clarity framework and ideal client filter",
        "Positioning statement, bio, and intro email rewrite",
        "Offer architecture review and pricing restructure",
        "60-day follow-up call for implementation review"
      ],
      "rationale": "Mid-tier at £2,800 is the designed optimal choice: it adds the offer restructure and the follow-up call — the two deliverables that address the highest-frequency secondary goal 'raise my prices without losing my best clients' (freq=11). The pricing lands below the primary ICP's £3,000 mental threshold identified in buying trigger data, making it feel accessible relative to the transformation scope."
    },
    {
      "tier": "VIP + Implementation",
      "price": 4500,
      "deliverables": [
        "Full Day tier (all deliverables)",
        "90-day Voxer implementation support",
        "Two additional 60-minute review calls",
        "Done-for-you rewrite of the sales page or offer deck"
      ],
      "rationale": "Premium tier at £4,500 targets the highest-urgency segment — ICP profiles with 'I need to make this change fast and I need to know it'll stick' as a buying trigger. The Voxer support and done-for-you deliverable address the objection 'I'll do the intensive but then lose momentum implementing it' (freq=8) — the primary fear that stops the highest-intent buyers from choosing the mid-tier."
    }
  ],
  "bonuses": [
    {
      "title": "The 'Not My Client' Script",
      "description": "A word-for-word script for declining enquiries from prospects outside the ideal client criteria — including how to redirect them without burning the relationship.",
      "objection_addressed": "Objection: 'I feel guilty turning people away and I don't know how to say no gracefully' (freq=9) — this bonus removes the social anxiety barrier to implementing the new client criteria."
    },
    {
      "title": "Premium Pricing Calculator",
      "description": "A guided spreadsheet that calculates a defensible price point based on transformation value, delivery cost, and ICP outcome urgency — with three worked examples from similar coaching niches.",
      "objection_addressed": "Objection: 'I don't know how to justify a higher price without feeling like I'm overcharging' (freq=14) — this bonus gives a logical framework that replaces the emotional discomfort of price-setting with a structured rationale."
    }
  ],
  "guarantee": {
    "type": "Outcome-linked refund guarantee",
    "terms": "If you complete the intensive, implement the positioning framework, and do not receive at least one enquiry from an ideal-fit prospect within 60 days, we will refund your investment in full — no questions asked.",
    "objection_addressed": "Objection: 'I've invested in coaching before and not seen results' (freq=19) — the most common and highest-frequency trust barrier in the CI pool. This guarantee makes the investment effectively risk-free for the primary ICP, removing the single biggest conversion barrier."
  },
  "urgency_element": {
    "type": "Cohort-based availability",
    "description": "The Full Day and VIP tiers are limited to 4 clients per calendar month to protect delivery quality. Spots are allocated on a first-deposit basis and typically fill 2-3 weeks in advance.",
    "is_genuine": true
  },
  "copy_angles": [
    {
      "angle_type": "pain-agitation",
      "headline_text": "Still saying yes to clients who pay you late, demand more than agreed, and leave you wondering why you started this business?"
    },
    {
      "angle_type": "outcome-proof",
      "headline_text": "In one day, [CLIENT NAME] went from dreading her Monday enquiry inbox to turning away two clients who weren't the right fit — and raised her prices by 40%."
    },
    {
      "angle_type": "objection-reframe",
      "headline_text": "You don't need more clients. You need fewer, better ones — and a clear way to tell the difference before they book."
    }
  ],
  "positioning_notes": "The existing portfolio contains a 90-Day Revenue Accelerator (priced at £3,500 mid-tier) that addresses revenue growth broadly. The Client Clarity Intensive is positioned upstream of that offer — it addresses the audience who are not yet ready to focus on revenue growth because they first need to solve who they serve and at what price. This creates a natural upsell path: Intensive → Revenue Accelerator, rather than competing for the same buyer."
}
```\
"""



def render_offer_creation_system_prompt(profile: PromptProfile | None = None) -> str:
    """Render the offer creation system prompt for a specific instance profile."""
    return render(_OFFER_CREATION_SYSTEM_PROMPT_TEMPLATE_V1, profile)


# Rendered with the frozen defaults (the pre-Phase-1 literals) so importers and
# the parity snapshot see stable text regardless of process state.
OFFER_CREATION_SYSTEM_PROMPT_V1 = render_offer_creation_system_prompt(DEFAULT_PROFILE)

# ---------------------------------------------------------------------------
# User prompt builder
# ---------------------------------------------------------------------------


def build_offer_creation_user_prompt(data: dict) -> str:  # noqa: PLR0912
    """Format pre-loaded Marketing Director enrichment data into the offer creation prompt.

    Parameters
    ----------
    data:
        A dict with keys: ``offer_type``, ``offer_brief``, ``icp_primary``,
        ``pain_points``, ``wins``, ``objections``, ``goals``,
        ``existing_offers``, ``brand_voice``.

    Returns
    -------
    str
        The fully-rendered user prompt ready to send to the model.
    """

    offer_type = data.get("offer_type") or "1:1_coaching"
    offer_brief = data.get("offer_brief") or ""
    brand_voice = data.get("brand_voice") or (
        "Direct, outcome-led, grounded in the client's experience rather than "
        "the coach's methodology. Warm but specific — never vague or aspirational."
    )

    lines: list[str] = [
        "## Creation Context",
        "",
        f"- Offer type: {offer_type}",
        f"- Brand voice: {brand_voice}",
    ]
    if offer_brief:
        lines.append(f"- Brief / constraints from Marketing Director: {offer_brief}")
    lines.append("")

    # -- Primary ICP ----------------------------------------------------------
    icp_primary: dict = data.get("icp_primary") or {}
    if icp_primary:
        lines += [
            "## Primary ICP Profile",
            "",
        ]
        segment = icp_primary.get("segment") or "Unknown"
        description = icp_primary.get("description") or ""
        demographics = icp_primary.get("demographics") or ""
        pain_summary = icp_primary.get("pain_summary") or ""
        buying_triggers = icp_primary.get("buying_triggers") or ""
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
        lines += ["## Primary ICP Profile", "", "(No ICP data available.)", ""]

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

    # -- Existing offers (optional) ------------------------------------------
    existing_offers: list[dict] = data.get("existing_offers") or []
    if existing_offers:
        lines += [
            "## Existing Offers to Differentiate From",
            "",
        ]
        for i, existing in enumerate(existing_offers, start=1):
            title = existing.get("title") or "Untitled"
            price_points: list[dict] = existing.get("price_points") or []
            price_summary = ", ".join(
                f"{t.get('tier', 'Tier')}: £{t.get('price', 0):,}"
                for t in sorted(price_points, key=lambda t: t.get("price", 0))
            ) if price_points else "No price data"
            lines.append(f"{i}. **{title}** — {price_summary}")
        lines.append("")

    # -- Output instructions --------------------------------------------------
    lines += [
        "---",
        "",
        "## Your Task",
        "",
        f"Using all of the intelligence above, design a complete {offer_type} offer and return it as a single JSON object conforming to the output schema.",
        "",
        "Creation requirements:",
        "- offer_title and tagline must use vocabulary drawn directly from the ICP's pain and goal language — the words they use in calls and applications. Test every word: would the primary ICP recognise their own situation in it? Avoid abstract aspirational language.",
        "- ci_anchor must name the single CI data point (pain point, objection, or win) with its frequency count that is the primary design driver for the entire offer.",
        "- transformation_statement must be a 'from X to Y' sentence using the ICP's own language for both the current painful state and the desired outcome — drawn from the pain_points and goals pools.",
        f"- Design 2-3 pricing tiers appropriate for the '{offer_type}' format. Each tier must have:",
        "  - A clear rationale explaining why this price is justified by the value delivered relative to the ICP's pain intensity and outcome urgency.",
        "  - Deliverables that map to specific, named ICP goals from the CI pool.",
        "  - The entry tier must clear the highest-frequency price-related objection.",
        "  - The mid-tier must be the obvious choice (highest perceived value-to-price ratio).",
        "  - The premium tier (if included) must serve the highest-urgency segment and address the 'I'll lose momentum implementing it' class of objection.",
        "- Design 2-3 bonuses. Each bonus MUST:",
        "  - Address a specific, named objection from the CI pool (include frequency count).",
        "  - Have a title that signals the problem it solves — not a clever name that obscures the function.",
        "- guarantee must directly counter the highest-frequency objection in the CI pool. State specific terms (measurable outcome + timeframe) — not a generic satisfaction guarantee.",
        "- urgency_element must be genuine (cohort dates, limited delivery capacity, real deadlines). Set is_genuine: true only if the scarcity is real and defensible. Never manufacture urgency.",
        "- copy_angles must produce exactly 3 headline angles: one pain-agitation, one outcome-proof (drawing from the most resonant win in the CI pool), one objection-reframe (taking the most common hesitation and reframing it as a reason to act). Each angle must be grounded in a named CI data point.",
        "- positioning_notes: if existing_offers were provided, explain how this offer is positioned distinctly — different entry point, mechanism, promise, or audience segment. If no existing offers, state how this offer occupies a specific position in the market for this ICP.",
        "",
        "Output format — return ONLY this JSON object, nothing else:",
        "",
        json.dumps(
            {
                "offer_title": "The offer name in ICP language — not the coach's internal framing.",
                "tagline": "One-sentence outcome promise in ICP language — specific, not aspirational.",
                "offer_type": offer_type,
                "ci_anchor": "The primary CI data point (pain point/objection/win with frequency count) driving the core design of this offer.",
                "transformation_statement": "From [specific painful state in ICP language] to [specific desired outcome in ICP language].",
                "price_points": [
                    {
                        "tier": "Tier name",
                        "price": 0,
                        "deliverables": ["Deliverable 1", "Deliverable 2"],
                        "rationale": "Why this price is justified by the value delivered relative to the ICP's pain intensity and outcome urgency — name the specific CI data point.",
                    }
                ],
                "bonuses": [
                    {
                        "title": "Bonus title that signals the problem it solves.",
                        "description": "What the bonus delivers and why it matters to the ICP.",
                        "objection_addressed": "The specific CI objection this bonus neutralises — name the objection text and frequency count.",
                    }
                ],
                "guarantee": {
                    "type": "Guarantee type (e.g. outcome-linked refund, results guarantee).",
                    "terms": "Specific terms: measurable outcome + timeframe — not a generic satisfaction guarantee.",
                    "objection_addressed": "The specific CI objection this guarantee directly counters — name the objection text and frequency count.",
                },
                "urgency_element": {
                    "type": "Type of urgency (cohort availability, limited spots, deadline).",
                    "description": "The genuine urgency mechanism and how it is communicated.",
                    "is_genuine": True,
                },
                "copy_angles": [
                    {
                        "angle_type": "pain-agitation | outcome-proof | objection-reframe",
                        "headline_text": "The headline copy for this angle, grounded in a specific CI data point.",
                    }
                ],
                "positioning_notes": "How this offer is positioned distinctly from existing offers (if provided) or in the market for this ICP.",
            },
            indent=2,
        ),
        "",
        "Replace all placeholder strings with the actual generated offer content.",
        "Return ONLY the JSON object — no other text.",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Output schema (documentation / validation reference)
# ---------------------------------------------------------------------------

OFFER_CREATION_OUTPUT_SCHEMA: dict = {
    "type": "object",
    "description": (
        "A structurally complete, CI-grounded coaching or consulting offer "
        "produced by the Offer Creator specialist (CI-OFR) in creation mode.  "
        "Every element is anchored to a named CI data point.  Consumed by the "
        "Marketing Director for review and deployment."
    ),
    "required": [
        "offer_title",
        "tagline",
        "offer_type",
        "ci_anchor",
        "transformation_statement",
        "price_points",
        "bonuses",
        "guarantee",
        "urgency_element",
        "copy_angles",
        "positioning_notes",
    ],
    "properties": {
        "offer_title": {
            "type": "string",
            "description": (
                "The name of the offer, written in ICP language — vocabulary drawn "
                "from the pain points and goals in the CI pool.  Must pass the test: "
                "would the primary ICP recognise their own situation in this title?"
            ),
        },
        "tagline": {
            "type": "string",
            "description": (
                "A single-sentence outcome promise in ICP language.  Specific, not "
                "aspirational.  Must describe the transformation from a named painful "
                "state to a named desired outcome — not a motivational statement."
            ),
            "example": "Stop taking every client who'll pay you — and start attracting the ones who'll stay.",
        },
        "offer_type": {
            "type": "string",
            "enum": [
                "1:1_coaching",
                "group_programme",
                "mastermind",
                "vip_day",
                "digital_product",
                "retainer",
            ],
            "description": "The delivery model for this offer.  Must match the offer_type provided in the creation context.",
        },
        "ci_anchor": {
            "type": "string",
            "description": (
                "The primary CI data point driving the core design of this offer.  "
                "Names the most strategically important pain point, objection, or win "
                "from the CI pool — with frequency count.  This is the editorial "
                "rationale for the offer's existence."
            ),
            "example": "Pain point: 'I keep taking on clients who drain me because I can't afford to say no' (freq=17).",
        },
        "transformation_statement": {
            "type": "string",
            "description": (
                "'From X to Y' statement in ICP language.  X is the current painful "
                "state drawn from the pain_points pool.  Y is the desired outcome drawn "
                "from the goals pool.  Both must be specific and recognisable to the "
                "primary ICP — not generic transformation language."
            ),
            "example": "From saying yes to every client and ending each month exhausted and underearning, to a clear client criteria, a premium positioning, and the confidence to charge what the work is worth.",
        },
        "price_points": {
            "type": "array",
            "description": (
                "2-3 pricing tiers for the offer.  Each tier has a justified price, "
                "deliverables mapped to CI goals, and a rationale grounded in the "
                "ICP's pain intensity and outcome urgency."
            ),
            "minItems": 2,
            "maxItems": 3,
            "items": {
                "type": "object",
                "required": ["tier", "price", "deliverables", "rationale"],
                "properties": {
                    "tier": {
                        "type": "string",
                        "description": "The tier name (e.g. 'Foundation', 'Full Day', 'VIP + Implementation').",
                    },
                    "price": {
                        "type": "number",
                        "description": "The tier price as a number (e.g. 1200 for £1,200).",
                        "example": 2800,
                    },
                    "deliverables": {
                        "type": "array",
                        "description": "List of deliverables included in this tier.  Each deliverable should map to a named ICP goal.",
                        "items": {"type": "string"},
                        "minItems": 2,
                    },
                    "rationale": {
                        "type": "string",
                        "description": (
                            "Explanation of why this price is justified relative to the value "
                            "delivered and the ICP's pain intensity and outcome urgency.  Must "
                            "name a specific CI data point (objection, goal, or buying trigger) "
                            "that grounds the pricing decision."
                        ),
                    },
                },
            },
        },
        "bonuses": {
            "type": "array",
            "description": (
                "2-3 bonuses, each designed to neutralise a specific, named objection "
                "from the CI pool.  Bonuses are pre-emptive objection handling tools — "
                "not add-ons or upsell assets."
            ),
            "minItems": 2,
            "maxItems": 3,
            "items": {
                "type": "object",
                "required": ["title", "description", "objection_addressed"],
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Bonus title that signals the problem it solves — not a clever name that obscures the function.",
                    },
                    "description": {
                        "type": "string",
                        "description": "What the bonus delivers, how it is consumed, and why it matters to the primary ICP.",
                    },
                    "objection_addressed": {
                        "type": "string",
                        "description": (
                            "The specific CI objection this bonus neutralises.  Must name "
                            "the objection text and frequency count.  A bonus without a "
                            "named objection fails quality review."
                        ),
                        "example": "Objection: 'I don't know how to justify a higher price without feeling like I'm overcharging' (freq=14).",
                    },
                },
            },
        },
        "guarantee": {
            "type": "object",
            "description": (
                "The offer guarantee, designed to directly counter the highest-frequency "
                "objection in the CI pool.  Terms must be specific and measurable — not "
                "a generic satisfaction guarantee."
            ),
            "required": ["type", "terms", "objection_addressed"],
            "properties": {
                "type": {
                    "type": "string",
                    "description": "The guarantee type (e.g. 'Outcome-linked refund guarantee', 'Results guarantee', 'Progress guarantee').",
                },
                "terms": {
                    "type": "string",
                    "description": (
                        "The specific terms of the guarantee.  Must include a measurable "
                        "outcome and a defined timeframe.  Not a generic satisfaction promise."
                    ),
                    "example": "Full refund if you do not achieve [specific measurable outcome] within [specific timeframe], having completed the programme requirements.",
                },
                "objection_addressed": {
                    "type": "string",
                    "description": (
                        "The specific CI objection this guarantee directly counters.  "
                        "Must name the objection text and frequency count."
                    ),
                    "example": "Objection: 'I've invested in coaching before and not seen results' (freq=19).",
                },
            },
        },
        "urgency_element": {
            "type": "object",
            "description": (
                "A genuine urgency mechanism for this offer.  Must be real — "
                "cohort availability, limited delivery capacity, or an actual deadline.  "
                "Manufactured scarcity destroys trust with sophisticated buyers."
            ),
            "required": ["type", "description", "is_genuine"],
            "properties": {
                "type": {
                    "type": "string",
                    "description": "Type of urgency (e.g. 'Cohort-based availability', 'Limited spots per month', 'Intake deadline').",
                },
                "description": {
                    "type": "string",
                    "description": "How the urgency mechanism works, what the limit is, and how it is communicated to prospects.",
                },
                "is_genuine": {
                    "type": "boolean",
                    "description": "True if the scarcity or deadline is operationally real and defensible.  False if it is manufactured.",
                },
            },
        },
        "copy_angles": {
            "type": "array",
            "description": (
                "Exactly 3 headline angles for marketing this offer — one per angle type: "
                "pain-agitation, outcome-proof, and objection-reframe.  Each angle must "
                "be grounded in a named CI data point and written in ICP language."
            ),
            "minItems": 3,
            "maxItems": 3,
            "items": {
                "type": "object",
                "required": ["angle_type", "headline_text"],
                "properties": {
                    "angle_type": {
                        "type": "string",
                        "enum": ["pain-agitation", "outcome-proof", "objection-reframe"],
                        "description": (
                            "The psychological angle this headline deploys.  "
                            "pain-agitation: names the problem and makes it feel urgent.  "
                            "outcome-proof: leads with a specific client result from the CI wins pool.  "
                            "objection-reframe: takes the most common hesitation and reframes it as a reason to act."
                        ),
                    },
                    "headline_text": {
                        "type": "string",
                        "description": (
                            "The headline copy for this angle.  Must be grounded in a specific "
                            "CI data point — the pain point text, the win story, or the "
                            "objection being reframed.  Specific over clever."
                        ),
                    },
                },
            },
        },
        "positioning_notes": {
            "type": "string",
            "description": (
                "How this offer is positioned distinctly from existing offers in the "
                "portfolio (if provided) — different entry point, delivery mechanism, "
                "primary promise, or audience segment.  If no existing offers were "
                "provided, describes how this offer occupies a specific, defensible "
                "position in the market for this ICP."
            ),
        },
    },
}

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

__all__ = [
    "OFFER_CREATION_SYSTEM_PROMPT_V1",
    "OFFER_CREATION_OUTPUT_SCHEMA",
    "build_offer_creation_user_prompt",
    "render_offer_creation_system_prompt",
]
