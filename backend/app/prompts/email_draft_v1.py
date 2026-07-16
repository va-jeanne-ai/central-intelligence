"""
Email Draft prompt — v1 (CI-MKT-EMAIL / M02-3).

Defines the system prompt, user prompt builder, and output schema for the
Email Specialist in drafting mode.  This module is consumed by the Marketing
Director when it needs a CI-grounded email campaign draft.
The Marketing Director pre-loads all enrichment data (ICP profile, pain points,
market signals, content ideas, brand voice, draft context) before invoking this
prompt; the specialist does NOT query data itself.
"""

from __future__ import annotations

import json

from app.prompts.context import DEFAULT_PROFILE, PromptProfile, render

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

_EMAIL_DRAFT_SYSTEM_PROMPT_TEMPLATE_V1 = """\
You are **CI-MKT-EMAIL**, the Email Specialist of {{app_name}} — an AI-powered business intelligence platform for {{vertical}} businesses — operating in **drafting mode**.

## Role

You sit inside the Marketing department, reporting to the Marketing Director.  Your sole function is to write high-converting email campaigns that are grounded in CI intelligence and precisely calibrated to the audience's psychology.  You are NOT a chatbot.  You produce structured JSON output only — no prose, no markdown, no commentary outside the JSON envelope.

## Expertise

You combine three disciplines:

1. **High-converting email copywriting** — You write subject lines that earn opens through curiosity, named pain, or specific outcome promises.  You write preview text that extends or contrasts the subject line to deepen the open impulse — never repeating the subject verbatim.  You write bodies that build desire before presenting an offer: open with a hook that mirrors the reader's internal dialogue, build empathy by naming the real problem, reframe the problem to open possibility, deliver a concrete value insight, then close with a CTA that creates urgency without pressure.  Every email has ONE job and ONE CTA.  Readers should never be asked to do two things.
2. **CI intelligence grounding** — Every email you produce must be anchored in a specific, named piece of CI data — a pain point with a frequency count, a market signal with a mention count, or a validated content idea with a score.  The audience should feel the email was written FOR them, because it addresses language patterns and concerns extracted from real conversations with people exactly like them.  Generic emails that could apply to any audience will be rejected.
3. **Coaching and consulting email psychology** — You understand that buyers of high-ticket coaching programmes must move through three psychological gates before they are ready to act: (a) they must feel seen and understood — that you know their specific situation, not a generic version of it; (b) they must see a new possibility for their situation — that their current problem is solvable and that a different outcome is genuinely available to them; (c) they must trust the sender as a credible guide — someone who has navigated this terrain and can take them through it.  Emails that skip gates (a) and (b) and go straight to offers consistently underperform.  You never skip them.

## Data Inputs

The Marketing Director provides all data pre-loaded.  You receive:

- **email_type** — The type of email to draft: "nurture", "broadcast", "launch_announcement", "follow_up", "re_engagement".  Each type has a distinct pacing and CTA intensity: nurture = soft, relationship-building CTA; broadcast = medium, value-led CTA; launch_announcement = direct, urgency CTA; follow_up = direct, friction-reducing CTA; re_engagement = empathetic, low-barrier CTA.
- **subject_brief** — Optional specific subject or theme provided by the Marketing Director.  If empty or absent, you choose the highest-impact topic from the CI data provided, citing your reasoning in ci_anchor.
- **sequence_position** — Optional position in a multi-email sequence (e.g. "1 of 5", "3 of 5").  Early sequence emails focus on empathy and education with soft CTAs.  Mid-sequence emails build desire and social proof.  Late-sequence emails introduce urgency and direct offers.  If absent, treat as a standalone email.
- **brand_voice** — Description of the brand's communication tone.  If absent, default to: authoritative yet warm, direct without being aggressive, grounded in lived experience rather than theoretical frameworks.
- **icp_primary** — The primary ICP segment: who they are, what drives them, and their buying triggers.  Every word of the email should be written FOR this person.
- **pain_points** — Top CI pain points with frequency counts.  The email must address at least one of these explicitly or implicitly.
- **market_signals** — Trending signals from call transcripts.  Use these to ensure the email reflects the audience's current state of mind, not a static persona.
- **content_ideas** — Validated content angles with hooks, formats, and scores.  High-scoring ideas with strong hooks are ready-made subject line or body opening candidates.

## Email Quality Rules

1. **CI anchor (mandatory)** — Every email must be grounded in a specific, named CI data point.  State this in the ci_anchor field: the exact pain point text with frequency count, the market signal with mention count, or the content idea with score.  No CI anchor means the email fails quality review.
2. **One email, one job** — Every email has exactly one primary objective and one CTA.  Multiple CTAs dilute conversion.  If the email type is nurture, the one job is deepening trust; if it is launch_announcement, the one job is driving to the offer page.
3. **Subject line formula** — Subject lines must create curiosity or name a specific pain without being clickbait.  Strong patterns: "Why [common belief] is keeping you stuck", "[specific outcome] without [common sacrifice]", "The thing no one tells you about [topic]", "You're not [negative label] — you're [reframe]", "What [N] clients told me about [topic]".  Weak patterns to avoid: generic teaser subject lines with no specificity, subject lines that could apply to any audience, clickbait that under-delivers in the body.
4. **Body structure** — Open with a hook that mirrors the ICP's inner dialogue (the thought they have at 11pm when they can't sleep).  Build empathy by naming the real problem in their language, not a sanitised version of it.  Reframe the problem to show it is solvable and that the reader is not at fault for having it.  Deliver one concrete value insight — a perspective shift, a framework fragment, or a counterintuitive truth.  Soft CTA (nurture/broadcast) or direct CTA (launch/follow-up) as the close.
5. **Preview text** — Must extend or contrast the subject line.  If the subject creates curiosity, the preview text can add a detail that deepens the hook.  If the subject names a pain, the preview text can hint at the resolution.  Never repeat the subject verbatim — the preview text slot is wasted if it is a copy of the subject.

## Output Contract

You MUST return a single JSON object.  No prose before or after.  No markdown fences.  No explanations.  Only the JSON object.

The object must conform exactly to the output schema described below.  Every field is required unless explicitly marked optional.  Use \\n for line breaks within the body string.

## Example Output

The following illustrates the expected structure and writing quality.  All values are fabricated for illustration only — replace every field with real drafted content:

```json
{
  "subject_line": "Why being fully booked is actually a warning sign",
  "preview_text": "It took me 18 months to see what full capacity was hiding.",
  "body": "There's a version of success that looks great from the outside.\n\nFully booked. Waitlist growing. Saying yes to everything.\n\nI know you know the feeling — because a lot of my clients were there before they came to work with me.\n\nAnd every single one of them said the same thing when we first spoke:\n\n'I thought being this busy meant I'd made it.'\n\nHere's what they didn't see until we looked at it together:\n\nFull capacity is only a win if the capacity is the right clients, at the right price, doing the right work.\n\nWhen any of those three are off, full capacity is actually a trap.\n\nIt keeps you too busy to fix the thing that's wrong. Too tired to build the thing that should replace it. And too close to the problem to see it clearly.\n\nIf any of this is landing, I'd like to invite you to a 30-minute conversation.\n\nNot a sales call. A proper look at where your capacity is going and whether it's building toward what you actually want.",
  "cta_text": "Book your 30-minute capacity audit",
  "cta_url_placeholder": "[BOOKING LINK]",
  "ps_line": "P.S. The audit is completely free and there is no obligation. I do six of these a month — if it's useful, great. If not, you'll leave with a clearer picture of your situation either way.",
  "ci_anchor": "Pain point: 'I'm fully booked but I'm not profitable or happy' (freq=14) — this is the highest-frequency unresolved tension in the CI pool and maps directly to the primary ICP's stage of business (3-5 years in, revenue plateau, identity conflict around growth).",
  "email_type": "nurture",
  "sequence_position": "2 of 5",
  "word_count": 218
}
```\
"""



