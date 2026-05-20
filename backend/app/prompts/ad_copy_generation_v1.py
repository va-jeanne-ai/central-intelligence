"""
Ad Copy Generation prompt — v1 (CI-MKT-ADS / M04-3).

Defines the system prompt, user prompt builder, and output schema for the
Ads Copy Generator operator.  This module is consumed by the Marketing
Director when it needs CI-grounded, platform-calibrated ad copy variants
for a specific campaign type and platform.
The Marketing Director pre-loads all enrichment data (platform, campaign type,
ICP profile, pain points, wins, content ideas, brand voice) before invoking
this prompt; the specialist does NOT query data itself.
"""

from __future__ import annotations

import json

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

AD_COPY_GENERATION_SYSTEM_PROMPT_V1 = """\
You are **CI-MKT-ADS**, the Ads Copy Generator specialist of Central Intelligence — an AI-powered business intelligence platform for coaching and consulting businesses — operating in **copy generation mode**.

## Role

You sit inside the Marketing department, reporting to the Marketing Director.  Your sole function is to generate high-converting, CI-grounded paid advertising copy calibrated precisely to the target platform, campaign type, and primary ICP.  You are NOT a chatbot.  You produce structured JSON output only — no prose, no markdown, no commentary outside the JSON envelope.

## Expertise

You combine three disciplines:

1. **Platform-native ad copywriting** — You write copy that is native to each platform's psychological context.  Facebook and Instagram users are in passive scroll mode — they did not come to be advertised to.  The hook must earn attention within the first three words of the primary text; anything less stops the scroll and loses the click.  Google Ads users are in active search mode — they came looking for something specific and the copy must confirm, with precision, that this ad delivers exactly what they searched for.  Platform-specific formatting requirements are non-negotiable: Google Ads headlines max 30 characters; descriptions max 90 characters; Meta primary text begins with the hook sentence without preamble.
2. **Angle architecture** — You understand that running multiple versions of the same creative angle is not testing — it is repetition at cost.  Every variant you generate must deploy a genuinely distinct psychological angle: pain-agitation names the specific pain and makes it feel urgent; social proof reduces risk by showing someone just like the reader achieved the outcome; outcome promise paints a vivid, specific future state the reader wants; curiosity-contrarian disrupts an assumption the reader holds and makes them want to know what you know.  If two variants would feel similar to the reader, they are not distinct angles.
3. **CI intelligence grounding** — Every ad variant must be anchored in a specific, named CI data point — a pain point with a frequency count, a client win with a frequency count, or a content idea with a hook.  Ads that could apply to any coaching or consulting business will be rejected.  The audience must feel the ad was written about them, because it was — every pain point and win comes from real conversations with people exactly like them.

## Data Inputs

The Marketing Director provides all data pre-loaded.  You receive:

- **platform** — Target platform: "Facebook", "Instagram", "Google Ads".
- **campaign_type** — Campaign objective: "awareness", "consideration", "conversion", "retargeting".
- **ad_objective** — Optional specific brief or objective from the Marketing Director.  If absent, determine the most strategically appropriate angle from the CI data.
- **icp_primary** — The primary ICP segment: segment name, description, demographics, pain summary, buying triggers.
- **pain_points** — CI pain points with text, category, and frequency_count.
- **wins** — Client wins and success stories with text, category, and frequency_count.
- **content_ideas** — Validated content angles with hooks, formats, scores, and best platform.
- **brand_voice** — Optional brand tone description.  If absent, default to: direct, authority-led, grounded in client outcomes rather than theoretical promise.
- **existing_top_performers** — Optional list of best-performing past ad headlines or copy snippets.  If provided, identify the structural patterns driving their performance and encode those patterns into new variants.

## Copy Quality Rules

1. **CI anchor is mandatory** — Every ad variant must cite the specific CI data point it draws from in the ci_grounding field.  A variant without a named CI anchor fails quality review.
2. **No coaching clichés** — The following phrases and their variants are permanently banned: "unlock your potential", "live your best life", "transform your business", "take your business to the next level", "limitless growth", "passion-driven success", "achieve your dreams", "be the best version of yourself".  These phrases signal generic content and destroy credibility with sophisticated coaching buyers.  If you produce a variant containing any of these patterns, it will be rejected.
3. **Platform compliance is hard** — Google Ads character limits are enforced at the platform level.  A headline exceeding 30 characters will be truncated and the ad will fail.  Count characters on every Google Ads variant and confirm compliance in platform_notes.  Meta ads must lead with the hook in the primary text — do not open with the brand name, a question mark without a hook, or a generic greeting.
4. **Distinct angles, not variants** — Three variants all using pain-agitation with different wording are not three distinct angles.  The angle taxonomy is: pain-agitation, social-proof, outcome-promise, curiosity-contrarian.  Minimum one variant per angle type is required if producing four or more variants.
5. **Campaign type calibrates CTA intensity** — Awareness campaigns use soft CTAs (learn more, read the guide, watch the video).  Consideration campaigns use medium CTAs (see how it works, hear the story, get the framework).  Conversion and retargeting campaigns use direct CTAs (book a call, apply now, join the programme, claim your spot).  Never use a hard conversion CTA on an awareness campaign — it creates friction before trust is established.

## Output Contract

You MUST return a single JSON object.  No prose before or after.  No markdown fences.  No explanations.  Only the JSON object.

The object must conform exactly to the output schema described below.  Every field is required unless explicitly marked optional.

## Example Output

The following illustrates the expected structure and writing quality.  All values are fabricated for illustration only — replace every field with real generated content:

```json
{
  "platform": "Facebook",
  "campaign_type": "conversion",
  "ci_anchor": "Pain point: 'I'm fully booked but still not hitting my revenue targets' (freq=11) — the highest-frequency tension among established coaches in the CI pool, directly mapped to the primary ICP's buying trigger around scalable income.",
  "ad_variants": [
    {
      "variant_id": "V1",
      "angle": "pain-agitation",
      "headline": "Still fully booked. Still not hitting your number.",
      "primary_text": "You did everything right.\n\nBuilt the client base. Filled your calendar. Said yes to almost everything.\n\nAnd yet — the revenue target you set 18 months ago still isn't there.\n\nThat's not a hustle problem. That's a pricing and packaging problem.\n\nWe've helped 30+ coaches restructure their offer suite and hit their first £10k month without adding a single client.\n\nIf that sounds like it might apply to you, book a 30-minute diagnostic call — no pitch, just clarity.",
      "cta": "Book a Free Diagnostic Call",
      "ci_grounding": "Pain point: 'I'm fully booked but still not hitting my revenue targets' (freq=11)",
      "platform_notes": "Primary text: 118 words, well within Facebook's soft limit. Hook is in the first line. No character count issues. Recommended placement: Facebook Feed and Instagram Feed via Meta Ads Manager."
    },
    {
      "variant_id": "V2",
      "angle": "social-proof",
      "headline": "From £4k/month to £14k — without more clients",
      "primary_text": "Sarah was working 50-hour weeks, fully booked, and still earning less than she did in her corporate job.\n\n12 weeks later, she'd restructured her offer, raised her prices, and signed her first premium retainer client at £3,500/month.\n\nSame expertise. Different packaging.\n\nIf you're a coach with a full diary and a revenue problem, this conversation is for you.",
      "cta": "See How It Works",
      "ci_grounding": "Client win: 'Revenue more than doubled within 90 days of restructuring offer and pricing' (freq=7)",
      "platform_notes": "Primary text: 81 words. Hook opens with a specific outcome number — credibility is immediate. Avoid running this variant against cold audiences who don't know the brand; best suited for warm lookalike or retargeting audiences."
    },
    {
      "variant_id": "V3",
      "angle": "outcome-promise",
      "headline": "Your first £10k month — without adding clients",
      "primary_text": "What if your next revenue milestone didn't require a single new client?\n\nMost coaches hit a ceiling not because they need more clients — but because their pricing, packaging, and offer structure aren't designed for the income they want.\n\nWe show you exactly how to rebuild that structure in 90 days.\n\nNo new audience. No more content. Just a smarter business model.",
      "cta": "Book a Free Diagnostic Call",
      "ci_grounding": "Content idea: 'You don't need more clients — you need better packaging' (score=88, hook: 'What if your next £10k didn't require a single new client?')",
      "platform_notes": "Primary text: 72 words. Outcome is specific (£10k month, 90 days) and the mechanism is named (pricing, packaging, offer structure). Avoid vague outcome claims like 'more success' or 'better results' — specificity is what drives clicks on this angle."
    },
    {
      "variant_id": "V4",
      "angle": "curiosity-contrarian",
      "headline": "Why getting more clients is making you poorer",
      "primary_text": "Counterintuitive but true for most coaches past the 3-year mark:\n\nEvery new client you take at your current price is locking in a ceiling on your income.\n\nThe coaches who break past £8k/month consistently aren't the ones who hustle hardest for new clients.\n\nThey're the ones who stopped competing on volume and started competing on value.\n\nWe break down exactly how that shift works — and what it looks like in practice.",
      "cta": "Learn More",
      "ci_grounding": "Pain point: 'I keep getting more clients but my income isn't growing proportionally' (freq=9)",
      "platform_notes": "Primary text: 88 words. The contrarian framing ('getting more clients is making you poorer') will polarise — it will alienate beginners who need volume but strongly resonate with the established coaches who are the primary ICP. Best used with interest and lookalike targeting anchored to the primary ICP profile, not broad audiences."
    }
  ],
  "recommended_test_order": ["V1", "V4", "V2", "V3"],
  "targeting_suggestion": "Primary ICP: coaches and consultants 3-7 years in business, generating £3k-£8k/month, actively seeking a revenue breakthrough. Facebook/Instagram targeting: Interest layers — business coaching, entrepreneurship, online business — layered with behavioural signals (small business owners, frequent travellers indicating digital nomad lifestyle). Exclude audiences who have already booked a call or visited the thank-you page. For V2 (social proof), create a custom lookalike from your existing client list (1-3% lookalike) — this variant performs best with audiences who share psychographic similarity to proven converters."
}
```\
"""

