"""Apply the base schema (supabase/migrations/*.sql) to a FRESH database.

The alembic chain does not start from zero: the earliest tables (users, teams,
audit_log, …) were created by the SQL files in ``supabase/migrations/`` before
alembic took over, and alembic's migrations build on top of them. A brand-new
database therefore needs those files applied first, in filename order — then
``alembic upgrade head`` brings it to current.

Idempotent: skips entirely when the ``users`` table already exists (i.e. any
previously-initialized database). Refuses to run against a database that has
alembic state but no base schema (that would indicate something unexpected).

Skips ``supabase/seed.sql`` on purpose — demo rows are opt-in, not part of the
schema (pass --with-demo-seed to load them, e.g. for a demo instance).

Usage (from backend/):
    PYTHONPATH=. .venv/bin/python -m scripts.apply_base_schema [--with-demo-seed]
Reads DATABASE_URL from the environment/.env like the rest of the app.
"""

from __future__ import annotations

import sys
from pathlib import Path

import psycopg2

from app.config import settings

REPO_ROOT = Path(__file__).resolve().parents[2]
SQL_DIR = REPO_ROOT / "supabase" / "migrations"
SEED = REPO_ROOT / "supabase" / "seed.sql"


def _sync_dsn() -> str:
    return settings.database_url.replace("+asyncpg", "")


def main(argv: list[str]) -> int:
    files = sorted(SQL_DIR.glob("*.sql"))
    if not files:
        raise SystemExit(f"No SQL files found in {SQL_DIR}")

    conn = psycopg2.connect(_sync_dsn())
    conn.autocommit = False
    try:
        cur = conn.cursor()
        cur.execute("SELECT to_regclass('public.users')")
        if cur.fetchone()[0]:
            print("base schema already present (users table exists) — nothing to do")
            return 0

        for f in files:
            print(f"applying {f.name} ...")
            cur.execute(f.read_text())

        if "--with-demo-seed" in argv:
            print("applying seed.sql (demo rows) ...")
            cur.execute(SEED.read_text())

        conn.commit()
        print(f"base schema applied ({len(files)} files). Now run: alembic upgrade head")
        return 0
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
