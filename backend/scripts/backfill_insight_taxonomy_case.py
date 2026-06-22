"""One-time backfill: Title-Case raw insight taxonomy values.

Insight taxonomy fields (``insight_type``, ``signal_family``, ``signal_strength``,
``pain_layer``, ``quote_confidence``, ``best_use_case``) arrived in mixed casing:
most WGR values are already Title Case, but ``pain_layer`` was lowercase across
many rows and one CI-analyzed call used snake_case throughout. The WGR sync
mapping now normalizes these on ingest (``mapping.humanize_label`` over
``_INSIGHT_TAXONOMY_FIELDS``); this script fixes the rows already stored.

Idempotent — re-running changes nothing once normalized. Touches only CI's
mirror, never the upstream WGR database.

Usage:
    python -m scripts.backfill_insight_taxonomy_case          # dry run
    python -m scripts.backfill_insight_taxonomy_case --yes    # execute
"""

from __future__ import annotations

import asyncio
import sys

from sqlalchemy import text

from app.database import engine
from app.services.wgr_sync.mapping import (
    _INSIGHT_TAXONOMY_FIELDS,
    humanize_label,
)

FIELDS = sorted(_INSIGHT_TAXONOMY_FIELDS)


async def main(execute: bool) -> None:
    cols = ", ".join(["id", *FIELDS])
    async with engine.connect() as conn:
        rows = (
            await conn.execute(text(f"SELECT {cols} FROM insights"))
        ).mappings().fetchall()

    # Build the set of changes: (id, field) -> new_value.
    updates: list[tuple[str, dict[str, str]]] = []
    for r in rows:
        diff = {f: humanize_label(r[f]) for f in FIELDS if humanize_label(r[f]) != r[f]}
        if diff:
            updates.append((r["id"], diff))

    per_field: dict[str, int] = {}
    for _id, diff in updates:
        for f in diff:
            per_field[f] = per_field.get(f, 0) + 1

    print(f"Insight rows needing normalization: {len(updates)} / {len(rows)}")
    for f in FIELDS:
        if per_field.get(f):
            print(f"  {f}: {per_field[f]} values")

    if not execute:
        print("\nDry run only. Re-run with --yes to apply.")
        return

    # Apply per-field UPDATEs in one transaction. Each field updates only the
    # ids whose value changes, so it's a handful of statements, not row-by-row.
    async with engine.begin() as conn:
        for f in FIELDS:
            ids = [i for i, diff in updates if f in diff]
            if not ids:
                continue
            # Group ids by their target value so each UPDATE sets one literal.
            by_value: dict[str, list[str]] = {}
            for i, diff in updates:
                if f in diff:
                    by_value.setdefault(diff[f], []).append(i)
            for new_value, id_list in by_value.items():
                await conn.execute(
                    text(
                        f'UPDATE insights SET "{f}" = :v WHERE id = ANY(:ids)'
                    ),
                    {"v": new_value, "ids": id_list},
                )
        print(f"\nApplied normalization to {len(updates)} insight rows.")


if __name__ == "__main__":
    execute = "--yes" in sys.argv
    asyncio.run(main(execute))
