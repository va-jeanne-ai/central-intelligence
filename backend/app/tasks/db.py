"""Shared synchronous database session factory for Celery tasks.

Celery workers run outside FastAPI's async event loop, so they need
a synchronous SQLAlchemy session (psycopg2 driver).

The engine is module-level (built lazily on first call) so we don't
spin up a fresh connection pool every time a task runs. Supabase's
session-mode pooler caps total client connections per database
(15 on free tier); a per-call engine quickly exhausts that.
"""

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings


def _get_sync_db_url(async_url: str) -> str:
    """Convert an asyncpg URL to a psycopg2 URL."""
    return async_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")


# Module-level singletons — built on first use, reused for the lifetime
# of the Celery worker process. Each forked worker has its own copy
# (this module is imported per-process), which is the right scope for
# psycopg2's non-fork-safe connections.
_engine: Engine | None = None
_SessionLocal: sessionmaker | None = None


def _get_engine() -> Engine:
    """Lazily build the shared engine + session factory."""
    global _engine, _SessionLocal
    if _engine is not None:
        return _engine

    sync_url = _get_sync_db_url(settings.database_url)
    if "supabase" in sync_url and "sslmode" not in sync_url:
        separator = "&" if "?" in sync_url else "?"
        sync_url = f"{sync_url}{separator}sslmode=require"

    # Conservative pool sizing — Supabase free-tier pooler caps total
    # session-mode clients at 15. Keep this comfortably below so other
    # services (web backend, alembic, ad-hoc queries) have headroom.
    # pool_recycle keeps Supabase's idle-timeout from biting on quiet
    # periods between celery beat ticks.
    _engine = create_engine(
        sync_url,
        pool_pre_ping=True,
        pool_size=3,
        max_overflow=2,
        pool_recycle=300,
    )
    _SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False)
    return _engine


def make_sync_session() -> Session:
    """Return a synchronous SQLAlchemy session backed by the shared engine."""
    _get_engine()
    assert _SessionLocal is not None  # _get_engine populates this
    return _SessionLocal()
