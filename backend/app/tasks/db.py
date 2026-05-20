"""Shared synchronous database session factory for Celery tasks.

Celery workers run outside FastAPI's async event loop, so they need
a synchronous SQLAlchemy session (psycopg2 driver).
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings


def _get_sync_db_url(async_url: str) -> str:
    """Convert an asyncpg URL to a psycopg2 URL."""
    return async_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")


def make_sync_session() -> Session:
    """Create a new synchronous SQLAlchemy session for Celery tasks."""
    sync_url = _get_sync_db_url(settings.database_url)
    # Add sslmode for remote Supabase connections
    if "supabase" in sync_url and "sslmode" not in sync_url:
        separator = "&" if "?" in sync_url else "?"
        sync_url = f"{sync_url}{separator}sslmode=require"
    engine = create_engine(sync_url, pool_pre_ping=True)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    return SessionLocal()
