"""Pydantic schemas for the /api/v1/freshness endpoint."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class FreshnessSourceResult(BaseModel):
    """Freshness for one scheduled data source."""

    key: str
    label: str
    description: str
    interval_minutes: int
    last_run_at: datetime | None = None
    last_status: str | None = None
    age_minutes: float | None = None
    verdict: str  # "fresh" | "stale" | "unknown"
    detail: str


class FreshnessResponse(BaseModel):
    """GET /api/v1/freshness — per-source freshness + a rolled-up verdict.

    ``overall`` is the worst verdict across sources: "stale" if any source is
    stale, else "unknown" if any has never run, else "fresh". ``checked_at``
    is the server clock the verdicts were computed against, so the UI can show
    "as of HH:MM" rather than guessing.
    """

    overall: str  # "fresh" | "stale" | "unknown"
    checked_at: datetime
    sources: list[FreshnessSourceResult]


class SyncTriggerResponse(BaseModel):
    """POST /api/v1/freshness/wgr/sync — on-demand WGR pull result.

    ``queued`` is False (with an explanatory ``message``) when the sync was
    not enqueued — e.g. client_sync_enabled is off, or the broker was
    unreachable — so the UI can distinguish "kicked off" from "couldn't".
    """

    queued: bool
    task_id: str | None = None
    message: str


class SyncStatusResponse(BaseModel):
    """GET /api/v1/freshness/wgr/sync/{task_id} — poll a WGR sync task.

    ``running`` is the single boolean the UI needs to drive a spinner that
    survives refreshes (the browser persists ``task_id`` and re-polls on
    mount). ``state`` is the raw Celery state for display/debugging.

    Celery reports an unknown OR not-yet-started task as ``PENDING`` and can't
    tell them apart — so after a refresh a stale id would spin forever. The
    route resolves that into ``running`` using elapsed time (see the route),
    so the frontend can treat ``running=false`` as "stop polling".
    """

    task_id: str
    state: str  # raw Celery state: PENDING | STARTED | SUCCESS | FAILURE | RETRY
    running: bool
    # Populated on terminal states: a short human summary (rows synced, or the
    # error). None while still running.
    detail: str | None = None
