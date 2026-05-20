"""Deterministic error logging agent with retry queue.

This is NOT an AI agent -- it is a structured logging utility that persists
errors to the ``error_logs`` database table via ``AsyncSessionLocal``.
"""

import logging
import traceback
from datetime import datetime, timezone
from typing import Any

from app.database import AsyncSessionLocal
from app.models.audit import ErrorLog

logger = logging.getLogger(__name__)


class ErrorHandlerAgent:
    """Async error logging agent with retry queue.

    Singleton instance used across the app for structured error logging
    to the error_logs database table.
    """

    def __init__(self) -> None:
        self._retry_queue: list[dict[str, Any]] = []
        self._max_retries: int = 3

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def log_error(
        self,
        error_message: str,
        error_code: str,
        context: dict | None = None,
        severity: str = "error",
        agent_id: str | None = None,
        request_id: str | None = None,
        user_id: str | None = None,
        stack_trace: str | None = None,
    ) -> None:
        """Log an error to the database. On failure, queue for retry."""
        entry = {
            "error_message": error_message,
            "error_code": error_code,
            "context": context,
            "severity": severity,
            "agent_id": agent_id,
            "request_id": request_id,
            "user_id": user_id,
            "stack_trace": stack_trace,
        }
        await self._persist(entry)

    async def log_warning(
        self, message: str, context: dict | None = None, **kwargs: Any
    ) -> None:
        """Convenience: log with severity='warning'."""
        await self.log_error(
            error_message=message,
            error_code=kwargs.pop("error_code", "WARNING"),
            context=context,
            severity="warning",
            **kwargs,
        )

    async def log_info(
        self, message: str, context: dict | None = None, **kwargs: Any
    ) -> None:
        """Convenience: log with severity='info'."""
        await self.log_error(
            error_message=message,
            error_code=kwargs.pop("error_code", "INFO"),
            context=context,
            severity="info",
            **kwargs,
        )

    async def flush_queue(self) -> int:
        """Retry queued error logs. Returns count of successfully flushed."""
        if not self._retry_queue:
            return 0

        flushed = 0
        remaining: list[dict[str, Any]] = []

        for item in self._retry_queue:
            entry = item["entry"]
            attempts = item["attempts"]

            if attempts >= self._max_retries:
                logger.warning(
                    "Discarding error log after %d failed attempts: %s",
                    attempts,
                    entry.get("error_message", "")[:120],
                )
                continue

            success = await self._try_persist(entry)
            if success:
                flushed += 1
            else:
                remaining.append({"entry": entry, "attempts": attempts + 1})

        self._retry_queue = remaining
        if flushed:
            logger.info("Flushed %d queued error log(s) to database.", flushed)
        return flushed

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _persist(self, entry: dict[str, Any]) -> None:
        """Attempt to write an entry to the DB; queue on failure."""
        success = await self._try_persist(entry)
        if not success:
            self._retry_queue.append({"entry": entry, "attempts": 1})
            logger.warning(
                "Failed to persist error log; queued for retry (%d in queue). "
                "Message: %s",
                len(self._retry_queue),
                entry.get("error_message", "")[:120],
            )

    async def _try_persist(self, entry: dict[str, Any]) -> bool:
        """Write a single entry to the database.

        Returns ``True`` on success, ``False`` on any database error.
        """
        try:
            async with AsyncSessionLocal() as session:
                record = ErrorLog(**entry)
                session.add(record)
                await session.commit()
            return True
        except Exception:
            logger.debug(
                "DB write failed for error log: %s",
                traceback.format_exc(),
            )
            return False


# Module-level singleton --------------------------------------------------
error_handler = ErrorHandlerAgent()
