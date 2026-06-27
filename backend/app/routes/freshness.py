"""Data-freshness endpoint.

GET /api/v1/freshness

Answers "is the data up to date?" on demand — the backend behind the
"Check data freshness" button on the Integrations page. Reads each scheduled
source's last-run timestamp (from integrations.last_synced_at, the latest
sync_log row, or MAX(updated_at) on a results table) and classifies it against
that source's expected cadence. See app/services/freshness.py for the catalog.

Read-only and side-effect-free: it inspects recorded sync state, it does NOT
trigger any sync. That keeps it cheap to click repeatedly and safe to call
even when the worker/beat are stopped (which is exactly when a user wants to
know how stale things are).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser, get_current_user
from app.config import settings
from app.database import get_session
from app.schemas.freshness import (
    FreshnessResponse,
    FreshnessSourceResult,
    SyncStatusResponse,
    SyncTriggerResponse,
)
from app.services.freshness import compute_freshness

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/freshness", tags=["freshness"])


def _roll_up(verdicts: list[str]) -> str:
    """Worst-wins: stale beats unknown beats fresh. Empty → unknown."""
    if "stale" in verdicts:
        return "stale"
    if "unknown" in verdicts or not verdicts:
        return "unknown"
    return "fresh"


@router.get("", response_model=FreshnessResponse)
async def get_freshness(
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),  # noqa: ARG001 — auth gate
):
    """Compute and return per-source data freshness."""
    now = datetime.now(tz=timezone.utc)
    results = await compute_freshness(session, now)

    sources = [
        FreshnessSourceResult(
            key=r.key,
            label=r.label,
            description=r.description,
            interval_minutes=r.interval_minutes,
            last_run_at=r.last_run_at,
            last_status=r.last_status,
            age_minutes=r.age_minutes,
            verdict=r.verdict,
            detail=r.detail,
        )
        for r in results
    ]

    return FreshnessResponse(
        overall=_roll_up([s.verdict for s in sources]),
        checked_at=now,
        sources=sources,
    )


@router.post("/wgr/sync", response_model=SyncTriggerResponse)
async def trigger_wgr_sync(
    current_user: CurrentUser = Depends(get_current_user),  # noqa: ARG001 — auth gate
):
    """Enqueue an on-demand incremental WGR pull.

    Mirrors the hourly ``wgr-sync-hourly`` beat job — ``since=None`` means
    "pull rows changed since the stored watermark" (idempotent upsert; the
    first run ever is a full backfill). This is what the "Sync WGR now" button
    on the Integrations page calls when the WGR data looks stale.

    The task itself no-ops when ``client_sync_enabled`` is off, but we check it
    here too so the UI gets an honest "not enabled" message instead of a queued
    task id that silently does nothing.
    """
    if not settings.client_sync_enabled:
        return SyncTriggerResponse(
            queued=False,
            message=(
                "WGR sync is not enabled on this environment "
                "(client_sync_enabled is off)."
            ),
        )

    # Lazy import so the route module doesn't pull the Celery task graph at
    # app import time (matches offer-generate / transcribe).
    from app.tasks.wgr_sync import sync_wgr

    try:
        task = sync_wgr.delay()  # since=None → incremental from watermark
    except Exception as exc:  # noqa: BLE001 — broker down shouldn't 500 the UI
        logger.warning("trigger_wgr_sync: failed to enqueue — %s", exc)
        return SyncTriggerResponse(
            queued=False,
            message=f"Couldn't queue the sync — the task broker may be down: {exc}",
        )

    logger.info("trigger_wgr_sync: enqueued task_id=%s", task.id)
    return SyncTriggerResponse(
        queued=True,
        task_id=task.id,
        message=(
            f"WGR sync queued (task {task.id[:8]}…). "
            "This can take a minute — the indicator clears when it's done."
        ),
    )


# Celery reports both "unknown task" and "queued, not yet picked up" as
# PENDING and can't distinguish them. After a browser refresh, a task id that
# already finished (and whose result expired from the backend) also reads
# PENDING. Without a guard the spinner would never stop. So: if a task is still
# PENDING this long after the client queued it, we treat it as no-longer-running
# (the worker would have moved it to STARTED well within this window). The
# client supplies ``queued_seconds_ago`` from the timestamp it persisted next to
# the task id — no extra server-side bookkeeping needed.
PENDING_GIVEUP_SECONDS = 90


@router.get("/wgr/sync/{task_id}", response_model=SyncStatusResponse)
async def get_wgr_sync_status(
    task_id: str,
    queued_seconds_ago: float | None = None,
    current_user: CurrentUser = Depends(get_current_user),  # noqa: ARG001 — auth gate
):
    """Poll a WGR sync task's state. Drives the refresh-proof running indicator.

    ``running`` is the boolean the UI acts on: keep the spinner + keep polling
    while True, stop when False. ``queued_seconds_ago`` lets us resolve the
    ambiguous PENDING state (see ``PENDING_GIVEUP_SECONDS``).
    """
    from celery.result import AsyncResult

    from app.tasks.celery_app import celery_app

    async_result = AsyncResult(task_id, app=celery_app)
    state = async_result.status  # PENDING | STARTED | SUCCESS | FAILURE | RETRY

    running = state in ("PENDING", "STARTED", "RETRY")
    detail: str | None = None

    if state == "PENDING" and (
        queued_seconds_ago is not None and queued_seconds_ago > PENDING_GIVEUP_SECONDS
    ):
        # Stale/expired id — stop the spinner rather than hang forever.
        running = False
        detail = "Sync status is no longer tracked (it likely finished). Re-check freshness."
    elif state == "SUCCESS":
        result = async_result.result
        if isinstance(result, dict):
            total = result.get("total")
            if result.get("status") == "skipped":
                detail = "Sync skipped — WGR sync is not enabled."
            elif total is not None:
                detail = f"Done — {total} row(s) synced. Re-check freshness."
            else:
                detail = "Done. Re-check freshness."
        else:
            detail = "Done. Re-check freshness."
    elif state == "FAILURE":
        detail = f"Sync failed: {str(async_result.result)[:300]}"

    return SyncStatusResponse(
        task_id=task_id, state=state, running=running, detail=detail
    )


# Re-export for app/main.py
__all__ = ["router"]
