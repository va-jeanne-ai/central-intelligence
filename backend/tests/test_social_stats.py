"""Tests for the pure social-page rollup helpers (app.repositories.social_stats).
Mirrors test_offer_stats.py / test_funnel_stats.py style: plain dict fakes, no DB.

Contract under test — reproducing Greg's own tracking page semantics
(central-intelligence-greg/index.html, view-mkt-social — deliverable 1):
- filter_posts: inclusive date-range + type filter (REELS matches is_reel;
  other types match media_type case-insensitively).
- build_summary_stats: reel-only Watch Time/Views; all-post sums for
  Reach/Likes/Saves; counts for Posts in Range/Reels/Carousels.
- build_keyword_totals: per-keyword + total lead counts, scoped to only the
  posts present in the filtered set (matches the filter-bar-reactive stat
  cards on Greg's page).
- attach_post_lead_counts: merges wgr_post_comment_leads onto posts by
  ig_media_id; posts with no match get an empty dict / 0 total.
- sort_posts: nulls-always-last sort by any sortable column, both directions.
- build_leads_by_day: buckets comment events by day (UTC), scoped by the
  same date range, keyword-generic (never hardcodes keyword names).
- paginate_posts: pre-slice total (not page length) + correct page
  boundaries, matching the frontend Pagination component's contract.
"""

from datetime import date, datetime, timezone

import pytest
from fastapi import HTTPException

from app.repositories.social_stats import (
    attach_post_lead_counts,
    build_keyword_totals,
    build_leads_by_day,
    build_summary_stats,
    filter_posts,
    paginate_posts,
    sort_posts,
)
from app.routes.social import _SORT_COLUMNS, _validate_sort_col


def _post(
    ig_media_id="m1", posted_at=None, is_reel=False, media_type="IMAGE",
    likes_count=10, comments_count=2, saves_count=1, shares_count=0,
    reach=100, views=None, avg_watch_time_sec=None, engagement_rate=1.5,
):
    return {
        "id": ig_media_id, "ig_media_id": ig_media_id, "posted_at": posted_at,
        "is_reel": is_reel, "media_type": media_type,
        "likes_count": likes_count, "comments_count": comments_count,
        "saves_count": saves_count, "shares_count": shares_count,
        "reach": reach, "views": views, "avg_watch_time_sec": avg_watch_time_sec,
        "engagement_rate": engagement_rate, "permalink": None, "caption": None,
    }


# --- filter_posts ---


def test_filter_posts_inclusive_date_range():
    posts = [
        _post("a", posted_at=datetime(2026, 1, 1, tzinfo=timezone.utc)),
        _post("b", posted_at=datetime(2026, 1, 15, tzinfo=timezone.utc)),
        _post("c", posted_at=datetime(2026, 2, 1, tzinfo=timezone.utc)),
    ]
    out = filter_posts(posts, date_from=date(2026, 1, 1), date_to=date(2026, 1, 31))
    assert {p["ig_media_id"] for p in out} == {"a", "b"}


def test_filter_posts_reels_type_matches_is_reel():
    posts = [_post("a", is_reel=True), _post("b", is_reel=False)]
    out = filter_posts(posts, media_type="REELS")
    assert [p["ig_media_id"] for p in out] == ["a"]


def test_filter_posts_media_type_case_insensitive():
    posts = [_post("a", media_type="CAROUSEL_ALBUM"), _post("b", media_type="IMAGE")]
    out = filter_posts(posts, media_type="carousel_album")
    assert [p["ig_media_id"] for p in out] == ["a"]


def test_filter_posts_no_filters_returns_all():
    posts = [_post("a"), _post("b")]
    assert len(filter_posts(posts)) == 2


def test_filter_posts_excludes_null_dates_when_range_given():
    posts = [_post("a", posted_at=None), _post("b", posted_at=datetime(2026, 1, 1, tzinfo=timezone.utc))]
    out = filter_posts(posts, date_from=date(2026, 1, 1))
    assert [p["ig_media_id"] for p in out] == ["b"]


# --- build_summary_stats ---


