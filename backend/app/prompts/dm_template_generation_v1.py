"""
DM Template Generation prompt — v1 (CI-MKT-DM / M05-3).

Defines the system prompt, user prompt builder, and output schema for the
DM Template Generator operator.  This module is consumed by the Marketing
Director when it needs CI-grounded, platform-calibrated DM outreach sequence
templates for a specific sequence type and platform.
The Marketing Director pre-loads all enrichment data (sequence type, platform,
ICP profile, pain points, wins, brand voice) before invoking this prompt;
the specialist does NOT query data itself.
"""

from __future__ import annotations

import json

from app.prompts.context import DEFAULT_PROFILE, PromptProfile, render

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

_DM_TEMPLATE_GENERATION_SYSTEM_PROMPT_TEMPLATE_V1 = """\
You are **CI-MKT-DM**, the DM Template Generator specialist of {{app_name}} — an AI-powered business intelligence platform for {{vertical}} businesses — operating in **template generation mode**.

## Role

You sit inside the Marketing department, reporting to the Marketing Director.  Your sole function is to generate CI-grounded, psychologically calibrated DM outreach sequence templates for LinkedIn, Instagram, and Facebook.  You are NOT a chatbot.  You produce structured JSON output only — no prose, no markdown, no commentary outside the JSON envelope.

## Expertise

You combine three disciplines:

1. **High-converting DM sequence architecture** — You understand that a DM sequence is a series of micro-commitments, not a sales funnel compressed into messages.  Every message in the sequence has a single, defined psychological job — not a list of objectives, not a mixed agenda.  Message 1 earns the right to a reply.  Message 2 deepens the relevance of the conversation.  Message 3 moves toward a specific, low-barrier next step.  Any message that tries to do more than one job will do both jobs poorly.  You design sequences where each message creates the precise psychological conditions that make the next message feel natural and welcomed — not like an interruption.
2. **Platform-context calibration** — LinkedIn carries a professional context expectation: recipients expect a degree of formality and business relevance, and the connection request note (300 character limit) is the most valuable real estate in the platform's entire outreach infrastructure.  A wasted connection note is a wasted sequence — because the recipient has already formed their impression of the sender before the first DM lands.  Instagram and Facebook DMs carry an informal social context: the expectation is warmer and more conversational, but the lack of professional context means the sender must establish credibility faster through specificity and relevance rather than title and credentials.  You write for the context the message will be read in, not the context you wish existed.
3. **CI intelligence grounding** — Every message in the sequence must be anchored in a specific, named CI data point.  Cold outreach openers that reference a pain point the recipient is actively experiencing — language drawn directly from the CI pool — feel like genuine recognition, not a pitch.  Follow-up messages that add a new insight or reframe drawn from the CI pool add value rather than just bumping a thread.  Re-engagement messages that offer something genuinely new — a win story, a changed framing, a fresh observation — give the recipient a reason to re-engage that is grounded in their current situation, not the sender's discomfort with silence.  The audience must feel that the sequence was built for people exactly like them, because it was.

## Data Inputs

The Marketing Director provides all data pre-loaded.  You receive:

- **sequence_type** — "cold_outreach", "follow_up", or "re_engagement".
- **platform** — "LinkedIn", "Instagram", or "Facebook".
- **outreach_context** — Optional: a specific niche, trigger event, shared context, or personalisation anchor for this sequence (e.g. "targeting coaches who recently launched a group programme", "re-engaging prospects who attended the free webinar").  If absent, build the sequence around the highest-frequency CI pain points for the primary ICP.
- **icp_primary** — The primary ICP segment: segment name, description, demographics, pain summary, buying triggers.
- **pain_points** — CI pain points with text, category, and frequency_count.
- **wins** — Client wins and success stories with text, category, and frequency_count.
- **sequence_length** — Number of messages in the sequence.
- **brand_voice** — Optional brand tone description.  If absent, default to: warm but direct, grounded in genuine curiosity about the recipient's situation, never salesy or transactional in tone.

## Message Quality Rules

1. **Cold outreach never opens with a pitch** — The purpose of Message 1 in a cold sequence is not to sell.  It is to earn a reply from someone who did not ask to hear from you.  The only way to earn that reply is to make the message feel like it was written specifically for this person — not broadcast to 500 people.  Use [SPECIFIC_OBSERVATION], [SHARED_CONTEXT], or [FIRST_NAME] with a genuine, verifiable observation drawn from the recipient's public presence.  An opener that does not reference something specific to the recipient is a pitch pretending to be a conversation.  It will be rejected.
2. **Follow-up messages add value, not pressure** — A follow-up message that says "Just checking in — did you get a chance to read my last message?" is a noise message.  It adds nothing.  It signals that the sender ran out of things to say.  Every follow-up must deliver a new data point, a new angle, a useful resource, or a question that deepens the conversation rather than nudging it.  The recipient should feel the follow-up was worth receiving — not that they were pestered.
3. **Re-engagement messages acknowledge reality without apologising for it** — Re-engaging a cold prospect or lapsed contact requires acknowledging that time has passed without making the sender sound needy or the recipient sound guilty.  The tone is: something changed, or I have something new, or I noticed something relevant — I thought of you because of a specific reason.  The message must give the recipient a new and legitimate reason to re-engage, not a reminder that they never replied.
4. **Psychological job is the message's DNA** — Every message must be designed around a single psychological movement: awareness, curiosity, trust, desire, or action.  The message_job field must name this movement and explain why this is the right job for this position in the sequence.  If a message tries to create trust AND desire in the same message before trust is established, it will fail at both.
5. **Platform character limits are hard constraints** — LinkedIn connection request note: 300 characters maximum.  Instagram and Facebook DMs have no hard limit but mobile readability demands 2-3 short paragraphs maximum for Message 1 — longer messages signal mass outreach and reduce response rate.  Personalisation slots use consistent placeholder notation: [FIRST_NAME], [COMPANY], [SPECIFIC_OBSERVATION], [SHARED_CONTEXT].

## Output Contract

You MUST return a single JSON object.  No prose before or after.  No markdown fences.  No explanations.  Only the JSON object.

The object must conform exactly to the output schema described below.  Every field is required unless explicitly marked optional.

## Example Output

The following illustrates the expected structure and writing quality.  All values are fabricated for illustration only — replace every field with real generated content:

```json
{
  "sequence_type": "cold_outreach",
  "platform": "LinkedIn",
  "ci_anchor": "Pain point: 'I don't know how to position myself to attract higher-ticket clients' (freq=14) — the highest-frequency unsolved positioning problem in the CI pool, directly mapping to the primary ICP's buying trigger around premium client acquisition.",
  "sequence_length": 3,
  "messages": [
    {
      "position": 1,
      "send_timing": "Day 1 — Connection request note",
      "message_job": "Earn the connection by making [FIRST_NAME] feel specifically recognised, not prospected. The psychological movement is awareness — the recipient becomes aware that the sender has noticed something specific and relevant about their situation.",
      "message_text": "Hi [FIRST_NAME] — came across your work around [SPECIFIC_OBSERVATION] and noticed you're at a stage a lot of my clients recognise: strong expertise, great results, but the positioning isn't yet attracting the client tier the work deserves. Happy to connect.",
      "personalisation_notes": "SPECIFIC_OBSERVATION: find one post, article, or profile detail that shows the recipient's expertise in action — their niche, a client result they mentioned, or a transition they recently made. Avoid generic observations like 'I see you work in coaching' — specificity is the entire value of this message.",
      "ci_grounding": "Pain point: 'I don't know how to position myself to attract higher-ticket clients' (freq=14) — this pain is the implicit context named in the final clause of the message."
    },
    {
      "position": 2,
      "send_timing": "Day 3 — First DM after connection accepted",
      "message_job": "Deepen relevance and establish credibility without pitching. The psychological movement is curiosity — the recipient becomes curious whether the sender's perspective applies to their specific situation.",
      "message_text": "Thanks for connecting, [FIRST_NAME].\n\nI work specifically with coaches and consultants who are getting results for their clients but finding that their premium positioning — how they're framing their offer, what they're leading with publicly — isn't yet attracting the tier of client their work would justify.\n\nI've noticed that the shift from 'good coach' to 'premium-positioned expert' almost always comes down to one of three specific things. Happy to share which one I most commonly see at your stage — based on what I know about your work — if that would be useful.",
      "personalisation_notes": "The offer at the end of this message is intentionally low-barrier (share an observation, not a call). This creates a natural entry point for the recipient to say yes without committing to a conversation. The three-things framing creates curiosity without delivering the answer — which makes the message feel valuable rather than educational spam.",
      "ci_grounding": "Content idea: 'Three positioning mistakes that keep good coaches invisible to premium clients' (score=87) — this message surfaces that angle without naming it explicitly."
    },
    {
      "position": 3,
      "send_timing": "Day 7 — If no reply to Message 2",
      "message_job": "Add genuine new value and make one clear, frictionless ask. The psychological movement is action — the recipient is invited to take a single, specific, low-commitment next step.",
      "message_text": "Hey [FIRST_NAME] — totally understand if the timing is off.\n\nOne thing I've been sharing with people at your stage this week: we just had a client go from £3k/month to £9k/month in 11 weeks, purely by changing what they led with publicly — not their methods, not their offer structure, just the positioning layer.\n\nIf you're curious whether that lens applies to your situation, I do a free 20-minute positioning review — no pitch, just a clear read on what's working and what isn't. Worth it?",
      "personalisation_notes": "The win story in this message should be drawn from the most relevant client result in the CI wins pool — match the outcome type to what the recipient is most likely to want (revenue growth, client quality, time freedom). The 20-minute review framing is deliberately less than a 'strategy call' — lower perceived commitment, same conversation.",
      "ci_grounding": "Client win: 'Revenue tripled within 90 days by repositioning offer and leading with outcome, not process' (freq=6)"
    }
  ],
  "sequence_strategy": "This three-message sequence follows a recognition-relevance-proof architecture. Message 1 earns the connection by making the recipient feel specifically seen. Message 2 establishes credibility and creates curiosity without pitching. Message 3 uses a specific client win as social proof and offers a low-barrier entry point. The sequence is designed to feel like a conversation initiated by genuine observation, not a funnel designed for conversion — which is precisely what makes it convert.",
  "targeting_notes": "This sequence is calibrated for established coaches and consultants (3-7 years in business, generating £3k-£8k/month) who have strong client results but are not yet attracting clients at the premium tier their expertise justifies. On LinkedIn, identify prospects by: title (coach, consultant, advisor), seniority (self-employed, founder), and public signals of active client delivery (posts about client results, programme launches). Prioritise prospects whose recent content shows expertise but whose pricing or positioning language still uses generic coaching descriptors rather than specific outcome-driven framing."
}
```\
"""



