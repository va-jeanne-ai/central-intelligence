# Plan — Pull client Supabase data into Central Intelligence

> Companion to [client-supabase-connection.md](client-supabase-connection.md). Read that first for the schema.
> **Goal:** ingest the client's GHL-mirror Supabase (`mntsbmuxbdnnlnheuwqk`) — `leads`, `appointments`, `calls` — into CI's own tables + RAG store, incrementally and idempotently.

---

## 0. Decisions to confirm before building (do not skip)

1. **Auth split.** ✅ **DONE (2026-06-17).** Client project moved to dedicated `CLIENT_SUPABASE_*` vars; primary `SUPABASE_*` restored to CI's own project (`iqqobmubutxwhtvpdrnf`). Config fields added in `app/config.py`. See §1 and the connection doc §2.
2. **Access level.** ✅ **UPGRADED (2026-06-17).** Client provided `WGR_DATABASE_URL` (direct Postgres, session pooler) — full schema + reliable bulk reads. Read via `app/services/wgr_client.py` (forced read-only). Full schema captured in `docs/client-supabase-schema.md`. ⚠️ Still want a **dedicated read-only role** — the current credential is the write-capable `postgres` role (guarded read-only on our side, not removed). Anon key remains as fallback.
3. **Source of truth.** CI already has its own GHL pipeline. Decide: does the client DB **replace** CI's direct GHL sync, **backfill** it, or run **alongside** as a cross-check? Plan treats it as an **additive source** writing into the same CI tables with a `source` marker so we never silently overwrite CI-native rows.

---

## 1. Configuration (additive, non-destructive) — ✅ DONE (2026-06-17)

Added to `app/config.py` `Settings`:
```python
client_supabase_url: str = ""
client_supabase_anon_key: str = ""
client_supabase_service_key: str = ""   # preferred once client provides it
client_sync_enabled: bool = False        # master switch
```
`.env` now keeps the two projects in separate variable sets — `SUPABASE_*` = CI's own auth project (`iqqobmubutxwhtvpdrnf`), `CLIENT_SUPABASE_*` = client GHL mirror (`mntsbmuxbdnnlnheuwqk`). `CLIENT_SYNC_ENABLED=false` until the sync task exists. Verified loading + reachability (see connection doc §2).

> Note: `client_sync_enabled` stays **false** until the sync task (§5) is built — turning it on before then is a no-op.

---

## 2. New service — `client_supabase_client.py`

A thin **read-only** PostgREST client (sync, httpx — mirrors the `ghl_client.py` convention so it slots into Celery cleanly).

Responsibilities:
- `iter_table(name, *, since=None, page_size=1000)` → generator of row dicts, paginating with `offset`/`limit` and `Range`, ordered by `updated_at`/`created_at` ascending.
- Incremental filter: `?updated_at=gte.<watermark>` for `leads`; `created_at` for `calls`/`appointments` (no `updated_at` on those).
- `count(name)` via `Prefer: count=exact`, `Range: 0-0`.
- Retry/backoff on 429/5xx (copy the `_MAX_429_RETRIES` pattern from `ghl_client.py`).
- Never writes. No service-role operations.

---

## 3. Field mapping → CI models

CI already owns `leads`, `calls`, `appointments` (`app/models/operational.py`). **Map, don't duplicate.** Reuse the existing upsert philosophy in `ghl_upsert.py` (same GHL shapes), adding a `source="client_supabase"` provenance marker and keying on the GHL ids so rows reconcile with CI's own GHL sync instead of double-inserting.

| Client column | → CI field | Transform |
|---------------|-----------|-----------|
| `leads.ghl_contact_id` | dedupe key | match CI's existing GHL contact key |
| `leads.lead_id` | external ref | store as-is |
| `leads.name/email/phone` | name/email/phone | normalize phone to E.164 |
| `leads.utm_*_last` | attribution | map to CI's attribution fields |
| `appointments.*` | Appointment | join lead via `lead_id`; `outcome`→CI status enum |
| `appointments.call_id` | link to Call | preserve FK |
| `calls.*` | Call | **soft-join** lead on `lead_id` (no FK); `call_result`→CI enum |
| `calls.rep_id` / `appointments.rep_id` | rep key | group/join on `rep_id`, never on the dirty name strings |
| `calls.notes` | → RAG | see §4 |

Write a `mapping` module with one pure function per table (`map_lead`, `map_appointment`, `map_call`) so it's unit-testable against the sample rows in the connection doc.

---

## 4. RAG hookup (required by project policy — RAG everything)

`calls.notes` holds rich AI-written call summaries — exactly the kind of content the vector store wants. After upsert, enqueue each `calls.notes` (and any non-trivial `appointments.notes` / `leads.notes`) through the existing chunk→embed path (`chunker.py` → `voyage_client.py` → embed worker). Tag chunks with `source=client_supabase`, `rep_id`, `lead_id`, `call_id` metadata for filtered retrieval. Skip empty/`null` notes.

---

## 5. Sync task & cadence

- New Celery task `sync_client_supabase` (alongside the existing GHL sync task), gated on `client_sync_enabled`.
- **Watermark** stored in CI's `sync_log` table (already exists, `app/models/audit.py`) per source+table; pull only rows newer than the last successful watermark. Backfill = watermark `null` → full pull (11.5k leads paginates in ~12 pages of 1000).
- Idempotent: upsert on the GHL id keys; safe to re-run.
- Cadence: hourly incremental to start (calls/appointments are low-volume); confirm the client's own write cadence (open question #3) so we don't pull mid-write.

---

## 6. Build / validation order

1. Config + `.env` split (§1) — confirm decision #1 first.
2. `client_supabase_client.py` read client + a `scripts/` smoke test that counts all 3 tables.
3. Mapping functions + unit tests against documented sample rows.
4. Upsert reusing `ghl_upsert` semantics with `source` provenance.
5. Backfill run into a **dev/staging** CI DB first (never prod — safety rule), validate row counts: 11,547 leads / 1,776 appts / 109 calls.
6. RAG enqueue for `notes`.
7. Celery task + watermark + schedule.
8. Update `INTEGRATIONS.md` (client Supabase as a new source) and `CHANGELOG.md`.

---

## 7. Risks / guardrails
- **Read-only always** — we never write to the client DB. No service-role write ops even if the key is later provided.
- **RLS drift** — anon access could be revoked by the client; the task must fail loud (log to `error_log`), not silently sync zero rows.
- **Schema blind spots** — we only see 4 tables; treat the inventory as partial until we get service_role/DB access.
- **No prod backfill without a state backup** (safety rule): export CI tables before the first large upsert.
- **Don't clobber CI-native GHL rows** — provenance marker + GHL-id keying makes the two sources reconcile rather than fight.
