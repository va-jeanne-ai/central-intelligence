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
import random
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import delete, select, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.config import settings
from app.models.operational import EmbedPending, Embedding, EmbeddingBudget
from app.services import voyage_client
from app.services.chunker import chunk_text
from app.tasks.celery_app import celery_app
from app.tasks.db import make_sync_session


@dataclass
class _PendingSnapshot:
    """Plain-data snapshot of an EmbedPending row.

    Captured under the lock-and-claim SELECT so the rest of the work
    never touches the ORM instance — that way an autoflush rollback
    can't trigger an ObjectDeletedError when we read the row's fields
    later for error logging.
    """

    id: uuid.UUID
    source_table: str
    source_id: str
    content_hash: str
    text_to_embed: str

logger = logging.getLogger(__name__)


_MAX_ATTEMPTS = 3
_WINDOW_HOURS = 24

# Voyage's documented cap is 320k tokens per request; we use 200k for
# safety margin against tokenizer drift (our tiktoken count is close
# but not identical to Voyage's tokenizer). Hard input-count cap is
# also 128 per call.
_VOYAGE_MAX_TOKENS_PER_CALL = 200_000
_VOYAGE_MAX_INPUTS_PER_CALL = 128

# Cheap-and-fast token estimator — Voyage doesn't expose their
# tokenizer, but tiktoken cl100k is what the chunker uses and tracks
# Voyage's count within ~10-15%. Good enough for batch sizing.
_TOKEN_ESTIMATOR_ENCODING = "cl100k_base"


def _is_transient_db_error(exc: OperationalError) -> bool:
    """True for retryable Postgres errors (deadlock, serialization fail).

    psycopg2 wraps these in dedicated exception classes; we also string-
    match as a fallback in case the driver layer flattens them.
    """
    cause = getattr(exc, "orig", None)
    cause_cls = type(cause).__name__ if cause is not None else ""
    if cause_cls in {"DeadlockDetected", "SerializationFailure"}:
        return True
    msg = str(exc).lower()
    return "deadlock detected" in msg or "could not serialize access" in msg


def _split_into_voyage_batches(chunks: list[str]) -> list[list[str]]:
    """Group chunks into sub-batches that fit Voyage's per-call limits."""
    import tiktoken
    enc = tiktoken.get_encoding(_TOKEN_ESTIMATOR_ENCODING)

    batches: list[list[str]] = []
    current: list[str] = []
    current_tokens = 0
    for chunk in chunks:
        n = len(enc.encode(chunk))
        # If a single chunk somehow exceeds the per-call cap, send it
        # alone — Voyage may still reject it, but the embed_worker's
        # error path will surface the issue without poisoning siblings.
        if n > _VOYAGE_MAX_TOKENS_PER_CALL:
            if current:
                batches.append(current)
                current = []
                current_tokens = 0
            batches.append([chunk])
            continue
        # Flush the current batch if appending would exceed either limit.
        would_exceed_tokens = current_tokens + n > _VOYAGE_MAX_TOKENS_PER_CALL
        would_exceed_count = len(current) + 1 > _VOYAGE_MAX_INPUTS_PER_CALL
        if current and (would_exceed_tokens or would_exceed_count):
            batches.append(current)
            current = []
            current_tokens = 0
        current.append(chunk)
        current_tokens += n
    if current:
        batches.append(current)
    return batches


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


def _split_header_and_body(text: str) -> tuple[str, str]:
    """Pull the filename-context header off the top of an embed payload.

    The Drive ingest pipeline (see ``services/drive_upsert.build_embedding_text``)
    prepends two layers of context to every Drive file:

      1. ``[Key: value]`` bracket lines (File / Folder / Type).
      2. ``Document: <title>`` + ``This document is titled "<title>".``
         natural-prose lines.

    Both need to live on every chunk, not just chunk-0, or filename
    queries only retrieve the first chunk of a file. We split the
    combined header off here so the caller can re-attach it to each
    chunk after the body is chunked.
    """
    if not text:
        return "", ""
    lines = text.splitlines()
    n = len(lines)

    # Phase 1: walk the bracket block.
    i = 0
    bracket_end = 0
    while i < n:
        s = lines[i].strip()
        if not s:
            bracket_end = i + 1
            i += 1
            break
        if not (s.startswith("[") and s.endswith("]") and ":" in s):
            # First non-bracket line — no bracket header present.
            bracket_end = 0
            break
        i += 1
    else:
        # Pure-bracket-header input (no separator + body).
        return text, ""

    # Phase 2: skip natural-prose title sentences immediately after.
    title_end = bracket_end
    while title_end < n:
        s = lines[title_end].strip()
        if s.startswith("Document: ") or s.startswith(
            'This document is titled "'
        ):
            title_end += 1
            continue
        if not s:
            title_end += 1
            break
        break

    header_lines_end = title_end
    # Trim the trailing blank line that separates header from body so
    # we don't include it in the header text itself.
    if header_lines_end > 0 and not lines[header_lines_end - 1].strip():
        header = "\n".join(lines[:header_lines_end - 1]).strip()
    else:
        header = "\n".join(lines[:header_lines_end]).strip()
    body = "\n".join(lines[header_lines_end:]).strip()
    return header, body


