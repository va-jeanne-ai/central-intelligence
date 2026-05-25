"""One-shot embedding backfills for already-in-DB sources.

Three Celery tasks:

  * ``backfill_email_messages_embeddings``
  * ``backfill_lead_notes_embeddings``
  * ``backfill_insights_embeddings``

Each one SELECTs the source rows that aren't already in ``embeddings``
(or whose ``content_hash`` differs), computes the hash, and INSERTs an
``embed_pending`` row. The embed worker drains them on the next tick.

These tasks are idempotent — re-running after a partial drain just
adds the still-missing rows. None of them are on the beat schedule;
they're meant to be invoked manually (or once during deploy):

    >>> from app.tasks.embed_backfill import backfill_email_messages_embeddings
    >>> backfill_email_messages_embeddings.delay()
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from typing import Any

from sqlalchemy import text

from app.tasks.celery_app import celery_app
from app.tasks.db import make_sync_session

logger = logging.getLogger(__name__)


_BATCH_SIZE = 500  # how many source rows to enqueue per task run


def _hash(text_in: str | None) -> str:
    return hashlib.sha256(
        (text_in or "").encode("utf-8", errors="replace"),
    ).hexdigest()[:64]


def _enqueue_missing(
    session,
    *,
    source_table: str,
    rows: list[tuple[str, str]],
) -> int:
    """Given (source_id, text) tuples, enqueue any not already embedded.

    "Not already embedded" = no row in ``embeddings`` with this
    (source_table, source_id) at the same content_hash. Returns the
    number of rows enqueued.
    """
    if not rows:
        return 0

    # Snapshot existing (source_id → content_hash) for these IDs in one query.
    source_ids = [r[0] for r in rows]
    existing = session.execute(
        text("""
            SELECT DISTINCT source_id, content_hash
            FROM embeddings
            WHERE source_table = :st
              AND source_id = ANY(:ids)
        """),
        {"st": source_table, "ids": source_ids},
    ).fetchall()
    existing_hashes: dict[str, set[str]] = {}
    for sid, h in existing:
        existing_hashes.setdefault(sid, set()).add(h)

    # Skip rows already in the queue too — re-running while the worker
    # is draining shouldn't double-enqueue the same source row.
    pending = session.execute(
        text("""
            SELECT DISTINCT source_id, content_hash
            FROM embed_pending
            WHERE source_table = :st
              AND source_id = ANY(:ids)
        """),
        {"st": source_table, "ids": source_ids},
    ).fetchall()
    for sid, h in pending:
        existing_hashes.setdefault(sid, set()).add(h)

    enqueued = 0
    for source_id, body in rows:
        if not body or not body.strip():
            continue
        h = _hash(body)
        if h in existing_hashes.get(source_id, set()):
            continue
        session.add_all([])  # explicit no-op; keeps the linter happy
        session.execute(
            text("""
                INSERT INTO embed_pending
                    (id, source_table, source_id, text_to_embed, content_hash)
                VALUES
                    (:id, :st, :sid, :body, :h)
            """),
            {
                "id": str(uuid.uuid4()),
                "st": source_table,
                "sid": source_id,
                "body": body,
                "h": h,
            },
        )
        enqueued += 1
    return enqueued


@celery_app.task(
    bind=True, name="app.tasks.embed_backfill.backfill_email_messages_embeddings",
)
def backfill_email_messages_embeddings(self, batch_size: int = _BATCH_SIZE) -> dict[str, Any]:
    """Enqueue every ``email_messages`` row missing an embedding.

    Picks rows in oldest-first order so the chat's "what did X say"
    queries see the longest tail of context first. Body text + subject
    are concatenated for the embed payload — short subjects on their
    own rarely surface useful matches.
    """
    with make_sync_session() as session:
        rows = session.execute(
            text("""
                SELECT id::text AS id,
                       coalesce(subject, '') || E'\\n\\n' || coalesce(body_text, '') AS body
                FROM email_messages
                WHERE body_text IS NOT NULL AND length(body_text) > 0
                ORDER BY sent_at ASC NULLS LAST
                LIMIT :n
            """),
            {"n": batch_size},
        ).fetchall()
        enqueued = _enqueue_missing(
            session,
            source_table="email_messages",
            rows=[(r[0], r[1]) for r in rows],
        )
        session.commit()
    logger.info(
        "backfill_email_messages_embeddings: enqueued=%d (of %d candidates)",
        enqueued, len(rows),
    )
    return {"enqueued": enqueued, "candidates": len(rows)}


@celery_app.task(
    bind=True, name="app.tasks.embed_backfill.backfill_lead_notes_embeddings",
)
def backfill_lead_notes_embeddings(self, batch_size: int = _BATCH_SIZE) -> dict[str, Any]:
    """Enqueue every ``lead_notes`` row missing an embedding."""
    with make_sync_session() as session:
        rows = session.execute(
            text("""
                SELECT id::text AS id, body
                FROM lead_notes
                WHERE body IS NOT NULL AND length(body) > 0
                ORDER BY created_at ASC
                LIMIT :n
            """),
            {"n": batch_size},
        ).fetchall()
        enqueued = _enqueue_missing(
            session,
            source_table="lead_notes",
            rows=[(r[0], r[1]) for r in rows],
        )
        session.commit()
    logger.info(
        "backfill_lead_notes_embeddings: enqueued=%d (of %d candidates)",
        enqueued, len(rows),
    )
    return {"enqueued": enqueued, "candidates": len(rows)}


@celery_app.task(
    bind=True, name="app.tasks.embed_backfill.backfill_insights_embeddings",
)
def backfill_insights_embeddings(self, batch_size: int = _BATCH_SIZE) -> dict[str, Any]:
    """Enqueue every ``insights`` row missing an embedding.

    Concatenates the high-signal narrative columns into one payload
    (raw quote + what they say + real problem + emotional driver +
    marketing translation). Saves the worker from needing to know
    which column matters for which signal type.
    """
    with make_sync_session() as session:
        rows = session.execute(
            text("""
                SELECT id,
                       concat_ws(E'\\n\\n',
                           coalesce(raw_quote, ''),
                           coalesce(what_they_say, ''),
                           coalesce(the_real_problem, ''),
                           coalesce(emotional_driver, ''),
                           coalesce(marketing_translation, '')
                       ) AS body
                FROM insights
                WHERE (
                    coalesce(raw_quote, '') <> '' OR
                    coalesce(what_they_say, '') <> '' OR
                    coalesce(the_real_problem, '') <> ''
                )
                ORDER BY created_at ASC
                LIMIT :n
            """),
            {"n": batch_size},
        ).fetchall()
        enqueued = _enqueue_missing(
            session,
            source_table="insights",
            rows=[(r[0], r[1]) for r in rows],
        )
        session.commit()
    logger.info(
        "backfill_insights_embeddings: enqueued=%d (of %d candidates)",
        enqueued, len(rows),
    )
    return {"enqueued": enqueued, "candidates": len(rows)}
