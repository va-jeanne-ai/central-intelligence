"""Clear Central Intelligence's DOMAIN data while preserving config/auth.

Part of the WGR-database rebase (see docs/ + the approved plan). CI's domain
tables are about to be re-sourced from the client's (Greg/WGR) database, so we
wipe the empty/seed-fed domain rows but keep the irreplaceable config: encrypted
integration credentials, Supabase-mirrored users, offers, chat history, audit log.

WHY BATCHED DELETE (not TRUNCATE)
---------------------------------
CI's Supabase is reachable only through the transaction pooler, which enforces a
short server ``statement_timeout`` and ignores per-session ``SET``. ``TRUNCATE``
needs an ACCESS EXCLUSIVE lock and consistently exceeds that timeout (especially
on ``embeddings`` with its pgvector index). Batched ``DELETE`` in small chunks
stays comfortably under the timeout, takes only row locks, and is restartable.

SAFETY
------
* Operates ONLY on CI's own DB (``settings.database_url`` → iqqobmubutxwhtvpdrnf),
  reusing the app's async engine (``app.database.engine``).
* Explicit CLEAR / PRESERVE allow-lists — never "drop everything", never DDL.
* Refuses to run unless every public table is in exactly one list.
* ``alembic_version`` is never touched.
* ``--yes`` required to execute; default is a dry-run report. Idempotent.

A clean backup of the PRESERVE tables already exists (Phase 0:
.tmp/ci-preserve-backup-*.sql). CLEAR tables are re-derivable from WGR/external.

Usage (from backend/):
    .venv/bin/python -m scripts.clear_domain_data            # dry run
    .venv/bin/python -m scripts.clear_domain_data --yes      # execute
"""

from __future__ import annotations

import asyncio
import sys

from sqlalchemy import text

from app.config import settings
from app.database import engine

# Delete children before parents so row-level FK checks never block.
# Order matters: leaf/child tables first, hub tables (leads/calls/members) last.
CLEAR_ORDERED = [
    # embeddings / queue (no inbound FKs)
    "embeddings", "embed_pending",
    # call-derived children
    "insight_tags", "content_ideas", "insights",
    # email children → parents
    "email_messages", "email_threads",
    # google sync
    "google_drive_files", "google_calendar_events",
    # lead/member children
    "lead_notes", "member_notes", "goals", "pain_points", "wins", "objections",
    "appointments", "support_tickets",
    # marketing / stats (independent)
    "market_signals", "social_stats", "social_comments", "email_campaigns",
    "funnel_events", "funnel_stats", "ads_stats", "dm_stats", "promotions", "icp",
    # ops logs (independent)
    "sync_log", "error_log", "idempotency_keys",
    # hubs last
    "calls", "members", "leads",
]

PRESERVE = [
    "users", "integrations", "user_integration_credentials",
    "business_profile", "offers", "monthly_preferences", "tag_dictionary",
    "chat_sessions", "chat_messages", "audit_log",
    "embedding_budget", "teams",
]

NEVER = ["alembic_version"]

BATCH = 500  # rows per DELETE — small enough to stay under the pooler timeout


async def _all_tables(conn) -> set[str]:
    rows = (await conn.execute(
        text("SELECT tablename FROM pg_tables WHERE schemaname='public'")
    )).fetchall()
    return {r[0] for r in rows}


async def _count(conn, t: str) -> int:
    return (await conn.execute(text(f'SELECT count(*) FROM public."{t}"'))).scalar_one()


async def _delete_batched(t: str) -> int:
    """Delete all rows from one table in BATCH-sized chunks. Returns total deleted."""
    total = 0
    while True:
        # Each DELETE runs in its own short transaction (engine.begin) so a chunk
        # never accumulates a long-held lock.
        async with engine.begin() as conn:
            res = await conn.execute(text(f"""
                DELETE FROM public."{t}"
                WHERE ctid IN (
                    SELECT ctid FROM public."{t}" LIMIT {BATCH}
                )
            """))
            n = res.rowcount or 0
        total += n
        if n < BATCH:
            break
    return total


async def main(execute: bool) -> int:
    async with engine.connect() as conn:
        actual = await _all_tables(conn)
        accounted = set(CLEAR_ORDERED) | set(PRESERVE) | set(NEVER)
        unaccounted = actual - accounted
        if unaccounted:
            print("ABORT: unclassified tables:", sorted(unaccounted))
            return 2

        clear_present = [t for t in CLEAR_ORDERED if t in actual]

        print(f"DB: {settings.database_url.split('@')[-1]}")
        print(f"Mode: {'EXECUTE (batched DELETE)' if execute else 'DRY RUN'}\n")
        print("PRESERVE (untouched):")
        for t in PRESERVE:
            if t in actual:
                print(f"  keep  {t:30s} {await _count(conn, t):>7} rows")
        print("\nCLEAR:")
        for t in clear_present:
            print(f"  wipe  {t:30s} {await _count(conn, t):>7} rows")

    if not execute:
        print("\nDry run only. Re-run with --yes to delete.")
        return 0

    print("\nDeleting...")
    for t in clear_present:
        n = await _delete_batched(t)
        print(f"  {t:30s} deleted {n}")

    async with engine.connect() as conn:
        print("\nVerification:")
        ok = True
        for t in clear_present:
            c = await _count(conn, t)
            if c:
                ok = False
            print(f"  {t:30s} {c:>7} rows {'✓' if c == 0 else '✗ STILL HAS ROWS'}")
        print("\nPreserved spot-check:")
        for t in ("integrations", "offers", "chat_messages", "audit_log"):
            if t in actual:
                print(f"  {t:30s} {await _count(conn, t):>7} rows (kept)")
    print("\nDONE." if ok else "\nDONE WITH ERRORS.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main(execute="--yes" in sys.argv)))
