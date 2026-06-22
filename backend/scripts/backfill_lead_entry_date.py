"""Backfill leads.entry_date from WGR for already-synced WGR leads.

The Phase 4 backfill loaded WGR leads before CI modelled ``entry_date``, so every
synced lead has it null. ``map_lead`` now carries ``entry_date``, so a full re-run
of the bulk loader would set it — but that re-processes ~56k rows across all
tables. This script does the minimal thing: read ``lead_id, entry_date`` from WGR
(read-only) and ``UPDATE leads SET entry_date = ... WHERE source='wgr' AND
external_id = lead_id`` in CI, batched.

Idempotent: re-running just re-sets the same values. Only touches WGR-sourced
leads (``source='wgr'``); CI-native leads are left alone.

Uses the same synchronous psycopg2 path as the bulk loader (CI is reachable only
through the transaction pooler, where sustained async writes hang).

Usage (from backend/):
    PYTHONPATH=. .venv/bin/python -m scripts.backfill_lead_entry_date --dry-run
    PYTHONPATH=. .venv/bin/python -m scripts.backfill_lead_entry_date --yes
"""

from __future__ import annotations

import sys

import psycopg2
from psycopg2.extras import execute_values

from app.services import wgr_client
from app.services.wgr_sync.bulk_load import _sync_url

BATCH = 1000


def _wgr_entry_dates() -> list[tuple[str, object]]:
    """(lead_id, entry_date) for every WGR lead that has an entry_date."""
    rows = wgr_client.query(
        "SELECT lead_id, entry_date FROM leads WHERE entry_date IS NOT NULL"
    )
    return [(r["lead_id"], r["entry_date"]) for r in rows if r.get("lead_id")]


def dry_run() -> None:
    pairs = _wgr_entry_dates()
    print(f"WGR leads with a non-null entry_date: {len(pairs)}")
    conn = psycopg2.connect(_sync_url())
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM leads WHERE source='wgr'")
            total = cur.fetchone()[0]
            cur.execute(
                "SELECT count(*) FROM leads WHERE source='wgr' AND entry_date IS NOT NULL"
            )
            already = cur.fetchone()[0]
        print(f"CI WGR leads: {total} total, {already} already have entry_date set")
    finally:
        conn.close()
    print("\nDry run only. Re-run with --yes to backfill.")


def execute() -> None:
    pairs = _wgr_entry_dates()
    print(f"Backfilling entry_date for up to {len(pairs)} WGR leads…")
    conn = psycopg2.connect(_sync_url())
    try:
        for i in range(0, len(pairs), BATCH):
            chunk = pairs[i : i + BATCH]
            with conn.cursor() as cur:
                # Update by matching external_id (= WGR lead_id) on WGR-sourced rows.
                execute_values(
                    cur,
                    """
                    UPDATE leads AS l
                    SET entry_date = v.entry_date
                    FROM (VALUES %s) AS v(external_id, entry_date)
                    WHERE l.source = 'wgr' AND l.external_id = v.external_id
                    """,
                    chunk,
                    template="(%s, %s::date)",
                )
            conn.commit()
        # cur.rowcount on execute_values only reflects the final sub-statement, so
        # report the true outcome by counting populated rows after the fact.
        with conn.cursor() as cur:
            cur.execute(
                "SELECT count(*) FROM leads WHERE source='wgr' AND entry_date IS NOT NULL"
            )
            populated = cur.fetchone()[0]
        print(f"Done. WGR leads with entry_date now set: {populated}")
    finally:
        conn.close()


if __name__ == "__main__":
    if "--yes" in sys.argv:
        execute()
    else:
        dry_run()
