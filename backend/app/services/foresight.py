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
from dataclasses import dataclass, field
from typing import Literal, NamedTuple, Optional

Verdict = Literal["published_lift", "published_warning", "gated"]
Confidence = Literal["High", "Medium"]


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


def _intervals_overlap(a: Interval, b: Interval) -> bool:
    return a.low <= b.high and b.low <= a.high


def verdict(
    baseline: Interval,
    variant: Interval,
    *,
    hold_reason_fn: Optional[callable] = None,
) -> VerdictResult:
    """The publication gate.

    - ``published_lift``: variant.low > baseline.high — variant is CLEARLY
      above baseline, intervals don't touch.
    - ``published_warning``: variant.high < baseline.low — variant is
      CLEARLY below baseline (an inverse finding worth publishing as a
      caution, per the plan's meta_paid result).
    - ``gated``: intervals overlap — no separation, the gate holds. Callers
      should supply ``hold_reason_fn`` (called with no args, returning the
      human-readable why-held string) since gated cards need a reason but
      published ones don't.

    Confidence (published cards only): High when the gap between the
    intervals is greater than the width of the narrower interval, else
    Medium. Gated cards carry no confidence tier (None) — there's nothing
    to be confident about when the gate hasn't cleared.
    """
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

    hold_reason = hold_reason_fn() if hold_reason_fn is not None else None
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
    hold_reason_fn: Optional[callable] = None,
) -> dict:
    """Assemble one candidate definition + its computed stats into the dict
    the persistence layer/API/frontend consume. Pure — no DB, no Claude
    call, no prose generation beyond the number formatting helpers above."""
    result = verdict(baseline, variant, hold_reason_fn=hold_reason_fn)

    hindsight_headline = (
        f"{candidate.variant_label} {variant.fmt()} vs "
        f"{candidate.baseline_label} {baseline.fmt()}"
    )
    hindsight_detail = f"{candidate.n_label} — {lift_text(baseline, variant)}"

    return {
        "id": candidate.id,
        "status": result.verdict,
        "confidence": result.confidence,
        "title": candidate.title,
        "department": candidate.department,
        "hindsight_headline": hindsight_headline,
        "hindsight_detail": hindsight_detail,
        "evidence_href": candidate.evidence_href,
        "evidence_label": candidate.evidence_label,
        "insight_text": candidate.insight_text,
        "action_text": candidate.action_text,
        "lift_text": lift_text(baseline, variant),
        "hold_reason": result.hold_reason,
        "baseline_label": candidate.baseline_label,
        "baseline_rate": baseline.rate,
        "baseline_low": baseline.low,
        "baseline_high": baseline.high,
        "variant_label": candidate.variant_label,
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
        f"{baseline.fmt()} baseline — closest is {top_family} at {top.fmt()}. "
        "The engine recounts nightly and publishes if the intervals separate."
    )


__all__ = [
    "Interval",
    "wilson_interval",
    "mean_interval",
    "Verdict",
    "Confidence",
    "VerdictResult",
    "verdict",
    "lift_text",
    "CandidateDef",
    "build_card",
    "CANDIDATES",
    "discovery_hold_reason",
]
