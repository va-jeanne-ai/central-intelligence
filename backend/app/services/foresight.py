"""Foresight P1 — pure statistics engine (no DB).

Implements the plan's P1 architecture (docs/superpowers/plans/
2026-08-06-foresight-layer-prototype.md): every recommendation is a
reproducible SQL count, turned into a Wilson (or mean-of-campaigns)
confidence interval, and a card only PUBLISHES when its interval clears
the baseline. No ML, no heuristics — this module never invents a number,
it only formats and compares the counts the repository layer hands it.

Three building blocks:
  - ``wilson_interval`` / ``mean_interval`` — the two interval estimators.
  - ``verdict`` — the publication gate (published_lift / published_warning /
    gated) plus a confidence tier.
  - ``build_card`` — assembles a declarative candidate definition + computed
    stats into the dict the API/frontend renders. All prose lives in the
    candidate definitions (``CANDIDATES`` below) — this module only formats
    numbers ("X.X% [low–high]", "+2.8pp · 1.4×").
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Literal, NamedTuple, Optional

Verdict = Literal["published_lift", "published_warning", "gated"]
Confidence = Literal["High", "Medium"]

# Gate-integrity floor: any cohort with fewer than this many observations is
# too thin to trust, regardless of what its interval happens to say. Guards
# against exactly the failure mode a missing/renamed channel label or an
# empty cohort produces: wilson_interval(0, 0) = Interval(0, 0, 0), which
# would otherwise trivially satisfy "variant.high < baseline.low" and
# publish a fabricated warning card off zero data. n=30 is a conservative,
# documented floor — comfortably above every stable candidate's n in this
# project (smallest today is ig_dm's ~4,656) but a real backstop for
# candidates that could legitimately thin out (a channel losing traffic
# entirely, a taxonomy relabel, a single-campaign email cohort).
MIN_COHORT_N = 30

# Bonferroni-corrected z for the discovery-family sweep. The sweep tests 7
# independent signal families each night and publishes whichever one clears
# the baseline — a multiple-comparisons problem: at the standard z=1.96
# (single-comparison alpha=0.05), testing 7 families gives roughly a
# 1-(1-0.05)^7 ~= 30% chance SOME family clears by chance alone even if
# none is real. Bonferroni controls the family-wise error rate by testing
# each comparison at alpha/7 instead of alpha: z = ppf(1 - 0.05/(2*7)) =
# 2.69 (two-sided, k=7). Only the discovery-family sweep uses this z — the
# other four candidates are each a single planned comparison, so 1.96 (the
# standard 95% CI multiplier) is correct for them.
DISCOVERY_SWEEP_Z = 2.69
DISCOVERY_FAMILY_COUNT = 7


class Interval(NamedTuple):
    """A point estimate with a confidence interval, all in percent."""

    rate: float
    low: float
    high: float

    @property
    def width(self) -> float:
        return self.high - self.low

    def fmt(self) -> str:
        """"X.X% [low–high]" — the one place numbers become prose."""
        return f"{self.rate:.1f}% [{self.low:.1f}–{self.high:.1f}]"


def wilson_interval(successes: int, n: int, z: float = 1.96) -> Interval:
    """Wilson score interval for a Bernoulli proportion (successes/n), in
    percent. Preferred over the naive normal-approximation interval because
    it stays inside [0, 1] and is well-behaved at small n / extreme rates —
    exactly the regime this project's cohorts live in (n as low as 88, rates
    as low as 0.1%). ``z=1.96`` is the standard 95% CI multiplier.

    Returns rate=0, low=0, high=0 for n=0 (no data — never divide by zero,
    never fabricate a rate for an empty cohort).
    """
    if n <= 0:
        return Interval(0.0, 0.0, 0.0)

    p = successes / n
    denom = 1 + z**2 / n
    center = (p + z**2 / (2 * n)) / denom
    half_width = (z / denom) * math.sqrt((p * (1 - p) / n) + (z**2 / (4 * n**2)))
    low = max(0.0, center - half_width)
    high = min(1.0, center + half_width)
    return Interval(p * 100, low * 100, high * 100)


def mean_interval(mean: float, sd: float, n: int, z: float = 1.96) -> Interval:
    """t/normal interval for a MEAN of per-campaign rates, in percent.

    Why Wilson doesn't apply here: Wilson assumes a single Bernoulli trial
    per unit (one lead either converts or doesn't). The email candidate's
    unit is a *campaign*, and its value is that campaign's own open_rate —
    already a proportion averaged over its recipients. We're estimating the
    population mean of those campaign-level proportions, not counting
    successes over a shared n — so this is a standard mean ± z * SEM
    interval (using the normal approximation; with n=649/1,779 campaigns
    the t and normal quantiles are indistinguishable). ``mean``/``sd`` are
    expected in percent already (matches campaign_type's open_rate column).

    Returns rate=mean, low=high=mean for n<=1 (no variance estimate
    possible — never fabricate a width from a single observation).
    """
    if n <= 1:
        return Interval(mean, mean, mean)
    sem = sd / math.sqrt(n)
    half_width = z * sem
    return Interval(mean, mean - half_width, mean + half_width)


@dataclass(frozen=True)
class VerdictResult:
    verdict: Verdict
    confidence: Optional[Confidence]  # None for gated cards
    hold_reason: Optional[str] = None


def _default_hold_reason(baseline: Interval, variant: Interval) -> str:
    """Generic, computed-values-only hold reason used whenever a candidate
    doesn't supply its own ``hold_reason_fn``. Every candidate must render
    SOME why-held text when gated — falling back to a card's hypothesis
    copy would present an unproven insight as if it were the reason the
    gate held, which is exactly the kind of fabrication this engine exists
    to avoid."""
    return (
        f"Intervals overlap at current n: variant {variant.fmt()} vs "
        f"baseline {baseline.fmt()}. Recounted nightly."
    )


def verdict(
    baseline: Interval,
    variant: Interval,
    *,
    baseline_n: int,
    variant_n: int,
    min_n: int = MIN_COHORT_N,
    hold_reason_fn: Optional[Callable[[], str]] = None,
) -> VerdictResult:
    """The publication gate.

    Gate-integrity floor (checked FIRST, before any interval comparison):
    if either cohort's n is below ``min_n``, the card is gated regardless
    of what the interval says. This is not optional — an empty or missing
    cohort (e.g. a channel label that stops appearing, a taxonomy rename,
    ``wilson_interval(0, 0)`` collapsing to ``Interval(0, 0, 0)``) can
    otherwise trivially satisfy the separation test and publish a
    fabricated finding off zero data. The hold reason for this branch names
    which cohort was too small.

    - ``published_lift``: variant.low > baseline.high — variant is CLEARLY
      above baseline, intervals don't touch.
    - ``published_warning``: variant.high < baseline.low — variant is
      CLEARLY below baseline (an inverse finding worth publishing as a
      caution, per the plan's meta_paid result).
    - ``gated``: intervals overlap — no separation, the gate holds. Callers
      may supply ``hold_reason_fn`` (called with no args, returning the
      human-readable why-held string) for a candidate-specific reason;
      otherwise ``_default_hold_reason`` produces a generic, computed-only
      fallback so every gated card always carries SOME reason — never the
      card's hypothesis prose standing in as if it were the reason.

    Confidence (published cards only): High when the gap between the
    intervals is greater than the width of the narrower interval, else
    Medium. Gated cards carry no confidence tier (None) — there's nothing
    to be confident about when the gate hasn't cleared.
    """
    if baseline_n < min_n or variant_n < min_n:
        too_small = []
        if baseline_n < min_n:
            too_small.append(f"baseline n={baseline_n}")
        if variant_n < min_n:
            too_small.append(f"variant n={variant_n}")
        reason = (
            f"Cohort too small / not found ({', '.join(too_small)}, floor={min_n}). "
            "Recounted nightly."
        )
        return VerdictResult("gated", None, reason)

    if variant.low > baseline.high:
        gap = variant.low - baseline.high
        narrower_width = min(baseline.width, variant.width)
        confidence: Confidence = "High" if gap > narrower_width else "Medium"
        return VerdictResult("published_lift", confidence)

    if variant.high < baseline.low:
        gap = baseline.low - variant.high
        narrower_width = min(baseline.width, variant.width)
        confidence = "High" if gap > narrower_width else "Medium"
        return VerdictResult("published_warning", confidence)

    hold_reason = (
        hold_reason_fn() if hold_reason_fn is not None else _default_hold_reason(baseline, variant)
    )
    return VerdictResult("gated", None, hold_reason)


def lift_text(baseline: Interval, variant: Interval) -> str:
    """"+2.8pp · 1.4×" — percentage-point delta and ratio, the only two
    derived numbers this module ever prints beyond the interval itself."""
    pp = variant.rate - baseline.rate
    ratio = (variant.rate / baseline.rate) if baseline.rate > 0 else float("inf")
    sign = "+" if pp >= 0 else ""
    ratio_str = f"{ratio:.1f}×" if math.isfinite(ratio) else "—"
    return f"{sign}{pp:.1f}pp · {ratio_str}"


@dataclass(frozen=True)
class CandidateDef:
    """Declarative recommendation definition — ALL display copy lives here.
    The engine (this module) never generates prose from numbers beyond
    formatting rates/lift. See the module docstring."""

    id: str
    title: str
    department: str
    insight_text: str
    action_text: str
    evidence_href: str
    evidence_label: str
    baseline_label: str
    variant_label: str
    n_label: str


def build_card(
    candidate: CandidateDef,
    baseline: Interval,
    variant: Interval,
    *,
    baseline_n: int,
    variant_n: int,
    min_n: int = MIN_COHORT_N,
    hold_reason_fn: Optional[Callable[[], str]] = None,
    title_override: Optional[str] = None,
    variant_label_override: Optional[str] = None,
    action_text_override: Optional[str] = None,
) -> dict:
    """Assemble one candidate definition + its computed stats into the dict
    the persistence layer/API/frontend consume. Pure — no DB, no Claude
    call, no prose generation beyond the number formatting helpers above.

    ``baseline_n``/``variant_n`` feed the gate-integrity floor in
    ``verdict`` — every card assembly must state its cohort sizes, there is
    no path that skips the floor check.

    The three ``*_override`` params exist ONLY for interpolating a
    COMPUTED value (e.g. the winning signal_family's name) into a
    candidate's otherwise-static copy — never for inventing new prose.
    Callers pass a string built from the same computed inputs already on
    hand (e.g. an f-string naming ``top_family``), not free text.
    """
    result = verdict(
        baseline, variant, baseline_n=baseline_n, variant_n=variant_n,
        min_n=min_n, hold_reason_fn=hold_reason_fn,
    )

    variant_label = variant_label_override or candidate.variant_label
    title = title_override or candidate.title
    action_text = action_text_override or candidate.action_text

    hindsight_headline = (
        f"{variant_label} {variant.fmt()} vs "
        f"{candidate.baseline_label} {baseline.fmt()}"
    )
    hindsight_detail = f"{candidate.n_label} — {lift_text(baseline, variant)}"

    return {
        "id": candidate.id,
        "status": result.verdict,
        "confidence": result.confidence,
        "title": title,
        "department": candidate.department,
        "hindsight_headline": hindsight_headline,
        "hindsight_detail": hindsight_detail,
        "evidence_href": candidate.evidence_href,
        "evidence_label": candidate.evidence_label,
        "insight_text": candidate.insight_text,
        "action_text": action_text,
        "lift_text": lift_text(baseline, variant),
        "hold_reason": result.hold_reason,
        "baseline_label": candidate.baseline_label,
        "baseline_rate": baseline.rate,
        "baseline_low": baseline.low,
        "baseline_high": baseline.high,
        "variant_label": variant_label,
        "variant_rate": variant.rate,
        "variant_low": variant.low,
        "variant_high": variant.high,
        "n_label": candidate.n_label,
    }


# ---------------------------------------------------------------------------
# Candidate definitions — declarative, no numbers. Copy sourced from the
# plan's "Copy for the four cards" section (verbatim-ish).
# ---------------------------------------------------------------------------

CANDIDATES: dict[str, CandidateDef] = {
    "live_watch": CandidateDef(
        id="live_watch",
        title="Follow up with live webinar watchers first",
        department="sales",
        insight_text=(
            "Intent peaks in the hours after live attendance — live watchers "
            "chose a fixed time, and the Q&A creates a personal hook a "
            "replay can't."
        ),
        action_text=(
            "Prioritize same-day follow-up for live watchers, ahead of "
            "replay-watcher outreach."
        ),
        evidence_href="/marketing/funnels",
        evidence_label="Funnel: lead_journey watched_live vs replay-only",
        baseline_label="Replay-only",
        variant_label="Watched live",
        n_label="lead_journey watchers",
    ),
    "ig_dm_channel": CandidateDef(
        id="ig_dm_channel",
        title="ig_dm is the closing channel — protect and scale it",
        department="marketing",
        insight_text=(
            "DM conversations pre-qualify by dialogue: by the time a lead "
            "books from a DM, the objection handling has already started."
        ),
        action_text=(
            "Keep DM response capacity staffed; treat DM keyword campaigns "
            "as the primary revenue channel when planning content."
        ),
        evidence_href="/marketing/funnels",
        evidence_label="Funnel: channel breakdown → ig_dm",
        baseline_label="All-lead baseline",
        variant_label="ig_dm",
        n_label="leads by channel, closed rate",
    ),
    "meta_paid_close": CandidateDef(
        id="meta_paid_close",
        title="meta_paid volume isn't converting to closes",
        department="marketing",
        insight_text=(
            "Paid reach buys webinar registrations, but the close-side data "
            "says those leads behave differently from DM-sourced ones."
        ),
        action_text=(
            "Don't scale Meta spend expecting closes at the blended rate — "
            "measure it as a top-of-funnel channel and judge it on cost per "
            "booked call, not per lead."
        ),
        evidence_href="/marketing/funnels",
        evidence_label="Funnel: channel breakdown → meta_paid",
        baseline_label="All-lead baseline",
        variant_label="meta_paid",
        n_label="leads by channel, closed rate",
    ),
    "email_value": CandidateDef(
        id="email_value",
        title="Value/Education emails out-open everything else",
        department="marketing",
        insight_text=(
            "Story-led subjects earn the open; promo-led subjects spend the "
            "goodwill those opens build."
        ),
        action_text=(
            "Sequence two Value/Education sends ahead of each promotional "
            "push; watch unsubscribes as the guardrail."
        ),
        evidence_href="/marketing/email",
        evidence_label="Email: campaign_type breakdown",
        baseline_label="Other campaign types",
        variant_label="Value/Education",
        n_label="campaigns, mean open_rate",
    ),
    "discovery_families": CandidateDef(
        id="discovery_families",
        # Title/copy intentionally state-agnostic: this candidate's verdict
        # is genuinely data-dependent run to run (unlike the other four,
        # which have consistently separated/held since P1 validation) — at
        # small per-family n (as low as 20), a family can cross the gate as
        # new discovery calls land. Never hardcode a "held by the gate"
        # title that could go stale against a family that just published.
        title="Discovery-call signal family vs. the discovery-held baseline",
        department="sales",
        insight_text=(
            "Each discovery call surfaces a dominant pain signal family — "
            "this candidate asks whether any one family's close rate "
            "separates from the overall discovery-held baseline, or "
            "whether the differences seen so far are noise at this sample "
            "size."
        ),
        action_text=(
            "When gated: no action yet — the engine recounts nightly and "
            "publishes automatically the moment a family's interval clears "
            "the baseline. When published: route leads carrying this "
            "signal family to the objection-handling script it implies, "
            "and keep watching — small-n findings can revert."
        ),
        evidence_href="/ci-insights",
        evidence_label="Insights: signal_family × discovery close rate",
        baseline_label="Discovery-held baseline",
        variant_label="Top signal family",
        n_label="discovery calls by signal family",
    ),
}


def discovery_hold_reason(*, n: int, baseline: Interval, top_family: str, top: Interval) -> str:
    """Human-readable hold reason for the discovery_families gated card —
    generated from the computed numbers (never invented), matching the
    plan's example copy."""
    return (
        f"At n={n} discovery calls, no signal family separates from the "
        f"{baseline.fmt()} baseline (Bonferroni-corrected for {DISCOVERY_FAMILY_COUNT} "
        f"families, z={DISCOVERY_SWEEP_Z}) — closest is {top_family} at {top.fmt()}. "
        "The engine recounts nightly and publishes if the intervals separate."
    )


def discovery_family_title(family_name: str) -> str:
    """Published-state title for the discovery_families card — interpolates
    the COMPUTED winning family name (never invented prose) into the
    otherwise-static candidate title."""
    return f"{family_name} discovery calls close at a different rate"


def discovery_family_action(family_name: str) -> str:
    """Published-state action copy for the discovery_families card —
    interpolates the COMPUTED winning family name into the candidate's
    static action text (see CANDIDATES['discovery_families'].action_text
    for the gated-state wording, which names no family since none has
    cleared)."""
    return (
        f"Route leads whose discovery call surfaces the {family_name} signal "
        "family to the objection-handling script it implies, and keep "
        "watching — this cleared a multiple-comparisons-corrected bar, but "
        "small-n findings can still revert."
    )


REQUIRED_CLEAR_NIGHTS = 2


@dataclass(frozen=True)
class HysteresisResult:
    """The displayed status/confidence after applying hysteresis to a raw
    nightly verdict, plus the ``consecutive_clear_nights`` counter to
    persist for next run."""

    status: Verdict
    confidence: Optional[Confidence]
    hold_reason: Optional[str]
    consecutive_clear_nights: int


def apply_hysteresis(
    *,
    prior_status: Optional[Verdict],
    prior_consecutive_clear_nights: int,
    raw_verdict: VerdictResult,
) -> HysteresisResult:
    """State machine gating what actually gets DISPLAYED, on top of the raw
    per-night statistical verdict. Two rules, deliberately asymmetric
    (fail-toward-gated):

    - gated -> published requires the raw verdict to clear (publish_lift or
      publish_warning) on ``REQUIRED_CLEAR_NIGHTS`` (2) CONSECUTIVE nightly
      runs before the DISPLAYED status flips to published. One clearing
      night alone bumps ``consecutive_clear_nights`` to 1 and keeps
      DISPLAYING gated (with a reason naming the streak) — guards against a
      single-night statistical fluke (exactly the "cleared by 0.4pp the day
      after failing" scenario) driving a publish.
    - published -> gated flips IMMEDIATELY the first night the raw verdict
      no longer clears — no grace period on the way down. A recommendation
      that stops being true must stop being shown as true without delay;
      the risk of erring toward gated (understating a still-real effect for
      one extra night) is strictly preferred over erring toward published
      (overstating a no-longer-real one).
    - ``prior_status=None`` (first run ever for a candidate) is treated
      like "prior was gated, streak 0" — a brand-new candidate must earn
      its first publish the same way any recovery from gated does.

    Pure function — no DB, no I/O. ``raw_verdict`` is this run's
    ``verdict()`` output; the caller persists the returned
    ``consecutive_clear_nights`` back onto the row for next run's
    ``prior_consecutive_clear_nights``.
    """
    raw_clears = raw_verdict.verdict in ("published_lift", "published_warning")
    was_published = prior_status in ("published_lift", "published_warning")

    if was_published:
        if raw_clears:
            # Still separated — stays published, streak is irrelevant once
            # published (only tracked on the way up).
            return HysteresisResult(
                raw_verdict.verdict, raw_verdict.confidence, raw_verdict.hold_reason, 0
            )
        # Immediate flip to gated — no grace period, fail-toward-gated.
        # raw_verdict.verdict == "gated" here, so verdict() has already
        # populated hold_reason (candidate-specific or the generic
        # fallback) — never None.
        return HysteresisResult("gated", None, raw_verdict.hold_reason, 0)

    # Prior state was gated (or this is the first run ever).
    if not raw_clears:
        return HysteresisResult("gated", None, raw_verdict.hold_reason, 0)

    streak = prior_consecutive_clear_nights + 1
    if streak >= REQUIRED_CLEAR_NIGHTS:
        return HysteresisResult(
            raw_verdict.verdict, raw_verdict.confidence, raw_verdict.hold_reason, streak
        )

    # Cleared, but not yet for two consecutive nights — stays gated,
    # displayed hold reason names the streak so it's visibly progressing
    # rather than silently identical to a "no signal at all" gate.
    hold_reason = (
        f"Cleared the gate tonight (night {streak} of {REQUIRED_CLEAR_NIGHTS} required) "
        "but needs a second consecutive clearing night before it publishes. "
        f"Raw result: variant vs baseline separated — {raw_verdict.verdict}."
    )
    return HysteresisResult("gated", None, hold_reason, streak)


__all__ = [
    "Interval",
    "wilson_interval",
    "mean_interval",
    "MIN_COHORT_N",
    "DISCOVERY_SWEEP_Z",
    "DISCOVERY_FAMILY_COUNT",
    "Verdict",
    "Confidence",
    "VerdictResult",
    "verdict",
    "lift_text",
    "CandidateDef",
    "build_card",
    "CANDIDATES",
    "discovery_hold_reason",
    "discovery_family_title",
    "discovery_family_action",
    "REQUIRED_CLEAR_NIGHTS",
    "HysteresisResult",
    "apply_hysteresis",
]
