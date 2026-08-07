"""Foresight P1 cohort counting — one SQL aggregate query per candidate
family (pooler rule: no row shipping — see funnel_stats.py's perf note for
why this matters at the Supabase transaction pooler's timeout).

Four candidate families (docs/superpowers/plans/
2026-08-06-foresight-layer-prototype.md "P1 architecture"):

  - live_vs_replay: lead_journey watched_live (booked) vs replay-only.
  - channel_close: lead_journey combos grouped by the 5 UTM fields (no
    utm_content_last upstream — None passed in the 6-tuple, same as
    funnels.py), bucketed via bucket_channel_combos, sliced per-channel.
  - email_value: email_campaigns AVG/STDDEV_SAMP/COUNT of open_rate by
    campaign_type.
  - discovery_families: insights x calls x leads x lead_journey join,
    counting close rate per signal_family among discovery-held leads.

Each function takes an ``AsyncSession`` and returns plain dicts/tuples —
no ORM row objects leak out — so the pure app.services.foresight layer
never needs to know about SQLAlchemy.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.attribution import bucket_channel_combos, build_resolver


async def fetch_live_vs_replay(session: AsyncSession) -> dict[str, dict[str, int]]:
    """ONE aggregate query over lead_journey: watched_live cohort (booked =
    appt_count>0) vs replay-only (watched_replay AND NOT watched_live).
    Returns {"watched_live": {"n": ..., "booked": ...}, "replay_only": {...}}.
    """
    row = (
        await session.execute(
            text(
                """
                SELECT
                    COUNT(*) FILTER (WHERE watched_live) AS live_n,
                    COUNT(*) FILTER (WHERE watched_live AND appt_count > 0) AS live_booked,
                    COUNT(*) FILTER (WHERE watched_replay AND NOT watched_live) AS replay_n,
                    COUNT(*) FILTER (
                        WHERE watched_replay AND NOT watched_live AND appt_count > 0
                    ) AS replay_booked
                FROM lead_journey
                """
            )
        )
    ).mappings().one()

    return {
        "watched_live": {"n": int(row["live_n"] or 0), "booked": int(row["live_booked"] or 0)},
        "replay_only": {"n": int(row["replay_n"] or 0), "booked": int(row["replay_booked"] or 0)},
    }


async def fetch_channel_close(session: AsyncSession) -> dict[str, dict[str, int]]:
    """Journey combos grouped by the 5 UTM fields (utm_content_last passed
    as None — lead_journey has no such column upstream, same contract as
    funnels.py's /overview), COUNT(*) + COUNT(sale_id) per combo. Bucketed
    via bucket_channel_combos (never reimplement bucket rules) into
    per-channel (n, closed) totals, plus the all-lead baseline.

    The combo rows themselves (~172 distinct UTM combinations, verified in
    funnels.py's perf note) are NOT per-lead rows — this is the same
    bounded aggregate shape the funnels endpoint already ships, not a
    violation of the "one aggregate, never ship rows" rule for the
    12,933-row lead table itself.
    """
    combo_rows = (
        await session.execute(
            text(
                """
                SELECT
                    utm_source_first, utm_medium_first, utm_content_first,
                    utm_source_last, utm_medium_last,
                    COUNT(*) AS n,
                    COUNT(sale_id) AS closed
                FROM lead_journey
                GROUP BY 1, 2, 3, 4, 5
                """
            )
        )
    ).mappings().all()

    taxonomy_rows = (await session.execute(text("SELECT * FROM attribution_taxonomy"))).fetchall()
    resolver = build_resolver(taxonomy_rows)

    combos_for_bucketing = [
        (
            r["utm_source_first"], r["utm_medium_first"], r["utm_content_first"],
            r["utm_source_last"], r["utm_medium_last"], None,  # no utm_content_last upstream
            int(r["n"] or 0),
        )
        for r in combo_rows
    ]
    bucket_map, _buckets = bucket_channel_combos(combos_for_bucketing, resolver)

    # Merge per-combo closed counts into per-bucket-label totals.
    per_bucket: dict[str, dict[str, int]] = {}
    total_n = 0
    total_closed = 0
    for r in combo_rows:
        key = (
            r["utm_source_first"], r["utm_medium_first"], r["utm_content_first"],
            r["utm_source_last"], r["utm_medium_last"], None,
        )
        label = bucket_map[key]
        n = int(r["n"] or 0)
        closed = int(r["closed"] or 0)
        total_n += n
        total_closed += closed
        totals = per_bucket.setdefault(label, {"n": 0, "closed": 0})
        totals["n"] += n
        totals["closed"] += closed

    per_bucket["__all_leads__"] = {"n": total_n, "closed": total_closed}
    return per_bucket


async def fetch_email_value(session: AsyncSession) -> dict[str, dict[str, Any]]:
    """AVG/STDDEV_SAMP/COUNT of open_rate for campaign_type='Value/Education'
    vs the rest (deleted_at IS NULL, open_rate IS NOT NULL). ONE aggregate
    query, two FILTER'd column sets — never ships a row per campaign."""
    row = (
        await session.execute(
            text(
                """
                SELECT
                    COUNT(*) FILTER (WHERE campaign_type = 'Value/Education') AS value_n,
                    AVG(open_rate) FILTER (WHERE campaign_type = 'Value/Education') AS value_mean,
                    STDDEV_SAMP(open_rate) FILTER (
                        WHERE campaign_type = 'Value/Education'
                    ) AS value_sd,
                    COUNT(*) FILTER (
                        WHERE campaign_type IS DISTINCT FROM 'Value/Education'
                    ) AS other_n,
                    AVG(open_rate) FILTER (
                        WHERE campaign_type IS DISTINCT FROM 'Value/Education'
                    ) AS other_mean,
                    STDDEV_SAMP(open_rate) FILTER (
                        WHERE campaign_type IS DISTINCT FROM 'Value/Education'
                    ) AS other_sd
                FROM email_campaigns
                WHERE deleted_at IS NULL AND open_rate IS NOT NULL
                """
            )
        )
    ).mappings().one()

    return {
        "value_education": {
            "n": int(row["value_n"] or 0),
            "mean": float(row["value_mean"]) if row["value_mean"] is not None else 0.0,
            "sd": float(row["value_sd"]) if row["value_sd"] is not None else 0.0,
        },
        "other": {
            "n": int(row["other_n"] or 0),
            "mean": float(row["other_mean"]) if row["other_mean"] is not None else 0.0,
            "sd": float(row["other_sd"]) if row["other_sd"] is not None else 0.0,
        },
    }


async def fetch_discovery_families(
    session: AsyncSession, *, min_n: int = 20
) -> dict[str, Any]:
    """insights x calls x leads x lead_journey join: per-signal_family close
    rate among discovery-held leads (n>=20), plus the discovery-held
    baseline (all leads with discovery_held=true, regardless of family).

    Join contract (same as routes/leads.py's journey lookup, hardened the
    same way sales_stats.py's channel/revenue query is): insights -> calls
    (call_id) -> leads (lead_id) -> lead_journey, matched via a LATERAL
    subquery preferring leads.external_id = lead_journey.lead_id and
    falling back to leads.ghl_contact_id = lead_journey.ghl_contact_id,
    LIMIT 1. A plain multi-condition JOIN ... ON (OR ...) can silently fan
    a lead out across multiple lead_journey rows when its external_id and
    ghl_contact_id each match a *different* journey row — confirmed present
    in this DB. Only lead_journey.discovery_held = true rows count (a lead
    can appear under multiple signal_families if multiple insights tag it —
    intentional per the plan's "signal-family -> close rate" framing, not a
    double-count bug: each family's rate is independently the close rate
    AMONG LEADS CARRYING THAT SIGNAL).

    Returns {"baseline": {"n":.., "closed":..}, "families": [{"signal_family":..,
    "n":.., "closed":..}, ...]} — families list already filtered to n>=min_n.
    """
    baseline_row = (
        await session.execute(
            text(
                """
                SELECT
                    COUNT(*) AS n,
                    COUNT(*) FILTER (WHERE sale_id IS NOT NULL) AS closed
                FROM lead_journey
                WHERE discovery_held IS TRUE
                """
            )
        )
    ).mappings().one()

    # LEFT JOIN LATERAL ... ORDER BY (external_id match) DESC LIMIT 1 — same
    # guard as sales_stats.py's channel/revenue query. A plain
    # "ON lj.lead_id = l.external_id OR (... ghl_contact_id ...)" join can
    # silently fan a lead out across MULTIPLE lead_journey rows when a
    # lead's external_id matches one journey row and its ghl_contact_id
    # matches a *different* one (confirmed present in this DB — 3+ leads
    # exhibit this). COUNT(DISTINCT lj.lead_id) alone doesn't fully guard
    # against that: it would still let a lead contribute a `closed=True`
    # count from a wrong journey row via the OR branch. The lateral join
    # picks exactly one journey row per lead (external_id match preferred),
    # eliminating the fan-out at the join itself.
    family_rows = (
        await session.execute(
            text(
                """
                SELECT
                    i.signal_family AS signal_family,
                    COUNT(DISTINCT l.id) AS n,
                    COUNT(DISTINCT l.id) FILTER (WHERE lj.sale_id IS NOT NULL) AS closed
                FROM insights i
                JOIN calls c ON c.id = i.call_id
                JOIN leads l ON l.id = c.lead_id
                JOIN LATERAL (
                    SELECT lv.lead_id, lv.sale_id
                    FROM lead_journey lv
                    WHERE lv.discovery_held IS TRUE
                      AND (
                            lv.lead_id = l.external_id
                         OR (l.ghl_contact_id IS NOT NULL AND lv.ghl_contact_id = l.ghl_contact_id)
                      )
                    ORDER BY (lv.lead_id = l.external_id) DESC
                    LIMIT 1
                ) lj ON TRUE
                WHERE i.signal_family IS NOT NULL
                GROUP BY i.signal_family
                HAVING COUNT(DISTINCT l.id) >= :min_n
                ORDER BY i.signal_family
                """
            ),
            {"min_n": min_n},
        )
    ).mappings().all()

    return {
        "baseline": {
            "n": int(baseline_row["n"] or 0),
            "closed": int(baseline_row["closed"] or 0),
        },
        "families": [
            {
                "signal_family": r["signal_family"],
                "n": int(r["n"] or 0),
                "closed": int(r["closed"] or 0),
            }
            for r in family_rows
        ],
    }


__all__ = [
    "fetch_live_vs_replay",
    "fetch_channel_close",
    "fetch_email_value",
    "fetch_discovery_families",
]