def test_build_summary_stats_counts_and_sums():
    posts = [
        _post("a", is_reel=True, media_type="VIDEO", views=1000, avg_watch_time_sec=20, reach=50, likes_count=5, saves_count=2),
        _post("b", is_reel=False, media_type="CAROUSEL_ALBUM", reach=30, likes_count=3, saves_count=1),
        _post("c", is_reel=False, media_type="IMAGE", reach=20, likes_count=2, saves_count=0),
    ]
    stats = build_summary_stats(posts)
    assert stats["posts_in_range"] == 3
    assert stats["reels_count"] == 1
    assert stats["carousels_count"] == 1
    assert stats["total_views"] == 1000
    assert stats["total_watch_time_sec"] == 20
    assert stats["total_reach"] == 100
    assert stats["total_likes"] == 10
    assert stats["total_saves"] == 3


def test_build_summary_stats_reel_only_fields_ignore_non_reels():
    posts = [_post("a", is_reel=False, views=999, avg_watch_time_sec=999)]
    stats = build_summary_stats(posts)
    assert stats["total_views"] == 0
    assert stats["total_watch_time_sec"] == 0


def test_build_summary_stats_empty_list():
    stats = build_summary_stats([])
    assert stats["posts_in_range"] == 0
    assert stats["total_reach"] == 0


# --- build_keyword_totals ---


def test_build_keyword_totals_sums_per_keyword_and_total():
    posts = [_post("a"), _post("b")]
    lead_rows = [
        {"ig_media_id": "a", "keyword_counts": {"info": 3, "agent": 1}, "total_leads": 4},
        {"ig_media_id": "b", "keyword_counts": {"info": 2}, "total_leads": 2},
    ]
    totals = build_keyword_totals(posts, lead_rows)
    assert totals["per_keyword"] == {"info": 5, "agent": 1}
    assert totals["total_leads"] == 6
    assert totals["keywords"] == ["agent", "info"]


def test_build_keyword_totals_scoped_to_filtered_posts_only():
    posts = [_post("a")]  # "b" filtered out upstream
    lead_rows = [
        {"ig_media_id": "a", "keyword_counts": {"info": 1}, "total_leads": 1},
        {"ig_media_id": "b", "keyword_counts": {"info": 99}, "total_leads": 99},
    ]
    totals = build_keyword_totals(posts, lead_rows)
    assert totals["total_leads"] == 1
    assert totals["per_keyword"] == {"info": 1}


def test_build_keyword_totals_no_leads_is_zero():
    totals = build_keyword_totals([_post("a")], [])
    assert totals["total_leads"] == 0
    assert totals["per_keyword"] == {}
    assert totals["keywords"] == []


# --- attach_post_lead_counts ---


def test_attach_post_lead_counts_merges_by_media_id():
    posts = [_post("a"), _post("b")]
    lead_rows = [{"ig_media_id": "a", "keyword_counts": {"info": 3}, "total_leads": 3}]
    out = attach_post_lead_counts(posts, lead_rows)
    by_id = {p["ig_media_id"]: p for p in out}
    assert by_id["a"]["lead_counts"] == {"info": 3}
    assert by_id["a"]["lead_total"] == 3
    assert by_id["b"]["lead_counts"] == {}
    assert by_id["b"]["lead_total"] == 0


# --- sort_posts ---


def test_sort_posts_desc_by_likes():
    posts = [_post("a", likes_count=5), _post("b", likes_count=20), _post("c", likes_count=10)]
    out = sort_posts(posts, sort_col="likes_count", sort_dir="desc")
    assert [p["ig_media_id"] for p in out] == ["b", "c", "a"]


def test_sort_posts_asc_by_likes():
    posts = [_post("a", likes_count=5), _post("b", likes_count=20)]
    out = sort_posts(posts, sort_col="likes_count", sort_dir="asc")
    assert [p["ig_media_id"] for p in out] == ["a", "b"]


