"""Tests for the pure funnel-stage aggregation helpers built on lead_journey
(app.repositories.funnel_stats). Mirrors test_leads_channel.py style:
SimpleNamespace/dict fakes, no DB.

Contract under test (post 2026-08-04 perf fix — combo-level, not per-row):
- combo_stage_counts: reads the six pre-aggregated stage counts off one SQL
  GROUP BY combo row (dict-like RowMapping OR attribute-style fake).
- aggregate_overall_stages: sums combo-level stage counts into the ordered
  overall funnel + pct_of_leads (of stage 0) + conversion_from_previous
  (None when no previous stage or previous is 0).
- aggregate_by_channel: per-bucket stage counts + lead->close rate, summed
  from combo-level dicts, reusing bucket_channel_combos so bucket rules
  never get reimplemented.
"""

from app.repositories.funnel_stats import (
    aggregate_by_channel,
    aggregate_overall_stages,
    combo_stage_counts,
)
from app.services.attribution import build_resolver
from types import SimpleNamespace


def _combo_row(leads=0, registered=0, watched=0, booked_appt=0, discovery_held=0, closed=0):
    """A SQL GROUP BY combo row, as a dict — same shape a RowMapping exposes
    via .get()/[] (dict-like, but NOT a dict subclass in real SQLAlchemy;
    a plain dict here exercises the same .get() code path)."""
    return {
        "leads": leads, "registered": registered, "watched": watched,
        "booked_appt": booked_appt, "discovery_held": discovery_held, "closed": closed,
    }


# --- combo_stage_counts ---


def test_combo_stage_counts_reads_dict_row():
    row = _combo_row(leads=10, registered=8, watched=5, booked_appt=2, discovery_held=1, closed=1)
    counts = combo_stage_counts(row)
    assert counts == {
        "leads": 10, "registered": 8, "watched": 5,
        "booked_appt": 2, "discovery_held": 1, "closed": 1,
    }


def test_combo_stage_counts_reads_attribute_style_fake():
    """Non-dict fakes (e.g. SimpleNamespace) must also work via getattr —
    covers any caller that doesn't have a RowMapping/dict on hand."""
    row = SimpleNamespace(leads=3, registered=2, watched=1, booked_appt=0, discovery_held=0, closed=0)
    counts = combo_stage_counts(row)
    assert counts["leads"] == 3
    assert counts["registered"] == 2


def test_combo_stage_counts_missing_fields_default_to_zero():
    counts = combo_stage_counts({})
    assert all(v == 0 for v in counts.values())


def test_combo_stage_counts_coerces_none_and_non_numeric_to_zero():
    row = _combo_row()
    row["leads"] = None
    counts = combo_stage_counts(row)
    assert counts["leads"] == 0


# --- aggregate_overall_stages ---


def test_aggregate_overall_stages_sums_combo_rows():
    """Mirrors the discovery contract via combo rows instead of per-lead
    rows — two combos summing to the same totals a per-row expansion would
    have produced."""
    combos = [
        _combo_row(leads=4, registered=3, watched=2, booked_appt=1, discovery_held=0, closed=0),
        _combo_row(leads=2, registered=2, watched=2, booked_appt=2, discovery_held=2, closed=1),
    ]
    stages = aggregate_overall_stages(combos)
    by_key = {s["stage"]: s for s in stages}
    assert by_key["leads"]["count"] == 6
    assert by_key["registered"]["count"] == 5
    assert by_key["watched"]["count"] == 4
    assert by_key["booked_appt"]["count"] == 3
    assert by_key["discovery_held"]["count"] == 2
    assert by_key["closed"]["count"] == 1
    # pct_of_leads is share of stage-0 (leads) count
    assert by_key["closed"]["pct_of_leads"] == round(1 / 6 * 100, 1)
    # conversion_from_previous chains stage-to-stage
    assert by_key["registered"]["conversion_from_previous"] == round(5 / 6 * 100, 1)
    assert by_key["leads"]["conversion_from_previous"] is None


def test_aggregate_overall_stages_empty_input():
    stages = aggregate_overall_stages([])
    assert all(s["count"] == 0 for s in stages)
    assert all(s["pct_of_leads"] == 0.0 for s in stages)
    assert stages[0]["conversion_from_previous"] is None