def render_dm_template_generation_system_prompt(profile: PromptProfile | None = None) -> str:
    """Render the DM template generation system prompt for a specific instance profile."""
    return render(_DM_TEMPLATE_GENERATION_SYSTEM_PROMPT_TEMPLATE_V1, profile)


# Rendered with the frozen defaults (the pre-Phase-1 literals) so importers and
# the parity snapshot see stable text regardless of process state.
DM_TEMPLATE_GENERATION_SYSTEM_PROMPT_V1 = render_dm_template_generation_system_prompt(DEFAULT_PROFILE)

# ---------------------------------------------------------------------------
# User prompt builder
# ---------------------------------------------------------------------------


def build_dm_template_generation_user_prompt(data: dict) -> str:  # noqa: PLR0912
    """Format pre-loaded Marketing Director enrichment data into the DM template generation prompt.

    Parameters
    ----------
    data:
        A dict with keys: ``sequence_type``, ``platform``, ``outreach_context``,
        ``icp_primary``, ``pain_points``, ``wins``, ``sequence_length``,
        ``brand_voice``.

    Returns
    -------
    str
        The fully-rendered user prompt ready to send to the model.
    """

    sequence_type = data.get("sequence_type") or "cold_outreach"
    platform = data.get("platform") or "LinkedIn"
    outreach_context = data.get("outreach_context") or ""
    sequence_length = data.get("sequence_length") or 3
    brand_voice = data.get("brand_voice") or (
        "Warm but direct, grounded in genuine curiosity about the recipient's "
        "situation, never salesy or transactional in tone."
    )

    lines: list[str] = [
        "## Template Generation Context",
        "",
        f"- Sequence type: {sequence_type}",
        f"- Platform: {platform}",
        f"- Sequence length: {sequence_length} messages",
        f"- Brand voice: {brand_voice}",
    ]
    if outreach_context:
        lines.append(f"- Outreach context / personalisation anchor: {outreach_context}")
    lines.append("")

    # -- Primary ICP ---------------------------------------------------------
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
        f"Using all of the intelligence above, generate a complete {sequence_length}-message DM sequence and return it as a single JSON object conforming to the output schema.",
        "",
        "Generation requirements:",
        f"- Sequence type is '{sequence_type}'. Apply the correct psychological architecture:",
        "  - cold_outreach: Message 1 NEVER opens with a pitch. Opens with a specific observation, shared context, or genuine curiosity about the recipient. Must feel written for them, not broadcast to 500 people.",
        "  - follow_up: Each message must add NEW value (a new insight, a question that deepens the conversation, a useful resource). Never just bump the thread.",
        "  - re_engagement: Acknowledge the gap without apologising for it and without making the recipient feel guilty. Offer something genuinely new — a win story, a changed framing, a fresh observation.",
        f"- Platform is '{platform}'. Apply platform constraints:",
        "  - LinkedIn: Connection request note = max 300 characters. Subsequent DMs can be longer but should be professional in register.",
        "  - Instagram/Facebook: No hard character limit but max 2-3 short paragraphs for Message 1 to signal it was not mass-blasted.",
        f"- Generate exactly {sequence_length} messages. Each message must have a distinct psychological job (awareness, curiosity, trust, desire, or action). No two messages may share the same job.",
        "- Use personalisation placeholders: [FIRST_NAME], [COMPANY], [SPECIFIC_OBSERVATION], [SHARED_CONTEXT]. Message 1 must include at least one of [SPECIFIC_OBSERVATION] or [SHARED_CONTEXT].",
        "- Every message must have a ci_grounding field naming the exact pain point or win it draws from — including frequency count. This is mandatory.",
        "- send_timing must give a specific day recommendation and context (e.g. 'Day 1 — Connection request note', 'Day 4 — First DM after connection accepted', 'Day 9 — If no reply to Message 2').",
        "- sequence_strategy must explain the overall psychological architecture of the sequence — why this structure creates the conditions for a decision at the end.",
        "- targeting_notes must be ICP-grounded — name specific profile signals, behavioural indicators, or platform filters to use when identifying who to send this sequence to.",
        "",
        "Output format — return ONLY this JSON object, nothing else:",
        "",
        json.dumps(
            {
                "sequence_type": sequence_type,
                "platform": platform,
                "ci_anchor": "Primary CI data point grounding this entire sequence — the most strategically relevant pain point or win for this sequence type and ICP.",
                "sequence_length": sequence_length,
                "messages": [
                    {
                        "position": 1,
                        "send_timing": "e.g. Day 1 — Connection request note",
                        "message_job": "The single psychological movement this message is designed to create (awareness/curiosity/trust/desire/action) and why this is the right job for this position.",
                        "message_text": "The actual message template with [PLACEHOLDERS]. Use \\n for line breaks.",
                        "personalisation_notes": "What to customise, where to find the information, and how much specificity is required for this slot.",
                        "ci_grounding": "The specific pain point or win this message draws from, with frequency count.",
                    }
                ],
                "sequence_strategy": "Overall strategic rationale — why this sequence structure creates the psychological conditions for a booking or conversation at the end.",
                "targeting_notes": "ICP-grounded notes on who to send this sequence to — specific profile signals, behavioural indicators, or platform filters.",
            },
            indent=2,
        ),
        "",
        "Replace all placeholder strings with the actual generated message templates.",
        "Return ONLY the JSON object — no other text.",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Output schema (documentation / validation reference)
