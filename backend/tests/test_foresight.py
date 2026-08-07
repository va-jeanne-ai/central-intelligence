"""Tests for the pure Foresight P1 statistics engine (app.services.foresight).
No-DB style — mirrors test_funnel_stats.py / test_attribution_resolver.py.

Covers the acceptance numbers from docs/superpowers/plans/
2026-08-06-foresight-layer-prototype.md's "P1 validation results" table:
wilson_interval on the exact cohort counts must reproduce the stated
rate/interval, verdict must classify each of the three branches, and
confidence tiering must split High/Medium correctly.
"""
from __future__ import annotations

import math

import pytest

from app.services.foresight import (
    CANDIDATES,
    Interval,
    build_card,
    discovery_hold_reason,
    lift_text,
    mean_interval,
    verdict,
    wilson_interval,
)

# --- wilson_interval: known values from the validation table -------------


@pytest.mark.parametrize(
    "successes, n, exp_rate, exp_low, exp_high",
    [
        (499, 5347, 9.3, 8.6, 10.1),   # watched_live
        (104, 1590, 6.5, 5.4, 7.9),    # replay-only
        (52, 4656, 1.12, 0.85, 1.46),  # ig_dm (plan states 1.12% [0.85-1.46])
        (83, 12933, 0.6, 0.5, 0.8),    # all-lead baseline
        (4, 3466, 0.1, 0.0, 0.3),      # meta_paid
        (23, 188, 12.2, 8.3, 17.7),    # discovery baseline
        (21, 88, 23.9, 16.2, 33.7),    # Life Circumstances
    ],
)
def test_wilson_interval_matches_validation_table(successes, n, exp_rate, exp_low, exp_high):
    iv = wilson_interval(successes, n)
    assert iv.rate == pytest.approx(exp_rate, abs=0.05)
    assert iv.low == pytest.approx(exp_low, abs=0.05)
    assert iv.high == pytest.approx(exp_high, abs=0.05)


def test_wilson_interval_zero_n_returns_zeros():
    iv = wilson_interval(0, 0)
    assert iv == Interval(0.0, 0.0, 0.0)


def test_wilson_interval_never_exceeds_0_100_percent():
    # Extreme rate, small n — interval must stay clamped to [0, 100].
    iv = wilson_interval(1, 1)
    assert 0.0 <= iv.low <= iv.high <= 100.0


def test_wilson_interval_rate_matches_raw_proportion():
    iv = wilson_interval(10, 40)
    assert iv.rate == pytest.approx(25.0)


# --- mean_interval ----------------------------------------------------


def test_mean_interval_known_values():
    # 649 campaigns, mean 26.1, implied sd ~14.3 -> half-width ~1.1
    iv = mean_interval(mean=26.1, sd=14.3, n=649)
    assert iv.rate == pytest.approx(26.1)
    assert iv.low == pytest.approx(26.1 - 1.1, abs=0.05)
    assert iv.high == pytest.approx(26.1 + 1.1, abs=0.05)


def test_mean_interval_other_campaigns():
    # 1,779 campaigns, mean 22.7, implied sd ~15.06 -> half-width ~0.7
    iv = mean_interval(mean=22.7, sd=15.06, n=1779)
    assert iv.low == pytest.approx(22.7 - 0.7, abs=0.05)
    assert iv.high == pytest.approx(22.7 + 0.7, abs=0.05)


def test_mean_interval_n_le_1_returns_degenerate_interval():
    # No variance estimate possible from a single observation — never
    # fabricate a width.
    iv = mean_interval(mean=50.0, sd=0.0, n=1)
    assert iv == Interval(50.0, 50.0, 50.0)
    iv0 = mean_interval(mean=50.0, sd=0.0, n=0)
    assert iv0 == Interval(50.0, 50.0, 50.0)


def test_mean_interval_wider_n_yields_narrower_interval():
    small = mean_interval(mean=50.0, sd=10.0, n=10)
    large = mean_interval(mean=50.0, sd=10.0, n=1000)
    assert large.width < small.width


# --- verdict: three branches -------------------------------------------


def test_verdict_published_lift_when_variant_clears_baseline_above():
    baseline = Interval(2.0, 1.5, 2.5)
    variant = Interval(5.0, 4.0, 6.0)  # variant.low(4.0) > baseline.high(2.5)
    result = verdict(baseline, variant)
    assert result.verdict == "published_lift"
    assert result.confidence in ("High", "Medium")
    assert result.hold_reason is None


def test_verdict_published_warning_when_variant_clears_baseline_below():
    baseline = Interval(5.0, 4.0, 6.0)
    variant = Interval(1.0, 0.5, 1.5)  # variant.high(1.5) < baseline.low(4.0)
    result = verdict(baseline, variant)
    assert result.verdict == "published_warning"
    assert result.confidence in ("High", "Medium")


def test_verdict_gated_when_intervals_overlap():
    baseline = Interval(10.0, 8.0, 12.0)
    variant = Interval(11.0, 9.0, 13.0)  # overlaps baseline
    result = verdict(baseline, variant, hold_reason_fn=lambda: "held because overlap")
    assert result.verdict == "gated"
    assert result.confidence is None
    assert result.hold_reason == "held because overlap"


