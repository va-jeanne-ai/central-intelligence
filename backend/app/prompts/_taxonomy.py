"""Shared insight taxonomy vocabularies.

Single source of truth for controlled-vocabulary values that the analyzer
prompts reference and the persist path enforces. Keeping the list here (rather
than inline in each prompt) means the prompt instruction, the write-time
validation, and the backfill script can't drift apart.

Currently holds ``best_use_case`` — a *seed* vocabulary that is open to growth:
the model prefers these values but may coin a new one when none fits, subject to
a strict shape rule (Title Case, ≤3 words, single purpose, no slashes / no
sentences). The shape rule is what prevents the field from sprawling back into
the free-text mess it started as (240 distinct values, 213 singletons).
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# best_use_case — seed vocabulary (extensible)
# ---------------------------------------------------------------------------

# Where an insight is best used downstream. Single-purpose values only — never
# slash-combos. New clean values may join this list over time; review distinct
# stored values periodically and promote common new ones here.
BEST_USE_CASE_SEED: tuple[str, ...] = (
    "Email Subject",
    "Email Nurture",
    "Ad Copy",
    "Ad Headline",
    "Ad Targeting",
    "Landing Page Hook",
    "Sales Objection Handler",
    "Coaching Curriculum",
    "Content Idea",
    "Instagram Reel",
    "Instagram Post",
    "Long-form Post",
    "Webinar Hook",
    "Testimonial",
    "Case Study",
    "Social Proof",
    # Promoted from the 2026-06-24 remap of existing rows (clean new values the
    # model coined when no seed value fit; see plans/2026-06-24-best-use-case-enum.md).
    "Brand Positioning",
    "Lead Magnet",
)

# Rendered into the prompt field descriptions as a comma-separated list.
BEST_USE_CASE_SEED_LIST_STR = ", ".join(f"`{v}`" for v in BEST_USE_CASE_SEED)

# Max words for a coined best_use_case value (the strict shape rule).
_BEST_USE_CASE_MAX_WORDS = 3


def normalize_best_use_case(value: object) -> object:
    """Enforce the best_use_case *shape* rule on a stored value.

    Membership in :data:`BEST_USE_CASE_SEED` is **not** required — clean new
    single-purpose values are allowed by design. This only rejects values that
    violate the shape (the sprawl signature):

    - contains ``/`` (slash-combo, e.g. ``"Instagram Reel / Email subject line"``)
    - more than ``_BEST_USE_CASE_MAX_WORDS`` words (sentence-like)

    Anything rejected becomes ``None`` (the column is nullable) rather than
    storing a sprawl value. Non-strings and ``None`` pass through unchanged so
    callers can apply this uniformly.
    """
    if not isinstance(value, str):
        return value
    v = value.strip()
    if not v:
        return None
    if "/" in v:
        return None
    if len(v.split()) > _BEST_USE_CASE_MAX_WORDS:
        return None
    return v
