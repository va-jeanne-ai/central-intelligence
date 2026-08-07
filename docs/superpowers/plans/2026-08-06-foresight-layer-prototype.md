# Foresight Layer — plan + static prototype

**Goal:** a CI surface that pairs every recommendation with the evidence chain
that produced it — three lenses per card: **Hindsight** (what the data shows),
**Insight** (why we think it happens), **Foresight** (what to do, with
confidence). Aligns with the 2026-06-29 pivot (statistical recommendation
engine over pooled data, no heuristics) and the directors' contract
(hypothesize from real data, never fabricate).

## Phases

### P0 — Static prototype (THIS commit)
`/foresight` page with hardcoded sample recommendations so the client can feel
the format. Numbers are directionally real (funnel counts, channel/revenue
figures from the live mirrors) but the statistics are illustrative — the page
carries a permanent amber PROTOTYPE banner. No backend. Remove or replace in P1.

### P1 — Statistics engine (real, minimal)
- Nightly Celery task computes **conditional-probability recommendations** by
  counting over existing mirrors (lead_journey, closed_sales, email_campaigns,
  insights × calls). Pure counting + Wilson score intervals — no ML, no
  heuristics, honest at n=83 sales.
- Candidate recs to validate against real data first (kill any that don't
  survive scrutiny): live-vs-replay watch → booking rate; channel → lead-close
  rate; campaign_type → open-rate prior; discovery-call signal families →
  close rate.
- Each rec persisted with: the observed rates, n, CI bounds, the SQL-derivable
  evidence description, and links to the hindsight surface that shows it.
- `GET /foresight/recommendations` replaces the static data; page unchanged.
- Publication gate: a rec renders only if its CI excludes the baseline (no
  overlapping-interval "insights").

### P2 — Lifecycle
Accept/dismiss per rec (staff), outcome tracking (did the metric move), stale
rec expiry when the underlying rates converge. Feeds the decision-journal
pattern.

### P3 — Autonomy ladder
Recs graduate from Inform → Recommend → (much later) queued actions. Requires
P2 outcome history first.

## Non-goals (explicit)
- No revenue *forecasts* at n=83 sales — only rate comparisons with intervals.
- No black-box scoring; every number must be reproducible by a SQL count.

## P1 validation results (2026-08-07, live data — build against THESE)

| Candidate | Cohorts | Result | Verdict |
|---|---|---|---|
| Live-watch → booking | watched_live (499/5,347 = 9.3% [8.6–10.1]) vs replay-only (104/1,590 = 6.5% [5.4–7.9]) | separated, 1.4× | **PUBLISH** |
| Channel → close | ig_dm 52/4,656 = 1.12% [0.85–1.46] vs all-lead baseline 83/12,933 = 0.64% [0.52–0.79] | separated, 1.75× — ig_dm carries 52 of 83 sales | **PUBLISH** |
| meta_paid → close | 4/3,466 = 0.12% [0.04–0.30] vs baseline — significantly BELOW | inverse finding | **PUBLISH as warning card** |
| Email Value/Education open rate | 649 campaigns, mean 26.1% ±1.1 vs other 1,779 at 22.7% ±0.7 (mean-of-campaigns t-interval, NOT Wilson — document why) | separated, +3.4pp | **PUBLISH** |
| Discovery signal-family → close | all 7 families with n≥20 overlap the 12.2% [8.3–17.7] baseline (closest: Life Circumstances 23.9% [16.2–33.7]) | gate holds | **GATED (render as held)** |

Notes: real effects are smaller than the P0 illustrative numbers (1.4× not 3.4×) —
ship the real ones. No invented impact projections: cards display observed lift
(pp delta + ratio) only. lead_journey has 5 UTM fields (no utm_content_last) —
pass None in the 6-tuple like the funnels aggregation does.

## P1 architecture (as built)
- `app/services/foresight.py` — pure: wilson_interval, mean_interval,
  confidence tiering (published requires interval separation; warning cards =
  separation in the negative direction), card assembly from cohort counts.
- `app/repositories/foresight_stats.py` — one SQL aggregate per cohort family
  (pooler rule: no row shipping).
- `foresight_recommendations` table (migration) — nightly snapshot of computed
  cards incl. gated ones with their why-held explanation.
- Celery beat: compute nightly after the WGR sync; also computed on demand via
  the backfill-style one-off during this build.
- `GET /foresight/recommendations` — published + gated lists from the table.
- `/foresight` page: live data, PROTOTYPE banner replaced by "computed nightly ·
  last refresh" line; P0 static file deleted. P2 (accept/track) unchanged, later.