def test_sort_posts_nulls_always_last_regardless_of_direction():
    posts = [_post("a", likes_count=None), _post("b", likes_count=5)]
    desc = sort_posts(posts, sort_col="likes_count", sort_dir="desc")
    asc = sort_posts(posts, sort_col="likes_count", sort_dir="asc")
    assert [p["ig_media_id"] for p in desc] == ["b", "a"]
    assert [p["ig_media_id"] for p in asc] == ["b", "a"]


def test_sort_posts_timestamp_alias_sorts_by_posted_at():
    posts = [
        _post("a", posted_at=datetime(2026, 1, 1, tzinfo=timezone.utc)),
        _post("b", posted_at=datetime(2026, 2, 1, tzinfo=timezone.utc)),
    ]
    out = sort_posts(posts, sort_col="timestamp", sort_dir="desc")
    assert [p["ig_media_id"] for p in out] == ["b", "a"]


# --- build_leads_by_day ---


def test_build_leads_by_day_buckets_by_date_and_keyword():
    events = [
        {"occurred_at": datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc), "keyword": "info"},
        {"occurred_at": datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc), "keyword": "info"},
        {"occurred_at": datetime(2026, 1, 1, 14, 0, tzinfo=timezone.utc), "keyword": "agent"},
        {"occurred_at": datetime(2026, 1, 2, 9, 0, tzinfo=timezone.utc), "keyword": "info"},
    ]
    result = build_leads_by_day(events)
    days = {d["day"]: d for d in result["days"]}
    assert days["2026-01-01"]["info"] == 2
    assert days["2026-01-01"]["agent"] == 1
    assert days["2026-01-01"]["total"] == 3
    assert days["2026-01-02"]["total"] == 1
    assert result["keywords"] == ["agent", "info"]


def test_build_leads_by_day_sorted_most_recent_first():
    events = [
        {"occurred_at": datetime(2026, 1, 1, tzinfo=timezone.utc), "keyword": "info"},
        {"occurred_at": datetime(2026, 1, 3, tzinfo=timezone.utc), "keyword": "info"},
    ]
    result = build_leads_by_day(events)
    assert [d["day"] for d in result["days"]] == ["2026-01-03", "2026-01-01"]


def test_build_leads_by_day_respects_date_range():
    events = [
        {"occurred_at": datetime(2026, 1, 1, tzinfo=timezone.utc), "keyword": "info"},
        {"occurred_at": datetime(2026, 1, 15, tzinfo=timezone.utc), "keyword": "info"},
    ]
    result = build_leads_by_day(events, date_from=date(2026, 1, 10))
    assert len(result["days"]) == 1
    assert result["days"][0]["day"] == "2026-01-15"


def test_build_leads_by_day_ignores_events_with_no_keyword():
    events = [{"occurred_at": datetime(2026, 1, 1, tzinfo=timezone.utc), "keyword": None}]
    result = build_leads_by_day(events)
    assert result["days"] == []


def test_build_leads_by_day_empty_events():
    result = build_leads_by_day([])
    assert result["days"] == []
    assert result["keywords"] == []


# --- paginate_posts ---


def test_paginate_posts_returns_pre_slice_total_not_page_length():
    posts = [_post(str(i)) for i in range(25)]
    page, total = paginate_posts(posts, limit=10, offset=0)
    assert total == 25
    assert len(page) == 10


def test_paginate_posts_first_page():
    posts = [_post(str(i)) for i in range(25)]
    page, total = paginate_posts(posts, limit=10, offset=0)
    assert [p["ig_media_id"] for p in page] == [str(i) for i in range(10)]
    assert total == 25


def test_paginate_posts_middle_page():
    posts = [_post(str(i)) for i in range(25)]
    page, _ = paginate_posts(posts, limit=10, offset=10)
    assert [p["ig_media_id"] for p in page] == [str(i) for i in range(10, 20)]


def test_paginate_posts_last_partial_page():
    posts = [_post(str(i)) for i in range(25)]
    page, total = paginate_posts(posts, limit=10, offset=20)
    assert [p["ig_media_id"] for p in page] == [str(i) for i in range(20, 25)]
    assert len(page) == 5
    assert total == 25


