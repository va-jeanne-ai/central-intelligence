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

## Go High Level (GHL) ✅

**What it does today**

Two-way GHL link, both directions GHL → CI:

1. **Inbound push** — Custom Webhook workflow action delivers contacts within seconds (form-fill, tag-added, etc.).
2. **Outbound pull** — nightly Celery job (02:30 UTC) + on-demand "Sync contacts now" button paginates GHL's `GET /contacts/` to backfill existing contacts and catch out-of-band edits the webhook doesn't fire on.

Both feed the same upsert path in [`backend/app/services/ghl_upsert.py`](backend/app/services/ghl_upsert.py); dedup keys are identical so handling the same contact twice is a no-op.

- **Direction:** GHL → CI only (read-only). Reverse sync (CI → GHL) is on the roadmap.
- **Auth model:** token-in-URL. The integration page generates a URL-safe token (`secrets.token_urlsafe(32)`), stores it Fernet-encrypted in the integrations row, and shows the user the full URL to paste into GHL: `https://<your-api>/api/v1/webhooks/ghl/<token>/leads`. Token comparison uses `secrets.compare_digest` (constant-time). Mismatched tokens return **404** — never 401 — so the URL never confirms its own shape to a probing attacker.
- **Path:** [`backend/app/routes/webhooks.py`](backend/app/routes/webhooks.py).
- **Payload tolerance:** GHL's workflow Custom Webhook sends whatever the user mapped, and field names vary across triggers (Form Submitted vs Contact Created vs Tag Added). The endpoint accepts a raw dict and reads from a `GHL_FIELD_VARIANTS` table (`email`/`Email`/`contact_email`, `contact_id`/`contactId`/`id`, etc.) — first hit wins. The full raw payload is JSON-stringified into `lead.notes` so nothing's lost downstream.
- **Dedup order:** `(source='ghl', external_id=contact_id)` first, then `email` (lowercased + stripped). Partial unique index on `(source, external_id)` enforces this at the DB level.
- **Partial updates are safe:** A GHL "tag added" trigger fires with just `contact_id` + `tags`. The upsert path only overwrites fields the payload contains; the existing name/phone/status survive. Email is one-way too (only filled if previously null) — mid-life email changes are rare and dangerous to auto-apply.
- **Rotation:** the **Rotate Secret** button on the integration page generates a fresh token. The old URL stops working immediately (GHL will start getting 404s). User pastes the new URL back into GHL.
- **Last-sync stamp:** every successful webhook hit updates `integration.last_synced_at + last_sync_status='ok'`. Parse failures stamp `'error'` + the message but still return 200 — GHL retries aggressively on non-2xx and we don't want a single malformed payload to retry-storm.
- **Pull sync (nightly + on-demand):** [`backend/app/tasks/ghl_sync.py`](backend/app/tasks/ghl_sync.py) loads the integration row, decrypts the `api_access_token` + `location_id` from the credentials blob, paginates [`backend/app/services/ghl_client.py`](backend/app/services/ghl_client.py)'s `fetch_contacts()` against GHL's v2 `/contacts/` endpoint, and upserts each contact via [`upsert_ghl_lead_sync`](backend/app/services/ghl_upsert.py). Per-contact errors are counted and recorded in `sync_log.details["errors"]` (capped at 50) but never abort the run. **GHL wins** for contact fields; `staff_notes` is in a separate table and is never touched. Beat schedule entry: `ghl-contacts-sync-nightly` at 02:30 UTC. On-demand trigger: `POST /api/v1/integrations/ghl/sync`.
- **Rate-limit handling:** the HTTP client sleeps on 429 per the `Retry-After` header (default 5s when absent) and retries up to 3 times per page before letting the task fail.
- **Auth-middleware bypass:** `/api/v1/webhooks/` is in `_EXEMPT_PREFIXES` ([`backend/app/middleware/auth.py`](backend/app/middleware/auth.py)). Third parties don't have JWTs; the path-token comparison inside the route is the auth check.

**Surfaces it powers today**

