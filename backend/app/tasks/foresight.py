"""Celery task: compute Foresight P1 recommendation cards nightly.

Runs the four cohort-count queries (app.repositories.foresight_stats),
assembles cards (app.services.foresight), and overwrites the
foresight_recommendations table in one transaction (delete+insert — OUR
table, not a WGR mirror, small enough that snapshot-reconcile machinery
buys nothing). See docs/superpowers/plans/
2026-08-06-foresight-layer-prototype.md "P1 architecture (as built)".

Uses ``asyncio.run`` + ``AsyncSessionLocal`` (same bridge pattern as
``app.tasks.wgr_sync.sync_wgr``) because the repository layer is async but
Celery tasks run outside FastAPI's event loop.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from uuid import uuid4

from celery.exceptions import MaxRetriesExceededError
from sqlalchemy import delete, insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.intelligence import ForesightRecommendation
from app.repositories.foresight_stats import (
    fetch_channel_close,
    fetch_discovery_families,
    fetch_email_value,
    fetch_live_vs_replay,
)
from app.services.foresight import (
    CANDIDATES,
    build_card,
    discovery_hold_reason,
    mean_interval,
    wilson_interval,
)
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


async def _compute_cards(session: AsyncSession) -> list[dict]:
    """Run all four cohort queries and assemble every card. Pure orchestration
    — no prose generation here, that lives in app.services.foresight."""
    cards: list[dict] = []

    # 1. live_vs_replay
    lvr = await fetch_live_vs_replay(session)
    baseline = wilson_interval(lvr["replay_only"]["booked"], lvr["replay_only"]["n"])
    variant = wilson_interval(lvr["watched_live"]["booked"], lvr["watched_live"]["n"])
    cards.append(build_card(CANDIDATES["live_watch"], baseline, variant))

    # 2. channel_close — ig_dm and meta_paid vs the all-lead baseline
    channels = await fetch_channel_close(session)
    all_leads = channels.get("__all_leads__", {"n": 0, "closed": 0})
    all_leads_iv = wilson_interval(all_leads["closed"], all_leads["n"])

    ig_dm = channels.get("ig_dm", {"n": 0, "closed": 0})
    ig_dm_iv = wilson_interval(ig_dm["closed"], ig_dm["n"])
    cards.append(build_card(CANDIDATES["ig_dm_channel"], all_leads_iv, ig_dm_iv))

    meta_paid = channels.get("meta_paid", {"n": 0, "closed": 0})
    meta_paid_iv = wilson_interval(meta_paid["closed"], meta_paid["n"])
    cards.append(build_card(CANDIDATES["meta_paid_close"], all_leads_iv, meta_paid_iv))

    # 3. email_value
    email = await fetch_email_value(session)
    other_iv = mean_interval(
        mean=email["other"]["mean"], sd=email["other"]["sd"], n=email["other"]["n"]
    )
    value_iv = mean_interval(
        mean=email["value_education"]["mean"],
        sd=email["value_education"]["sd"],
        n=email["value_education"]["n"],
    )
    cards.append(build_card(CANDIDATES["email_value"], other_iv, value_iv))

    # 4. discovery_families — expected ALL GATED; render the top-rate family
    # (by rate) as the held example, per the plan.
    discovery = await fetch_discovery_families(session)
    disc_baseline_iv = wilson_interval(
        discovery["baseline"]["closed"], discovery["baseline"]["n"]
    )
    families = discovery["families"]
    if families:
        family_intervals = [
            (f["signal_family"], wilson_interval(f["closed"], f["n"])) for f in families
        ]
        top_family, top_iv = max(family_intervals, key=lambda pair: pair[1].rate)
    else:
        top_family, top_iv = "—", wilson_interval(0, 0)

    def _hold_reason() -> str:
        return discovery_hold_reason(
            n=discovery["baseline"]["n"],
            baseline=disc_baseline_iv,
            top_family=top_family,
            top=top_iv,
        )

    cards.append(
        build_card(
            CANDIDATES["discovery_families"],
            disc_baseline_iv,
            top_iv,
            hold_reason_fn=_hold_reason,
        )
    )

    return cards


async def _run() -> dict:
    started = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as session:
        cards = await _compute_cards(session)

        now = datetime.now(timezone.utc)
        rows = [
            {
                "id": card["id"],
                "status": card["status"],
                "confidence": card["confidence"],
                "title": card["title"],
                "department": card["department"],
                "hindsight_headline": card["hindsight_headline"],
                "hindsight_detail": card["hindsight_detail"],
                "evidence_href": card["evidence_href"],
                "evidence_label": card["evidence_label"],
                "insight_text": card["insight_text"],
                "action_text": card["action_text"],
                "lift_text": card["lift_text"],
                "hold_reason": card["hold_reason"],
                "baseline_label": card["baseline_label"],
                "baseline_rate": card["baseline_rate"],
                "baseline_low": card["baseline_low"],
                "baseline_high": card["baseline_high"],
                "variant_label": card["variant_label"],
                "variant_rate": card["variant_rate"],
                "variant_low": card["variant_low"],
                "variant_high": card["variant_high"],
                "n_label": card["n_label"],
                "computed_at": now,
            }
            for card in cards
        ]

        # Full overwrite in one transaction — OUR table, small (5 rows).
        # AsyncSessionLocal's session already autobegins a transaction on
        # first use, so this commits it rather than opening a nested one.
        await session.execute(delete(ForesightRecommendation))
        if rows:
            await session.execute(insert(ForesightRecommendation), rows)
        await session.commit()

        elapsed = (datetime.now(timezone.utc) - started).total_seconds()
        return {
            "cards_computed": len(cards),
            "published": sum(1 for c in cards if c["status"].startswith("published")),
            "gated": sum(1 for c in cards if c["status"] == "gated"),
            "computed_at": now.isoformat(),
            "elapsed_seconds": round(elapsed, 2),
        }


@celery_app.task(bind=True, max_retries=3, default_retry_delay=300)
def compute_foresight_recommendations(self) -> dict:
    """Scheduled Celery task — recompute all Foresight P1 cards from the
    live mirrors and overwrite foresight_recommendations.

    Idempotent (full overwrite each run). Pure aggregate reads — expected
    well under 60s (see the plan's pooler-timeout rule: no row shipping).
    """
    task_id = self.request.id or uuid4().hex
    logger.info("compute_foresight_recommendations started — task_id=%s", task_id)

    try:
        result = asyncio.run(_run())
        logger.info(
            "compute_foresight_recommendations done in %.2fs — %d cards "
            "(%d published, %d gated) — task_id=%s",
            result["elapsed_seconds"], result["cards_computed"],
            result["published"], result["gated"], task_id,
        )
        return {"task_id": task_id, "status": "completed", **result}
    except Exception as exc:
        logger.exception(
            "compute_foresight_recommendations failed — task_id=%s error=%s", task_id, exc
        )
        try:
            raise self.retry(exc=exc)
        except MaxRetriesExceededError:
            logger.error(
                "Max retries exceeded for compute_foresight_recommendations task_id=%s", task_id
            )
            raise


__all__ = ["compute_foresight_recommendations"]
