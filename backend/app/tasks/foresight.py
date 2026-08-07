"""Celery task: compute Foresight P1 recommendation cards nightly.

Runs the four cohort-count queries (app.repositories.foresight_stats),
assembles cards (app.services.foresight), applies the hysteresis state
machine against each candidate's PRIOR persisted status, and overwrites the
foresight_recommendations table in one transaction (delete+insert — OUR
table, not a WGR mirror, small enough that snapshot-reconcile machinery
buys nothing). See docs/superpowers/plans/
2026-08-06-foresight-layer-prototype.md "P1 architecture (as built)".

Uses ``asyncio.run`` + ``AsyncSessionLocal`` (same bridge pattern as
``app.tasks.wgr_sync.sync_wgr``) because the repository layer is async but
Celery tasks run outside FastAPI's event loop.

Gate-integrity notes (fixed after code review, see CHANGELOG):
  - Every ``build_card`` call passes both cohorts' n so the gate-integrity
    floor (``MIN_COHORT_N=30``) can reject thin/missing/empty cohorts
    before any interval comparison runs.
  - The channel candidates (ig_dm, meta_paid) compare against the
    COMPLEMENT baseline (all leads EXCLUDING the variant's own leads), not
    the inclusive all-lead baseline — the variant no longer contaminates
    what it's measured against.
  - The discovery-family sweep uses the Bonferroni-corrected
    ``DISCOVERY_SWEEP_Z`` (2.69, alpha/7) for every family's Wilson interval,
    controlling the family-wise error rate across the 7-way comparison.
  - A candidate's DISPLAYED status is the hysteresis-adjusted one
    (``apply_hysteresis``), not the raw per-night verdict — gated->published
    needs 2 consecutive clearing nights; published->gated is immediate.
    This requires reading each row's PRIOR status/streak before the
    delete+insert.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from uuid import uuid4

from celery.exceptions import MaxRetriesExceededError
from sqlalchemy import delete, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.intelligence import ForesightRecommendation
from app.repositories.foresight_stats import (
    complement_baseline,
    fetch_channel_close,
    fetch_discovery_families,
    fetch_email_value,
    fetch_live_vs_replay,
)
from app.services.foresight import (
    CANDIDATES,
    DISCOVERY_SWEEP_Z,
    MIN_COHORT_N,
    VerdictResult,
    apply_hysteresis,
    build_card,
    discovery_family_action,
    discovery_family_title,
    discovery_hold_reason,
    mean_interval,
    verdict,
    wilson_interval,
)
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


async def _fetch_prior_state(session: AsyncSession) -> dict[str, tuple[str, int]]:
    """Read each candidate's PRIOR displayed status + streak before this
    run's delete+insert — the hysteresis state machine needs it. Returns
    {slug: (status, consecutive_clear_nights)}; a slug absent from the
    table (first run ever) is simply absent from the dict, and
    apply_hysteresis treats a missing prior as prior_status=None."""
    rows = (
        await session.execute(
            select(
                ForesightRecommendation.id,
                ForesightRecommendation.status,
                ForesightRecommendation.consecutive_clear_nights,
            )
        )
    ).all()
    return {r.id: (r.status, r.consecutive_clear_nights) for r in rows}


def _displayed_card(
    card: dict, prior: dict[str, tuple[str, int]]
) -> dict:
    """Apply hysteresis to one already-assembled card dict (which carries
    the RAW per-night verdict from build_card) and overwrite its
    status/confidence/hold_reason with the DISPLAYED (hysteresis-adjusted)
    values, adding consecutive_clear_nights for persistence."""
    prior_status, prior_streak = prior.get(card["id"], (None, 0))
    raw_result = VerdictResult(card["status"], card["confidence"], card["hold_reason"])
    hyst = apply_hysteresis(
        prior_status=prior_status,  # type: ignore[arg-type]
        prior_consecutive_clear_nights=prior_streak,
        raw_verdict=raw_result,
    )
    return {
        **card,
        "status": hyst.status,
        "confidence": hyst.confidence,
        "hold_reason": hyst.hold_reason,
        "consecutive_clear_nights": hyst.consecutive_clear_nights,
    }


async def _compute_cards(session: AsyncSession) -> list[dict]:
    """Run all four cohort queries and assemble every card's RAW verdict.
    Pure orchestration — no prose generation here beyond interpolating
    already-computed values (e.g. the winning family name), which lives in
    app.services.foresight's discovery_family_title/_action helpers."""
    cards: list[dict] = []

    # 1. live_vs_replay — single planned comparison, standard z=1.96.
    lvr = await fetch_live_vs_replay(session)
    baseline = wilson_interval(lvr["replay_only"]["booked"], lvr["replay_only"]["n"])
    variant = wilson_interval(lvr["watched_live"]["booked"], lvr["watched_live"]["n"])
    cards.append(
        build_card(
            CANDIDATES["live_watch"], baseline, variant,
            baseline_n=lvr["replay_only"]["n"], variant_n=lvr["watched_live"]["n"],
        )
    )

    # 2. channel_close — ig_dm and meta_paid vs their OWN complement
    # baseline (all leads EXCLUDING that variant's leads), not the
    # inclusive all-lead baseline. Single planned comparison per channel,
    # standard z=1.96.
    channels = await fetch_channel_close(session)

    ig_dm = channels.get("ig_dm", {"n": 0, "closed": 0})
    ig_dm_baseline = complement_baseline(channels, "ig_dm")
    ig_dm_baseline_iv = wilson_interval(ig_dm_baseline["closed"], ig_dm_baseline["n"])
    ig_dm_iv = wilson_interval(ig_dm["closed"], ig_dm["n"])
    cards.append(
        build_card(
            CANDIDATES["ig_dm_channel"], ig_dm_baseline_iv, ig_dm_iv,
            baseline_n=ig_dm_baseline["n"], variant_n=ig_dm["n"],
        )
    )

    meta_paid = channels.get("meta_paid", {"n": 0, "closed": 0})
    meta_paid_baseline = complement_baseline(channels, "meta_paid")
    meta_paid_baseline_iv = wilson_interval(meta_paid_baseline["closed"], meta_paid_baseline["n"])
    meta_paid_iv = wilson_interval(meta_paid["closed"], meta_paid["n"])
    cards.append(
        build_card(
            CANDIDATES["meta_paid_close"], meta_paid_baseline_iv, meta_paid_iv,
            baseline_n=meta_paid_baseline["n"], variant_n=meta_paid["n"],
        )
    )

    # 3. email_value — single planned comparison, standard z=1.96.
    email = await fetch_email_value(session)
    other_iv = mean_interval(
        mean=email["other"]["mean"], sd=email["other"]["sd"], n=email["other"]["n"]
    )
    value_iv = mean_interval(
        mean=email["value_education"]["mean"],
        sd=email["value_education"]["sd"],
        n=email["value_education"]["n"],
    )
    cards.append(
        build_card(
            CANDIDATES["email_value"], other_iv, value_iv,
            baseline_n=email["other"]["n"], variant_n=email["value_education"]["n"],
        )
    )

    # 4. discovery_families — a 7-way sweep (one comparison per signal
    # family with n>=20), so EVERY family interval uses the
    # Bonferroni-corrected DISCOVERY_SWEEP_Z (2.69, alpha/7) to control the
    # family-wise error rate. The published family's name is a COMPUTED
    # value (the winning signal_family) interpolated into the card's
    # otherwise-static title/action via discovery_family_title/_action —
    # never invented prose.
    discovery = await fetch_discovery_families(session)
    disc_baseline_iv = wilson_interval(
        discovery["baseline"]["closed"], discovery["baseline"]["n"], z=DISCOVERY_SWEEP_Z
    )
    families = discovery["families"]
    if families:
        family_intervals = [
            (f["signal_family"], f["n"], wilson_interval(f["closed"], f["n"], z=DISCOVERY_SWEEP_Z))
            for f in families
        ]
        top_family, top_n, top_iv = max(family_intervals, key=lambda triple: triple[2].rate)
    else:
        top_family, top_n, top_iv = "—", 0, wilson_interval(0, 0, z=DISCOVERY_SWEEP_Z)

    def _hold_reason() -> str:
        return discovery_hold_reason(
            n=discovery["baseline"]["n"],
            baseline=disc_baseline_iv,
            top_family=top_family,
            top=top_iv,
        )

    # The raw verdict decides whether the family name should be interpolated
    # at all — a gated card must NOT claim a winning family in its title
    # (there is no winner when the gate holds), only the hold_reason names
    # the closest family. Compute the raw verdict once here so the
    # title/action overrides are conditional on it, then let build_card
    # recompute the same verdict internally (cheap, pure, keeps build_card
    # as the single source of truth for the verdict itself).
    raw_disc_verdict = verdict(
        disc_baseline_iv, top_iv,
        baseline_n=discovery["baseline"]["n"], variant_n=top_n,
        hold_reason_fn=_hold_reason,
    )
    disc_publishes = raw_disc_verdict.verdict in ("published_lift", "published_warning")

    cards.append(
        build_card(
            CANDIDATES["discovery_families"],
            disc_baseline_iv,
            top_iv,
            baseline_n=discovery["baseline"]["n"],
            variant_n=top_n,
            hold_reason_fn=_hold_reason,
            title_override=discovery_family_title(top_family) if disc_publishes else None,
            variant_label_override=top_family if disc_publishes else None,
            action_text_override=discovery_family_action(top_family) if disc_publishes else None,
        )
    )

    return cards


async def _run() -> dict:
    started = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as session:
        # Read PRIOR displayed status/streak BEFORE the delete — the
        # hysteresis state machine needs last run's state to decide this
        # run's displayed state.
        prior = await _fetch_prior_state(session)

        raw_cards = await _compute_cards(session)
        cards = [_displayed_card(card, prior) for card in raw_cards]

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
                "consecutive_clear_nights": card["consecutive_clear_nights"],
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
            "min_cohort_n": MIN_COHORT_N,
        }


@celery_app.task(bind=True, max_retries=3, default_retry_delay=300)
def compute_foresight_recommendations(self) -> dict:
    """Scheduled Celery task — recompute all Foresight P1 cards from the
    live mirrors and overwrite foresight_recommendations.

    Idempotent (full overwrite each run — but the DISPLAYED status is
    hysteresis-adjusted against the row it's overwriting, so re-running
    twice in a row is safe and expected, not merely non-destructive). Pure
    aggregate reads — expected well under 60s (see the plan's
    pooler-timeout rule: no row shipping).
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