| Surface | What it shows |
|---|---|
| [`/leads`](frontend/src/app/(app)/leads/page.tsx) | Every pushed GHL contact appears as a row, `source='ghl'`. KPI cards (`/leads/stats`) fill in once leads start arriving. |
| [`/integrations/ghl`](frontend/src/app/(app)/integrations/[slug]/page.tsx) | Webhook URL in a copyable code block, `api_access_token` + `location_id` form fields for the pull sync, **Sync contacts now** button, Test + Disconnect actions, "Last synced" timestamp updating on every webhook hit *and* every sync run. |
| `sync_log` table | Per-run history of the contact pull. Query `SELECT * FROM sync_log WHERE operation='ghl_contacts_sync' ORDER BY created_at DESC` to see inserted/updated/errors counts. |

**What it could power but doesn't yet**

- **Appointments webhook** — a second endpoint `POST /webhooks/ghl/appointments` to feed the `appointments` table. GHL has appointment-booked / -rescheduled / -cancelled triggers. Would populate the Sales Calls "next 7 days" surface.
- **Tags as a real `lead_tags` table** — today GHL tags land inside `notes` JSON. A dedicated `lead_tags` table would unlock "all leads tagged 'hot-lead'" queries from the Marketing Director chat.
- **Custom-field mapping UI** — let the user map their GHL custom fields (LTV, lead score, etc.) into specific Lead columns instead of stuffing them into `notes`. Mailchimp-style "field schema" approach.
- **Reverse sync (CI → GHL)** — push CI-side enrichments back into GHL. Examples: lead score from the call analyzer, "best contact time" from the calendar integration. Today's outbound API is read-only; reverse sync would need write scopes + conflict resolution on the GHL side.
- **OAuth callback flow** — today's setup is manual API access token paste. A proper OAuth dance would handle refresh tokens automatically.
- **Multi-location support** — GHL has `location_id` for agencies running sub-accounts. Today we ignore it (single integration row per provider). A multi-location version would add `location_id` to the leads table and route incoming contacts accordingly.

**Operational notes**

- **Setup in GHL:** Workflows → Add Action → Custom Webhook → paste URL → Method `POST` → Body type `JSON` → map the contact fields. Done.
- **Test without GHL:** `curl -X POST '<webhook_url>' -H 'Content-Type: application/json' -d '{"contact_id":"test1","email":"a@b.com","firstName":"Test"}'` → expect 200 `{"ok":true}` → check `/leads`.
- **Token rotation:** the old URL stops working the instant Rotate Secret is clicked. Don't rotate during business hours unless you've already updated the URL in GHL. (If you do, GHL retries for ~24h, so updating shortly after is fine.)
- **`public_api_base_url` setting** — defaults to `http://localhost:8000`. In prod, set this in `.env` to the externally-reachable URL (e.g. `https://api.centralintelligence.ai`) or the URL the user copies won't be reachable from GHL's servers.
- **What's stored encrypted:** `{"webhook_token": "...", "api_access_token": "...", "location_id": "..."}` in a single Fernet-encrypted blob on `integrations.credentials_encrypted`. The webhook_token is server-generated on first save (regenerable via Update); api_access_token + location_id are user-supplied. Disconnecting clears all three.

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

## Instagram ⬜

**What it could power**

Replace `update_social_stats` ([`backend/app/tasks/social_stats.py`](backend/app/tasks/social_stats.py)) seed rows for the Instagram platform. Followers, reach, impressions, engagement, story views, profile visits.

**Surfaces it would power**

- **`/marketing/social`** — live IG metrics.
- **`/ci-market-signals`** — IG comments via `social_comments` table (already seeded; would feed real ones from the Graph API).
- **Content performance ↔ content idea linkage** — when a post tagged with one of Greg's `content_ideas` is published, automatically attach reach/engagement to the idea row.

**What's needed to ship**

- IG Business Account (already required for Graph API access — most coaches have this).
- Meta App with `instagram_basic`, `instagram_manage_insights`, `pages_show_list` permissions.
- A `meta_graph_client.py` (likely shared with Facebook below — same API root).

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
