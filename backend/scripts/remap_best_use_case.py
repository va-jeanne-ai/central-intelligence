"""One-time remap: collapse free-text ``best_use_case`` values onto the
disciplined seed vocabulary (or a clean new single-purpose value).

``best_use_case`` sprawled to ~240 distinct values (slash-combos, sentences)
before the analyzer prompts were constrained (see
``app/prompts/_taxonomy.py`` and ``plans/2026-06-24-best-use-case-enum.md``).
This script normalizes the rows already stored. The prompt change prevents new
sprawl; this fixes the backlog.

Mapping is semantic (e.g. ``"Email nurture sequence for cold leads…"`` ->
``"Email Nurture"``), so it uses one batched Opus call over the DISTINCT values
(240, not 303 rows). Each distinct value maps to either a seed value or a clean
new single-purpose value following the same shape rule the prompt enforces
(Title Case, <=3 words, no slashes/sentences). The model's output is run through
``normalize_best_use_case`` as a final guard before anything is written.

Flow (safe by default):
    1. DRY RUN (default): call Opus, write the proposed mapping to
       ``.tmp/best_use_case_remap.json`` for human review. NO DB writes.
    2. APPLY (``--apply``): read the reviewed mapping file (does NOT re-call the
       API) and UPDATE the rows in one transaction.

So the paid API call happens once during the dry run; ``--apply`` is free and
deterministic against the reviewed file. Idempotent — re-running APPLY changes
nothing once normalized. Touches only CI's mirror, never upstream WGR.

Usage:
    python -m scripts.remap_best_use_case            # dry run: call Opus, write mapping file
    python -m scripts.remap_best_use_case --apply    # apply the reviewed mapping file
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from sqlalchemy import text

from app.config import settings
from app.database import engine
from app.prompts._taxonomy import (
    BEST_USE_CASE_SEED,
    BEST_USE_CASE_SEED_LIST_STR,
    normalize_best_use_case,
)

MODEL = "claude-opus-4-8"
MAPPING_FILE = Path(__file__).resolve().parents[1] / ".tmp" / "best_use_case_remap.json"

SYSTEM_PROMPT = """\
You normalize a messy free-text field called `best_use_case` onto a disciplined \
vocabulary. Each value describes where a marketing insight is best used downstream.

You will receive a JSON array of distinct raw values. Map EACH one to a single \
clean target value, following these rules in order:

1. STRONGLY PREFER this seed list — if a raw value's primary intent matches one, use it exactly:
{seed}

2. Many raw values are slash-combos ("Instagram Reel / Email subject line") or \
sentences ("Email nurture sequence for cold leads who are satisfied"). Pick the \
SINGLE dominant use case and map to the matching seed value. For a slash-combo, \
choose the first / most prominent use unless a later one is clearly the primary intent.

3. Only if NO seed value reasonably fits may you coin a new target value. It MUST be: \
Title Case, 3 words or fewer, single-purpose, NO slashes, NO sentences. Reuse the \
SAME new value across raw inputs that mean the same thing (do not invent variants).

4. Never output null — every raw value has a usable downstream purpose.

