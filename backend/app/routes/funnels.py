"""Funnel webhook endpoint + real funnel overview.

  POST /api/v1/funnels           — receive and log funnel conversion events
  GET  /api/v1/funnels            — legacy funnel_stats summary (dead scaffolding)
  GET  /api/v1/funnels/overview   — real lead_journey-derived funnel (deliverable 3)

Sprint 3b / M03-3
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timezone
from types import SimpleNamespace

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser, get_current_user
from app.database import get_session
from app.repositories.funnel_stats import (
    aggregate_by_channel,
    aggregate_overall_stages,
    stage_flags_for_row,
)
from app.repositories.marketing import FunnelEventRepository, FunnelStatsRepository
from app.schemas.funnels import (
    FunnelChannelRow,
    FunnelDataResponse,
    FunnelOverviewResponse,
    FunnelOverviewStage,
    FunnelStageStats,
    FunnelWebhookRequest,
    FunnelWebhookResponse,
)
from app.services.attribution import build_resolver

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/funnels", tags=["funnels"])


def _parse_date_param(value: str | None, *, param_name: str) -> date | None:
    """Parse a query param as a strict ISO ``YYYY-MM-DD`` date.

    Same idiom as ``routes/ads.py._parse_date_param`` — fail loudly (422)
    rather than letting a malformed string reach the ``Date`` bind param and
    surface as an opaque 500 from the driver.
    """
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid {param_name}: {value!r} — expected ISO format YYYY-MM-DD",
        ) from exc


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


# ---------------------------------------------------------------------------
# Endpoint: GET /api/v1/funnels/overview
# ---------------------------------------------------------------------------
#
# Discovery (2026-08): CI's own funnel_events/funnel_stats tables are empty —
# dead scaffolding, left in place above. The REAL synced funnel lives in the
# lead_journey mirror (1 row per lead): stages are derivable per lead via
# stage_flags_for_row (app.repositories.funnel_stats). This endpoint rebuilds
# the funnel from that mirror, optionally scoped by entry_date, and slices it
# by channel using the same resolver machinery leads.py/sales_stats.py use —
# never reimplement bucket rules.


@router.get("/overview", response_model=FunnelOverviewResponse)
async def get_funnels_overview(
    entry_from: str | None = Query(
        default=None, description="Filter lead_journey.entry_date >= this date (YYYY-MM-DD)"
    ),
    entry_to: str | None = Query(
        default=None, description="Filter lead_journey.entry_date <= this date (YYYY-MM-DD)"
    ),
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> FunnelOverviewResponse:
    """Return the real funnel derived from lead_journey, overall + by channel.

    ``entry_from``/``entry_to`` scope ``lead_journey.entry_date`` (validated
    via the ``_parse_date_param`` idiom in ``routes/ads.py`` — fail loudly
    with 422 on a malformed date rather than an opaque 500 from the driver).
    """
    logger.info(
        "get_funnels_overview called — user=%s entry_from=%s entry_to=%s",
        current_user.id,
        entry_from,
        entry_to,
    )

    parsed_from = _parse_date_param(entry_from, param_name="entry_from")
    parsed_to = _parse_date_param(entry_to, param_name="entry_to")

    where_sql = "1=1"
    params: dict[str, object] = {}
    if parsed_from is not None:
        where_sql += " AND entry_date >= :entry_from"
        params["entry_from"] = parsed_from
    if parsed_to is not None:
        where_sql += " AND entry_date <= :entry_to"
        params["entry_to"] = parsed_to

    # NOTE: lead_journey carries 5 UTM/channel fields, not 6 — there is no
    # utm_content_last column upstream (verified against the live schema).
    # channel_for_lead/bucket_channel_combos take a 6-tuple signature; we pass
    # utm_content_last=NULL explicitly below rather than inventing a column,
    # which is exactly the resolver's documented wildcard/null semantics.
    rows = (
        await session.execute(
            text(
                f"""
                SELECT
                    webinar_registered_at, watched_live, watched_replay,
                    appt_count, discovery_held, sale_id,
                    utm_source_first, utm_medium_first, utm_content_first,
                    utm_source_last, utm_medium_last
                FROM lead_journey
                WHERE {where_sql}
                """  # noqa: S608 — where_sql built from a fixed whitelist above
            ),
            params,
        )
    ).mappings().all()

    # aggregate_overall_stages / stage_flags_for_row read attributes
    # (getattr), matching their SimpleNamespace-fake test contract — a raw
    # SQLAlchemy RowMapping is dict-like, not attribute-accessible, so wrap
    # each row before handing it to the pure helpers.
    journey_rows = [SimpleNamespace(**dict(r)) for r in rows]

    overall_stages = aggregate_overall_stages(journey_rows)
    overall = [FunnelOverviewStage(**s) for s in overall_stages]

    # ---- Channel slice — load taxonomy once per request (same idiom as
    # compute_lead_stats / routes/leads.py), group rows by their 6-tuple, and
    # let aggregate_by_channel resolve buckets via bucket_channel_combos.
    taxonomy_rows = (await session.execute(text("SELECT * FROM attribution_taxonomy"))).fetchall()
    resolver = build_resolver(taxonomy_rows)

    combo_groups: dict[tuple, list] = {}
    for r in journey_rows:
        # utm_content_last is explicitly None — lead_journey has no such
        # column upstream (see the query comment above).
        key = (
            r.utm_source_first, r.utm_medium_first, r.utm_content_first,
            r.utm_source_last, r.utm_medium_last, None,
        )
        combo_groups.setdefault(key, []).append(stage_flags_for_row(r))

    combos = [
        (sf, mf, cf, sl, ml, cl, flags_list)
        for (sf, mf, cf, sl, ml, cl), flags_list in combo_groups.items()
    ]
    by_channel_rows = aggregate_by_channel(combos, resolver)
    by_channel = [FunnelChannelRow(**row) for row in by_channel_rows]

    return FunnelOverviewResponse(
        overall=overall,
        by_channel=by_channel,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )
