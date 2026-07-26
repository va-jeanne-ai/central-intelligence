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
2. **`attribution_taxonomy`:** WGR bigint id kept as PK; full pull every run
   (tiny, no watermark) so upstream edits and deletes-by-edit propagate.
3. **`lead_engagements`:** native text PK `engagement_id`; WGR `lead_id`
   stored as plain-text `wgr_lead_id`; watermark `created_at`.
4. **`meta_campaigns` / `meta_ads` / `meta_ad_performance`:** native text PKs
   (`campaign_id` / `ad_id` / `perf_id`); watermarks `updated_at` /
   `updated_at` / `created_at`. Gated on probe.

**Out of scope:** `commenter_lead_links`; any channel UI (deliverable-9
ticket); RAG/embedding hookup for the new tables (open policy gap, tracked
separately); coaching/EOD/webinar tables (already mirrored).

## Components

- **`backend/scripts/probe_wgr_attribution.py`** — read-only probe printing row
  counts/coverage for every new source. Go/no-go gate: `leads.utm_source_first`
  missing → stop the feature and surface (WGR hasn't received Greg's
  migrations); `meta_ad_performance` empty → skip the meta mirror.
- **Sync extension** — new `map_*` functions in `wgr_sync/mapping.py`,
  `_NATIVE_PLAN` registrations in `wgr_sync/upsert.py`, watermark entries in
  `wgr_sync/reader.py`. The hourly Celery task calls `sync_all()`, which
  iterates the plan — no task changes.
- **`backend/app/services/attribution.py`** — `build_resolver(rows) -> Resolver`;
  `Resolver.resolve(source, medium, content) -> Resolution(channel, platform,
  reportable)`. Contract (from Greg's migration `20260724_000000`):
  case-insensitive on the triple; NULL observed_* = wildcard; most-specific
  match wins (content beats source+medium beats source-only); ties by lowest
  id; no match → `unmapped:<source>/<medium>` with `reportable=True`;
  `include_in_channel_reporting=false` rows resolve with `reportable=False`;
  all-empty input → `Resolution(None, None, False)`. Ships in the foundation so
  deliverable 9 consumes it ready-made.
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

## Process notes

- Branch `feature/wgr-attribution-sync` off latest main → merge to staging.
- INTEGRATIONS.md updated in the same commit as the last sync-expansion task
  (project same-commit rule); FEATURE-VERIFICATION.md + CHANGELOG entries ship
  with the feature; graphify rebuild before each code commit.
- No paid API calls anywhere in this feature.
