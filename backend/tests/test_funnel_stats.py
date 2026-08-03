"""Tests for the pure funnel-stage aggregation helpers built on lead_journey
(app.repositories.funnel_stats). Mirrors test_leads_channel.py style:
SimpleNamespace fakes, no DB.

Contract under test:
- stage_flags_for_row: six stage predicates over a lead_journey-like row,
  matching the deliverable's discovery contract exactly (registered =
  webinar_registered_at not null; watched = watched_live OR watched_replay;
  booked_appt = appt_count>0; discovery_held column; closed = sale_id not
  null).
- aggregate_overall_stages: ordered stage counts + pct_of_leads (of stage 0)
  + conversion_from_previous (None when no previous stage or previous is 0).
- aggregate_by_channel: per-bucket stage counts + lead->close rate, reusing
  bucket_channel_combos so bucket rules never get reimplemented.
"""

from types import SimpleNamespace

from app.repositories.funnel_stats import (
    aggregate_by_channel,
    aggregate_overall_stages,
    stage_flags_for_row,
)
from app.services.attribution import build_resolver


def _journey(
    webinar_registered_at=None,
    watched_live=False,
    watched_replay=False,
    appt_count=0,
    discovery_held=False,
    sale_id=None,
):
    return SimpleNamespace(
        webinar_registered_at=webinar_registered_at,
        watched_live=watched_live,
        watched_replay=watched_replay,
        appt_count=appt_count,
        discovery_held=discovery_held,
        sale_id=sale_id,
    )


# --- stage_flags_for_row ---


def test_stage_flags_bare_lead_only_leads_true():
    flags = stage_flags_for_row(_journey())
    assert flags.leads is True
    assert flags.registered is False
    assert flags.watched is False
    assert flags.booked_appt is False
    assert flags.discovery_held is False
    assert flags.closed is False


def test_stage_flags_registered_requires_non_null_timestamp():
    flags = stage_flags_for_row(_journey(webinar_registered_at="2026-01-01T00:00:00Z"))
    assert flags.registered is True


def test_stage_flags_watched_true_if_either_live_or_replay():
    assert stage_flags_for_row(_journey(watched_live=True)).watched is True
    assert stage_flags_for_row(_journey(watched_replay=True)).watched is True
    assert stage_flags_for_row(_journey()).watched is False


def test_stage_flags_booked_appt_requires_positive_count():
    assert stage_flags_for_row(_journey(appt_count=0)).booked_appt is False
    assert stage_flags_for_row(_journey(appt_count=None)).booked_appt is False
    assert stage_flags_for_row(_journey(appt_count=2)).booked_appt is True


def test_stage_flags_closed_requires_sale_id():
    assert stage_flags_for_row(_journey(sale_id=None)).closed is False
    assert stage_flags_for_row(_journey(sale_id="s-1")).closed is True


def test_stage_flags_missing_attributes_default_safely():
    """A fake exposing none of the attributes must not raise — every
    predicate treats a missing/None field as 'does not qualify'."""
    flags = stage_flags_for_row(SimpleNamespace())
    assert flags.leads is True
    assert flags.registered is False
    assert flags.watched is False
    assert flags.booked_appt is False
    assert flags.discovery_held is False
    assert flags.closed is False


# --- aggregate_overall_stages ---


def test_aggregate_overall_stages_matches_discovery_shape():
    rows = [
        _journey(),  # lead only
        _journey(webinar_registered_at="t"),  # registered
        _journey(webinar_registered_at="t", watched_live=True),  # watched
        _journey(webinar_registered_at="t", watched_live=True, appt_count=1),  # booked
        _journey(
            webinar_registered_at="t", watched_live=True, appt_count=1,
            discovery_held=True,
        ),  # discovery held
        _journey(
            webinar_registered_at="t", watched_live=True, appt_count=1,
            discovery_held=True, sale_id="s-1",
        ),  # closed
    ]
    stages = aggregate_overall_stages(rows)
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
    rows = [_journey(), _journey()]
    stages = aggregate_overall_stages(rows)
    by_key = {s["stage"]: s for s in stages}
    assert by_key["registered"]["count"] == 0
    assert by_key["watched"]["conversion_from_previous"] is None


def test_aggregate_overall_stages_order_is_fixed():
    stages = aggregate_overall_stages([_journey()])
    assert [s["stage"] for s in stages] == [
        "leads", "registered", "watched", "booked_appt", "discovery_held", "closed",
    ]


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


def _combo(sf=None, mf=None, cf=None, sl=None, ml=None, cl=None, flags_list=None):
    return (sf, mf, cf, sl, ml, cl, flags_list or [])


def test_aggregate_by_channel_buckets_and_sums_stage_counts():
    resolver = build_resolver(ROWS)
    ig_flags = [
        stage_flags_for_row(_journey()),
        stage_flags_for_row(_journey(webinar_registered_at="t", sale_id="s-1")),
    ]
    combos = [_combo(sf="ig", flags_list=ig_flags)]
    result = aggregate_by_channel(combos, resolver)
    bucket = {row["channel"]: row for row in result}
    assert bucket["instagram_organic"]["leads"] == 2
    assert bucket["instagram_organic"]["registered"] == 1
    assert bucket["instagram_organic"]["closed"] == 1
    assert bucket["instagram_organic"]["lead_to_close_pct"] == round(1 / 2 * 100, 1)


def test_aggregate_by_channel_merges_multiple_combos_into_same_bucket():
    resolver = build_resolver(ROWS)
    combos = [
        _combo(sf="ig", mf="paid", flags_list=[stage_flags_for_row(_journey(sale_id="s-1"))]),
        _combo(sl="ig", ml="paid", flags_list=[stage_flags_for_row(_journey())]),
    ]
    result = aggregate_by_channel(combos, resolver)
    bucket = {row["channel"]: row for row in result}
    assert bucket["meta_paid"]["leads"] == 2
    assert bucket["meta_paid"]["closed"] == 1


def test_aggregate_by_channel_ordered_by_leads_desc():
    resolver = build_resolver(ROWS)
    combos = [
        _combo(sf="ig", flags_list=[stage_flags_for_row(_journey())]),
        _combo(
            sf="ig", mf="paid",
            flags_list=[stage_flags_for_row(_journey()) for _ in range(5)],
        ),
    ]
    result = aggregate_by_channel(combos, resolver)
    assert result[0]["channel"] == "meta_paid"
    assert result[0]["leads"] == 5
    assert result[1]["channel"] == "instagram_organic"


def test_aggregate_by_channel_no_leads_zero_percent_not_none():
    resolver = build_resolver(ROWS)
    combos = [_combo(sf="ig", flags_list=[])]
    result = aggregate_by_channel(combos, resolver)
    # A bucket with zero leads (degenerate — shouldn't normally happen since
    # combos come from GROUP BY on real rows) still returns 0.0, not a crash.
    if result:
        assert result[0]["lead_to_close_pct"] == 0.0
