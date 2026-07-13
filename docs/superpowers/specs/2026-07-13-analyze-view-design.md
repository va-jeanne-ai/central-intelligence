# Design: "Analyze this view" — grounded analysis of the current filtered data

**Date:** 2026-07-13
**Status:** Approved design, pending implementation plan
**Branch:** `feat/analyze-view`

## Purpose

On any filtered list page, the user clicks **"Analyze this view"** and gets a narrative analysis of what the currently filtered dataset shows — grounded entirely in server-computed aggregates, never in numbers the LLM invents.

## Decisions made during brainstorming

| Question | Decision |
|---|---|
| Scope | Generic mechanism across all filtered list pages; wave 1 = Appointments, Sales Calls, Leads, Members (the four surfaces with filterable list endpoints today) |
| Analysis type | LLM narrative over real server-computed aggregates (hypothesize-never-fabricate rule applies) |
| UX shape | Inline drawer/panel on the page; no chat hand-off |
| Persistence | Ephemeral — generated on demand, gone when closed; LLM is called only on explicit user click |
| Verification | No seeded-data unit tests, no mock-mode test runs. Feature ships with a manual test document (FEATURE-VERIFICATION.md style); the user verifies personally against real data |
| Mock mode | Ignored entirely in the new code — every analyze call is a real LLM call; missing API key → clear error, never a canned response (2026-07-13) |

## Architecture

```
[List page] --filter state--> POST /api/v1/analyze/{surface}?<same filter params as the list endpoint>
                                    |
                          aggregator registry[surface]
                                    |  re-runs the filtered query, computes aggregates (SQL)
                                    v
                          shared narrative step (Claude)
                                    |  numbers come ONLY from the aggregates JSON
                                    v
                  { narrative, highlights[], hypotheses[], stats, row_count, filters_echo, generated_at }
                                    |
                          <AnalyzeViewDrawer /> renders narrative + the stats it was grounded in
```

The frontend never sends rows. It serializes the page's current filter state — the same query params the list endpoint already takes — and the backend re-runs the filtered query itself, so the analysis always covers the **entire** filtered dataset, not just the visible page.

## Backend

### Route

New `backend/app/routes/analyze.py`:

- `POST /api/v1/analyze/{surface}` where `surface ∈ {appointments, sales_calls, leads, members}` (registry-driven; unknown surface → 404).
- Accepts the same filter query params as that surface's list endpoint (`status`, `rep`, `from`/`to`, `source`, `search`, `call_type`, `call_result`, … as applicable). Pagination and sort params are ignored — aggregation covers the full filtered set.
- Auth: same dependency the list endpoints already use.

### Aggregator registry

New `backend/app/analytics/view_analysis/` package, mirroring the existing `analytics/registry.py` pattern. Each surface registers one aggregator with:

- `key` — `"appointments"` | `"sales_calls"` | `"leads"` | `"members"`
- `parse_filters(params) -> Filters` — reuses the list endpoint's filter semantics (extract or call the existing WHERE-building logic; do not duplicate it)
- `aggregate(session, filters) -> dict` — a handful of SQL queries returning:
  - `row_count`
  - breakdowns applicable to the surface (by status / rep / source / call_result / call_type)
  - rates where meaningful (e.g. appointment show rate, booked rate)
  - a time-bucketed series across the filtered window
- `describe() -> str` — one paragraph telling the LLM what this surface's fields mean

Where per-surface stats code already exists (`compute_appointment_stats`, `sales_stats`, the `/calls/stats` logic in `ci.py`), the aggregator threads filters through it rather than writing parallel queries.

### Narrative step (shared)

One function modeled directly on `analytics/overall_insight.py`: same sync Anthropic client pattern, same `extract_json_object` parsing, `settings.anthropic_model_default`. Unlike `overall_insight`, this feature **ignores `mock_mode` entirely** — the project is past the UI-building stage and works with real data, so every analyze call is a real LLM call. If no Anthropic key is configured, the endpoint returns a clear error rather than a canned response.

Prompt receives: surface name, human-readable echo of the active filters (e.g. "Sales calls, Mar 1–31, rep: Marco"), `row_count`, `describe()` text, and the aggregates JSON. Grounding rules in the system prompt:

1. Every number cited must appear verbatim in the aggregates block.
2. Interpretations go in a separate `hypotheses` list and must be phrased as hypotheses.
3. If `row_count` is too small to support a claim, say so rather than stretching.

Output schema: `narrative` (2–4 paragraphs), `highlights` (3–5 one-liners), `hypotheses` (0–3 items).

## Frontend

- New `frontend/src/components/analyze/AnalyzeViewDrawer.tsx` (shared) + `frontend/src/lib/analyze-client.ts` (following `appointments-client.ts` style).
- Each wave-1 list page adds one **"Analyze this view"** button beside its existing filter bar. On click it serializes the page's current filter state (the same object it already uses to fetch the list) and opens the drawer.
- Drawer contents, top to bottom:
  1. Filter echo — "Analyzing 214 sales calls, Mar 1–31, rep: Marco"
  2. Loading state while the analysis runs
  3. `narrative` → `highlights` → `hypotheses` (visually marked as speculative)
  4. Collapsible **"Data this is based on"** section rendering the raw aggregates, so every number in the narrative can be checked
  5. Re-run button
- Closing the drawer discards the analysis (ephemeral).

## Guardrails & error handling

- `row_count == 0` → drawer shows "no data in this view"; **no LLM call is made** (no cost).
- Unknown surface → 404. Aggregator or LLM failure → clean error state in the drawer with a retry action; never a partial narrative.
- Privacy: only aggregates are sent to the model. Breakdown labels (rep names, statuses, sources) are included; raw rows and contact PII (emails, phone numbers) are never sent.
- Cost: one LLM call per explicit click, using the default model. No background or automatic invocations.

## Verification (manual, per user's standing rule)

No seeded-data unit tests and no mock-mode test runs. The feature ships with a **test document** in the established `FEATURE-VERIFICATION.md` style, covering each wave-1 surface:

- **Feature:** what "Analyze this view" does on this page
- **How to locate:** URL + where the button sits
- **Steps to test:** apply a specific filter combination → click Analyze → confirm the filter echo matches, `row_count` matches the list's total, every number in the narrative appears in the "Data this is based on" section, hypotheses are marked as speculative, the zero-rows case shows "no data" without an LLM call, and errors surface the retry state
- **Rating:** ⬜ pending / ✅ pass / ❌ fail (with note)

The user performs verification personally against real data.

## Rollout

Wave 1 wires all four surfaces with filterable list endpoints today: **Appointments, Sales Calls, Leads, Members**. The registry + shared drawer make any future surface (coaching calls, marketing lists, fulfillment) one aggregator + one button.
