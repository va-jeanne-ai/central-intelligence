"""Pure unit tests for ``_channel_buckets_to_breakdown`` (sales_stats.py).

No DB access exists for this path (compute_lead_stats is DB-only), so this
covers the one piece that can be factored out and fed fake ``summarize_channels``
bucket lists — percentage math, the transitional `source == channel` overload,
and that counts always sum to the input total.
"""
from app.repositories.sales_stats import _channel_buckets_to_breakdown


def test_percentage_computed_from_bucket_total():
    buckets = [
        {"channel": "meta_paid", "platform": "ig", "reportable": True, "count": 3},
        {"channel": "No attribution", "platform": None, "reportable": False, "count": 1},
    ]
    out = _channel_buckets_to_breakdown(buckets)
    assert out[0]["percentage"] == 75.0
    assert out[1]["percentage"] == 25.0


def test_source_key_mirrors_channel_transitionally():
    buckets = [{"channel": "email", "platform": None, "reportable": True, "count": 5}]
    out = _channel_buckets_to_breakdown(buckets)
    assert out[0]["source"] == out[0]["channel"] == "email"


def test_all_expected_keys_present():
    buckets = [{"channel": "manual_entry", "platform": None, "reportable": False, "count": 2}]
    out = _channel_buckets_to_breakdown(buckets)
    assert set(out[0]) == {"source", "channel", "platform", "reportable", "count", "percentage"}


def test_counts_sum_to_input_total():
    buckets = [
        {"channel": "meta_paid", "platform": "ig", "reportable": True, "count": 7},
        {"channel": "Non-marketing", "platform": None, "reportable": False, "count": 2},
        {"channel": "unmapped:tiktok/bio", "platform": None, "reportable": True, "count": 4},
    ]
    out = _channel_buckets_to_breakdown(buckets)
    assert sum(item["count"] for item in out) == 13


def test_empty_buckets_returns_empty_list_no_div_by_zero():
    assert _channel_buckets_to_breakdown([]) == []


def test_reportable_and_platform_default_when_missing():
    # summarize_channels always includes these keys today, but the mapper
    # should not crash if a caller passes a sparser dict.
    buckets = [{"channel": "x", "count": 1}]
    out = _channel_buckets_to_breakdown(buckets)
    assert out[0]["platform"] is None
    assert out[0]["reportable"] is True


def test_sorted_count_desc_regardless_of_input_order():
    # summarize_channels builds buckets from a dict/hash-agg with no
    # guaranteed iteration order — the breakdown must always come back
    # sorted largest-first so /leads/stats + /sales/summary responses (and
    # the frontend donut/legend order) never shuffle between requests.
    buckets = [
        {"channel": "small", "platform": None, "reportable": True, "count": 2},
        {"channel": "large", "platform": None, "reportable": True, "count": 10},
        {"channel": "medium", "platform": None, "reportable": True, "count": 5},
    ]
    out = _channel_buckets_to_breakdown(buckets)
    assert [item["channel"] for item in out] == ["large", "medium", "small"]
    assert [item["count"] for item in out] == [10, 5, 2]


def test_sorted_count_desc_tie_broken_by_channel_name():
    # Equal counts must resolve deterministically by channel name (ascending)
    # rather than falling back to whatever order the input happened to be in.
    buckets = [
        {"channel": "zeta", "platform": None, "reportable": True, "count": 4},
        {"channel": "alpha", "platform": None, "reportable": True, "count": 4},
        {"channel": "mu", "platform": None, "reportable": True, "count": 4},
    ]
    out = _channel_buckets_to_breakdown(buckets)
    assert [item["channel"] for item in out] == ["alpha", "mu", "zeta"]