Return ONLY a JSON object mapping each raw value (verbatim, as the key) to its \
target value (the string). No prose, no markdown fences.
"""


async def _fetch_distinct() -> list[str]:
    async with engine.connect() as conn:
        return (
            await conn.execute(
                text(
                    "SELECT DISTINCT best_use_case FROM insights "
                    "WHERE best_use_case IS NOT NULL ORDER BY 1"
                )
            )
        ).scalars().all()


def _extract_json_object(s: str) -> str:
    s = s.strip()
    if s.startswith("```"):
        s = s.split("```", 2)[1]
        if s.startswith("json"):
            s = s[4:]
        s = s.strip()
    start, end = s.find("{"), s.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("No JSON object found in model output.")
    return s[start : end + 1]


def _call_opus(values: list[str]) -> dict[str, str]:
    import anthropic  # lazy import — large module

    if not settings.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set; cannot run the remap.")

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    system = SYSTEM_PROMPT.format(seed=BEST_USE_CASE_SEED_LIST_STR)
    user = "Map these distinct values:\n" + json.dumps(values, ensure_ascii=False)

    msg = client.messages.create(
        model=MODEL,
        max_tokens=16384,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    raw = msg.content[0].text
    mapping = json.loads(_extract_json_object(raw))
    if not isinstance(mapping, dict):
        raise ValueError("Expected a JSON object mapping raw -> target.")

    usage = msg.usage
    print(
        f"Opus usage: {usage.input_tokens} in / {usage.output_tokens} out tokens "
        f"(~${usage.input_tokens/1e6*15 + usage.output_tokens/1e6*75:.3f} at Opus pricing)"
    )
    return mapping


def _clean_mapping(raw_values: list[str], mapping: dict[str, str]) -> dict[str, str]:
    """Final guard: every raw value must have a target that passes the shape rule.

    Drops the raw value (leaves it untouched in DB) if the model omitted it or
    produced a target that fails the shape rule and can't be salvaged.
    """
    seed = set(BEST_USE_CASE_SEED)
    cleaned: dict[str, str] = {}
    new_values: set[str] = set()
    skipped: list[str] = []
    for v in raw_values:
        target = mapping.get(v)
        norm = normalize_best_use_case(target) if isinstance(target, str) else None
        if not norm:
            skipped.append(v)
            continue
        cleaned[v] = norm
        if norm not in seed:
            new_values.add(norm)
    if skipped:
        print(f"\n⚠ {len(skipped)} raw value(s) had no usable target (left unchanged):")
        for v in skipped:
            print(f"    {v!r}")
    if new_values:
        print(f"\nNEW values coined (not in seed) — review for promotion to seed list:")
        for nv in sorted(new_values):
            print(f"    {nv}")
    return cleaned


async def dry_run() -> None:
    values = await _fetch_distinct()
    print(f"Distinct best_use_case values to remap: {len(values)}")
    mapping = _call_opus(values)
    cleaned = _clean_mapping(values, mapping)

    # Summarize the collapse.
    targets = sorted(set(cleaned.values()))
    print(f"\nDistinct targets after remap: {len(targets)} (from {len(values)})")
    for t in targets:
        n = sum(1 for x in cleaned.values() if x == t)
        print(f"  {n:>4}  {t}")

    MAPPING_FILE.parent.mkdir(parents=True, exist_ok=True)
    MAPPING_FILE.write_text(json.dumps(cleaned, indent=2, ensure_ascii=False))
    print(f"\nProposed mapping written to {MAPPING_FILE}")
    print("Review it, then run with --apply to write to the DB.")


async def apply() -> None:
    if not MAPPING_FILE.exists():
        print(f"No mapping file at {MAPPING_FILE}. Run the dry run first.")
        sys.exit(1)
    mapping: dict[str, str] = json.loads(MAPPING_FILE.read_text())

    # Only rows whose current value differs from the target need updating.
    # Group by target so each UPDATE sets one literal across many old values.
    by_target: dict[str, list[str]] = {}
    for old, new in mapping.items():
        if old != new:
            by_target.setdefault(new, []).append(old)

    if not by_target:
        print("Nothing to apply — all values already normalized.")
        return

    total = sum(len(olds) for olds in by_target.values())
    async with engine.begin() as conn:
        affected = 0
        for new, olds in by_target.items():
            res = await conn.execute(
                text(
                    "UPDATE insights SET best_use_case = :new "
                    "WHERE best_use_case = ANY(:olds)"
                ),
                {"new": new, "olds": olds},
            )
            affected += res.rowcount or 0
    print(
        f"Applied remap: {affected} rows updated across {len(by_target)} target values "
        f"({total} distinct old values remapped)."
    )


if __name__ == "__main__":
    if "--apply" in sys.argv:
        asyncio.run(apply())
    else:
        asyncio.run(dry_run())
