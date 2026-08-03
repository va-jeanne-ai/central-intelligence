"""Pure unit tests for ``_revenue_buckets_to_breakdown`` (sales_stats.py).

Mirrors ``test_channel_breakdown.py``'s style for the parallel lead-count
breakdown: no DB access, fake bucket lists in, deterministic breakdown out.
Covers bucket merge, revenue sums preserved (nothing dropped), ordering, and
the missing-lead -> "No attribution" contract (via the caller,
``compute_revenue_by_channel``, folding an unmatched sale's all-null combo
into that same bucket before this function ever sees it).
"""
from app.repositories.sales_stats import _revenue_buckets_to_breakdown


def test_percentage_computed_from_bucket_revenue_total():
    buckets = [
        {"channel": "meta_paid", "platform": "ig", "reportable": True, "revenue": 7500.0, "sales_count": 3},
        {"channel": "No attribution", "platform": None, "reportable": False, "revenue": 2500.0, "sales_count": 1},
    ]
    out = _revenue_buckets_to_breakdown(buckets)
    assert out[0]["revenue_percentage"] == 75.0
    assert out[1]["revenue_percentage"] == 25.0


def test_all_expected_keys_present():
    buckets = [{"channel": "manual_entry", "platform": None, "reportable": False, "revenue": 1000.0, "sales_count": 2}]
    out = _revenue_buckets_to_breakdown(buckets)
    assert set(out[0]) == {"channel", "platform", "reportable", "sales_count", "revenue", "revenue_percentage"}


def test_revenue_sums_preserved_nothing_dropped():
    buckets = [
        {"channel": "meta_paid", "platform": "ig", "reportable": True, "revenue": 12345.67, "sales_count": 7},
        {"channel": "Non-marketing", "platform": None, "reportable": False, "revenue": 999.99, "sales_count": 2},
        {"channel": "unmapped:tiktok/bio", "platform": None, "reportable": True, "revenue": 4000.34, "sales_count": 4},
    ]
    out = _revenue_buckets_to_breakdown(buckets)
    assert round(sum(item["revenue"] for item in out), 2) == round(12345.67 + 999.99 + 4000.34, 2)
    assert sum(item["sales_count"] for item in out) == 13


def test_empty_buckets_returns_empty_list_no_div_by_zero():
    assert _revenue_buckets_to_breakdown([]) == []


def test_reportable_and_platform_default_when_missing():
    buckets = [{"channel": "x", "revenue": 100.0}]
    out = _revenue_buckets_to_breakdown(buckets)
    assert out[0]["platform"] is None
    assert out[0]["reportable"] is True
    assert out[0]["sales_count"] == 0


def test_sorted_revenue_desc_regardless_of_input_order():
    buckets = [
        {"channel": "small", "platform": None, "reportable": True, "revenue": 200.0, "sales_count": 1},
        {"channel": "large", "platform": None, "reportable": True, "revenue": 10000.0, "sales_count": 5},
        {"channel": "medium", "platform": None, "reportable": True, "revenue": 5000.0, "sales_count": 2},
    ]
    out = _revenue_buckets_to_breakdown(buckets)
    assert [item["channel"] for item in out] == ["large", "medium", "small"]
    assert [item["revenue"] for item in out] == [10000.0, 5000.0, 200.0]


def test_sorted_revenue_desc_tie_broken_by_channel_name():
    buckets = [
        {"channel": "zeta", "platform": None, "reportable": True, "revenue": 500.0, "sales_count": 1},
        {"channel": "alpha", "platform": None, "reportable": True, "revenue": 500.0, "sales_count": 1},
        {"channel": "mu", "platform": None, "reportable": True, "revenue": 500.0, "sales_count": 1},
    ]
    out = _revenue_buckets_to_breakdown(buckets)
    assert [item["channel"] for item in out] == ["alpha", "mu", "zeta"]


def test_bucket_merge_via_mapping_matches_bucket_channel_combos_labels():
    """Integration-lite: exercise the real bucket_channel_combos + the mapping
    re-aggregation pattern compute_revenue_by_channel uses, with fake combos
    standing in for SQL rows. Verifies revenue merges correctly per final
    bucket label (including the "No attribution" all-null case) without a DB.
    """
    from types import SimpleNamespace

    from app.services.attribution import bucket_channel_combos, build_resolver

    taxonomy_rows = [
        SimpleNamespace(
            id=1, observed_source="ig", observed_medium="paid", observed_content=None,
            canonical_channel="meta_paid", platform="ig", include_in_channel_reporting=True,
        ),
    ]
    resolver = build_resolver(taxonomy_rows)

    # (sf, mf, cf, sl, ml, cl, count) — count doubles as a stand-in for
    # sales_count in this combo-shape test.
    combos = [
        ("ig", "paid", None, None, None, None, 2),  # -> meta_paid
        (None, None, None, None, None, None, 1),     # -> No attribution (missing lead)
    ]
    # revenue per combo, matched positionally to `combos` above
    revenues = {
        ("ig", "paid", None, None, None, None): 6000.0,
        (None, None, None, None, None, None): 1500.0,
    }

    mapping, _buckets = bucket_channel_combos(combos, resolver)

    revenue_buckets: dict[str, dict] = {}
    for sf, mf, cf, sl, ml, cl, count in combos:
        key = (sf, mf, cf, sl, ml, cl)
        label = mapping[key]
        revenue = revenues[key]
        if label in revenue_buckets:
            revenue_buckets[label]["revenue"] += revenue
            revenue_buckets[label]["sales_count"] += count
        else:
            revenue_buckets[label] = {"channel": label, "revenue": revenue, "sales_count": count}

    out = _revenue_buckets_to_breakdown(list(revenue_buckets.values()))
    by_channel = {item["channel"]: item for item in out}

    assert by_channel["meta_paid"]["revenue"] == 6000.0
    assert by_channel["meta_paid"]["sales_count"] == 2
    assert by_channel["No attribution"]["revenue"] == 1500.0
    assert by_channel["No attribution"]["sales_count"] == 1
    assert round(sum(item["revenue"] for item in out), 2) == 7500.0
