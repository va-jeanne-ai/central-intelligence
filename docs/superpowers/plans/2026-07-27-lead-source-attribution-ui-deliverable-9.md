# Implementation Plan — Lead & Sales Source Attribution (deliverable 9)

**Ticket:** ClickUp 86d3u65cb — Lead & Sales source attribution (the channel UI the
WGR attribution foundation unblocks).
**Design source of truth:** `docs/superpowers/specs/2026-07-26-wgr-attribution-sync-design.md`
(foundation, approved) + `plans/2026-07-26-wgr-attribution-sync-and-source-attribution.md`
Tasks 7–9 (the deliverable-9 sketch — corrected below where it predates the built code).

**Goal:** Surface Greg's canonical marketing **channel** (resolved at read time from
mirrored first/last-touch UTMs) on the Leads list, the lead detail page, and the
lead-source breakdown chart — in place of the generic provenance `source` (`'wgr'`).
Channel is **computed, never stored**; the resolver already exists and is tested.

**Status of the foundation (verified against the branch):** DONE and committed. The
resolver (`app/services/attribution.py`), all 8 lead `utm_*` columns + `ghl_contact_id`,
`attribution_taxonomy`, `lead_engagements`, and the three `meta_*` tables are mirrored;
CHANGELOG + INTEGRATIONS + FEATURE-VERIFICATION carry the foundation blocks. This plan
adds **only the read-time UI/API surface** — no new migrations, no new mirror tables.

**Ground-truth verified 2026-07-27** against branch `ralph/auto-ceaa51a` via a 4-agent
parallel code read. Every file:line below was reconfirmed against current source (a few
were corrected from the pre-verification draft — noted inline). The Task-1 helpers
(`channel_for_lead`, `summarize_channels`) do **not** yet exist anywhere in `backend/app/`
(no duplicate implementation to reconcile). Merge target is `staging`, never `main`
(confirmed in the foundation plan).

---

## Ground truth (from a full codebase read — trust these over Plan A's guessed line numbers)

- **Resolver, complete + tested + currently unused:** `backend/app/services/attribution.py`
  — `build_resolver(rows) -> Resolver`; `Resolver.resolve(source, medium, content) ->
  Resolution(channel, platform, reportable)` (`Resolution` is a `NamedTuple`). Contract:
  normalize `strip().lower()`, empty→None; all-null triple → `Resolution(None, None, False)`;
  most-specific match wins, tie by lowest id; no match → `Resolution("unmapped:<src>/<med>",
  None, True)`; `include_in_channel_reporting=false` → `reportable=False`. Campaign is
  deliberately outside the contract. `Resolution` NamedTuple field order is
  **`(channel, platform, reportable)`** (`attribution.py:20–23`). **Label sanitization
  (verified):** the `unmapped:*` label runs through `_label_part` — a null/empty source or
  medium each render as `-` (printable-only, 64-char capped, leading `=+@` chars stripped), so
  BUILD's `summarize_channels` tests must expect the sanitized form (e.g. `unmapped:ig/-`),
  not a raw `unmapped:ig/`. Tests: `backend/tests/test_attribution_resolver.py`
  (pure `SimpleNamespace` fakes, no DB).
- **Lead model:** `backend/app/models/operational.py:30` (`__tablename__="leads"`;
  `TimestampMixin` + `SoftDeleteMixin` → has `deleted_at`) — has `source` (44, **not indexed**),
  `external_id` (53, indexed), `ghl_contact_id` (64, indexed), `entry_date` (48, indexed), and
  `utm_{source,medium,campaign,content}_{first,last}` (68–75). **Indexed columns are `email,
  entry_date, external_id, ghl_contact_id, utm_source_first`** — of the six UTM fields the
  breakdown groups on, **only `utm_source_first` is indexed** (corrected: the earlier draft said
  "only `utm_source_first` + `ghl_contact_id`"; `entry_date`/`external_id` are also indexed).
- **Leads list endpoint:** `backend/app/routes/leads.py:184` (`list_leads`). Flat SELECT
  (no join) at **226–234**, returns `id,name,email,phone,status,source,entry_date,created_at`,
  mapped → `LeadRecord` at **252–264**. Server-side filter on `source` only
  (`repositories/list_filters.py:159–161`, exact lowercased match). **No `channel` filter, no
  UTM columns selected.**
