"""
Market Signals aggregation Celery task — OPS-MS1.

Recomputes the ``market_signals`` reporting table from the ``insights`` table.
This is the aggregation job the handover (§3.6) describes: market_signals is
"populated by queries against the insights table, not by direct insertion...
updated by an aggregation job."

Why recompute (not increment): ``total_mentions`` is all-time, but ``last_30_days``
and ``last_7_days`` are ROLLING windows — they must decay as time passes, which a
+1-per-call increment can't do. So each run recomputes counts from scratch and
upserts on the (signal_family, signal) natural key.

Preserves curated fields: ``best_marketing_angle`` and ``notes`` are human-set
and NOT derivable from insights, so the ON CONFLICT update leaves them untouched.

Uses a synchronous SQLAlchemy session (Celery runs outside the async loop).
"""

import logging
from datetime import datetime, timezone
from uuid import uuid4

from celery.exceptions import MaxRetriesExceededError
from sqlalchemy import text

from app.tasks.celery_app import celery_app
from app.tasks.db import make_sync_session

logger = logging.getLogger(__name__)


# Single-statement recompute + upsert.
#   - counts grouped by (signal_family, signal) with rolling windows via FILTER
#   - representative quote/call = the most recent non-null raw_quote (DISTINCT ON)
#   - insight_type = the most-frequent type per signal (mode via a window pick)
#   - ON CONFLICT updates ONLY computed columns; best_marketing_angle/notes survive
_RECOMPUTE_SQL = text(
    """
    WITH agg AS (
        SELECT
            signal_family,
            signal,
            COUNT(*)                                                              AS total_mentions,
            COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '30 days')      AS last_30_days,
            COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '7 days')       AS last_7_days
        FROM insights
        WHERE signal_family IS NOT NULL AND signal IS NOT NULL
        GROUP BY signal_family, signal
    ),
    -- Most-frequent insight_type per signal (ties broken arbitrarily but deterministically).
    type_pick AS (
        SELECT DISTINCT ON (signal_family, signal)
            signal_family, signal, insight_type
        FROM (
            SELECT signal_family, signal, insight_type, COUNT(*) AS c
            FROM insights
            WHERE signal_family IS NOT NULL AND signal IS NOT NULL AND insight_type IS NOT NULL
            GROUP BY signal_family, signal, insight_type
        ) t
        ORDER BY signal_family, signal, c DESC, insight_type ASC
    ),
    -- Newest insight carrying a raw_quote per signal → representative example.
    quote_pick AS (
        SELECT DISTINCT ON (signal_family, signal)
            signal_family, signal, raw_quote AS example_quote, call_id AS example_call_id
        FROM insights
        WHERE signal_family IS NOT NULL AND signal IS NOT NULL AND raw_quote IS NOT NULL
        ORDER BY signal_family, signal, created_at DESC
    )
    INSERT INTO market_signals
        (signal_family, signal, insight_type, total_mentions, last_30_days, last_7_days,
         example_quote, example_call_id, updated_at)
    SELECT
        a.signal_family, a.signal, tp.insight_type,
        a.total_mentions, a.last_30_days, a.last_7_days,
        qp.example_quote, qp.example_call_id, NOW()
    FROM agg a
    LEFT JOIN type_pick tp  ON tp.signal_family = a.signal_family AND tp.signal = a.signal
    LEFT JOIN quote_pick qp ON qp.signal_family = a.signal_family AND qp.signal = a.signal
    ON CONFLICT (signal_family, signal) DO UPDATE SET
        insight_type    = EXCLUDED.insight_type,
        total_mentions  = EXCLUDED.total_mentions,
        last_30_days    = EXCLUDED.last_30_days,
        last_7_days     = EXCLUDED.last_7_days,
        example_quote   = EXCLUDED.example_quote,
        example_call_id = EXCLUDED.example_call_id,
        updated_at      = EXCLUDED.updated_at
    RETURNING 1
    """
)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=300)
def update_market_signals(self) -> dict:
    """Recompute market_signals from insights and upsert on (signal_family, signal).

    Idempotent: counts are recomputed from scratch each run, not incremented.
    No-ops cleanly when there are no qualifying insights (does not wipe the table).
    Preserves human-curated ``best_marketing_angle`` / ``notes`` on existing rows.

    Returns a summary dict with the number of signal rows upserted.
    """
    task_id = self.request.id or uuid4().hex
    logger.info("update_market_signals started — task_id=%s", task_id)

    try:
        db = make_sync_session()
        try:
            result = db.execute(_RECOMPUTE_SQL)
            upserted = len(result.fetchall())
            db.commit()
        finally:
            db.close()

        logger.info(
            "update_market_signals: upserted %d signal(s) — task_id=%s", upserted, task_id
        )
        return {
            "task_id": task_id,
            "status": "completed",
            "signals_upserted": upserted,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as exc:
        logger.exception("update_market_signals failed — task_id=%s error=%s", task_id, exc)
        try:
            raise self.retry(exc=exc)
        except MaxRetriesExceededError:
            logger.error("Max retries exceeded for update_market_signals task_id=%s", task_id)
            raise