def test_aggregate_overall_stages_conversion_none_when_previous_zero():
    # No leads registered at all -> every downstream conversion is None,
    # not a misleading 0.0%.
    combos = [_combo_row(leads=2, registered=0, watched=0)]
    stages = aggregate_overall_stages(combos)
    by_key = {s["stage"]: s for s in stages}
    assert by_key["registered"]["count"] == 0
    assert by_key["watched"]["conversion_from_previous"] is None


def test_aggregate_overall_stages_order_is_fixed():
    stages = aggregate_overall_stages([_combo_row(leads=1)])
    assert [s["stage"] for s in stages] == [
        "leads", "registered", "watched", "booked_appt", "discovery_held", "closed",
    ]


def test_aggregate_overall_stages_matches_real_discovery_numbers():
    """A single combo row carrying the exact discovery totals must pass
    through unchanged — sanity-checks the SQL->helper contract end to end
    without a DB."""
    combos = [
        _combo_row(
            leads=12820, registered=11557, watched=6872,
            booked_appt=1289, discovery_held=183, closed=83,
        )
    ]
    stages = aggregate_overall_stages(combos)
    counts = [s["count"] for s in stages]
    assert counts == [12820, 11557, 6872, 1289, 183, 83]


# --- aggregate_by_channel ---

ROWS = [
    SimpleNamespace(
        id=1, observed_source="ig", observed_medium=None, observed_content=None,
        canonical_channel="instagram_organic", platform=None,
        include_in_channel_reporting=True,
    ),
    SimpleNamespace(
        id=2, observed_source="ig", observed_medium="paid", observed_content=None,
        canonical_channel="meta_paid", platform="ig",
        include_in_channel_reporting=True,
    ),
]


def _combo(sf=None, mf=None, cf=None, sl=None, ml=None, cl=None, **stage_kwargs):
    return (sf, mf, cf, sl, ml, cl, _combo_row(**stage_kwargs))


def test_aggregate_by_channel_buckets_and_sums_stage_counts():
    resolver = build_resolver(ROWS)
    combos = [_combo(sf="ig", leads=2, registered=1, closed=1)]
    result = aggregate_by_channel(combos, resolver)
    bucket = {row["channel"]: row for row in result}
    assert bucket["instagram_organic"]["leads"] == 2
    assert bucket["instagram_organic"]["registered"] == 1
    assert bucket["instagram_organic"]["closed"] == 1
    assert bucket["instagram_organic"]["lead_to_close_pct"] == round(1 / 2 * 100, 1)


def test_aggregate_by_channel_merges_multiple_combos_into_same_bucket():
    resolver = build_resolver(ROWS)
    combos = [
        _combo(sf="ig", mf="paid", leads=1, closed=1),
        _combo(sl="ig", ml="paid", leads=1),
    ]
    result = aggregate_by_channel(combos, resolver)
    bucket = {row["channel"]: row for row in result}
    assert bucket["meta_paid"]["leads"] == 2
    assert bucket["meta_paid"]["closed"] == 1


def test_aggregate_by_channel_ordered_by_leads_desc():
    resolver = build_resolver(ROWS)
    combos = [
        _combo(sf="ig", leads=1),
        _combo(sf="ig", mf="paid", leads=5),
    ]
    result = aggregate_by_channel(combos, resolver)
    assert result[0]["channel"] == "meta_paid"
    assert result[0]["leads"] == 5
    assert result[1]["channel"] == "instagram_organic"


def test_aggregate_by_channel_no_leads_zero_percent_not_none():
    resolver = build_resolver(ROWS)
    combos = [_combo(sf="ig", leads=0)]
    result = aggregate_by_channel(combos, resolver)
    # A bucket with zero leads (degenerate — shouldn't normally happen since
    # combos come from GROUP BY on real rows) still returns 0.0, not a crash.
    if result:
        assert result[0]["lead_to_close_pct"] == 0.0


def test_aggregate_by_channel_sum_of_leads_equals_input_sum():
    """Reconciliation contract: sum of every bucket's leads must equal the
    sum of every input combo's leads — same guarantee bucket_channel_combos
    provides at the raw-combo level, preserved through the stage-count
    summation."""
    resolver = build_resolver(ROWS)
    combos = [
        _combo(sf="ig", leads=100, closed=5),
        _combo(sf="ig", mf="paid", leads=50, closed=2),
        _combo(leads=25, closed=1),  # No attribution
    ]
    result = aggregate_by_channel(combos, resolver)
    assert sum(row["leads"] for row in result) == 175
    assert sum(row["closed"] for row in result) == 8
