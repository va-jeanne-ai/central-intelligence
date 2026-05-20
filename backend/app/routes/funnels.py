"""Funnel webhook endpoint.

  POST /api/v1/funnels — receive and log funnel conversion events

Sprint 3b / M03-3
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser, get_current_user
from app.database import get_session
from app.repositories.marketing import FunnelEventRepository, FunnelStatsRepository
from app.schemas.funnels import (
    FunnelDataResponse,
    FunnelStageStats,
    FunnelWebhookRequest,
    FunnelWebhookResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/funnels", tags=["funnels"])


@router.post("", response_model=FunnelWebhookResponse)
async def receive_funnel_event(
    body: FunnelWebhookRequest,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> FunnelWebhookResponse:
    """Receive and persist a funnel conversion event.

    Accepts webhook payloads from funnel tools (e.g. ClickFunnels, Kartra).
    Persists the event to the ``funnel_events`` table via FunnelEventRepository
    and returns an acknowledgement.
    """
    processed_at = datetime.now(timezone.utc).isoformat()

    logger.info(
        "Funnel event received — funnel_id=%s event_type=%s stage=%s",
        body.funnel_id,
        body.event_type,
        body.stage,
    )

    repo = FunnelEventRepository(session)
    await repo.create(
        funnel_id=body.funnel_id,
        event_type=body.event_type,
        stage=body.stage,
        metadata_json=json.dumps(body.metadata),
    )

    return FunnelWebhookResponse(
        received=True,
        funnel_id=body.funnel_id,
        event_type=body.event_type,
        stage=body.stage,
        processed_at=processed_at,
    )


@router.get("", response_model=FunnelDataResponse)
async def get_funnel_data(
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> FunnelDataResponse:
    """Return aggregated funnel stats across all tracked funnels.

    Queries the funnel_stats table via FunnelStatsRepository and returns
    the latest stats for every funnel stage.
    """
    logger.info("get_funnel_data called — user=%s", current_user.id)

    repo = FunnelStatsRepository(session)
    stats = await repo.find_all_latest()
    stages = [
        FunnelStageStats(
            funnel_id=s.funnel_id,
            stage=s.stage,
            event_count=s.event_count,
            conversion_rate=s.conversion_rate,
            updated_at=s.updated_at.isoformat(),
        )
        for s in stats
    ]

    return FunnelDataResponse(
        stages=stages,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )
