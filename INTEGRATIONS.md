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
- **API calls:** `GET /3.0/campaigns?status=sent&sort_field=send_time&sort_dir=DESC&count=50` for the list, then `GET /3.0/reports/{campaign_id}` per campaign for the metric breakdown.
- **Data pulled per campaign:** name, subject, type (regular/automation/rss), status, send time, recipients, opens, clicks, unsubscribes, bounces, open rate, click rate.
- **Provenance tagging:** every row Mailchimp writes is tagged `source="mailchimp"` + `external_id=<Mailchimp campaign_id>`. Seed-fallback rows get `source="seed"`. The task dedups on `(source, external_id)` first (survives renames in Mailchimp), then falls back to `name` for legacy untagged rows. The recent-campaigns list on `/marketing/email` shows a badge per row.
- **Failure mode:** if the Mailchimp HTTP call fails (bad key, outage, network), the task logs the error, stamps `last_sync_status="error"` + `last_sync_error=<msg>` on the integration row, and falls back to seed data so the dashboard keeps rendering.
- **Credential auto-derive:** `server_prefix` (e.g. `us21`) is parsed from the API key's `-<dc>` suffix when the form's server-prefix field is left blank.
- **Client implementation:** [`backend/app/services/mailchimp_client.py`](backend/app/services/mailchimp_client.py) — thin `httpx` wrapper, no SDK.
- **Limits:** 50 most-recent campaigns per sync. Older campaigns won't appear in the dashboard until that limit's raised in code.

**Surfaces it powers today**

| Surface | What it shows |
|---|---|
| [`/marketing/email`](frontend/src/app/(app)/marketing/email/page.tsx) | KPI cards (avg open/click rate) + the list of recent campaigns with per-row metrics |
| [`/marketing`](frontend/src/app/(app)/marketing/page.tsx) | Marketing overview hub — pulls aggregate email KPIs |
| [`/integrations/mailchimp`](frontend/src/app/(app)/integrations/[slug]/page.tsx) | "Last synced" timestamp + last sync error if any |

**What it could power but doesn't yet**

- **Subject-line leaderboard** — top-N performers ranked by open rate, with date and recipient count. Data's already in `email_campaigns`; just needs a new card or a `/marketing/email/leaderboard` page.
- **Marketing Director chat awareness** — `/marketing-director` chat could reference real campaign performance ("Last week's newsletter pulled 38% opens — keep doing X").
- **Lead-level email engagement** — Mailchimp returns per-recipient open/click data via `/reports/{id}/email-activity`. Joining that to `leads.email` would surface "Lead X opened 3 of your last 5 emails" on the lead detail page.
- **Cohort analysis** — newsletter vs broadcast vs sequence performance over time. Schema supports it via `campaign_type`; needs a chart.
- **Re-send / variant suggestions** — the email compose page (`/marketing/email/compose`) could draft a follow-up specifically tuned for non-openers of a prior campaign.
- **Anomaly alerts** — when open rate on a new campaign is materially lower than the rolling baseline, surface a warning ("This send is tracking 12% below your 30-day average").

**Operational notes**

- API key format: `<32 hex chars>-<dc>` (e.g. `abc123def...-us21`). Find at Mailchimp → Profile → Extras → API keys.
- Rate limit: 10 concurrent connections per key. We use one connection serially — never an issue.
- Seed rows (`Weekly Newsletter #42`, `New Program Launch`, `Re-engagement Sequence`) coexist with real Mailchimp rows until manually deleted. Distinguishable via the `source` column or the badge on the dashboard. To clean up after first real sync:
  ```sql
  DELETE FROM email_campaigns WHERE source = 'seed';
  ```
- Renames in Mailchimp now update the existing row (dedup is on `(source, external_id)` first, where `external_id` is Mailchimp's stable `campaign_id`). Falls back to dedup-by-name only when external_id is missing (e.g. pre-tagging legacy rows).

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
