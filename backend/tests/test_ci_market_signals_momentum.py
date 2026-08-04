"""Pure unit tests for `_momentum` and `_parse_datetime_param` (routes/ci.py).

No DB harness exists for these routes (async-session-backed), so this covers
the two pieces that can be factored out and exercised without a database.
Mirrors the no-DB style of test_email_campaigns.py / test_channel_breakdown.py
— import the module under test directly, no app/session/HTTP fixtures.

`_momentum` is exercised specifically against the live-data shape audited on
2026-08-03: `last_30_days` never exceeds 2 across all 1,961 `market_signals`
rows, and `last_7_days` is always 0 or 1. An earlier draft gated momentum on
`total_mentions < 3` (a field `_momentum` doesn't even take as input) and
silently returned `None` for every single row in production — these tests
exist specifically to catch that class of regression before it ships again.
"""
from datetime import date, datetime, timezone

import pytest
from fastapi import HTTPException

from app.routes.ci import _momentum, _parse_datetime_param


# ---------------------------------------------------------------------------
# _momentum
# ---------------------------------------------------------------------------


def test_momentum_zero_last_30_days_is_none():
    # No activity at all in the 30d window — genuinely nothing to compare.
    assert _momentum(last_7_days=0, last_30_days=0) is None


def test_momentum_live_data_shape_last_30_days_equals_1_no_recent():
    # The single most common non-zero row shape in production: 1 mention in
    # the last 30 days, none of it in the last 7. Must NOT be None — this is
    # exactly the case the old `total_mentions < 3` guard broke.
    result = _momentum(last_7_days=0, last_30_days=1)
    assert result is not None
    assert result < 0  # all of the activity is in the "prior" period — cooling off


def test_momentum_live_data_shape_last_30_days_equals_1_all_recent():
    # 1 mention total, and it happened in the last 7 days — accelerating.
    result = _momentum(last_7_days=1, last_30_days=1)
    assert result == 1.0


def test_momentum_live_data_shape_last_30_days_equals_2():
    # The rarest live shape (1 row in production): 2 mentions in 30d, 1 of
    # them in the last 7 — recent rate (1/7) vs prior rate (1/23), positive.
    result = _momentum(last_7_days=1, last_30_days=2)
    assert result is not None
    assert result > 0


def test_momentum_never_none_when_last_30_days_positive():
    # The regression this whole test module exists to catch: for every
    # last_30_days > 0 combination actually observed in production
    # (0 or 1 for last_7_days, 1 or 2 for last_30_days), momentum must be a
    # real float, never None.
    for last_30 in (1, 2):
        for last_7 in (0, 1):
            if last_7 > last_30:
                continue  # not a real combination (7d count can't exceed 30d count)
            assert _momentum(last_7_days=last_7, last_30_days=last_30) is not None


def test_momentum_prior_rate_zero_and_recent_rate_zero_is_none():
    # last_30_days > 0 but all of it is inside the 7d window, and last_7_days
    # is also 0 — contradictory input (30d has activity, 7d subset doesn't,
    # but prior period computes to 0 because last_30 <= last_7 can't happen
    # here); covered directly by construction: prior_mentions = max(0, 30-7).
    # With last_7_days=0 and last_30_days=0 this is the same as the first
    # test; included here for the explicit "both rates zero" branch via a
    # last_30_days that nets a zero prior with zero recent — not reachable
    # with non-negative ints other than the all-zero case, so this doubles
    # as an explicit regression pin on that branch's return value (None, not 1.0).
    assert _momentum(last_7_days=0, last_30_days=0) is None


def test_momentum_boundary_large_values_still_directional():
    # Not a live-data shape, but a sanity check that the formula still holds
    # outside the observed range (e.g. if volume grows in the future).
    # 30 mentions in the last 7 days alone, prior period had 0 — should read
    # as strongly accelerating (recent_rate > 0, prior_rate == 0 branch).
    result = _momentum(last_7_days=30, last_30_days=30)
    assert result == 1.0


def test_momentum_symmetric_cooling_case():
    # All mentions in the prior period, none recently — should be negative
    # (cooling off), the mirror image of the accelerating case above.
    result = _momentum(last_7_days=0, last_30_days=23)
    assert result is not None
    assert result < 0


# ---------------------------------------------------------------------------
# _parse_datetime_param
# ---------------------------------------------------------------------------


def test_parse_datetime_param_none_passthrough():
    assert _parse_datetime_param(None, param_name="updated_from") is None


def test_parse_datetime_param_empty_string_passthrough():
    assert _parse_datetime_param("", param_name="updated_from") is None


def test_parse_datetime_param_valid_bare_date():
    result = _parse_datetime_param("2026-07-01", param_name="updated_from")
    assert result is not None
    assert result.date() == date(2026, 7, 1)
    # Bare date with no end_of_day flag stays at midnight.
    assert result.hour == 0 and result.minute == 0 and result.second == 0


def test_parse_datetime_param_valid_full_datetime():
    result = _parse_datetime_param("2026-07-01T15:30:00", param_name="updated_from")
    assert result == datetime(2026, 7, 1, 15, 30, 0, tzinfo=timezone.utc)


def test_parse_datetime_param_bare_date_end_of_day_pushed_to_2359():
    result = _parse_datetime_param("2026-07-01", param_name="updated_to", end_of_day=True)
    assert result is not None
    assert result.hour == 23 and result.minute == 59 and result.second == 59
    assert result.microsecond == 999999


def test_parse_datetime_param_full_datetime_end_of_day_not_overridden():
    # end_of_day only pushes bare dates (len <= 10); an explicit time
    # component is respected as-is, not clobbered to 23:59:59.
    result = _parse_datetime_param(
        "2026-07-01T08:00:00", param_name="updated_to", end_of_day=True
    )
    assert result == datetime(2026, 7, 1, 8, 0, 0, tzinfo=timezone.utc)


def test_parse_datetime_param_naive_datetime_gets_utc():
    result = _parse_datetime_param("2026-07-01T00:00:00", param_name="updated_from")
    assert result is not None
    assert result.tzinfo == timezone.utc


def test_parse_datetime_param_malformed_raises_422():
    with pytest.raises(HTTPException) as exc_info:
        _parse_datetime_param("not-a-date", param_name="updated_from")
    assert exc_info.value.status_code == 422
    detail = exc_info.value.detail
    assert detail["error"]["code"] == "VALIDATION_ERROR"
    assert detail["error"]["field"] == "updated_from"
    assert "not-a-date" in detail["error"]["message"]


def test_parse_datetime_param_wrong_format_raises_422():
    with pytest.raises(HTTPException) as exc_info:
        _parse_datetime_param("07/01/2026", param_name="updated_to")
    assert exc_info.value.status_code == 422
    assert exc_info.value.detail["error"]["field"] == "updated_to"