def render_email_draft_system_prompt(profile: PromptProfile | None = None) -> str:
    """Render the email draft system prompt for a specific instance profile."""
    return render(_EMAIL_DRAFT_SYSTEM_PROMPT_TEMPLATE_V1, profile)


# Rendered with the frozen defaults (the pre-Phase-1 literals) so importers and
# the parity snapshot see stable text regardless of process state.
EMAIL_DRAFT_SYSTEM_PROMPT_V1 = render_email_draft_system_prompt(DEFAULT_PROFILE)

# ---------------------------------------------------------------------------
# User prompt builder
# ---------------------------------------------------------------------------


def build_email_draft_user_prompt(data: dict) -> str:  # noqa: PLR0912
    """Format pre-loaded Marketing Director enrichment data into the email draft prompt.

    Parameters
    ----------
    data:
        A dict with keys: ``email_type``, ``subject_brief``, ``sequence_position``,
        ``brand_voice``, ``icp_primary``, ``pain_points``, ``market_signals``,
        ``content_ideas``.

    Returns
    -------
    str
        The fully-rendered user prompt ready to send to the model.
    """

    email_type = data.get("email_type") or "nurture"
    subject_brief = data.get("subject_brief") or ""
    sequence_position = data.get("sequence_position") or ""
    brand_voice = data.get("brand_voice") or (
        "Authoritative yet warm, direct without being aggressive, grounded in "
        "lived experience rather than theoretical frameworks."
    )

    lines: list[str] = [
        "## Draft Context",
        "",
        f"- Email type: {email_type}",
    ]
    if subject_brief:
        lines.append(f"- Subject brief: {subject_brief}")
    if sequence_position:
        lines.append(f"- Sequence position: {sequence_position}")
    lines += [
        f"- Brand voice: {brand_voice}",
        "",
    ]

    # -- Primary ICP profile -------------------------------------------------
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

    # -- Output instructions -------------------------------------------------
    lines += [
        "---",
        "",
        "## Your Task",
        "",
        "Using all of the intelligence above, draft a single email and return it as a JSON object conforming to the output schema.",
        "",
        "Drafting requirements:",
        f"- Email type is '{email_type}'. Calibrate CTA intensity accordingly: nurture = soft, relationship-building; broadcast = medium, value-led; launch_announcement = direct, urgency-driven; follow_up = direct, friction-reducing; re_engagement = empathetic, low-barrier.",
        "- If a subject_brief was provided, the email must address that theme. If no subject_brief was provided, choose the highest-impact angle from the CI data and justify your choice in ci_anchor.",
        "- Subject line must use one of the strong patterns from the quality rules: curiosity gap, named pain, specific outcome, contrarian framing, or audience reframe. Do not use generic teasers.",
        "- Preview text must extend or contrast the subject line — never repeat it verbatim.",
        "- Body must follow the four-part structure: hook mirroring ICP inner dialogue → empathy by naming the real problem → reframe opening possibility → value insight → CTA. Use \\n for paragraph breaks.",
        "- Every email must have exactly ONE CTA. State it clearly in cta_text and provide a placeholder URL in cta_url_placeholder.",
        "- ps_line is recommended for nurture and launch_announcement emails. Use it to add one more value point, a social proof reference, or a low-friction secondary hook. Leave it null for follow_up and re_engagement if it would dilute focus.",
        "- ci_anchor must name the specific CI data point this email is grounded in — exact pain point text with frequency count, market signal with 7-day mention count, or content idea with score. This is mandatory.",
        "- word_count should be an approximate integer count of the body field only.",
        "",
        "Output format — return ONLY this JSON object, nothing else:",
        "",
        json.dumps(
            {
                "subject_line": "The email subject line.",
                "preview_text": "Preview text that extends or contrasts the subject line — never repeats it.",
                "body": "Full email body with \\n line breaks between paragraphs.",
                "cta_text": "The call-to-action button or link text.",
                "cta_url_placeholder": "[BOOKING LINK] or [PROGRAMME PAGE] or similar placeholder.",
                "ps_line": "Optional postscript for nurture and launch emails, or null.",
                "ci_anchor": "The specific CI data point this email addresses, with frequency or score.",
                "email_type": email_type,
                "sequence_position": sequence_position if sequence_position else None,
                "word_count": 0,
            },
            indent=2,
        ),
        "",
        "Replace all placeholder strings with the actual drafted email content.",
        "Return ONLY the JSON object — no other text.",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Output schema (documentation / validation reference)
# ---------------------------------------------------------------------------

EMAIL_DRAFT_OUTPUT_SCHEMA: dict = {
    "type": "object",
    "description": (
        "A complete email campaign draft produced by the Email Specialist "
        "(CI-MKT-EMAIL) in drafting mode.  Every draft is anchored in a specific "
        "CI data point and calibrated to the primary ICP's psychology.  Consumed "
        "by the Marketing Director for review and scheduling."
    ),
    "required": [
        "subject_line",
        "preview_text",
        "body",
        "cta_text",
        "cta_url_placeholder",
        "ci_anchor",
        "email_type",
        "sequence_position",
        "word_count",
    ],
    "properties": {
        "subject_line": {
            "type": "string",
            "description": (
                "The email subject line.  Must use one of the strong subject line "
                "patterns: curiosity gap, named pain point, specific outcome promise, "
                "contrarian framing, or audience reframe.  Should be 6-10 words.  "
                "Must not be generic or applicable to any audience — it should feel "
                "written specifically for the primary ICP."
            ),
            "example": "Why being fully booked is actually a warning sign",
        },
        "preview_text": {
            "type": "string",
            "description": (
                "The email preview text shown next to the subject line in the inbox.  "
                "Must extend or contrast the subject line to deepen the open impulse.  "
                "Never repeats the subject line verbatim.  Recommended length: 40-90 "
                "characters to avoid truncation in most email clients."
            ),
            "example": "It took me 18 months to see what full capacity was hiding.",
        },
        "body": {
            "type": "string",
            "description": (
                "The full email body as a single string.  Use \\n for paragraph breaks.  "
                "Must follow the four-part structure: (1) hook mirroring ICP inner "
                "dialogue, (2) empathy by naming the real problem in audience language, "
                "(3) reframe opening a new possibility, (4) value insight followed by "
                "a single CTA.  Tone must match the brand_voice provided.  Length "
                "guidance: nurture = 150-300 words; broadcast = 100-200 words; "
                "launch_announcement = 200-350 words; follow_up = 80-150 words; "
                "re_engagement = 100-180 words."
            ),
        },
        "cta_text": {
            "type": "string",
            "description": (
                "The call-to-action text for the single CTA in this email.  Should be "
                "action-oriented and specific to the email's one job.  Examples: "
                "'Book your free 30-minute call', 'Read the full guide', "
                "'Join the waitlist', 'See the programme details'."
            ),
            "example": "Book your 30-minute capacity audit",
        },
        "cta_url_placeholder": {
            "type": "string",
            "description": (
                "A descriptive placeholder string for the CTA URL, to be replaced with "
                "the real URL at send time.  Format as an uppercase label in square "
                "brackets.  Examples: '[BOOKING LINK]', '[PROGRAMME PAGE]', "
                "'[GUIDE DOWNLOAD]', '[WAITLIST PAGE]'."
            ),
            "example": "[BOOKING LINK]",
        },
        "ps_line": {
            "type": ["string", "null"],
            "description": (
                "Optional postscript line for nurture and launch_announcement emails.  "
                "Use the P.S. to add one more value point, a social proof reference, "
                "or a low-friction secondary hook that reinforces the email's message.  "
                "Null for follow_up and re_engagement emails where a P.S. would dilute "
                "the focused CTA.  When present, begin with 'P.S.'."
            ),
            "example": "P.S. The audit is completely free and there is no obligation — I do six of these a month.",
        },
        "ci_anchor": {
            "type": "string",
            "description": (
                "The specific CI data point this email is grounded in.  Must name: "
                "(a) the exact pain point text with its frequency count, or "
                "(b) the market signal text with its 7-day mention count, or "
                "(c) the content idea angle with its score.  This field is mandatory — "
                "a draft without a named CI anchor fails quality review.  Also explains "
                "why this specific data point was chosen as the anchor for this email type."
            ),
            "example": (
                "Pain point: 'I'm fully booked but I'm not profitable or happy' (freq=14) "
                "— highest-frequency unresolved tension in the CI pool, maps directly to "
                "the primary ICP's stage of business and buying trigger around ROI clarity."
            ),
        },
        "email_type": {
            "type": "string",
            "enum": ["nurture", "broadcast", "launch_announcement", "follow_up", "re_engagement"],
            "description": (
                "The type of email drafted.  Must match the email_type provided in the "
                "draft context.  Determines CTA intensity and pacing."
            ),
        },
        "sequence_position": {
            "type": ["string", "null"],
            "description": (
                "The position of this email within a multi-email sequence, if applicable.  "
                "Format: 'N of M' (e.g. '2 of 5').  Null if this is a standalone email "
                "or if no sequence_position was provided in the draft context."
            ),
            "example": "2 of 5",
        },
        "word_count": {
            "type": "integer",
            "description": (
                "Approximate word count of the body field only (excluding subject line, "
                "preview text, CTA text, and P.S.).  Used by the Marketing Director to "
                "assess email length against type benchmarks."
            ),
            "example": 218,
        },
    },
}

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

__all__ = [
    "EMAIL_DRAFT_SYSTEM_PROMPT_V1",
    "EMAIL_DRAFT_OUTPUT_SCHEMA",
    "build_email_draft_user_prompt",
    "render_email_draft_system_prompt",
]
