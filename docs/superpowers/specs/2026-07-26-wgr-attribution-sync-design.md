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
| Snapshot-table deletions (`attribution_taxonomy`, `meta_campaigns`, `meta_ads`) | **Snapshot + delete-reconciliation against RAW ids, count-guarded** | Upserts never delete, and a stale taxonomy rule would keep winning resolution (stale ads/campaigns would look active). Each run pulls the full table and deletes CI rows absent from the **raw** (successfully read) id set — NOT the mapped set: reconciling on mapped ids would turn a mapper bug or upstream type drift into mass deletion (r3 #3 — this supersedes the r2 #5 position; a present-but-unmappable row is kept, skipped, and loudly counted instead of deleted). One deliberate exception (r4): a taxonomy row whose `canonical_channel` is nulled/blanked upstream is a *source-data disable statement*, checkable on the RAW row — it is excluded from the raw-id set and reconciled away, so a disabled rule stops resolving instead of resolving with its stale channel. Guard against silent partial reads (r3 #2): a source-side `COUNT(*)` (a separate advisory query — NOT a same-snapshot guarantee; the single-statement read below is what provides consistency) must match the rows actually read, else reconciliation is skipped for that run. Failure semantics: a read failure or count mismatch aborts reconciliation (transient problems can never wipe the mirror); a *successful, count-confirmed* pull returning 0 rows is honored — upstream legitimately emptied the table, CI empties too (r2 #4/r3 #4: this single rule applies everywhere; there is no separate "non-empty" condition). These tables are far smaller than one page, and snapshot reads use page_size 10 000 → a single SQL statement → Postgres statement-level MVCC consistency; a page-overflow tripwire skips reconciliation if that assumption ever breaks. **Deletion circuit breaker (r6 #1):** reconciliation that would delete >10 rows AND >20% of the CI table (or would fully wipe a populated table, at any size) skips and demands the table-scoped override `WGR_SYNC_MASS_DELETE_TABLE=<table>` for one deliberate run (via `docker compose exec -e` — see Rollback) — so a wrong replica, source cutover, permission change, or upstream truncate can trim nothing without a human. The confirmed-empty rule operates through the breaker: emptying a populated mirror always requires the override. |
| Lead joins from mirror tables | **`external_id` first, `ghl_contact_id` fallback** | The lead email-merge path (`plan_lead_writes` case 4) preserves a pre-existing lead's `source`/`external_id`, so `wgr_lead_id → leads.external_id` misses email-merged leads. `ghl_contact_id` is a data column (survives merges) and exists on both sides. A crosswalk table was considered and rejected as over-engineering (audit finding #1). |
| Meta Ads tables | **Gated on probe, per table family (r6 #14)** | Skipped only if ALL THREE meta tables are empty at probe time; if any has rows, all three are mirrored (empty ones sync to empty and fill when upstream produces). No speculative mirrors when the whole family is empty. |
| FKs on mirrored tables | **None** | Mirror data tolerates orphans (WGR filters/test rows); joins go through `leads.external_id` (source='wgr'). |
| Resolver caching | **None (load per request)** | Taxonomy is tiny; add caching only if profiling shows it hot. |

## Scope

**Mirrored into CI's own DB (`DATABASE_URL`), sourced from WGR (`CLIENT_DATABASE_URL`; the legacy name `WGR_DATABASE_URL` is still accepted by config):**

1. **`leads` — 9 new nullable columns:** `utm_source_first`, `utm_medium_first`,
   `utm_campaign_first`, `utm_content_first`, `utm_source_last`,
   `utm_medium_last`, `utm_campaign_last`, `utm_content_last`,
   `ghl_contact_id`. Verbatim, never rewritten. `leads.source` stays sync
   provenance (`'wgr'`) — never overloaded with marketing attribution.
2. **`attribution_taxonomy`:** WGR bigint id kept as PK; full snapshot every
   run (tiny, no watermark) **with delete-reconciliation** — CI rows whose id
   is absent from a successful, count-confirmed pull are deleted (raw-id set;
   see Decisions for the exact rule — a confirmed-empty pull empties CI), so
   upstream edits AND deletions propagate.
3. **`lead_engagements`:** native text PK `engagement_id`; WGR `lead_id`
   stored as plain-text `wgr_lead_id`; watermark `created_at`. Append-mostly
   upstream; post-insert edits are missed until a `sync_wgr(since='full')`
   run (documented limitation — no `updated_at` exists upstream).
4. **`meta_campaigns` / `meta_ads`:** native text PKs, **snapshot +
   delete-reconciliation every run** (small config tables — upstream edits AND
   deletions self-heal). **`meta_ad_performance`:** text PK `perf_id`,
   watermark `created_at` (no `updated_at` exists upstream); later edits to
   kpi_status/notes are missed until a `sync_wgr(since='full')` run
   (documented limitation). **Gating is per table family** (r6 #14): Task 5 is skipped
   only when all three meta tables are empty; if any has rows, all three are
   mirrored (empty ones sync to empty and fill whenever upstream starts
   producing — no re-enable action needed). Only the all-empty case needs
   manual re-evaluation, recipe on the Ads ticket (86d3u65cc): re-run the
   probe; if rows now exist, execute plan Task 5 on a fresh branch.

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
  triples — wildcard/NULL rows included — are prevented upstream by WGR's
  expression unique index on `lower(coalesce(observed_*, ''))` (verified in
  his migration `20260724_000000`, lines 42–47; r5 #8's NULLS-NOT-DISTINCT
  concern does not apply to an expression index over coalesced values).
  Two documented divergences (r6 #9–#10): CI's normalization also TRIMS
  whitespace, which WGR's index does not — upstream rows differing only by
  padding collapse in CI and resolve deterministically by lowest id
  (pathological seed data, benign outcome); and a highly specific
  non-reportable rule DOES win resolution over a less-specific reportable
  one, marking the touch non-reportable — that is Greg's contract ("honest
  origins, not marketing touches"), not an accident. **Taxonomy edits
  retroactively change historical reports by design** — that is Greg's
  read-time-normalization contract ("no backfill rewrite"); if reproducibility
  is ever needed, stamp reports with a taxonomy revision (future option, not
  built). **`utm_campaign` is intentionally outside the resolution contract**
  (r4): Greg's `attribution_taxonomy` has no `observed_campaign` column — his
  contract is the (source, medium, content) triple; campaign is mirrored as
  data and displayable, never matched on. Ships in the foundation so
  deliverable 9 consumes it ready-made.
- **Four hand-written Alembic migrations** (lead columns; taxonomy;
  engagements; meta tables — y6d7…, z7e8…, a8f9…, b9a0…). No autogenerate
  (project rule — it emits spurious index drops).

## Data flow

Hourly `sync_wgr` (:50 UTC) → watermark-scoped `reader.read_table` →
`mapping.map_*` → idempotent batched upserts (existing `_NATIVE_PLAN` /
batch-500 machinery). One-time full pull after migration populates history —
**command: `sync_wgr(since='full')`**, the same everywhere in this feature
(see Schema evolution → cadence; `scripts/backfill_wgr.py` is the legacy
bulk_load path and does not cover these tables — r5 #1 resolved this
section's stale reference).

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

## Schema evolution — the operating model (owner: Jeanne)

CI's mirror schema is deliberately decoupled from Greg's: our tables are
shaped for our app, and they change only when we change them. When Greg
changes his database, the workflow is **manual and owned by us**:

1. Signal: the `sync_leads` drift tripwire warns in logs when expected
   upstream columns disappear; new upstream tables/columns are discovered by
   re-running `scripts/probe_wgr_attribution.py` (or hearing it from Greg).
2. Decide whether CI needs the new data (does a surface or the recommendation
   engine want it?). If not, ignore it — the sync only pulls what we map.
3. If yes: hand-written Alembic migration → extend the mapper → extend the
   probe's expected-columns set → test → backfill. Same pattern as this
   feature, every time.

Cadence note (r3 #9): run a full pull after any mapper/schema change, after
EOD server-off gaps (existing practice), and roughly monthly as the
correction sweep for the `created_at`-watermarked tables. **The full-pull
command is `sync_wgr(since='full')`** (in-process:
`python -c "from app.tasks.wgr_sync import sync_wgr; print(sync_wgr(since='full'))"`)
— NOT `scripts/backfill_wgr.py`, which drives the legacy `bulk_load` loader
whose separate `_PLAN` does not cover the attribution-era tables (r4 catch);
the sync-task path also honors `client_sync_enabled`, so the kill switch
gates both scheduled and manual pulls.

Deployment order (r3 #16) is handled by the droplet's compose stack: the
one-shot `migrate` service runs Alembic before api/worker/beat start, and all
migrations in this feature are additive, so old code + new schema coexist
safely during the deploy window. For rollback order, follow the **Rollback
section below verbatim** — in particular, any schema downgrade happens
BEFORE the code revert, never after (self red-team: an earlier draft of this
paragraph taught the reverse order, which bricks the compose stack).

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
  `meta_ad_performance` (no upstream `updated_at`); healed by the periodic
  `sync_wgr(since='full')` sweep (see cadence — never `backfill_wgr`, which
  cannot see these tables).
- **Sync concurrency: RESOLVED in-feature (r6, hardened r7)** — a Redis run
  lock (plan Task 5b) serializes hourly beat, user trigger, and manual full
  pulls; latecomers skip with an explicit status. Lock craft per r7: unique
  owner token, compare-and-delete release (never frees a successor's lock),
  fail-closed when Redis is unreachable, 2-hour TTL (≫ run time, no renewal
  machinery), acquired before the watermark is read. (Redis, not Postgres
  advisory locks, because the app DB sits behind Supabase's pooler.) Trigger
  rate-limiting/role-gating stays in hardening ticket 86d3u66pj.
- **Manual partial pulls never advance the canonical watermark (r7)** —
  `sync_wgr(since=<ISO>)` repairs a window without touching the cursor; only
  incremental (None) and `since='full'` runs own it. Closes the
  operator-poisons-history path (`since=now` would otherwise skip everything
  between the old watermark and now, forever).
- **Lead deletion policy (r7):** CI leads are append-only — WGR lead
  deletions are not propagated (upstream deletes leads essentially never;
  test rows are filtered at map time). If that changes, leads get the
  soft-delete treatment (the model already carries SoftDeleteMixin), not
  hard reconciliation.
- **LIMIT/OFFSET pagination can skip rows under live upstream writes** —
  affects every mirrored table today. Hardening ticket: keyset pagination on
  `(watermark, pk)`.
- **WGR credential: RESOLVED as a prerequisite (r6, enforced r7)** — plan
  Task 0 provisions a dedicated `ci_reader` SELECT-only Postgres role on
  the WGR project; every WGR connection in this feature runs on it, with
  Postgres enforcing the boundary rather than our session flag.
  **Provisioning is self-service** (Jeanne, 2026-07-26): we run the CREATE
  ROLE SQL ourselves over the existing `postgres` DSN — a one-time,
  documented exception to the read-only rule (role DDL only; no app tables
  or data touched), matching how Greg applies SQL to his projects; Greg
  gets an FYI plus a rotation recommendation afterwards. Enforcement is
  verified at runtime, not asserted: the probe checks
  `current_user = 'ci_reader'` and fails its gate on any other role, and
  Task 0 includes a plain-connection write probe proving CREATE is denied.
- **Mass-delete override is table-scoped AND process-scoped (r7 + internal
  red-team)** — `WGR_SYNC_MASS_DELETE_TABLE=<table>` authorizes exactly one
  table's reconciliation and is supplied via `docker compose exec -e` for the
  single deliberate run (never written to `.env`, where it would persist
  until the next container recreation). Every reconciliation deletion writes
  a `sync_log` audit row (`wgr_snapshot_reconcile`) carrying the deleted ids
  — the rollback artifact for the only destructive step in the feature. The
  breaker trips unconditionally on a full-wipe of a populated table, at any
  size.
- **Data sensitivity:** UTMs and `ghl_contact_id` are marketing identifiers;
  CI already stores names/emails/phones/transcripts under the same auth
  boundary, and agent SQL access goes through the business-prose gate. No new
  access policy needed for this feature.

## Rollback

WGR is the durable source of truth; CI mirrors are rebuildable by design, and
no CI report references this data until deliverable 9 ships. Rollback path:

Order matters — steps corrected per the internal ops red-team (the previous
order would have bricked the compose stack: reverting code deletes the
migration files, after which the one-shot `migrate` service cannot locate the
DB's revision and api/worker/beat never start).

1. **Kill switch, with real semantics:** set `CLIENT_SYNC_ENABLED=false` in
   the droplet's env, then `docker compose up -d` — **recreation, not
   `restart`** (restart/stop+start never reload `env_file`; the flag is read
   into settings at process start). The task checks it at run start.
2. **Revoke queued WGR sync tasks WHILE WORKERS ARE STILL UP** (inspect gets
   no replies and revoke broadcasts to nobody once they're stopped):
   `docker compose exec worker celery -A app.tasks.celery_app inspect reserved`
   and `… inspect scheduled` (one action per invocation), then
   `… control revoke <task-id>` for each `app.tasks.wgr_sync.sync_wgr` entry.
   Never blanket `celery purge` — it discards unrelated email/embed work.
   Then `docker compose stop worker beat`. A killed run leaves committed
   batches in place — the mirror is *replayable*, not atomically undone; the
   un-advanced watermark makes the next clean run converge. Stragglers that
   survive revocation are gated by the kill switch + run lock anyway.
3. **Schema decision BEFORE touching code** (if schema removal is wanted):
   `docker compose run --rm migrate alembic downgrade x5c6d7e8f9a0` — a named
   revision, not a count (the feature has FOUR migrations: y6d7…, z7e8…,
   a8f9…, b9a0…). This must run while the feature image/migration files
   still exist. Safe today because every mirrored value exists upstream and
   nothing in CI references the tables yet; **destructive to CI reporting
   state once deliverable 9 ships** — then prefer keeping the schema
   (additive schema + old code coexist fine).
4. **Now revert the feature branch** and `docker compose up -d --build` so
   workers load the reverted code. If you skipped step 3, keep the migration
   files in the revert (additive-only) so `migrate` still recognizes the DB
   revision.
5. Re-enable: `CLIENT_SYNC_ENABLED=true` + `docker compose up -d` (recreate
   again).

**Mass-delete override procedure** (one-run semantics for real): never bake
`WGR_SYNC_MASS_DELETE_TABLE` into `.env` — run the one deliberate
reconciliation as
`docker compose exec -e WGR_SYNC_MASS_DELETE_TABLE=<table> worker python -c
"from app.tasks.wgr_sync import sync_wgr; print(sync_wgr(since='full'))"` —
the variable exists only for that process, so nothing needs unsetting and the
hourly worker never sees it.

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
