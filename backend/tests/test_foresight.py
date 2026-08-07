"""Tests for the pure Foresight P1 statistics engine (app.services.foresight).
No-DB style — mirrors test_funnel_stats.py / test_attribution_resolver.py.

Covers the acceptance numbers from docs/superpowers/plans/
2026-08-06-foresight-layer-prototype.md's "P1 validation results" table:
wilson_interval on the exact cohort counts must reproduce the stated
rate/interval, verdict must classify each of the three branches, and
confidence tiering must split High/Medium correctly.

Also covers the 2026-08-07 gate-integrity fixes (code review): the n-floor
guard (MIN_COHORT_N), Bonferroni-corrected z for the discovery sweep, the
hysteresis state machine, winning-family interpolation, and the generic
hold_reason fallback.
"""
from __future__ import annotations

import math

import pytest

from app.services.foresight import (
    CANDIDATES,
    DISCOVERY_SWEEP_Z,
    MIN_COHORT_N,
    REQUIRED_CLEAR_NIGHTS,
    HysteresisResult,
    Interval,
    VerdictResult,
    apply_hysteresis,
    build_card,
    discovery_family_action,
    discovery_family_title,
    discovery_hold_reason,
    lift_text,
    mean_interval,
    verdict,
    wilson_interval,
)

# A default n comfortably above MIN_COHORT_N for tests that aren't
# specifically exercising the floor.
BIG_N = 1000


def _v(baseline, variant, **kwargs):
    """Shorthand: call verdict() with big-enough n's by default so existing
    interval-shape tests don't need to restate baseline_n/variant_n."""
    kwargs.setdefault("baseline_n", BIG_N)
    kwargs.setdefault("variant_n", BIG_N)
    return verdict(baseline, variant, **kwargs)


def _card(candidate, baseline, variant, **kwargs):
    kwargs.setdefault("baseline_n", BIG_N)
    kwargs.setdefault("variant_n", BIG_N)
    return build_card(candidate, baseline, variant, **kwargs)


# --- wilson_interval: known values from the validation table -------------


