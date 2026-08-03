"""Pure funnel-stage aggregation helpers, built on ``lead_journey``.

The real synced funnel (see ``GET /api/v1/funnels/overview``) is derived
from ``lead_journey`` — there is no funnel_events/funnel_stats data (those
tables are empty dead scaffolding, left alone). Six ordered stages:

    leads          -> COUNT(*)
    registered     -> COUNT(webinar_registered_at)
    watched        -> COUNT(*) FILTER (WHERE watched_live OR watched_replay)
    booked appt    -> COUNT(*) FILTER (WHERE appt_count > 0)
    discovery held -> COUNT(*) FILTER (WHERE discovery_held)
    closed         -> COUNT(sale_id)

**Perf note (2026-08-04):** this module used to expand every one of the
12,820 ``lead_journey`` rows into a per-row ``StageFlags`` object in Python.
The route's ``SELECT *`` (41 columns) over the Supabase transaction pooler
took 68.4s — well past the frontend's 30s abort, so ``/marketing/funnels``
rendered empty in production. Fixed by pushing the whole aggregation into
ONE SQL statement: ``GROUP BY`` the 5 UTM/channel fields with the six stage
counts as ``FILTER`` aggregates (172 combo rows, ~3.3s). These helpers now
consume that combo-level shape directly — no per-lead-row Python loop, no
``StageFlags`` per-row expansion. Verified stage totals are unchanged
(12,820 / 11,557 / 6,872 / 1,289 / 183 / 83).

These helpers are pure (no DB) so they're unit-testable against fake combo
rows — mirrors ``test_leads_channel.py``'s SimpleNamespace-fake style. The
route layer does ONE grouped SQL read (``lead_journey`` scoped by
``entry_date``, ``GROUP BY`` the 5 UTM fields with FILTER aggregates) and
hands the resulting combo rows straight to these functions.
"""

from __future__ import annotations

from typing import Any, Sequence

from app.services.attribution import bucket_channel_combos, channel_for_lead

# Ordered stage keys — order is the funnel order — never resort this list.
STAGE_KEYS: tuple[str, ...] = (
    "leads", "registered", "watched", "booked_appt", "discovery_held", "closed",
)

STAGE_LABELS: dict[str, str] = {
    "leads": "Leads",
    "registered": "Registered",
    "watched": "Watched",
    "booked_appt": "Booked Appt",
    "discovery_held": "Discovery Held",
    "closed": "Closed",
}

# Kept for backward compat with any external caller keying off STAGE_DEFS.
STAGE_DEFS: tuple[tuple[str, str], ...] = tuple((k, STAGE_LABELS[k]) for k in STAGE_KEYS)


def _int(value: object) -> int:
    """Return value as int, falling back to 0 for None or non-numeric values."""
    try:
        return int(value) if value is not None else 0
    except (TypeError, ValueError):
        return 0


def combo_stage_counts(row: Any) -> dict[str, int]:
    """Read the six pre-aggregated stage counts off one SQL combo row (or a
    fake exposing the same attributes/keys). The row already carries COUNT/
    COUNT-FILTER results from the GROUP BY query — this just coerces them to
    int, never re-deriving a predicate over raw lead data (that work now
    happens in SQL, not here).

    Duck-types on ``.get`` rather than ``isinstance(row, dict)`` — a
    SQLAlchemy ``RowMapping`` (what ``.mappings()`` returns) is dict-*like*
    (supports ``.get``/``[]``) but is NOT a ``dict`` subclass, so an
    isinstance check would silently fall through to attribute access and
    return all zeros for real DB rows."""
    getter = row.get if hasattr(row, "get") else lambda k, d=None: getattr(row, k, d)
    return {key: _int(getter(key, 0)) for key in STAGE_KEYS}


def aggregate_overall_stages(combo_rows: Sequence[Any]) -> list[dict]:
    """Aggregate a sequence of SQL combo rows (one row per distinct 5-UTM
    combo, each carrying pre-aggregated stage counts) into the ordered
    overall funnel: [{stage, label, count, pct_of_leads,
    conversion_from_previous}, ...].

    ``pct_of_leads``: stage count / total lead count (stage 0), 1dp, 0.0 when
    there are no leads. ``conversion_from_previous``: stage count / previous
    stage's count, 1dp, None for the first stage or when the previous
    stage's count is 0 (avoid div-by-zero, not a 0.0% claim).

    Pure — no DB — so this is unit-testable against fakes (dicts or
    SimpleNamespace) exposing the six stage-count fields.
    """
    counts: dict[str, int] = {key: 0 for key in STAGE_KEYS}
    for row in combo_rows:
        row_counts = combo_stage_counts(row)
        for key in STAGE_KEYS:
            counts[key] += row_counts[key]

    total_leads = counts["leads"]
    stages: list[dict] = []
    prev_count: int | None = None
    for key in STAGE_KEYS:
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
                "label": STAGE_LABELS[key],
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
    """Bucket pre-aggregated combo rows by channel (via
    ``bucket_channel_combos``, reusing the shared resolver machinery — never
    reimplement bucket rules) and sum the six stage counts + lead->close
    rate per bucket.

    ``combos``: iterable of (utm_source_first, utm_medium_first,
    utm_content_first, utm_source_last, utm_medium_last, utm_content_last,
    stage_counts) where ``stage_counts`` is a dict with the six STAGE_KEYS
    (as returned by ``combo_stage_counts``) — one entry per distinct 6-tuple,
    already aggregated in SQL. ``leads`` doubles as the combo's row count,
    matching ``bucket_channel_combos``' ``(sf, mf, cf, sl, ml, cl, count)``
    combo contract.

    Returns rows ordered by leads count descending (ties broken by channel
    name ascending, for deterministic output): [{channel, platform,
    reportable, leads, registered, watched, booked_appt, discovery_held,
    closed, lead_to_close_pct}, ...].
    """
    combo_counts: dict[tuple, dict[str, int]] = {}
    for sf, mf, cf, sl, ml, cl, stage_counts in combos:
        key = (sf, mf, cf, sl, ml, cl)
        combo_counts[key] = stage_counts

    count_combos = [
        (sf, mf, cf, sl, ml, cl, stage_counts["leads"])
        for (sf, mf, cf, sl, ml, cl), stage_counts in combo_counts.items()
    ]
    bucket_map, buckets = bucket_channel_combos(
        count_combos, resolver, unmapped_top_n=unmapped_top_n
    )

    # Merge per-combo stage vectors into per-bucket-label stage totals.
    bucket_stage_totals: dict[str, dict[str, int]] = {}
    for key, label in bucket_map.items():
        totals = bucket_stage_totals.setdefault(label, {k: 0 for k in STAGE_KEYS})
        for stage_key in STAGE_KEYS:
            totals[stage_key] += combo_counts[key][stage_key]

    result: list[dict] = []
    for b in buckets:
        label = b["channel"]
        totals = bucket_stage_totals.get(label, {k: 0 for k in STAGE_KEYS})
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
    "STAGE_KEYS",
    "STAGE_LABELS",
    "STAGE_DEFS",
    "combo_stage_counts",
    "aggregate_overall_stages",
    "aggregate_by_channel",
    "channel_for_lead",
]
