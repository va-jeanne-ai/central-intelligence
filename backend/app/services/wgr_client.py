"""WGR (client) Postgres client — STRICTLY READ-ONLY.

Wraps a direct Postgres connection to the client's Supabase project via
``CLIENT_DATABASE_URL`` / ``settings.client_database_url`` (the legacy env name
``WGR_DATABASE_URL`` is still accepted — see ``app/config.py``).
This connection gives full-schema visibility and reliable bulk reads that the
anon PostgREST key cannot — see ``docs/client-supabase-connection.md``.

────────────────────────────────────────────────────────────────────────────
SAFETY — the credential behind ``CLIENT_DATABASE_URL`` is the ``postgres`` role and
is WRITE-CAPABLE on the client's production database. This is the client's data;
we never modify it (project safety rule). To make writes structurally impossible
on our side, every connection opened here:

  * is put in read-only session mode (``SET SESSION CHARACTERISTICS AS
    TRANSACTION READ ONLY``) BEFORE any query runs, and
  * only exposes ``SELECT``-returning helpers (``query`` / ``iter_rows`` /
    ``count`` / schema introspection). There is no write path in this module.

If a caller ever needs to write, it must NOT use this client. Ask the client for
a dedicated read-only Postgres role to remove the footgun entirely.
────────────────────────────────────────────────────────────────────────────

Sync style (psycopg2), matching the ``ghl_client`` / ``mailchimp_client``
convention so it slots into Celery worker threads cleanly.
"""

from __future__ import annotations

import contextlib
import logging
from typing import Any, Iterator, Optional

import psycopg2
import psycopg2.extras

from app.config import settings

logger = logging.getLogger(__name__)

_CONNECT_TIMEOUT = 15  # seconds
_DEFAULT_PAGE_SIZE = 1000


class WgrAccessError(RuntimeError):
    """Raised when ``CLIENT_DATABASE_URL`` is not configured."""


def _dsn() -> str:
    dsn = settings.client_database_url
    if not dsn:
        raise WgrAccessError(
            "CLIENT_DATABASE_URL is not set — client Postgres access is unavailable. "
            "Set it in backend/.env (see docs/client-supabase-connection.md)."
        )
    return dsn


@contextlib.contextmanager
def _connection():
    """Yield a psycopg2 connection forced into READ ONLY, autocommit mode.

    Read-only is set at the session level before the caller runs anything, so
    no statement on this connection can mutate the client's database. The
    connection is always closed on exit.
    """
    conn = psycopg2.connect(_dsn(), connect_timeout=_CONNECT_TIMEOUT)
    try:
        # autocommit so the read-only session characteristic applies to every
        # implicit transaction; readonly=True issues SET SESSION ... READ ONLY.
        conn.set_session(readonly=True, autocommit=True)
        yield conn
    finally:
        conn.close()


def query(sql: str, params: Optional[tuple] = None) -> list[dict[str, Any]]:
    """Run a read-only ``SELECT`` and return all rows as dicts.

    Intended for small/bounded results (schema introspection, counts, lookups).
    For large table scans use :func:`iter_rows` so we don't buffer everything.
    """
    with _connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            return [dict(r) for r in cur.fetchall()]


def iter_rows(
    table: str,
    *,
    columns: str = "*",
    where: Optional[str] = None,
    params: Optional[tuple] = None,
    order_by: Optional[str] = None,
    page_size: int = _DEFAULT_PAGE_SIZE,
) -> Iterator[dict[str, Any]]:
    """Stream rows from ``public.<table>`` in keyset-free LIMIT/OFFSET pages.

    Yields one dict per row. ``table``/``columns``/``order_by`` are identifiers
    we control (callers pass known table names), not user input; values always
    go through ``params`` placeholders. Pages keep memory bounded for the large
    tables (sales_activities ~19k, lead_opt_in_events ~14k, etc.).
    """
    safe_table = _qualify(table)
    base = f"SELECT {columns} FROM {safe_table}"
    if where:
        base += f" WHERE {where}"
    if order_by:
        base += f" ORDER BY {order_by}"

    offset = 0
    with _connection() as conn:
        while True:
            page_sql = f"{base} LIMIT %s OFFSET %s"
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(page_sql, (params or ()) + (page_size, offset))
                rows = cur.fetchall()
            if not rows:
                break
            for r in rows:
                yield dict(r)
            if len(rows) < page_size:
                break
            offset += page_size


def count(table: str, *, where: Optional[str] = None, params: Optional[tuple] = None) -> int:
    sql = f"SELECT count(*) AS n FROM {_qualify(table)}"
    if where:
        sql += f" WHERE {where}"
    return query(sql, params)[0]["n"]


# ---------------------------------------------------------------------------
# Schema introspection
# ---------------------------------------------------------------------------

def list_tables(schema: str = "public") -> list[str]:
    rows = query(
        """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = %s AND table_type = 'BASE TABLE'
        ORDER BY table_name
        """,
        (schema,),
    )
    return [r["table_name"] for r in rows]


def columns(table: str, schema: str = "public") -> list[dict[str, Any]]:
    return query(
        """
        SELECT column_name, data_type, is_nullable, column_default
        FROM information_schema.columns
        WHERE table_schema = %s AND table_name = %s
        ORDER BY ordinal_position
        """,
        (schema, table),
    )


def primary_keys(table: str, schema: str = "public") -> list[str]:
    rows = query(
        """
        SELECT a.attname AS column_name
        FROM pg_index i
        JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
        WHERE i.indrelid = %s::regclass AND i.indisprimary
        """,
        (f'"{schema}"."{table}"',),
    )
    return [r["column_name"] for r in rows]


def foreign_keys(schema: str = "public") -> list[dict[str, Any]]:
    """All FK relationships in the schema (declared constraints only)."""
    return query(
        """
        SELECT
            tc.table_name        AS from_table,
            kcu.column_name      AS from_column,
            ccu.table_name       AS to_table,
            ccu.column_name      AS to_column
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
            ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
        JOIN information_schema.constraint_column_usage ccu
            ON ccu.constraint_name = tc.constraint_name AND ccu.table_schema = tc.table_schema
        WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_schema = %s
        ORDER BY from_table, from_column
        """,
        (schema,),
    )


def _qualify(table: str) -> str:
    """Quote a bare table name into ``public."table"``. Rejects qualified or
    quoted input so callers can't sneak in a schema or injection via the name."""
    if '"' in table or "." in table:
        raise ValueError(f"Unexpected table identifier: {table!r}")
    return f'public."{table}"'