def _embed_one_row(
    session, snap: _PendingSnapshot, budget: EmbeddingBudget,
) -> bool:
    """Embed the chunks for a single pending row. Returns True on success."""
    # Pull the [File: …] header off the top so we can re-attach it to
    # every chunk. Without this, the chunker would put the header only
    # on chunk-0 — chunks 1..N would lose the filename context, so
    # filename-keyword queries only retrieve the first chunk of a file.
    header, body = _split_header_and_body(snap.text_to_embed or "")
    chunks = chunk_text(
        body or snap.text_to_embed or "",
        max_tokens=settings.embed_worker_max_tokens_per_chunk,
    )
    if header and chunks:
        chunks = [f"{header}\n\n{c}" for c in chunks]
    if not chunks:
        # Nothing embeddable — delete the queue row, don't try again.
        session.execute(
            delete(EmbedPending).where(EmbedPending.id == snap.id)
        )
        return True

    # Voyage caps each request at ~320k tokens total. A 600-page PDF
    # can produce 500+ chunks at our 1024-token chunk size; sending
    # them as a single call hits the cap and 400s. Sub-batch by total
    # token count so each Voyage call stays well under the limit.
    # We use 200k as our internal cap (safety margin), and at most 128
    # inputs per call (Voyage's hard input-count cap).
    sub_batches = _split_into_voyage_batches(chunks)

    vectors: list[list[float]] = []
    tokens_used = 0
    for sub in sub_batches:
        v, t = voyage_client.embed_batch(sub, input_type="document")
        vectors.extend(v)
        tokens_used += t

    # First clear out any older embeddings for this (source_table, source_id)
    # — the content changed, so they're stale.
    session.execute(
        delete(Embedding).where(
            Embedding.source_table == snap.source_table,
            Embedding.source_id == snap.source_id,
        )
    )

    now = datetime.now(timezone.utc)
    # INSERT ... ON CONFLICT DO NOTHING as a last-line safety net.
    # The SELECT FOR UPDATE SKIP LOCKED above already prevents concurrent
    # workers from picking the same row, but a stale embed_pending row
    # that was already drained (e.g. via a manual re-queue) could still
    # collide with the unique constraint without this guard.
    rows_to_insert = [
        {
            "id": uuid.uuid4(),
            "source_table": snap.source_table,
            "source_id": snap.source_id,
            "chunk_index": idx,
            "text_chunk": chunk,
            "embedding": vector,
            "content_hash": snap.content_hash,
            "embedded_at": now,
        }
        for idx, (chunk, vector) in enumerate(zip(chunks, vectors))
    ]
    if rows_to_insert:
        stmt = pg_insert(Embedding.__table__).values(rows_to_insert)
        stmt = stmt.on_conflict_do_nothing(
            index_elements=["source_table", "source_id", "chunk_index"],
        )
        session.execute(stmt)

    # Pop the queue row + bump the budget — same transaction so partial
    # progress doesn't double-charge tokens.
    session.execute(delete(EmbedPending).where(EmbedPending.id == snap.id))
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

        # SELECT ... FOR UPDATE SKIP LOCKED prevents two concurrent
        # workers from picking up the same row. Each worker grabs a
        # distinct slice of the queue and the locks release on commit.
        # Snapshot the payload into plain dicts so subsequent error
        # logging never has to re-load attributes from a detached or
        # deleted ORM instance.
        locked_rows = session.execute(
            text("""
                SELECT id, source_table, source_id, content_hash, text_to_embed
                FROM embed_pending
                WHERE attempts < :max_attempts
                ORDER BY created_at ASC
                LIMIT :n
                FOR UPDATE SKIP LOCKED
            """),
            {"max_attempts": _MAX_ATTEMPTS, "n": settings.embed_worker_batch_size},
        ).mappings().all()

        # De-dup defensively in case the same source_id appears twice
        # in the queue (would collide on the unique constraint after
        # one of the embeds finishes). Keep the oldest row per
        # source_id; drop the rest in this tick.
        seen_source_ids: set[tuple[str, str]] = set()
        snapshots: list[_PendingSnapshot] = []
        for r in locked_rows:
            key = (r["source_table"], r["source_id"])
            if key in seen_source_ids:
                continue
            seen_source_ids.add(key)
            snapshots.append(_PendingSnapshot(
                id=r["id"],
                source_table=r["source_table"],
                source_id=r["source_id"],
                content_hash=r["content_hash"],
                text_to_embed=r["text_to_embed"] or "",
            ))

        rate_limit_hit = False
        deadlock_skipped = 0
        for snap in snapshots:
            try:
                _embed_one_row(session, snap, budget)
                processed += 1
                # Commit per row so a later failure doesn't roll back
                # earlier successful embeds + token-budget bumps. This
                # also releases the row's FOR UPDATE lock.
                session.commit()
                # Re-fetch budget after the commit — it may have changed.
                budget = _get_or_reset_budget(session)
                if budget is None:
                    skipped_at_cap = True
                    break
            except voyage_client.VoyageRateLimited as exc:
                # Rate limit exhausted backoff — bail out of this tick.
                # Leave the row in place WITHOUT bumping attempts so a
                # transient rate-limit storm doesn't three-strike valid
                # rows out of the queue. The next tick (2 min from now)
                # will pick them up after the API has had time to cool.
                session.rollback()
                logger.warning(
                    "embed_worker: rate limited — stopping tick early "
                    "(processed=%d, remaining %d untouched). %s",
                    processed, len(snapshots) - processed - failed, exc,
                )
                rate_limit_hit = True
                break
            except OperationalError as exc:
                # Postgres transient errors (deadlock, serialization
                # failure, connection blip). These aren't row problems
                # — concurrent workers fighting over the IVFFLAT index
                # is the usual cause. Don't bump attempts; let the next
                # tick (or the same tick after a brief sleep) retry.
                session.rollback()
                if _is_transient_db_error(exc):
                    sleep = 0.1 + random.random() * 0.4
                    logger.warning(
                        "embed_worker: transient DB error on source=%s id=%s — "
                        "retrying without bumping attempts (sleep %.2fs)",
                        snap.source_table, snap.source_id, sleep,
                    )
                    time.sleep(sleep)
                    deadlock_skipped += 1
                    continue
                # Genuine OperationalError (not deadlock) — treat as fail.
                logger.exception(
                    "embed_worker: row failed (db error) source=%s id=%s",
                    snap.source_table, snap.source_id,
                )
                session.execute(
                    text("""
                        UPDATE embed_pending
                        SET attempts = attempts + 1,
                            last_error = :err
                        WHERE id = :id
                    """),
                    {"err": str(exc)[:1000], "id": snap.id},
                )
                session.commit()
                failed += 1
            except Exception as exc:  # noqa: BLE001
                session.rollback()
                logger.exception(
                    "embed_worker: row failed source=%s id=%s",
                    snap.source_table, snap.source_id,
                )
                # Stamp the row in a separate mini-transaction.
                session.execute(
                    text("""
                        UPDATE embed_pending
                        SET attempts = attempts + 1,
                            last_error = :err
                        WHERE id = :id
                    """),
                    {"err": str(exc)[:1000], "id": snap.id},
                )
                session.commit()
                failed += 1

    logger.info(
        "embed_worker: processed=%d failed=%d deadlock_skipped=%d "
        "skipped_at_cap=%s rate_limited=%s",
        processed, failed, deadlock_skipped, skipped_at_cap, rate_limit_hit,
    )
    return {
        "status": "ok" if not (failed or rate_limit_hit) else "partial",
        "processed": processed,
        "failed": failed,
        "deadlock_skipped": deadlock_skipped,
        "skipped_at_cap": skipped_at_cap,
        "rate_limited": rate_limit_hit,
    }
