# Integrations

Living catalog of every third-party integration Central Intelligence supports or plans to support. One entry per provider. Each entry covers: **what it does today** (shipped), **what surfaces in the app it powers**, and **what it could power but doesn't yet** (roadmap signal, not promises).

> **Update rule:** every time we add, expand, or remove an integration — or wire a new surface to an existing one — update this file in the same commit. The provider registry at [`backend/app/services/integrations_registry.py`](backend/app/services/integrations_registry.py) is the source of truth for what shows up in the UI; this doc is the source of truth for *why*.

**How users connect:** sidebar → Settings → Integrations → click a provider card → fill credentials → Save. Backed by the `integrations` table with Fernet-encrypted credentials at rest. See [`backend/app/routes/integrations.py`](backend/app/routes/integrations.py).

---

## Status legend

- ✅ **Live** — connector implemented, data flowing, surfaces consume it
- 🟡 **UI stub** — provider card exists, form/OAuth not yet wired
- ⬜ **Coming soon** — listed in the registry, no backend yet

---

## Mailchimp ✅

**What it does today**

Pulls sent-email campaign metrics into the `email_campaigns` table on a schedule. Replaces the seed-data fallback once a valid API key is saved.

- **Sync trigger:** Celery task `update_email_stats` ([`backend/app/tasks/email_stats.py`](backend/app/tasks/email_stats.py)). Fires on the Celery beat schedule (every 6h at :15 UTC) AND immediately when the user clicks **Save & Connect** on `/integrations/mailchimp`.
- **API calls per sync:** `GET /3.0/campaigns?status=sent&sort_field=send_time&sort_dir=DESC&count=50` for the list, then for each campaign two follow-up calls: `GET /3.0/reports/{id}` (metric breakdown) and `GET /3.0/campaigns/{id}/content` (rendered HTML body). Three HTTP calls × ~50 campaigns ≈ ~15s per full sync. Acceptable as a background job.
- **Data pulled per campaign:** name, subject, type (regular/automation/rss), status, send time, recipients, opens, clicks, unsubscribes, bounces, open rate, click rate, audience name (list), segment description, rendered HTML body, archive URL.
- **Provenance tagging:** every row Mailchimp writes is tagged `source="mailchimp"` + `external_id=<Mailchimp campaign_id>`. Seed-fallback rows get `source="seed"`. The task dedups on `(source, external_id)` first (survives renames in Mailchimp), then falls back to `name` for legacy untagged rows. The recent-campaigns list on `/marketing/email` shows a badge per row.
- **Failure mode:** if the Mailchimp HTTP call fails (bad key, outage, network), the task logs the error, stamps `last_sync_status="error"` + `last_sync_error=<msg>` on the integration row, and falls back to seed data so the dashboard keeps rendering.
- **Credential auto-derive:** `server_prefix` (e.g. `us21`) is parsed from the API key's `-<dc>` suffix when the form's server-prefix field is left blank.
- **Client implementation:** [`backend/app/services/mailchimp_client.py`](backend/app/services/mailchimp_client.py) — thin `httpx` wrapper, no SDK.
- **Limits:** 50 most-recent campaigns per sync. Older campaigns won't appear in the dashboard until that limit's raised in code.

**Surfaces it powers today**

| Surface | What it shows |
|---|---|
| [`/marketing/email`](frontend/src/app/(app)/marketing/email/page.tsx) | KPI cards (avg open/click rate) + the list of recent campaigns with per-row metrics, provenance badge, and click-to-expand showing subject / audience / segment / rendered body (sandboxed iframe) / Open-in-Mailchimp link |
| [`/marketing/email/compose`](frontend/src/app/(app)/marketing/email/compose/page.tsx) | Mailchimp-style **page-builder** compose flow: pick campaign type (Regular/Plain text/Template) → pick one of 3 starter templates (Newsletter, Promo, Welcome) → three-column page builder: **left palette** of 6 block types (Hero, Heading, Paragraph, Image, Button, Divider), **center canvas** showing the email faithfully with click-to-select + per-block ↑/↓/✕ toolbar, **right edit panel** with typed form controls per block. AI Fill rewrites the block list as `[heading, ...paragraphs, button]`. Save Draft writes the deterministic HTML output (via `renderBlocksToHtml`) to `email_campaigns` (source='manual', status='draft'). Sending via Mailchimp deferred. |
| [`/marketing`](frontend/src/app/(app)/marketing/page.tsx) | Marketing overview hub — pulls aggregate email KPIs |
| [`/integrations/mailchimp`](frontend/src/app/(app)/integrations/[slug]/page.tsx) | "Last synced" timestamp + last sync error if any |

**What it could power but doesn't yet**

- **Subject-line leaderboard** — top-N performers ranked by open rate, with date and recipient count. Data's already in `email_campaigns`; just needs a new card or a `/marketing/email/leaderboard` page.
- **Marketing Director chat awareness** — `/marketing-director` chat could reference real campaign performance ("Last week's newsletter pulled 38% opens — keep doing X").
- **Lead-level email engagement** — Mailchimp returns per-recipient open/click data via `/reports/{id}/email-activity`. Joining that to `leads.email` would surface "Lead X opened 3 of your last 5 emails" on the lead detail page.
- **Cohort analysis** — newsletter vs broadcast vs sequence performance over time. Schema supports it via `campaign_type`; needs a chart.
- **Re-send / variant suggestions** — the email compose page (`/marketing/email/compose`) could draft a follow-up specifically tuned for non-openers of a prior campaign.
- **Anomaly alerts** — when open rate on a new campaign is materially lower than the rolling baseline, surface a warning ("This send is tracking 12% below your 30-day average").
- **Send manual drafts via Mailchimp** — `/marketing/email/compose` writes drafts locally today (source='manual'). Wiring `POST /3.0/campaigns` + `/actions/send` (with a "send test only" guardrail + confirm dialog) would let Greg compose AND send from CI instead of bouncing to Mailchimp's UI.
- **User-saved templates** — the 3 starter templates are hardcoded in `frontend/src/lib/email-templates.ts`. A future `email_templates` table + CRUD would let Greg save his own.
- **Image upload to storage** — compose currently accepts image URLs only. Adding S3 / Supabase Storage uploads is its own task.

