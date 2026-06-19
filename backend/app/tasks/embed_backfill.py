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


@celery_app.task(
    bind=True, name="app.tasks.embed_backfill.reembed_drive_files",
)
def reembed_drive_files(self) -> dict[str, Any]:
    """Force a full re-embed of every Drive file with extracted text.

    Use after changing the embedding-payload shape (e.g. when we added
    the filename + folder header to each chunk). Steps:

      1. DELETE all existing google_drive_files rows from `embeddings`.
      2. Bump every file's content_hash so the next regular sync sees
         it as "changed" even if the underlying body bytes are identical.
      3. INSERT one embed_pending row per Drive file with extracted text,
         using build_embedding_text() to assemble the new payload.

    Idempotent — re-running after a partial drain just adds the
    still-missing rows. Run manually:

        >>> from app.tasks.embed_backfill import reembed_drive_files
        >>> reembed_drive_files.delay()
    """
    # Lazy import — avoids a circular import at module-load time and
    # keeps the dependency edge explicit ("backfill needs upsert's
    # text-builder").
    from app.services.drive_upsert import build_embedding_text

    # 1. Wipe the existing Drive embeddings in chunks so each DELETE
    #    fits inside Supabase's 2-minute statement timeout. A single
    #    "DELETE FROM embeddings WHERE source_table=..." on a ~5k row
    #    IVFFLAT-indexed table can take longer than 2min because each
    #    row triggers index-page rewrites; batching keeps each statement
    #    short and lets the IVFFLAT index settle between rounds.
    deleted_embeddings = 0
    batch_size = 500
    while True:
        with make_sync_session() as session:
            result = session.execute(
                text("""
                    DELETE FROM embeddings
                    WHERE id IN (
                        SELECT id FROM embeddings
                        WHERE source_table = 'google_drive_files'
                        LIMIT :n
                    )
                """),
                {"n": batch_size},
            )
            row_count = result.rowcount or 0
            session.commit()
        deleted_embeddings += row_count
        logger.info(
            "reembed_drive_files: deleted %d embeddings so far",
            deleted_embeddings,
        )
        if row_count < batch_size:
            break

    # 2. Drain any half-flight pending rows for Drive — we're about
    #    to re-enqueue the whole corpus and don't want collisions
    #    with the older payload format.
    with make_sync_session() as session:
        result = session.execute(
            text("DELETE FROM embed_pending WHERE source_table = 'google_drive_files'")
        )
        cleared_pending = result.rowcount or 0
        session.commit()

    # 3. Pull every Drive file id (lightweight — no body text yet) so we
    #    can iterate them in small batches. Pulling 1265 rows × multi-KB
    #    text in one shot blows Supabase's statement timeout.
    with make_sync_session() as session:
        ids = [
            row["id"] for row in session.execute(
                text("""
                    SELECT id::text AS id
                    FROM google_drive_files
                    WHERE extracted_text IS NOT NULL
                      AND length(extracted_text) > 0
                    ORDER BY id
                """)
            ).mappings().all()
        ]

    # 4. For each batch of IDs, fetch the body + parent + mime, build
    #    the prefixed payload, enqueue. Commit per batch so a stalled
    #    transaction can't time out, and each fetch stays small enough
    #    to round-trip well under Supabase's statement timeout.
    _PAYLOAD_BATCH = 50
    enqueued = 0
    for chunk_start in range(0, len(ids), _PAYLOAD_BATCH):
        batch_ids = ids[chunk_start:chunk_start + _PAYLOAD_BATCH]
        with make_sync_session() as session:
            rows = session.execute(
                text("""
                    SELECT id::text AS id, name, parent_folder_name,
                           mime_type, extracted_text
                    FROM google_drive_files
                    WHERE id::text = ANY(:ids)
                """),
                {"ids": batch_ids},
            ).mappings().all()

            for f in rows:
                payload = build_embedding_text(
                    name=f["name"],
                    parent_folder_name=f["parent_folder_name"],
                    mime_type=f["mime_type"],
                    body=f["extracted_text"],
                )
                new_hash = _hash(payload)
                session.execute(
                    text("""
                        INSERT INTO embed_pending
                            (id, source_table, source_id, text_to_embed, content_hash)
                        VALUES
                            (:id, 'google_drive_files', :sid, :body, :h)
                    """),
                    {
                        "id": str(uuid.uuid4()),
                        "sid": f["id"],
                        "body": payload,
                        "h": new_hash,
                    },
                )
                session.execute(
                    text("UPDATE google_drive_files SET content_hash = :h WHERE id = :id"),
                    {"h": new_hash, "id": f["id"]},
                )
                enqueued += 1
            session.commit()
        logger.info(
            "reembed_drive_files: enqueued %d / %d files",
            enqueued, len(ids),
        )

    # Keep the older variable name for the log line below.
    files = ids

    logger.info(
        "reembed_drive_files: deleted_embeddings=%d cleared_pending=%d "
        "enqueued=%d (of %d files with text)",
        deleted_embeddings, cleared_pending, enqueued, len(files),
    )
    return {
        "deleted_embeddings": deleted_embeddings,
        "cleared_pending": cleared_pending,
        "enqueued": enqueued,
        "files_with_text": len(files),
    }


