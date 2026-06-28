# Central Intelligence — North Star: Data Intelligence & Recommendations

> **As of 2026-06-29.** This supersedes the "build more operational features" framing.
> The operational surfaces (Marketing / Sales / Fulfillment pages, CRUD, integrations)
> are **done and working** — we are NOT adding more of those. Read this together with
> `status-rebaseline.md` (what exists) — this doc redefines what "next" means.

---

## 1. The goal, restated

Central Intelligence is now an **analysis-and-recommendation layer over the data we
already pool.** Its job:

1. **Pool** data from many sources (already happening — 13 sync/ingest tasks).
2. **Analyze** the *actual* data to compute outcome metrics.
3. **Surface** what's working and what needs to change — from the numbers, not opinion.
4. **Recommend** next actions, grounded **purely in the data**.
5. **Monitor progress** over time as more data accumulates.

**We do not want heuristic information.** No hardcoded rules-of-thumb, no
"best-practice" advice, no LLM guessing. Every conclusion must trace to computed data.

---

## 2. The three decisions that shape the architecture

| Decision | Choice | Implication |
|----------|--------|-------------|
| **Recommendation basis** | **Statistical only** | Conclusions come strictly from metrics, correlations, trends, and statistical tests. The LLM may **only phrase what the numbers already prove** — it never forms the conclusion. Fully auditable. |
| **Measurement model** | **Outcome metrics + baselines** | Define outcome metrics per area, snapshot baselines, track deltas over time. "Works" = trending up; "needs change" = flat/declining. **Requires a metrics/snapshot store (net-new).** |
| **Surface** | **Both — shared engine** | Build the recommendation engine once; surface it on a standing Insights dashboard AND make it answerable in CI chat. |

---

## 3. What this changes about the existing design

The current per-department **specialist agents** are LLM agents with DB-read tools whose
system prompts say things like *"tie your recommendations to pain points…"* — i.e. they
produce **LLM-narrative / heuristic advice.** Under the new north star that is exactly
what we move away from for *recommendations*. The specialists stay useful for content
generation and conversational lookups, but **they are not the recommendation engine.**

The only existing piece that already matches the new philosophy is **`market_signals`**
(raw SQL aggregation, recomputed from scratch each run, no heuristics). That is the model
to generalize.

---

## 4. Architecture (target)

```
   SOURCES (already pooled)            ENGINE (net-new)                 SURFACES
 ┌───────────────────────┐     ┌──────────────────────────┐     ┌──────────────────┐
 │ WGR sync, GHL, Google  │     │ 1. Metric definitions     │     │ Insights /       │
 │ Workspace, email/social│ ──▶ │ 2. Snapshot store (time-  │ ──▶ │ Recommendations  │
 │ /ads/funnel stats,     │     │    series, per metric)    │     │ dashboard        │
 │ calls, market signals  │     │ 3. Trend + significance   │     │                  │
 │ (13 ingest tasks)      │     │    tests (pure stats)     │     │ CI chat          │
 └───────────────────────┘     │ 4. Recommendation gen     │     │ (same engine,    │
                                │    (data-derived + cite)  │     │  cited answers)  │
   STATS REPOS (exist)          │ 5. Progress tracking      │     └──────────────────┘
   sales_stats, marketing,      └──────────────────────────┘
   fulfillment_stats, goal_stats,
   intelligence, shared_intelligence
```

**Build on, don't rebuild:** the stats repositories already compute current department
KPIs. The engine consumes those (plus raw tables) — it does not re-derive them.

---

## 5. The net-new pieces (in build order)

### A. Metric registry — *what* we measure
A declared catalog of **outcome metrics**, each with: id, area (sales/marketing/etc.),
the exact SQL/aggregation that computes it, unit, direction (higher-is-better or not).
Examples to define from columns that already exist:
- Sales: lead→close rate (`leads` → `closed_sales`), avg call score (`sales_call_scores`),
  appointment show rate (`appointments`).
- Marketing: funnel stage conversion (`funnel_stats`), email CTR (`email_messages`),
  social engagement (`social_stats`).
- Fulfillment: goal completion (`goals`), coaching-strike trend (`coaching_strikes`).

### B. Snapshot store — *track over time* (the missing foundation)
A timeseries table (e.g. `metric_snapshots`: metric_id, scope, value, sample_size,
computed_at). A Celery task snapshots every registered metric on a schedule. **This is
what makes "monitor progress as we generate more data" possible** — today there is no
snapshot/timeseries table at all.

### C. Trend + significance layer — *what works / needs change*
Pure statistics over the snapshots: deltas vs. baseline, trend direction, and a
significance gate (don't flag noise — require enough sample size / a real change, not a
one-point wiggle). Output: per metric, a verdict {improving / declining / flat /
insufficient-data} with the numbers behind it.

### D. Recommendation generator — *what to do*
Rules are **statistical, not heuristic**: a recommendation is emitted only when the data
crosses a defined threshold (e.g. "metric X declined ≥N% over the window with sample ≥M").
The recommendation record stores the **evidence** (which metric, which numbers, which
window). The LLM's *only* role is to phrase the finding in plain language — it cannot
invent a recommendation the data didn't trigger.

### E. Surfaces — dashboard + chat over the same engine
- **Insights dashboard:** current verdicts, trends, active recommendations + their status.
- **CI chat:** "what's working in sales this month?" → answered from the same computed
  verdicts, with citations. No new reasoning path; it reads the engine's output.

### F. Progress / feedback loop
Recommendations have a lifecycle (open → acted-on → re-measured). As more data arrives,
the engine re-checks whether the metric moved — closing the loop on "monitor progress."

---

## 6. Guardrails (the "no heuristics" contract)

- **Every recommendation cites its data.** If it can't point to a metric + numbers +
  window, it doesn't ship.
- **The LLM phrases, it does not conclude.** Conclusions come from §C/§D.
- **Significance before signal.** Insufficient data → say "insufficient data," never guess.
- **Recompute from scratch** where feasible (the `market_signals` pattern) so results are
  reproducible and auditable.

---

## 7. Suggested first step

Build **A (metric registry) + B (snapshot store)** as the foundation — they unblock
everything else and are the genuinely missing piece. Start with one area end-to-end
(Sales is the most data-rich: leads, calls, scores, closed sales) to prove the loop:
*define metrics → snapshot → detect trend → emit a data-cited recommendation → show it
on the dashboard and answer it in chat.* Then generalize to Marketing and Fulfillment.

---

## 8. Explicitly out of scope now

- New operational features / CRUD surfaces (those work).
- LLM/heuristic advice as a recommendation source.
- The earlier roadmap's "build the missing pages" priority — except where a page is the
  surface for this engine (the Insights dashboard).
