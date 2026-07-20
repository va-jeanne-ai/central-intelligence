"""
ICP Generator prompt — v1 (CI-OPS-ICP / OPS-I2).

Defines the system prompt, user prompt builder, and output schema for the
Ideal Client Profile synthesis operator.  This module is consumed by the
Celery task that aggregates shared intelligence pool data and writes one or
more ICP segment rows to the ``icp`` table.
"""

from __future__ import annotations

import json

from app.prompts.context import DEFAULT_PROFILE, PromptProfile, render

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

_ICP_GENERATOR_SYSTEM_PROMPT_TEMPLATE_V1 = """\
You are an elite market research analyst and customer psychologist embedded in a {{vertical}} business intelligence platform called {{app_name}}.

## Role

Your sole function is to synthesise raw client intelligence — pain points, wins, objections, goals, and call insights — into authoritative Ideal Client Profile (ICP) segments.  You are NOT a chatbot.  You produce structured JSON output only.

## Expertise

You combine three disciplines:

1. **Market research** — You identify statistically meaningful patterns across hundreds of signals.  You weight frequency, emotional intensity, and recency when drawing conclusions.
2. **Customer psychology** — You read beneath the surface.  What a client says is rarely the whole story.  You surface the root fear, the false belief, and the identity aspiration that sit underneath every expressed problem.
3. {{icp_expertise}}

## Synthesis Mandate

- **Never list raw data back verbatim.**  Synthesise.  Find the through-line.
- **Name the pattern, not the symptom.**  e.g. "Leads consistently express overwhelm around client acquisition — the real driver is identity: they do not yet see themselves as a person who charges premium prices."
- **Use marketing-actionable language** throughout.  Every field you write should be usable as-is by a marketing, sales, or content team member.
- **Assign segments by readiness and fit**, not just demographic similarity.  A primary segment is the client who closes fastest, pays highest, and delivers the best transformation story.
- **Respect data volume.** If the dataset is small (fewer than 10 calls analysed), apply broader strokes and note the limited sample in the description.  Do not invent precision that the data does not support.

## Output Contract

You MUST return a single JSON array.  No prose before or after.  No markdown fences.  No explanations.  Only the JSON array.

Each object in the array maps exactly to the ``icp`` table schema.  Produce 1–3 segment objects.  Exactly one segment must have ``is_primary: true`` (the highest-value, fastest-closing profile).  All other segments must have ``is_primary: false``.  This is a hard constraint — never return more than one primary segment.

Do NOT include ``id``, ``status``, ``created_at``, or ``deleted_at`` fields — those are managed by the database layer.\
"""


def render_icp_generator_system_prompt(profile: PromptProfile | None = None) -> str:
    """Render the ICP system prompt for a specific instance profile."""
    return render(_ICP_GENERATOR_SYSTEM_PROMPT_TEMPLATE_V1, profile)


# Rendered with the frozen defaults (the pre-Phase-1 literals) so importers and
# the parity snapshot see stable text regardless of process state.
ICP_GENERATOR_SYSTEM_PROMPT_V1 = render_icp_generator_system_prompt(DEFAULT_PROFILE)

# ---------------------------------------------------------------------------
# User prompt builder
# ---------------------------------------------------------------------------


