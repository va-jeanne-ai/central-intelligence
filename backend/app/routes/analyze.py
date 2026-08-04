"""Analyze the current filtered view.

POST /api/v1/analyze/{surface} — accepts the SAME filter query params as the
surface's list endpoint (pagination/sort params are ignored), re-runs the
filtered query via the surface's registered aggregator, and returns an LLM
narrative grounded exclusively in the computed aggregates.

POST /api/v1/analyze/{surface}/chat — same filter query params PLUS a JSON
body of the running message history; recomputes fresh aggregates from the
CURRENT filters and answers the follow-up grounded in them.

Ephemeral by design: nothing is persisted; one real LLM call per invocation
(row_count == 0 short-circuits without calling the LLM). Auth comes from the
global AuthMiddleware like every other /api/v1 route.
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.view_analysis import get_surface
from app.analytics.view_analysis.narrative import chat_view_analysis, synthesize_view_analysis
from app.database import get_session
from app.schemas.analyze import AnalyzeChatRequest, AnalyzeChatResponse, AnalyzeViewResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["analyze"])


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@router.post(
    "/analyze/{surface_key}",
    response_model=AnalyzeViewResponse,
    summary="Grounded LLM analysis of the current filtered list view",
)
async def analyze_view(
    surface_key: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> AnalyzeViewResponse:
    surface = get_surface(surface_key)
    if surface is None:
        raise HTTPException(status_code=404, detail=f"Unknown surface: {surface_key!r}")

    filters = surface.parse_filters(request.query_params)
    aggregates = await surface.aggregate(session, filters)
    echo = surface.echo(filters)

    if aggregates["row_count"] == 0:
        return AnalyzeViewResponse(
            surface=surface.key, label=surface.label, filters_echo=echo,
            row_count=0, empty=True, stats=aggregates,
            narrative="", highlights=[], hypotheses=[],
            generated_at=_now_iso(), model=None,
        )

    parsed = await synthesize_view_analysis(
        label=surface.label, describe=surface.describe,
        filters_echo=echo, aggregates=aggregates,
    )
    return AnalyzeViewResponse(
        surface=surface.key, label=surface.label, filters_echo=echo,
        row_count=aggregates["row_count"], empty=False, stats=aggregates,
        narrative=parsed["narrative"], highlights=parsed["highlights"],
        hypotheses=parsed["hypotheses"],
        generated_at=_now_iso(), model=parsed["model"],
    )


@router.post(
    "/analyze/{surface_key}/chat",
    response_model=AnalyzeChatResponse,
    summary="Follow-up chat about the current filtered view, grounded in fresh aggregates",
)
async def analyze_view_chat(
    surface_key: str,
    body: AnalyzeChatRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> AnalyzeChatResponse:
    surface = get_surface(surface_key)
    if surface is None:
        raise HTTPException(status_code=404, detail=f"Unknown surface: {surface_key!r}")

    if not body.messages:
        raise HTTPException(status_code=400, detail="messages must not be empty.")

    # Recompute aggregates from the CURRENT filters — same code path as
    # analyze_view — so the chat is always grounded in fresh data, not a
    # stale snapshot from the initial analysis call.
    filters = surface.parse_filters(request.query_params)
    aggregates = await surface.aggregate(session, filters)
    echo = surface.echo(filters)

    messages = [{"role": m.role, "content": m.content} for m in body.messages]
    result = await chat_view_analysis(
        label=surface.label, filters_echo=echo, aggregates=aggregates, messages=messages,
    )
    return AnalyzeChatResponse(
        reply=result["reply"], model=result["model"], generated_at=_now_iso(),
    )