**Operational notes**

- API key format: `<32 hex chars>-<dc>` (e.g. `abc123def...-us21`). Find at Mailchimp → Profile → Extras → API keys.
- Rate limit: 10 concurrent connections per key. We use one connection serially — never an issue.
- Seed rows (`Weekly Newsletter #42`, `New Program Launch`, `Re-engagement Sequence`) coexist with real Mailchimp rows until manually deleted. Distinguishable via the `source` column or the badge on the dashboard. To clean up after first real sync:
  ```sql
  DELETE FROM email_campaigns WHERE source = 'seed';
  ```
- Renames in Mailchimp now update the existing row (dedup is on `(source, external_id)` first, where `external_id` is Mailchimp's stable `campaign_id`). Falls back to dedup-by-name only when external_id is missing (e.g. pre-tagging legacy rows).

---

## Go High Level (GHL) 🟡 superseded by the WGR mirror

> **Status update (2026-06-18, WGR rebase):** CI no longer ingests contacts **directly** from GoHighLevel. The client's WGR Supabase (a GHL mirror) is now CI's single upstream for leads/appointments/calls — see "WGR client database" below and [`backend/app/tasks/wgr_sync.py`](backend/app/tasks/wgr_sync.py). Concretely: the inbound lead/appointment webhooks return **410 Gone** while `ghl_inbound_enabled=False` (default), and the `ghl-contacts-sync-nightly` beat entry was removed. The code paths below remain intact and are re-enabled by setting `ghl_inbound_enabled=True` and restoring the beat entry. The **reverse-sync push (CI → GHL)** is unaffected — CI can still write enrichments back to GHL.

**What it did (direct path, now disabled)**

Genuinely two-way GHL link:

1. **Inbound push** — GHL Custom Webhook workflow action delivers contacts within seconds (form-fill, tag-added, etc.).
2. **Outbound pull** — nightly Celery job (02:30 UTC) + on-demand "Sync contacts now" button paginates GHL's `GET /contacts/` to backfill existing contacts and catch out-of-band edits.
3. **Inbound writes (CI → GHL)** — when staff PATCH a lead in CI (status, score, etc.), we push selected fields back to the matching GHL contact via a `PUT /contacts/{id}` call fired inline from the PATCH route. Failures fall through to a Celery retry task. See "Reverse-sync push" below.

The pull and the webhook feed the same upsert path in [`backend/app/services/ghl_upsert.py`](backend/app/services/ghl_upsert.py); dedup keys are identical so handling the same contact twice is a no-op.

- **Direction:** Two-way. GHL still wins for raw contact fields (name/email/phone) — those flow GHL → CI only. CI-side enrichments (status, score, latest note, last call date) flow CI → GHL.
- **Auth model:** token-in-URL. The integration page generates a URL-safe token (`secrets.token_urlsafe(32)`), stores it Fernet-encrypted in the integrations row, and shows the user the full URL to paste into GHL: `https://<your-api>/api/v1/webhooks/ghl/<token>/leads`. Token comparison uses `secrets.compare_digest` (constant-time). Mismatched tokens return **404** — never 401 — so the URL never confirms its own shape to a probing attacker.
- **Path:** [`backend/app/routes/webhooks.py`](backend/app/routes/webhooks.py).
- **Payload tolerance:** GHL's workflow Custom Webhook sends whatever the user mapped, and field names vary across triggers (Form Submitted vs Contact Created vs Tag Added). The endpoint accepts a raw dict and reads from a `GHL_FIELD_VARIANTS` table (`email`/`Email`/`contact_email`, `contact_id`/`contactId`/`id`, etc.) — first hit wins. The full raw payload is JSON-stringified into `lead.notes` so nothing's lost downstream.
- **Dedup order:** `(source='ghl', external_id=contact_id)` first, then `email` (lowercased + stripped). Partial unique index on `(source, external_id)` enforces this at the DB level.
- **Partial updates are safe:** A GHL "tag added" trigger fires with just `contact_id` + `tags`. The upsert path only overwrites fields the payload contains; the existing name/phone/status survive. Email is one-way too (only filled if previously null) — mid-life email changes are rare and dangerous to auto-apply.
- **Rotation:** the **Rotate Secret** button on the integration page generates a fresh token. The old URL stops working immediately (GHL will start getting 404s). User pastes the new URL back into GHL.
- **Last-sync stamp:** every successful webhook hit updates `integration.last_synced_at + last_sync_status='ok'`. Parse failures stamp `'error'` + the message but still return 200 — GHL retries aggressively on non-2xx and we don't want a single malformed payload to retry-storm.
- **Pull sync (nightly + on-demand):** [`backend/app/tasks/ghl_sync.py`](backend/app/tasks/ghl_sync.py) loads the integration row, decrypts the `api_access_token` + `location_id` from the credentials blob, paginates [`backend/app/services/ghl_client.py`](backend/app/services/ghl_client.py)'s `fetch_contacts()` against GHL's v2 `/contacts/` endpoint, and upserts each contact via [`upsert_ghl_lead_sync`](backend/app/services/ghl_upsert.py). Per-contact errors are counted and recorded in `sync_log.details["errors"]` (capped at 50) but never abort the run. **GHL wins** for contact fields; `staff_notes` is in a separate table and is never touched. Beat schedule entry: `ghl-contacts-sync-nightly` at 02:30 UTC. On-demand trigger: `POST /api/v1/integrations/ghl/sync`.
- **Rate-limit handling:** the HTTP client sleeps on 429 per the `Retry-After` header (default 5s when absent) and retries up to 3 times per page before letting the task fail.
- **Reverse-sync push (CI → GHL):** [`backend/app/services/ghl_push.py`](backend/app/services/ghl_push.py) — runs inline from `PATCH /leads/{id}` after our local commit. Pushes a `customFields` payload containing `ci_status`, `ci_score`, `ci_last_note_preview` (200-char), and `ci_last_call_date`. Eligible only when the lead has `source='ghl'` AND `external_id IS NOT NULL` (CI-native leads are silently skipped). **Conflict policy:** before writing, GETs the GHL contact, compares `dateUpdated` vs our `integration.last_synced_at` — if GHL is newer, refuses to push and surfaces the warning in the lead's history feed. **Retry:** transient failures (network, 5xx) enqueue [`tasks/ghl_push.py:push_lead_to_ghl_async`](backend/app/tasks/ghl_push.py) which retries 3× with 120s base delay before giving up. Every push emits a `lead.pushed_to_ghl` audit event with `after = {status, fields, reason}` — visible on the lead detail page's History card.
- **Kill switch:** set `integrations.config->>'push_enabled' = 'false'` in psql to silently skip all pushes without disconnecting the integration. Use this when GHL custom fields aren't set up yet or when debugging. No UI toggle for v1 — flip via DB and the push helper picks it up immediately.
- **GHL custom-field key overrides:** if your GHL deployment uses different custom-field keys than `ci_status` / `ci_score` / `ci_last_note_preview` / `ci_last_call_date`, set `integrations.config->'ghl_custom_field_keys'` to a JSON dict like `{"status": "my_status_key", "score": "my_score_key", ...}`. Defaults baked into `services/ghl_push.py:DEFAULT_CUSTOM_FIELD_KEYS`.
- **Auth-middleware bypass:** `/api/v1/webhooks/` is in `_EXEMPT_PREFIXES` ([`backend/app/middleware/auth.py`](backend/app/middleware/auth.py)). Third parties don't have JWTs; the path-token comparison inside the route is the auth check.

**Surfaces it powers today**

| Surface | What it shows |
|---|---|
| [`/leads`](frontend/src/app/(app)/leads/page.tsx) | Every pushed GHL contact appears as a row, `source='ghl'`. KPI cards (`/leads/stats`) fill in once leads start arriving. |
| [`/integrations/ghl`](frontend/src/app/(app)/integrations/[slug]/page.tsx) | Webhook URL in a copyable code block, `api_access_token` + `location_id` form fields for the pull sync, **Sync contacts now** button, Test + Disconnect actions, "Last synced" timestamp updating on every webhook hit *and* every sync run. |
| `sync_log` table | Per-run history of the contact pull. Query `SELECT * FROM sync_log WHERE operation='ghl_contacts_sync' ORDER BY created_at DESC` to see inserted/updated/errors counts. |
| [`/appointments`](frontend/src/app/(app)/appointments/page.tsx) + lead-detail **Appointments** card | Appointment webhook rows appear here. KPI cards (total, upcoming this week, show rate, no-show rate). |

**Appointments webhook (LIVE)**

A second inbound endpoint `POST /api/v1/webhooks/ghl/{webhook_token}/appointments` ([`backend/app/routes/webhooks.py`](backend/app/routes/webhooks.py)) feeds the `appointments` table. Same constant-time path-token validation as the lead webhook. Point a GHL appointment-booked / -rescheduled / -cancelled workflow webhook at this URL.

- **Upsert:** `upsert_ghl_appointment` ([`backend/app/services/ghl_upsert.py`](backend/app/services/ghl_upsert.py)) — tolerant field-variant extraction, status normalized to booked/confirmed/showed/no-show/cancelled/rescheduled, datetime parsed from ISO or epoch-ms. Dedup on `(source='ghl', external_id=<appointment id>)`, so book → reschedule → cancel update one row.
- **Linking:** best-effort to a lead (by `(source='ghl', external_id)` then email) and a member (by email); both stay nullable when unmatched (the contact snapshot still renders).
- **Surfaces:** `/appointments` directory, the lead-detail Appointments card, an `appointments` KPI block in `/sales/summary`, and the Sales Director's `get_appointments` tool ("what's booked this week?").

**What it could power but doesn't yet**

- **Outbound appointment pull** — a nightly `sync_ghl_appointments` Celery task + `fetch_appointments()` GHL client method to backfill appointments the webhook missed (e.g. booked before the webhook was wired). Deferred until GHL calendar-API scope is confirmed on the access token.
- **Tags as a real `lead_tags` table** — today GHL tags land inside `notes` JSON. A dedicated `lead_tags` table would unlock "all leads tagged 'hot-lead'" queries from the Marketing Director chat.
- **Custom-field mapping UI** — let the user map their GHL custom fields (LTV, lead score, etc.) into specific Lead columns instead of stuffing them into `notes`. Mailchimp-style "field schema" approach.
- **Reverse-sync write-back for raw contact fields** — today we push CI-side enrichments (status, score, custom fields) but never name/email/phone (GHL still wins on those). A "force CI as source of truth" mode would push those too; needs conflict resolution UX.
- **OAuth callback flow** — today's setup is manual API access token paste. A proper OAuth dance would handle refresh tokens automatically.
- **Multi-location support** — GHL has `location_id` for agencies running sub-accounts. Today we ignore it (single integration row per provider). A multi-location version would add `location_id` to the leads table and route incoming contacts accordingly.

**Operational notes**

- **Setup in GHL:** Workflows → Add Action → Custom Webhook → paste URL → Method `POST` → Body type `JSON` → map the contact fields. Done.
- **Test without GHL:** `curl -X POST '<webhook_url>' -H 'Content-Type: application/json' -d '{"contact_id":"test1","email":"a@b.com","firstName":"Test"}'` → expect 200 `{"ok":true}` → check `/leads`.
- **Token rotation:** the old URL stops working the instant Rotate Secret is clicked. Don't rotate during business hours unless you've already updated the URL in GHL. (If you do, GHL retries for ~24h, so updating shortly after is fine.)
- **`public_api_base_url` setting** — defaults to `http://localhost:8000`. In prod, set this in `.env` to the externally-reachable URL (e.g. `https://api.centralintelligence.ai`) or the URL the user copies won't be reachable from GHL's servers.
- **What's stored encrypted:** `{"webhook_token": "...", "api_access_token": "...", "location_id": "..."}` in a single Fernet-encrypted blob on `integrations.credentials_encrypted`. The webhook_token is server-generated on first save (regenerable via Update); api_access_token + location_id are user-supplied. Disconnecting clears all three.

---

## Google Workspace (Gmail + Drive + Calendar + RAG) ✅

**What it does today**

Three ingest pipelines on one per-user OAuth grant:

1. **Gmail thread sync** — pulls threads where a known lead's email address appears (From/To/Cc/Bcc) into our database, rendered as collapsible threads on the lead detail page. Plain-text bodies only; HTML is ignored. Attachments are recorded as metadata (filename + size + mime) but bytes are not downloaded — staff click through to Gmail for the file itself.
2. **Drive file sync + RAG layer** — sweeps every connected user's Drive, indexes file metadata into `google_drive_files`, and pulls plain-text content from supported file types (Google Docs, Sheets, Slides, PDFs, DOCX, txt/markdown). Extracted text feeds the **embeddings pipeline** (Voyage `voyage-3`, 1024-d, pgvector on Supabase) that powers the chat agent's `search_knowledge_base` tool. The lead detail page renders a **Documents** card listing files shared with the lead's email address.
3. **Calendar event sync** — sweeps every calendar a connected user can see (primary + secondary + shared), expands recurring events into individual instances via `singleEvents=true`, and stores them in `google_calendar_events`. First-class surface: dedicated **`/calendar`** page lists upcoming + past events with an attendee-email search. The lead detail page also renders an **Events** card listing meetings where the lead is an attendee. Calendar events flow into the same embeddings pipeline, plus the chat gets a structured **`query_calendar`** tool for time-window questions ("what's on Friday", "anything with @lazaderm.com next week") that vector search can't answer.

- **Auth model:** **Per-user OAuth.** Each staff member runs through Google's consent flow once on `/integrations/google_workspace`; CI stores their encrypted refresh token in `user_integration_credentials` and uses it to read their mailbox + Drive + Calendar on the schedule. All three sync tasks share the same grant (`gmail.readonly` + `drive.readonly` + `calendar.readonly`). Multiple connected users share the same `email_threads` / `email_messages` / `google_drive_files` / `google_calendar_events` tables; Gmail messages dedup automatically on `provider_message_id`; Drive files and Calendar events dedup on read (one row per `connected_via_user_id`). Service-account + domain-wide delegation was the original plan, but most GCP orgs enforce `iam.disableServiceAccountKeyCreation`, blocking that path. Per-user OAuth has no policy guardrails and gives each user the comfort of seeing exactly what was authorized.
- **Path:** [`backend/app/services/google_oauth.py`](backend/app/services/google_oauth.py) holds the OAuth flow primitives (authorize URL, code exchange, refresh). [`backend/app/services/google_oauth_credentials.py`](backend/app/services/google_oauth_credentials.py) loads + decrypts a user's tokens and builds a `google.oauth2.credentials.Credentials` object. [`backend/app/routes/oauth.py`](backend/app/routes/oauth.py) provides `/start` + `/callback` + `/connected-users` + `/disconnect` endpoints. [`backend/app/services/gmail_client.py`](backend/app/services/gmail_client.py) wraps `googleapiclient.discovery.build('gmail', 'v1', ...)` — auth-agnostic, takes any `Credentials`. [`backend/app/services/gmail_upsert.py`](backend/app/services/gmail_upsert.py) keeps `email_threads` + `email_messages` rows in sync. [`backend/app/tasks/gmail_sync.py`](backend/app/tasks/gmail_sync.py) holds both Celery entry points — the full nightly sweep (`sync_gmail_threads`, fan-out across every connected user) and the per-lead on-demand variant (`sync_gmail_threads_for_lead`).
- **Schedule:** Gmail beat-scheduled at **02:45 UTC** daily (`gmail-thread-sync-nightly`); Drive at **03:00 UTC** (`google-drive-sync-nightly`); Calendar at **03:15 UTC** (`google-calendar-sync-nightly`); embed worker drain every **2 minutes** (`embed-queue-drain`). On-demand: `POST /api/v1/integrations/google_workspace/sync` fans out all three in one click. `POST /api/v1/leads/{lead_id}/sync-emails`, `POST /api/v1/leads/{lead_id}/sync-documents`, and `POST /api/v1/leads/{lead_id}/sync-events` cover the per-lead variants. `POST /api/v1/calendar/sync` is the single-user button on the `/calendar` page.
- **Incremental sync:** Gmail filters with `after:<unix_ts_of_user_last_synced_at>`. Drive uses `modifiedTime > <last_sync>` plus a `content_hash` short-circuit. Calendar uses `updatedMin = last_synced_at` on subsequent runs and the full history window (10 years back + 1 year forward) on the first run for each user. All three short-circuit re-embedding when the content hash matches.
- **Query shape (Gmail):** `(from:"<email>" OR to:"<email>" OR cc:"<email>" OR bcc:"<email>") after:<ts>`.
- **Storage:**
  - `email_threads(id, lead_id FK CASCADE, provider_thread_id, subject, last_message_at, message_count, created_at, updated_at)`. Composite UNIQUE on `(lead_id, provider_thread_id)`. Index on `(lead_id, last_message_at DESC)`. Migration `i9d0e1f2g3h4`.
  - `email_messages(id, thread_id FK CASCADE, provider_message_id UNIQUE, from_address, to_addresses JSONB, cc_addresses JSONB, subject, body_text, sent_at, has_attachments, attachments_meta JSONB, created_at)`. Index on `(thread_id, sent_at)`. Migration `i9d0e1f2g3h4`.
  - `user_integration_credentials(id, user_id FK CASCADE, provider, credentials_encrypted, scopes JSONB, connected_email, last_synced_at, last_sync_status, last_sync_error, created_at, updated_at)`. Composite UNIQUE on `(user_id, provider)`. Migration `j1a2b3c4d5e6`.
  - `google_drive_files(id, connected_via_user_id FK CASCADE, provider_file_id, name, mime_type, owner_email, modified_time, web_view_link, parent_folder_id, parent_folder_name, shared_with JSONB, size_bytes, is_trashed, extracted_text, content_hash, last_extracted_at, created_at, updated_at)`. Composite UNIQUE on `(provider_file_id, connected_via_user_id)`. **GIN index on `shared_with`** for the lead documents card's JSONB containment query. Migration `k2b3c4d5e6f7`.
  - `google_calendar_events(id, connected_via_user_id FK CASCADE, provider_event_id, calendar_id, calendar_name, title, description, location, organizer_email, attendees JSONB, start_time, end_time, is_all_day, event_link, status, recurring_event_id, extracted_text, content_hash, last_extracted_at, created_at, updated_at)`. Composite UNIQUE on `(provider_event_id, connected_via_user_id)`. Index on `(connected_via_user_id, start_time DESC)`. **GIN index on `attendees`** for lead-by-email containment and the chat agent's `query_calendar(attendee_email_contains=...)` filter. Migration `m4d5e6f7a8b9`.
  - `embed_pending(id, source_table, source_id, text_to_embed, content_hash, attempts, last_error, created_at)`. FIFO drain queue, polymorphic across all four embedded sources. Migration `k2b3c4d5e6f7`.
  - `embeddings(id, source_table, source_id, chunk_index, text_chunk, embedding vector(1024), content_hash, embedded_at)`. **IVFFLAT index** on `embedding vector_cosine_ops` (lists=100). Composite UNIQUE on `(source_table, source_id, chunk_index)`. Migration `k2b3c4d5e6f7`.
  - `embedding_budget(id, daily_token_cap, tokens_used_today, usage_window_started_at)`. Single-row global daily cap. Migration `k2b3c4d5e6f7`.
- **Error tolerance:** Each sync catches per-user and per-message/file exceptions and surfaces them in `sync_log.details["errors_by_user"]` (keyed by user_id, capped at 50 entries per user). A user whose refresh token has been revoked is logged + marked `last_sync_status='error'` on their `user_integration_credentials` row (the UI surfaces "Reconnect needed"); the rest of the sweep continues. The embed worker uses per-row attempt counting (max 3) so a malformed source row can't block the queue.

**AI chat retrieval (the RAG layer)**

The Central Intelligence chat agent has **three retrieval tools**; the LLM picks which to call:

| Tool | Use for | Source |
|---|---|---|
| `query_database` | Structured business data — counts, lists, status filters, lead/call/insight joins | Postgres tables (read-only SELECT) |
| `query_calendar` | Time-window calendar questions ("Friday", "next week", attendee filter) | `google_calendar_events` table (structured range query, not vector) |
| `search_knowledge_base` | Semantic / "find anything about…" questions | `embeddings` table; pgvector cosine against the Voyage-embedded chunks |

Embeddings cover five sources today, all polymorphic-keyed by `(source_table, source_id)`:

- `google_drive_files` — primary RAG corpus. Docs/Sheets/Slides exported via Drive API to `text/plain` or `text/csv`; PDFs via pdfplumber; DOCX via python-docx; plain text + markdown as-is. Files >15MB are indexed at metadata level only.
- `email_messages` — subject + body_text concatenated per message.
- `google_calendar_events` — title + description + attendees + when concatenated (so semantic queries like "find the budget review meeting" hit on the right event).
- `lead_notes` — staff-side journal entries.
- `insights` — call insights (raw_quote + what_they_say + the_real_problem + emotional_driver + marketing_translation concatenated).

Chunking: `tiktoken` cl100k_base, 1024 tokens per chunk with 200-token overlap. Embeddings stored on every chunk; one source row → many `embeddings` rows.

**Setup (one-time, by a deployment admin)**

1. Google Cloud Console → create or pick a project → enable **Gmail API**, **Drive API**, and **Calendar API**.
2. APIs & Services → **OAuth consent screen** → configure (External or Internal depending on Workspace). Add scopes `gmail.readonly`, `drive.readonly`, `calendar.readonly` plus `openid` + `email`. Add yourself + any tester accounts under "Test users" until the app is verified.
3. APIs & Services → **Credentials** → Create Credentials → **OAuth 2.0 Client ID** → Web application. Add authorized redirect URI: `http://localhost:8000/api/v1/integrations/google_workspace/oauth/callback` (for dev; replace host in prod).
4. Voyage AI → create an account at [voyageai.com](https://www.voyageai.com) → generate an API key.
5. Add to `backend/.env`:
   - `GOOGLE_OAUTH_CLIENT_ID=<client id from step 3>`
   - `GOOGLE_OAUTH_CLIENT_SECRET=<client secret from step 3>`
   - `GOOGLE_OAUTH_REDIRECT_URI=http://localhost:8000/api/v1/integrations/google_workspace/oauth/callback`
   - `VOYAGE_API_KEY=<key from step 4>`
6. Restart the backend + Celery worker + beat so the new sync tasks register.
7. **Force re-consent for already-connected users** every time a scope is added. Calendar scope is additive but Google's consent layer requires re-grant: `DELETE FROM user_integration_credentials WHERE provider = 'google_workspace';`. Each staff member then reconnects to grant the expanded scopes.

**Per-user connect (each staff member, once)**

1. Sign into CI as that user.
2. Navigate to `/integrations/google_workspace`.
3. Click **Connect Gmail** → browser redirects to Google's consent screen → grant `gmail.readonly` + `drive.readonly` + `calendar.readonly`.
4. Google redirects back; the page shows your row in "Connected users" with your email + sync status.
5. Threads + documents + events start showing up after the next sync (nightly or manual). RAG embeddings begin populating within a few minutes of each sweep (embed worker drains every 2 min).

**Surfaces it powers today**

| Surface | What it shows |
|---|---|
| [`/integrations/google_workspace`](frontend/src/app/(app)/integrations/[slug]/page.tsx) | "Connect Gmail" button for the current user; "Connected users" list showing every staff member who has connected, each with `connected_email` + last sync status + a Disconnect action (own-row only). |
| [`/calendar`](frontend/src/app/(app)/calendar/page.tsx) | Dedicated calendar page. Day-grouped list of events with **Upcoming (14d)** / **Recent (30d)** / **Past 30d + Next 60d** toggles + an attendee-email search filter + a per-user **Sync now** button. |
| [`/leads/[lead_id]`](frontend/src/app/(app)/leads/[lead_id]/page.tsx) | **Emails** card with collapsed thread rows + per-lead **Sync emails now** button. **Events** card listing Calendar events where the lead's email is in `attendees`, with per-lead **Sync events now** button. **Documents** card listing Drive files where the lead's email is in `shared_with`, with mime icon + last modified + owner + per-lead **Sync documents now** button. |
| `/chat` (Central Intelligence agent) | Three retrieval tools. `query_database` for structured business data, `query_calendar` for time-window event lookups, `search_knowledge_base` for unstructured semantic search across everything. |
| `sync_log` table | Per-run history. `operation='gmail_thread_sync'` for Gmail; `operation='drive_file_sync'` for Drive; `operation='calendar_event_sync'` for Calendar. `details` carries `users_processed`, `inserted`, `content_changed`, `errors_by_user`. |

**What it could power but doesn't yet**

- **Send email from CI.** Read-only for v1. Sending is a separate (significant) build — needs `gmail.send` scope (which would re-trigger consent) + a compose UI.
- **Real-time via Gmail Pub/Sub push.** Push subscriptions watch the mailbox and POST a webhook when a new message arrives. Significant ops scope (Cloud Pub/Sub topic, push subscription, watch renewal every 7 days). Add only if 24h latency becomes a complaint.
- **HTML rendering.** Marketing-style HTML emails currently render as "(no plain-text body)". A sanitizer + `dangerouslySetInnerHTML` path could fix this.
- **Attachment downloads.** Today we only record metadata. Downloading bytes opens a "where do we store them?" decision (S3 / local fs / Drive).
- **Body search.** Threads are accessed via the lead — no global "find all emails mentioning competitor X" yet.
- **Admin-side disconnect for another user.** Each user can only disconnect themselves today; an admin endpoint would handle off-boarded staff.

**Operational notes**

- **What's stored encrypted (per-user):** `{"refresh_token": "...", "access_token": "...", "token_uri": "...", "client_id": "...", "client_secret": "...", "expires_at": "...", "scopes": [...]}` in `user_integration_credentials.credentials_encrypted` (Fernet). The access token is auto-refreshed when it's within 60 seconds of expiry; the new access token + expiry are re-persisted.
- **Revocation handling.** If a user revokes consent from myaccount.google.com, the next refresh attempt returns `invalid_grant`. The loader stamps `last_sync_status='error'` + `last_sync_error="Token unavailable — reconnect needed"`; the UI surfaces "Reconnect needed" and Sync runs skip that user until they reconnect.
- **Scopes:** read-only `gmail.readonly` + `drive.readonly` + `openid` + `email`. CI never gets write access; we only read the user's mailbox + Drive for display + embeddings.
- **Quota:** Gmail API and Drive API both have generous quotas (1B units/day per project on Gmail; 1k req/100s per user on Drive). The sweep stays well under these for typical team sizes.
- **Voyage cost guardrails.** Token usage is reported by Voyage on every embed call and decremented against `embedding_budget.tokens_used_today`. Default cap is **50M tokens/day** (~$3/day at Voyage `voyage-3` pricing). The worker pauses when the cap is hit and resets on a rolling 24h window. To adjust: `UPDATE embedding_budget SET daily_token_cap = <N> WHERE id = 1`.
- **Re-embed semantics.** Each source row's `content_hash` (sha256[:64]) is compared to the most recent `embeddings` row for `(source_table, source_id)`. If unchanged, the embed is skipped. When content changes the worker DELETEs the old chunks for that source row before inserting the new ones — no version sprawl.
- **Backfill the other three sources.** `app.tasks.embed_backfill` provides three one-shot tasks (`backfill_email_messages_embeddings`, `backfill_lead_notes_embeddings`, `backfill_insights_embeddings`) that enqueue every row missing an embedding. Invoke from a Celery shell or via `.delay()` from a Python REPL after the migration runs.
- **Why the state parameter is encrypted, not just signed.** The state encodes `{user_id, nonce, issued_at}` and is Fernet-encrypted with the integrations master key. Encryption gives us tamper-proofing + freshness-checking + opacity in one primitive without adding a session store. TTL is 10 min — enough for the OAuth round-trip.

---

## Google Calendar 🟡

**What it does today**

Nothing functional. The provider card renders on `/integrations` and clicking it opens a placeholder detail page with a disabled "Connect with Google (coming soon)" button.

**What's needed to ship**

- OAuth 2.0 flow: redirect to Google, handle the callback, persist the refresh token in the integration row's encrypted blob.
- Calendar list selection (Greg has multiple calendars; the UI needs to ask which one to sync).
- Celery task to pull events on a schedule.
- A new `calendar_events` table (or extend `appointments` if the shapes overlap).

**Surfaces it could power**

- **Appointments page** (`/appointments` is currently empty) — populate from Google Calendar events tagged as sales calls / coaching sessions.
- **Sales Calls list** — auto-link incoming transcript uploads to the matching calendar event by attendee + time window, pre-filling `call_owner` and `member_id`.
- **Marketing Director chat context** — "you have a call with Rich at 2pm — here's his last call's pain points."
- **Promo Calendar overlay** — show committed campaigns alongside personal availability so Greg doesn't double-book.
- **Auto-block focus time** when the analyzer is processing a long upload (no, too creepy — kidding, but you could).

---

## Meta Ads ⬜

**What it could power**

Replace the seed data in `update_ads_stats` ([`backend/app/tasks/ads_stats.py`](backend/app/tasks/ads_stats.py)) with real Meta Marketing API calls. Pull spend, impressions, clicks, conversions, CPC, CPM, CTR, ROAS per campaign per platform (Facebook + Instagram).

**Surfaces it would power**

- **`/marketing/ads`** — replace placeholder numbers with live Meta spend.
- **`/marketing/funnels`** — attribute Meta-sourced leads through the funnel via UTM joins on `funnel_events`.
- **ROAS-aware recommendations** in `/marketing-director` chat ("FB lookalike is at 4.2x ROAS, IG carousels at 1.1x — shift spend").
- **Lead source enrichment** — tag `leads.source = "Meta Ads"` automatically when the Lead Ads form fires the webhook.

**What's needed to ship**

- App registration on Meta for Developers (Business app type), permissions: `ads_read`, `ads_management`, `pages_read_engagement`.
- OAuth flow with token refresh (Meta tokens are short-lived; we'd need a daily refresh job).
- A `meta_ads_client.py` mirroring the Mailchimp client pattern.
- Map Meta's `campaign_id / adset_id / ad_id` hierarchy onto our flatter `ads_stats` model — probably extend the model with `parent_campaign_id` etc.

---

## Google Ads ⬜

**What it could power**

Same shape as Meta Ads — search + display performance metrics into `ads_stats`.

**Surfaces it would power**

- **`/marketing/ads`** — Google rows alongside Meta rows.
- **Keyword performance roll-ups** (Meta doesn't have this concept, Google does — would need a new `keyword_stats` table).
- **Cross-platform attribution** — last-click vs first-click model comparison.

**What's needed to ship**

- Google Ads API access (requires a developer token + manager account approval — multi-week process at Google).
- OAuth flow with refresh tokens.
- A separate `google_ads_client.py`; the API shape is meaningfully different from Meta's (GAQL vs REST).

---

## Instagram ✅

**What it does today**

Pulls live organic metrics for one Instagram Business/Creator account from the Meta Graph API (v19.0) and upserts them into `social_stats`. Manual-token connector (same pattern as GHL/Mailchimp): the admin saves an **Access Token** + **Instagram Account ID** on `/integrations/instagram`; credentials are encrypted at rest in the `integrations` row.

- [`backend/app/services/instagram_client.py`](backend/app/services/instagram_client.py) — Graph API wrapper. Profile (`followers_count`, `media_count`), account insights (`reach`, `impressions` over `days_28`), and recent media (`like_count`/`comments_count`) to estimate an engagement rate. Insights + media are best-effort; a failure there still records followers/posts.
- [`backend/app/services/instagram_credentials.py`](backend/app/services/instagram_credentials.py) — decrypts `(access_token, ig_user_id)` from the integration blob (mirrors `ghl_credentials.py`).
- [`backend/app/tasks/social_stats.py`](backend/app/tasks/social_stats.py) — `update_social_stats` now syncs Instagram live when connected; **skips** IG (no fake-data overwrite) when not connected or on error, and stamps `last_sync_status`/`last_sync_error` + a `sync_log` row. facebook/linkedin/tiktok remain on seed values until their connectors land.
- Wired into [`backend/app/routes/integrations.py`](backend/app/routes/integrations.py): `_trigger_sync("instagram")` enqueues the task (the page's Sync button) and the **Test** button calls `instagram_client.verify()`.
- Beat: rides the existing `social-stats-every-6h` schedule.

**Surfaces it powers**

- **`/marketing/social`** — live IG followers, posts, reach, impressions, engagement once a sync runs.

**Auth / setup** — manual token (paste a long-lived token + IG account ID on `/integrations/instagram`; the page has a collapsible **Setup steps** panel walking through both):

- IG Business or Creator account linked to a Facebook Page.
- Meta App with `instagram_basic` + `instagram_manage_insights` + `pages_read_engagement` scopes.
- A **long-lived access token** (Graph API Explorer → exchange for a ~60-day token) and the numeric **IG Business account ID** (`GET /me/accounts` → `GET /<page-id>?fields=instagram_business_account`). Re-paste the token every ~60 days when it expires.

**Not yet**

- **"Connect with Meta" OAuth button** (one-click connect + token auto-refresh) — built then deferred to ship the manual connector first; lives in git history (branch `feat/instagram-social-integration`).
- No story/profile-visit metrics. IG comments → `social_comments` still seed-only (separate collector).

---

## Facebook ✅

**What it does today**

Pulls live organic metrics for one Facebook Page into `social_stats` (the `facebook` platform row), replacing the seed data. Manual long-lived **Page** token + Page ID. Unlike Instagram, no account-type conversion is needed — any Page admin can read Page insights.

- [`backend/app/services/facebook_client.py`](backend/app/services/facebook_client.py) — Graph API v19 wrapper. Page profile (`followers_count`/`fan_count`, `name`), Page Insights (`page_impressions` over `days_28`, summed), recent `/posts` (likes+comments) for an engagement-rate estimate. Profile required; insights + posts best-effort. `reach` is left null (no Page metric comparable to IG reach).
- [`backend/app/services/facebook_credentials.py`](backend/app/services/facebook_credentials.py) — decrypts `(access_token, page_id)` from the integration blob.
- [`backend/app/tasks/social_stats.py`](backend/app/tasks/social_stats.py) — Facebook rides the shared `update_social_stats` task via the generic `_sync_live_platform` path (alongside Instagram). Live when connected; **skips** (no fake-data overwrite) when not connected/on error, stamping `last_sync_status`/`last_sync_error` + a `sync_log` row.
- Wired into [`backend/app/routes/integrations.py`](backend/app/routes/integrations.py): `_trigger_sync("facebook")` enqueues the task (Sync button); **Test** calls `facebook_client.verify()`.
- Beat: rides the existing `social-stats-every-6h` schedule.

**Surfaces it powers**

- **`/marketing/social`** — live Facebook followers, posts, impressions, engagement once a sync runs.

**Auth / setup** — manual Page token (the `/integrations/facebook` page has a collapsible **Setup steps** panel):

- You must be an **admin** of the Facebook Page.
- Meta App with **Facebook Login** + the `pages_read_engagement` + `pages_show_list` + `read_insights` scopes.
- A **long-lived Page access token** (Graph API Explorer → select your Page under "User or Page" → generate → exchange for a ~60-day token) and the numeric **Page ID** (`GET /me/accounts`). Re-paste the token every ~60 days.

**Not yet**

- No "Connect with Meta" OAuth button (manual token only). No per-post breakdown surface. No `page_reach`. Shares `facebook_client` patterns with the Instagram connector.

---

## LinkedIn ⬜

**What it could power**

Same shape as Instagram — pull org-page post metrics into `social_stats`.

**Surfaces it would power**

- **`/marketing/social`** — LinkedIn column populated.
- **Lead-to-LinkedIn link** — when a lead has a LinkedIn URL in their record, surface their recent post activity on the lead detail page.
- **Comment ingestion** for `/ci-market-signals` — LinkedIn comments tend to be more substantive than other platforms.

**What's needed to ship**

- LinkedIn Developer App with `r_organization_social`, `rw_organization_admin` scopes (requires a company-page admin role).
- OAuth flow (LinkedIn tokens are 60 days; refresh path needed).
- A `linkedin_client.py`. The Marketing Developer API has different endpoints from the Sales Navigator API — we want the former.

---

## TikTok ⬜

**What it could power**

Replace TikTok rows in `social_stats`. Followers, video views, likes, shares, profile visits.

**Surfaces it would power**

- **`/marketing/social`** — TikTok metrics.
- **Short-form content insight** — TikTok comments tend to be reaction-heavy; valuable for `/ci-market-signals` voice-of-customer surfacing.

**What's needed to ship**

- TikTok for Developers App + Business API access (this is the slowest of all the social APIs to get approved).
- OAuth flow.
- A `tiktok_client.py`. Newer API, simpler shape than Meta's but rate limits are stricter.

---

## Connector implementation checklist

When wiring a new connector, this is the contract:

1. **Provider entry** in `backend/app/services/integrations_registry.py` (`status: "available"` once shipped, `"coming_soon"` until then).
2. **Service client** at `backend/app/services/<provider>_client.py` with:
   - `_resolve_creds()` — DB row first, settings fallback
   - `is_configured()` — returns bool
   - Public fetch helpers — sync, since Celery is sync
3. **Celery task** that calls the client, stamps `integrations.last_synced_at` via the same pattern as `_stamp_integration_sync` in `update_email_stats`.
4. **Trigger task mapping** in `routes/integrations.py::_trigger_sync` so Save kicks off an immediate pull.
5. **Test handler** in `routes/integrations.py::test_integration` — quick connectivity probe, doesn't persist.
6. **Update this file.** Move the provider from ⬜/🟡 to ✅, document the surfaces it powers, list the next things it could but doesn't yet.

---

## Why each provider lives in this catalog

Even ⬜ entries serve two purposes:
- **Roadmap signal** — anyone scanning the file sees what's coming.
- **UI placeholder** — the integrations page shows the cards so the product feels complete and discoverable, not bolted-together one-platform-at-a-time.

If a provider stops being on the roadmap, remove it from both `integrations_registry.py` AND this file in the same commit.