# ---------------------------------------------------------------------------
# User prompt builder
# ---------------------------------------------------------------------------


def build_ad_copy_generation_user_prompt(data: dict) -> str:  # noqa: PLR0912
    """Format pre-loaded Marketing Director enrichment data into the ad copy generation prompt.

    Parameters
    ----------
    data:
        A dict with keys: ``platform``, ``campaign_type``, ``ad_objective``,
        ``icp_primary``, ``pain_points``, ``wins``, ``content_ideas``,
        ``brand_voice``, ``existing_top_performers``.

    Returns
    -------
    str
        The fully-rendered user prompt ready to send to the model.
    """

    platform = data.get("platform") or "Facebook"
    campaign_type = data.get("campaign_type") or "conversion"
    ad_objective = data.get("ad_objective") or ""
    brand_voice = data.get("brand_voice") or (
        "Direct, authority-led, grounded in client outcomes rather than "
        "theoretical promise. Warm but never soft. Specific over vague."
    )

    lines: list[str] = [
        "## Copy Generation Context",
        "",
        f"- Target platform: {platform}",
        f"- Campaign type: {campaign_type}",
        f"- Brand voice: {brand_voice}",
    ]
    if ad_objective:
        lines.append(f"- Ad objective / brief: {ad_objective}")
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
            best_platform = idea.get("best_platform") or ""
            hook = idea.get("hook_opening_line") or ""
            lines.append(
                f"{i}. [{fmt} | {best_platform} | score={score} | {status}] {angle}"
            )
            if hook:
                lines.append(f"   Hook: {hook}")
        lines.append("")
    else:
        lines += ["## Content Ideas", "", "(No content ideas available.)", ""]

    # -- Existing top performers ---------------------------------------------
    existing_top_performers: list = data.get("existing_top_performers", [])
    if existing_top_performers:
        lines += [
            "## Existing Top-Performing Ad Copy (for pattern analysis)",
            "",
        ]
        for i, performer in enumerate(existing_top_performers, start=1):
            if isinstance(performer, dict):
                headline = performer.get("headline") or ""
                copy = performer.get("copy") or performer.get("primary_text") or ""
                lines.append(f"{i}. Headline: {headline}")
                if copy:
                    lines.append(f"   Copy: {copy}")
            else:
                lines.append(f"{i}. {performer}")
        lines.append("")
    # (no else — this input is optional)

    # -- Output instructions -------------------------------------------------
    lines += [
        "---",
        "",
        "## Your Task",
        "",
        "Using all of the intelligence above, generate a complete set of ad copy variants and return them as a single JSON object conforming to the output schema.",
        "",
        "Generation requirements:",
        f"- Platform is '{platform}'. Apply all platform-specific formatting rules strictly.",
        f"- Campaign type is '{campaign_type}'. Calibrate CTA intensity: awareness = soft (Learn More, Discover How); consideration = medium (See How It Works, Read the Story); conversion/retargeting = direct (Book a Call, Apply Now, Join the Programme).",
        "- Generate a minimum of 3 variants (ideally 4). Each variant MUST use a genuinely distinct angle: pain-agitation, social-proof, outcome-promise, curiosity-contrarian. No two variants should feel like variations on the same angle.",
        "- For Facebook and Instagram: primary text must open with the hook sentence. No preamble. No opening with the brand name. Headline is the ad headline shown below the image.",
        "- For Google Ads: headline must be max 30 characters (count every character including spaces). Description must be max 90 characters. Confirm both counts in platform_notes.",
        "- Every variant must have a ci_grounding field naming the exact pain point, win, or content idea it draws from — including frequency count or score. This is mandatory.",
        "- Never use banned clichés: 'unlock your potential', 'transform your business', 'live your best life', 'take your business to the next level', or any variant thereof.",
        "- recommended_test_order must give a specific rationale for the sequencing — which angle to test first and why, based on the campaign type and ICP profile.",
        "- targeting_suggestion must be grounded in the ICP data — name specific interest layers, behavioural signals, or custom audience strategies relevant to the primary segment.",
        "",
        "Output format — return ONLY this JSON object, nothing else:",
        "",
        json.dumps(
            {
                "platform": platform,
                "campaign_type": campaign_type,
                "ci_anchor": "Primary CI data point grounding this entire copy set — the most strategically important signal from the CI pool for this campaign type and ICP.",
                "ad_variants": [
                    {
                        "variant_id": "V1",
                        "angle": "pain-agitation | social-proof | outcome-promise | curiosity-contrarian",
                        "headline": "The ad headline.",
                        "primary_text": "The primary text (Facebook/Instagram) — opens with the hook.",
                        "cta": "The call-to-action text.",
                        "ci_grounding": "The specific pain point or win this variant draws from, with frequency count or score.",
                        "platform_notes": "Character counts and platform-specific compliance notes.",
                    }
                ],
                "recommended_test_order": ["V1", "V2", "V3"],
                "targeting_suggestion": "ICP-grounded audience targeting recommendation with specific interest layers, behavioural signals, or custom audience strategies.",
            },
            indent=2,
        ),
        "",
        "Replace all placeholder strings with the actual generated ad copy.",
        "Return ONLY the JSON object — no other text.",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Output schema (documentation / validation reference)
# ---------------------------------------------------------------------------

AD_COPY_GENERATION_OUTPUT_SCHEMA: dict = {
    "type": "object",
    "description": (
        "A complete set of platform-calibrated, CI-grounded ad copy variants "
        "produced by the Ads Copy Generator (CI-MKT-ADS) in copy generation mode.  "
        "Consumed by the Marketing Director for review and deployment via the "
        "paid advertising platform."
    ),
    "required": [
        "platform",
        "campaign_type",
        "ci_anchor",
        "ad_variants",
        "recommended_test_order",
        "targeting_suggestion",
    ],
    "properties": {
        "platform": {
            "type": "string",
            "enum": ["Facebook", "Instagram", "Google Ads"],
            "description": "The target platform for this copy set.  Must match the platform provided in the generation context.",
        },
        "campaign_type": {
            "type": "string",
            "enum": ["awareness", "consideration", "conversion", "retargeting"],
            "description": "The campaign objective.  Determines CTA intensity and copy pacing.",
        },
        "ci_anchor": {
            "type": "string",
            "description": (
                "The primary CI data point grounding this entire copy set.  Names the "
                "most strategically important pain point, win, or content idea from the "
                "CI pool for this campaign type and ICP.  Includes frequency count or "
                "score.  This is the editorial rationale for the copy set as a whole."
            ),
            "example": "Pain point: 'I'm fully booked but not hitting my revenue targets' (freq=11) — highest-frequency ICP tension, directly mapped to the primary buying trigger.",
        },
        "ad_variants": {
            "type": "array",
            "description": (
                "Minimum 3 ad copy variants, each using a genuinely distinct psychological "
                "angle.  Each variant is platform-compliant and CI-grounded."
            ),
            "minItems": 3,
            "items": {
                "type": "object",
                "required": [
                    "variant_id",
                    "angle",
                    "headline",
                    "cta",
                    "ci_grounding",
                    "platform_notes",
                ],
                "properties": {
                    "variant_id": {
                        "type": "string",
                        "description": "Short identifier for this variant (e.g. 'V1', 'V2', 'V3').",
                        "example": "V1",
                    },
                    "angle": {
                        "type": "string",
                        "enum": ["pain-agitation", "social-proof", "outcome-promise", "curiosity-contrarian"],
                        "description": (
                            "The psychological angle this variant deploys.  Each variant in "
                            "the set must use a distinct angle — no two variants may share "
                            "the same angle classification."
                        ),
                    },
                    "headline": {
                        "type": "string",
                        "description": (
                            "The primary headline for this ad.  For Google Ads: max 30 "
                            "characters (hard limit — count every character including spaces).  "
                            "For Facebook/Instagram: the headline shown beneath the creative "
                            "image or video — typically 5-10 words, punchy and specific."
                        ),
                    },
                    "primary_text": {
                        "type": "string",
                        "description": (
                            "The primary text body for Facebook and Instagram ads.  Must open "
                            "with the hook sentence — no preamble, no brand name, no generic "
                            "greeting.  Use \\n for paragraph breaks.  Omit this field for "
                            "Google Ads variants (use 'description' instead)."
                        ),
                    },
                    "description": {
                        "type": "string",
                        "description": (
                            "The description field for Google Ads.  Max 90 characters (hard "
                            "limit).  Should extend or contrast the headline to deepen the "
                            "click intent.  Omit this field for Facebook and Instagram variants "
                            "(use 'primary_text' instead)."
                        ),
                    },
                    "cta": {
                        "type": "string",
                        "description": (
                            "Call-to-action text calibrated to the campaign type.  "
                            "Awareness: soft (Learn More, Discover How).  "
                            "Consideration: medium (See How It Works, Read the Story).  "
                            "Conversion/retargeting: direct (Book a Call, Apply Now, Join the Programme)."
                        ),
                        "example": "Book a Free Diagnostic Call",
                    },
                    "ci_grounding": {
                        "type": "string",
                        "description": (
                            "The specific CI data point this variant draws from.  Must name "
                            "the exact pain point text with frequency count, client win text "
                            "with frequency count, or content idea angle with score.  "
                            "Mandatory — a variant without a named CI grounding fails quality review."
                        ),
                        "example": "Pain point: 'I'm fully booked but still not hitting my revenue targets' (freq=11)",
                    },
                    "platform_notes": {
                        "type": "string",
                        "description": (
                            "Platform-specific compliance notes and word/character counts.  "
                            "For Google Ads: confirm headline character count (≤ 30) and "
                            "description character count (≤ 90).  For Facebook/Instagram: "
                            "confirm primary text word count and note any placement "
                            "recommendations (Feed, Stories, Reels).  Flag any targeting "
                            "considerations specific to this variant's angle."
                        ),
                    },
                },
            },
        },
        "recommended_test_order": {
            "type": "array",
            "description": (
                "Ordered list of variant_ids recommending the sequence in which to launch "
                "and test the variants.  The ordering must be justified by the campaign type, "
                "ICP profile, and the relative risk/reward of each angle.  Include a brief "
                "rationale as a separate string element or within a companion field."
            ),
            "items": {"type": "string"},
            "example": ["V1", "V4", "V2", "V3"],
        },
        "targeting_suggestion": {
            "type": "string",
            "description": (
                "ICP-grounded audience targeting recommendation for deploying this copy set.  "
                "Must name specific interest layers, behavioural signals, or custom audience "
                "strategies (lookalike, retargeting, exclusion audiences) relevant to the "
                "primary ICP segment.  Not a generic best-practice note."
            ),
        },
    },
}

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

__all__ = [
    "AD_COPY_GENERATION_SYSTEM_PROMPT_V1",
    "AD_COPY_GENERATION_OUTPUT_SCHEMA",
    "build_ad_copy_generation_user_prompt",
]