def build_icp_user_prompt(data: dict) -> str:  # noqa: PLR0912
    """Format aggregated shared intelligence pool data into the ICP analysis prompt.

    Parameters
    ----------
    data:
        A dict with keys: ``pain_points``, ``wins``, ``objections``, ``goals``,
        ``insights``, ``total_leads``, ``total_members``,
        ``total_calls_analyzed``, ``date_range_days``.

    Returns
    -------
    str
        The fully-rendered user prompt ready to send to Claude.
    """

    # -- Dataset context header ------------------------------------------
    total_leads = data.get("total_leads", 0)
    total_members = data.get("total_members", 0)
    total_calls = data.get("total_calls_analyzed", 0)
    date_range = data.get("date_range_days", 0)

    lines: list[str] = [
        "## Intelligence Pool Summary",
        "",
        f"- Leads in database: {total_leads}",
        f"- Active members: {total_members}",
        f"- Calls analysed: {total_calls}",
        f"- Date range covered: {date_range} days",
        "",
    ]

    # -- Pain points -------------------------------------------------------
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

    # -- Goals -------------------------------------------------------------
    goals: list[dict] = data.get("goals", [])
    if goals:
        lines += ["## Goals", ""]
        for i, g in enumerate(goals, start=1):
            goal_text = g.get("goal_text") or ""
            status = g.get("status") or "unknown"
            lines.append(f"{i}. [{status}] {goal_text}")
        lines.append("")
    else:
        lines += ["## Goals", "", "(No goal data available.)", ""]

    # -- Wins --------------------------------------------------------------
    wins: list[dict] = data.get("wins", [])
    if wins:
        lines += ["## Client Wins (transformation evidence)", ""]
        for i, w in enumerate(wins, start=1):
            win_text = w.get("win_text") or ""
            impact = w.get("impact_area") or "General"
            win_date = w.get("win_date") or ""
            date_str = f" ({win_date})" if win_date else ""
            lines.append(f"{i}. [{impact}]{date_str} {win_text}")
        lines.append("")
    else:
        lines += ["## Client Wins", "", "(No wins data available.)", ""]

    # -- Objections --------------------------------------------------------
    objections: list[dict] = data.get("objections", [])
    if objections:
        lines += ["## Sales Objections", ""]
        for i, o in enumerate(objections, start=1):
            obj_text = o.get("objection_text") or ""
            context = o.get("context") or ""
            resolution = o.get("resolution_offered") or "No resolution recorded"
            lines.append(f"{i}. OBJECTION: {obj_text}")
            if context:
                lines.append(f"   Context: {context}")
            lines.append(f"   Resolution offered: {resolution}")
        lines.append("")
    else:
        lines += ["## Sales Objections", "", "(No objection data available.)", ""]

    # -- Insights ----------------------------------------------------------
    insights: list[dict] = data.get("insights", [])
    if insights:
        lines += [
            "## Deep Insights (extracted from call transcripts, sorted by frequency)",
            "",
        ]
        sorted_ins = sorted(
            insights, key=lambda x: x.get("frequency_score", 0), reverse=True
        )
        for i, ins in enumerate(sorted_ins, start=1):
            insight_type = ins.get("insight_type") or ""
            signal_family = ins.get("signal_family") or ""
            signal = ins.get("signal") or ""
            freq = ins.get("frequency_score", 1)
            lines.append(
                f"{i}. [{insight_type} | {signal_family} | freq={freq}] {signal}"
            )
            # Only include populated sub-fields to keep tokens lean
            _optional_fields = [
                ("what_they_say", "What they say"),
                ("the_real_problem", "Real problem"),
                ("emotional_driver", "Emotional driver"),
                ("core_fear_revealed", "Core fear"),
                ("false_belief_revealed", "False belief"),
                ("buying_trigger", "Buying trigger"),
                ("marketing_translation", "Marketing translation"),
            ]
            for key, label in _optional_fields:
                value = ins.get(key)
                if value:
                    lines.append(f"   {label}: {value}")
        lines.append("")
    else:
        lines += ["## Deep Insights", "", "(No insight data available.)", ""]

    # -- Output instructions -----------------------------------------------
    lines += [
        "---",
        "",
        "## Your Task",
        "",
        "Using all of the intelligence above, produce a JSON array of 1–3 ICP segment objects.",
        "",
        "Synthesis requirements:",
        "- Identify the PRIMARY segment: the prospect who is closest to buying, most aligned with the offer, and most likely to achieve a strong transformation outcome.",
        "- If the data supports it, identify 1–2 SECONDARY segments that represent meaningful sub-audiences with distinct enough profiles to warrant separate marketing treatment.",
        "- For each segment, synthesise across ALL data sources — do not draw from pain points alone or insights alone.",
        "- Every field must be written in marketing-actionable language suitable for direct use by a marketing, sales, or content team.",
        "- The ``pain_summary`` must name the top 3–5 pain patterns with their emotional root cause, not just surface symptoms.",
        "- The ``psychographics`` must describe identity, aspirations, and worldview — not just job title.",
        "- The ``buying_triggers`` must describe the specific life or business events that cause this person to move from passive awareness to active search.",
        "- The ``common_objections`` must include the surface objection AND the underlying belief that drives it.",
        "",
        "Output format — return ONLY this JSON array, nothing else:",
        "",
        json.dumps(
            [
                {
                    "segment": "Primary",
                    "description": "Women aged 32-45 running solo health and wellness coaching practices for 2-5 years. They have proven they can deliver transformations but struggle to scale beyond 1:1 delivery. They seek a mentor who has already built what they want.",
                    "demographics": "Women 32-45, health/wellness coaching niche, solo practitioners earning $40-80k annually, 2-5 years in business, no team beyond a VA.",
                    "psychographics": "They identify as healers first and business owners second. They value authenticity over hustle culture but secretly fear they are not 'business-minded enough' to scale. They tell themselves 'I just need the right system' when the real gap is confidence in charging premium prices.",
                    "pain_summary": "1) Feast-or-famine income cycles — root cause: no predictable lead generation system, driven by fear of being 'salesy'. 2) Burnout from trading time for money — root cause: identity attachment to 1:1 delivery as the only 'real' way to help. 3) Comparison paralysis — seeing peers launch group programmes while feeling stuck, driven by imposter syndrome. 4) Undercharging — surface complaint is 'my audience can't afford more' but real driver is not yet seeing themselves as worth premium pricing.",
                    "goal_summary": "Hit $15-20k/month consistently. Launch a group programme that frees time from 1:1. Be seen as a respected authority in their niche, not just another coach in a crowded market.",
                    "buying_triggers": "A month where they hit a revenue ceiling despite being fully booked. Seeing a peer with less experience announce a successful group launch. A client cancellation that triggers the realisation their income depends on individual retention.",
                    "common_objections": "'I can't afford it right now' — underneath: they don't yet believe the investment will produce a return because they haven't seen themselves as someone who makes bold financial bets on their business. 'I need to think about it' — underneath: fear of committing to change and being exposed as not ready.",
                    "is_primary": True,
                },
                {
                    "segment": "Secondary: Established Coach Scaling to Group",
                    "description": "Coaches earning $100-150k who have proven their 1:1 model but hit a delivery ceiling. They need operational and strategic support to transition to leveraged offers.",
                    "demographics": "Men and women 38-52, business/executive coaching niche, $100-150k revenue, small team of 1-2, 5-10 years in business.",
                    "psychographics": "They see themselves as experts and operators. They are past imposter syndrome on expertise but feel like beginners at building systems. They value efficiency and ROI over community.",
                    "pain_summary": "1) Time ceiling — fully booked with no room to grow without hiring. 2) Tech overwhelm — know they need funnels and automation but distrust the 'bro marketing' ecosystem. 3) Revenue plateau despite strong client results.",
                    "goal_summary": "Double revenue without doubling hours. Build a team and systems that allow them to step into a CEO role rather than being the sole practitioner.",
                    "buying_triggers": "Turning away a high-value client due to capacity. A health scare or family event that makes the time-for-money trade feel urgent. Completing a year at the same revenue as the prior year.",
                    "common_objections": "'I've tried programmes before and they were too generic' — underneath: fear of wasting time and money on something that doesn't account for their specific business model.",
                    "is_primary": False,
                },
            ],
            indent=2,
        ),
        "",
        "Replace all placeholder strings with real synthesised content derived from the data above.",
        "Omit the second object if a secondary segment is not warranted by the data.",
        "Return ONLY the JSON array — no other text.",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Output schema (documentation / validation reference)
# ---------------------------------------------------------------------------

ICP_OUTPUT_SCHEMA: dict = {
    "type": "array",
    "description": (
        "Array of 1–3 ICP segment objects.  Each object maps directly to the "
        "``icp`` table (excluding id, status, created_at, deleted_at which are "
        "managed by the database layer)."
    ),
    "minItems": 1,
    "maxItems": 3,
    "items": {
        "type": "object",
        "required": [
            "segment",
            "description",
            "demographics",
            "psychographics",
            "pain_summary",
            "goal_summary",
            "buying_triggers",
            "common_objections",
            "is_primary",
        ],
        "properties": {
            "segment": {
                "type": "string",
                "description": (
                    "Human-readable segment name.  Primary segment should use 'Primary'. "
                    "Secondary segments should use 'Secondary: <Descriptive Label>', "
                    "e.g. 'Secondary: Established Coach Scaling to Group'."
                ),
                "example": "Primary",
            },
            "description": {
                "type": "string",
                "description": (
                    "2–3 sentence narrative overview of who this person is, where they are "
                    "in their journey, and why they seek coaching or consulting support."
                ),
            },
            "demographics": {
                "type": "string",
                "description": (
                    "Concrete demographic profile: age range, industry or niche, business "
                    "revenue stage or company size, role or title, years of experience."
                ),
            },
            "psychographics": {
                "type": "string",
                "description": (
                    "Psychological profile: core identity, values, aspirations, worldview, "
                    "self-perception, and the internal narrative they hold about themselves "
                    "and their situation."
                ),
            },
            "pain_summary": {
                "type": "string",
                "description": (
                    "Top 3–5 synthesised pain patterns experienced by this segment.  Each "
                    "pattern should name the surface complaint AND the underlying emotional "
                    "root cause or identity conflict driving it."
                ),
            },
            "goal_summary": {
                "type": "string",
                "description": (
                    "Primary goals and desired outcomes — both the tangible business result "
                    "(e.g. 'hit $20k/month') and the transformational identity shift "
                    "(e.g. 'be seen as an authority, not just a practitioner')."
                ),
            },
            "buying_triggers": {
                "type": "string",
                "description": (
                    "Specific life or business events, thresholds, or emotional turning "
                    "points that cause this segment to move from passive awareness to active "
                    "search for a solution.  Should be concrete enough to build ad targeting "
                    "or outreach messaging around."
                ),
            },
            "common_objections": {
                "type": "string",
                "description": (
                    "Objections this segment raises during the sales process.  For each "
                    "objection include: (1) the surface-level phrasing, and (2) the "
                    "underlying belief or fear that drives it."
                ),
            },
            "is_primary": {
                "type": "boolean",
                "description": (
                    "True for the single primary ICP segment (highest-value, fastest-closing "
                    "client profile).  False for all secondary segments."
                ),
            },
        },
    },
}

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

__all__ = [
    "ICP_GENERATOR_SYSTEM_PROMPT_V1",
    "ICP_OUTPUT_SCHEMA",
    "build_icp_user_prompt",
]
