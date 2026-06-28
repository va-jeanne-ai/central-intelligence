# Changelog

All notable changes to the Central Intelligence project will be documented in this file.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]


### Fixed — Dashboard Weekly Performance Snapshot used sync date, not entry date

Audited the dashboard snapshot. **Total Leads** (11,721) and **Calls This Week** (28) are accurate.
**Active Members** shows 0 because the members table is genuinely empty (data gap, not a bug). The code
bug: **"This Week"** and the **Lead Volume sparkline** counted `created_at` (sync time, which bunches
all backfilled rows into the sync window) — the same issue fixed on /leads.

- **`routes/dashboard.py`** — "This Week" (and its prev-week comparison) now count `entry_date` in the
  last 7 days: **164 → 127**, consistent with /leads. The 8-week Lead Volume sparkline now buckets by
  `entry_date` too (81/58/49/60/85/105/331/107), matching the /leads chart.

Verified end-to-end via the dashboard route. `tsc` + `next build` pass.


### Added — click a Sales Funnel stage to filter the table

Funnel bars on /leads are now clickable: clicking a stage sets the table's status filter to match it
and scrolls the records table into view. Stage → filter: Leads → all, Appointments → appointment_set,
Applications → qualified + appointment-set, Sales → closed_won.

- **`routes/leads.py`** — added an `applications` composite to `_API_TO_DB_STATUSES`
  (`qualified` + `appointment-set`); the list endpoint already handled multi-value via an IN clause.
  Verified counts match the funnel (applications 108, appointment_set 81, closed_won 3).
- **`leads/page.tsx`** — funnel bars are buttons (hover lift + focus ring) wired to a stage→filter map;
  the status dropdown gains an "Applications (qualified + booked)" option so it stays in sync; clicks
  scroll to the table.

`tsc` + ESLint clean, `next build` passes.


### Changed — Sales Funnel Overview restyled to the mockup + Avg Deal Value wired

Restyled the funnel on /leads to match the design: centered, **tapering** stage bars (width ∝ count,
floored for legibility) with the count + stage label + step-conversion % **inline inside each bar**,
centered ▼ connectors, and a right rail showing **Overall Conv.** ("Lead to sale") and **Avg Deal
Value** ("Per closed sale", green). Was previously left-aligned gray-track bars with Avg Deal Value
showing "—".

- **`repositories/sales_stats.py`** + **`schemas/leads.py`** — KPIs gain `avg_deal_value`: avg
  `closed_sales.amount_collected`, range-scoped via the sale's lead `entry_date`. closed_sales.lead_id
  holds the raw WGR id, so it joins on `leads.external_id` (not the CI UUID).
- **`leads/page.tsx`** — `SalesFunnel` rewritten to the tapering layout; rail wired to `avg_deal_value`.

Verified: all-time Avg Deal Value $5,680 (71 sales); range-scoped (current week shows $0 when no sales
entered that week). `tsc` + ESLint clean, `next build` passes.


### Fixed — "This Week" KPI counted sync date, not entry date

Audited the three lead KPIs. **Conversion Rate** and **Active Applications** were correct (right math,
consistently range-scoped). **"This Week"** was the odd one — it counted `created_at` (sync time), which
bunches every backfilled row into the sync window (it showed 164, but `created_at` only spans the
Jun 17–28 sync), disagreeing with the page's entry-date basis.

- **`repositories/sales_stats.py`** — `leads_this_week` now counts `entry_date >= today - 7 days` (real
  funnel entries in the last 7 days), down from 164 → **127**. Still a fixed rolling 7-day window (not the
  selected range). Conversion Rate / Active Applications unchanged.
- **`leads/page.tsx`** — subtitle "Last 7 days" → "Entered, last 7 days".

Verified: This Week 127, Conversion 0.03%, Active Applications 108. `tsc` + tests + `next build` pass.


### Fixed — "Total Leads" KPI showed the range count but was labeled "All time"

After the entry-date range work scoped the report numbers, the "Total Leads" card kept its "All time"
label but displayed the range-scoped count (e.g. 107 for the default current-week range instead of
11,721). Now the card shows the true all-time total as its headline with the in-range count as a
subtitle, so both numbers are visible and honest.

- **`repositories/sales_stats.py`** + **`schemas/leads.py`** — KPIs gain `all_time_total` (an unscoped
  `COUNT(*)`) alongside the range-scoped `total_leads`.
