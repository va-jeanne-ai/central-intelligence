"""Pure funnel-stage aggregation helpers, built on ``lead_journey``.

The real synced funnel (see ``GET /api/v1/funnels/overview``) is derived
per-lead from ``lead_journey`` rows — there is no funnel_events/funnel_stats
data (those tables are empty dead scaffolding, left alone). Six ordered
stages, each a boolean/derived predicate over one ``lead_journey`` row:

    leads          -> always true (every row)
    registered     -> webinar_registered_at IS NOT NULL
    watched        -> watched_live OR watched_replay
    booked appt    -> appt_count > 0
    discovery held -> discovery_held
    closed         -> sale_id IS NOT NULL

These helpers are pure (no DB) so they're unit-testable against fake
journey-like rows — mirrors ``test_leads_channel.py``'s SimpleNamespace-fake
style. The route layer does the DB read (``lead_journey`` scoped by
``entry_date``, and the six-UTM-tuple GROUP BY for the channel slice) and
hands rows/combos to these functions.
"""

from __future__ import annotations

from typing import Any, NamedTuple, Sequence

from app.services.attribution import bucket_channel_combos, channel_for_lead

# Ordered stage definitions: (key, label, predicate over a lead_journey-like row).
# Order is the funnel order — never resort this list.
STAGE_DEFS: tuple[tuple[str, str], ...] = (
    ("leads", "Leads"),
    ("registered", "Registered"),
    ("watched", "Watched"),
    ("booked_appt", "Booked Appt"),
    ("discovery_held", "Discovery Held"),
    ("closed", "Closed"),
)


def _int(value: object) -> int:
    """Return value as int, falling back to 0 for None or non-numeric values."""
    try:
        return int(value) if value is not None else 0
    except (TypeError, ValueError):
        return 0


class StageFlags(NamedTuple):
    """Precomputed stage membership for one lead_journey-like row. Every
    later stage in the funnel is *not* implied to be a subset of the earlier
    one at the data level (a lead could in principle have appt_count>0 but
    no registered_at) — but the funnel presentation always walks the fixed
    STAGE_DEFS order regardless, matching the discovery counts' semantics
    (each stage counted independently off the row, not gated on the
    previous stage)."""

    leads: bool
    registered: bool
    watched: bool
    booked_appt: bool
    discovery_held: bool
    closed: bool


def stage_flags_for_row(row: Any) -> StageFlags:
    """Compute the six stage booleans for one lead_journey row (or a fake
    exposing the same attributes). Never raises on missing/None fields —
    every predicate treats None as "does not qualify"."""
    webinar_registered_at = getattr(row, "webinar_registered_at", None)
    watched_live = bool(getattr(row, "watched_live", False))
    watched_replay = bool(getattr(row, "watched_replay", False))
    appt_count = _int(getattr(row, "appt_count", None))
    discovery_held = bool(getattr(row, "discovery_held", False))
    sale_id = getattr(row, "sale_id", None)

    return StageFlags(
        leads=True,
        registered=webinar_registered_at is not None,
        watched=watched_live or watched_replay,
        booked_appt=appt_count > 0,
        discovery_held=discovery_held,
        closed=sale_id is not None,
    )


def aggregate_overall_stages(rows: Sequence[Any]) -> list[dict]:
    """Aggregate a sequence of lead_journey-like rows into the ordered
    overall funnel: [{stage, label, count, pct_of_leads,
    conversion_from_previous}, ...].

    ``pct_of_leads``: stage count / total lead count (stage 0), 1dp, 0.0 when
    there are no leads. ``conversion_from_previous``: stage count / previous
    stage's count, 1dp, None for the first stage or when the previous
    stage's count is 0 (avoid div-by-zero, not a 0.0% claim).

    Pure — no DB — so this is unit-testable against fakes built with
    SimpleNamespace exposing the lead_journey attributes stage_flags_for_row
    reads.
    """
    total_leads = len(rows)
    counts: dict[str, int] = {key: 0 for key, _ in STAGE_DEFS}
    for row in rows:
        flags = stage_flags_for_row(row)
        for key, _ in STAGE_DEFS:
            if getattr(flags, key):
                counts[key] += 1

    stages: list[dict] = []
    prev_count: int | None = None
    for key, label in STAGE_DEFS:
        count = counts[key]
        pct_of_leads = round((count / total_leads) * 100, 1) if total_leads > 0 else 0.0
        conversion_from_previous = (
            round((count / prev_count) * 100, 1)
            if prev_count is not None and prev_count > 0
            else None
        )
        stages.append(
            {
                "stage": key,
                "label": label,
                "count": count,
                "pct_of_leads": pct_of_leads,
                "conversion_from_previous": conversion_from_previous,
            }
        )
        prev_count = count
    return stages


