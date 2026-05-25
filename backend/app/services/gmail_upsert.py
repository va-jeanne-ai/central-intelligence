"""Upsert helper for Gmail messages → email_threads + email_messages.

Called once per message yielded by ``gmail_client.fetch_messages_for_email``.
Finds or creates the parent ``email_threads`` row keyed on
``(lead_id, provider_thread_id)``, then INSERT-IGNOREs the message keyed
on the globally-unique ``provider_message_id``. Whenever a new message
lands, bumps ``email_threads.last_message_at`` (if newer) and
``email_threads.message_count`` so the lead-detail GET stays cheap.

Sync session only — the caller is a Celery task using
``make_sync_session``. No commits inside; caller owns the transaction.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.operational import EmailMessage, EmailThread

logger = logging.getLogger(__name__)


def upsert_thread_and_message_sync(
    session: Session,
    lead_id: uuid.UUID,
    msg: dict[str, Any],
) -> bool:
    """Upsert one Gmail message into our DB. Returns True iff inserted.

    Idempotent — re-running on the same message is a no-op. The caller
    counts True returns to populate the SyncLog ``inserted`` metric.
    """
    provider_thread_id: str | None = msg.get("provider_thread_id")
    provider_message_id: str | None = msg.get("provider_message_id")
    if not provider_thread_id or not provider_message_id:
        # Gmail's API should always populate both, but defend against
        # surprises rather than poison the sync.
        logger.warning(
            "gmail_upsert: missing thread/message id (thread=%s, msg=%s)",
            provider_thread_id, provider_message_id,
        )
        return False

    sent_at: datetime | None = msg.get("sent_at")

    # 1. Find or create the thread.
    thread = session.execute(
        select(EmailThread).where(
            EmailThread.lead_id == lead_id,
            EmailThread.provider_thread_id == provider_thread_id,
        )
    ).scalar_one_or_none()

    if thread is None:
        thread = EmailThread(
            id=uuid.uuid4(),
            lead_id=lead_id,
            provider_thread_id=provider_thread_id,
            subject=msg.get("subject"),
            last_message_at=sent_at,
            message_count=0,
        )
        session.add(thread)
        session.flush()  # populate thread.id for the message FK

    # 2. INSERT-IGNORE the message by provider_message_id.
    existing = session.execute(
        select(EmailMessage.id).where(
            EmailMessage.provider_message_id == provider_message_id,
        )
    ).scalar_one_or_none()
    if existing is not None:
        return False

    session.add(EmailMessage(
        id=uuid.uuid4(),
        thread_id=thread.id,
        provider_message_id=provider_message_id,
        from_address=msg.get("from_address"),
        to_addresses=msg.get("to_addresses") or [],
        cc_addresses=msg.get("cc_addresses") or [],
        subject=msg.get("subject"),
        body_text=msg.get("body_text"),
        sent_at=sent_at,
        has_attachments=bool(msg.get("has_attachments")),
        attachments_meta=msg.get("attachments_meta") or [],
    ))

    # 3. Bump thread denormalised columns.
    thread.message_count = (thread.message_count or 0) + 1
    if sent_at is not None and (
        thread.last_message_at is None or sent_at > thread.last_message_at
    ):
        thread.last_message_at = sent_at
        # If the latest message has a different subject, prefer it.
        # Reply threads carry "Re: …" prefixes; this gives the most
        # recent visible subject without too much fuss.
        if msg.get("subject"):
            thread.subject = msg.get("subject")

    return True