- **`leads/page.tsx`** — Total Leads card value = `all_time_total`, subtitle = "All time · N in range".
  (The Source donut's center total stays `total_leads` — correct, since its segments are range-scoped too.)

Verified: current-week range → headline 11,721 / subtitle "107 in range"; no range → both 11,721.
`tsc` + ESLint clean, `next build` passes.


### Added — hover tooltips on the Lead Volume chart points

Hovering a point on the "Lead Volume — Last 8 Weeks" chart (/leads) now shows its value and week
label in a small tooltip, with the point enlarging/highlighting. Implemented in
**`leads/page.tsx`**: a hovered-index state, forgiving invisible hit-area circles per point (r=14)
that drive it, an in-SVG tooltip box clamped to stay inside the chart, plus a native `<title>` per
point for accessibility/touch. The chart's `aria-hidden` was removed and replaced with a proper
`role="img"` label. `tsc` + ESLint clean, `next build` passes.


### Changed — Lead Volume chart now follows entry_date + the selected range

The "Lead Volume — Last 8 Weeks" chart on /leads bucketed on `created_at` (sync date) and was anchored
to "now", ignoring the entry-date range. Now it buckets on **`entry_date`** and the 8-week window ends
at the **selected range's end** (`entry_to`), falling back to today when unset — so it stays a real
8-week trend while following the entered date, consistent with the funnel/KPIs.

- **`repositories/sales_stats.py`** — lead-volume query rewritten to bucket on `entry_date` relative to
  an anchor (range end or today); the newest bar reads "Now" only when the anchor is actually today
  (else "Wk 8"). Removed the now-unused `_week_label` helper.
- **`leads/page.tsx`** — chart header gains a "by entry date" subtitle; it already re-fetched on range
  change (shares the stats payload).

Verified: current-week anchor shows the 8 weeks of entry-date volume up to this week; a past range end
anchors there with no misleading "Now". `tsc` + ESLint clean, `next build` passes.


### Added — date range on Sales Funnel Overview (scoped by entry_date)

The Sales Funnel (and the KPIs/source breakdown) were always "All time" and ignored the date filter,
so they could disagree with the table. Now the leads page's "Entered" date-range picker drives the
**report** numbers too — funnel, conversion, active applications, source breakdown — all filtered on
**`entry_date`** (the lead's actual funnel-entry date, not created/sync date). Defaults to the
**current week** (Mon–Sun) instead of all-time; clearing filters reverts to all-time.

- **`repositories/sales_stats.py`** — `compute_lead_stats(date_from, date_to)` adds an `entry_date`
  range clause to the total/funnel/conversion/active-apps/source queries (dates parsed to `date`
  objects; bad input ignored). The 8-week sparkline + "This Week" KPI stay rolling-window metrics.
- **`routes/leads.py`** — `GET /leads/stats` takes `entry_from` / `entry_to` (same param names as the
  list) and passes them through.
- **`leads/page.tsx`** — entry range defaults to the current week via the existing calendar pickers;
  the stats fetch re-runs on range change; the funnel header now shows the active range
  ("Jun 22 – Jun 28, 2026 • by entry date") instead of "All time".

Verified end-to-end: current week → Leads 107 / Appointments 9 / Applications 11; all-time →
11,721 / 81 / 108 / 3. `tsc` + ESLint clean, `next build` passes.


### Fixed — Sales Funnel (and KPIs) counted 0 appointments/applications/sales

The funnel showed leads with "Appointment Set" status as 0 Appointments. Root cause: WGR's
`pipeline_stage` arrives Title-Cased (`Appointment Set`, `Applied`, `Closed`, `Lead`) and `map_lead`
stored it raw, but the funnel/KPI SQL in `sales_stats.py` (and `routes/leads.py::_DB_TO_API_STATUS`)
match CI's canonical lowercase-hyphen vocabulary (`appointment-set`, `qualified`, `sale`, `new`) — so
nothing matched and every downstream stage counted 0.

- **`services/wgr_sync/mapping.py`** — new `map_lead_status` normalizes WGR `pipeline_stage` →
  canonical CI status (`Appointment Set`→`appointment-set`, `Applied`→`qualified`, `Closed`→`sale`,
  `Lead`→`new`; unknown values pass through lowercased; blank→None). `map_lead` now uses it.
- **Backfill** — one-time UPDATE applying the same mapping to existing leads (817 rows changed). The
  funnel now reads **Leads 11,721 → Appointments 81 → Applications 108 → Sales 3**, and the KPIs
  (`conversion_rate`, `active_applications` = 108) reflect real data (were 0).
- **`tests/test_wgr_mapping.py`** — `test_map_lead_status` covers the mapping + end-to-end via `map_lead`.

No frontend change needed — the existing `_DB_TO_API_STATUS` layer maps the now-correct DB values to
the UI vocabulary (`appointment-set`→`appointment_set`, `sale`→`closed_won`).


### Changed — lead conversation sender labels + always-visible Tags card

- **Conversations** now label each message **CSR** (outbound — our rep/business) or **Lead** (inbound),
  derived from the direction (verified against real data: outbound carries a `rep_id`, inbound is the
  lead's reply). Positioning was already CSR-right / lead-left; this adds the explicit text label.
- **Tags card** now always renders on the lead detail page (was hidden when empty), with a "No tags yet"
  empty state so the section is discoverable even on leads without tagged calls.


### Added — "jump to page" input on all paginated tables

The shared `Pagination` component now includes a "Go to" page-number input next to Prev/Next, so
users can jump directly to a page instead of clicking through. Local draft state (commits on Enter or
blur, clamped to [1, totalPages]) avoids a fetch per keystroke; it re-syncs to the live page when the
page changes elsewhere (Prev/Next/filter reset). Shown only when there's more than one page. Lands on
all 8 tables that use the component (Leads, Calls, Appointments, Members, Tech SOS, Goals, Insights,
Coaching Calls) via the single `frontend/src/components/ui/pagination.tsx` change.


### Added — per-lead Conversations & Tags on the lead detail page

Surfaced two things the data already supported but the UI never showed.

- **Conversations** — `GET /api/v1/leads/{id}/conversations` returns the lead's omni-channel message
  log (SMS / Instagram + Facebook DMs / email / calls) from `sales_activities`, joined on the lead's
  upstream id (`sales_activities.lead_id` stores the raw `LEAD_xxx` string, matched to
  `leads.external_id` — NOT the CI UUID). `direction` derived from the `activity_type` suffix.
  The lead detail page renders it as a chat timeline (outbound right, inbound left, channel pills).
  Verified: lead Carii returns 55 messages across email/sms/phone in order. No sync change needed.
- **Tags** — `GET /api/v1/leads/{id}/tags` aggregates tags via `lead → calls → insights →
  insight_tags`, distinct tags by frequency. Rendered as accent pills on the lead detail page.

### Fixed — WGR sync dropped `calls.lead_id`, breaking lead→tag traceability

WGR `calls` carry `lead_id` (213/213) but `map_call` never copied it, so all 214 CI `calls.lead_id`
were NULL and the `lead → calls → insights → insight_tags` chain (needed for per-lead tags) was
broken. Fixed in **both** sync paths so an incremental run can't re-NULL what the backfill fixes:

- `services/wgr_sync/mapping.py` — `map_call` now carries `_wgr_lead_id` (mirrors `map_appointment`).
- `services/wgr_sync/upsert.py` — new `sync_calls` resolves `_wgr_lead_id` → CI lead UUID per batch;
  removed calls from `_NATIVE_PLAN`, called before insights in `sync_all`.
- `services/wgr_sync/bulk_load.py` — new `_load_calls` does the same for the backfill CLI path.
- Ran `scripts/backfill_wgr --yes`: `calls.lead_id` now 213/214 populated; **55 leads** reach tags
  (was 0). CI `Call.lead_id` column already existed — no migration.

`tsc` + ESLint clean, `next build` passes, existing WGR tests green.


### Fixed — /leads Source Breakdown donut rendered blank for a single source

The donut built each slice as an SVG arc (`A`) wedge. A single source at 100% (the live data — all leads currently come from `wgr`) has coincident start/end points, so the arc path collapsed and the donut showed **nothing**. Two smaller bugs compounded it: real integration sources (`wgr`, `facebook_ads`, …) aren't in the enum-keyed `SOURCE_COLORS`/`SOURCE_CONFIG`, so they fell back to gray with the raw lowercase label.

- **`frontend/src/app/(app)/leads/page.tsx`** — `SourceDonutChart` now renders a plain stroked ring when there's a single ≥99.95% segment (arc wedges only for 2+ sources); colors unknown sources from a hashed fallback palette (stable per source) instead of all-gray; and labels them via the existing `resolveSource` prettifier (`wgr` → "WGR"). Added a "No source data" legend fallback. The all-`wgr` donut now renders a solid green ring labeled "WGR — 100%".

`tsc` + ESLint clean (no new warnings), `next build` passes.


### Removed — /sales page (duplicate of /leads); now redirects there

`/sales` and `/leads` had converged on the same screen-3 "Leads Dashboard" — same `compute_lead_stats` aggregation (KPIs, 8-week lead volume, source breakdown, funnel) and a leads table. `/leads` is the more complete implementation (adds filtering, search, sort, pagination, and clickable row → `/leads/[lead_id]` detail), so it's the canonical page.

- **`frontend/src/app/(app)/sales/page.tsx`** — reduced to a server-side `redirect("/leads")` (mirrors `app/page.tsx`'s redirect pattern) so any existing `/sales` links keep working instead of 404ing.
- **`frontend/src/components/layout/sidebar.tsx`** — dropped the "Sales Overview" nav entry; "Leads" remains under Sales.
- Left untouched: the `GET /sales/summary` backend endpoint (harmless, still serves the same data) and `header.tsx`'s `startsWith("/sales")` action-button rule (load-bearing for `/sales-calls` / `/sales-director`).

`tsc` + ESLint clean (no new warnings), `next build` passes — `/sales` is now a 147 B redirect stub.


### Added — tokenized gold accent theme + Dashboard (screen 1) mockup fidelity

The app's accent was hardcoded indigo (`indigo-*`) in 245 places across 36 files, while the mockup (`webapp-mockup.html`) uses gold/amber as the product accent. Replaced the scattered hardcoding with a single themeable token system and switched the active accent to the mockup's gold.

- **`globals.css`** — new `--accent-50…900` CSS-var scale (mapped to Tailwind's amber values per the mockup). `--brand*` now alias the accent scale. **Re-theming the whole app is a one-file edit** to these vars.
- **`tailwind.config.ts`** — new `accent` color scale resolving through the CSS vars (`bg-accent-600`, `text-accent-500`, `ring-accent-300`, …); `brand` token re-pointed at the vars.
- **Migration** — every `indigo-N` utility → `accent-N` (same weight) across all 36 files, plus 30 hardcoded `#6366F1` hexes (inline styles / timeline + chart colors) → gold. Department colors (green/blue/orange) intentionally unchanged. Zero `indigo` references remain.
- **Dashboard (screen 1)** restyled to match the mockup: department cards are now bold gradient-filled white-text cards (was white + colored border) with the corner-circle accent; the Central Intelligence widget uses the dark amber→gray gradient with gold accents and glass recommendation cards (was light indigo); 4-col KPI grid; `1fr / 380px` bottom layout; gold sparkline highlight. Live data wiring and the schedule-brief / weekly-focus extras preserved.
- **Dark sidebar** to match the mockup (was light/white). Tokenized the same way as the accent: new `--sidebar-*` CSS vars (`bg #1F2937`, hover `#374151`, muted text, gold active) + a `sidebar` Tailwind color scale, so the whole sidebar re-themes from one place. Active nav item is now a uniform gold left-bar + gold-tinted pill (was per-department colored pills); logo mark and user avatar use the gold gradient; department section labels muted to read on dark.
- **Sidebar Expand all / Collapse all** — one control toggles every collapsible nav section + nested group at once. Open-state was lifted out of the individual `SectionNode`/`NavGroupNode` (local `useState`) into the `Sidebar` as a single id `Set`, so the control can drive them together; the label flips between "Expand all" and "Collapse all" based on whether everything's open. Existing behavior preserved: navigating still auto-opens the section/group containing the active page (union with current open-state, so manual toggles aren't clobbered).
- **Smooth sidebar collapse/expand animation** — sections and nested groups now glide open/closed (height + opacity) instead of popping. New `Collapsible` wrapper uses the grid-rows `0fr→1fr` technique (no fixed height / JS measurement; children stay mounted so it animates both ways); applies to individual toggles and the Expand-all/Collapse-all. Added a global `prefers-reduced-motion` guard so these transitions (and existing pulse/spin animations) collapse to near-instant for users who request reduced motion.

Verified: `tsc` clean, ESLint clean, and a full `next build` confirms the var-backed `accent-*` utilities compile.


### Added — pagination + records-per-page (default 20) across all record tables

Most tables fetched only the first N rows (hardcoded 50–100) with no way to page through the rest, and limits were inconsistent per page. The backends already supported pagination (they returned `total` and accepted `page`+`per_page`/`limit`); the frontend just never wired the navigation. Added a single shared control and rolled it out.

- **`frontend/src/components/ui/pagination.tsx`** (new) — shared `Pagination` molecule: Prev/Next + "Page X of Y" + a **rows-per-page selector (20 / 50 / 100, default 20)** + an "a–b of N" range readout. Presentational; callers pass normalized `(page, total, pageSize)` so it works across the differing endpoint conventions.
- **`frontend/src/hooks/use-pagination.ts`** (new) — `usePagination(storageKey)` owns page + pageSize, **persists the size choice per table in localStorage** (survives refresh), snaps to page 1 on size change, and exposes `resetToFirstPage()` for filter changes.
- Wired into: Calls (shared `CallsTable` → All Calls + Sales Calls), Leads, Appointments, Members, Tech SOS, Goals (table view only — board view unchanged), Insights (replaced its bespoke `PaginationBar`, added the size selector), Coaching Calls. Each sends real `page`/size to its endpoint, reads `total`, and resets to page 1 when filters/search/sort change. Card/stat grids (Market Signals, email/social/ads) were intentionally left out — they aren't row tables.

Backend unchanged — existing `per_page` (≤200) / `limit` (≤100) caps cover 20/50/100. Pagination determinism verified against the DB (the calls query's `ORDER BY … , id ASC` tiebreaker gives disjoint pages).

### Fixed — /sales-calls hid 116 Outbound calls

The Sales Calls page locked its call-type filter to `Sales,Discovery`, written (commit `f27e3fc`) before the WGR sync began importing calls. WGR passes `call_type` through verbatim with no normalization, so the client's real data is 116 `Outbound` + 97 `Discovery` + 1 `Sales` (214 total, **zero** soft-deleted — verified against the DB). The lock silently excluded all 116 `Outbound` rows, so they looked "missing" from the page even though they were present and queryable everywhere else (incl. the All Calls page).

- **`frontend/src/app/(app)/sales-calls/page.tsx`** — lock widened to `Sales,Discovery,Outbound`. The page now matches all 214 live calls. Upload widget stays `callType="Sales"` (new uploads are still Sales); only the list filter changed.

### Added — on-demand data-freshness check (endpoint + Integrations panel)

Answers "how do I know the data is up to date?" without reasoning about the beat schedule. All scheduled data refreshes via Celery beat, which only fires when the worker/beat are running — so after an end-of-day stop, data is frozen until they restart. This makes that observable on demand.

- **`backend/app/services/freshness.py`** — catalog of every scheduled source with its expected cadence (mirroring `tasks/celery_app.py`) and where its last-run timestamp lives: `integrations.last_synced_at` (Mailchimp, Instagram, Facebook, GHL, Google Workspace), the latest `sync_log` row (WGR), or `MAX(updated_at)` on the results table for tasks that record neither (funnel_stats, market_signals). Pure `classify()` flags a source `stale` past 3× its cadence, `unknown` if never run.
- **`backend/app/routes/freshness.py`** — `GET /api/v1/freshness` (auth'd, read-only — does NOT trigger a sync). Returns per-source verdicts plus a worst-wins `overall`. Also `POST /api/v1/freshness/wgr/sync` — enqueues an on-demand **incremental** WGR pull (`sync_wgr.delay()`, `since=None`, same as the hourly job; idempotent upsert). Returns `queued=false` with an honest message when `client_sync_enabled` is off or the broker is down, rather than a no-op task id. And `GET /api/v1/freshness/wgr/sync/{task_id}` — polls the task's Celery state into a single `running` boolean; resolves Celery's ambiguous `PENDING` (unknown vs. queued) via a `queued_seconds_ago` giveup window so a stale id can't spin forever.
- **`frontend/.../integrations/freshness-panel.tsx`** — "Data freshness" card at the top of the Integrations page with a Check-now button; renders each source's verdict pill, age, and last-run time. The WGR row has a **"Sync now"** button that triggers the on-demand pull. The running state is **durable across refresh/navigation**: the task id + queued time are persisted in `localStorage`, re-hydrated on mount, and polled until terminal — driving a spinner on the button plus an always-visible "WGR sync in progress…" banner. On completion it toasts the row count (or error) and auto re-checks freshness so the timestamp updates.
- **`backend/tests/test_freshness_classify.py`** — covers the verdict logic + roll-up (cadence-aware staleness, grace boundary, naive-tz tolerance).

### Fixed — WGR backfill silently dropped market_signals with orphan call FKs

`market_signals.example_call_id` is a real FK to `calls` (ON DELETE SET NULL). WGR signals can reference a call CI filtered out (`TEST_`) or hasn't synced yet, so the ref is orphaned in CI. The async sync path (`upsert.sync_market_signals`) nulls orphan FKs before insert via `_null_orphan_fks`, but the **sync bulk-load path** (`bulk_load._load_market_signals`, used by the `scripts/backfill_wgr` CLI) had no equivalent — the FK violation aborted the whole `execute_values` batch and those rows never landed, silently.

Surfaced during a post-backfill WGR↔CI sanity check: CI held 340 market_signals vs WGR's 348; all 8 missing rows referenced one orphan call (`CALL_LEADhphcQ5wt_20260623_…`).

- **`backend/app/services/wgr_sync/bulk_load.py`** — `_load_market_signals` now pre-loads CI `calls.id` and nulls any orphan `example_call_id` via the `_load_table` `inject` hook, mirroring `_load_insight_tags`' orphan-tolerant policy. Backfill now lands all 348 (idempotent; re-run = 348, no error).

### Changed — `best_use_case` constrained to a disciplined, extensible vocabulary

`best_use_case` on insights had sprawled to 240 distinct values across 303 rows (213 singletons) — slash-combos (`Instagram Reel / Email subject line` ×11, plus 3 other spellings) and full sentences (`Email nurture sequence for cold leads who are currently satisfied`). Cause: the analyzer prompts only *suggested* example values, so the model treated it as free text. The field is meant to drive downstream content-pipeline routing and in that state couldn't.

Decision: a **seed vocabulary that stays disciplined but is open to growth** — prefer the list, coin a new value only when none fits, under a strict shape rule.

- **Shared taxonomy module** (`backend/app/prompts/_taxonomy.py`, new) — single source of truth: `BEST_USE_CASE_SEED` (16 single-purpose values) + `normalize_best_use_case()` which enforces the *shape* rule (no slashes, ≤3 words) on write. Membership is not required — clean new single-purpose values pass; only sprawl-shaped values are coerced to null.
- **Analyzer prompts** (`backend/app/prompts/call_analyzer_v1.py`, `coaching_analyzer_v1.py`) — `best_use_case` guidance rewritten from open "e.g." examples to "choose the single best from this list; only if none fits, coin ONE new value — Title Case, ≤3 words, single-purpose, no slashes, no sentences." Seed list injected from the shared module so prompt and validation can't drift.
- **Write path** (`backend/app/tasks/call_analyzer.py`) — `_write_insights` runs `normalize_best_use_case()` on every persisted value, so the shape rule holds even if the model disobeys.
- **Seed vocabulary** is now 18 values — `Brand Positioning` and `Lead Magnet` were promoted from the backfill below (clean values Opus coined when no seed fit).
- **Backfill of existing rows** (`backend/scripts/remap_best_use_case.py`, new) — collapsed the 240 sprawled values to **17** via one batched Opus call over the distinct values (dry-run writes the proposed map to `.tmp/best_use_case_remap.json` for review; `--apply` reads the reviewed file and writes, no re-call). 290 rows updated, idempotent, CI mirror only. Result: 90 `Email Nurture`, 71 `Instagram Reel`, 43 `Instagram Post`, … — no slash-combos or sentences remain.

### Added — sortable/filterable calls table with a Date Added column

The Sales Calls and All Calls pages were flat card lists with no way to sort, filter, or see when a call was ingested. Replaced both with a shared sortable table.

- **Backend** (`backend/app/routes/ci.py`, `backend/app/schemas/ci.py`) — `GET /ci/calls` gains `sort_by` (whitelisted: date, created_at, call_type, call_result, call_owner, source) + `sort_dir`, plus `call_result`, `source`, and `search` (ILIKE on call_id/owner) filters. `created_at` ("Date Added") added to `CallSummary`. Sort column is whitelisted against injection with a stable `id` tiebreaker.
- **Frontend** — new shared `CallsTable` (`frontend/src/components/calls/calls-table.tsx`): sortable headers (▲/▼/↕), a filter bar (search · type · result · source · call-date range · Clear), a **Date Added** column alongside Call Date, plus Owner / Insights / Source / transcript columns. All sorting and filtering is server-side.
- **All Calls** (`frontend/.../calls/page.tsx`) — uses the table with the Type column + filter shown.
- **Sales Calls** (`frontend/.../sales-calls/page.tsx`) — uses the table locked to `Sales,Discovery` (Type filter hidden), keeps the upload widget, and refetches via a `refreshKey` bump after a successful upload.

### Fixed — inconsistent insight typography (snake_case / lowercase taxonomy values)

Insight taxonomy values were stored in mixed casing, so some calls showed `buying_signal` / `value_clarity` / `structural` while others showed `Goal` / `Skills & Competency`. Two causes: the CI analyzer prompt emitted snake_case, and WGR stores `pain_layer` lowercase. Fixed at all three layers so stored, synced, and displayed values agree:

- **Frontend** (`frontend/.../sales-calls/[call_id]/page.tsx`) — `humanizeLabel()` Title-Cases taxonomy values at render (insight_type, signal_family, signal_strength, pain_layer). Display-only via a new `displayTransform` prop on `InlineTextEdit` — the edit input still shows and saves the raw value. Already-human values (with spaces or internal caps) pass through untouched; free-text fields (signal, quotes) are never transformed.
- **Analyzer prompts** (`backend/app/prompts/call_analyzer_v1.py`, `coaching_analyzer_v1.py`) — enum guidance + mock output rewritten to Title Case (`Pain`/`Goal`/`Trigger`, `Strong`/`Moderate`/`Weak`, `Verbatim`/`Near Verbatim`), aligning future CI analyses with WGR's vocabulary.
- **WGR sync** (`backend/app/services/wgr_sync/mapping.py`) — new shared `humanize_label()` normalizes the 6 taxonomy fields on ingest (`_INSIGHT_TAXONOMY_FIELDS`), so re-syncs keep CI's mirror normalized rather than reverting `pain_layer` to lowercase.
- **Backfill** (`backend/scripts/backfill_insight_taxonomy_case.py`) — one-time, idempotent normalization of **157 existing insight rows** (152 lowercase `pain_layer` + the 5-field CI-vocab call). Dry-run by default; `--yes` to apply. Touches CI's mirror only, never upstream WGR.

### Added — CI analyzer now generates content ideas (closes Pipeline B gap)

`analyze_call` extracted insights but never created content ideas — every content idea in CI came mirrored from the client's (WGR) pipeline, so re-analyzing a CI-native call produced insights but zero content. Closed the gap so a single analysis pass produces both.

- **New prompt** (`backend/app/prompts/content_idea_generator_v1.py`) — a Claude Sonnet 4.6 "content strategist" that converts the just-extracted insights into 0–8 shootable briefs (16 fields each: hook, premise, teaching point, CTA, audience, format, platform, score…). Selects only *marketable* insights rather than mechanically converting all of them.
- **Analyzer wiring** (`backend/app/tasks/call_analyzer.py`) — after writing insights, `analyze_call` feeds the persisted insights (with their new IDs) to `_call_claude_content_ideas` → `_write_content_ideas`. Content ideas link back to real insight rows; dangling `insight_id`s are NULLed (FK is SET NULL). Generation failure is non-fatal — the call is still analyzed with its insights. Re-analyze now clears this call's prior insights **and** content ideas before regenerating. Mock-mode path included for tests/no-key.

### Added — provenance badge (WGR-synced vs CI-analyzed) on calls

Calls and their insights/content ideas come from two pipelines — mirrored from the client's WGR DB (`source='wgr'`) or analyzed natively in CI — and the UI didn't distinguish them. Surfaced `Call.source`:

- **Backend** — `source` added to `CallSummary` + `CallDetail` schemas and populated in the list/detail endpoints; `POST /ci/calls` now stamps `source='ci_upload'` on locally-uploaded calls.
- **Frontend** — a **WGR** / **CI** tag on each row (Sales Calls + All Calls) and a full **WGR-synced** / **CI-analyzed** pill in the call-detail header, with tooltips explaining the difference.

### Added — full content-idea briefs on the call detail page

The call-detail page rendered each content idea as just `content_format · priority_level` (e.g. "Reel · High"), hiding the 17 other fields the analyzer generates — the actual brief (hook line, premise, teaching point, CTA, source quote, audience, repurpose options).

- **Backend** (`backend/app/schemas/ci.py`, `backend/app/routes/ci.py`) — new `ContentIdeaDetail` schema (all 19 fields) + `_content_idea_detail()` helper; `GET /ci/calls/{id}` now embeds it instead of the 5-field `ContentIdeaBrief`. No DB change — every content_ideas column is already fully populated (234 rows).
- **Frontend** (`frontend/.../sales-calls/[call_id]/page.tsx`) — new `ContentIdeaCard` renders each idea as an always-expanded shootable brief: the hook line gets a highlighted callout, then premise / teaching point / CTA / audience / repurpose / trigger insight in a two-column grid, with the sparking prospect quote underneath. Header shows format · platform · angle · priority · score · status.

### Added — full insight analysis on the call detail page (expandable)

The call-detail endpoint returned only a 4-field insight brief (`insight_type`, `signal_family`, `signal`, `raw_quote`), so the 16 deeper analysis fields per insight — the marketing/psychology gold — never reached the UI despite being in the DB.

- **Backend** (`backend/app/routes/ci.py`, `backend/app/schemas/ci.py`) — `GET /ci/calls/{id}` now embeds the full `InsightDetail` payload (was `InsightBrief`). Extracted a shared `_insight_detail()` helper, also used by `GET /ci/insights/{id}`, so both surface the same complete shape. No DB/repository change — `find_by_call` already returned full ORM rows.
- **Frontend** (`frontend/.../sales-calls/[call_id]/page.tsx`) — each insight now has a **Show analysis** toggle that expands a card grouping the deep fields into **Psychology** (real problem, emotional driver, core fear, false belief, structural obstacle, identity signal, pain layer) and **Marketing** (marketing translation, hook angle example, buying trigger, objection created, best use case). Empty fields are hidden; the 4 summary fields stay inline-editable. Signal strength now shows as a pill. Insight markup extracted into an `InsightRow` component.

### Fixed — Sales Calls page showed no calls after WGR rebase; added All Calls page

The `/sales-calls` page filtered for `call_type=Sales` (exact match), but every WGR-synced call is typed `Discovery` (81) or `Outbound` (77) — so the page rendered its empty state despite 158 processed calls in the DB.

- **Backend** (`backend/app/routes/ci.py`) — `GET /ci/calls`'s `call_type` filter now accepts a comma-separated list (`Sales,Discovery`) via `IN (...)`. A single value still works as an exact match (backward compatible).
- **Sales Calls** (`frontend/.../sales-calls/page.tsx`) — now requests `call_type=Sales,Discovery` → shows the **81** Discovery calls (plus any future `Sales` uploads). Outbound is intentionally excluded here.
- **All Calls** (new `frontend/.../calls/page.tsx` + sidebar entry under Sales) — lists every call type with no filter (**158**), each row tagged with its `call_type` pill. Reuses the existing `/sales-calls/[call_id]` detail page.

### Added — surface social_comments: Recent Comments card + RAG embedding

The 10,395 synced `social_comments` had no surface. Wired them up — but ~98% are bare GHL keyword triggers ("Info"/"Agent" typed to fire a DM funnel), so both surfaces keep only the **substantive** comments (real voice-of-customer).

- **UI** (`frontend/src/app/(app)/marketing/social/page.tsx`) — new **Recent Comments** card on `/marketing/social` showing recent genuine comments (platform dot + text + date). `SocialCommentRepository.find_recent_substantive()` excludes trigger words (length > 20 AND not a known trigger phrase); served via a new `recent_comments` field on `GET /social`.
- **RAG** (`backend/app/tasks/embed_backfill.py`) — `backfill_wgr_embeddings` gains a `wgr_social_comment` source using the same substantive filter. **Embedded live: 116 comments** through Voyage (the ~10,279 trigger-word comments are excluded as noise). Now retrievable by the chat agent's knowledge-base search.

### Added — WGR marketing/social mirror (4 previously-empty CI tables wired to real data)

Four CI tables had models + UI but sat empty (the original seed data was cleared in the Phase 1 rebase). Wired them to WGR's real data via the existing sync — read-only from WGR, write only to CI. **Backfilled live:** email_campaigns **2,394**, social_comments **10,395**, instagram_posts **1,000**, insight_tags **752** (+ tag_dictionary **627**).

- `backend/app/models/marketing.py` — added `source`/`external_id` (+ unique) to `SocialComment` for idempotent WGR dedup; new `InstagramPost` model (per-post grain — engagement/reach/reel metrics + creative context like hook/pillar/transcript). Distinct from `SocialStats` (per-period aggregate), which is why instagram_posts gets its own table rather than being forced into social_stats.
- Migration `o6f7a8b9c0d1` (hand-written) — social_comments columns + indexes + unique; new instagram_posts table.
- `backend/app/services/wgr_sync/mapping.py` — `map_email_campaign` (unique_opens/clicks → headline counts; status='sent'), `map_social_comment` (skips empty-text rows; post_id falls back to fb_page_id), `map_instagram_post`, `map_insight_tag`.
- `backend/app/services/wgr_sync/bulk_load.py` + `upsert.py` — both sync paths wired. **FK handling discovered live:** (1) `insight_tags.tag → tag_dictionary.tag` — WGR doesn't enforce it and its tag_dictionary is empty, so a new seed step derives CI's dictionary from the 627 distinct tags actually used before loading; (2) `insight_tags.insight_id → insights.id` — 51 tags reference insights CI didn't sync, so orphan insight_ids are nulled (kept the tag), same policy as strike evidence. `email_campaigns` uses a PARTIAL unique index (like leads) so its ON CONFLICT repeats the WHERE predicate; social_comments/instagram_posts use full constraints.
- `backend/app/services/wgr_sync/reader.py` — watermarks for incremental hourly sync (email_campaigns/instagram_posts on `synced_at`, comment_events on `created_at`).
- `backend/tests/test_wgr_mapping.py` — added `test_map_marketing_social` (18 checks). All mapping checks pass.
- **Surfacing:** the email page reads `email_campaigns` directly → shows the 2,394 real campaigns immediately. social_comments feed VoC/RAG + chat (no dedicated page). instagram_posts is in CI + embeddable but not yet wired to a route — UI is a follow-up.

### Added — clickable column sorting on the leads table

The leads table headers were static text; the backend already supported `sort_by`/`sort_dir` but nothing drove it. Headers are now click-to-sort.

- `frontend/src/app/(app)/leads/page.tsx` — new `SortableHeader` component with an active ▲/▼ indicator (idle ↕); `sortBy`/`sortDir` state (defaults `entry_date` desc, matching the API). Clicking a column flips direction; a new column starts desc. Wired into the fetch as `sort_by`/`sort_dir` + effect deps. Name → `name`, Source → `source`, Date Added → `entry_date`, Status → `status`. **Score** stays a plain header (no DB column — it's derived from status, which the Status sort already orders by).
- `backend/app/routes/leads.py` — list `ORDER BY` now appends `NULLS LAST, id ASC` so null entry-dates don't dominate the top when sorting desc, and pagination is deterministic on ties.
- Verified live: all four sort columns run in both directions. Note: sorting by Source is a visual no-op — every WGR lead is `source='wgr'` in CI (the original platform lives in utm/notes), so there's nothing to reorder.

### Added — entry-date range filter on the leads table

The `/leads` toolbar had a dead "Date range..." free-text input that was collected into state but never sent to the API. Replaced it with a real entry-date range filter, wired end-to-end on the now-persisted `entry_date`.

- `frontend/src/app/(app)/leads/page.tsx` — `FilterBar` now renders two `<input type="date">` pickers ("Entered" from–to) with min/max cross-bounding; page state `dateRange` → `entryFrom`/`entryTo`, both sent as `entry_from`/`entry_to` query params and added to the fetch effect deps + clear-filters reset.
- `backend/app/routes/leads.py` — `list_leads` accepts `entry_from`/`entry_to` (YYYY-MM-DD), filtering on `entry_date`. New `_parse_date` helper swallows invalid/half-typed dates (degrades to no-filter rather than 422). Verified live: 2026-06 range → 511 leads, since-2025 → 9,372, pre-2021 → 29.

### Fixed — /leads crash on null source/status + persist WGR entry_date

Two issues surfaced once real WGR leads (the ~11.6k backfilled rows) flowed into the UI.

- **Fix — `/leads` crash (`Cannot read properties of null (reading 'split')`):** WGR stores most leads with a null `pipeline_stage` (94%) and null source (85%); CI's `Lead` type wrongly assumes these are never null. `resolveStatus(null)`/`resolveSource(null)` fell through to `_humanise(null)` → `null.split()`. `frontend/src/app/(app)/leads/page.tsx`: `_humanise` now returns `"Unknown"` for null/empty, and both resolvers skip the config lookup when `raw` is falsy and accept `string | null | undefined`. The lead-detail page already guarded this.
- **Added — persist `entry_date`:** the list showed `created_at` (CI sync time), not when the lead actually entered the funnel — so most leads displayed the sync date. WGR carries a real `entry_date` per lead that the Phase 4 sync dropped. Now persisted end-to-end:
  - `backend/app/models/operational.py` — new `Lead.entry_date` (Date, nullable, indexed). Migration `n5e6f7a8b9c0` (hand-written; autogenerate emits spurious index drops on this project).
  - `backend/app/services/wgr_sync/mapping.py` — `map_lead` now carries `entry_date`, so the hourly sync populates it going forward.
  - `backend/app/routes/leads.py` — list + update responses serve `entry_date or created_at` as the lead's `createdAt`; `entry_date` added to `_SORTABLE_COLUMNS`. Detail response adds a dedicated `entry_date` field; the detail page shows an "Entered" row above "Created".
  - `backend/scripts/backfill_lead_entry_date.py` (new) — one-shot, idempotent, pooler-safe psycopg2 backfill (`--dry-run` / `--yes`) that updates WGR-sourced CI leads from WGR. **Run live:** 11,592 of 11,599 WGR leads populated (7 have no upstream date); entry dates span 2019→2026.
  - `backend/tests/test_wgr_mapping.py` — added entry_date checks; all mapping checks still pass.

### Added/Fixed — WGR sync feeds RAG + first end-to-end run fixes (Phase 7)

Running the now-enabled hourly sync against live data for the first time surfaced three blockers (the sync had never executed past the backfill). This wires synced rows into the RAG corpus and fixes the bugs that aborted every run.

- **RAG-everything wiring** (`backend/app/tasks/wgr_sync.py`): after a successful `sync_wgr` with rows synced, chains `backfill_wgr_embeddings` + `backfill_insights_embeddings` via `.delay()`. Without this, synced WGR rows were queryable by SQL but invisible to chat — the vector store froze at the Phase 5 snapshot. The backfills full-scan and dedup on `content_hash` (only new/changed rows reach Voyage); skipped entirely when nothing synced. Verified live: an 8-call incremental sync enqueued exactly 8 `wgr_call_analysis` rows, 0 re-embeds.
- **Fix — orphan FK aborts (Phase 4 latent bug):** WGR child rows reference parents CI filtered out (TEST_ calls) or outside the watermark window, tripping FKs and aborting the whole sync transaction. New `_null_orphan_fks` helper nulls nullable / `ON DELETE SET NULL` columns whose parent isn't in CI (schema's intent), applied to `market_signals.example_call_id` and `sales_strike_evidence.call_score_id`. `sales_strike_evidence.strike_id` (NOT NULL) instead **skips** parentless rows. Live run: 18 + 14 orphan refs nulled, 0 rows wrongly dropped.
- **Fix — `Unconsumed column names: activity_metadata` (Phase 4 latent bug):** `_on_conflict_upsert` built the INSERT from `model.__table__` (column names) but received ORM-attribute-keyed dicts; `activity_metadata`→`metadata` and any other attr≠column pair failed. Now remaps attribute keys → column names via the mapper before `.values()`.
- **Fix — masked errors (Phase 6 bug):** the error-`SyncLog` write ran on the already-aborted transaction → `InFailedSQLTransactionError`, hiding the real cause and never recording it. Now `session.rollback()` before writing the error row.
- `backend/tests/test_wgr_orphan_fks.py` (new) — 7 checks on `_null_orphan_fks`. All pass; `test_wgr_watermark` + `test_wgr_mapping` still pass.
- **Verified end-to-end:** full incremental `sync_wgr` completes (680 rows), watermark advances, error path records cleanly, embedding chain enqueues. **Note:** the running Celery worker holds pre-fix code — restart it to pick these up before the `:50` beat tick.

### Added — WGR hourly sync watermark persistence (Phase 6)

The hourly `wgr-sync-hourly` task shipped (Phase 4) but its incremental path was plumbed and not wired: the beat entry called `sync_wgr` with no args, so `since` was always `None` → a **full async re-pull of all ~56k rows every hour** through CI's transaction pooler — exactly the workload `bulk_load.py` went synchronous to avoid. The `sync_log` watermark the docstring promised did not exist. This wires it.

- `backend/app/tasks/wgr_sync.py` — `sync_wgr` now reads the watermark from the most recent successful `wgr_sync` `SyncLog` row (`details->>'watermark'`) and pulls only rows changed since it, minus a 5-minute `WATERMARK_LOOKBACK` (catches rows committed mid-run / clock skew; idempotent upserts make the overlap harmless). The next watermark is captured **before** any WGR row is read. A `SyncLog` row is written on every run — `status='ok'` (advances the watermark, records per-table counts) or `status='error'` (does **not** advance, so the next run re-pulls the same window). `since` arg: `None` = incremental (first run = full backfill), `"full"` = force full, ISO string = manual re-sync from a point. Pure `resolve_since()` extracted for testing.
- `backend/scripts/seed_wgr_watermark.py` (new) — one-time bootstrap seed. Writes a successful `wgr_sync` `SyncLog` row dated `--as-of` (default now), so the first enabled hourly run does a pooler-safe **delta** instead of a full async re-pull. `--show` to inspect; refuses to seed if a watermark already exists.
- `backend/tests/test_wgr_watermark.py` (new) — 11 checks on `resolve_since` (bootstrap-full / incremental-with-lookback / forced-full / manual override). All pass. Existing `test_wgr_mapping.py` still passes.
- **Operational sequence to enable:** (1) merge; (2) `python -m scripts.seed_wgr_watermark`; (3) set `CLIENT_SYNC_ENABLED=true` in the worker/beat env; (4) restart worker + beat. Still open follow-up: confirm new synced rows get enqueued for embedding so the RAG corpus doesn't drift stale.

### Added — RAG ingest of WGR call intelligence (Phase 5)

CI's RAG layer, which held zero business-specific knowledge, now contains the WGR call-intelligence corpus — **1,086 embeddings** in pgvector via the existing Voyage pipeline.

- `backend/app/services/wgr_sync/bulk_load.py` — `_enrich_calls()` backfills CI `calls.transcript_text` (from WGR `sales_call_transcripts`) and `calls.summary` (from `sales_call_analyses.call_summary` + `performance_notes`), joined on call_id. 108 calls enriched. Wired into `run_backfill`.
- `backend/app/tasks/embed_backfill.py` — new `backfill_wgr_embeddings` task enqueues the WGR-sourced text under distinct `source_table` tags (`wgr_call_transcript`, `wgr_call_analysis`, `wgr_call_score`, `wgr_content_idea`, `wgr_business_profile`) so retrieval can filter by kind. Reuses `_enqueue_missing` (content-hash idempotent).
- Backfilled embeddings: insights 296, wgr_call_score 236, wgr_content_idea 234, wgr_call_transcript 168 (chunked from 108), wgr_call_analysis 150, wgr_business_profile 2. Drained through the real Voyage `voyage-3` worker; `embed_pending` now empty.

### Added — WGR → CI sync service + backfill (Phase 4)

CI now loads the client's (Greg/WGR) database into its own tables. **56,169 rows backfilled** across 20 tables with verified fidelity (insights/content_ideas/appointments/sales_activities/webinar/opt_in exact; leads 11,555 after email-dedup; calls 150 after TEST_ filtering).

- `backend/app/services/wgr_sync/` (new package):
  - `mapping.py` — 16 pure WGR-row → CI-kwargs functions. Transforms: phone→E.164, appointment outcome→status enum, rep identity on rep_id only, test-call filtering, blank→None. Covered by `backend/tests/test_wgr_mapping.py` (38 checks, all pass).
  - `reader.py` — read-only WGR reader with per-table watermarks for incremental sync.
  - `upsert.py` — async idempotent upserts (ON CONFLICT) for the hourly incremental task.
  - `bulk_load.py` — **synchronous** psycopg2 `execute_values` bulk loader for the one-shot backfill. Sync was required: sustained async (asyncpg) multi-batch writes hang on CI's transaction pooler; the sync path loads ~56k rows in minutes.
- `backend/app/tasks/wgr_sync.py` + beat entry `wgr-sync-hourly` (gated on `client_sync_enabled`, default off).
- `backend/scripts/backfill_wgr.py` — `--dry-run` (source vs CI counts) / `--yes` (run). Idempotent.
- Dedup strategy: shared-domain tables key on `(source='wgr', external_id)`; WGR-only tables keep WGR's native PK. Data-quality handling: WGR's non-unique `leads.email` collapsed to CI's unique-email constraint; appointments delete-then-insert (no unique index for ON CONFLICT); JSONB columns wrapped via `Json()`, ARRAY columns left native.

### Added — WGR subsystem models + migration (Phase 3)

New CI tables for the WGR subsystems CI never modelled, so Greg's sales/coaching/revenue/funnel data has somewhere to land.

- `backend/app/models/sales.py` (new) — `SalesRep`, `ScorecardCategory`, `CallScore`, `StrikeRule`, `CoachingStrike`, `StrikeAction`, `StrikeEvidence`, `EodReport`, `ClosedSale`, `SalesActivity`. These hold WGR-only data, so they keep WGR's native text PKs (rep_id, score_id, strike_id, …) — sync upserts are idempotent on the natural key. `rep_id` FKs stay within the module; `business_id` is a plain Integer (no cross-table FK to CI's business_profile).
- `backend/app/models/marketing.py` — added `WebinarEngagement` and `OptInEvent` (WGR top-of-funnel).
- `backend/app/models/operational.py` — added `source` + `external_id` to `Call` (provenance + idempotent dedup for WGR-sourced calls; distinct from `transcript_source`).
- Migration `aa7e787e302d` — creates the 12 tables + Call columns. **Hand-edited** to strip ~13 spurious autogenerate ops (it wanted to drop existing hand-crafted partial/GIN/composite indexes and the `uq_leads/uq_email_campaigns` dedup constraints, which the ORM metadata doesn't model). Verified: 12 tables created, existing indexes intact, downgrade/upgrade round-trips cleanly.
- Lock note: had to terminate orphaned `idle in transaction` sessions (from earlier failed pg_dump COPYs) that were blocking `ALTER TABLE calls`. The pooler's short `statement_timeout` makes lock contention fatal to migrations.

### Changed — Re-base CI on the WGR database: clear CI domain data (Phase 1)

First step of making the client's (Greg/WGR) database CI's single upstream. Backed up CI's irreplaceable config/auth tables, then cleared CI's empty/seed-fed domain data so it can be re-sourced from WGR.

- `backend/scripts/clear_domain_data.py` (new) — clears 33 domain/synced/derived tables (leads, calls, insights, content_ideas, market_signals, appointments, social/email/funnel stats, embeddings, google sync, etc.) via **batched DELETE** while preserving config/auth (integrations + encrypted creds, users, business_profile, offers, chat history, audit_log, embedding_budget, tag_dictionary). Explicit CLEAR/PRESERVE allow-lists with a guard that refuses to run if any public table is unclassified; `--yes` required, idempotent.
- Batched DELETE (not TRUNCATE) because CI's Supabase is reachable only via the transaction pooler, which enforces a short `statement_timeout` and ignores per-session `SET` — TRUNCATE's ACCESS EXCLUSIVE lock consistently timed out; 500-row DELETE chunks stay under it.
- Phase 0 backup of the preserve-list tables lives at `backend/.tmp/ci-preserve-backup-*.sql` (gitignored).
- Result verified: all 33 domain tables at 0 rows; integrations (5), offers (7), chat history, audit log intact. Login unaffected (auth is Supabase-side, not app-table-dependent).

### Added — Greg's database × CI analysis report (HTML)

`docs/greg-database-analysis.html` — a self-contained, graphical report analyzing the client's 74-table WGR database (subsystem map, FK-hub ER diagram, end-to-end data-flow pipeline, RAG-corpus inventory), comparing it table-by-table against Central Intelligence's own schema, and ranking nine feature opportunities by value × readiness. Key finding: CI's schema mirrors Greg's domain almost exactly but CI's tables are empty/seed-fed while Greg's are full of real, AI-enriched data — so the highest-leverage moves are RAG-ingesting the call-intelligence stack and backfilling CI's matching tables, not net-new building. Built from parallel read-only data sampling + a full CI codebase inventory.

### Added — Read-only client (WGR) Postgres access + full schema map

The client provided `WGR_DATABASE_URL`, a direct Postgres connection to their project (`mntsbmuxbdnnlnheuwqk`) via the Supabase session pooler. This supersedes the anon key for the client-data sync: full-schema visibility and reliable bulk reads.

- `app/services/wgr_client.py` — strictly read-only Postgres client. Every connection opens with `set_session(readonly=True, autocommit=True)`; only `SELECT`-returning helpers exist (`query`, `iter_rows` paginated, `count`, schema introspection). No write path.
- `app/config.py` — added `wgr_database_url` field.
- `scripts/dump_wgr_schema.py` + `scripts/__init__.py` — introspects the full schema and writes `docs/client-supabase-schema.md` (74 tables, 54 non-empty, full FK graph + per-table columns/types/PKs). Re-runnable.
- **Discovery:** the client DB is **74 tables**, not the 4 the anon key could see — a full sales-and-marketing intelligence platform (CRM, `sales_*` transcripts/analyses/scores, email/Meta/Instagram/webinar marketing, insights). Scope decision: ingest everything non-empty.
- ⚠️ **SAFETY:** `WGR_DATABASE_URL` is the `postgres` role and is *write-capable*. We force read-only on our side; flagged a request to the client for a dedicated read-only role. Documented in `.env`, `config.py`, and the connection doc.

### Changed — Split Supabase: separate projects for auth vs. client data

The client's GHL-mirror Supabase had been dropped into the primary `SUPABASE_URL` / `SUPABASE_ANON_KEY` / `SUPABASE_JWT_SECRET` slots during introspection, which would have made CI verify user logins against the *client's* project. Split them:

- `SUPABASE_*` restored to CI's own project (`iqqobmubutxwhtvpdrnf`) — drives auth (`app/middleware/auth.py`, `app/auth/supabase_client.py`); now agrees with `DATABASE_URL`.
- Client GHL mirror (`mntsbmuxbdnnlnheuwqk`) moved to dedicated, read-only `CLIENT_SUPABASE_URL` / `CLIENT_SUPABASE_ANON_KEY` / `CLIENT_SUPABASE_SERVICE_KEY` vars + `CLIENT_SYNC_ENABLED` master switch (default `false`).
- Added matching `client_supabase_*` / `client_sync_enabled` fields to `app/config.py`.
- Verified: CI auth resolves to its own project (JWKS + GoTrue health `200`), client vars resolve to the mirror, no overlap. Docs updated (`docs/client-supabase-connection.md` §2, `docs/client-supabase-pull-plan.md` §0–1).

### Added — Today's Schedule dashboard brief

A new "Today's Schedule" panel on the dashboard showing the logged-in user's calendar events for today, read deterministically from the already-synced `google_calendar_events` table. No AI, no cache, no migration, no new sync.

- `app/schemas/dashboard.py` — `ScheduleBriefItem` (title, start/end, is_all_day, location, attendees_count, status) + `ScheduleBriefResponse` (items, summary, event_count, calendar_connected, generated_at).
- `app/routes/dashboard.py` — `GET /dashboard/schedule-brief`. Auth-scoped to `current_user` (like `/calendar/events`): queries `google_calendar_events WHERE connected_via_user_id = <user>`, within the `start`/`end` window (default now → +24h), **excludes cancelled events**, capped at 50, ordered by start. `calendar_connected` is derived from the user's `user_integration_credentials` row so the empty state can distinguish "nothing today" from "you haven't connected a calendar." Builds a deterministic one-line summary (count + next event). No cache — the query is cheap and per-user (caching a per-user payload in a shared module dict would leak across users).
- `frontend/src/components/dashboard/schedule-brief.tsx` (new) — sky-accented panel mirroring the weekly-focus pattern (`apiClient.get(..., {silent:true})` + `authLoading`, skeleton, empty, populated). **Timezone-correct:** computes the browser's local day bounds and passes them as `start`/`end`, and renders each event time in the browser's locale, so "today" matches the user's wall clock even though events are stored in UTC.
- `frontend/src/app/(app)/dashboard/page.tsx` — `ScheduleBrief` placed in a 2-column row beside `WeeklyFocus`, with a matching 2-column skeleton.

Verified with zero API cost: endpoint registered, scoped query against live data (cancelled excluded, connected flag correct), empty-state path, tsc clean + next build green.

### Added — CI chat resumes your last conversation on reload

Chat history was already persisted (DB-backed `chat_sessions`/`chat_messages` + a history sidebar; the agent re-hydrates full context on session resume), but the frontend minted a fresh session UUID on every mount — so a page reload dropped you onto a blank "New chat" and you had to re-pick the conversation from the sidebar.

- `frontend/src/hooks/use-chat.ts` — the active `sessionId` is now mirrored to `localStorage` (`ci-chat-session-id`) on every change and restored on mount, so a reload reconnects the WebSocket to the same session (backend re-hydrates the agent's memory). A one-time mount effect re-fetches that session's transcript so the on-screen bubbles reappear too. Guards: only restores when the id came from storage (a true first visit still starts blank, no needless fetch), degrades silently if the stored session was deleted server-side, and doesn't interfere with `startNewChat`/`loadSession`.

No backend changes — the persistence layer was already complete.

### Added — Connect buttons on the /marketing/social Platform Breakdown

Each platform row now reflects real connection state. Connected platforms show live metrics; an **unconnected** platform that has a connect form shows a **Connect →** button linking to `/integrations/{slug}`; platforms not yet wired (TikTok, LinkedIn) show a muted **Coming soon** tag instead of a dead button.

- `app/schemas/social.py` + `app/routes/social.py` — `SocialPlatformMetric` gains `connected` (from the `integrations` table, not merely a seed `social_stats` row) + `provider_status` (registry available/coming_soon); metric fields are now nullable and only populated when connected. The endpoint returns a row for all four display platforms.
- `frontend/.../marketing/social/page.tsx` — the breakdown card renders three states per row: connected → metrics; available + not connected → Connect button; coming_soon → disabled tag.

### Fixed — /marketing/social Platform Breakdown shows live per-platform data

The "Platform Breakdown" card rendered a **hardcoded** `PLATFORMS` array of `"—"` literals and never read any data — so Facebook (and every platform) always showed "—" no matter what synced. The `/social` endpoint also only returned summed totals, with no per-platform rows.

- `app/schemas/social.py` + `app/routes/social.py` — `SocialDataResponse` gains a `by_platform` list of `SocialPlatformMetric` (platform, followers, posts_count, engagement_rate); the GET handler populates it via `repo.find_latest_by_platform` for instagram/facebook/tiktok/linkedin (omitting platforms with no row).
- `frontend/.../marketing/social/page.tsx` — `PlatformMetricsCard` now takes `data` and merges live `by_platform` values onto the display scaffold (icons + order), formatting followers/posts/engagement; falls back to "—" only when a platform has no synced row. The top KPI tiles were already live; this fixes the per-platform breakdown beneath them.

### Fixed — Logout works (and stale sessions no longer strand you on the dashboard)

Clicking sign-out did nothing when the session was already invalid (expired JWT / missing user). `signOut` `await`ed `supabase.auth.signOut()` *before* clearing local state, so when that call threw/hung on an invalid session, execution never reached the token-clear + `setUser(null)` + redirect — the button silently no-op'd.

- `frontend/src/contexts/auth-context.tsx` — wrapped the Supabase sign-out in try/catch; local cleanup (clear token, clear cached user, null the user) + `router.push("/login")` now always run, so logout succeeds regardless of server-side session state.
- `frontend/src/components/layout/auth-guard.tsx` (new) + `frontend/src/app/(app)/layout.tsx` — added a client-side `AuthGuard` that redirects to `/login` once auth finishes loading and the user is null. The Next middleware only guards on navigation; this catches a session going invalid while you're already sitting on a protected page (the "stuck on dashboard" symptom).

### Fixed — Facebook Page Insights metric churn handled gracefully

Meta is deprecating the bare `page_impressions` Page-insights metric through mid-2026 (it now returns `(#100) The value must be a valid insights metric`). `facebook_client.fetch_facebook_stats` now tries `page_impressions_unique` then `page_impressions`, uses whichever the API accepts, and logs Meta's actual error message (via a new `_error_message` helper, also used by `verify()`) instead of a raw traceback. Insights stay best-effort — followers/posts still sync when the impressions metric is rejected or absent (e.g. a low-activity Page returns no insights). `reach` remains null (no comparable Page metric).

### Fixed — Social credential loaders read the account ID from `config`, not the blob

The Instagram/Facebook sync reported "credentials unusable" even with a valid token saved, because the save route stores the **secret** field (`access_token`) in the encrypted blob but the **non-secret** ID field (`ig_user_id` / `page_id`) in the `config` JSONB column — and the loaders only read both from the blob. `load_instagram_credentials` / `load_facebook_credentials` now read the token from the decrypted blob and the ID from `integration.config` (with a blob fallback for older rows). With this fix, a saved Facebook Page token syncs live.

### Added — Manual "Sync now" button for social + email connectors

The on-demand sync button on the integration detail page (previously GHL-only) now renders for every connector with a backing sync task — **Mailchimp, Instagram, Facebook**, and GHL. The backend `POST /integrations/{slug}/sync` was already generic (routes through `_trigger_sync`); this just surfaces the button with per-provider labels ("Sync metrics now" / "Sync campaigns now" / "Sync contacts now"). Lets an admin pull fresh data immediately after saving credentials instead of waiting for the next beat tick.

- `frontend/.../integrations/[slug]/page.tsx` — `SYNCABLE_SLUGS` set + `SYNC_BUTTON_LABEL` map drive the button's visibility/label; removed the `slug === "ghl"` gate.

### Added — Facebook Page integration (Meta Graph API)

Makes the `/marketing/social` **Facebook** column live, mirroring the Instagram connector. Manual long-lived **Page** token + Page ID; no migration. Unlike Instagram, Facebook needs no account-type conversion — any Page admin can read Page insights.

- `app/services/facebook_client.py` (new) — Graph API v19 wrapper: Page profile (`followers_count`/`fan_count`, `name`), Page Insights (`page_impressions` over `days_28`, summed across the window), and recent `/posts` (likes+comments summary) for an engagement-rate estimate. Profile required; insights + posts best-effort. `reach` left null (no Page metric comparable to IG reach). `verify()` powers the Test button.
- `app/services/facebook_credentials.py` (new) — decrypts `(access_token, page_id)` from the integration blob (mirrors `instagram_credentials.py`).
- `app/tasks/social_stats.py` — refactored the per-platform live sync into a generic `_sync_live_platform(db, platform, …)` driven by a `_LIVE_PLATFORMS` map `{instagram, facebook}` (each → its creds-loader + fetch fn). Facebook syncs live when connected, **skips** (no fake-data overwrite) when not connected or on error, stamping `last_sync_status`/`last_sync_error` + a `sync_log` row. Removed `facebook` from `_SEED_DATA` (linkedin/tiktok stay seeded). The task result dict now reports per-platform sync results.
- `app/services/integrations_registry.py` — new `facebook` provider (icon 📘, category social, `available`, fields `access_token` + `page_id`, `trigger_task: "facebook"`).
- `app/routes/integrations.py` — `_trigger_sync` enqueues the shared `update_social_stats` for both `instagram`/`facebook`; `test_integration` facebook branch calls `facebook_client.verify()`.
- `frontend/.../integrations/[slug]/page.tsx` — `FacebookSetupStepsCard`: collapsible steps for getting a long-lived Page token (Graph API Explorer → select Page → token-exchange) and the Page ID (`/me/accounts`).

No `/marketing/social` change — it already renders a Facebook row; it lights up once a sync writes real data. Verified structurally with zero API cost (registry/fields, creds-None-on-empty, engagement-rate math, insight-value summing, `verify()` not-connected message, task syncs both live platforms + skips gracefully with no rows). Live Graph test needs a user-provided long-lived Page token + Page ID.

### Added — Instagram social integration (Meta Graph API)

Makes the `/marketing/social` Instagram column **live**. Previously `update_social_stats` wrote hardcoded seed data for all platforms; now Instagram pulls real organic metrics from the Meta Graph API. Manual-token connector following the GHL/Mailchimp pattern — no migration (the `integrations` table already has every column needed).

- `app/services/integrations_registry.py` — Instagram flipped `coming_soon` → `available` with two fields (`access_token` secret, `ig_user_id`) and `trigger_task: "instagram"`. This is what makes the card clickable on `/integrations` and renders the connect form at `/integrations/instagram`.
- `app/services/instagram_client.py` (new) — Graph API v19 httpx wrapper: profile (`followers_count`, `media_count`), account insights (`reach`/`impressions`, `days_28`), recent-media engagement-rate estimate. Insights + media are best-effort; profile is required. `verify()` powers the Test button; `is_configured()`/`_resolve_creds()` read the DB.
- `app/services/instagram_credentials.py` (new) — decrypts `(access_token, ig_user_id)` from the integration blob (mirrors `ghl_credentials.py`); returns None on any failure.
- `app/tasks/social_stats.py` — `update_social_stats` syncs Instagram live when connected; **skips** it (no fake-data overwrite) when not connected or on error, stamping `last_sync_status`/`last_sync_error` + a `sync_log` row. facebook/linkedin/tiktok stay on seed values (clearly marked) so the dashboard stays populated.
- `app/routes/integrations.py` — `_trigger_sync("instagram")` enqueues `update_social_stats` (Sync button); `test_integration` instagram branch calls `instagram_client.verify()`.
- `INTEGRATIONS.md` — Instagram entry rewritten from ⬜ to ✅.

No frontend change to `/marketing/social` — it renders from the DB and lights up once credentials are saved and a sync runs. The `/integrations/instagram` detail page has a collapsible **Setup steps** panel walking through getting a long-lived access token (Graph API Explorer → token-exchange endpoint) and the IG Business account ID (`/me/accounts` → `instagram_business_account`). Verified structurally with zero API cost (registry/fields, creds-None-on-empty, engagement-rate math, `verify()` not-connected message, task skips IG gracefully with no row). Live Graph API test requires a user-provided Meta long-lived token + IG account ID (the user's token, not app-key spend).

> **Deferred:** a "Connect with Meta" OAuth button (single shared business account, long-lived-token auto-refresh) was built and then removed in favor of shipping the manual-token connector first. The implementation lives in git history (branch `feat/instagram-social-integration`, commits `1566abc`/`65b6e1b`/`22c36af`) for a future sprint.

### Added — Central Intelligence cross-department delegation (Sprint 8)

Connects the top-level Central Intelligence chat agent to the three department Directors so it can finally answer cross-department questions ("what should we focus on this week?") with real Sales/Marketing/Fulfillment intelligence. Previously CI's only tools were `query_database`/`search_knowledge_base`/`query_calendar`, and its prompt admitted Directors weren't connected.

**Strict hierarchy (deliberate invariant):** delegation flows strictly **down** — CI → Director → specialists. CI is the *only* cross-department agent; **Directors never delegate to each other** (enforced by omission — no peer-delegate tools are added to any Director, verified in tests). Specialists stay department-scoped.

#### Backend
- `app/agents/central_intelligence.py` — three new delegate tools: `delegate_to_marketing_director`, `delegate_to_sales_director`, `delegate_to_fulfillment_director` (CI now registers 6 tools). Each handler opens a **fresh `AsyncSessionLocal()`**, builds the Director on the spot, runs `director.execute(task)`, and returns its prose. Directors must be built per-call because CI is a long-lived per-session object while DB sessions are per-request — a Director held at `__init__` would carry a stale, closed session. Handlers are error-resilient (return a short JSON error string instead of crashing the CI tool loop).
- `app/prompts/central_intelligence_v1.py` — removed the false "Directors are not yet connected" limitation; added a **Delegating to Directors** section: a routing table (which Director per topic), scoped-vs-broad guidance (one Director for a scoped question; all three + synthesize for strategy), and a cross-department optimization framework (leads not being worked, fulfillment at capacity → pause sales, recurring call pain → content angle, member wins → proof). Existing secrecy guardrails retained (never name a Director/specialist/tool; present as one CEO synthesis).
- `app/routes/dashboard.py` + `app/schemas/dashboard.py` — `GET /dashboard/weekly-focus`: runs CI once with a fixed "what should we focus on this week?" prompt (asks for strict JSON), returns `{focus:[{title,detail}], summary, generated_at, cached}`. **Cached 15 min** because each run fans out to all three Directors (several chained model calls), and falls back to deterministic priorities (from the recommendation-metrics queries) when no API key is configured or the CI run fails. JSON extraction tolerates stray prose/fences.

#### Frontend
- `frontend/src/components/dashboard/weekly-focus.tsx` — new "This Week's Focus" panel (indigo CI accent matching `CIWidget`): fetches `/dashboard/weekly-focus` with the `apiClient.get(..., {silent:true})` + `authLoading` pattern, renders the synthesized summary + numbered priority list, with skeleton and graceful empty state.
- `frontend/src/app/(app)/dashboard/page.tsx` — renders `WeeklyFocus` as a full-width row above the existing snapshot/recommendations row; added a matching skeleton bar.

No migration, no new agent classes, no Director changes. Real-AI path (CI → 3 Directors → specialists) incurs app-key spend and is gated behind the 15-min cache; verified structurally with zero API cost (6-tool registration, Director isolation, deterministic weekly-focus fallback, tolerant JSON parse).

### Added — Market Signals aggregation job

Fills the missing engine for `market_signals` (handover §3.6): the table, read API, and UI surfaces existed, but nothing ever populated it from `insights`. Now a scheduled job recomputes it so the trend dashboards (`/ci-market-signals`, the Marketing Director's `get_market_signals` tool, `/marketing/summary`) show live data.

- `app/tasks/market_signals.py` — `update_market_signals` Celery task. Recomputes (not increments) from `insights` grouped by `(signal_family, signal)`: `total_mentions` + rolling `last_30_days`/`last_7_days` (windows must decay, so a full recompute each run), most-frequent `insight_type`, and the newest `raw_quote`/`call_id` as the example. Single `INSERT ... ON CONFLICT` upsert that **preserves the human-curated `best_marketing_angle`/`notes`**. Idempotent; no-ops cleanly on empty insights (never wipes the table).
- `app/models/intelligence.py` + migration `c4049d9dcf4c` — unique constraint `uq_market_signals_family_signal` on `(signal_family, signal)` (the aggregation key for `ON CONFLICT`).
- `app/tasks/celery_app.py` — task added to the worker include list + a `market-signals-hourly` beat entry (recompute hourly at :35).
- `app/routes/ci.py` — `POST /ci/market-signals/refresh` enqueues the job on demand (mirrors the GHL sync button).

No frontend change — the existing read surfaces light up once the job populates the table. Zero API cost (pure SQL aggregation).

### Added — Tech SOS (Fulfillment support tickets, F04)

Wires the last unbuilt Fulfillment sidebar link (`/tech-sos`) to a member support-ticket tracker. Greenfield (new table). AI categorization deferred (F04-2) — category is staff-set for now.

#### Backend
- `app/models/operational.py` — new `SupportTicket` model (`support_tickets` table): nullable `member_id` (SET NULL), contact snapshot, subject/description, category (login/billing/video/portal/access/other), status (open/in_progress/resolved/closed), priority, resolution, resolved_at, source ('staff'|'submit'). Migration `5310f9ce275a` (hand-trimmed).
- `app/repositories/tech_sos_stats.py` — `compute_ticket_stats` (KPIs incl. avg resolution hours, category + status breakdown, 8-week volume) + `get_open_tickets`.
- `app/schemas/tech_sos.py` + `app/routes/tech_sos.py` — `GET /tech-sos` (filters status/category/member/search), `/tech-sos/stats`, detail, history, `POST /tech-sos` (staff create), **`POST /tech-sos/submit` (public, unauthenticated — best-effort member link by email)**, `PATCH` (status→resolved stamps resolved_at; reopen clears; audited), `DELETE` (soft-delete).
- `app/main.py` mounts the router; `app/middleware/auth.py` exempts `/api/v1/tech-sos` (makes /submit public).
- `app/agents/specialists/members.py` — `get_tech_sos` read tool; `app/routes/fulfillment.py` — additive `tech_sos` block in `/fulfillment/summary` (member KPIs unchanged).

#### Frontend (Fulfillment orange #F97316)
- `components/tech-sos/ticket-modal.tsx` — shared create/edit modal (member dropdown on create; member-locked variant; edit fetches full ticket so description/resolution aren't blanked).
- `(app)/tech-sos/page.tsx` — admin page: KPI cards (open/in-progress/resolved/avg-resolution), patterns dashboard (category + status bars), ticket table (member link, category, status/priority badges) with Manage/Delete + filters + New Ticket.
- `(app)/members/[member_id]/page.tsx` — Tech SOS card (member's tickets + New + Manage).

#### Notes
- The public `POST /tech-sos/submit` is open (no token) for v1 — a rate-limit / submit-token guard is a sensible follow-up before exposing it on a real member form.
- AI categorization (auto-category + suggested resolution + pattern detection) deferred; the model has the fields for it.

### Added — Goals kanban board (Accountability)

A Table / Board view toggle on `/accountability` with drag-and-drop across kanban stages.

- `goals.stage` column (todo/in_progress/blocked/done) + migration (`cd767c18679b`). **Independent of `status`** (active/completed/abandoned) — orthogonal workflow dimension; `compute_goal_stats` (KPIs/funnel) stays status-based.
- `app/schemas/goals.py` + `app/routes/goals.py` thread `stage` through list/detail/create (defaults `todo`)/PATCH (audited `goal.stage_changed`); new `GET /goals?stage=` filter.
- `components/goals/goal-board.tsx` — dnd-kit board (4 columns; cards show member/goal/status/overdue/target). Dragging a card optimistically moves it then `PATCH /goals/{id}` with the new stage; reverts on error.
- `(app)/accountability/page.tsx` — Table/Board toggle (persisted to localStorage); same KPIs/funnel/filters apply to both. Added `@dnd-kit/core` + `@dnd-kit/utilities`.

### Added — Accountability (Goal tracking)

Wires the dead `/accountability` sidebar link to a goal-tracking dashboard (Sprint 6 F03). Built on the existing `Goal` model — no migration. Goals also still arrive via the CI insight-sync bridge (`insight_type='Goal'`); manual CRUD is additive.

#### Backend
- `app/repositories/goal_stats.py` — `compute_goal_stats()`: KPIs (total, in_progress, completed, overdue), 3-stage goal funnel (matches the fulfillment dashboard), status breakdown. Member-scoped.
- `app/schemas/goals.py` + `app/routes/goals.py` — goals CRUD: `GET /goals` (filters: member_id/status/overdue/search), `GET /goals/stats`, `GET /goals/{id}`, `GET /goals/{id}/history`, `POST /goals` (create for a member, `goal.created` audit), `PATCH /goals/{id}` (per-field audit incl. `goal.status_changed`; complete = status='completed'), `DELETE /goals/{id}` (soft-delete, `goal.deleted` audit).
- `app/main.py` mounts `goals_router`; `app/middleware/auth.py` exempts `/api/v1/goals`.
- `app/agents/specialists/members.py` — `get_goal_progress` read tool (funnel + overdue across members).

#### Frontend (Fulfillment orange #F97316)
- `components/goals/goal-modal.tsx` — shared Add/Edit Goal modal (member locked in member-detail context).
- `(app)/accountability/page.tsx` — dashboard: KPI cards (Total/In Progress/Completed/Overdue), goal-funnel bars, goals table (member link, status badge + overdue flag, target date) with Complete/Edit/Delete row actions, status + overdue + search filters, Add Goal.
- `(app)/members/[member_id]/page.tsx` — Goals section gained Add + per-goal Complete/Edit/Delete.

### Added — Coaching Calls (Fulfillment)

Wires the dead `/coaching-calls` sidebar link to a real page. Coaching calls are `calls` rows with `call_type='Coaching'` — same VOC pipeline as sales calls (transcript → insights incl. wins → content ideas), analyzed by the coaching-tuned analyzer built in Sprint 6a-lite. Mostly a themed frontend mirror of `/sales-calls` plus member-linking on upload.

#### Backend
- `app/routes/transcribe.py` — `POST /transcribe/upload` now accepts a `memberId` form field (validated UUID + existence check, mirroring `leadId`), so file-uploaded coaching calls attach to a member.
- `app/routes/ci.py` + `app/schemas/ci.py` — `POST /ci/transcripts/upload` (base64 transcript path) now accepts optional `lead_id`/`member_id` and sets them on the Call (previously it linked neither).

#### Frontend (Fulfillment orange #F97316)
- `components/upload/transcript-upload-widget.tsx` — new optional `memberId` prop, threaded into all three submit paths (multipart `/transcribe/upload`, URL `/transcribe`, base64 `/ci/transcripts/upload`).
- `(app)/coaching-calls/page.tsx` — list page mirroring `/sales-calls`: upload widget (callType=Coaching), table of analyzed coaching calls (`GET /ci/calls?call_type=Coaching`), download transcript.
- `(app)/coaching-calls/[call_id]/page.tsx` — orange-themed detail page (copy of the call-type-agnostic sales detail): summary + insights (inline edit) + content ideas + transcript + re-analyze.
- `(app)/members/[member_id]/page.tsx` — member call rows now link to `/coaching-calls/{id}` (coaching) or `/sales-calls/{id}` (else).
- Sidebar/header already routed `/coaching-calls` → Fulfillment Director (no change).

### Added — Sprint 5 S01: Appointments

Makes appointments a first-class entity (previously only a lead status / funnel proxy). Fed by an inbound GHL appointment webhook + manual entry. Outbound nightly GHL appointment pull is deferred (GHL calendar-API access unverified).

#### Backend — Model + migration
- `app/models/operational.py` — new `Appointment` model (`appointments` table): nullable `lead_id`/`member_id` FKs (SET NULL), contact snapshot (name/email/phone), `status` (booked/confirmed/showed/no-show/cancelled/rescheduled), `appointment_type`, `scheduled_at`/`end_at`, `source` ('ghl'|'manual'), `external_id` (GHL appt id — dedup key), `notes`. Registered in `models/__init__.py`.
- `alembic/versions/ca825332c707_add_appointments_table.py` — creates `appointments` + 6 indexes only (hand-trimmed autogenerate drift).

#### Backend — Inbound GHL webhook
- `app/services/ghl_upsert.py` — `upsert_ghl_appointment()` + `GHL_APPT_FIELD_VARIANTS` + `_GHL_APPT_STATUS_MAP` + tolerant datetime parse (ISO + epoch-ms). Dedup on `(source='ghl', external_id)`; best-effort link to a lead (external_id then email) and member (email). Refactored `_pick` → generic `_pick_from`. INSERT → `appointment.created`; UPDATE → `appointment.status_changed`/`rescheduled` only on real change (so book→reschedule→cancel reads cleanly).
- `app/routes/webhooks.py` — new `POST /webhooks/ghl/{webhook_token}/appointments` (LIVE), mirroring the lead webhook's constant-time token validation. Extracted shared `_resolve_ghl_integration` helper.

#### Backend — Stats, CRUD, surfaces
- `app/repositories/appointment_stats.py` — `compute_appointment_stats()` (KPIs: total, upcoming_this_week, show_rate, no_show_rate; 8-week volume; status breakdown) + `get_upcoming_appointments()`.
- `app/schemas/appointments.py` + `app/routes/appointments.py` — `GET /appointments` (filters: status/search/window/date), `GET /appointments/stats`, `GET /appointments/{id}`, `GET /appointments/{id}/history`, `POST /appointments` (manual booking), `PATCH /appointments/{id}` (per-field audit incl. rescheduled), `DELETE /appointments/{id}` (soft-cancel → status='cancelled', row stays visible).
- `app/routes/leads.py` — `GET /leads/{id}/appointments` for the lead-detail card.
- `app/routes/sales.py` — `/sales/summary` gains an additive `appointments` block (real booked counts). The funnel's "Appointments" stage is unchanged (still the lead-status proxy) — `/leads/stats` shape preserved.
- `app/agents/specialists/leads.py` — `get_appointments` tool so the Sales Director (via leads_analyst) can answer "what's booked this week?".
- `app/main.py` mounts `appointments_router`; `app/middleware/auth.py` exempts `/api/v1/appointments` (matches /leads, /members).

#### Frontend (Sales blue #3B82F6)
- `(app)/appointments/page.tsx` — directory: KPI cards (Total, Upcoming, Show Rate, No-Show Rate), table (contact → /leads/{id} when linked, scheduled time, status badge, type), status + window + search filters, "Book Appointment" modal (manual create).
- `(app)/leads/[lead_id]/page.tsx` — Appointments card (fetches `/leads/{id}/appointments`).

#### Notes
- Lead/member linking is best-effort; a webhook for an unknown contact lands with null FKs and renders via the contact snapshot (won't retro-link if the lead arrives later).
- Outbound nightly GHL appointment pull remains the one deferred GHL roadmap item.

### Added — Sprint 6a-lite: Fulfillment Department core (Fulfillment Director + Members/Coaching specialists)

Adds the Fulfillment Director coordination layer (post-sale: members, goals, wins, coaching intelligence) on top of the existing Member/Goal/Win/Call data layer. Deferred to Sprint 6b: Accountability specialist, Tech SOS (greenfield model), and the CI integrations (ActiveCampaign, Fireflies, content-calendar). Lead→Member conversion also deferred.

#### Backend — New model + migration
- `app/models/operational.py` — new `MemberNote` model (`member_notes` table), mirroring `LeadNote`; added `Member.staff_notes` relationship. Registered in `app/models/__init__.py`.
- `alembic/versions/6802177b2e45_add_member_notes_table.py` — creates `member_notes` only (hand-trimmed: autogenerate drift that would have dropped ~13 unrelated indexes was removed).

#### Backend — Shared aggregation
- `app/repositories/fulfillment_stats.py` — `compute_member_stats()` (member KPIs, 8-week enrollment volume, status breakdown, goal funnel) and `get_recent_wins()`. Reuses `get_top_pain_points`/`get_recent_insights` from `sales_stats.py`.

#### Backend — Coaching analyzer (wins-first)
- `app/prompts/coaching_analyzer_v1.py` — `COACHING_ANALYZER_SYSTEM_PROMPT_V1` (+ `build_coaching_user_prompt`, `MOCK_COACHING_ANALYZER_OUTPUT`). Same 22-field Insight schema as the sales analyzer but reframed for coaching: wins as first-class, coaching signal families, pain = blocks-to-progress.
- `app/tasks/call_analyzer.py` — `_call_claude` now routes by call_type: `coaching` → coaching prompt, everything else → the existing sales prompt (regression-safe). Coaching calls already flow through `analyze_call` with `member_id` attached.

#### Backend — Agents
- `app/agents/specialists/members.py` — `MembersSpecialist` (`fulfillment_members`): read-only tools `get_member_stats`, `get_member_list`, `get_member_goals`.
- `app/agents/specialists/coaching.py` — `CoachingSpecialist` (`fulfillment_coaching`): read-only tools `get_recent_coaching_calls`, `get_recent_wins`, `get_top_pain_points`. Distinct from the `coaching_analyzer_v1` Celery extractor.
- `app/prompts/fulfillment_director_v1.py` — `FULFILLMENT_DIRECTOR_SYSTEM_PROMPT_V1` (exported in `prompts/__init__.py`).
- `app/agents/directors/fulfillment.py` — `FulfillmentDirector` (`claude-sonnet-4-6`), registers `members_analyst` + `coaching` specialists and director tools `get_fulfillment_summary`, `get_top_pain_points`.

#### Backend — Routes & wiring
- `app/routes/members.py` + `app/schemas/members.py` — full CRUD: `GET /members` (list/filters), `GET /members/stats`, `GET /members/{id}` (detail with calls/goals/wins/pain/notes), `GET /members/{id}/history`, `PATCH /members/{id}` (per-field `member.*` audit via `record_event`, no GHL push), `POST`/`DELETE /members/{id}/notes`.
- `app/routes/fulfillment.py` — `GET /api/v1/fulfillment/summary` (auth-gated, like `/sales/summary`).
- `app/routes/directors.py` — registered `"fulfillment-director"` → `WS /ws/v1/fulfillment-director/{session_id}`.
- `app/main.py` — mounted `members_router` + `fulfillment_router` under `/api/v1`.
- `app/middleware/auth.py` — `/api/v1/members` added to exempt prefixes (matches `/leads`).

#### Frontend
- `frontend/src/components/chat/fulfillment-director-chat-view.tsx` + `(app)/fulfillment-director/page.tsx` — orange (#F97316) chat, 🏆, `useDirectorChat("fulfillment-director")`.
- `(app)/fulfillment/page.tsx` — dashboard: 4 orange KPI cards from `/fulfillment/summary`, tools card (Members, Coaching Calls), Director CTA.
- `(app)/members/page.tsx` + `(app)/members/[member_id]/page.tsx` — members directory (table + filters + KPIs) and detail (inline edit, goals/wins/pain, staff notes, history timeline).
- `frontend/src/components/layout/sidebar.tsx` — added Fulfillment Overview + Fulfillment Director links.
- `frontend/src/components/layout/header.tsx` — fulfillment-page CTA now routes to `/fulfillment-director`.

### Added — Sprint 5a: Sales Department core (Sales Director + specialists)

Adds the Sales Director coordination layer on top of the already-shipped Leads (S02) and Sales Calls / Call Analyzer (S03) data layer. Leads and Sales Calls were NOT rebuilt — their routes/UI stay as-is and are wrapped as read-only specialists. Appointments (S01) is deferred to Sprint 5b (planned to use a GHL appointment sync).

#### Backend — Shared aggregation (single source of truth)
- `app/repositories/sales_stats.py` — new module with `compute_lead_stats()` (KPIs, 8-week lead volume, source breakdown, 4-stage funnel — SQL lifted verbatim from the leads route), `get_top_pain_points()`, and `get_recent_insights()`. Both the leads route and the Sales surfaces consume it so the funnel definition can't drift.
- `app/routes/leads.py` — `GET /api/v1/leads/stats` now delegates to `compute_lead_stats()` and adapts the dict into `LeadsStatsResponse`. Behavior is identical (verified by before/after regression: 14 leads, same volume/funnel shape).

#### Backend — Agents
- `app/prompts/sales_director_v1.py` — `SALES_DIRECTOR_SYSTEM_PROMPT_V1`, mirroring the Marketing Director prompt structure (Role, How-to-Respond guardrails, Intelligence Pre-Flight, internal Routing, Response Structure). Exported from `app/prompts/__init__.py`.
- `app/agents/specialists/leads.py` — `LeadsSpecialist` (`sales_leads`), read-only tools `get_leads_summary`, `get_lead_list`. No write tools — lead CRUD stays in the route.
- `app/agents/specialists/call_analyzer.py` — `CallAnalyzerSpecialist` (`sales_calls`), read-only tools `get_recent_calls`, `get_call_insights`, `get_top_pain_points`. Distinct from the `call_analyzer_v1` Celery extractor — this only reads `insights` rows.
- `app/agents/directors/sales.py` — `SalesDirector` (model `claude-sonnet-4-6`, matching the Marketing Director). Registers `leads_analyst` + `call_analyzer` specialists (auto-creating `delegate_to_*` tools) and director-level data tools `get_sales_summary`, `get_top_pain_points`.

#### Backend — Routes & wiring
- `app/routes/sales.py` — `GET /api/v1/sales/summary` mirroring `/marketing/summary`: KPIs, lead volume, source breakdown, funnel, top pain points, recent insights. (Auth-gated, same as `/marketing/summary`.)
- `app/routes/directors.py` — registered `"sales-director"` in `_DIRECTOR_REGISTRY`; the WebSocket route `WS /ws/v1/sales-director/{session_id}` now resolves with no other change.
- `app/main.py` — mounted `sales_router` under `/api/v1`.

#### Frontend
- `frontend/src/components/chat/sales-director-chat-view.tsx` + `frontend/src/app/(app)/sales-director/page.tsx` — Sales Director chat, using `useDirectorChat("sales-director")`, blue (#3B82F6) accent, 💼 avatar.
- `frontend/src/app/(app)/sales/page.tsx` — Sales department dashboard: 4 blue KPI cards from `/sales/summary`, a Sales Tools card (Leads, Sales Calls), and a Sales Director CTA.
- `frontend/src/components/layout/sidebar.tsx` — added "Sales Overview" (`/sales`) and "Sales Director" (`/sales-director`) to the Sales section.
- `frontend/src/components/layout/header.tsx` — sales-page "Sales Director" CTA now routes to `/sales-director` (was `/chat`).

#### Notes (deliberate decisions)
- **CI awareness:** Central Intelligence left untouched — the Marketing Director isn't wired into CI either; matched that precedent.
- **No `__init__` re-exports** for the new director/specialists — the verified convention is import-by-dotted-path (registry / inline), not re-export. Matches Marketing.

### Fixed — Sprint 3 Data Connectivity: Database Persistence Pipeline

#### Backend — New Models & Repositories
- `app/models/marketing.py` — 5 new SQLAlchemy models: `SocialStats`, `SocialComment`, `EmailCampaign`, `FunnelEvent`, `FunnelStats` with proper indexes, timestamps, soft-delete, and unique constraints
- `app/repositories/marketing.py` — 5 new repository classes with domain-specific queries: `SocialStatsRepository` (aggregate_totals, upsert_stats), `SocialCommentRepository`, `EmailCampaignRepository` (aggregate_stats, upsert_campaign), `FunnelEventRepository` (count_by_funnel_and_stage), `FunnelStatsRepository` (find_all_latest, upsert_stats)
- `app/models/__init__.py` — registered all 5 marketing models for Alembic autodiscovery
- `app/repositories/__init__.py` — exported all 5 marketing repositories

#### Backend — Routes Wired to Database
- `app/routes/social.py` — `GET /api/v1/social` now queries `SocialStatsRepository.aggregate_totals()` instead of returning hardcoded zeros
- `app/routes/email.py` — `GET /api/v1/email` now queries `EmailCampaignRepository.aggregate_stats()` instead of returning hardcoded zeros
- `app/routes/funnels.py` — `POST /api/v1/funnels` now persists events to `funnel_events` table via `FunnelEventRepository`; added `GET /api/v1/funnels` endpoint returning aggregated stage stats via `FunnelStatsRepository`
- `app/schemas/funnels.py` — added `FunnelStageStats` and `FunnelDataResponse` Pydantic schemas

#### Backend — Celery Tasks Wired to Database
- `app/tasks/db.py` — new shared sync session helper (`make_sync_session()`) for Celery tasks
- `app/tasks/social_stats.py` — replaced placeholder with upsert loop writing seed data to `social_stats` table for 4 platforms
- `app/tasks/email_stats.py` — replaced placeholder with upsert loop writing seed campaign data to `email_campaigns` table
- `app/tasks/funnel_stats.py` — replaced placeholder with aggregation query on `funnel_events` → upsert into `funnel_stats`
- `app/tasks/comments_collector.py` — replaced placeholder with dedup-aware insert of seed comments into `social_comments` table

#### Backend — Bug Fix
- `app/tasks/celery_app.py` — added missing `"app.tasks.funnel_stats"` to Celery include list (task was never discovered by workers)

#### Frontend — Pages Wired to Backend APIs
- `marketing/social/page.tsx` — fetches `GET /api/v1/social`, populates KPI tiles with real followers/posts/engagement data
- `marketing/email/page.tsx` — fetches `GET /api/v1/email`, populates KPI tiles with real campaign count/open rate/CTR
- `marketing/funnels/page.tsx` — fetches `GET /api/v1/funnels`, populates KPI tiles and stale indicator with real funnel stage data
- `marketing/social/scripts/page.tsx` — wired Generate button to `POST /api/v1/social` (falls back to mock on error)
- `marketing/email/compose/page.tsx` — wired AI Assist button to `POST /api/v1/email` (falls back to mock on error)

### Added — VIR-39, VIR-40: Sprint 4a/4b — Ads, DM, and Offer Specialist Prompts

- `app/prompts/ad_analysis_v1.py` (M04-2) — `CI-MKT-ADS` analysis mode. ROAS-primary campaign health diagnostics (strong ≥3x, moderate 1.5-3x, weak <1.5x), layer-level diagnosis (creative/copy/targeting/landing page), cross-domain alerts for pain points and wins not in any ad creative. `build_ad_analysis_user_prompt`: ad_stats sorted by ROAS, pain_points, wins, content_ideas. 8-field output schema.
- `app/prompts/ad_copy_generation_v1.py` (M04-3) — `CI-MKT-ADS` copy generation mode. Platform-native rules (Facebook/Instagram hook-within-3-words, Google Ads 30-char headline hard limit). 4 angle types enforced as distinct categories. `ad_variants` minItems=3. Banned clichés list in system prompt. Includes `recommended_test_order` and `targeting_suggestion`.
- `app/prompts/dm_analysis_v1.py` (M05-2) — `CI-MKT-DM` analysis mode. Three-stage funnel diagnostics (response_rate / positive_response_rate / conversion_rate). Opener pattern analysis at structural DNA level. DM-calibrated health thresholds (>5% conversion = strong). `opener_pattern_analysis` array with `replication_advice` per sequence type.
- `app/prompts/dm_template_generation_v1.py` (M05-3) — `CI-MKT-DM` template generation mode. Per-message `message_job` field (psychological movement). Platform-context calibration (LinkedIn professional vs Instagram/Facebook social register). Cold outreach never-pitch rule enforced. Personalisation placeholders: [FIRST_NAME], [COMPANY], [SPECIFIC_OBSERVATION], [SHARED_CONTEXT].
- `app/prompts/offer_analysis_v1.py` (M06-2) — `CI-OFR` analysis mode. Per-offer audit: `pain_alignment_score` (1-10), `objection_coverage` (addressed/missed), `missing_value_props`, per-offer `optimization_recommendations`. `pricing_gap_analysis` across full portfolio. Offers sorted by conversion_rate ascending (failures first).
- `app/prompts/offer_creation_v1.py` (M06-3) — `CI-OFR` creation mode. Every offer element CI-grounded. Pricing tier rationale required. Bonuses each require `objection_addressed`. Guarantee with `objection_addressed`. `urgency_element` with `is_genuine` boolean. 3 typed copy angles.
- `app/prompts/offer_generator_v1.py` (OPS-O2) — `CI-OPS-OFR` Celery operator. Deterministic, autonomous. `status` field: success/insufficient_data/error. Data threshold enforcement (< 3 pain_points or wins → insufficient_data). Offer type auto-selection logic from CI signals. `generated_at_signal` data quality note.
- `app/prompts/__init__.py` — updated with all 18 new symbols from the 7 new prompt modules.

### Added — VIR-33, VIR-34: Sprint 3a/3b — Email + Funnel Specialist Prompts

- `app/prompts/email_analysis_v1.py` (M02-2) — `EMAIL_ANALYSIS_SYSTEM_PROMPT_V1`: CI-MKT-EMAIL analysis-mode prompt with 3 expertise areas, per-campaign-type analysis mandate, coaching-industry benchmarks, example output. `build_email_analysis_user_prompt(data)`: handles email_stats, content_ideas, market_signals, pain_points, ICP segments with graceful empty-data fallbacks. `EMAIL_ANALYSIS_OUTPUT_SCHEMA`: 8-field JSON Schema (summary, top_performing_campaign_type, overall_health, campaign_breakdown, subject_line_insights, content_gaps, cross_domain_insights, recommended_focus).
- `app/prompts/email_draft_v1.py` (M02-3) — `EMAIL_DRAFT_SYSTEM_PROMPT_V1`: CI-MKT-EMAIL draft-mode prompt with 5 enforced quality rules (CI anchor, one-email-one-CTA, subject line formula, body structure, preview text). `build_email_draft_user_prompt(data)`: handles email_type, subject_brief, sequence_position, brand_voice, icp_primary, CI data. `EMAIL_DRAFT_OUTPUT_SCHEMA`: 9-field schema including ps_line (nullable) and ci_anchor.
- `app/prompts/funnel_analysis_v1.py` (M03-2) — `FUNNEL_ANALYSIS_SYSTEM_PROMPT_V1`: CI-MKT-FUN Funnels Analyst prompt with 3 expertise areas (metrics analysis, conversion psychology, CI synthesis), coaching-industry drop-off severity benchmarks, full stage + source analysis mandate. `build_funnel_analysis_user_prompt(data)`: funnel_stages (sorted ascending by conversion to surface bottlenecks), lead_sources (sorted by conversion quality), pain_points, ICP segments, market_signals. `FUNNEL_ANALYSIS_OUTPUT_SCHEMA`: 8-field schema including critical_bottleneck, stage_analysis with drop_off_severity enum, optimization_priorities (ranked by revenue impact).
- `app/prompts/__init__.py` — exported all 6 new symbols from email_analysis_v1, email_draft_v1, and funnel_analysis_v1.

### Added — VIR-35: Sprint 3a — Social Media + Email Specialist Agents + Stats Operators
- `app/schemas/social.py` — Pydantic schemas: `SocialAnalyzeRequest`, `SocialPost`, `SocialAnalyzeResponse`, `SocialDataResponse`
- `app/schemas/email.py` — Pydantic schemas: `EmailAnalyzeRequest`, `EmailDraftRequest`, `EmailAnalyzeResponse`, `EmailDraftResponse`, `EmailDataResponse`
- `app/agents/specialists/social_media.py` — `SocialMediaSpecialist` (M01-1): extends `SpecialistAgent`, domain `social_media_marketing`, tools: `get_social_data`, `generate_social_script`
- `app/agents/specialists/email.py` — `EmailSpecialist` (M02-1): extends `SpecialistAgent`, domain `email_marketing`, tools: `get_email_metrics`, `draft_email`
- `app/routes/social.py` — FastAPI router (M01-4): `POST /api/v1/social` (analyze/script generation), `GET /api/v1/social` (social data)
- `app/routes/email.py` — FastAPI router (M02-4): `POST /api/v1/email` (analyze/draft), `GET /api/v1/email` (email data)
- `app/tasks/email_stats.py` — Celery task `update_email_stats` (OPS-SE1): scheduled task to pull/update email campaign metrics
- `app/tasks/social_stats.py` — Celery task `update_social_stats` (OPS-SS1): scheduled task for social media metrics
- `app/tasks/comments_collector.py` — Celery task `collect_social_comments` (OPS-SC1): polling task to collect and store social comments
- `app/agents/directors/marketing.py` — (M01-5, M02-5) registered `SocialMediaSpecialist` and `EmailSpecialist` with Marketing Director
- `app/main.py` — mounted `social_router` and `email_router` under `/api/v1`
- `app/tasks/celery_app.py` — added new task modules to Celery `include` list for worker autodiscovery

### Fixed — VIR-29: ORM table name mismatches causing SQL transaction failures
- `app/models/intelligence.py` — `BusinessProfile.__tablename__` changed from `business_profiles` to `business_profile` to match Supabase migration
- `app/models/audit.py` — `AuditLog.__tablename__` changed from `audit_logs` to `audit_log` to match Supabase migration
- `app/models/audit.py` — `ErrorLog.__tablename__` changed from `error_logs` to `error_log` to match Supabase migration
- `app/models/audit.py` — `SyncLog.__tablename__` changed from `sync_logs` to `sync_log` to match Supabase migration

### Changed — VIR-27: Prompt Audit Implementation
- `app/agents/directors/marketing.py` — Replaced 12-line placeholder system prompt with production-grade prompt adapted from workflow spec: routing decision table, parallel/sequential coordination rules, intelligence data pre-flight, structured JSON response format, and internal reasoning checklist
- `app/agents/operators/transcriber.py` — Replaced one-sentence system prompt with production version: call-type awareness (sales_call, coaching, accountability), error handling guidance, and output contract
- `app/prompts/central_intelligence_v1.py` — Fixed "honest about limitations" vs. secrecy section contradiction (now "honest about capabilities, not process"); added hallucination guard rule (never fabricate data overrides silence-on-errors); added empty-result guidance
- `app/agents/central_intelligence.py` — Upgraded model from `claude-3-haiku-20240307` to `claude-sonnet-4-6` (Haiku was too weak for SQL generation + CEO persona complexity)
- `app/prompts/icp_generator_v1.py` — Replaced instruction-placeholder JSON example with realistic fictional ICP examples; strengthened `is_primary` uniqueness constraint to "exactly one, hard constraint"

### Fixed — VIR-28: Director WebSocket endpoint missing

- `app/routes/directors.py` — New WebSocket route `WS /ws/v1/{director_slug}/{session_id}` for Director agents, mirroring the Central Intelligence WebSocket protocol. Supports `marketing-director` slug, in-memory session store keyed by `(slug, session_id)`, mock mode fallback, JWT auth, and DB session lifecycle management.
- `app/main.py` — Mounted `directors_router` at root (after `central_intelligence_router`) so Director WebSocket paths resolve correctly.

### Added — Sprint 2 / VIR-20: Central Intelligence Webhook Endpoints + Data Sync Bridges
- `app/schemas/ci.py` — Pydantic models for all 13 CI endpoints (transcripts, calls, insights, content-ideas, market-signals, tags, offers, monthly-preferences) plus pagination and sync result schemas
- `app/routes/ci.py` — CI router with 15 endpoints:
  - CI-MKT-01 (8pts): 13 webhook endpoints — `POST transcripts/upload`, `POST transcripts/process`, `GET/GET:id calls`, `GET/GET:id insights`, `GET/PUT content-ideas`, `GET market-signals`, `GET tags`, `GET offers`, `GET/PUT monthly-preferences`
  - CI-MKT-02 (5pts): `POST /ci/sync/insights` — data sync bridge mapping CI insights to shared intelligence tables (pain_points, wins, objections, goals) with dedup and frequency increment
  - CI-MKT-03 (3pts): `POST /ci/sync/content-ideas` — data sync bridge validating and tagging CI pipeline content ideas in the shared content_ideas table
- `app/main.py` — registered CI router under `/api/v1` (resolves to `/api/v1/ci/*`)

### Added — Sprint 2 / VIR-18: Optimistic Locking (updatedAt + If-Match)
- `app/middleware/optimistic_lock.py` — ETag utilities: `etag_from_datetime`, `parse_if_match`, `StaleUpdateError` (409), `require_if_match` dependency (428 on missing header), `add_etag_header` response helper
- `app/dependencies/optimistic_lock.py` — FastAPI Header-based dependency returning parsed `datetime` for route handler injection via `Depends(require_if_match)`
- `app/repositories/base.py` — `update_optimistic(id, expected_updated_at, **kwargs)` method on `RepositoryBase` with UTC normalization, 1µs tolerance, 404/409 error handling
- `app/schemas/common.py` — `ErrorDetail` and `ErrorResponse` standard error envelope schemas

### Added — Sprint 2 / VIR-17: UX Components (Skeleton Loaders, Empty States, Confirm Dialog)
- `components/ui/skeleton.tsx` — added `TableSkeleton` (props: rows, cols, showFilters), `ChartCardSkeleton` (prop: height), and `DonutChartSkeleton` reusable system-wide components
- `components/ui/empty-state.tsx` — new `EmptyState` component with icon, title, description, primary action (amber CTA), and secondary action (text link)
- `components/ui/confirm-dialog.tsx` — new `ConfirmDialog` modal with danger/warning/default variants, loading state, ESC key + backdrop dismiss, focus trap, and full ARIA support

### Added — Sprint 2 / CI-CORE-01 / T01-2: Transcriber Operator
- `app/agents/operators/transcriber.py` — `TranscriberOperator` extending `BaseAgent` with audio download, pydub MP3 extraction, OpenAI Whisper transcription, URL SHA-256 deduplication, and `transcribe_audio` tool registration
- `app/agents/operators/__init__.py` — operators package
- `app/schemas/transcribe.py` — `TranscribeRequest` / `TranscribeResponse` Pydantic models
- `app/routes/transcribe.py` — `POST /api/v1/transcribe` endpoint with deduplication check, error handling (422/502/500), and Call record persistence
- `app/models/operational.py` — added `video_url_hash` (unique indexed SHA-256) and `transcript_text` columns to `Call` model
- `app/config.py` — added `openai_api_key` setting
- `app/main.py` — registered transcribe router under `/api/v1`
- `requirements.txt` — added `openai>=1.30.0`, `pydub>=0.25.1`, `requests>=2.31.0`

## [0.2.0] - 2026-03-30 — Sprint 1B Auth + Error Handling Core

### Added

#### Backend
- **Supabase Auth integration** with full mock bypass mode:
  - Auth routes: `POST /api/v1/auth/login`, `/signup`, `/refresh`, `/logout`, `/password-reset`, `GET /me`
  - When `SUPABASE_URL` is empty, all auth routes return mock responses (fake tokens, mock user)
  - When credentials are provided, real Supabase auth activates with zero code changes
- **Auth middleware** (`AuthMiddleware`):
  - JWT verification via `python-jose` for zero-latency token checks
  - Exempt paths: `/auth/*`, `/health`, `/docs`, `/redoc`, `/openapi.json`
  - Mock mode bypass when `SUPABASE_URL` is empty or `MOCK_MODE=true`
  - Standard error envelope on 401: `{"error": {"code": "UNAUTHORIZED", ...}}`
  - WebSocket auth via `?token=` query parameter
- **Error Handler agent** (`ErrorHandlerAgent`):
  - Async error logging to `error_logs` database table
  - In-memory retry queue with exponential backoff (3 max retries)
  - Convenience methods: `log_error()`, `log_warning()`, `log_info()`, `flush_queue()`
  - Module-level singleton: `error_handler`
- **ErrorLog repository** with `list_by_severity()` and `list_recent()` queries
- **Health check enhancements**: `auth`, `redis`, `uptime` fields added to `GET /api/v1/health`
- Auth Pydantic schemas: `LoginRequest`, `LoginResponse`, `UserProfile`, `PasswordResetRequest`, `TokenRefreshRequest`
- New columns on `ErrorLog` model: `agent_id`, `request_id`, `user_id` (FK), `stack_trace`

#### Frontend
- **Login page** (`/login`) matching Screen 0 of webapp mockup:
  - Dark stage background with radial gold shimmer overlay
  - Centered 420px white card with bee icon, "Central Intelligence" branding
  - Email + password fields with gold focus ring, eye toggle for password
  - Remember me checkbox + Forgot password (wired to `resetPassword`)
  - Gold gradient Sign In button with loading spinner state
  - Error banner with attempt tracker (X of 5 dots), red input error states
  - Client-side validation before auth call
  - "Powered by Central Intelligence AI" footer
- **Route group restructure**: pages moved under `(app)/` for sidebar layout, `/login` renders standalone
- **Auth context** (`AuthProvider`) with mock mode:
  - Auto-signs in with mock user when Supabase is not configured
  - `useAuth()` hook: `user`, `signIn`, `signOut`, `resetPassword`, `isLoading`, `isMockMode`
  - Real mode: Supabase session hydration, `onAuthStateChange` listener, token sync to API client
- **Next.js middleware** for session refresh + auth redirects (pass-through in mock mode)
- **Supabase client wiring**: browser client + middleware client with modern `getAll`/`setAll` cookie API
- **Toast notification system** (sonner):
  - `<Toaster />` provider in top-right position with brand styling
  - Helpers: `showSuccess()`, `showError()`, `showWarning()`, `showInfo()`, `showApiError()`
- **Error boundaries**:
  - React class component `<ErrorBoundary>` with "Try again" + "Return to Dashboard"
  - Next.js `error.tsx` for `(app)` route group with error digest display in dev mode
- **API client interceptor** enhancements:
  - AbortController timeout (30s default)
  - Retry with exponential backoff (3 attempts on 5xx, no retry on 4xx)
  - 401 interceptor: clear token, toast "Session expired", redirect to `/login`
  - Auto-toast on errors (suppressible via `{ silent: true }`)
  - Error normalization to standard `ApiError` with `field` and `requestId`
- **WebSocket improvements**:
  - Connection state change events (`onStateChange` handler)
  - Toast notification on connection failure after max reconnect attempts
  - Token passed as `?token=` query parameter for backend auth
  - `useChat` hook now tracks real connection state (replaces blind timer)
- Dynamic sidebar user from `useAuth()` with logout button (replaces hardcoded "Jade Doe")

### Changed
- Root `layout.tsx` simplified to minimal html/body/Providers shell (sidebar grid moved to `(app)/layout.tsx`)
- `pydantic` dependency updated to `pydantic[email]` for `EmailStr` support
- `requirements.txt` now includes `supabase>=2.0.0` and `python-jose[cryptography]>=3.3.0`
- Frontend packages added: `@supabase/supabase-js`, `@supabase/ssr`, `sonner`, `lucide-react`

## [0.1.0] - 2026-03-29 — Sprint 1A Foundation

### Added

#### Backend (Python + FastAPI)
- FastAPI application with app factory pattern (`backend/app/main.py`)
- Pydantic-settings configuration with `.env` loading (`backend/app/config.py`)
- Async SQLAlchemy engine with asyncpg + NullPool for Supabase (`backend/app/database.py`)
- **21 SQLAlchemy ORM models** across 4 modules:
  - Operational (9): Lead, Member, Call, Insight, ContentIdea, Goal, PainPoint, Win, Objection
  - Meta (2): User, Team
  - Intelligence (6): InsightTag, TagDictionary, MarketSignal, Offer, BusinessProfile, MonthlyPreference
  - Audit (4): AuditLog, ErrorLog, SyncLog, IdempotencyKey
- Base mixins: TimestampMixin, SoftDeleteMixin
- **Generic RepositoryBase[T]** with async CRUD, soft-delete filtering, and count
- **15 concrete repositories** with domain-specific query methods (e.g., `LeadRepository.find_by_email`)
- IntelligenceRepository facade for cross-domain queries
- Alembic async migration configuration
- **BaseAgent class** with Anthropic AsyncAnthropic SDK integration:
  - Tool registration (schema separate from handlers)
  - Async streaming via `messages.stream()` with automatic tool-use loop
  - Conversation history management
  - Error handling for API, rate limit, and connection errors
- **DirectorAgent** skeleton with specialist registration and delegation tools
- **SpecialistAgent** skeleton with domain context and DB/operator tool hooks
- **CentralIntelligence agent** (CI-CORE-00) with comprehensive system prompt v1
- **API endpoints**:
  - `GET /api/v1/health` — database connectivity check
  - `POST /api/v1/central-intelligence/chat` — SSE streaming chat
  - `WS /ws/v1/central-intelligence/{session_id}` — WebSocket streaming chat
- In-memory session store for agent conversations (Redis planned for Sprint 1B)

#### Frontend (Next.js 14 + TypeScript + Tailwind CSS)
- Next.js 14 App Router project with TypeScript and Tailwind CSS
- TanStack Query (React Query) provider setup
- **Light color scheme** with department-colored accents:
  - White sidebar (228px) with colored section labels and active-state borders
  - Marketing (#10B981), Sales (#3B82F6), Fulfillment (#F97316) department colors
  - Gold (#F59E0B) accent for Central Intelligence elements
- **Sidebar navigation** matching mockup: Dashboard, Central Intelligence Chat, Sales (3), Fulfillment (4), Marketing (7), Admin (1)
- **Header component** with dynamic title, date display, and context-sensitive actions
- **Dashboard page** with:
  - 3-column department summary cards (white bg, colored left borders, KPI stats)
  - Weekly Performance Snapshot (4 KPI mini-cards + sparkline bar chart)
  - Central Intelligence Recommendations widget (light gold-tinted bg, 4 AI-generated focus areas)
- **Chat UI page** with:
  - WebSocket-based real-time streaming
  - `useChat` hook managing connection lifecycle, message state, and streaming
  - Message bubbles (Central Intelligence: white/left, User: blue/right) with avatar icons
  - Inline markdown rendering (bold, lists, code blocks)
  - Typing indicator with animated dots
  - Auto-growing textarea input with Enter-to-send
  - Auto-scroll to latest message
- **API client library** with fetch wrapper, SSE stream parsing, auth header injection
- **WebSocket client** with exponential backoff reconnection (max 5 attempts)
- App name stored in config constant (pending final naming decision)

#### Infrastructure
- WAT framework project isolation (per-project CLAUDE.md, .env, tools/, workflows/, .tmp/)
- Root CLAUDE.md rewritten as slim orchestrator with bootstrapping template
- `.gitignore` for credentials, .env, .tmp across all projects

### Changed

- All 14 documents in `New Documents/` migrated from n8n workflow architecture to Python + Claude SDK agentic architecture (v3.0.0)
- Architecture: n8n → FastAPI + Claude SDK + Celery + Redis
- Database: n8n Data Tables + Airtable → unified Supabase PostgreSQL with SQLAlchemy ORM
- Frontend framework confirmed: Next.js 14 (App Router)
- Auth strategy: Supabase Auth (JWT + RLS) replacing NextAuth.js

## [Sprint 2] Marketing Director + Shared Repository Layer + Summary Endpoint

### Added
- `app/models/operational.py` — `ICP` model (Ideal Customer Profile segments)
- `app/repositories/operational.py` — `ICPRepository` with `find_primary()` and `find_by_status()`
- `app/repositories/shared_intelligence.py` — `SharedIntelligenceRepository` facade composing all 7 shared intelligence tables (goals, wins, pain_points, objections, content_ideas, icp, offers)
- `app/agents/directors/marketing.py` — `MarketingDirector` extending `DirectorAgent` with 6 data tools and specialist routing
- `app/routes/marketing.py` — `GET /api/v1/marketing/summary` aggregating marketing dept metrics
- `app/main.py` — wired marketing router under `/api/v1`

**Tasks:** DIR-M1 (5pts), DIR-M3 (3pts), DIR-M4 (2pts) | Total: 10 story points
