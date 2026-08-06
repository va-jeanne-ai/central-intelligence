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
