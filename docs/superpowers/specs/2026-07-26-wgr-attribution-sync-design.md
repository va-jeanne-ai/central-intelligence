# WGR Attribution Data Sync (Foundation) — Design

**Date:** 2026-07-26
**Ticket:** ClickUp 86d3u65c6 — WGR Attribution Data Sync
**Status:** Approved (design review 2026-07-26)
**Unblocks:** Leads & Sales source attribution (86d3u65cb), Marketing Ads section (86d3u65cc)

## Purpose

Mirror Greg's attribution-era data from the WGR database into CI so the
recommendation engine and the week-of-July-27 UI deliverables see his cleaned
attribution instead of CI's "Unattributed" fallback. CI's analytics currently
report ~83% of sales_activities and ~40% of closed sales as unattributed;
Greg fixed this upstream (first/last-touch UTM capture, taxonomy-based channel
normalization) and CI does not yet mirror any of it.

Strictly a read-only mirror: CI never writes to the WGR database.

## Decisions

| Decision | Choice | Why |
|---|---|---|
| Channel resolution | **Python read-time resolver** (`services/attribution.py`) | Unit-testable contract; honors Greg's raw-never-rewritten / normalize-at-read rule; fits CI's Python-first analytics. SQL views (Greg's approach) rejected as untestable-in-unit and gnarly for the specificity rules; sync-time materialization rejected because taxonomy edits would leave stale channels. |
| `commenter_lead_links` (DM identity bridge) | **Deferred** | Auto-linked commenters already carry first-touch UTMs on `leads` upstream; mirror the bridge only when a surface needs commenter-level drill-down or review-queue visibility. |
| Snapshot-table deletions (`attribution_taxonomy`, `meta_campaigns`, `meta_ads`) | **Snapshot + delete-reconciliation** | Upserts never delete, and a stale taxonomy rule would keep winning resolution (stale ads/campaigns would look active). Each run pulls the full table and deletes CI rows absent from the **mapped** pull. Failure semantics: a read failure raises and aborts the run before reconciliation (transient failures can never wipe the mirror); a *successful* pull returning 0 mapped rows is honored — upstream legitimately emptied the table, CI empties too, and the next hourly run restores whatever reappears. Rows the mapper skips (e.g. canonical_channel gone NULL) are deleted rather than left resolving with a stale channel. (Audit findings #2 r1; #4, #5, #18 r2.) |
| Lead joins from mirror tables | **`external_id` first, `ghl_contact_id` fallback** | The lead email-merge path (`plan_lead_writes` case 4) preserves a pre-existing lead's `source`/`external_id`, so `wgr_lead_id → leads.external_id` misses email-merged leads. `ghl_contact_id` is a data column (survives merges) and exists on both sides. A crosswalk table was considered and rejected as over-engineering (audit finding #1). |
| Meta Ads tables | **Gated on probe** | Mirrored only if the read-only probe finds rows in `meta_ad_performance`; no speculative mirrors. |
| FKs on mirrored tables | **None** | Mirror data tolerates orphans (WGR filters/test rows); joins go through `leads.external_id` (source='wgr'). |
| Resolver caching | **None (load per request)** | Taxonomy is tiny; add caching only if profiling shows it hot. |

## Scope

**Mirrored into CI's own DB (`DATABASE_URL`), sourced from WGR (`WGR_DATABASE_URL`):**

1. **`leads` — 9 new nullable columns:** `utm_source_first`, `utm_medium_first`,
   `utm_campaign_first`, `utm_content_first`, `utm_source_last`,
   `utm_medium_last`, `utm_campaign_last`, `utm_content_last`,
   `ghl_contact_id`. Verbatim, never rewritten. `leads.source` stays sync
   provenance (`'wgr'`) — never overloaded with marketing attribution.
2. **`attribution_taxonomy`:** WGR bigint id kept as PK; full snapshot every
   run (tiny, no watermark) **with delete-reconciliation** — CI rows whose id
   is absent from a successful non-empty pull are deleted, so upstream edits
   AND deletions propagate.
3. **`lead_engagements`:** native text PK `engagement_id`; WGR `lead_id`
   stored as plain-text `wgr_lead_id`; watermark `created_at`. Append-mostly
   upstream; post-insert edits are missed until a full `backfill_wgr` run
   (documented limitation — no `updated_at` exists upstream).
4. **`meta_campaigns` / `meta_ads`:** native text PKs, **snapshot +
   delete-reconciliation every run** (small config tables — upstream edits AND
   deletions self-heal). **`meta_ad_performance`:** text PK `perf_id`,
   watermark `created_at` (no `updated_at` exists upstream); later edits to
   kpi_status/notes are missed until a full `backfill_wgr` run (documented
   limitation). All gated on probe. **Gate re-evaluation:** the gate is not a
   permanent off-switch — if skipped, the Ads ticket (86d3u65cc) carries the
   re-enable recipe (re-run the probe; if rows now exist, execute plan Task 5
   on a fresh branch). Manual re-evaluation is acceptable at this scale.

**Out of scope:** `commenter_lead_links`; any channel UI (deliverable-9
ticket); RAG/embedding hookup for the new tables (open policy gap, tracked
separately); coaching/EOD/webinar tables (already mirrored).

## Components

- **`backend/scripts/probe_wgr_attribution.py`** — read-only probe that, per
  source table: verifies readability (`SELECT * LIMIT 1`), diffs the actual
  column set against every column the mappers consume (missing columns are
  named), and prints row counts/coverage. Go/no-go gate:
  `leads.utm_source_first` missing → stop the feature and surface (WGR hasn't
  received Greg's migrations); `meta_ad_performance` empty → skip the meta
  mirror. A probe pass means: table readable + all mapped columns present +
  counts recorded; it does not guarantee type compatibility (mappers pass
  values through; the backfill run is the type gate).
- **Sync extension** — new `map_*` functions in `wgr_sync/mapping.py`,
  `_NATIVE_PLAN` registrations in `wgr_sync/upsert.py`, watermark entries in
  `wgr_sync/reader.py`. The hourly Celery task calls `sync_all()`, which
  iterates the plan — no task changes.
- **`backend/app/services/attribution.py`** — `build_resolver(rows) -> Resolver`;
  `Resolver.resolve(source, medium, content) -> Resolution(channel, platform,
  reportable)`. Contract (from Greg's migration `20260724_000000`):
  case-insensitive on the triple; NULL observed_* = wildcard; most-specific
  match wins; ties by lowest id; no match → `unmapped:<source>/<medium>` with
  `reportable=True`; `include_in_channel_reporting=false` rows resolve with
  `reportable=False`; all-empty input → `Resolution(None, None, False)`.
  **Specificity is exactly the count of concrete (non-wildcard) observed
  fields on the rule (3 > 2 > 1)** — so a hypothetical content-only wildcard
  rule loses to a concrete source+medium rule; deterministic, and matches
  Greg's seed data (his content rules always carry source+medium too).
  Normalization = `strip().lower()`; empty string ≡ NULL. Duplicate observed
  triples are prevented upstream by WGR's unique index. **Taxonomy edits
  retroactively change historical reports by design** — that is Greg's
  read-time-normalization contract ("no backfill rewrite"); if reproducibility
  is ever needed, stamp reports with a taxonomy revision (future option, not
  built). Ships in the foundation so deliverable 9 consumes it ready-made.
- **Three hand-written Alembic migrations** (lead columns; taxonomy;
  engagements + meta tables). No autogenerate (project rule — it emits spurious
  index drops).

## Data flow

Hourly `sync_wgr` (:50 UTC) → watermark-scoped `reader.read_table` →
`mapping.map_*` → idempotent batched upserts (existing `_NATIVE_PLAN` /
batch-500 machinery). One-time `python -m scripts.backfill_wgr` run after
migration populates history.

## Error handling

- `map_*` functions use `.get()` everywhere — older WGR snapshots lacking a
  column yield `None`, never a crash.
- Backfill validation: any expected-nonzero table reporting 0 rows halts the
  feature until diagnosed against probe counts.
- Orphan `meta_ad_performance.ad_id` values tolerated (no FK).
- Rows without a usable PK (or taxonomy rows without `canonical_channel`) are
  skipped by the mapper (return `None`), matching existing sync behavior.

## Testing

- Mapping unit tests per table in `tests/test_wgr_mapping.py` (incl.
  missing-column tolerance).
- Resolver contract tests in `tests/test_attribution_resolver.py`:
  specificity ordering, wildcards, case-insensitivity, tie-break by id,
  unmapped format, non-reportable flag, empty input.
- Existing `test_wgr_lead_email_merge.py` re-run proves the new lead keys
  don't break `plan_lead_writes`.
- Backfill spot-check: landed counts vs probe counts; sample WGR lead shows
  UTM values in CI.

## Known limitations & inherited properties (2026-07-26 audit)

Accepted for this feature; the systemic items are tracked in a separate
hardening ticket because they predate it and affect all ~20 existing mirrors:

- **Email-merged leads break `external_id` joins** — mitigated by the
  `ghl_contact_id` fallback (see Decisions); residual gap only for merged
  leads with no GHL id. Join consumers (deliverable 9) must scope the
  `external_id` match with `source='wgr'`, prefer the wgr-sourced row when
  both keys match different leads, and count such conflicts rather than
  resolve them silently (r2 #7–#8 — enforcement lives in the deliverable-9
  plan, since this feature ships no joins).
- **Unmapped channel labels embed raw UTM values** by Greg's design (surface
  loudly). Reporting surfaces must cap cardinality (top-N + "other unmapped")
  — deliverable-9 concern, noted forward (r2 #12).
- **Watermark semantics are at-least-once, not exactly-once:** reader filters
  `>= watermark` with a 5-minute lookback (`WATERMARK_LOOKBACK`), watermark
  persists only on clean runs, upserts are idempotent — duplicates are
  harmless refreshes; an upstream transaction open longer than 5 minutes at
  run time could still commit rows behind the watermark (accepted; healed by
  full backfills; keyset pagination tracked in hardening ticket 86d3u66pj).
- **`created_at` watermarks miss post-insert edits** on `lead_engagements` /
  `meta_ad_performance` (no upstream `updated_at`); healed by periodic full
  `backfill_wgr` runs.
- **No sync concurrency lock** (hourly beat + user trigger can overlap) —
  self-healing by design: watermark only advances on clean runs, upserts are
  idempotent, and the leads unique index turns races into a failed run, not
  corruption. Hardening ticket: advisory lock + return-active-run.
- **LIMIT/OFFSET pagination can skip rows under live upstream writes** —
  affects every mirrored table today. Hardening ticket: keyset pagination on
  `(watermark, pk)`.
- **`CLIENT_DATABASE_URL` is the write-capable `postgres` role**, made safe
  only by session-level READ ONLY on this code path (documented footgun in
  `wgr_client.py`). Hardening ticket: ask Greg for a dedicated
  SELECT-only role.
- **Data sensitivity:** UTMs and `ghl_contact_id` are marketing identifiers;
  CI already stores names/emails/phones/transcripts under the same auth
  boundary, and agent SQL access goes through the business-prose gate. No new
  access policy needed for this feature.

## Rollback

WGR is the durable source of truth; CI mirrors are rebuildable by design, and
no CI report references this data until deliverable 9 ships. Rollback path:

1. Set `client_sync_enabled=false` (stops NEW hourly + on-demand runs; the
   task checks it at start).
2. Drain in-flight work before touching schema: `docker compose stop worker
   beat` on the droplet (or locally, stop the celery processes). An already-
   running sync finishes or dies with the worker; the watermark only advances
   on clean completion, so a killed run is safe.
3. Revert the feature branch (resolver + sync registrations disappear;
   `sync_all` returns to the prior table set). Redeploy so workers load the
   reverted code.
4. `alembic downgrade` through the three migrations if schema removal is
   wanted — safe TODAY because every mirrored value still exists upstream in
   WGR and nothing in CI references the tables yet; **this step becomes
   destructive to CI reporting state once deliverable 9 ships** — after that,
   prefer stopping at step 3 and leaving the schema in place.
5. Re-enable `client_sync_enabled` and restart workers.

"Bad but successful data" (r2 #24): for a pure mirror, replaying current WGR
IS the recovery — a mapper bug is fixed in code and the next full backfill
overwrites every derived value. CI-side state that a backfill cannot restore
does not exist in this feature.

## Process notes

- Branch `feature/wgr-attribution-sync` off latest main → merge to staging.
- INTEGRATIONS.md updated in the same commit as the last sync-expansion task
  (project same-commit rule); FEATURE-VERIFICATION.md + CHANGELOG entries ship
  with the feature; graphify rebuild before each code commit.
- No paid API calls anywhere in this feature.
