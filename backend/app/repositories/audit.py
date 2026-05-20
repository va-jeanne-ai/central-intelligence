"""Repository for audit domain models."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import ErrorLog
from app.repositories.base import RepositoryBase


class ErrorLogRepository(RepositoryBase[ErrorLog]):
    """Repository for the ErrorLog model."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, ErrorLog)

    async def list_by_severity(
        self, severity: str, limit: int = 50
    ) -> list[ErrorLog]:
        """List errors filtered by severity, ordered by created_at desc."""
        stmt = (
            self._base_select()
            .where(ErrorLog.severity == severity)
            .order_by(ErrorLog.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_recent(
        self, hours: int = 24, limit: int = 100
    ) -> list[ErrorLog]:
        """List errors from the last N hours, ordered by created_at desc."""
        cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=hours)
        stmt = (
            self._base_select()
            .where(ErrorLog.created_at >= cutoff)
            .order_by(ErrorLog.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
