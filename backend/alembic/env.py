"""Alembic async environment for Central Intelligence backend.

Uses SQLAlchemy's async engine so migrations run through the same asyncpg
driver as the application.  All models are imported via app.models so
autogenerate can detect every table in Base.metadata.
"""

import asyncio
import os
from logging.config import fileConfig

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# Load backend/.env before reading DATABASE_URL — keeps `alembic upgrade head`
# usable without exporting env vars in every shell.
load_dotenv()

# ---------------------------------------------------------------------------
# Import Base *and* all model modules so that their tables are registered
# in Base.metadata before autogenerate inspects it.
# ---------------------------------------------------------------------------
from app.models import Base  # noqa: F401 — side-effect: registers all mapped classes

# ---------------------------------------------------------------------------
# Alembic Config object — provides access to values in alembic.ini
# ---------------------------------------------------------------------------
config = context.config

# Override sqlalchemy.url from the environment when DATABASE_URL is set.
# This lets CI/CD inject the real connection string without touching alembic.ini.
_db_url = os.environ.get("DATABASE_URL")
if _db_url:
    # Escape bare '%' characters so configparser doesn't treat them as
    # interpolation tokens (e.g. URL-encoded passwords like %3B).
    config.set_main_option("sqlalchemy.url", _db_url.replace("%", "%%"))

# Set up Python logging from the [loggers] section of alembic.ini.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# The MetaBase to use for autogenerate support.
target_metadata = Base.metadata


# ---------------------------------------------------------------------------
# Offline migrations — emit SQL without a live DB connection
# ---------------------------------------------------------------------------

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    Configures the context with just a URL and not an Engine.  Calls to
    context.execute() emit the resulting SQL to the script output.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # Include schema comparisons for column-level changes
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


# ---------------------------------------------------------------------------
# Online migrations — run against a live async engine
# ---------------------------------------------------------------------------

def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Create an async engine and run migrations through a sync connection wrapper."""
    import ssl as _ssl
    from sqlalchemy.ext.asyncio import create_async_engine

    url = config.get_main_option("sqlalchemy.url")

    # Mirror app/database.py: hosted Supabase needs TLS; a local stack
    # (supabase start / plain Postgres on localhost) rejects SSL upgrades.
    connect_args: dict = {}
    if "supabase" in url:
        ssl_ctx = _ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = _ssl.CERT_NONE
        connect_args["ssl"] = ssl_ctx

    connectable = create_async_engine(
        url,
        poolclass=pool.NullPool,
        connect_args=connect_args,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Entry point for online migrations — drives the asyncio event loop."""
    asyncio.run(run_async_migrations())


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
