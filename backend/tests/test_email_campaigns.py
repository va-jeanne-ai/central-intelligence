"""Pure unit tests for the GET /email/campaigns helpers (routes/email.py).

No DB harness exists for this route (raw-SQL, session-backed), so this covers
the three pieces that can be factored out and exercised without a database:
date-param parsing, the sort_by whitelist fallback, and the summary
aggregation over a plain list of ``EmailCampaignListRow`` instances. Mirrors
the no-DB style of test_channel_breakdown.py / test_leads_channel.py — import
the module under test directly, no app/session/HTTP fixtures.
"""
import pytest
from fastapi import HTTPException

from app.routes.email import (
    _CAMPAIGNS_SORTABLE_COLUMNS,
    _parse_campaigns_date_param,
    _resolve_campaigns_sort_by,
    _summarize_campaigns,
)
from app.schemas.email import EmailCampaignListRow


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


# ---------------------------------------------------------------------------
# _summarize_campaigns
# ---------------------------------------------------------------------------


def _row(
    *,
    recipients=0,
    opens=0,
    clicks=0,
    open_rate=None,
    click_rate=None,
    unsubs=0,
    bounces=0,
    name="Test campaign",
) -> EmailCampaignListRow:
    return EmailCampaignListRow(
        id="00000000-0000-0000-0000-000000000000",
        name=name,
        subject=None,
        campaign_type=None,
        status="sent",
        sent_at=None,
        audience_name=None,
        recipients_count=recipients,
        open_count=opens,
        click_count=clicks,
        unsubscribe_count=unsubs,
        bounce_count=bounces,
        open_rate=open_rate,
        click_rate=click_rate,
        archive_url=None,
    )


def test_summarize_empty_list_returns_all_zero():
    summary = _summarize_campaigns([])
    assert summary.count == 0
    assert summary.total_recipients == 0
    assert summary.total_opens == 0
    assert summary.total_clicks == 0
    assert summary.avg_open_rate == 0.0
    assert summary.avg_click_rate == 0.0


def test_summarize_totals_sum_across_rows():
    rows = [
        _row(recipients=100, opens=20, clicks=5, open_rate=20.0, click_rate=5.0),
        _row(recipients=200, opens=60, clicks=10, open_rate=30.0, click_rate=5.0),
    ]
    summary = _summarize_campaigns(rows)
    assert summary.count == 2
    assert summary.total_recipients == 300
    assert summary.total_opens == 80
    assert summary.total_clicks == 15


def test_summarize_avg_rates_are_simple_mean_of_present_values():
    rows = [
        _row(open_rate=20.0, click_rate=2.0),
        _row(open_rate=30.0, click_rate=4.0),
    ]
    summary = _summarize_campaigns(rows)
    assert summary.avg_open_rate == 25.0
    assert summary.avg_click_rate == 3.0


def test_summarize_avg_rate_rounds_to_two_decimals():
    rows = [_row(open_rate=10.0), _row(open_rate=11.0), _row(open_rate=11.0)]
    summary = _summarize_campaigns(rows)
    # (10 + 11 + 11) / 3 = 10.666... -> rounds to 10.67
    assert summary.avg_open_rate == 10.67


def test_summarize_null_rates_excluded_from_average_not_treated_as_zero():
    # A campaign with no rate recorded shouldn't drag the average down to 0 —
    # it should simply not count toward the denominator.
    rows = [_row(open_rate=None), _row(open_rate=40.0)]
    summary = _summarize_campaigns(rows)
    assert summary.avg_open_rate == 40.0
    assert summary.count == 2  # still counted toward `count`/totals


def test_summarize_all_null_rates_yields_zero_average_not_error():
    rows = [_row(open_rate=None), _row(open_rate=None)]
    summary = _summarize_campaigns(rows)
    assert summary.avg_open_rate == 0.0
    assert summary.avg_click_rate == 0.0
    assert summary.count == 2
