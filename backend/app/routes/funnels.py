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

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser, get_current_user
from app.database import get_session
from app.repositories.funnel_stats import (
    aggregate_by_channel,
    aggregate_overall_stages,
    combo_stage_counts,
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
# lead_journey mirror. This endpoint rebuilds the funnel from that mirror,
# optionally scoped by entry_date, and slices it by channel using the same
# resolver machinery leads.py/sales_stats.py use — never reimplement bucket
# rules.
#
# Perf fix (2026-08-04): originally did `SELECT *` over all 12,820 rows
# (41 cols) and aggregated in Python — 68.4s over the Supabase transaction
# pooler, past the frontend's 30s abort, so the page rendered empty in
# production. Now ONE SQL statement does the whole aggregation: GROUP BY the
# 5 UTM/channel fields with the six stage counts as COUNT/COUNT-FILTER
# aggregates. This is a genuinely single grouped read — no per-row Python
# loop over lead_journey, no second full-table pass — 172 combo rows in
# ~3.3s. Verified unchanged stage totals: 12,820 / 11,557 / 6,872 / 1,289 /
# 183 / 83.


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

    # ONE grouped SQL read does the entire aggregation — GROUP BY the 5
    # UTM/channel fields (lead_journey has no utm_content_last column
    # upstream, verified against the live schema) with the six stage counts
    # as COUNT/COUNT-FILTER aggregates. 172 distinct combos vs 12,820 raw
    # rows: this is what took the query from 68.4s (SELECT * + Python loop)
    # to ~3.3s.
    combo_rows = (
        await session.execute(
            text(
                f"""
                SELECT
                    utm_source_first, utm_medium_first, utm_content_first,
                    utm_source_last, utm_medium_last,
                    COUNT(*) AS leads,
                    COUNT(webinar_registered_at) AS registered,
                    COUNT(*) FILTER (WHERE watched_live OR watched_replay) AS watched,
                    COUNT(*) FILTER (WHERE appt_count > 0) AS booked_appt,
                    COUNT(*) FILTER (WHERE discovery_held) AS discovery_held,
                    COUNT(sale_id) AS closed
                FROM lead_journey
                WHERE {where_sql}
                GROUP BY 1, 2, 3, 4, 5
                """  # noqa: S608 — where_sql built from a fixed whitelist above
            ),
            params,
        )
    ).mappings().all()

    overall_stages = aggregate_overall_stages(combo_rows)
    overall = [FunnelOverviewStage(**s) for s in overall_stages]

    # ---- Channel slice — load taxonomy once per request (same idiom as
    # compute_lead_stats / routes/leads.py), then resolve each already-
    # aggregated combo row via bucket_channel_combos. No second DB read and
    # no per-lead-row Python loop: the combo rows above already carry every
    # stage count this needs.
    taxonomy_rows = (await session.execute(text("SELECT * FROM attribution_taxonomy"))).fetchall()
    resolver = build_resolver(taxonomy_rows)

    combos = [
        (
            r["utm_source_first"], r["utm_medium_first"], r["utm_content_first"],
            r["utm_source_last"], r["utm_medium_last"],
            # utm_content_last is explicitly None — lead_journey has no such
            # column upstream (see the query comment above).
            None,
            combo_stage_counts(r),
        )
        for r in combo_rows
    ]
    by_channel_rows = aggregate_by_channel(combos, resolver)
    by_channel = [FunnelChannelRow(**row) for row in by_channel_rows]

    return FunnelOverviewResponse(
        overall=overall,
        by_channel=by_channel,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )
