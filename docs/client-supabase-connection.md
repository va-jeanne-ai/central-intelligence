# Client Supabase — Connection & Data Reference

> **Status:** Documented 2026-06-17. Source: live introspection via the anon key set in `backend/.env`.
> **Owner of the data:** the client (Greg Wheeler / "WGR" sales org). This is a **read source** for Central Intelligence — we do not own or write to it.

---

## 1. Identity & access

| Item | Value |
|------|-------|
| Project ref | `mntsbmuxbdnnlnheuwqk` |
| REST base URL | `https://mntsbmuxbdnnlnheuwqk.supabase.co` |
| PostgREST | `https://mntsbmuxbdnnlnheuwqk.supabase.co/rest/v1/` |
| Auth (GoTrue) | live, `v2.190.0` — reachable |
| Storage | enabled, **0 buckets** (no files to pull) |
| Credentials we hold | `CLIENT_SUPABASE_ANON_KEY`, `CLIENT_SUPABASE_JWT_SECRET`, **`WGR_DATABASE_URL`** (direct Postgres, added 2026-06-17) |
| Credentials we do **not** hold | dedicated read-only Postgres role, `service_role` API key |

### ⚠️ UPDATE 2026-06-17 — we now have a direct Postgres connection (`WGR_DATABASE_URL`)

The client provided `WGR_DATABASE_URL` — a direct Postgres connection to their project (`mntsbmuxbdnnlnheuwqk`) via the Supabase **session pooler** (`aws-1-us-east-1.pooler.supabase.com:5432`). This supersedes the anon key for schema discovery and bulk reads. Confirmed connecting and listing the full `public` schema.

**🚨 SAFETY — this is the `postgres` superuser-adjacent role, NOT a read-only role.** `has_table_privilege` confirms it can `INSERT` (and by extension UPDATE/DELETE/DDL) on the client's tables. Our session sets `readonly=True` as a client-side guard, but the *credential itself can write to client production data*. Per project safety rules (NEVER modify client data), every connection MUST open with `SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY` / `set_session(readonly=True)`, and we should **ask the client for a dedicated read-only role** to remove the footgun entirely. Until then, treat `WGR_DATABASE_URL` as radioactive: reads only, never wrap it in anything that writes.

### What the anon key can and cannot do (now mostly superseded)
- ✅ **Read** rows from any table whose RLS policy grants the `anon` role `SELECT`.
- ❌ **Cannot** list the full schema — `GET /rest/v1/` returns `401 "Only the service_role API key can be used for this endpoint."`

The anon-probed inventory in §4 was **badly incomplete** — it found 4 tables. The direct Postgres connection reveals **75 tables** in `public` (see §4a). Schemas `auth`, `storage`, `realtime`, `vault`, `graphql`, `supabase_migrations`, `extensions`, `pgbouncer` also exist (standard Supabase internals — not data to sync).

---

## 2. ✅ `.env` split — auth and client data are now separate (2026-06-17)

**Resolved.** The two Supabase projects are split into distinct variable sets in `backend/.env`:

| Variable set | Project | Role |
|--------------|---------|------|
| `SUPABASE_URL` / `SUPABASE_ANON_KEY` / `SUPABASE_JWT_SECRET` | `iqqobmubutxwhtvpdrnf` (**CI's own**) | User login / auth. Consumed by `app/middleware/auth.py` and `app/auth/supabase_client.py`. Matches `DATABASE_URL`. |
| `CLIENT_SUPABASE_URL` / `CLIENT_SUPABASE_ANON_KEY` / `CLIENT_SUPABASE_SERVICE_KEY` | `mntsbmuxbdnnlnheuwqk` (**client's GHL mirror**) | Read-only data source. Consumed only by the client-data sync. Never verifies logins, never written to. |

Backed by `app/config.py` fields `client_supabase_url` / `client_supabase_anon_key` / `client_supabase_service_key` / `client_sync_enabled` (master switch, default `false`).

Verified: CI auth resolves to `iqqobmubutxwhtvpdrnf` (JWKS + GoTrue health both `200`); the client vars resolve to `mntsbmuxbdnnlnheuwqk`; no overlap between the two. Auth and app-DB now agree on CI's own project.

---

## 3. What this database is

A **GoHighLevel (GHL) CRM mirror** for the client's sales operation. An external system (the client's, not ours) already syncs GHL contacts, calendar appointments, and call records into these tables. Tell-tale signs: `ghl_contact_id`, `ghl_call_id` columns, `transcript_source = "GHL"`, calendar names like *"WGR Consultation Follow Up Call"* and *"Path To Freedom Discovery Call"*, reps Colton Lindsay / Tatjana Cristal / Nelson Figueria / Greg Wheeler.

This overlaps directly with CI's **own** GHL pipeline (`ghl_client.py` → `ghl_upsert.py`) and CI's own `leads` / `calls` / `appointments` models. The client's Supabase is effectively a **second, already-populated source** for the same domain — useful as a backfill / cross-check source rather than a new domain.

---

## 4. Table inventory (anon-readable)

| Table | Rows | Notes |
|-------|------|-------|
| `leads` | **11,547** | Contacts. Entry dates 2019-01-28 → present; `created_at` shows the mirror was (re)built starting 2026-05-11. |
| `appointments` | **1,776** | Calendar bookings. `scheduled_date` 2024-08-06 → 2026-07-06 (future bookings present). |
| `calls` | **109** | Scored call records w/ transcripts metadata. Dates 2026-05-26 → present (recent only). |
| `emails` | **0** | Table exists, currently empty. Columns unknown (no row to introspect, schema endpoint locked). |

> Other tables may exist but are RLS-hidden from `anon`. Treat this list as "what we can read today," not "the complete schema."

---

## 4a. FULL table inventory (via `WGR_DATABASE_URL`, 2026-06-17)

All 75 `public` base tables and live row counts. The anon key saw only the first four. Counts are a point-in-time snapshot.

| Table | Rows | | Table | Rows |
|-------|-----:|-|-------|-----:|
| `leads` | 11,561 | | `sales_activities` | 18,802 |
| `appointments` | 1,786 | | `sales_poll_conversation_state` | 6,863 |
| `calls` | 145 | | `webinar_engagements` | 7,566 |
| `emails` | 0 | | `lead_opt_in_events` | 13,973 |
| `applications` | 467 | | `comment_events` | 9,879 |
| `application_appointments` | 927 | | `webhook_logs` | 1,005 |
| `email_campaigns` | 2,390 | | `instagram_posts` | 1,000 |
| `content_ideas` | 220 | | `insights` | 280 |
| `insight_tags` | 661 | | `market_signals` | 294 |
| `pending_transcripts` | 264 | | `unmatched_opt_ins` | 314 |
| `sales` | 74 | | `sales_reps` | 7 |
| `sales_call_transcripts` | 103 | | `sales_call_analyses` | 55 |
| `sales_call_scores` | 220 | | `sales_eod_reports` | 102 |
| `sales_meaningful_conversation_flags` | 123 | | `sales_proactive_flag_prompts` | 134 |
| `sales_coaching_strikes` | 10 | | `sales_strike_actions` | 34 |
| `sales_strike_evidence` | 28 | | `sales_strike_rules` | 16 |
| `sales_scorecard_categories` | 11 | | `sales_dashboard_sessions` | 14 |
| `offers` | 11 | | `offer_mappings` | 15 |
| `offer_tag_programs` | 3 | | `email_best_practices` | 41 |
| `email_types` | 17 | | `email_categories` | 5 |
| `email_sync_log` | 15 | | `meta_campaigns` | 29 |
| `meta_ad_settings` | 1 | | `call_type_patterns` | 9 |
| `business_profile` | 2 | | `everwebinar_webinars` | 3 |
| `voice_channels` | 6 | | `creator_vision` / `creator_stories` | 1 / 1 |
| `backfill_state` | 4 | | `sync_meta` / `email_sync_meta` | 1 / 1 |
| `video_analyses` | 1 | | `monthly_preferences` | 2 |

**Empty today (0 rows)** — schema exists, no data yet: `emails`, `broll_clips`, `broll_segments`, `broll_ingest_failures`, `calendar_entries`, `creator_7x7`, `creator_subjects`, `dm_conversations`, `dm_messages`, `lead_engagements`, `meta_ads`, `meta_ad_performance`, `meta_creative_tests`, `sales_webhook_events`, `script_coverage_gaps`, `tag_dictionary`, `voice_conflicts`, `voice_core`, `voice_extraction_sessions`, `voice_variations`, `pending_transcripts`(264, not empty).

### What this database actually is (revised)

Not just a GHL mirror. It's the client's **full sales-and-marketing intelligence platform**, in layers:
- **CRM / GHL core** — `leads`, `appointments`, `calls`, `applications`, `lead_opt_in_events`.
- **Sales intelligence** — `sales_*` (transcripts, analyses, scores, EOD reports, coaching strikes, rep scorecards, poll state). This is rich, AI-generated text — **prime RAG material**.
- **Marketing** — `email_campaigns`, `meta_campaigns`, `instagram_posts`, `comment_events`, `webinar_engagements`, `content_ideas`, `insights`, `market_signals`.
- **Creator/voice/broll** — mostly empty scaffolding for a content pipeline.

> Note: live counts differ slightly from the anon-era §4 (e.g. `calls` 109→145, `leads` 11,547→11,561) — the mirror keeps growing. §4a is authoritative.

---

## 5. Schemas (from live rows)

### `leads` — 19 columns
| Column | Type | Notes |
|--------|------|-------|
| `lead_id` | text (PK) | `LEAD_<ghl_contact_id>` format |
| `ghl_contact_id` | text | GHL's native contact id |
| `name` | text | |
| `email` | text | |
| `phone` | text | mixed formats: `12143365496`, `+15612210606` |
| `entry_date` | date | first seen (back to 2019) |
| `pipeline_stage` | text, nullable | mostly `null`; values seen: `Lead`, `Appointment Set`, `Applied` |
| `utm_source_first` / `_medium_first` / `_campaign_first` / `_content_first` | text, nullable | first-touch attribution (often null) |
| `utm_source_last` / `_medium_last` / `_campaign_last` / `_content_last` | text, nullable | last-touch; sources: `fb`, `ig`, `instagram`, `CRM UI`, `CRM Workflows`, `Direct traffic` |
| `notes` | text, nullable | |
| `created_at` / `updated_at` | timestamptz | |
| `last_opted_in_at` | timestamptz, nullable | |

### `appointments` — 17 columns
| Column | Type | Notes |
|--------|------|-------|
| `appointment_id` | text (PK) | GHL appointment id |
| `lead_id` | text (**FK → `leads.lead_id`**, declared) | |
| `ghl_contact_id` | text | |
| `call_id` | text, nullable (**FK → `calls.call_id`**, declared) | links to the call that resulted |
| `call_number` | text | `Discovery`, `Sales`, `Follow Up` |
| `calendar_name` | text | e.g. "WGR Consultation Follow Up Call - Colton" |
| `appointment_owner` | text | rep name |
| `booked_by` | text | |
| `source` | text | e.g. `contactdetails_page` |
| `scheduled_date` | timestamptz | |
| `date_added` | date | |
| `outcome` | text | `Showed`, `Cancelled`, `Confirmed`, `No Show`, `Invalid` |
| `app_score` | nullable | usually null |
| `rescheduled` | bool | |
| `notes` | text, nullable | |
| `created_at` | timestamptz | |
| `rep_id` | text | `REP_<NAME>` normalized id |

### `calls` — 27 columns
| Column | Type | Notes |
|--------|------|-------|
| `call_id` | text (PK) | `CALL_<Name>_<YYYYMMDD>` |
| `date` / `processed_date` | date | |
| `call_type` | text | `Outbound`, `Discovery` |
| `call_subtype` | text | `booked_discovery`, `outbound_qualified`, … |
| `call_result` | text | `No Show`, `Follow-up Scheduled`, `Not Qualified`, `Booked`, `No Sale` |
| `call_owner` | text | rep name (note: dirty values — `Colton`, `Colton  Lindsay` with double space) |
| `lead_id` | text | **soft** ref → `leads.lead_id` (no declared FK; validated 10/10 in sampling) |
| `rep_id` | text | `REP_<NAME>` |
| `transcript_source` | text | `GHL` |
| `transcript_uid` / `transcript_link` | nullable | |
| `transcript_quality` | text | `Clean`, `Poor` |
| `call_duration_minutes` | int | |
| `notes` | text | **rich AI-generated call summaries** (high value for RAG) |
| `source` | text | `ghl_phone` |
| `ghl_call_id` / `call_sid` | text | Twilio/GHL call sid |
| `business_id` | nullable | |
| `score_status` | text | `scored`, `skipped` |
| `score_queued_at` / `score_started_at` / `score_completed_at` | timestamptz | scoring pipeline timestamps |
| `score_error` | nullable | |
| `discovery_occurred` | bool | |
| `outbound_feedback` | nullable | |

### `emails` — empty
Exists but has 0 rows; columns can't be introspected without the service_role key. Build the mapping for it only once it has data or we get full schema access.

---

## 6. Relationships

```
leads (lead_id) ──┬──< appointments.lead_id   [declared FK]
                  └──< calls.lead_id           [SOFT — no FK, join on text equality]

calls (call_id) ───< appointments.call_id      [declared FK, nullable]
```

- PostgREST embedding works for the **declared** FKs:
  - `GET /appointments?select=*,leads(name,email)` ✅
  - `GET /appointments?select=*,calls(call_result)` ✅
  - `GET /calls?select=*,leads(name)` ❌ (no FK — join manually on `lead_id`).
- All three tables also carry `ghl_contact_id` / `rep_id`, giving stable cross-keys to GHL and to a (not-yet-visible) reps table.

---

## 7. Data quality notes
- `leads.pipeline_stage` is mostly `null` — don't rely on it as a funnel field; derive funnel state from `appointments.outcome` + `calls.call_result` instead.
- `call_owner` / `appointment_owner` have inconsistent rep spellings; `rep_id` (`REP_<NAME>`) is the clean key — **join/group on `rep_id`, display the name only as a label.**
- `phone` is unnormalized (with/without `+`/country code).
- `calls` only goes back to 2026-05-26 while `leads`/`appointments` go back years — the call mirror is recent-only.
- `emails` is empty today.

---

## 8. How to query (reference)

```bash
# Count rows in a table
curl -s "https://mntsbmuxbdnnlnheuwqk.supabase.co/rest/v1/leads?select=*&limit=1" \
  -H "apikey: $CLIENT_SUPABASE_ANON_KEY" \
  -H "Authorization: Bearer $CLIENT_SUPABASE_ANON_KEY" \
  -H "Prefer: count=exact" -H "Range: 0-0" -i | grep -i content-range

# Pull a page with embedded lead
curl -s "https://mntsbmuxbdnnlnheuwqk.supabase.co/rest/v1/appointments?select=*,leads(name,email)&limit=100&offset=0" \
  -H "apikey: $CLIENT_SUPABASE_ANON_KEY" -H "Authorization: Bearer $CLIENT_SUPABASE_ANON_KEY"

# Incremental pull (rows changed since a timestamp)
curl -s "https://mntsbmuxbdnnlnheuwqk.supabase.co/rest/v1/leads?select=*&updated_at=gte.2026-06-16T00:00:00Z&order=updated_at.asc&limit=1000" \
  -H "apikey: $CLIENT_SUPABASE_ANON_KEY" -H "Authorization: Bearer $CLIENT_SUPABASE_ANON_KEY"
```

PostgREST paginates via `Range`/`offset`+`limit`; max page is 1000 rows. `Prefer: count=exact` returns the total in `Content-Range`.

---

## 9. Open questions for the client
1. Can we get a **service_role key** or a **read-only Postgres role + connection string**? (Needed for full schema + reliable bulk pulls.)
2. Are there tables beyond `leads/appointments/calls/emails` we should sync (reps, pipelines, opportunities, messages)?
3. What is the client's own sync cadence into this DB (so we don't pull mid-write or duplicate effort)?
4. Is `emails` expected to populate? On what schedule?
5. Confirm: should CI auth move to the client project, or keep CI's own and read the client DB via dedicated variables?