def aggregate_by_channel(
    combos: Sequence[tuple],
    resolver,
    *,
    unmapped_top_n: int = 8,
) -> list[dict]:
    """Bucket lead_journey rows by channel (via ``bucket_channel_combos``,
    reusing the shared resolver machinery — never reimplement bucket rules)
    and aggregate the six stage counts + lead->close rate per bucket.

    ``combos``: iterable of (utm_source_first, utm_medium_first,
    utm_content_first, utm_source_last, utm_medium_last, utm_content_last,
    *stage_flags_list) where stage_flags_list is a list of StageFlags (or
    objects exposing the same fields) — one per lead_journey row sharing
    that exact 6-tuple. This lets the route do ONE grouped read from
    lead_journey and hand this function everything it needs without a
    second DB round-trip.

    Returns rows ordered by leads count descending (ties broken by channel
    name ascending, for deterministic output): [{channel, platform,
    reportable, leads, registered, watched, booked_appt, discovery_held,
    closed, lead_to_close_pct}, ...].
    """
    # Reduce each combo's row-list down to a single count vector first (one
    # entry per distinct 6-tuple, matching bucket_channel_combos' combo
    # contract of (sf, mf, cf, sl, ml, cl, count)).
    combo_stage_counts: dict[tuple, dict[str, int]] = {}
    combo_lead_counts: dict[tuple, int] = {}
    for sf, mf, cf, sl, ml, cl, flags_list in combos:
        key = (sf, mf, cf, sl, ml, cl)
        stage_counts = combo_stage_counts.setdefault(key, {k: 0 for k, _ in STAGE_DEFS})
        for flags in flags_list:
            for stage_key, _ in STAGE_DEFS:
                if getattr(flags, stage_key):
                    stage_counts[stage_key] += 1
        combo_lead_counts[key] = combo_lead_counts.get(key, 0) + len(flags_list)

    count_combos = [
        (sf, mf, cf, sl, ml, cl, combo_lead_counts[(sf, mf, cf, sl, ml, cl)])
        for (sf, mf, cf, sl, ml, cl) in combo_stage_counts
    ]
    bucket_map, buckets = bucket_channel_combos(
        count_combos, resolver, unmapped_top_n=unmapped_top_n
    )

    # Merge per-combo stage vectors into per-bucket-label stage totals.
    bucket_stage_totals: dict[str, dict[str, int]] = {}
    for key, label in bucket_map.items():
        totals = bucket_stage_totals.setdefault(label, {k: 0 for k, _ in STAGE_DEFS})
        for stage_key, _ in STAGE_DEFS:
            totals[stage_key] += combo_stage_counts[key][stage_key]

    result: list[dict] = []
    for b in buckets:
        label = b["channel"]
        totals = bucket_stage_totals.get(label, {k: 0 for k, _ in STAGE_DEFS})
        leads_count = totals["leads"]
        closed_count = totals["closed"]
        lead_to_close_pct = (
            round((closed_count / leads_count) * 100, 1) if leads_count > 0 else 0.0
        )
        result.append(
            {
                "channel": label,
                "platform": b.get("platform"),
                "reportable": b.get("reportable", True),
                "leads": totals["leads"],
                "registered": totals["registered"],
                "watched": totals["watched"],
                "booked_appt": totals["booked_appt"],
                "discovery_held": totals["discovery_held"],
                "closed": totals["closed"],
                "lead_to_close_pct": lead_to_close_pct,
            }
        )
    result.sort(key=lambda item: (-item["leads"], item["channel"]))
    return result


__all__ = [
    "STAGE_DEFS",
    "StageFlags",
    "stage_flags_for_row",
    "aggregate_overall_stages",
    "aggregate_by_channel",
    "channel_for_lead",
]
