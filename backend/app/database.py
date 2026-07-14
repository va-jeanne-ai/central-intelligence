from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
import ssl as _ssl

from app.config import settings

_connect_args: dict = {}
if "supabase" in settings.database_url:
    _ssl_ctx = _ssl.create_default_context()
    _ssl_ctx.check_hostname = False
    _ssl_ctx.verify_mode = _ssl.CERT_NONE
    _connect_args["ssl"] = _ssl_ctx

# Supabase's session pooler admits at most `pool_size` clients per user/db
# (15 on this project) and rejects the rest with EMAXCONNSESSION. A NullPool
# here opened one fresh pooler client per request, so a single page-load burst
# of parallel API calls exhausted the 15 slots and every excess request 500'd.
# A bounded client-side pool queues excess requests on our side instead.
# Slot budget: API 5+2 here, worker 3+2 in tasks/db.py — 12 of 15, leaving
# headroom for local dev / psql against the same pooler.
engine = create_async_engine(
    settings.database_url,
    pool_size=5,
    max_overflow=2,
    pool_timeout=30,
    pool_pre_ping=True,
    pool_recycle=1800,
    echo=settings.debug,
    future=True,
    connect_args=_connect_args,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an async database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
