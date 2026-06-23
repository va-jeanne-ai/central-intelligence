# Plan — Constrain `best_use_case` to a closed enum + remap existing values

**Date:** 2026-06-24
**Branch:** `feat/best-use-case-enum` (fresh off latest `main`)
**Status:** Implemented — all 5 steps done. Backfill collapsed 240 → 17 values
(290 rows updated, idempotent) via one Opus call ($0.485). `Brand Positioning` +
`Lead Magnet` promoted into the seed (now 18 values).

## Problem

`best_use_case` on the `insights` table has sprawled to **240 distinct values across 303 rows
(213 singletons)**. The analyzer prompts only *suggest* example values ("in Title Case — e.g.
`Email Subject`, `Ad Copy`…") rather than constraining to a closed set, so the model emits
free-text, compound, sentence-like values:

- Near-duplicate slash-combos: `Instagram Reel / Email subject line` (11×),
  `Instagram Reel hook / Email subject line` (6×), `Instagram reel / Email subject line` (4×)
  — same intent, three spellings.
- Full sentences: `Email nurture sequence for cold leads who are currently satisfied`.

`humanize_label` (mapping.py) intentionally leaves multi-word values untouched, so this is **not**
a casing bug the existing normalization can fix — it's an unconstrained-prompt bug.

### Current blast radius (why this is low-urgency but worth fixing)

`best_use_case` is currently **display-only** — rendered as a label on the call-detail page
([sales-calls/[call_id]/page.tsx:98](../frontend/src/app/(app)/sales-calls/[call_id]/page.tsx#L98)).
It is **not** used for filtering, grouping, or routing:
- The content-idea sync convention ([ci.py:1213](../backend/app/routes/ci.py#L1213)) keys off
  `insight_type`, not `best_use_case` (the comment there is misleading).
- `content_idea_generator_v1.py` does not read `best_use_case` at all.

So nothing is broken today. The value is that this field is *meant* to drive downstream
content-pipeline routing, and in its current state it can't. Fixing it unblocks that future use
and cleans up the display.

## Goal

Make `best_use_case` a single-purpose **seed vocabulary that stays disciplined** — groupable and
filterable like the other five taxonomy fields (`insight_type`, `signal_family`,
`signal_strength`, `pain_layer`, `quote_confidence` — 8/13/4/7/2 distinct), but **open to growth**:
the model prefers the seed list and may coin a new value when nothing fits, subject to a strict
shape rule.

## Decisions (locked 2026-06-24)

1. **Single-value** — model picks the *one* best use case (not a slash-combo). Column stays scalar
   `Text`; no schema change.
2. **Seed enum, extensible** — define the list below once, but allow new values during analysis.
3. **New-value rule: strict shape, prefer-existing.** The prompt must instruct: pick the single
   best value FROM the list; only if none genuinely fits may the model coin ONE new value, and it
   must be **Title Case, ≤3 words, single-purpose, no slashes, no sentences.** This is the
   guardrail that prevents the original sprawl (the old prompt's free "e.g." creation is what
   produced 213 singletons).

## Seed enum

Single-purpose values (NOT slash-combos). Derived from the existing examples + the high-frequency
real values. **Confirmed:**

```
Email Subject
Email Nurture
Ad Copy
Ad Headline
Ad Targeting
Landing Page Hook
Sales Objection Handler
Coaching Curriculum
Content Idea
Instagram Reel
Instagram Post
Long-form Post
Webinar Hook
Testimonial
Case Study
Social Proof
```

Folds the coaching-analyzer's wins vocabulary (`Testimonial`, `Case Study`, `Social Proof`) into
the same shared set. New values the model coins (per the strict-shape rule) join this set over
time — periodically review distinct values and promote common new ones into the seed list.

## Changes

### 1. Define the enum once (new shared constant)
- Add `BEST_USE_CASE_VALUES: frozenset[str]` somewhere both prompts + the backfill import
  (proposed: `app/prompts/_taxonomy.py` or extend `wgr_sync/mapping.py`). Single source of truth.

### 2. Constrain the analyzer prompts
- `call_analyzer_v1.py:61` — replace the open "e.g." example list with the **prefer-existing +
  strict-shape** instruction: "Choose the single best value from this list: `<seed enum>`. Only if
  none genuinely fits may you coin ONE new value — Title Case, ≤3 words, single purpose, no
  slashes, no sentences. Prefer the list. Null only if no use case applies." Mirror the
  decisiveness of the `insight_type` / `signal_strength` phrasing.
- `coaching_analyzer_v1.py:64` — same instruction, same shared seed enum.
- Update the few-shot example rows in both files if any use a slash-combo value.
- Bump prompt version note if the files track versions.

### 3. Defensive validation on write (shape, not membership)
- In `tasks/call_analyzer.py` (insight persist path, ~line 253), since new values ARE allowed we
  can't coerce off-list → null. Instead enforce the **shape rule**: if `best_use_case` contains a
  slash, is >3 words, or otherwise violates the shape, normalize what we can (trim) and otherwise
  set null rather than store a sprawl value. Membership in the seed list is NOT required; clean
  new single-purpose values pass through. Low cost, prevents regression to slash-combos even if the
  model disobeys.

### 4. Backfill the 240 existing values → enum-or-clean-new
- New script `backend/scripts/remap_best_use_case.py`, same shape as the taxonomy backfill
  (dry-run default, `--yes` to apply, idempotent, touches only CI's mirror).
- Remapping is **semantic**, not mechanical, so it needs an LLM pass. Per the extensible design,
  each distinct value maps to **either a seed-enum value OR a clean new single-purpose value**
  (following the same shape rule) — not forced into the seed list if a distinct, legitimately new
  use case exists. In practice most of the 240 collapse onto seed values (the slash-combos and
  sentences); a handful may yield genuinely new clean values worth promoting into the seed list.
  - Pull distinct non-null values (240).
  - One batched Claude call (Haiku/Sonnet) mapping each distinct string → seed value | clean new
    value | `null`. 240 distinct strings → cheap single batch, not per-row.
  - **Paid API call** — per CLAUDE.md, I stop and confirm cost with you before running it.
  - Build `old_value -> new_value` dict, apply with the same per-value `UPDATE … WHERE = ANY`
    pattern as the existing backfill. Save the mapping to `.tmp/` for audit before writing.
  - Report any new values the remap produced so we can decide which to promote into the seed enum.

### 5. Docs
- `CHANGELOG.md` entry.
- If `INTEGRATIONS.md` / any taxonomy doc lists field vocabularies, add `best_use_case`'s enum.

## Validation / acceptance
- After remap: `SELECT DISTINCT best_use_case` contains NO slash-combos and NO sentence-like
  values; distinct count drops from 240 to roughly the seed size + a few clean new values
  (target ≤ ~25, vs 240 today).
- Re-running the remap script reports 0 changes (idempotent).
- Spot-check 10 remapped rows on the call-detail page — labels read cleanly and the mapping is
  semantically defensible.
- A fresh test call analysis emits a single-purpose value (seed or clean-new shape) for
  `best_use_case` — never a slash-combo.

## Risks / notes
- **Semantic remap is lossy** — compound values like `Email / Instagram post` collapse to one
  enum value. Acceptable given the field is display-only today and singular by design; the audit
  file in `.tmp/` preserves the originals if we ever regret a mapping.
- Touches the analyzer prompts → could subtly shift extraction behavior. Keep the change scoped to
  the `best_use_case` line only; don't refactor surrounding fields.
- No DB migration needed for option (a) — column stays `Text`.

## Out of scope
- Multi-value `best_use_case` (would need a schema change — separate decision).
- Wiring `best_use_case` into actual content-pipeline routing (this plan only makes it
  *routable*; using it is future work).
- Touching the other five taxonomy fields — they're already clean.
