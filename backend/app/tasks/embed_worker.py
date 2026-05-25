"""Embed queue drainer — beats every 2 minutes.

Each tick:

  1. Fetch / reset the ``embedding_budget`` row. If today's window is
     stale (>24h old), roll it over to a fresh window with
     ``tokens_used_today = 0``. If we're at cap, log and return.

  2. ``SELECT`` up to ``settings.embed_worker_batch_size`` pending
     rows from ``embed_pending`` oldest-first.

  3. For each row, chunk the text, call Voyage with ``input_type=document``,
     INSERT (or UPDATE on conflict) one ``embeddings`` row per chunk,
     delete the ``embed_pending`` row, and bump the budget by the
     reported token usage.

  4. On any per-row failure, bump ``attempts``, write ``last_error``,
     and leave the row in place for the next tick. After 3 attempts we
     stop retrying that row (it stays in the table for manual review).
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import delete, select, text

from app.config import settings
from app.models.operational import EmbedPending, Embedding, EmbeddingBudget
from app.services import voyage_client
from app.services.chunker import chunk_text
from app.tasks.celery_app import celery_app
from app.tasks.db import make_sync_session

logger = logging.getLogger(__name__)


_MAX_ATTEMPTS = 3
_WINDOW_HOURS = 24


def _get_or_reset_budget(session) -> EmbeddingBudget | None:
    """Return the (possibly reset) budget row, or None if at cap."""
    budget = session.execute(
        select(EmbeddingBudget).where(EmbeddingBudget.id == 1)
    ).scalar_one_or_none()
    if budget is None:
        # Migration seeds row id=1; if it's missing something is wrong.
        # Seed it on the fly so the worker doesn't hard-fail in dev.
        budget = EmbeddingBudget(
            id=1,
            daily_token_cap=50_000_000,
            tokens_used_today=0,
            usage_window_started_at=datetime.now(timezone.utc),
        )
        session.add(budget)
        session.flush()

    now = datetime.now(timezone.utc)
    window_age = now - (budget.usage_window_started_at or now)
    if window_age > timedelta(hours=_WINDOW_HOURS):
        logger.info("embed_worker: rolling over daily window")
        budget.tokens_used_today = 0
        budget.usage_window_started_at = now
        session.add(budget)
        session.flush()

    if budget.tokens_used_today >= budget.daily_token_cap:
        logger.warning(
            "embed_worker: budget exceeded — used %d / cap %d; skipping tick",
            budget.tokens_used_today, budget.daily_token_cap,
        )
        return None

    return budget


def _embed_one_row(session, row: EmbedPending, budget: EmbeddingBudget) -> bool:
    """Embed the chunks for a single pending row. Returns True on success."""
    chunks = chunk_text(
        row.text_to_embed or "",
        max_tokens=settings.embed_worker_max_tokens_per_chunk,
    )
    if not chunks:
        # Nothing embeddable — delete the queue row, don't try again.
        session.execute(
            delete(EmbedPending).where(EmbedPending.id == row.id)
        )
        return True

    vectors, tokens_used = voyage_client.embed_batch(
        chunks, input_type="document",
    )

    # First clear out any older embeddings for this (source_table, source_id)
    # — the content changed, so they're stale.
    session.execute(
        delete(Embedding).where(
            Embedding.source_table == row.source_table,
            Embedding.source_id == row.source_id,
        )
    )

    now = datetime.now(timezone.utc)
    for idx, (chunk, vector) in enumerate(zip(chunks, vectors)):
        session.add(Embedding(
            id=uuid.uuid4(),
            source_table=row.source_table,
            source_id=row.source_id,
            chunk_index=idx,
            text_chunk=chunk,
            embedding=vector,
            content_hash=row.content_hash,
            embedded_at=now,
        ))

    # Pop the queue row + bump the budget — same transaction so partial
    # progress doesn't double-charge tokens.
    session.execute(delete(EmbedPending).where(EmbedPending.id == row.id))
    budget.tokens_used_today = (budget.tokens_used_today or 0) + tokens_used
    session.add(budget)
    return True


@celery_app.task(bind=True, name="app.tasks.embed_worker.drain_embed_queue")
def drain_embed_queue(self) -> dict[str, Any]:
    """One tick of the embed queue. Returns a small status dict."""
    if not settings.voyage_api_key:
        logger.info("embed_worker: VOYAGE_API_KEY not set; skipping tick")
        return {"status": "skipped", "reason": "no_voyage_key"}

    processed = 0
    failed = 0
    skipped_at_cap = False

    with make_sync_session() as session:
        budget = _get_or_reset_budget(session)
        if budget is None:
            session.commit()
            return {"status": "skipped", "reason": "budget_exceeded"}

        rows = session.execute(
            select(EmbedPending)
            .where(EmbedPending.attempts < _MAX_ATTEMPTS)
            .order_by(EmbedPending.created_at.asc())
            .limit(settings.embed_worker_batch_size)
        ).scalars().all()

        for row in rows:
            try:
                _embed_one_row(session, row, budget)
                processed += 1
                # Commit per row so a later failure doesn't roll back
                # earlier successful embeds + token-budget bumps.
                session.commit()
                # Re-fetch budget after the commit — it may have changed.
                budget = _get_or_reset_budget(session)
                if budget is None:
                    skipped_at_cap = True
                    break
            except Exception as exc:  # noqa: BLE001
                session.rollback()
                logger.exception(
                    "embed_worker: row failed source=%s id=%s",
                    row.source_table, row.source_id,
                )
                # Stamp the row in a separate mini-transaction.
                session.execute(
                    text("""
                        UPDATE embed_pending
                        SET attempts = attempts + 1,
                            last_error = :err
                        WHERE id = :id
                    """),
                    {"err": str(exc)[:1000], "id": row.id},
                )
                session.commit()
                failed += 1

    logger.info(
        "embed_worker: processed=%d failed=%d skipped_at_cap=%s",
        processed, failed, skipped_at_cap,
    )
    return {
        "status": "ok" if not failed else "partial",
        "processed": processed,
        "failed": failed,
        "skipped_at_cap": skipped_at_cap,
    }