def test_verdict_gated_without_hold_reason_fn_is_none():
    baseline = Interval(10.0, 8.0, 12.0)
    variant = Interval(11.0, 9.0, 13.0)
    result = verdict(baseline, variant)
    assert result.hold_reason is None


# --- confidence tiers: gap vs narrower-interval-width -------------------


def test_confidence_high_when_gap_exceeds_narrower_width():
    # baseline width=1.0, variant width=1.0, gap(variant.low-baseline.high)=5.0
    baseline = Interval(2.0, 1.5, 2.5)
    variant = Interval(10.0, 7.5, 8.5)  # gap = 7.5 - 2.5 = 5.0 > width 1.0
    result = verdict(baseline, variant)
    assert result.verdict == "published_lift"
    assert result.confidence == "High"


def test_confidence_medium_when_gap_does_not_exceed_narrower_width():
    # narrow gap relative to interval widths.
    baseline = Interval(2.0, 1.0, 3.0)  # width 2.0
    variant = Interval(4.0, 3.2, 4.8)  # width 1.6, gap = 3.2 - 3.0 = 0.2 <= 1.6
    result = verdict(baseline, variant)
    assert result.verdict == "published_lift"
    assert result.confidence == "Medium"


def test_confidence_tiers_apply_symmetrically_to_warning_cards():
    baseline = Interval(10.0, 8.0, 12.0)  # width 4.0
    variant = Interval(1.0, 0.1, 0.5)  # width 0.4, gap = 8.0 - 0.5 = 7.5 > 0.4
    result = verdict(baseline, variant)
    assert result.verdict == "published_warning"
    assert result.confidence == "High"


# --- lift_text ------------------------------------------------------------


def test_lift_text_positive_lift():
    baseline = Interval(2.0, 1.5, 2.5)
    variant = Interval(4.0, 3.5, 4.5)
    text = lift_text(baseline, variant)
    assert text == "+2.0pp · 2.0×"


def test_lift_text_negative_lift():
    baseline = Interval(5.0, 4.0, 6.0)
    variant = Interval(1.0, 0.5, 1.5)
    text = lift_text(baseline, variant)
    assert text.startswith("-4.0pp")


def test_lift_text_handles_zero_baseline_rate_without_crashing():
    baseline = Interval(0.0, 0.0, 0.5)
    variant = Interval(3.0, 2.0, 4.0)
    text = lift_text(baseline, variant)
    assert "pp" in text
    assert "—" in text  # ratio undefined (division by zero baseline)


# --- Interval.fmt -----------------------------------------------------


def test_interval_fmt_format():
    iv = Interval(9.3, 8.6, 10.1)
    assert iv.fmt() == "9.3% [8.6–10.1]"


# --- build_card: card assembly from declarative definitions -------------


def test_build_card_published_lift_shape():
    candidate = CANDIDATES["live_watch"]
    baseline = wilson_interval(104, 1590)
    variant = wilson_interval(499, 5347)
    card = build_card(candidate, baseline, variant)

    assert card["id"] == "live_watch"
    assert card["status"] == "published_lift"
    assert card["confidence"] in ("High", "Medium")
    assert card["hold_reason"] is None
    assert card["title"] == candidate.title
    assert card["insight_text"] == candidate.insight_text
    assert card["action_text"] == candidate.action_text
    assert card["baseline_rate"] == pytest.approx(baseline.rate)
    assert card["variant_rate"] == pytest.approx(variant.rate)
    assert "pp" in card["lift_text"]


def test_build_card_gated_carries_hold_reason():
    candidate = CANDIDATES["discovery_families"]
    baseline = wilson_interval(23, 188)
    top = wilson_interval(21, 88)

    def reason():
        return discovery_hold_reason(
            n=188, baseline=baseline, top_family="Life Circumstances", top=top
        )

    card = build_card(candidate, baseline, top, hold_reason_fn=reason)
    assert card["status"] == "gated"
    assert card["confidence"] is None
    assert card["hold_reason"] is not None
    assert "188" in card["hold_reason"]
    assert "Life Circumstances" in card["hold_reason"]


def test_build_card_warning_status_for_meta_paid_shape():
    candidate = CANDIDATES["meta_paid_close"]
    baseline = wilson_interval(83, 12933)
    variant = wilson_interval(4, 3466)
    card = build_card(candidate, baseline, variant)
    assert card["status"] == "published_warning"
    assert card["department"] == "marketing"


def test_all_candidate_ids_present():
    expected = {
        "live_watch", "ig_dm_channel", "meta_paid_close",
        "email_value", "discovery_families",
    }
    assert set(CANDIDATES.keys()) == expected


def test_discovery_hold_reason_format():
    baseline = wilson_interval(23, 188)
    top = wilson_interval(21, 88)
    reason = discovery_hold_reason(n=188, baseline=baseline, top_family="Life Circumstances", top=top)
    assert reason.startswith("At n=188 discovery calls")
    assert "Life Circumstances" in reason
    assert "nightly" in reason
