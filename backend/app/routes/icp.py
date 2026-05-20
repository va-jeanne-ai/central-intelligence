"""
ICP (Ideal Customer Profile) routes.

  POST /api/v1/icp/generate   — enqueue the ICP Generator Celery task
  GET  /api/v1/icp            — return all active ICP segments
  GET  /api/v1/icp/primary    — return the current primary ICP segment

Sprint 2 / VIR-24 / OPS-I1
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Optional

from celery.result import AsyncResult
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser, get_current_user
from app.database import get_session
from app.repositories.operational import ICPRepository
from app.tasks.icp import generate_icp

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/icp", tags=["icp"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class ICPGenerateRequest(BaseModel):
    """Optional parameters for triggering an ICP generation run."""

    date_range_days: int = 90


class ICPGenerateResponse(BaseModel):
    """Response from POST /api/v1/icp/generate."""

    task_id: str
    status: str
    message: str


class ICPSegmentResponse(BaseModel):
    """Single ICP segment in API responses."""

    id: str
    segment: Optional[str] = None
    description: Optional[str] = None
    demographics: Optional[str] = None
    psychographics: Optional[str] = None
    pain_summary: Optional[str] = None
    goal_summary: Optional[str] = None
    buying_triggers: Optional[str] = None
    common_objections: Optional[str] = None
    is_primary: bool
    status: str
    created_at: str

    model_config = {"from_attributes": True}


class ICPListResponse(BaseModel):
    """Response from GET /api/v1/icp."""

    segments: list[ICPSegmentResponse]
    total: int


class ICPUpdateRequest(BaseModel):
    """Partial update payload for PUT /api/v1/icp/:id."""

    segment: Optional[str] = None
    description: Optional[str] = None
    demographics: Optional[str] = None
    psychographics: Optional[str] = None
    pain_summary: Optional[str] = None
    goal_summary: Optional[str] = None
    buying_triggers: Optional[str] = None
    common_objections: Optional[str] = None
    is_primary: Optional[bool] = None
    status: Optional[str] = None


class TaskStatusResponse(BaseModel):
    """Status of an enqueued ICP generation task."""

    task_id: str
    status: str
    result: Optional[Any] = None


# ---------------------------------------------------------------------------
# POST /api/v1/icp/generate
# ---------------------------------------------------------------------------


@router.post("/generate", response_model=ICPGenerateResponse)
async def trigger_icp_generation(
    body: ICPGenerateRequest = ICPGenerateRequest(),
    current_user: CurrentUser = Depends(get_current_user),
) -> ICPGenerateResponse:
    """Enqueue the ICP Generator Celery task.

    The task aggregates shared intelligence pool data (pain points, wins,
    objections, goals, insights), calls Claude to synthesise ICP segments,
    and persists the results to the ``icp`` table.

    Poll ``GET /api/v1/icp/generate/{task_id}/status`` to check completion.
    """
    task = generate_icp.delay(date_range_days=body.date_range_days)
    logger.info("ICP generation task enqueued — task_id=%s", task.id)
    return ICPGenerateResponse(
        task_id=task.id,
        status="queued",
        message=f"ICP generation task enqueued with date_range_days={body.date_range_days}.",
    )


@router.get("/generate/{task_id}/status", response_model=TaskStatusResponse)
async def icp_task_status(
    task_id: str,
    current_user: CurrentUser = Depends(get_current_user),
) -> TaskStatusResponse:
    """Poll the status of an ICP generation Celery task."""
    result = AsyncResult(task_id)
    return TaskStatusResponse(
        task_id=task_id,
        status=result.status,
        result=result.result if result.ready() else None,
    )


# ---------------------------------------------------------------------------
# GET /api/v1/icp
# ---------------------------------------------------------------------------


@router.get("", response_model=ICPListResponse)
async def list_icp_segments(
    db: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> ICPListResponse:
    """Return all active ICP segments, primary first."""
    repo = ICPRepository(db)
    segments = await repo.list_all(status="active")
    return ICPListResponse(
        segments=[
            ICPSegmentResponse(
                id=str(seg.id),
                segment=seg.segment,
                description=seg.description,
                demographics=seg.demographics,
                psychographics=seg.psychographics,
                pain_summary=seg.pain_summary,
                goal_summary=seg.goal_summary,
                buying_triggers=seg.buying_triggers,
                common_objections=seg.common_objections,
                is_primary=seg.is_primary,
                status=seg.status,
                created_at=seg.created_at.isoformat(),
            )
            for seg in segments
        ],
        total=len(segments),
    )


# ---------------------------------------------------------------------------
# GET /api/v1/icp/primary
# ---------------------------------------------------------------------------


@router.put("/{icp_id}", response_model=ICPSegmentResponse)
async def update_icp_segment(
    icp_id: str,
    body: ICPUpdateRequest,
    db: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> ICPSegmentResponse:
    """Update an ICP segment by ID.

    Only non-None fields in the request body are applied. Setting
    ``is_primary=True`` automatically demotes all other segments via the
    repository's single-primary invariant.
    """
    try:
        segment_uuid = uuid.UUID(icp_id)
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid ICP segment ID: {icp_id!r}",
        )

    repo = ICPRepository(db)
    updates = {k: v for k, v in body.model_dump().items() if v is not None}

    if not updates:
        raise HTTPException(
            status_code=422,
            detail="No update fields provided.",
        )

    # Use create_or_update_segment when is_primary is toggled (preserves invariant)
    if "is_primary" in updates and updates["is_primary"]:
        existing = await repo.get(segment_uuid)
        if existing is None:
            raise HTTPException(status_code=404, detail="ICP segment not found.")
        updated = await repo.create_or_update_segment(
            segment=updates.get("segment", existing.segment),
            description=updates.get("description", existing.description),
            demographics=updates.get("demographics", existing.demographics),
            psychographics=updates.get("psychographics", existing.psychographics),
            pain_summary=updates.get("pain_summary", existing.pain_summary),
            goal_summary=updates.get("goal_summary", existing.goal_summary),
            buying_triggers=updates.get("buying_triggers", existing.buying_triggers),
            common_objections=updates.get("common_objections", existing.common_objections),
            is_primary=updates.get("is_primary", existing.is_primary),
            status=updates.get("status", existing.status),
        )
    else:
        updated = await repo.update(segment_uuid, **updates)

    if updated is None:
        raise HTTPException(status_code=404, detail="ICP segment not found.")

    return ICPSegmentResponse(
        id=str(updated.id),
        segment=updated.segment,
        description=updated.description,
        demographics=updated.demographics,
        psychographics=updated.psychographics,
        pain_summary=updated.pain_summary,
        goal_summary=updated.goal_summary,
        buying_triggers=updated.buying_triggers,
        common_objections=updated.common_objections,
        is_primary=updated.is_primary,
        status=updated.status,
        created_at=updated.created_at.isoformat(),
    )


# ---------------------------------------------------------------------------
# GET /api/v1/icp/primary
# ---------------------------------------------------------------------------


@router.get("/primary", response_model=ICPSegmentResponse)
async def get_primary_icp(
    db: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> ICPSegmentResponse:
    """Return the current primary ICP segment."""
    repo = ICPRepository(db)
    primary = await repo.get_primary()
    if primary is None:
        raise HTTPException(
            status_code=404,
            detail="No primary ICP segment found. Run POST /api/v1/icp/generate first.",
        )
    return ICPSegmentResponse(
        id=str(primary.id),
        segment=primary.segment,
        description=primary.description,
        demographics=primary.demographics,
        psychographics=primary.psychographics,
        pain_summary=primary.pain_summary,
        goal_summary=primary.goal_summary,
        buying_triggers=primary.buying_triggers,
        common_objections=primary.common_objections,
        is_primary=primary.is_primary,
        status=primary.status,
        created_at=primary.created_at.isoformat(),
    )
