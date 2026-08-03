"""Paid ads endpoints.

POST /api/v1/ads           — analyze ad performance and generate ad copy
GET  /api/v1/ads           — retrieve current ads data summary (legacy, ads_stats)
GET  /api/v1/ads/overview  — real Meta Ads mirror data (deliverable 4)

Sprint 4a / M04-5
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser, get_current_user
from app.database import get_session
from app.repositories.marketing import AdsStatsRepository
from app.repositories.shared_intelligence import SharedIntelligenceRepository
from app.schemas.ads import (
    AdsAnalyzeRequest,
    AdsAnalyzeResponse,
    AdsDataResponse,
    AdsOverviewCampaign,
    AdsOverviewKpis,
    AdsOverviewResponse,
    AdsOverviewTopAd,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ads", tags=["ads"])


def _int(value: object) -> int:
    """Return value as int, falling back to 0 for None or non-numeric values."""
    try:
        return int(value) if value is not None else 0
    except (TypeError, ValueError):
        return 0


def _float(value: object) -> float:
    """Return value as float, falling back to 0.0 for None or non-numeric values."""
    try:
        return float(value) if value is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def _iso_date(value: object) -> str | None:
    """Return an ISO date string, or None."""
    if value is None:
        return None
    try:
        return value.isoformat()
    except AttributeError:
        return str(value)


def _parse_date_param(value: str | None, *, param_name: str) -> date | None:
    """Parse a query param as a strict ISO ``YYYY-MM-DD`` date.

    Unlike ``sales_stats._as_date`` (which silently drops bad input so a
    malformed report filter doesn't 500 the whole dashboard), this endpoint's
    date params bind directly to a ``Date`` column via asyncpg — a raw
    non-date string reaching that bind surfaces as an opaque 500 from the
    driver. Fail loudly and early instead: 422 with a clear message.
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


@router.post("", response_model=AdsAnalyzeResponse)
async def analyze_ads(
    body: AdsAnalyzeRequest,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> AdsAnalyzeResponse:
    """Analyze ad performance and generate ad copy.

    Routes through MarketingDirector → AdsSpecialist. The director loop
    queries content ideas, pain points, and offers via its data tools, then
    composes the response with Claude. We aggregate the stream into a single
    string for the `analysis` field to preserve the existing JSON contract.
    """
    # Lazy import to avoid circular imports at module load time.
    from app.agents.directors.marketing import MarketingDirector

    # MarketingDirector.__init__ already registers all specialists
    # (ads_manager, dm_specialist, email_writer, social_media, etc.).
    # Re-registering here used to create duplicate `delegate_to_<id>` tools
    # and would 400 with "Tool names must be unique."
    director = MarketingDirector(session=session)

    logger.info(
        "analyze_ads called — user=%s platform=%s",
        current_user.id,
        body.platform,
    )

    # Keep the data summary call for the response's `data_used` field — it's
    # cheap and the frontend may display it as evidence of grounding.
    shared = SharedIntelligenceRepository(session)
    summary = await shared.get_marketing_summary()

    # Build the user-turn message. The director's system prompt + data tools
    # do the heavy lifting; we just pass through the request's intent.
    period_clause = ""
    if body.date_from and body.date_to:
        period_clause = f" for the period {body.date_from} to {body.date_to}"
    platform_clause = f" focused on the {body.platform} platform" if body.platform else ""
    prompt = (
        f"Analyze our paid ads strategy{platform_clause}{period_clause}. "
        f"Use your data tools to pull context (top pain points, active offers, "
        f"ICP segments). Then produce a short, actionable analysis followed by "
        f"2-3 ad-copy variants tailored to the platform."
    )

    analysis_text = ""
    async for chunk in director.stream_response(prompt):
        analysis_text += chunk

    return AdsAnalyzeResponse(
        analysis=analysis_text,
        ad_copy="",  # Variants live inline in `analysis` (markdown). Filling
                    # this field separately requires structured-output prompting.
        recommendations=[],  # Same — director's analysis already includes recs.
        data_used={
            "content_ideas": summary["content_ideas"],
            "pain_points": summary["pain_points"],
            "offers": {"active_count": summary["offers"]["active_count"]},
        },
    )


@router.get("", response_model=AdsDataResponse)
async def get_ads_data(
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> AdsDataResponse:
    """Return current ads data summary.

    Queries the ads_stats table via AdsStatsRepository and returns
    aggregated totals across all tracked campaigns and platforms.
    """
    logger.info("get_ads_data called — user=%s", current_user.id)

    repo = AdsStatsRepository(session)
    totals = await repo.aggregate_totals()

    return AdsDataResponse(
        campaigns=totals["total_campaigns"],
        avg_roas=totals["avg_roas"],
        total_spend=totals["total_spend"],
        top_ads=[],
        generated_at=datetime.now(timezone.utc).isoformat(),
    )


# ---------------------------------------------------------------------------
# Endpoint: GET /api/v1/ads/overview
# ---------------------------------------------------------------------------
#
# Aggregation choice (verified read-only, 2026-08-03): `meta_ad_performance`
# carries exactly one `snapshot_type` value, "Daily" — spend/impressions vary
# day to day per ad (not a running cumulative total re-stated every row), so
# summing across the (optionally date-scoped) snapshot range is the correct
# way to roll up spend/impressions/leads/booked_calls. Point-in-time quality
# signals (`kpi_status`, `ctr`) are NOT summable — those come from each ad's
# LATEST snapshot in range instead.


@router.get("/overview", response_model=AdsOverviewResponse)
async def get_ads_overview(
    snapshot_from: str | None = Query(
        default=None, description="Filter meta_ad_performance.snapshot_date >= this date (YYYY-MM-DD)"
    ),
    snapshot_to: str | None = Query(
        default=None, description="Filter meta_ad_performance.snapshot_date <= this date (YYYY-MM-DD)"
    ),
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> AdsOverviewResponse:
    """Return real Meta Ads data straight from the WGR mirror tables.

    Rebuilds the Ads page from ``meta_campaigns`` / ``meta_ads`` /
    ``meta_ad_performance`` — no hardcoded platform breakdown, no
    ``ads_stats`` legacy summary. Campaign/ad identity lists are always
    unfiltered; only the performance aggregates are scoped by
    ``snapshot_from``/``snapshot_to`` when given.
    """
    logger.info(
        "get_ads_overview called — user=%s snapshot_from=%s snapshot_to=%s",
        current_user.id,
        snapshot_from,
        snapshot_to,
    )

    # Parse to real `date` objects before anything touches SQL — a malformed
    # string reaching Postgres as a Date bind param surfaces as an opaque
    # 500 from the driver instead of a clear 422 here.
    parsed_from = _parse_date_param(snapshot_from, param_name="snapshot_from")
    parsed_to = _parse_date_param(snapshot_to, param_name="snapshot_to")

    perf_where = "1=1"
    perf_params: dict[str, object] = {}
    if parsed_from is not None:
        perf_where += " AND snapshot_date >= :snapshot_from"
        perf_params["snapshot_from"] = parsed_from
    if parsed_to is not None:
        perf_where += " AND snapshot_date <= :snapshot_to"
        perf_params["snapshot_to"] = parsed_to

    # ---- Per-ad performance rollup (sum across snapshots in range) --------
    # + the latest-in-range snapshot's kpi_status/ctr (point-in-time, not
    # summable). One CTE computes the sums, a second (DISTINCT ON) grabs the
    # latest row per ad; joined together per ad_id.
    perf_rows = (
        await session.execute(
            text(
                f"""
                WITH sums AS (
                    SELECT
                        ad_id,
                        COALESCE(SUM(amount_spent), 0) AS spend,
                        COALESCE(SUM(impressions), 0) AS impressions,
                        COALESCE(SUM(leads), 0) AS leads,
                        COALESCE(SUM(booked_calls), 0) AS booked_calls,
                        COALESCE(SUM(link_clicks), 0) AS link_clicks
                    FROM meta_ad_performance
                    WHERE {perf_where}
                    GROUP BY ad_id
                ),
                latest AS (
                    SELECT DISTINCT ON (ad_id)
                        ad_id, kpi_status, ctr, snapshot_date
                    FROM meta_ad_performance
                    WHERE {perf_where}
                    ORDER BY ad_id, snapshot_date DESC NULLS LAST
                )
                SELECT
                    s.ad_id,
                    s.spend, s.impressions, s.leads, s.booked_calls, s.link_clicks,
                    l.kpi_status, l.ctr
                FROM sums s
                LEFT JOIN latest l ON l.ad_id = s.ad_id
                """  # noqa: S608 — perf_where built from a fixed whitelist above
            ),
            perf_params,
        )
    ).mappings().all()
    perf_by_ad: dict[str, dict] = {r["ad_id"]: dict(r) for r in perf_rows if r["ad_id"]}

    # ---- Ad identity (unfiltered) — for campaign rollups + top ads --------
    ad_rows = (
        await session.execute(
            text(
                """
                SELECT ad_id, campaign_id, name, ad_format, status, hook_text,
                       launched_date, kill_date, kill_reason
                FROM meta_ads
                """
            )
        )
    ).mappings().all()

    # ---- Campaign identity (unfiltered) ------------------------------------
    campaign_rows = (
        await session.execute(
            text(
                """
                SELECT campaign_id, name, status, objective, campaign_type,
                       daily_budget, lifetime_budget, start_date, end_date
                FROM meta_campaigns
                """
            )
        )
    ).mappings().all()
    campaign_name_by_id: dict[str, str | None] = {
        r["campaign_id"]: r["name"] for r in campaign_rows
    }

    # ---- KPIs ----------------------------------------------------------------
    total_spend = sum(_float(p["spend"]) for p in perf_by_ad.values())
    total_impressions = sum(_int(p["impressions"]) for p in perf_by_ad.values())
    total_leads = sum(_int(p["leads"]) for p in perf_by_ad.values())
    total_booked_calls = sum(_int(p["booked_calls"]) for p in perf_by_ad.values())
    total_link_clicks = sum(_int(p["link_clicks"]) for p in perf_by_ad.values())

    avg_cost_per_lead = (total_spend / total_leads) if total_leads > 0 else 0.0
    if total_impressions > 0:
        avg_ctr = (total_link_clicks / total_impressions) * 100
    else:
        ctr_values = [_float(p["ctr"]) for p in perf_by_ad.values() if p["ctr"] is not None]
        avg_ctr = (sum(ctr_values) / len(ctr_values)) if ctr_values else 0.0

    active_campaigns = sum(
        1 for r in campaign_rows if (r["status"] or "").strip().lower() == "active"
    )

    kpis = AdsOverviewKpis(
        total_spend=round(total_spend, 2),
        total_impressions=total_impressions,
        total_leads=total_leads,
        total_booked_calls=total_booked_calls,
        avg_cost_per_lead=round(avg_cost_per_lead, 2),
        avg_ctr=round(avg_ctr, 2),
        active_campaigns=active_campaigns,
        total_campaigns=len(campaign_rows),
        total_ads=len(ad_rows),
    )

    # ---- Campaigns table — aggregate each campaign's ads' performance -----
    campaign_agg: dict[str, dict] = {
        r["campaign_id"]: {"spend": 0.0, "leads": 0, "booked_calls": 0, "ads_count": 0}
        for r in campaign_rows
    }
    for ad in ad_rows:
        cid = ad["campaign_id"]
        if cid not in campaign_agg:
            continue  # orphan ad — campaign_id doesn't resolve to a known campaign
        campaign_agg[cid]["ads_count"] += 1
        perf = perf_by_ad.get(ad["ad_id"])
        if perf:
            campaign_agg[cid]["spend"] += _float(perf["spend"])
            campaign_agg[cid]["leads"] += _int(perf["leads"])
            campaign_agg[cid]["booked_calls"] += _int(perf["booked_calls"])

    campaigns: list[AdsOverviewCampaign] = []
    for r in campaign_rows:
        agg = campaign_agg[r["campaign_id"]]
        spend = agg["spend"]
        leads = agg["leads"]
        cost_per_lead = (spend / leads) if leads > 0 else 0.0
        campaigns.append(
            AdsOverviewCampaign(
                campaign_id=r["campaign_id"],
                name=r["name"],
                status=r["status"],
                objective=r["objective"],
                campaign_type=r["campaign_type"],
                daily_budget=_float(r["daily_budget"]) if r["daily_budget"] is not None else None,
                lifetime_budget=_float(r["lifetime_budget"]) if r["lifetime_budget"] is not None else None,
                start_date=_iso_date(r["start_date"]),
                end_date=_iso_date(r["end_date"]),
                ads_count=agg["ads_count"],
                spend=round(spend, 2),
                leads=leads,
                booked_calls=agg["booked_calls"],
                cost_per_lead=round(cost_per_lead, 2),
            )
        )
    campaigns.sort(key=lambda c: (-c.spend, c.name or ""))

    # ---- Top ads — top 15 by summed spend ----------------------------------
    ad_entries: list[tuple[float, AdsOverviewTopAd]] = []
    for ad in ad_rows:
        perf = perf_by_ad.get(ad["ad_id"])
        if perf is None:
            continue  # no performance rows in range — excluded from "top" ranking
        spend = _float(perf["spend"])
        leads = _int(perf["leads"])
        cost_per_lead = (spend / leads) if leads > 0 else 0.0
        ad_entries.append(
            (
                spend,
                AdsOverviewTopAd(
                    ad_id=ad["ad_id"],
                    name=ad["name"],
                    campaign_name=campaign_name_by_id.get(ad["campaign_id"]),
                    ad_format=ad["ad_format"],
                    status=ad["status"],
                    hook_text=ad["hook_text"],
                    kpi_status=perf["kpi_status"],
                    spend=round(spend, 2),
                    leads=leads,
                    cost_per_lead=round(cost_per_lead, 2),
                    ctr=_float(perf["ctr"]) if perf["ctr"] is not None else None,
                    launched_date=_iso_date(ad["launched_date"]),
                    kill_date=_iso_date(ad["kill_date"]),
                    kill_reason=ad["kill_reason"],
                ),
            )
        )
    ad_entries.sort(key=lambda t: t[0], reverse=True)
    top_ads = [entry for _, entry in ad_entries[:15]]

    return AdsOverviewResponse(kpis=kpis, campaigns=campaigns, top_ads=top_ads)
