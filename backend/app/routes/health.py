"""
Health check endpoint.

GET /api/v1/health

Validates database connectivity with a lightweight SELECT 1 probe and
returns a structured HealthResponse.  Designed for load-balancer liveness
checks and uptime monitors — always returns JSON, never raises 5xx unless
the framework itself is broken.
"""

import logging
import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_session
from app.schemas.chat import HealthResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])

_API_VERSION = "0.1.0"

# Recorded once at module import time; used to compute uptime on every request.
_PROCESS_START_TIME: float = time.monotonic()


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Liveness / readiness probe",
    description=(
        "Returns HTTP 200 with database=ok when the service and its primary "
        "database connection are healthy.  Returns HTTP 200 with database=error "
        "when the app is running but the database is unreachable — this lets "
        "orchestrators distinguish app crashes from infrastructure failures."
    ),
)
async def health_check(
    session: AsyncSession = Depends(get_session),
) -> HealthResponse:
    """Check application and database health."""
    db_status = "ok"

    try:
        await session.execute(text("SELECT 1"))
        logger.debug("Health probe: database OK")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Health probe: database unreachable — %s", exc)
        db_status = "error"

    supabase_url: str = getattr(settings, "supabase_url", "")
    auth_status = "configured" if supabase_url else "not_configured"

    uptime_seconds: float = time.monotonic() - _PROCESS_START_TIME

    return HealthResponse(
        status="ok",
        database=db_status,
        version=_API_VERSION,
        timestamp=datetime.now(tz=timezone.utc),
        auth=auth_status,
        redis="not_configured",
        uptime=uptime_seconds,
    )
