"""Audit event writer.

Single helper that builds an ``AuditLog`` row and adds it to the caller's
session. The caller owns the transaction — if their UPDATE/INSERT rolls
back, the audit row goes with it (correct: a failed write should not
leave behind a phantom "we did this" entry).

Action strings use a dotted namespace, e.g. ``lead.status_changed``.
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog

logger = logging.getLogger(__name__)


async def record_event(
    session: AsyncSession,
    *,
    user_id: uuid.UUID | None,
    action: str,
    table_name: str,
    record_id: str,
    before: dict | None = None,
    after: dict | None = None,
) -> None:
    """Stage an AuditLog row in the session. Does not commit.

    ``audit_log.user_id`` carries a FK to ``users.id``. Supabase auth
    users aren't auto-synced into the local ``users`` table — a JWT
    ``sub`` we haven't seen before would FK-violate the INSERT and
    take the whole request transaction down with it. Drop the
    attribution to NULL when the user isn't in the table; the audit
    row still lands.
    """
    safe_user_id: uuid.UUID | None = user_id
    if safe_user_id is not None:
        exists = (await session.execute(
            text("SELECT 1 FROM users WHERE id = :id"),
            {"id": str(safe_user_id)},
        )).scalar_one_or_none()
        if exists is None:
            logger.info(
                "record_event: user %s not in users table; storing NULL",
                safe_user_id,
            )
            safe_user_id = None

    entry = AuditLog(
        id=uuid.uuid4(),
        user_id=safe_user_id,
        action=action,
        table_name=table_name,
        record_id=record_id,
        before_value=before,
        after_value=after,
    )
    session.add(entry)