- **Lead detail endpoint:** `backend/app/routes/leads.py:338` (`get_lead_detail`,
  `@router.get("/leads/{lead_id}", response_model=LeadDetailResponse)`); lead-row SELECT at
  **355–356** returns `id,name,email,phone,status,source,notes,external_id,entry_date,created_at`
  (plus sub-queries for calls/goals/pain_points/objections/staff_notes). **No UTM fields today.**
  The backend response schema is **`LeadDetailResponse` at `backend/app/schemas/leads.py:165–189`**
  — do not confuse it with the *frontend-local* `LeadDetailResponse` type in
  `[lead_id]/page.tsx:56–73`; both need the new fields (backend Task 3, frontend Task 5).
- **Breakdown builder (shared by Leads AND Sales):** `backend/app/repositories/sales_stats.py:48`
  `compute_lead_stats`; breakdown SQL at **224–246** (SQL text 225–238):
  `SELECT COALESCE(LOWER(source),'other') AS src, COUNT(*) AS cnt FROM leads WHERE deleted_at IS
  NULL{range_sql} GROUP BY src ORDER BY cnt DESC` (the `{range_sql}` filters `entry_date`; grouped
  on the alias `src`). `closed_sales↔leads` join at **161–173** is `external_id`-only, unscoped by
  source (relevant only to Decisions #1 option B). **`compute_lead_stats` returns plain dicts**
  in `data["source_breakdown"]` (`sales_stats.py:244–246`: `{"source","count","percentage"}`), NOT
  `SourceBreakdownItem` objects. `/leads/stats` wraps each via `SourceBreakdownItem(**s)`
  (`leads.py:313`) — so **dict keys and schema fields must stay in lock-step** (Pydantic default
  `extra='ignore'` silently drops undeclared keys; a missing required field raises — Edge case #18);
  `/sales/summary` returns the raw dicts untyped (`routes/sales.py:54`) — so new dict keys
  reach `/sales` automatically. Both routes consume this one object. **The Sales breakdown counts
  leads, not sales/revenue** — it is a lead-source distribution rendered on the sales route.
- **Schemas:** `backend/app/schemas/leads.py` — `LeadRecord` (25–36: `id,name,email,phone,
  status,source,notes,createdAt,score`), `SourceBreakdownItem` (81–86: `source,count,percentage`).
  No channel/platform/reportable anywhere yet.
- **Frontend `/sales` is a redirect to `/leads`** (`frontend/src/app/(app)/sales/page.tsx`,
  8 lines). All breakdown UI lives on `/leads`. There is **no separate sales frontend surface.**
- **Frontend leads list:** `frontend/src/app/(app)/leads/page.tsx` — `Lead` type from
  `src/types/index.ts:72–83` (closed-enum `source`, **no** utm/channel fields); source chip
  render 796–803 via `resolveSource`/`SOURCE_CONFIG` (`SOURCE_CONFIG` is a closed
  `Record<LeadSource, {label; badgeClasses}>` at **156–166**); donut `SourceDonutChart` 453–601
  reading `source_breakdown:{source,count,percentage}[]` (inline field type at line 34, not a
  standalone alias) and `colorForSource` (446–451, hashes any string). Local `FilterBar`
  (880–1008) with a `source` select (941–952); params wired in `fetchLeads` (**1203–1226**,
  `apiClient.get<LeadsListResponse>` at 1216) (`src/lib/api-client.ts:412`).
- **Frontend lead detail:** `frontend/src/app/(app)/leads/[lead_id]/page.tsx` —
  frontend-local `LeadDetailResponse` (56–73, **no utm fields**, `source: string | null`);
  `Card/CardHeader/CardBody` imported line 6; two-column grid **opens at 1048**
  (`grid grid-cols-1 lg:grid-cols-2`) and **closes at line 1154**, immediately followed by a
  Tags card at **1159** — so a new full-width Attribution `Card` inserts cleanly at 1154–1159.
  Contact card renders `source` at 1085–1096 (`resolveSource(detail.source)` at 908). Note the
  existing `TODO(v2): hoist to @/lib/lead-display.ts` (line 207) — source-chip logic is
  duplicated across both pages; **`frontend/src/lib/lead-display.ts` does not exist yet** (Task 4
  optionally creates it).
- **Test harness reality:** backend has **no `conftest.py`, no DB-session/async-client
  fixture**; the only client idiom (`tests/test_error_envelope.py`) builds a throwaway inline
  app. So DB-backed route tests are NOT available — channel logic must be a **pure function
  fed fakes** (like `test_attribution_resolver.py`). Frontend uses **vitest** (`npm run test`,
  one existing test) + `next build` + `next lint` as the real gates.
- **Proof command:** `scripts/verify.sh` (SOP 18) runs frontend lint/typecheck/vitest/build +
  `backend/.venv/bin/python -m pytest tests -q` + security scan. This is the merge gate.

---

## Global constraints (carry into every task)

- **No new migrations / no new tables.** Every column this plan reads already exists.
- **Channel is never stored.** Resolve at read time via the existing resolver; taxonomy
  edits must retroactively change reports (Greg's contract).
- **Row-level first-touch preference, NOT field-level COALESCE** (see Edge case #2 — this
  corrects a contradiction inside Plan A). One lead resolves on its first-touch triple if any
  first-touch field is present, else its last-touch triple — never a mixed triple.
- **Counts must always sum to the lead total.** No bucket silently disappears: unattributed
  → `"No attribution"`; `reportable=False` → `"Non-marketing"`; unmapped capped (top-N +
  `"other unmapped"`), never dropped.
- No native browser dialogs; use shared atoms in `frontend/src/components/ui/` (project rule).
- Any commit wiring a new app surface to an integration updates `INTEGRATIONS.md` in the
  same commit (project rule).
- After each code-modifying task, rebuild the graph before committing. **graphify is installed
  only in `graphify-out/.graphify_venv`** (verified: not importable from the system `python3`),
  so invoke that interpreter: `graphify-out/.graphify_venv/bin/python -c "from graphify.watch
  import _rebuild_code; from pathlib import Path; _rebuild_code(Path('.'))"`. This is a
  maintenance step — **non-blocking to `verify.sh`** (the merge gate does not run it); if it
  errors, note it and proceed rather than blocking the task.
- Backend tests: `cd backend && .venv/bin/python -m pytest tests/<file> -v`. Full gate:
  `./scripts/verify.sh` from repo root. Frontend must pass `next build` (Vercel fails silently
  on lint/type errors). `next build` corrupts a running `next dev` — restart dev clean on 3000.
- **Modified Next.js (Tasks 4–5).** `frontend/AGENTS.md` warns this is a forked Next.js with
  breaking API/convention changes vs. stock — "read the relevant guide in
  `node_modules/next/dist/docs/` before writing any code." Tasks 4–5 are additive rendering that
  reuses existing in-file patterns (the `Card` atoms, `colorForSource`, the existing chip `<td>`
  markup), so they stay on well-trodden paths; still, if BUILD reaches for any Next.js API not
  already used in these files, consult that doc first rather than assuming stock behavior.
- Merge target is `staging`, never `main` (per foundation plan). No co-author trailers.

---

## Tasks (BUILD takes the top item; order is priority)

### Task 0 — Data preflight (cheap go/no-go; do first, ~5 min, no code)

**Why:** Building channel UI on empty attribution data ships a page that shows only
`"No attribution"`/`unmapped:*`. Confirm CI actually has the mirrored data before investing.

**Already answered by commit `f74d9ca` (backfill verified 2026-07-27):** taxonomy **27 rows**;
leads **87 first-touch / 2447 last-touch UTMs / 12347 ghl_contact_ids on 12624 `source='wgr'`
rows** (duplicate `ghl_contact_id`: 0 → the join has no conflict surface). So the data exists and
the gate is GREEN, but **UTM coverage is low (~20% have any touch)** — `"No attribution"` will be
the **largest bucket** on the donut. That is expected and correct (Edge case #4), not a bug.

**Do (a quick re-confirmation only — the backfill numbers above already pass the gate):** From
`backend/`, run read-only counts against CI's own DB (`DATABASE_URL`):
- `SELECT count(*) FROM attribution_taxonomy;` — expect > 0 (was 27 on 2026-07-27).
- `SELECT count(*) FILTER (WHERE utm_source_first IS NOT NULL) AS first_touch,
   count(*) FILTER (WHERE utm_source_last IS NOT NULL) AS last_touch, count(*) AS total
   FROM leads WHERE source='wgr';` — expect `first_touch` and/or `last_touch` > 0.

**Done / proof:** taxonomy count > 0 AND at least one of first/last touch > 0 (already true per
`f74d9ca`). If taxonomy is unexpectedly empty → STOP and re-run the foundation full pull
(`sync_wgr(since='full')`) before any UI work. Set expectations with the client that the channel
breakdown is meaningful for the ~20% of leads carrying UTMs and everything else reads
`"No attribution"` until upstream backfills more first-touch (accepted, not a bug).

---

### Task 1 — Channel helpers + breakdown summarizer (pure, unit-tested) [foundation, unambiguous]

**Why:** Single source of truth for channel logic, unit-testable without a DB (the only
harness available). Both the leads endpoints and the shared breakdown consume it.

**Files:**
- Modify: `backend/app/services/attribution.py` (add two pure helpers next to the resolver).
- Create: `backend/tests/test_leads_channel.py`.

**Add to `attribution.py`:**
```python
def channel_for_lead(resolver, lead) -> Resolution:
    """Row-level first-touch preferred; fall back to last-touch (Greg's grouping rule).
    Never mixes first/last fields. `lead` exposes utm_*_first / utm_*_last attributes."""
    if lead.utm_source_first or lead.utm_medium_first or lead.utm_content_first:
        return resolver.resolve(lead.utm_source_first, lead.utm_medium_first,
                                lead.utm_content_first)
    return resolver.resolve(lead.utm_source_last, lead.utm_medium_last,
                            lead.utm_content_last)

def summarize_channels(combos, resolver, *, unmapped_top_n=8):
    """combos: iterable of (utm_source_first, utm_medium_first, utm_content_first,
    utm_source_last, utm_medium_last, utm_content_last, count). Resolves each distinct
    combo via channel_for_lead semantics, merges counts per bucket, caps unmapped
    cardinality. Returns list[dict(channel, platform, reportable, count)] with buckets:
    canonical channels; 'No attribution' (all-null); 'Non-marketing' (reportable=False);
    'unmapped:*' capped to top_n by count, remainder folded into 'other unmapped'."""
```
Bucket rules (implement exactly): all-null triple → `channel="No attribution"`,
`reportable=False`; a resolution with `reportable=False` → merge under
`channel="Non-marketing"`; `unmapped:*` channels beyond `unmapped_top_n` (by descending
count) → merge under `channel="other unmapped"`. Everything else keyed by
`resolution.channel`. Sum of returned counts == sum of input counts (assert in a test).

**Test (`test_leads_channel.py`)** — mirror the resolver-test style (`SimpleNamespace` fakes,
no DB, no app import beyond `app.services.attribution`):
1. `channel_for_lead` prefers first-touch when a first-touch field is present.
2. `channel_for_lead` falls back to last-touch when all first-touch fields are null.
3. `channel_for_lead` returns `channel is None` when everything is null.
4. `channel_for_lead` never mixes: lead with `utm_source_first="ig"`,
   `utm_medium_last="paid"` resolves on `("ig", None, None)`, NOT `("ig","paid",...)`.
5. `summarize_channels` merges two combos resolving to the same channel into one count.
6. `summarize_channels` routes all-null → `"No attribution"`, `reportable=False` →
   `"Non-marketing"`, and caps unmapped at `unmapped_top_n` with an `"other unmapped"` rollup.
7. `summarize_channels` output counts sum to the input counts (nothing dropped).

**Done / proof:** `cd backend && .venv/bin/python -m pytest tests/test_leads_channel.py -v`
all green; existing `test_attribution_resolver.py` still green. Rebuild graph; commit
`feat: channel_for_lead + channel breakdown summarizer (pure, tested)`.

---

### Task 2 — Wire channel into the shared breakdown (`compute_lead_stats`) [both surfaces inherit]

**Why:** Turns the lead-source donut (on `/leads`, and inherited by `/sales/summary`) into a
canonical-channel breakdown in one place.

**Files:**
- Modify: `backend/app/repositories/sales_stats.py` (`compute_lead_stats`, breakdown block 224–246).
- Modify: `backend/app/schemas/leads.py` (`SourceBreakdownItem`).

**Steps:**
1. Replace the breakdown SQL (`GROUP BY COALESCE(LOWER(source),'other')`) with a group over
   the six UTM fields:
   ```sql
   SELECT utm_source_first, utm_medium_first, utm_content_first,
          utm_source_last,  utm_medium_last,  utm_content_last,
          COUNT(*) AS cnt
   FROM leads
   WHERE deleted_at IS NULL{range_sql}
   GROUP BY 1,2,3,4,5,6
   ```
   (Keep `{range_sql}` on `entry_date` exactly as today so `/leads/stats` date-scoping and
   `/sales/summary` all-time both keep working.)
2. Load taxonomy rows once: `SELECT * FROM attribution_taxonomy` → `build_resolver(rows)`.
   (Import `AttributionTaxonomy` from `app.models.marketing`, or a lightweight raw SELECT —
   the resolver only needs `id, observed_source, observed_medium, observed_content,
   canonical_channel, platform, include_in_channel_reporting`.)
3. Feed the grouped combos to `summarize_channels(...)`; compute `percentage` per bucket from
   the bucket total (same 1-dp rounding as today).
4. **Append plain dicts** (this is what `compute_lead_stats` returns today — do NOT construct
   `SourceBreakdownItem` inside the repository layer): each bucket →
   `{"source": …, "channel": …, "platform": …, "reportable": …, "count": …, "percentage": …}`
   where **`source` is set to the same string as `channel`** during transition, so the current
   frontend donut (which reads `.source`) keeps rendering until **Task 4** switches it to `.channel`.
   The `/leads/stats` route wraps each dict via `SourceBreakdownItem(**s)` (`leads.py:313`); the
   `/sales/summary` route passes the raw dicts through (`sales.py:54`).
5. Extend `SourceBreakdownItem` (`schemas/leads.py:81`): add `channel: str`,
   `platform: str | None = None`, `reportable: bool = True`; keep `source`, `count`, `percentage`.
   **Keep the step-4 dict keys and these schema fields in lock-step.** `SourceBreakdownItem` uses
   Pydantic's default `extra='ignore'`, so a `channel`/`platform`/`reportable` key added to the dict
   but NOT declared on the schema is **silently dropped** from the `/leads/stats` response (the donut
   then never receives `.channel` — a silent gap, not a crash); and a schema field made *required*
   with no default but absent from some dict raises `ValidationError`. Extending the schema here
   **with defaults** closes both (Edge case #18).

**Done / proof:** no DB unit test exists for this path — prove it two ways: (a) `./scripts/verify.sh`
green (schema + import wiring compiles, existing suite passes); (b) manual: hit `/leads/stats`
(or call `compute_lead_stats` in a `python -c` one-liner against CI DB) and confirm the
breakdown returns named channels + a `"No attribution"` bucket, and the counts sum to
`kpis.total_leads`. Also hit `/sales/summary` and confirm its `source_breakdown` carries the
same new keys (it inherits the dicts raw). The `SourceBreakdownItem(**s)` wrapper at
`/leads/stats` is the only place a dict-key/schema-field mismatch surfaces (verify.sh's suite
does not exercise it — see Edge case #18), so step (b) must actually hit that route. Rebuild
graph; commit `feat: canonical channel in the shared lead source/channel breakdown`.

---

### Task 3 — Channel + UTMs on the Leads list & detail endpoints

**Why:** The Leads list Channel column and the detail Attribution card need per-lead channel
and the raw first/last UTM values.

**Files:**
- Modify: `backend/app/routes/leads.py` — list SELECT at **226–234**, row-map to `LeadRecord`
  at **252–264**; detail handler **`get_lead_detail` (line 338)**, lead-row SELECT at **355–356**
  (currently returns no UTM fields).
- Modify: `backend/app/schemas/leads.py` — `LeadRecord` (**25–36**) and the backend detail
  response schema **`LeadDetailResponse` (165–189)** (distinct from the frontend-local type of
  the same name, which Task 5 edits).

**Steps:**
1. **List:** add the 8 `utm_*` columns to the SELECT and row-unpack. Load the resolver once per
   request (`build_resolver` from `attribution_taxonomy`); set
   `channel = channel_for_lead(resolver, row).channel` on each `LeadRecord`. Extend `LeadRecord`
   with `channel: str | None = None` and the 8 `utm_*` fields (nullable). Follow the file's
   existing field-naming convention (note `LeadRecord` uses camelCase `createdAt`; match it, or
   keep snake_case for the new UTM fields and map on the frontend — pick one and be consistent).
2. **Detail:** add the 8 `utm_*` fields + a resolved `channel` to the detail handler's SELECT
   and its response schema. Reuse `channel_for_lead` with a per-request resolver.
3. **Channel filtering = client-side only (accepted).** Do NOT add a server-side `channel`
   filter: channel is computed at read time, not a column, so SQL-side filtering would require
   materializing or resolving in SQL. The existing `source` filter stays. The frontend filters
   the loaded page client-side (Task 4) — note it in code as a follow-up if server-side is
   wanted later.

**Done / proof:** the per-lead channel uses the Task-1 helper (already unit-tested); route-level
DB tests are unavailable, so prove via `./scripts/verify.sh` (compiles + suite green) plus a
manual `GET /leads?per_page=5` / `GET /leads/{id}` showing `channel` + `utm_*` populated for a
lead that has UTMs. Rebuild graph; commit `feat: expose channel + first/last UTMs on leads list
and detail`.

---

### Task 4 — Frontend: Channel on the Leads list + breakdown donut

**Why:** The user-visible half of deliverable 9 on `/leads` (which is also where `/sales`
redirects — see Decisions #1).

**Files:**
- Modify: `frontend/src/types/index.ts` (`Lead` interface + a `SourceBreakdownItem`-shaped type).
- Modify: `frontend/src/app/(app)/leads/page.tsx`.
- Optional (satisfies the existing `TODO(v2)`): create `frontend/src/lib/lead-display.ts` and
  hoist the shared source/channel chip helper there, imported by both leads pages.

**Steps:**
1. Add `channel: string | null` and the 8 `utm_*` fields to the `Lead` interface
   (`types/index.ts:72–83`). **Caution:** an *unrelated* `channel: string` already exists on a
   *different* interface at `types/index.ts:30` (conversation medium) — don't reuse/confuse it.
   Also add `channel/platform/reportable` to the inline breakdown-item field type at
   `leads/page.tsx:34` (it's an inline field type inside the response interface, not a standalone
   alias — extend it in place).
2. Add a **Channel** column to the table (near the Source chip, 796–803). Render channel via a
   hash-color chip — reuse `colorForSource` (446–451, already hashes any string) keyed on
   `channel ?? "No attribution"`. Do NOT route channel through the closed-enum `SOURCE_CONFIG`
   (channel is an open string set). `unmapped:*` channels render with an **amber warning tint**
   so new UTM dialects surface loudly (taxonomy contract).
3. Switch `SourceDonutChart` to read `seg.channel` (payload key stays `source_breakdown`);
   labels are now canonical channels + `"No attribution"` + `"Non-marketing"` + `"other unmapped"`.
   Keep the single-segment full-circle fallback. The donut already caps nothing — with the
   backend top-N unmapped rollup, segment count stays bounded.
4. Add a **Channel** option to the local `FilterBar` select (941–952), filtering the loaded page
   **client-side** on `lead.channel` (server-side channel filter is out of scope per Task 3).
   Leave the existing Source filter as-is.

**Done / proof:** `cd frontend && npm run build` (zero type errors) + `npm run lint`; then
restart dev clean on 3000 and eyeball `/leads`: donut shows named channels, table shows a
Channel column, any `unmapped:*` chips are amber. Rebuild graph; commit `feat: channel column +
channel breakdown on the leads page`.

---

### Task 5 — Frontend: Attribution card on the lead detail page

**Why:** Shows the raw first/last-touch UTMs (unedited, per Greg's contract) + the resolved
channel for a single lead.

**Files:**
- Modify: `frontend/src/app/(app)/leads/[lead_id]/page.tsx`.

**Steps:**
1. Add `channel` + the 8 `utm_*` fields to `LeadDetailResponse` (56–73).
2. Insert a new full-width **Attribution** `Card` immediately after the two-column grid closes
   (**after line 1154**, before the Tags card), using `Card/CardHeader/CardBody` (already
   imported). Show a **First touch** row (`utm_source_first / utm_medium_first /
   utm_campaign_first / utm_content_first`) and a **Last touch** row, plus the resolved channel
   chip (reuse the Task-4 shared chip / `lead-display.ts`).
3. **Hide the card entirely when all 8 UTM fields are null** (many historical leads predate
   attribution — don't show an empty card).

**Done / proof:** `npm run build` + `npm run lint` green; eyeball one lead with UTMs (card shows
first/last values + channel) and one without (card hidden). Rebuild graph; commit `feat:
attribution card on lead detail`.

---

### Task 6 — Docs + verification

**Why:** Project rules require an integration-surface note + a verification section; keeps the
foundation docs honest that the UI now consumes the mirror.

**Files:**
- Modify: `INTEGRATIONS.md` (WGR attribution block: note the Leads/breakdown UI now surfaces
  read-time channel — a new *surface* wired to the existing integration).
- Modify: `FEATURE-VERIFICATION.md` (new "Lead & Sales Source Attribution" section — reuse the
  step-by-step template already sketched in Plan A Task 9 Step 2, but state that `/sales`
  redirects to `/leads` so the check happens on `/leads`).
- Modify: `CHANGELOG.md` (`[Unreleased]`: read-time channel on leads list, breakdown, and lead
  detail; both `/leads/stats` and `/sales/summary` inherit).

**Done / proof:** `./scripts/verify.sh` green (docs don't affect it, but run the full gate before
the final commit); no `[bracketed placeholder]` survives. Commit `docs: lead & sales channel
attribution verification + changelog`.

---

## Decisions needed (a human resolves before the affected task runs)

1. **Sales attribution semantics — BLOCKING for any *sales-specific* task; NOT blocking Tasks
   0–6.** Does deliverable-9 "Sales source attribution" mean:
   - **(A) — what this plan builds:** the existing shared **lead-source** breakdown, relabeled to
     canonical **channel**. `/sales/summary` inherits it automatically from `compute_lead_stats`
     (Task 2). This counts *leads*, not sales/revenue. Plan A and the current code both assume
     (A), and the frontend `/sales` is a redirect to `/leads`, so (A) needs zero sales-specific
     work. **OR**
   - **(B) — net-new, out of scope until chosen:** a genuine **sales/revenue-by-channel**
     breakdown — group `closed_sales` by the buying lead's channel via
     `closed_sales.lead_id → leads.external_id → leads.utm_* → resolver`. This is unbuilt and
     needs its own task, because: `closed_sales`/`sales_activities` carry no UTMs
     (`models/sales.py`); every existing `closed_sales↔leads` join is `external_id`-only and
     **unscoped by source** (`sales_stats.py:161–173`, `analytics/registry.py:108–125`); and the
     spec's mandated `source='wgr'` scoping + `ghl_contact_id` fallback + conflict-counting
     (design spec lines 26, 28, 185–191) is implemented nowhere. If (B) is wanted, it also needs
     a decision on whether a distinct `/sales` frontend surface is rebuilt (it's currently a
     redirect).
   **Recommendation:** ship (A) now (it delivers channel to both surfaces and is unambiguous),
   and open (B) as a follow-on only if the client wants revenue attributed to channel. The BUILD
   loop can complete Tasks 0–6 under (A) without this decision; only a hypothetical Task 7 (B)
   is blocked.

2. **(Non-blocking, pre-decided in this plan — flag if you disagree)** Channel *filtering* is
   client-side only (Task 3/4), because channel is computed at read time. If server-side channel
   filtering / pagination-correct channel filtering is required, that's added scope.

---

## Edge cases & failure modes

| # | Case | Disposition |
|---|------|-------------|
| 1 | **Unmapped cardinality explosion** — `unmapped:<src>/<med>` embeds raw UTM values; many dialects blow up the breakdown + donut. | **Handled** (Task 1 `summarize_channels` top-N + `"other unmapped"`; donut segment count stays bounded). Spec r2 #12. |
| 2 | **First/last-touch mixing** — Plan A's breakdown used field-level `COALESCE(...first,...last)`, which yields a triple matching neither touch and contradicts its own per-lead `_channel_for_lead`. | **Handled** — row-level `channel_for_lead` everywhere (Task 1); breakdown groups on the full 6-tuple and resolves per-combo. Matches Greg's "grouping prefers first-touch." |
| 3 | **Non-reportable rows vanish** — `include_in_channel_reporting=false` excluded → counts don't sum to total. | **Handled** — folded into a `"Non-marketing"` bucket, not dropped (Task 1/2). |
| 4 | **Leads with no UTMs disappear** — historical/pre-attribution leads, AND any lead whose provenance `leads.source` ≠ `'wgr'` (webinar/vsl/ads/referral/other carry no mirrored UTMs), have all-null UTMs. | **Handled** — all land in the `"No attribution"` bucket (Task 1/2), counts still sum to total; detail card hidden (Task 5). Acceptable: deliverable-9 replaces the single generic `'wgr'` provenance bucket (what the donut shows today, since mirrored leads are `source='wgr'`) with named channels. If `"No attribution"` dominates, Task 0's preflight surfaces the low UTM coverage before UI work — not a bug. |
| 5 | **Empty taxonomy at read time** — backfill not run → everything resolves `unmapped:*`/None. | **Handled/gated** — Task 0 preflight catches an empty taxonomy before UI work; at runtime the resolver degrades safely (unmapped, capped) and the amber chips are the visible signal to seed/backfill. |
| 6 | **Resolver load per request** — loads all taxonomy rows every call. | **Accepted** — taxonomy is tiny (spec: "None (load per request)"); add caching only if profiled hot. |
| 7 | **Breakdown GROUP BY on unindexed text columns** — of the six grouped UTM columns only `utm_source_first` is indexed (the other five are not); `/sales/summary` is all-time. The range filter's `entry_date` IS indexed. | **Accepted / watch** — distinct combos are few at current lead volume; revisit with a covering index or materialization only if leads grow large. |
| 8 | **Transitional `source == channel` overload** — Task 2 sets `SourceBreakdownItem.source = channel` for frontend compatibility. | **Handled** — only the breakdown item's `source` is overloaded; the `leads.source` *column* and its server-side filter are untouched. The donut is the sole consumer (verified). Drop the overload after Task 4 switches to `.channel` (follow-up noted in code). |
| 9 | **"Sales = leads, not revenue" misread** — relabeling the Sales-page breakdown to "channel" may imply revenue-by-channel. | **Decisions #1** — (A) keeps it a lead distribution (label it "Lead channel mix"); (B) is the out-of-scope revenue join. |
| 10 | **external_id/ghl_contact_id join scoping** — existing `closed_sales↔leads` joins are `external_id`-only, unscoped by source. | **Out of scope** for (A) — this plan reads `leads` directly and never joins sales tables. Required only if Decisions #1 chooses (B). |
| 11 | **Open channel string vs closed `LeadSource` enum** — frontend `SOURCE_CONFIG` is a closed enum; channel is open (`unmapped:*`, `No attribution`, etc.). | **Handled** — render channel via `colorForSource` hash (handles any string), not `SOURCE_CONFIG`; amber tint for `unmapped:*` (Task 4). |
| 12 | **Empty Attribution card** on leads with no UTMs. | **Handled** — hidden when all 8 fields null (Task 5). |
| 13 | **Percentages don't sum to 100** (1-dp rounding). | **Accepted** — pre-existing cosmetic behavior, unchanged. |
| 14 | **Breaking the one existing frontend vitest test / build** with new code. | **Handled** — run `./scripts/verify.sh`; keep `tour-logic.test.ts` green; new chip helper may get an optional vitest test but the gate is build+lint. |
| 15 | **`next build` corrupts a running `next dev`** (verify.sh note). | **Operational** — restart dev clean on 3000 after any build. |
| 16 | **Race: read during hourly taxonomy reconciliation** — a channel resolution mid-way through the snapshot+delete-reconciliation of `attribution_taxonomy` could see a transiently partial taxonomy → a lead resolves to a slightly different channel between two page loads. | **Accepted** — read-time resolution is idempotent and self-heals on the next request; the reconciliation itself is count-guarded + circuit-breakered upstream (foundation). No stored derived state to corrupt. |
| 17 | **Auth / data exposure** — the new API fields (`utm_*`, resolved `channel`) are marketing identifiers newly surfaced on the leads endpoints. | **Handled/accepted** — served under the same lead auth boundary that already returns names/emails/phones/transcripts; the design spec's Data-sensitivity note says no new access policy is needed. No new endpoint, no new role; `ghl_contact_id` is not added to any list/detail response by this plan (only the UTM triple + channel). |
| 18 | **Breakdown dict / schema drift** — `compute_lead_stats` emits plain dicts; `/leads/stats` constructs `SourceBreakdownItem(**s)` (`leads.py:313`). The schema uses Pydantic's default `extra='ignore'`, so a new dict key the schema doesn't declare is **silently dropped** (the `/leads/stats` donut never gets `.channel` — a silent gap, not a crash); conversely a schema field made *required* with no default but missing from some dict raises `ValidationError`. `/sales/summary` returns the raw dicts (no validation), so it always ships whatever keys the dict carries — the two routes can silently diverge. **No DB test covers this path.** | **Handled** — Task 2 step 5 keeps dict keys and schema fields in lock-step and defaults every new field; Task 2 proof step (b) must hit `/leads/stats` (the only validating consumer), not rely on `verify.sh`. |

**Rollback path:** every change here is **additive and read-time** — new response fields, a new
pure module, a changed GROUP BY, and frontend rendering. **No DB migration** (all columns exist
from the foundation), so there is no schema downgrade. Rollback = `git revert` the deliverable-9
commits; the WGR mirror and the foundation are untouched, and because channel is never stored
there is no derived data to unwind. If only the frontend regresses, revert Tasks 4–5 and the API
still serves the (harmless, additive) new fields.

---

## Out of scope (explicit)

- Sales/revenue-by-channel from `closed_sales` (Decisions #1 option B) and any `source='wgr'`
  join-scoping / `ghl_contact_id` fallback / conflict-counting work.
- A distinct `/sales` frontend surface (currently a redirect to `/leads`).
- Server-side channel filtering / pagination-correct channel filters.
- RAG/embedding of the new attribution tables (foundation-noted open policy gap, tracked
  separately).
- Ads section (ClickUp 86d3u65cc) and all other follow-on deliverables.
- `commenter_lead_links` / DM identity bridge (deferred at the foundation).
