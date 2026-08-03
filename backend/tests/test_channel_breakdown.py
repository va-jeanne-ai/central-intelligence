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