@pytest.mark.parametrize(
    "successes, n, exp_rate, exp_low, exp_high",
    [
        (499, 5347, 9.3, 8.6, 10.1),   # watched_live
        (104, 1590, 6.5, 5.4, 7.9),    # replay-only
        (52, 4656, 1.12, 0.85, 1.46),  # ig_dm (plan states 1.12% [0.85-1.46])
        (83, 12933, 0.6, 0.5, 0.8),    # all-lead baseline (inclusive, pre-amendment)
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


@pytest.mark.parametrize(
    "successes, n, exp_rate, exp_low, exp_high",
    [
        (52, 4656, 1.12, 0.85, 1.46),  # ig_dm variant (z=1.96, unaffected by amendment)
        (31, 8277, 0.37, 0.26, 0.53),  # ig_dm complement baseline
        (4, 3466, 0.12, 0.04, 0.30),   # meta_paid variant
        (79, 9467, 0.83, 0.67, 1.04),  # meta_paid complement baseline
    ],
)
def test_wilson_interval_matches_complement_baseline_amendment(
    successes, n, exp_rate, exp_low, exp_high
):
    """2026-08-07 amendment: channel cards compare against the complement
    baseline (total - variant), not the inclusive all-lead baseline."""
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


def test_wilson_interval_wider_z_yields_wider_interval():
    # Bonferroni z=2.69 > standard z=1.96 -> wider interval at the same n.
    standard = wilson_interval(21, 88, z=1.96)
    bonferroni = wilson_interval(21, 88, z=DISCOVERY_SWEEP_Z)
    assert bonferroni.width > standard.width
    assert bonferroni.low < standard.low
    assert bonferroni.high > standard.high


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


def test_mean_interval_n_1_can_publish_high_but_gate_catches_it():
    # Regression guard for review finding #1: a degenerate zero-width
    # interval at n=1 must NOT sail through the gate — the n-floor in
    # verdict() rejects it before the (trivially satisfied) separation
    # test ever runs.
    baseline = mean_interval(mean=10.0, sd=5.0, n=500)
    variant = mean_interval(mean=50.0, sd=0.0, n=1)  # zero-width, n=1
    assert variant.low == variant.high == 50.0  # would trivially clear baseline.high
    result = verdict(baseline, variant, baseline_n=500, variant_n=1)
    assert result.verdict == "gated"
    assert "n=1" in result.hold_reason


# --- verdict: gate-integrity n-floor (review finding #1) -----------------


def test_verdict_gates_on_missing_channel_zero_n():
    # channels.get("some_label", {"n": 0, "closed": 0}) + wilson(0, 0) is
    # exactly the failure mode from the review: a missing/renamed channel
    # label produces Interval(0, 0, 0), which trivially satisfies
    # "variant.high < baseline.low" against any positive-rate baseline —
    # this must gate, not publish a fabricated warning.
    baseline = wilson_interval(83, 12933)
    variant = wilson_interval(0, 0)  # missing/empty cohort
    result = verdict(baseline, variant, baseline_n=12933, variant_n=0)
    assert result.verdict == "gated"
    assert result.confidence is None
    assert "n=0" in result.hold_reason
    assert "too small" in result.hold_reason.lower()


def test_verdict_gates_when_baseline_n_below_floor():
    baseline = wilson_interval(2, 10)  # n=10 < MIN_COHORT_N=30
    variant = wilson_interval(50, 100)
    result = verdict(baseline, variant, baseline_n=10, variant_n=100)
    assert result.verdict == "gated"
    assert "baseline n=10" in result.hold_reason


def test_verdict_gates_when_variant_n_below_floor():
    baseline = wilson_interval(50, 100)
    variant = wilson_interval(2, 10)  # n=10 < MIN_COHORT_N=30
    result = verdict(baseline, variant, baseline_n=100, variant_n=10)
    assert result.verdict == "gated"
    assert "variant n=10" in result.hold_reason


def test_verdict_n_floor_is_inclusive_boundary():
    # n exactly at MIN_COHORT_N clears the floor (>= not >).
    baseline = wilson_interval(2, MIN_COHORT_N)
    variant = wilson_interval(20, MIN_COHORT_N)
    result = verdict(
        baseline, variant, baseline_n=MIN_COHORT_N, variant_n=MIN_COHORT_N
    )
    assert result.verdict != "gated" or "too small" not in (result.hold_reason or "")


def test_verdict_custom_min_n_override():
    baseline = wilson_interval(2, 10)
    variant = wilson_interval(50, 100)
    # With a lowered floor, the same cohort that gated above now passes
    # through to the interval comparison.
    result = verdict(baseline, variant, baseline_n=10, variant_n=100, min_n=5)
    assert result.verdict != "gated" or "too small" not in (result.hold_reason or "")


# --- verdict: three branches (using default BIG_N via _v helper) --------


def test_verdict_published_lift_when_variant_clears_baseline_above():
    baseline = Interval(2.0, 1.5, 2.5)
    variant = Interval(5.0, 4.0, 6.0)  # variant.low(4.0) > baseline.high(2.5)
    result = _v(baseline, variant)
    assert result.verdict == "published_lift"
    assert result.confidence in ("High", "Medium")
    assert result.hold_reason is None


def test_verdict_published_warning_when_variant_clears_baseline_below():
    baseline = Interval(5.0, 4.0, 6.0)
    variant = Interval(1.0, 0.5, 1.5)  # variant.high(1.5) < baseline.low(4.0)
    result = _v(baseline, variant)
    assert result.verdict == "published_warning"
    assert result.confidence in ("High", "Medium")


def test_verdict_gated_when_intervals_overlap():
    baseline = Interval(10.0, 8.0, 12.0)
    variant = Interval(11.0, 9.0, 13.0)  # overlaps baseline
    result = _v(baseline, variant, hold_reason_fn=lambda: "held because overlap")
    assert result.verdict == "gated"
    assert result.confidence is None
    assert result.hold_reason == "held because overlap"


def test_verdict_gated_without_hold_reason_fn_uses_generic_fallback():
    # Review finding #5: every candidate needs SOME hold_reason when gated
    # — the generic fallback fires when the caller supplies none.
    baseline = Interval(10.0, 8.0, 12.0)
    variant = Interval(11.0, 9.0, 13.0)
    result = _v(baseline, variant)
    assert result.hold_reason is not None
    assert "overlap" in result.hold_reason.lower()
    assert "10.0" in result.hold_reason or "8.0" in result.hold_reason  # computed values only


# --- confidence tiers: gap vs narrower-interval-width -------------------


def test_confidence_high_when_gap_exceeds_narrower_width():
    # baseline width=1.0, variant width=1.0, gap(variant.low-baseline.high)=5.0
    baseline = Interval(2.0, 1.5, 2.5)
    variant = Interval(10.0, 7.5, 8.5)  # gap = 7.5 - 2.5 = 5.0 > width 1.0
    result = _v(baseline, variant)
    assert result.verdict == "published_lift"
    assert result.confidence == "High"


def test_confidence_medium_when_gap_does_not_exceed_narrower_width():
    # narrow gap relative to interval widths.
    baseline = Interval(2.0, 1.0, 3.0)  # width 2.0
    variant = Interval(4.0, 3.2, 4.8)  # width 1.6, gap = 3.2 - 3.0 = 0.2 <= 1.6
    result = _v(baseline, variant)
    assert result.verdict == "published_lift"
    assert result.confidence == "Medium"


def test_confidence_tiers_apply_symmetrically_to_warning_cards():
    baseline = Interval(10.0, 8.0, 12.0)  # width 4.0
    variant = Interval(1.0, 0.1, 0.5)  # width 0.4, gap = 8.0 - 0.5 = 7.5 > 0.4
    result = _v(baseline, variant)
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
    card = _card(candidate, baseline, variant, baseline_n=1590, variant_n=5347)

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

    card = _card(candidate, baseline, top, baseline_n=188, variant_n=88, hold_reason_fn=reason)
    assert card["status"] == "gated"
    assert card["confidence"] is None
    assert card["hold_reason"] is not None
    assert "188" in card["hold_reason"]
    assert "Life Circumstances" in card["hold_reason"]


def test_build_card_warning_status_for_meta_paid_shape():
    candidate = CANDIDATES["meta_paid_close"]
    baseline = wilson_interval(79, 9467)  # complement baseline
    variant = wilson_interval(4, 3466)
    card = _card(candidate, baseline, variant, baseline_n=9467, variant_n=3466)
    assert card["status"] == "published_warning"
    assert card["department"] == "marketing"


def test_build_card_gates_on_missing_variant_cohort():
    # Regression guard for review finding #1, exercised through the public
    # build_card entry point (not just verdict directly): a channel label
    # that stops appearing (n=0) must gate, never publish.
    candidate = CANDIDATES["ig_dm_channel"]
    baseline = wilson_interval(79, 9467)
    variant = wilson_interval(0, 0)
    card = _card(candidate, baseline, variant, baseline_n=9467, variant_n=0)
    assert card["status"] == "gated"
    assert card["hold_reason"] is not None
    assert "n=0" in card["hold_reason"]


def test_build_card_interpolates_computed_family_name():
    # Review finding #4: a published discovery card must name the winning
    # family in variant_label/title/action — computed, not fabricated.
    candidate = CANDIDATES["discovery_families"]
    baseline = wilson_interval(23, 188, z=DISCOVERY_SWEEP_Z)
    variant = wilson_interval(30, 60, z=DISCOVERY_SWEEP_Z)  # clears baseline
    family_name = "Relationships"
    card = _card(
        candidate, baseline, variant, baseline_n=188, variant_n=60,
        title_override=discovery_family_title(family_name),
        variant_label_override=family_name,
        action_text_override=discovery_family_action(family_name),
    )
    assert family_name in card["title"]
    assert card["variant_label"] == family_name
    assert family_name in card["action_text"]
    assert family_name in card["hindsight_headline"]


def test_all_candidate_ids_present():
    expected = {
        "live_watch", "ig_dm_channel", "meta_paid_close",
        "email_value", "discovery_families",
    }
    assert set(CANDIDATES.keys()) == expected


def test_discovery_hold_reason_format():
    baseline = wilson_interval(23, 188, z=DISCOVERY_SWEEP_Z)
    top = wilson_interval(21, 88, z=DISCOVERY_SWEEP_Z)
    reason = discovery_hold_reason(n=188, baseline=baseline, top_family="Life Circumstances", top=top)
    assert reason.startswith("At n=188 discovery calls")
    assert "Life Circumstances" in reason
    assert "nightly" in reason
    assert "Bonferroni" in reason


def test_discovery_family_title_and_action_interpolate_name_only():
    title = discovery_family_title("Time & Freedom")
    action = discovery_family_action("Time & Freedom")
    assert "Time & Freedom" in title
    assert "Time & Freedom" in action


# --- Bonferroni correction (review finding #2) ---------------------------


def test_discovery_sweep_z_is_bonferroni_corrected():
    assert DISCOVERY_SWEEP_Z == pytest.approx(2.69, abs=0.01)


def test_bonferroni_z_can_flip_a_marginal_family_to_gated():
    # The review's concrete example: "Relationships" cleared by 0.4pp at
    # n=57 under standard z=1.96 the day after failing. Reproduce a
    # similarly marginal case and show the Bonferroni z holds it gated
    # while the standard z would have published it — this is the whole
    # point of the fix.
    baseline_std = wilson_interval(23, 188, z=1.96)
    variant_std = wilson_interval(16, 57, z=1.96)
    result_std = _v(baseline_std, variant_std)
    assert result_std.verdict == "published_lift"  # marginal clear at standard z

    baseline_corrected = wilson_interval(23, 188, z=DISCOVERY_SWEEP_Z)
    variant_corrected = wilson_interval(16, 57, z=DISCOVERY_SWEEP_Z)
    result_corrected = _v(baseline_corrected, variant_corrected)
    assert result_corrected.verdict == "gated"  # wider intervals now overlap


# --- apply_hysteresis: pure state machine (review finding #3) -----------


def _raw(verdict_str, confidence=None, hold_reason=None):
    return VerdictResult(verdict_str, confidence, hold_reason)


def test_hysteresis_first_clear_night_stays_gated_streak_1():
    result = apply_hysteresis(
        prior_status="gated",
        prior_consecutive_clear_nights=0,
        raw_verdict=_raw("published_lift", "Medium"),
    )
    assert result.status == "gated"
    assert result.confidence is None
    assert result.consecutive_clear_nights == 1
    assert "night 1 of 2" in result.hold_reason


def test_hysteresis_second_consecutive_clear_night_publishes():
    result = apply_hysteresis(
        prior_status="gated",
        prior_consecutive_clear_nights=1,
        raw_verdict=_raw("published_lift", "Medium"),
    )
    assert result.status == "published_lift"
    assert result.confidence == "Medium"
    assert result.consecutive_clear_nights == REQUIRED_CLEAR_NIGHTS


def test_hysteresis_streak_resets_when_a_night_fails_to_clear():
    # Cleared once (streak=1), then the NEXT night doesn't clear — streak
    # resets to 0, stays gated. Exactly the "cleared the day after failing"
    # scenario the review flagged: a single good night is not enough, and
    # a broken streak doesn't carry over partial credit.
    result = apply_hysteresis(
        prior_status="gated",
        prior_consecutive_clear_nights=1,
        raw_verdict=_raw("gated", None, "intervals overlap"),
    )
    assert result.status == "gated"
    assert result.consecutive_clear_nights == 0


def test_hysteresis_published_flips_to_gated_immediately_no_grace_period():
    # published -> gated is IMMEDIATE — no streak requirement on the way
    # down (fail-toward-gated).
    result = apply_hysteresis(
        prior_status="published_lift",
        prior_consecutive_clear_nights=0,
        raw_verdict=_raw("gated", None, "no longer separated"),
    )
    assert result.status == "gated"
    assert result.confidence is None
    assert result.consecutive_clear_nights == 0
    assert result.hold_reason == "no longer separated"


def test_hysteresis_published_stays_published_while_still_clearing():
    result = apply_hysteresis(
        prior_status="published_warning",
        prior_consecutive_clear_nights=0,
        raw_verdict=_raw("published_warning", "High"),
    )
    assert result.status == "published_warning"
    assert result.confidence == "High"


def test_hysteresis_first_run_ever_treated_as_gated_streak_zero():
    # prior_status=None (no row exists yet for this candidate) — must earn
    # its first publish the same way any gated->published recovery does,
    # not publish immediately on day one.
    result = apply_hysteresis(
        prior_status=None,
        prior_consecutive_clear_nights=0,
        raw_verdict=_raw("published_lift", "High"),
    )
    assert result.status == "gated"
    assert result.consecutive_clear_nights == 1


def test_hysteresis_gated_stays_gated_when_never_clearing():
    result = apply_hysteresis(
        prior_status="gated",
        prior_consecutive_clear_nights=0,
        raw_verdict=_raw("gated", None, "overlap"),
    )
    assert result.status == "gated"
    assert result.consecutive_clear_nights == 0
    assert result.hold_reason == "overlap"


def test_hysteresis_result_is_pure_no_mutation():
    # Calling twice with the same inputs gives the same output — no hidden
    # state.
    kwargs = dict(
        prior_status="gated",
        prior_consecutive_clear_nights=1,
        raw_verdict=_raw("published_warning", "Medium"),
    )
    r1 = apply_hysteresis(**kwargs)
    r2 = apply_hysteresis(**kwargs)
    assert r1 == r2