def test_paginate_posts_offset_past_end_returns_empty_page_but_true_total():
    posts = [_post(str(i)) for i in range(5)]
    page, total = paginate_posts(posts, limit=10, offset=100)
    assert page == []
    assert total == 5


def test_paginate_posts_empty_input():
    page, total = paginate_posts([], limit=10, offset=0)
    assert page == []
    assert total == 0


def test_paginate_posts_exact_page_boundary():
    # 20 posts, page size 10 → two full pages, no partial third page.
    posts = [_post(str(i)) for i in range(20)]
    page1, total1 = paginate_posts(posts, limit=10, offset=0)
    page2, total2 = paginate_posts(posts, limit=10, offset=10)
    assert len(page1) == 10
    assert len(page2) == 10
    assert total1 == total2 == 20


# --- _validate_sort_col (routes/social.py) ---


def test_validate_sort_col_accepts_every_whitelisted_column():
    for column in _SORT_COLUMNS:
        assert _validate_sort_col(column) == column


def test_validate_sort_col_invalid_value_raises_422():
    with pytest.raises(HTTPException) as exc_info:
        _validate_sort_col("nonexistent_column")
    assert exc_info.value.status_code == 422
    assert "nonexistent_column" in exc_info.value.detail


def test_validate_sort_col_sql_injection_attempt_raises_422():
    # The whitelist is the injection guard — anything not in it must fail
    # loudly (422), never silently pass through to sort_posts()/SQL.
    with pytest.raises(HTTPException) as exc_info:
        _validate_sort_col("id; DROP TABLE instagram_posts;--")
    assert exc_info.value.status_code == 422


def test_validate_sort_col_empty_string_raises_422():
    with pytest.raises(HTTPException) as exc_info:
        _validate_sort_col("")
    assert exc_info.value.status_code == 422


def test_validate_sort_col_case_sensitive_rejects_mismatched_case():
    # "Timestamp" is not "timestamp" — no case-insensitive matching, matches
    # the same strictness as the rest of the whitelist.
    with pytest.raises(HTTPException) as exc_info:
        _validate_sort_col("Timestamp")
    assert exc_info.value.status_code == 422


# --- raw-SQL reality: asyncpg returns json columns as str, not dict ---------


def test_build_keyword_totals_parses_json_string_counts():
    """Raw text() SELECTs hand keyword_counts to Python as a JSON *string*
    (asyncpg doesn't decode json for untyped raw queries). The rollup must
    parse it, not silently skip the row (the bug that shipped: 0 keyword
    cards against 2,754 real rows)."""
    from app.repositories.social_stats import build_keyword_totals

    posts = [{"ig_media_id": "m1"}, {"ig_media_id": "m2"}]
    lead_rows = [
        {"ig_media_id": "m1", "keyword_counts": '{"agent": 2}', "total_leads": 2},
        {"ig_media_id": "m2", "keyword_counts": '{"info": 7, "agent": 1}', "total_leads": 8},
    ]
    out = build_keyword_totals(posts, lead_rows)
    assert out["per_keyword"] == {"agent": 3, "info": 7}
    assert out["total_leads"] == 10


def test_build_keyword_totals_tolerates_malformed_string():
    from app.repositories.social_stats import build_keyword_totals

    posts = [{"ig_media_id": "m1"}]
    lead_rows = [{"ig_media_id": "m1", "keyword_counts": "not json", "total_leads": 3}]
    out = build_keyword_totals(posts, lead_rows)
    assert out["per_keyword"] == {}
    assert out["total_leads"] == 3


def test_attach_post_lead_counts_parses_json_string_counts():
    from app.repositories.social_stats import attach_post_lead_counts

    posts = [{"ig_media_id": "m1"}]
    lead_rows = [{"ig_media_id": "m1", "keyword_counts": '{"agent": 4}', "total_leads": 4}]
    out = attach_post_lead_counts(posts, lead_rows)
    assert out[0]["lead_counts"] == {"agent": 4}
    assert out[0]["lead_total"] == 4
