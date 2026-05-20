"""Generic async repository base using SQLAlchemy 2.0."""

from datetime import datetime, timedelta, timezone
from typing import Any, Generic, Optional, Type, TypeVar

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase

T = TypeVar("T", bound=DeclarativeBase)

_MISSING = object()  # sentinel for "no filter provided"


class RepositoryBase(Generic[T]):
    """Thread-safe, async-first generic repository.

    Concrete repositories extend this class and call ``super().__init__``
    with the target SQLAlchemy mapped class::

        class LeadRepository(RepositoryBase[Lead]):
            def __init__(self, session: AsyncSession):
                super().__init__(session, Lead)
    """

    def __init__(self, session: AsyncSession, model: Type[T]) -> None:
        self.session = session
        self.model = model

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _has_soft_delete(self) -> bool:
        """Return True when the model carries a ``deleted_at`` column."""
        return hasattr(self.model, "deleted_at")

    def _base_select(self):
        """Return a SELECT that automatically excludes soft-deleted rows."""
        stmt = select(self.model)
        if self._has_soft_delete():
            stmt = stmt.where(self.model.deleted_at.is_(None))  # type: ignore[attr-defined]
        return stmt

    def _apply_filters(self, stmt, filters: dict | None):
        """Append equality filters expressed as {column_name: value}."""
        if not filters:
            return stmt
        for column_name, value in filters.items():
            column = getattr(self.model, column_name, None)
            if column is not None:
                stmt = stmt.where(column == value)
        return stmt

    # ------------------------------------------------------------------
    # Primary key resolution
    # ------------------------------------------------------------------

    def _pk_columns(self):
        """Return the list of primary-key Column objects for the model."""
        from sqlalchemy import inspect as sa_inspect

        mapper = sa_inspect(self.model)
        return mapper.primary_key

    # ------------------------------------------------------------------
    # Public CRUD interface
    # ------------------------------------------------------------------

    async def get(self, id: Any) -> Optional[T]:
        """Fetch a single record by primary key, respecting soft deletes."""
        stmt = self._base_select().where(
            self._pk_columns()[0] == id  # type: ignore[index]
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list(
        self,
        limit: int = 100,
        offset: int = 0,
        filters: dict | None = None,
    ) -> list[T]:
        """Return a page of records, filtered and ordered by primary key.

        Soft-deleted records are always excluded.
        """
        stmt = self._base_select()
        stmt = self._apply_filters(stmt, filters)
        stmt = stmt.limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, **kwargs: Any) -> T:
        """Persist a new record and return the refreshed instance."""
        instance = self.model(**kwargs)
        self.session.add(instance)
        await self.session.flush()
        await self.session.refresh(instance)
        return instance

    async def update(self, id: Any, **kwargs: Any) -> Optional[T]:
        """Update column values on an existing record.

        Returns the updated instance, or ``None`` if the record does not
        exist or is soft-deleted.
        """
        instance = await self.get(id)
        if instance is None:
            return None
        for key, value in kwargs.items():
            if hasattr(instance, key):
                setattr(instance, key, value)
        self.session.add(instance)
        await self.session.flush()
        await self.session.refresh(instance)
        return instance

    async def delete(self, id: Any) -> bool:
        """Permanently remove a record from the database.

        Returns ``True`` when the row was deleted, ``False`` when not found.
        """
        instance = await self.get(id)
        if instance is None:
            return False
        await self.session.delete(instance)
        await self.session.flush()
        return True

    async def soft_delete(self, id: Any) -> bool:
        """Mark a record as deleted by setting ``deleted_at`` to now.

        Returns ``True`` on success, ``False`` when the record is not found
        or the model does not support soft deletes.
        """
        if not self._has_soft_delete():
            return await self.delete(id)

        instance = await self.get(id)
        if instance is None:
            return False
        instance.deleted_at = datetime.now(tz=timezone.utc)  # type: ignore[attr-defined]
        self.session.add(instance)
        await self.session.flush()
        return True

    async def update_optimistic(
        self,
        id: Any,
        expected_updated_at: datetime,
        **kwargs: Any,
    ) -> T:
        """Update a record only when the client's ETag matches the current row.

        This implements optimistic concurrency control using the ``updated_at``
        timestamp as a version token.  The client must supply the
        ``updated_at`` value it received from a prior GET (decoded from the
        ``If-Match`` header by the :func:`~app.dependencies.optimistic_lock.require_if_match`
        dependency).

        Comparison tolerance
        ~~~~~~~~~~~~~~~~~~~~
        Database drivers may round sub-microsecond precision when
        round-tripping through the wire protocol.  A tolerance of 1 µs is
        applied so that otherwise-identical timestamps are treated as equal.

        Parameters
        ----------
        id:
            Primary key of the record to update.
        expected_updated_at:
            The ``updated_at`` datetime the client last saw (from ``If-Match``).
        **kwargs:
            Column-value pairs to apply to the record.

        Returns
        -------
        T
            The refreshed, updated model instance.

        Raises
        ------
        HTTPException
            - **404 Not Found** — record does not exist or is soft-deleted.
            - **409 Conflict** (via :class:`~app.middleware.optimistic_lock.StaleUpdateError`)
              — ``updated_at`` does not match; another writer has modified the
              record since the client fetched it.
        """
        # Import here to avoid a circular import at module load time.
        from app.middleware.optimistic_lock import StaleUpdateError

        instance = await self.get(id)
        if instance is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": {
                        "code": "NOT_FOUND",
                        "message": f"Resource with id '{id}' was not found.",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "request_id": None,
                    }
                },
            )

        # Normalise both datetimes to UTC before comparison.
        row_updated_at: datetime = instance.updated_at  # type: ignore[attr-defined]
        if row_updated_at.tzinfo is None:
            row_updated_at = row_updated_at.replace(tzinfo=timezone.utc)
        if expected_updated_at.tzinfo is None:
            expected_updated_at = expected_updated_at.replace(tzinfo=timezone.utc)

        # Allow a 1-microsecond tolerance to absorb DB driver rounding.
        _TOLERANCE = timedelta(microseconds=1)
        if abs(row_updated_at - expected_updated_at) > _TOLERANCE:
            raise StaleUpdateError()

        for key, value in kwargs.items():
            if hasattr(instance, key):
                setattr(instance, key, value)

        self.session.add(instance)
        await self.session.flush()
        await self.session.refresh(instance)
        return instance

    async def count(self, filters: dict | None = None) -> int:
        """Return the number of active (non-soft-deleted) records matching filters."""
        stmt = select(func.count()).select_from(self.model)
        if self._has_soft_delete():
            stmt = stmt.where(self.model.deleted_at.is_(None))  # type: ignore[attr-defined]
        stmt = self._apply_filters(stmt, filters)
        result = await self.session.execute(stmt)
        return result.scalar_one()
