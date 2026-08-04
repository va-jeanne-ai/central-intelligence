"""Pure unit tests for the GET /email/campaigns helpers (routes/email.py).

No DB harness exists for this route (raw-SQL, session-backed), so this covers
the two pieces that can be factored out and exercised without a database:
date-param parsing and the sort_by whitelist fallback. Mirrors the no-DB
style of test_channel_breakdown.py / test_leads_channel.py — import the
module under test directly, no app/session/HTTP fixtures.

Perf rework (2026-08-05): the summary/tier-threshold/top-5/pagination logic
that used to live in the pure ``_summarize_campaigns`` helper moved into SQL
(COUNT/SUM/AVG/percentile_cont/ORDER BY+LIMIT/OFFSET, mirroring
social.py/funnels.py) — there's no longer a Python aggregation step to unit
test in isolation. ``_summarize_campaigns`` and its 6 tests
(test_summarize_empty_list_returns_all_zero,
test_summarize_totals_sum_across_rows,
test_summarize_avg_rates_are_simple_mean_of_present_values,
test_summarize_avg_rate_rounds_to_two_decimals,
test_summarize_null_rates_excluded_from_average_not_treated_as_zero,
test_summarize_all_null_rates_yields_zero_average_not_error) are deleted
rather than kept as dead-code coverage; the equivalent semantics (simple
mean over non-null rates, zero-safe on an empty/all-null filtered set) are
now exercised by the manual SQL-vs-SQL equivalence check documented in
.tmp/email-perf-report.md, not a unit test — there is no DB fixture in this
suite to assert against directly.
"""
import pytest
from fastapi import HTTPException

from app.routes.email import (
    _CAMPAIGNS_SORTABLE_COLUMNS,
    _parse_campaigns_date_param,
    _resolve_campaigns_sort_by,
)


# ---------------------------------------------------------------------------
# _parse_campaigns_date_param
# ---------------------------------------------------------------------------


def test_parse_date_param_valid_iso_date():
    from datetime import date

    result = _parse_campaigns_date_param("2026-07-01", param_name="sent_from")
    assert result == date(2026, 7, 1)


def test_parse_date_param_none_passthrough():
    assert _parse_campaigns_date_param(None, param_name="sent_from") is None


def test_parse_date_param_empty_string_passthrough():
    # Falsy-but-not-None input (e.g. an empty query param) also passes
    # through as None rather than attempting to parse "".
    assert _parse_campaigns_date_param("", param_name="sent_to") is None


def test_parse_date_param_malformed_raises_422():
    with pytest.raises(HTTPException) as exc_info:
        _parse_campaigns_date_param("not-a-date", param_name="sent_from")
    assert exc_info.value.status_code == 422
    assert "sent_from" in exc_info.value.detail
    assert "not-a-date" in exc_info.value.detail


def test_parse_date_param_wrong_format_raises_422():
    # US-style date, not ISO — should fail the same way as garbage input.
    with pytest.raises(HTTPException) as exc_info:
        _parse_campaigns_date_param("07/01/2026", param_name="sent_to")
    assert exc_info.value.status_code == 422


# ---------------------------------------------------------------------------
# _resolve_campaigns_sort_by
# ---------------------------------------------------------------------------


def test_resolve_sort_by_valid_column_passes_through():
    for column in _CAMPAIGNS_SORTABLE_COLUMNS:
        assert _resolve_campaigns_sort_by(column) == column


def test_resolve_sort_by_invalid_column_falls_back_to_default():
    assert _resolve_campaigns_sort_by("nonexistent_column") == "sent_at"


def test_resolve_sort_by_sql_injection_attempt_falls_back_to_default():
    # The whitelist is the injection guard — anything not in it, however
    # crafted, collapses to the safe default rather than reaching SQL text.
    assert _resolve_campaigns_sort_by("id; DROP TABLE email_campaigns;--") == "sent_at"


def test_resolve_sort_by_empty_string_falls_back_to_default():
    assert _resolve_campaigns_sort_by("") == "sent_at"