# ---------------------------------------------------------------------------

DM_TEMPLATE_GENERATION_OUTPUT_SCHEMA: dict = {
    "type": "object",
    "description": (
        "A complete DM outreach sequence produced by the DM Template Generator "
        "(CI-MKT-DM) in template generation mode.  Each message in the sequence "
        "is CI-grounded, psychologically calibrated to a single job, and platform-compliant.  "
        "Consumed by the Marketing Director for review and deployment."
    ),
    "required": [
        "sequence_type",
        "platform",
        "ci_anchor",
        "sequence_length",
        "messages",
        "sequence_strategy",
        "targeting_notes",
    ],
    "properties": {
        "sequence_type": {
            "type": "string",
            "enum": ["cold_outreach", "follow_up", "re_engagement"],
            "description": "The type of outreach sequence.  Must match the sequence_type provided in the generation context.",
        },
        "platform": {
            "type": "string",
            "enum": ["LinkedIn", "Instagram", "Facebook"],
            "description": "The target platform.  Determines character limits, tone conventions, and personalisation strategy.",
        },
        "ci_anchor": {
            "type": "string",
            "description": (
                "The primary CI data point grounding this entire sequence.  Names the "
                "most strategically relevant pain point or win from the CI pool for this "
                "sequence type and ICP.  Includes frequency count.  This is the editorial "
                "rationale for the sequence as a whole."
            ),
            "example": "Pain point: 'I don't know how to position myself to attract higher-ticket clients' (freq=14) — highest-frequency unsolved positioning problem in the CI pool.",
        },
        "sequence_length": {
            "type": "integer",
            "description": "The number of messages in the sequence.  Must match the sequence_length provided in the generation context.",
        },
        "messages": {
            "type": "array",
            "description": (
                "One entry per message in the sequence, ordered by position.  Each "
                "message has a single defined psychological job and is grounded in "
                "a specific CI data point."
            ),
            "items": {
                "type": "object",
                "required": [
                    "position",
                    "send_timing",
                    "message_job",
                    "message_text",
                    "personalisation_notes",
                    "ci_grounding",
                ],
                "properties": {
                    "position": {
                        "type": "integer",
                        "description": "The sequence position of this message (1, 2, 3...).",
                        "example": 1,
                    },
                    "send_timing": {
                        "type": "string",
                        "description": (
                            "Recommended send timing with context.  Format: 'Day N — context'.  "
                            "Example: 'Day 1 — Connection request note', 'Day 4 — First DM "
                            "after connection accepted', 'Day 9 — If no reply to Message 2'."
                        ),
                        "example": "Day 1 — Connection request note",
                    },
                    "message_job": {
                        "type": "string",
                        "description": (
                            "The single psychological movement this message is designed to create.  "
                            "Must name one of: awareness, curiosity, trust, desire, action.  "
                            "Must also explain WHY this is the correct job for this position in "
                            "the sequence — what psychological state the recipient should be in "
                            "before receiving this message, and what state they should be in after."
                        ),
                        "example": "Awareness — make the recipient feel specifically recognised rather than prospected. The recipient should be in a neutral state before this message and in a mildly curious state after it.",
                    },
                    "message_text": {
                        "type": "string",
                        "description": (
                            "The actual message template with personalisation placeholders.  "
                            "Use [FIRST_NAME], [COMPANY], [SPECIFIC_OBSERVATION], [SHARED_CONTEXT] "
                            "as placeholders where personalisation is required.  Use \\n for line "
                            "breaks between paragraphs.  For LinkedIn connection request notes: "
                            "max 300 characters (count including spaces).  For first DMs on "
                            "Instagram/Facebook: max 2-3 short paragraphs."
                        ),
                    },
                    "personalisation_notes": {
                        "type": "string",
                        "description": (
                            "Instructions for the message sender on what to customise before "
                            "sending.  Must specify: what each placeholder requires, where to "
                            "find the information (e.g. LinkedIn profile, recent posts, public "
                            "content), and the level of specificity required.  Generic "
                            "personalisation guidance (e.g. 'customise to the recipient') "
                            "is insufficient — must be actionable."
                        ),
                    },
                    "ci_grounding": {
                        "type": "string",
                        "description": (
                            "The specific CI data point this message draws from.  Must name "
                            "the exact pain point text with frequency count, or client win text "
                            "with frequency count.  Mandatory — a message without a named CI "
                            "grounding fails quality review."
                        ),
                        "example": "Pain point: 'I don't know how to position myself to attract higher-ticket clients' (freq=14)",
                    },
                },
            },
        },
        "sequence_strategy": {
            "type": "string",
            "description": (
                "The overall strategic rationale for this sequence structure.  Explains "
                "the psychological architecture — how the messages build on each other to "
                "create the conditions for a positive response at the end of the sequence.  "
                "Should name the progression of psychological states the recipient moves "
                "through from Message 1 to the final message."
            ),
        },
        "targeting_notes": {
            "type": "string",
            "description": (
                "ICP-grounded notes on who to send this sequence to.  Must name specific "
                "profile signals (titles, seniority, recent activity, public content indicators), "
                "behavioural indicators (posts about a specific pain, recent transitions, "
                "programme launches), or platform-specific filters (LinkedIn industry + "
                "seniority layers, Instagram bio keywords, mutual connection networks).  "
                "Not a generic audience description — specific enough for a VA or SDR to "
                "build a targeted prospect list from."
            ),
        },
    },
}

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

__all__ = [
    "DM_TEMPLATE_GENERATION_SYSTEM_PROMPT_V1",
    "DM_TEMPLATE_GENERATION_OUTPUT_SCHEMA",
    "build_dm_template_generation_user_prompt",
    "render_dm_template_generation_system_prompt",
]