@celery_app.task(
    bind=True, name="app.tasks.embed_backfill.backfill_wgr_embeddings",
)
def backfill_wgr_embeddings(self, batch_size: int = _BATCH_SIZE) -> dict[str, Any]:
    """Enqueue the WGR-sourced call-intelligence corpus for embedding (Phase 5).

    Covers the highest-value RAG content now living in CI (loaded by the WGR
    backfill): call transcripts + analysis prose (on ``calls``), call-score
    coaching notes, content ideas, and the business profile. Insights have their
    own backfill task (``backfill_insights_embeddings``) — run that too.

    Each source gets a distinct ``source_table`` tag so retrieval can filter by
    kind. Reuses ``_enqueue_missing`` (idempotent — content-hash dedup). The
    embed worker drains ``embed_pending`` on its 2-minute tick.
    """
    enqueued: dict[str, int] = {}
    with make_sync_session() as session:
        # 1. Call transcripts (richest verbatim source) — WGR-enriched onto calls.
        rows = session.execute(
            text("""
                SELECT id, transcript_text
                FROM calls
                WHERE source = 'wgr'
                  AND transcript_text IS NOT NULL AND length(transcript_text) > 0
                ORDER BY date ASC NULLS LAST
            """),
        ).fetchall()
        enqueued["wgr_call_transcript"] = _enqueue_missing(
            session, source_table="wgr_call_transcript",
            rows=[(r[0], r[1]) for r in rows],
        )
        session.commit()

        # 2. Call analysis summary/notes (on calls.summary) + the AI call notes.
        rows = session.execute(
            text("""
                SELECT id,
                       concat_ws(E'\\n\\n', coalesce(summary, ''), coalesce(notes, '')) AS body
                FROM calls
                WHERE source = 'wgr'
                  AND (coalesce(summary,'') <> '' OR coalesce(notes,'') <> '')
                ORDER BY date ASC NULLS LAST
            """),
        ).fetchall()
        enqueued["wgr_call_analysis"] = _enqueue_missing(
            session, source_table="wgr_call_analysis",
            rows=[(r[0], r[1]) for r in rows],
        )
        session.commit()

        # 3. Per-category call-score coaching rationale.
        rows = session.execute(
            text("""
                SELECT score_id, notes
                FROM sales_call_scores
                WHERE notes IS NOT NULL AND length(notes) > 0
                ORDER BY scored_at ASC NULLS LAST
            """),
        ).fetchall()
        enqueued["wgr_call_score"] = _enqueue_missing(
            session, source_table="wgr_call_score",
            rows=[(r[0], r[1]) for r in rows],
        )
        session.commit()

        # 4. Content ideas (ready-to-use hooks/premises/CTAs).
        rows = session.execute(
            text("""
                SELECT id,
                       concat_ws(E'\\n\\n',
                           coalesce(content_premise, ''),
                           coalesce(hook_opening_line, ''),
                           coalesce(teaching_point, ''),
                           coalesce(cta_idea, '')
                       ) AS body
                FROM content_ideas
                WHERE coalesce(content_premise,'') <> '' OR coalesce(hook_opening_line,'') <> ''
                ORDER BY created_at ASC
            """),
        ).fetchall()
        enqueued["wgr_content_idea"] = _enqueue_missing(
            session, source_table="wgr_content_idea",
            rows=[(r[0], r[1]) for r in rows],
        )
        session.commit()

        # 5. Business profile (brand grounding for system prompts).
        rows = session.execute(
            text("""
                SELECT id::text,
                       concat_ws(E'\\n\\n',
                           coalesce(business_name, ''), coalesce(mission, ''),
                           coalesce(target_audience, ''), coalesce(brand_voice, ''),
                           coalesce(core_values, ''), coalesce(key_differentiators, '')
                       ) AS body
                FROM business_profile
                WHERE coalesce(mission,'') <> '' OR coalesce(brand_voice,'') <> ''
            """),
        ).fetchall()
        enqueued["wgr_business_profile"] = _enqueue_missing(
            session, source_table="wgr_business_profile",
            rows=[(r[0], r[1]) for r in rows],
        )
        session.commit()

    total = sum(enqueued.values())
    logger.info("backfill_wgr_embeddings: enqueued=%d %s", total, enqueued)
    return {"enqueued_total": total, "by_source": enqueued}
