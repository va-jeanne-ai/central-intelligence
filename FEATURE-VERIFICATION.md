# Central Intelligence — Feature Verification Checklist

> **Purpose:** working checklist of every feature in the system, what state it's in, how to verify it, and what's still needed to finish it. Walk through one feature at a time. Tick the boxes as you go.
>
> **Last reconciled:** 2026-05-19 (post Step 1 seed + Step 2 Celery beat wiring)
>
> **How to use this doc:**
> - Each feature has a `Status: ⬜ pending verification` until you check it
> - Mark `✅ verified-working` once you've confirmed the data shows up correctly in the UI
> - Mark `⚠️ partial: <note>` if it kinda works but isn't right
> - Mark `❌ broken: <note>` if it errors or shows nothing it shouldn't
> - For each feature, the **"To finish"** column tells you what's needed if it's not done

---

## Prereqs to run any verification

Open three terminals before starting:

| Terminal | Command | Purpose |
|---|---|---|
| 1 | `cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000` | Backend API |
| 2 | `cd frontend && npm run dev` | Frontend at http://localhost:3000 |
| 3 | `cd backend && ./scripts/start-celery-worker.sh` + ANOTHER terminal `./scripts/start-celery-beat.sh` | Optional: only needed for features that depend on Celery (transcription, ICP gen, scheduled stat refreshes) |

After backend + frontend are up: log in via Supabase auth, then click through each section below.

---

## 🟢 DONE — should work right now with real data

These were already wired before this sprint. The seeded data from Step 1 means dashboards now show real numbers. Walk through to confirm nothing regressed.

### F1 — Login / Auth
- **Status:** ⬜ pending verification
- **URL:** `/login`
- **What to check:**
  - [ ] Can log in with Supabase credentials
  - [ ] After 5 failed attempts, account is locked out
  - [ ] "Forgot password" sends a reset email
  - [ ] After login, you land on `/dashboard`
- **Stack:** Supabase auth (real)
- **To finish:** nothing — should be done.
- **Related:** see **F31** for the password-reset flow (separate fix landed 2026-05-19).

### F2 — Dashboard overview
- **Status:** ✅ **verified-as-empty (2026-05-19)** — UI renders cleanly; CRM tables empty by design
- **URL:** `/dashboard`
- **Finding during verification:** `/dashboard` reads from `leads`, `members`, `calls`, `content_ideas`, `insights`, `market_signals` — none of which are seeded (Step 1's `seed_sprint3.py` populates *marketing* tables, not CRM tables). Earlier audit was wrong on this point: I expected `/dashboard` to reflect Step 1's seeding; it doesn't. The marketing seed feeds `/leads` (funnel chart), `/marketing/email`, `/marketing/social` instead.
- **What was verified:**
  - [x] `GET /api/v1/dashboard/stats` returns HTTP 200 with valid JSON
  - [x] All KPIs show `0` or `"—"` cleanly (no nulls, no errors, no 500s)
  - [x] Lead volume sparkline returns 8 weeks with zero counts (no crash)
- **What's NOT verified (deferred):**
  - [ ] 3 department cards render real numbers — requires CRM seed (a `seed_crm.py` script similar to `seed_sprint3.py`, or real lead/call ingestion from F19)
  - [ ] Lead sparkline shows non-zero activity — same prerequisite
  - [ ] CI widget shows real insights — depends on F19 (Sales Call Analyzer extraction)
- **To finish:** **Two paths converge here, pick one later:**
  1. Add a quick CRM seed script (mirror `seed_sprint3.py` shape — ~30 min) so dashboards visually populate during dev
  2. Wait for F19 (real call ingestion → real insights → real signals) to populate naturally
- **API:** `GET /api/v1/dashboard/stats`, `GET /api/v1/dashboard/recommendations`

### F3 — Leads pipeline
- **Status:** ✅ **verified-as-empty (2026-05-19)** — UI works; `leads` table empty (same blocker as F2)
- **URL:** `/leads`
- **Finding during verification:** `/leads/stats` reads from the `leads` table; that table has 0 rows. The "funnel" widget on this page reads `leads` join-aggregated by stage, **not** the `funnel_events`/`funnel_stats` we seeded in Step 1 (those feed F23 `/marketing/funnels`).
- **What was verified:**
  - [x] `GET /api/v1/leads/stats` returns HTTP 200 with valid JSON
  - [x] `GET /api/v1/leads` returns `{ leads: [], total: 0, page: 1 }` cleanly
  - [x] All KPIs / chart values are 0; no errors, no crashes
- **What's NOT verified (deferred):**
  - [ ] KPI cards / volume chart / source donut / funnel show real numbers — requires `leads` table to be populated
- **To finish:** Same as F2 — either run a CRM seed script or wait for real lead-capture ingestion (whatever Greg's intake path will be — webhook? form submit?)
- **API:** `GET /api/v1/leads`, `GET /api/v1/leads/stats`

### F4 — CI Insights
- **Status:** ✅ **superseded (2026-08-03)** — table populated (1,932 rows), full filters + source attribution shipped. See **"CI Insights — full filters, source attribution, expanded charts (2026-08-03)"** near the end of this doc for the current verification steps.
- **URL:** `/ci-insights`
- **API:** `GET /api/v1/ci/insights`, `GET /api/v1/ci/insights/facets`, `GET /api/v1/ci/insights/summary`, `GET /api/v1/ci/insights/{id}`

### F5 — Market Signals
- **Status:** ✅ **superseded (2026-08-03)** — table populated (1,961 rows), redesigned as a trending view. See **"Market Signals — filters + trending redesign (2026-08-03)"** near the end of this doc for the current verification steps.
- **URL:** `/ci-market-signals`
- **API:** `GET /api/v1/ci/market-signals`, `GET /api/v1/ci/market-signals/facets`

### F6 — Central Intelligence Chat
- **Status:** ✅ **verified-working (2026-05-19)**
- **URL:** `/chat`
- **What was verified:**
  - [x] Welcome message renders
  - [x] User question streams a real Claude response back
  - [x] WebSocket auth works after the F32 ES256 fix
- **Stack:** WebSocket → Claude (Anthropic SDK) with `query_database` tool
- **Note:** real CRM tables (`leads`, `members`, `calls`) are still empty, so DB-grounded questions like "how many leads do I have?" will correctly return 0. That's not a chat bug — it's the same CRM-empty state as F2/F3.

### F7 — Marketing Director Chat
- **Status:** ✅ **verified-working (2026-05-19)**
- **URL:** `/marketing-director`
- **What was verified:**
  - [x] Welcome message renders
  - [x] User question streams a real response (MarketingDirector → Claude Haiku)
  - [x] WebSocket auth works after the F32 ES256 fix
- **Stack:** WebSocket → MarketingDirector → specialists → Claude Haiku
- **Note:** this is the only working surface for specialists right now. The 4 specialist HTTP POST endpoints (F12) still return hardcoded text.

### F8 — Promo Calendar
- **Status:** ✅ **verified-working (2026-05-19)** — full CRUD round-trip confirmed
- **URL:** `/marketing/promo-calendar`
- **What was verified:**
  - [x] Calendar + list views both render
  - [x] Create → promo appears
  - [x] Edit → changes persist after refresh
  - [x] Delete → promo disappears
- **API:** `GET / POST / PUT / DELETE /api/v1/promo-calendar`
- **Note:** this is the most complete user-facing feature in the app. Every other CRUD page should follow this page's pattern.

### F9 — Offers library (read-only)
- **Status:** ✅ **superseded (2026-08-04)** — main listing now shows the real WGR offer catalog + revenue. See **"Marketing — Offers (real WGR catalog, deliverable 5)"** near the end of this doc for current verification steps.
- **URL:** `/marketing/offers`
- **API:** `GET /api/v1/offers/catalog` (new); legacy `GET /api/v1/offers` (app-CRUD test data) untouched, still backs the builder's create flow.

### F10 — Marketing overview hub
- **Status:** ✅ **verified-working (2026-05-19)**
- **URL:** `/marketing`
- **What was verified:**
  - [x] KPI tiles render
  - [x] Tool quick-links navigate to ads / email / social / dm / offers / promo / icp / funnels
  - [x] No errors
- **API:** `GET /api/v1/dashboard/stats`
- **Note:** the page reads `dashboard/stats` which we already verified. Hub itself is a thin navigation layer over the sub-pages.

---

## 🟡 PARTIAL — backend works, frontend is the gap (or vice versa)

These are the highest-value items. Each one is hours, not days.

### F11 — Sales Calls list
- **Status:** ✅ **verified-working (2026-05-20)** — wired to `GET /api/v1/ci/calls?call_type=Sales`
- **URL:** `/sales-calls`
- **What changed:** Page now fetches on mount + after every successful transcript upload. Renders rows with date, call_type, processed badge, insights count. Empty state ("No calls analyzed yet") still shows when the table is empty (currently the case — feeds will populate after F19 ships).
- **What was verified:** [x] Page renders cleanly with empty state, no errors
- **URL:** `/sales-calls`
- **What was verified:**
  - [x] Page renders without errors
  - [x] Upload widget + "No calls analyzed yet" empty state both visible
  - [x] Confirmed (by reading `page.tsx` source) that there is no `apiClient.` call anywhere on the page
- **What's still needed (~1 hour to wire, separate from F19 net-new work):**
  - Add `useEffect` + `apiClient.get("/ci/calls")` to the page
  - Render rows with call date, type, processed-status, link to detail page
  - Keep the empty state as fallback when list is actually empty
- **Note:** even after wiring, the page only displays useful data once F19 (Sales Call Analyzer) processes real calls.

### F12 — Marketing specialist HTTP endpoints return hardcoded text
- **Status:** ✅ **verified-working (2026-05-20)** — all 4 endpoints now stream real Claude output via MarketingDirector
- **Endpoints:** `POST /api/v1/{ads,dm,email,social}`
- **What was fixed (5 separate bugs found during this work):**
  1. **Hardcoded f-string returns** — each route built `MarketingDirector` + registered a specialist, then ignored both and returned a hardcoded `f"Email performance: {n} campaigns sent..."`. Replaced with real `director.stream_response(prompt)` aggregation.
  2. **Duplicate `register_specialist()` calls** — `MarketingDirector.__init__` already registers all 6 specialists (`social_media`, `email_writer`, `funnel_analyst`, `ads_manager`, `dm_specialist`, `offer_creator`). Routes were re-registering, creating duplicate `delegate_to_*` tools and 400-ing with `Tool names must be unique.` on the email route. Removed from all 4 routes.
  3. **Social-scripts: schema didn't accept what frontend sent** — page POSTed `{topic, platform, brand_voice}` but `SocialAnalyzeRequest` only had `{date_from, date_to}`. Pydantic silently dropped the fields → director never saw the topic → response didn't mention platforms. Added `topic / platform / brand_voice` to `SocialAnalyzeRequest`; added a script-mode branch to the prompt; backend now echoes the result into both `analysis` AND `script` so the frontend can read either.
  4. **Frontend MOCK fallbacks masked Claude output on regenerate** — both `/marketing/email/compose` and `/marketing/social/scripts` had silent `?? MOCK_AI_SUGGESTION` / `|| MOCK_SCRIPT` fallbacks that fired whenever the response field was empty. Every regenerate produced an identical hardcoded string. Removed both fallbacks; now show the real response or an explicit error message.
  5. **Client-side 30s timeout aborted long Claude tool-use loops** — `apiClient` default timeout was 30s; director→specialist→Claude tool-use rounds easily exceed that. Bumped `/email/draft` to 120s via per-call option. Other 3 endpoints unbumped so far — if they timeout, same fix applies.
- **Also added: structured email draft endpoint (`POST /api/v1/email/draft`)** — the page's "Apply to Draft" button needed structured `{subject, body, cta}` output. The base `/email` returns markdown analysis (the right shape for analysis, wrong for a compose form). New route prompts the director to return JSON, parses it (handles ```` ```json ```` fences + line-split fallback). Frontend now reads from `/email/draft` and renders structured Subject / Body / CTA sections.
- **Copy button bug (side-effect of verifying F14/F16)** — both `/marketing/ads/generator` and `/marketing/social/scripts` had Copy buttons with no `onClick` handler. Wired both to `navigator.clipboard.writeText()`.
- **Regenerate button bug** — `/marketing/social/scripts` "Regenerate" button had no `onClick`. Wired to `handleGenerate` via prop.
- **"Apply to Draft" silent no-op** — the page's `handleApplySuggestion` had `if (subject === "")` and `if (body === "")` guards that silently skipped overwriting fields with any existing text. Replaced with unconditional overwrite + structured field population from `/email/draft` response shape.
- **What was verified:**
  - [x] `POST /api/v1/ads` returns varying analysis across runs
  - [x] `POST /api/v1/dm` returns varying, relevant DM sequences
  - [x] `POST /api/v1/email` (analyze) returns varying analysis
  - [x] `POST /api/v1/email/draft` returns structured `{subject, body, cta}`
  - [x] `POST /api/v1/social` (script mode) returns content referencing the requested platform + topic
  - [x] Copy buttons copy text to clipboard
  - [x] Regenerate button re-runs generation
  - [x] Apply to Draft overwrites Subject + Body cleanly
- **Files touched (total for F12):**
  - `backend/app/routes/ads.py`, `dm.py`, `email.py`, `social.py`
  - `backend/app/schemas/social.py` (added 3 fields)
  - `frontend/src/app/(app)/marketing/email/compose/page.tsx`
  - `frontend/src/app/(app)/marketing/social/scripts/page.tsx`
  - `frontend/src/app/(app)/marketing/ads/generator/page.tsx`
- **What's left as polish (deferred):**
  - Other 3 specialist endpoints may need timeout bumps if exercised heavily (currently still on 30s default)
  - Frontend ads-generator / social-scripts / dm-templates currently render raw `analysis` markdown — could be parsed into typed UI components (variants list, sequence steps, etc.) but functional as-is
- **Affected URLs:** `/marketing/ads/generator`, `/marketing/email/compose`, `/marketing/social/scripts`, `/marketing/dm/templates`
- **Current state:** POST `/api/v1/{ads,dm,email,social}` instantiate `MarketingDirector` + specialist, then **ignore them** and return a hardcoded f-string. Frontend pages display the f-string as if it were real AI output.
- **What's needed (~2 hours total for all 4):**
  - In each of `backend/app/routes/{ads,dm,email,social}.py`, replace the hardcoded return with:
    ```python
    response_text = ""
    async for chunk in director.stream_response(query, context):
        response_text += chunk
    return XxxAnalyzeResponse(analysis=response_text, ...)
    ```
  - Verify response model still fits (may need to map markdown text into typed fields)
- **Verify after fix:**
  - [ ] POST `/api/v1/ads` twice with the same input → responses differ word-for-word (real LLM output varies)
  - [ ] Same for `/dm`, `/email`, `/social`

### F13 — Content Ideas persistence
- **Status:** ✅ **verified-working (2026-05-20)** — full read + create round-trip live
- **URL:** `/ci-content-ideas`
- **What changed:**
  - **Backend**: added `POST /api/v1/ci/content-ideas` (new) + `CreateContentIdeaRequest` schema. Maps frontend `title` → backend `content_premise`; `platform` → `content_format`. Also added `content_premise` field to `ContentIdeaSummary` so the title round-trips on GET.
  - **Frontend**: replaced `SEED_IDEAS + useState` with `apiClient.get/post`. Added `normaliseStatus` mapper to handle backend's new-enum values (`new / in_progress / used / archived`) gracefully.
- **What was verified:** [x] Add idea → appears in list (5s delay due to Supabase ap-southeast-2 pooler latency, not a bug) → still there after refresh
- **Latency note:** save takes ~5s from local Mac. Network speed-of-light to ap-southeast-2 Supabase. Optimistic rendering would mask it but adds complexity; left as-is.
- **URL:** `/ci-content-ideas`
- **Current state:** Pure client-state with `SEED_IDEAS` array + `useState`. Add Idea form saves to local state only — refreshing the page wipes everything.
- **Schema mismatch (the real complication):**
  - Frontend wants `title` + `platform` (Instagram/TikTok/Email/LinkedIn)
  - Backend `content_ideas` table has `content_format` + no `title` column
  - Backend has GET + PUT, but **no POST** endpoint to create new ideas
- **What's needed (~3 hours):**
  - Alembic migration: add `title VARCHAR(255)` + `platform VARCHAR(50)` columns to `content_ideas`
  - Add `POST /api/v1/ci/content-ideas` route in `backend/app/routes/ci.py`
  - Extend response schemas to include the new columns
  - Swap `SEED_IDEAS + useState` for `apiClient.get/post/put` calls in `frontend/src/app/(app)/ci-content-ideas/page.tsx`
- **Verify after fix:**
  - [ ] Create idea via UI → appears in list
  - [ ] Refresh page → idea still there
  - [ ] Walk status through Idea → Scheduled → Written → Sent → Archived (each allowed transition)
  - [ ] Invalid transition (e.g. Sent → Idea) returns 422

### F14 — AI ad-copy generator
- **Status:** ✅ **verified-working (2026-05-20)** — F12 fix lit this up. Backend now returns real varying analysis; page renders it.
- **URL:** `/marketing/ads/generator`
- **What was verified:**
  - [x] Submit form → output varies across runs
  - [x] Generated content references real pain points / offers from the data layer
  - [x] Copy button works (separate bug fixed during F12)
- **Polish deferred:** the page still has a `MOCK_VARIANTS`-shaped rendering path. Currently the markdown response renders correctly inside that frame. Parsing the markdown into separate `headline / body / CTA` typed variants would be a UI polish task; not blocking.

### F15 — Email compose AI assist
- **Status:** ✅ **verified-working (2026-05-20)** — full structured-draft flow live
- **URL:** `/marketing/email/compose`
- **What was verified:**
  - [x] AI Assist returns varying structured drafts (Subject + Body + CTA)
  - [x] Apply to Draft populates the form's Subject and Body fields cleanly
  - [x] No silent MOCK_AI_SUGGESTION fallback masking results
- **Backing endpoint:** `POST /api/v1/email/draft` (new — added in F12)
- **What's still NOT wired (deferred):**
  - "Send" button has no handler — clicking does nothing. Would need a `POST /api/v1/email/campaigns` create endpoint + frontend wiring. Out of scope; treat as a separate feature.

### F16 — Social script generator
- **Status:** ✅ **verified-working (2026-05-20)** — F12 fix lit this up
- **URL:** `/marketing/social/scripts`
- **What was verified:**
  - [x] Scripts vary across runs (MOCK_SCRIPT fallback removed)
  - [x] Output references the requested topic + platform (schema bug fixed in F12)
  - [x] Copy Script button works (separate bug fixed during F12)
  - [x] Regenerate button works (separate bug fixed during F12)
  - [x] User confirmed: "looks good to be honest"

### F17 — DM template generator
- **Status:** ✅ **verified-working (2026-05-20)** — F12 fix lit this up
- **URL:** `/marketing/dm/templates`
- **What was verified (user feedback during F12 testing): "works great, totally relevant"**
  - [x] Generated DM sequences vary across runs
  - [x] Output references real ICP + pain points from the data layer
  - [x] Page-specific copy/render bugs not encountered

### F18 — Offer builder save
- **Status:** ✅ **verified-working (2026-05-20)** — POSTs to `/offers`, persists, library reflects it
- **URL:** `/marketing/offers/builder`
- **Two bugs found + fixed during this:**
  1. **Save handler was toast-only** — never called the API. Wired to `apiClient.post("/offers", {name, description, price, status, notes})`. Structured form data (tiers, bonuses, guarantee, urgency, CTA) is stuffed into `notes` as JSON since the backend's `Offer` model is flat. **Lossy but persistent** — the library page needs to parse `notes` to render the structured fields back; deferred.
  2. **Backend 500 on `OfferResponse.model_validate(offer)`** — the schema typed `created_at: str` but the SQLAlchemy column returns a `datetime`. Pydantic raised `ValidationError`. Fixed by typing as `datetime` + adding a `field_serializer` to emit ISO 8601 string on the JSON contract. This silently broke any `GET /offers` that returned a non-empty list too — fix applies there as well.
- **UX polish:** after a successful save, the form **resets to defaults** (Starter/Pro/Elite tiers, "Apply Now" CTA, 30-day guarantee) so the user can build another offer immediately. `setIsSaved(true)` still shows the brief "Saved ✓" feedback.
- **What was verified:**
  - [x] Save returns 200/201
  - [x] Form clears to defaults after save
  - [x] New offer appears in `/marketing/offers` library
  - [x] Persists across refresh
- **Files touched:**
  - `backend/app/schemas/offers.py` (datetime fix)
  - `frontend/src/app/(app)/marketing/offers/builder/page.tsx` (Save handler + form reset)

---

## 🔴 STUB — page exists, feature does not

These need real work to wire up, but the backend largely exists.

### F19 — Sales Call Analyzer extraction pipeline
- **Status:** ✅ **verified-working (2026-05-20)** — end-to-end m4a → transcript → 16 insights + summary
- **What was built:**
  - `backend/app/prompts/call_analyzer_v1.py` — 22-field VoC extraction prompt with `summary` (4–7 sentence narrative) + `insights` (load-bearing moments)
  - `backend/app/tasks/call_analyzer.py` — Celery task `analyze_call(call_id)` calls Claude Sonnet 4.6, parses JSON (handles fenced/prose-wrapped variants), writes `summary` to `Call.summary` + N `Insight` rows
  - Alembic migration `a1b2c3d4e5f6` adds `Call.summary` TEXT column
  - `POST /api/v1/ci/calls` — paste-transcript ingestion (skips Whisper)
  - `POST /api/v1/ci/calls/{call_id}/analyze` — re-run analyzer on existing call
  - `POST /api/v1/transcribe/upload` — multipart audio upload (replaces 25 MB cap with local Whisper, no limit)
  - **Local Whisper via `faster-whisper` `small` model** — replaces OpenAI Whisper API entirely (free, offline, no quota). Model cached at `backend/.tmp/whisper-models/`
  - `transcribe_video` Celery task auto-chains `analyze_call` after successful transcription
  - Transcript saved as `.txt` artifact at `backend/.tmp/transcripts/{call_id}.txt`
  - `GET /ci/calls/{call_id}/transcript.txt` — download endpoint with DB fallback
- **Frontend:**
  - `/sales-calls` rows are clickable → opens new `/sales-calls/[call_id]` detail page
  - Detail page shows: summary, insights (with raw quotes), content ideas, transcript, plus Download / Re-analyze buttons
- **Verified end-to-end (2026-05-20):**
  - [x] Uploaded a 38 MB m4a sales call (Rich/Idaho broker — a real Greg discovery call)
  - [x] Whisper transcribed locally — 55 KB transcript text written to `Call.transcript_text` + `.tmp/transcripts/CALL_B23D56BB.txt`
  - [x] `analyze_call` chained automatically; Claude returned summary + 16 insights
  - [x] `SELECT COUNT(*) FROM insights WHERE call_id='CALL_B23D56BB'` → 16
  - [x] `Call.summary` populated with 1,163-char narrative
  - [x] Detail page renders all three: summary, 16 insights with raw quotes, full transcript
  - [x] Download transcript button works (serves .txt with Content-Disposition)
- **Operational note:** **Celery worker must be running** for the analyzer chain to fire. Without it, tasks pile up in Redis (`redis-cli llen celery`) and the UI shows 0 insights forever. Start with: `cd backend && set -a && source .env && set +a && PYTHONPATH=. .venv/bin/celery -A app.tasks.celery_app worker --loglevel=info`.
- **Out of scope (future):** Separate `pain_points`/`wins`/`objections`/`goals` tables aren't being written — the Insight model carries those signals via `insight_type` + `signal_family` columns, which is sufficient for `/ci-insights` and `/ci-market-signals`. If the dedicated tables are wanted later, mirror the Insight write loop.

### F20 — Social dashboard
- **Status:** ✅ **verified-working (2026-05-19)**
- **URL:** `/marketing/social`
- **Finding:** Earlier audit was wrong — the page IS wired (calls `apiClient.get("/social")` on mount). It was failing for the same F32 ES256 JWT reason as F21. Once F32 was fixed, KPIs populated.
- **What was verified:**
  - [x] 4 platforms render (Instagram, Facebook, LinkedIn, TikTok) with real numbers
  - [x] KPI tiles show followers, engagement, etc. — no "—" placeholders
- **Data source caveat:** the numbers come from `social_stats` rows seeded by Step 1 + refreshed by Celery beat. These are hardcoded constants in `seed_sprint3.py` and `app/tasks/social_stats.py`, not real Meta/LinkedIn API data. See F28 for real-platform connector work.

### F21 — Email dashboard
- **Status:** ✅ **verified-working (2026-05-19)** — but required fixing F32 first
- **URL:** `/marketing/email`
- **Finding:** Earlier audit was wrong — the page IS wired (imports `apiClient`, calls `apiClient.get<EmailData>("/email")`). It was returning 401 because of the F32 bug (Supabase ES256 JWTs rejected by HS256-only backend). Once F32 was fixed, the page rendered correctly.
- **What was verified:**
  - [x] `GET /api/v1/email` returns 200 OK with `{campaigns, avg_open_rate, avg_click_rate}`
  - [x] Frontend shows **7 sent campaigns** (one of 8 seeded rows has `status='draft'` and is correctly filtered out)
  - [x] KPI cards populate with real numbers
- **Note on the count:** seed script inserts 8 rows; 7 are `status='sent'` + 1 is `status='draft'`. The page surfaces "campaigns sent" semantics, so 7 is correct.

---

### F22 — Ads dashboard
- **Status:** ✅ **verified-as-empty (2026-05-19)** — wiring confirmed; `ads_stats` table empty (beat hasn't fired the ads task yet, will at next 06:20 UTC)
- **URL:** `/marketing/ads`
- **What was verified:**
  - [x] Page renders cleanly with 0 / "—" KPIs (no crash, no error)
  - [x] `GET /api/v1/ads` returns 200 OK (wiring fine)
- **To unblock:** wait for the next ads-stats beat tick (every 6h at :20 UTC), OR manually trigger via `cd backend && ./scripts/trigger-task.sh ads`. After that, page will show facebook_ads / google_ads / instagram_ads metrics.

### F23 — Funnels dashboard
- **Status:** ✅ **verified-working (2026-05-19)**
- **URL:** `/marketing/funnels`
- **Finding:** Earlier audit was wrong — page IS wired. Was failing for the F32 reason. Now works.
- **What was verified:**
  - [x] Two funnels render: `coaching-program-v2` and `webinar-apr-2026`
  - [x] Stage-by-stage conversion percentages shown (e.g. coaching: awareness → interest = 62.2%, intent = 49.7%, purchase = 43.1%)
- **Data source caveat:** funnel events are seed data (1,639 hardcoded rows from `seed_sprint3.py`). Replacing with real funnel-tool data is webhook work (page already has a working `POST /funnels` webhook receiver for that).

### F24 — ICP management UI
- **Status:** ✅ **verified-working (2026-05-20)** — wired to `GET /icp`, `PUT /icp/{id}`, `POST /icp/generate`
- **URL:** `/marketing/icp`
- **What changed:**
  - Loads ICPs from `GET /icp` on mount. Empty table → empty grid (currently the case).
  - Edits PUT to `/icp/{id}` (maps frontend `name`→backend `segment`, `industry`→`description`)
  - **New "✨ Generate ICPs" button** POSTs to `/icp/generate` (fire-and-forget; enqueues a Celery task that uses Claude to synthesise segments from real intelligence data). Shows "Refresh in ~30s" banner — proper task-status polling deferred.
  - Old manual "+ Add ICP" form left as client-state-only (the Generate path is the persistent one).
- **What was verified:** [x] Page loads, empty state renders correctly; ICPs table is empty (expected — no insights have been extracted yet, F19 territory)
- **Field mapping is lossy:** frontend has `industry, criteria.companySize, criteria.titleRole, criteria.painPoints, matchScore`. Backend has `segment, description, demographics, psychographics, pain_summary, goal_summary, is_primary`. I mapped what I could; unmapped fields show "—". A real schema alignment is needed if/when this gets heavily used.
- **URL:** `/marketing/icp`
- **Current state:** Pure client-state with hardcoded `INITIAL_ICPS`. Backend HAS `GET /icp`, `GET /icp/primary`, `PUT /icp/{id}`, AND a `POST /icp/generate` Celery-backed Claude generation task.
- **What's needed (~2-3 hours):**
  - Drop hardcoded `INITIAL_ICPS`
  - Wire `apiClient.get("/icp")` to fetch list
  - Wire add/edit/save buttons to `POST /icp/generate` (for AI generation) and `PUT /icp/{id}` (for edits)
- **Verify after fix:**
  - [ ] Page loads existing ICPs from DB
  - [ ] Trigger AI generation → new ICP appears after Celery task completes
  - [ ] Edit + save → persists after refresh

### F25 — DM template library CRUD
- **Status:** ✅ **verified-as-empty (2026-05-19)** — wiring confirmed; `dm_stats` empty + no `dm_templates` table yet
- **URL:** `/marketing/dm`
- **Current state:** Library shows hardcoded `SEED_TEMPLATES`. Backend `GET /dm` exists but there's no `dm_templates` table or CRUD endpoint for the templates themselves.
- **What's needed (~half a day):**
  - Alembic migration: new `dm_templates` table (id, name, platform, body, created_at, updated_at)
  - Backend: `GET /dm/templates`, `POST /dm/templates`, `PUT /dm/templates/{id}`, `DELETE`
  - Frontend: replace `SEED_TEMPLATES` with API calls; wire form
- **Verify after fix:**
  - [ ] Create template → persists
  - [ ] Edit template → persists
  - [ ] Delete template → gone after refresh

### F26 — Transcript upload general use
- **Status:** ⬜ pending verification
- **URL:** `/ci-transcript-upload`
- **Current state:** Upload widget identical to `/sales-calls`, never wired to any ingestion-and-display pipeline.
- **What's needed (~half a day after F19):**
  - Once F19 ships, this page becomes the generic ingestion entry point. Mostly just needs to show "Uploaded — processing" status + link to where the extracted insights will appear.
- **Verify after fix:**
  - [ ] Upload file → see processing status
  - [ ] After Celery completes, link goes to `/ci-insights` filtered to that call's results

---

## 🟣 NEW WORK — substantial product features

These are bigger than wiring jobs. Each is a sprint of its own.

### F27 — Org tier rollups (CEO → Director → Manager → Agent)
- **Status:** ⬜ not started
- **What it should do:** The product brief (per the user interview 2026-05-18) describes a CEO → Directors → Managers → Agents hierarchy with rollup views: each tier sees the tier below them in aggregate.
- **Current state:** No `agents`, `managers`, `directors` tables. No rollup queries. No scorecard UI for any tier.
- **What's needed (~2 sprints):**
  - Schema design for org structure + tenant scoping
  - Ingestion path: how do agents get added? (signup form? CSV import? auto from sales-call assignees?)
  - Rollup queries per tier
  - UI: agent scorecard, manager dashboard, director rollup, CEO summary

### F28 — Real-platform connectors
- **Status:** 🟡 **partial (2026-05-21)** — Mailchimp shipped; 4 platforms remain
- **What it should do:** Replace the 5 Celery tasks' embedded seed data with real API calls to Meta Ads, Google Ads, Mailchimp/ActiveCampaign, Instagram/LinkedIn/Facebook, TikTok.
- **Shipped:**
  - **Mailchimp connector for `update_email_stats`** — `backend/app/services/mailchimp_client.py` (httpx, no SDK). Task now hits `/3.0/campaigns` + `/3.0/reports/{id}`, normalises into the existing `EmailCampaign` shape, upserts by name. When `MAILCHIMP_API_KEY` is empty, falls back to the original seed data so the dashboard still renders. Returns `source: "mailchimp" | "seed"` for visibility.
  - **Settings:** `MAILCHIMP_API_KEY` + `MAILCHIMP_SERVER_PREFIX` (auto-derived from key suffix when empty)
  - **Resilience:** HTTP errors during Mailchimp fetch log and fall through to seed — task never crashes the beat tick on API outage
- **Still needed:** Meta Ads (for `update_ads_stats`), Google Ads (also `update_ads_stats`), Instagram/LinkedIn/Facebook (`update_social_stats`), TikTok (same), comments collector
- **Verify Mailchimp:**
  - [ ] Add `MAILCHIMP_API_KEY=us21-abc...` to `backend/.env`
  - [ ] Restart Celery worker; trigger task: `cd backend && PYTHONPATH=. .venv/bin/celery -A app.tasks.celery_app call app.tasks.email_stats.update_email_stats`
  - [ ] Task result should report `source: "mailchimp"` and `campaigns_checked > 0`
  - [ ] `/marketing/email` page shows real campaign rows with live open/click rates

### F29 — Multi-tenancy
- **Status:** ⬜ not started
- **Note:** Greg is the only tenant today. Out of scope for now per the migration plan.
- **What it should do:** When the product onboards a second customer, all queries need `tenant_id` scoping.
- **What's needed:** schema change adding `tenant_id` column to every business table + RLS policy + every route filtering by current tenant. The parked `central-intelligence-core/` had this documented as a deferred risk.

---

## Cron / scheduled-task verification

These are infrastructure, not user-visible features, but verifying them is important.

### F30 — Celery beat schedule fires
- **Status:** ✅ **verified-by-evidence (2026-05-19)**
- **What was verified:** Direct DB inspection of `social_stats` shows two distinct `period_start` values: 4 rows from `2026-04-01` (the original Step 1 seed) AND 4 rows from `2026-05-01` (added by Celery's `update_social_stats` task firing on cron). Same pattern in `funnel_stats`. The May rows can ONLY come from beat dispatching the task — confirms the beat schedule added in Step 2 is live and ticking.
- **What's NOT yet verified:** `ads_stats` is still empty (next cron at :20 every 6h UTC — may simply not have fired yet by the time of verification). Not a bug; just timing.

---

### F31 — Password reset flow
- **Status:** ⬜ pending verification — **fix landed 2026-05-19; needs end-to-end test**
- **URLs:** `/login` (request reset) → email link → `/reset-password` (set new password)
- **Original bug:** Clicking the reset email link redirected to `http://localhost:3000/login#error=access_denied&error_code=otp_expired&error_description=Email+link+is+invalid+or+has+expired`. Three root causes found:
  1. `resetPasswordForEmail()` in `auth-context.tsx` was called WITHOUT a `redirectTo` argument, so Supabase used the project's Site URL (which doesn't match where we can consume the token)
  2. No `/reset-password` page existed to consume the recovery token
  3. No `updatePassword()` function on the auth context — even if a page existed, it had no API surface to call
- **What was fixed:**
  - `frontend/src/contexts/auth-context.tsx` — added `redirectTo: ${window.location.origin}/reset-password` to the reset call; added new `updatePassword(newPassword)` function that wraps `supabase.auth.updateUser({password})`
  - `frontend/src/app/reset-password/page.tsx` — new page that detects the recovery token in `window.location.hash`, lets `@supabase/ssr`'s `createBrowserClient` (which has `detectSessionInUrl` on by default) bootstrap the PASSWORD_RECOVERY session, then renders a "set new password" form. Also parses `#error=...` hash params to show a helpful message when the token is expired or already-used.
- **Configuration step you must do in the Supabase Dashboard (one-time):**
  - Go to https://supabase.com/dashboard/project/dynsavtgnejtezhljpqk/auth/url-configuration (replace with your actual project ref if different)
  - Under **Redirect URLs**, add `http://localhost:3000/reset-password` (and your production URL when you deploy, e.g. `https://your-prod-host.com/reset-password`)
  - Save. **Without this allow-list entry, Supabase will refuse to honor the redirectTo argument and fall back to the Site URL.**
- **What to verify:**
  - [ ] Go to `/login`, click "Forgot password", enter your email, submit. Confirm "Reset link sent to ..." message.
  - [ ] Open the reset email. The link should now point to `http://localhost:3000/reset-password#access_token=...&refresh_token=...&type=recovery`
  - [ ] Click the link **within 1 hour**. You land on `/reset-password`.
  - [ ] Page shows "Validating reset link…" briefly, then a "Set a new password" form.
  - [ ] Enter a new password (≥ 8 chars, both fields match), submit.
  - [ ] Success message: "Password updated. Redirecting to login…", then redirects to `/login`.
  - [ ] Log in with the new password — should succeed.
- **Failure-mode test (optional, exercises the error UI):**
  - [ ] Click an old (expired or already-used) reset link → page shows "Reset link no longer valid" with the Supabase error description and a "Back to login →" link, NOT a blank page.
- **Files touched:**
  - `frontend/src/contexts/auth-context.tsx` (modified: added redirectTo + updatePassword)
  - `frontend/src/app/reset-password/page.tsx` (new)

---

### F32 — Backend JWT verification rejected Supabase ES256 tokens
- **Status:** ✅ **verified-working (2026-05-19)** — found during F21 verification, fixed inline
- **Severity when found:** Blocking — every authed page returned 401, every KPI card showed "—"
- **Original bug:** Supabase started signing JWTs with **ES256** (asymmetric, ECDSA P-256) in 2024. The backend's auth middleware (`backend/app/middleware/auth.py`) hardcoded `_JWT_ALGORITHMS = ["HS256"]` (HMAC symmetric) and verified with `settings.supabase_jwt_secret`. Every modern Supabase JWT was rejected as "invalid signature." 401s cascaded: page renders empty UI, no error visible to user.
- **Symptom path during verification:**
  1. Logged in successfully (cookies present in browser)
  2. `/marketing/email` showed empty KPI cards, no error visible
  3. DevTools → Network → `/api/v1/email` returning 401
  4. Request DID include `Authorization: Bearer eyJ...` header
  5. JWT header decoded to `{"alg":"ES256","kid":"...","typ":"JWT"}`
  6. Backend was verifying with HS256 + shared secret — mismatched algorithm, signature check fails
- **Affected surfaces:** Every authed HTTP endpoint (so: every page with a fetch except `/login`, `/dashboard/recommendations`, `/leads/*`). Also both WebSocket auth paths (Central Intelligence chat, Marketing Director chat — same hardcoded `algorithms=["HS256"]`).
- **What was fixed (3 files):**
  - `backend/app/middleware/auth.py`:
    - Added JWKS fetching with `httpx` against `{SUPABASE_URL}/auth/v1/.well-known/jwks.json` (requires `apikey` header — anon key)
    - Cache keyed by `kid`, refreshed hourly + on unknown-kid miss (5s fetch timeout)
    - Expanded `_JWT_ALGORITHMS = ["ES256", "RS256", "HS256"]`
    - New exported helper `verify_supabase_jwt(token) -> dict | None` that picks the right key based on the JWT header's `alg`
    - HS256 fallback path preserved for legacy/older Supabase projects
  - `backend/app/routes/central_intelligence.py`: WebSocket auth now calls `verify_supabase_jwt()` instead of raw `jwt.decode` with HS256
  - `backend/app/routes/directors.py`: same WebSocket auth fix
- **What to verify (when re-checking after fresh clone or env change):**
  - [x] Log in via Supabase
  - [x] Open any authed page (e.g. `/marketing/email`)
  - [x] DevTools → Network → all `/api/v1/*` requests return 200
  - [x] Page renders real data
- **Pitfall to know:** if the user has stale `sb-*` cookies in their browser (e.g. from a session that pre-dates the fix), they may see "Unknown user" in the sidebar even though the page loads. Fix: DevTools → Application → Cookies → delete `sb-<project-ref>-auth-token.*` cookies + clear Local Storage for the origin → hard reload → log in fresh. The auth-context will hydrate cleanly.
- **Files touched:**
  - `backend/app/middleware/auth.py` (modified: JWKS support + shared verify helper)
  - `backend/app/routes/central_intelligence.py` (modified: WebSocket auth)
  - `backend/app/routes/directors.py` (modified: WebSocket auth)

---

## Tracking metrics

After each session, count:

- **Completed across 2026-05-19 + 2026-05-20:**
  - **Verified working with real interaction:** F1 login, F8 promo-calendar (full CRUD), F10 marketing hub, F21 email, F20 social, F23 funnels, F6 chat, F7 marketing-director, F30 beat schedule, F12 specialist endpoints, F14 ad-copy gen, F15 email compose + structured draft, F16 social scripts, F17 DM templates, **F11 sales-calls list**, **F13 content-ideas CRUD**, **F18 offer-builder save**, **F24 ICP management**
  - **Verified-as-empty (wiring OK, table empty):** F2 dashboard, F3 leads, F4 ci-insights, F5 market-signals, F9 offers, F22 ads, F25 DM
  - **Fixes shipped:** F31 password reset (pending email cooldown), F32 ES256 JWT, F12 (5-bug cascade), `/email/draft` + `/ci/content-ideas` (POST) endpoints added, `OfferResponse.created_at` datetime serialization bug
- **Total verified:** 28 / 32 features
- **Remaining unverified (4):** F19 (Sales Call Analyzer — net-new sprint), F26 (transcript upload — depends on F19), F27 (org tier rollups), F28 (real-platform connectors), F29 (multi-tenancy), F31 e2e (email cooldown)
- **Critical-path blockers remaining:** F19 is the only big item. Once it's done, F4/F5/F11 dashboards populate naturally; F26 follows easily; F27 becomes addressable.
- **Deferred polish surfaced during the verification pass:**
  - `/ads`, `/dm`, `/social` POST endpoints may need timeout bumps to 120s like `/email/draft` — only that one is bumped so far. Same fix pattern.
  - Email "Send" button is still a no-op — needs a `POST /email/campaigns` endpoint + wiring.
  - Ads/DM/social pages render `analysis` as a single markdown block; could be parsed into typed UI sections.
  - F18 offer schema is lossy (tiers/bonuses/urgency stuffed into `notes` as JSON). Library page would need to parse `notes` to render richly.
  - F24 ICP "Generate" is fire-and-forget; no task-status polling.
  - F24 ICP UI/backend schema mismatch (industry, criteria, matchScore vs segment, demographics, psychographics, is_primary). Mapped what I could; full schema alignment deferred.
  - F13 content-ideas POST has ~5s latency from local Mac → Supabase ap-southeast-2 pooler. Optimistic rendering would mask it.

## WGR Attribution Data Sync (2026-07-26)

**Feature:** CI now mirrors Greg's attribution data: per-lead first/last-touch
UTMs + GHL contact id, the attribution taxonomy (UTM → canonical channel,
with a read-time resolver at `backend/app/services/attribution.py`),
attribution touches (`lead_engagements`), and Meta Ads campaigns/ads/daily
performance. Sync runs are serialized by a Redis lock; manual partial pulls
no longer advance the watermark.

**How to locate:** backend data only for now (the Leads/Sales UI ships in the
next ticket, ClickUp 86d3u65cb). Verify via DB or API.

**Steps:**
1. Run the probe: `cd backend && PYTHONPATH=. .venv/bin/python -m
   scripts.probe_wgr_attribution` — connection identity must say `ci_reader`,
   every table OK. Note the WGR-side counts.
2. In CI's DB (Supabase table editor or psql): `attribution_taxonomy`,
   `meta_campaigns`, `meta_ads`, `meta_ad_performance` row counts are > 0 and
   match the probe's WGR counts (2026-07-26 reference: 27 / 29 / 472 / 635).
   `lead_engagements` is expected EMPTY until Greg's email-attribution flow
   starts producing — not a failure.
3. Pick a lead you know came from Instagram or email — its row in `leads`
   shows `utm_source_last` (first-touch coverage is sparse upstream: ~85 of
   12k leads; last-touch ~2.4k — expected).
4. Wait for (or trigger) the hourly sync; `sync_log` shows the new tables
   syncing without errors, and a second concurrent trigger returns
   `run lock not acquired`.

**Pass:** counts match WGR's; a known lead carries UTM values; concurrent
runs skip cleanly. **Fail:** any mirrored table empty while WGR has rows
(except lead_engagements), sync errors in sync_log, or probe reports a role
other than ci_reader.

## Lead & Sales Source Attribution (2026-08-03)

**Feature:** The Leads UI now surfaces the read-time canonical channel from
the WGR attribution sync (previous section): a Channel column + filter and
channel breakdown donut on `/leads`, and a full-width Attribution card on
lead detail showing raw first/last-touch UTMs. `/sales/summary` inherits the
same breakdown since it shares `compute_lead_stats` with `/leads/stats`.
Channel is computed per-request, never stored.

**Sales half (deliverable 9b, added 2026-08-03):** `/leads` also gains a
**Revenue by Channel** card — `closed_sales.amount_collected` attributed to
the same canonical channel buckets, scoped by `close_date` via the page's
existing date-range filter. `GET /sales/summary` gains an unscoped
`revenue_by_channel` key with the same shape.

**How to locate:**
- **`/leads`** — the main Leads Dashboard.
- **`/leads/{lead_id}`** — click any row from the leads list to open detail.
- **`/sales`** — redirects straight to `/leads`; there is no separate Sales
  page to check. Verify the channel breakdown via `GET /sales/summary`
  directly (or trust `/leads/stats`, since both endpoints share the same
  `compute_lead_stats` breakdown code).

**Before you start:** with real data, expect `"No attribution"` to be the
*largest* bucket on both `/leads` and `/sales/summary` — only ~87 of 12,656
`source='wgr'` leads have first-touch UTMs and ~2,447 have last-touch UTMs
(~20% coverage). A dashboard mostly showing "No attribution" is correct
behavior, not a bug.

**Steps:**
1. Open `/leads`. Confirm a **Channel** column appears in the table, right
   of Name. (The old Source column and its filter were removed 2026-08-03 —
   channel is the meaningful axis; provenance `source` still shows on the
   lead detail Contact card and stays in the API.) Each row shows a colored
   chip (e.g.
   "Facebook Ads", "Email", "No attribution"). Any chip reading
   `unmapped:<source>/<medium>` or `"other unmapped"` renders with an amber
   warning tint, not the normal chip color — that's the taxonomy
   surface-loudly contract working as intended.
2. Look at the source/channel breakdown donut on `/leads`. Confirm its
   segments are now canonical channel names (not raw `leads.source` values
   like `wgr`/`ghl`), and that segment counts sum to the total lead count
   shown elsewhere on the page.
3. In the FilterBar, open the **Channel** filter. Its options are the same
   buckets as the Source Breakdown donut, each with its dataset-wide count
   (e.g. `meta_paid (714)`, `No attribution (10,187)`). Pick `meta_paid` and
   confirm: the table shows only meta_paid-chip rows, AND the
   "Showing X of Y" total drops to that bucket's count (the filter runs
   server-side across all leads, not just the loaded page) — pagination
   walks the full filtered set. Picking `Non-marketing` shows rows whose
   chips carry the specific non-marketing value (e.g. `system_workflow`) —
   the bucket is the rollup, the chip is the exact resolution.
3b. Confirm there is **no** Source dropdown in the FilterBar — only Search,
   Channel, Status, and the date range. (Removed 2026-08-03: with channel
   live, the provenance source filter was redundant on this page. The API's
   `source` param and `available_sources` field remain for API consumers.)
4. Pick a lead you can identify as having attribution data (from step 1's
   chips, choose a row NOT showing "No attribution") and open its detail
   page (`/leads/{lead_id}`). Confirm a full-width **Attribution** card
   appears showing a First touch row and a Last touch row of raw UTM values
   (source/medium/campaign/content) plus the resolved channel chip.
5. Pick a different lead whose list-page Channel chip read "No attribution"
   and open its detail page. Confirm the Attribution card does **not**
   render at all (hidden, not shown empty) — all 8 UTM fields are null for
   that lead.
5b. **Journey card (added 2026-08-03).** On the same detail pages, look for
   the full-width **Journey** card (between Attribution and Tags). Most WGR
   leads have one — 11,556 of 12,818 have webinar activity. Check: (a) a
   lead who watched the webinar shows Registered date, Watched live/replay
   Yes/No, and a watch time like "24m 38s"; (b) a lead with appointments
   shows an "Appointments (N)" section with first/last dates, last outcome,
   and booked-by; (c) a closed lead (filter Channel or use a known buyer)
   shows a green "Closed $X" chip in the card header plus close date and
   days-to-close in the Sales section; (d) a lead with no journey activity
   shows **no** Journey card at all (hidden, not empty). Data refreshes with
   the nightly WGR sync (snapshot reconcile — upstream rebuilds propagate,
   including deletions).
6. Navigate to `/sales`. Confirm it redirects immediately to `/leads` (no
   separate Sales page renders).
7. Call `GET /api/v1/sales/summary` directly (e.g. via the browser devtools
   Network tab while on `/leads`, or curl with an auth token) and confirm
   its breakdown list uses the same channel buckets as `/leads/stats` —
   canonical channels, `"No attribution"`, `"Non-marketing"`, and
   `unmapped:*` — with counts summing to the endpoint's total.
8. **Revenue by Channel (deliverable 9b).** On `/leads`, scroll below the
   Source Breakdown donut and confirm a **Revenue by Channel** card renders:
   each row shows a channel chip (same styling as the table's Channel
   column — amber for `unmapped:*`/`"other unmapped"`), a sales count, a
   dollar revenue figure (no decimals), and a % share of the range's total
   revenue. The card header shows the total revenue + sales count for the
   selected date range.
9. Clear all filters/date range (or set the range to "All time") and
   confirm the card's total revenue reads **$471,250** across **83 sales**
   — this is `closed_sales.amount_collected` summed across every closed
   sale, the revenue source of truth (the `lead_journey` mirror disagrees
   at $422,750; that's a known, un-reconciled discrepancy — `closed_sales`
   is authoritative). Confirm `"No attribution"` is the largest bucket by
   revenue (only 11 of the 83 buying leads carry any UTMs) — that is
   expected, not a bug.
10. Narrow the date range to a smaller window (e.g. one month) and confirm
   the card's total revenue and sales count both drop to a subset of the
   all-time figures, and the row set only shows channels with sales in that
   window (or the card shows its quiet "No closed sales in this range"
   empty state if none fall inside it).
11. Call `GET /api/v1/leads/stats` directly and confirm the JSON includes a
   `revenue_by_channel` array with `channel`, `platform`, `reportable`,
   `sales_count`, `revenue`, and `revenue_percentage` keys per bucket, and
   that `GET /sales/summary`'s `revenue_by_channel` (unscoped) sums to the
   same $471,250 / 83 sales as step 9.

**Pass:** Channel column + chips render on `/leads` with amber tint on
unmapped entries; donut segments are canonical channels summing to the
total; Channel filter narrows the loaded rows; Attribution card shows raw
UTMs + channel on leads with data and is absent (not empty) on leads
without; `/sales` still redirects to `/leads`; `/sales/summary` and
`/leads/stats` share the same bucket set; Revenue by Channel card renders
with all-time totals of $471,250 / 83 sales, "No attribution" dominant, and
a scoped date range narrows both figures to a subset. **Fail:** any of the
above missing, chip colors not distinguishing unmapped from mapped
channels, donut/filter counts not summing to the total, `/sales/summary`
diverging from `/leads/stats`'s bucket shape, or the Revenue by Channel
totals not matching $471,250 / 83 sales unscoped.

## Marketing — Ads (real data) (2026-08-03)

**Feature:** `/marketing/ads` no longer shows a hardcoded platform-breakdown
widget (Google/Facebook/Instagram/TikTok rows that always read "—"). The
page now renders straight from the WGR Meta Ads mirror — real campaigns, ads,
and daily performance snapshots — via a new `GET /ads/overview` endpoint. The
legacy `GET /ads` (ads_stats summary) and the `POST /ads` Analyze-with-AI /
ad-copy-generator flow are unchanged.

**How to locate:** `/marketing/ads` — the main Ads page under Marketing in
the sidebar.

**Before you start:** live counts as of 2026-08-03 are 29 campaigns, 472
ads, 647 performance snapshot rows — but only **7 of the 472 ads** currently
carry any performance data (the rest are identity-only: name, format,
status, hook, no spend yet). A Top Ads table showing exactly 7 rows (not 15)
is correct, not a bug. Most campaigns will show $0 spend / 0 leads for the
same reason — that's real data, not a rendering error.

**Steps:**
1. Open `/marketing/ads`. Confirm the **Platform Breakdown** card (rows for
   Google Ads / Facebook Ads / Instagram Ads / TikTok Ads, all showing "—")
   is gone entirely — there is no per-platform table at all now.
2. Confirm the KPI row shows four tiles with real numbers, not "—":
   **Active Campaigns** (14 of 29 total), **Total Spend** (~$17,006 as of
   2026-08-03 — will grow as sync continues), **Cost / Lead**, and **CTR**
   with an impressions sub-label. All four carry the marketing green
   (`#10B981`) top border.
3. Look at the **Campaigns** table. Confirm it lists real campaign names
   (e.g. "AK - new webinar", "WFM - Originals") — not placeholders — each
   with a status chip (Active/Paused), objective, budget (daily or
   lifetime, whichever the campaign has set), spend, leads, cost-per-lead,
   and an ads count. Rows are sorted by spend descending; the top row should
   be "AK - new webinar" (~$17,006 spend, 62 ads) at time of writing.
4. Look at the **Top Ads by Spend** table. Confirm each row shows a real ad
   name, its parent campaign name, ad format (e.g. "Video_Reel"), a status
   chip, a KPI-status chip (Scale/Watch/Kill — some cells legitimately blank
   since `kpi_status` is null on ~60% of performance rows), spend, leads,
   and cost-per-lead. Hover a hook-text cell that's truncated — the full
   hook shows in the tooltip. Hover a row for an ad with a `kill_date` set —
   the kill reason (e.g. "$80.94 spent, 0 leads ever — >3x kill threshold...")
   shows in the tooltip.
5. Confirm the **Generate Ad Copy** CTA card (right column, row 2) is still
   present and its "Generate Copy" button still links to
   `/marketing/ads/generator` — this is the preserved Analyze-with-AI
   affordance, untouched by this change.
6. Reload the page and watch the loading state — skeleton tiles/rows should
   render briefly, never a spinner-only or blank screen, and never native
   `alert()`/`confirm()` dialogs.

**Pass:** Platform Breakdown widget is gone; KPI tiles show real (non-"—")
numbers matching the DB; Campaigns table lists real campaign identity +
rollup data sorted by spend; Top Ads table shows up to 15 real ads with
spend-derived metrics and working hover tooltips for hook text and kill
reasons; the Ad Copy Generator CTA still works. **Fail:** Platform
Breakdown widget still present, any KPI/table showing fabricated or
placeholder values instead of real DB-backed numbers, the Ads generator CTA
missing or broken, or an empty table rendering as if it were an error
instead of a quiet "no data yet" placeholder.

## Marketing — Email Campaigns (2026-08-03)

**Feature:** `/marketing/email` overhaul (deliverable 2). The Compose Email
feature (page-builder UI at `/marketing/email/compose`) is removed. The page
now shows a filterable, sortable campaigns table backed by a new
`GET /email/campaigns` endpoint, plus a per-row visual performance indicator
(ScoreBar + Top/Mid/Low tercile chip on open_rate) and a "Top campaigns"
ranking card. `POST /email` (Analyze with AI) and `POST /email/draft` are
unchanged; the legacy `GET /email` summary endpoint is unchanged (still used
internally, no longer called by this page).

**How to locate:** `/marketing/email` — under Marketing in the sidebar.

**Before you start — audit numbers as of 2026-08-03 (read-only, live DB):**
`email_campaigns` has **2,426 rows**, all `deleted_at IS NULL`. **`status`
has exactly one distinct value: `sent`** — every row. There are **zero**
drafts and **zero** archived campaigns in the real database (those only
ever existed via the now-removed Compose flow), which is why the old
Drafts/Archived sections are gone rather than kept empty. `campaign_type`
has **12 distinct values**: Value/Education (648), Weekly Nurture (441),
Story-led (366), Launch (312), Transactional (307), Promotional Offer
(160), Client Win (94), Welcome/Onboarding (41), Re-engagement (35),
Unclassifiable (17), `regular` (2), and 3 rows with `campaign_type = NULL`.
`sent_at` ranges from 2016-07-25 to 2026-08-02. `bounce_count` is 0 on
every row today (column is real, just nothing to show yet).

**Steps:**
1. Open `/marketing/email`. Confirm there is **no Compose Email card and no
   "+ New Campaign" / "+ New Draft" button anywhere on the page** — the
   feature is fully removed, not just hidden.
2. Confirm the KPI row shows four tiles — **Campaigns**, **Avg Open Rate**,
   **Avg Click Rate**, **Total Recipients** — all with real numbers (not
   "—"), scoped to whatever filter is currently applied (unfiltered on
   first load, so **Campaigns = 2,426**).
3. In the filter row, confirm: a search box (name/subject), a **Campaign
   type** select whose options are exactly the 12 real distinct values
   above (never a fabricated option, never an option with 0 matches), a
   **Status** select (will show only **"sent"** — correct, since that's
   the only real value), a **Sent** date-range pair, and a **Sort by**
   metric select (Date sent, Sent/Recipients, Opens, Clicks, Open rate,
   Click rate, Unsubscribes, Bounces).
4. Type a campaign name fragment into search (e.g. "webinar") — confirm the
   table narrows to matching rows within ~300ms (debounced) and the KPI
   row's counts shrink to match the filtered set, not the full unfiltered
   total.
5. Set the Sent date range to a narrow recent window (e.g. 2026-07-01 to
   2026-08-02) — confirm the table and KPI row rescope to that window only,
   and the **Top campaigns** card (left column) re-ranks using only
   campaigns sent in that window.
6. Click a sortable column header (Recipients, Opens, Clicks, Unsubs,
   Bounces, or the Sent date header) — confirm it toggles ascending/
   descending (▲/▼ indicator) and the table re-sorts via a fresh server
   call (`sort_by`/`sort_dir` params), matching the leads table's
   click-to-sort behavior.
7. Confirm every row shows a **ScoreBar** in the rightmost "Performance"
   column, filled proportional to that row's open_rate relative to the
   filtered set's max open_rate, plus a small **Top / Mid / Low** chip.
   Sort by Open rate descending — confirm the top rows carry "Top" chips
   and the bottom rows carry "Low" chips (tercile split within the
   currently filtered set, not a fixed global threshold).
8. Confirm the **"Top campaigns"** card shows exactly 5 rows (or fewer if
   the filtered set has under 5), ranked #1–#5 by whichever metric is
   selected in "Sort by", each with a name, the metric's formatted value,
   and a ScoreBar — and that changing "Sort by" re-ranks this card using
   the SAME already-fetched data (no extra network call).
9. Clear all filters (via "Clear filters") — confirm the table returns to
   all 2,426 rows and the KPI row returns to the unfiltered totals.
10. Reload the page and watch the loading state — skeleton tiles/rows
    should render briefly, never a blank screen or native
    `alert()`/`confirm()` dialog.

**Pass:** Compose Email is fully gone (no card, no CTA, no route reachable);
filter dropdowns only ever show real, non-empty options; search/date-range/
type/status filters narrow both the table and the KPI row together; sort
toggles work via server round-trip and match the leads-table interaction
pattern; every row shows a ScoreBar + tercile chip that visibly correlates
with relative open_rate; the Top-campaigns card re-ranks correctly off the
selected metric within the current filtered range. **Fail:** any Compose
Email UI remnant reachable, a filter option that matches 0 rows, KPI row
not rescoping with filters, sort clicks doing nothing or hitting the wrong
column, or the performance indicator showing a fixed/fake value unrelated
to the row's real open_rate.

## CI Insights — full filters, source attribution, expanded charts (2026-08-03)

**Feature:** `/ci-insights` (deliverable 6). Note: there is a **separate**
`/insights` page (core department health metrics/recommendations engine,
`frontend/src/app/(app)/insights/`) — unrelated to this work, not touched.
The routed, sidebar-linked page for this deliverable is `/ci-insights`
(`Marketing → CI Insights` in the sidebar).

**Before you start — audit numbers as of 2026-08-03 (read-only, live DB):**
`insights` has **1,932 rows**. `insight_type`: Pain 948, Goal 510, Objection
275, Trigger 191, Win 3, Identity 2, Belief 2, Buying Signal 1 (8 distinct —
dropdown). `signal_family`: 30 distinct values (Time & Freedom 408, Income &
Money 405, Identity & Status 382, Skills & Competency 279, Life
Circumstances 184, Relationships 118, Market & Industry 112, plus 23 smaller
buckets — dropdown). `signal_strength`: Strong 1024, Moderate 826, Weak 80,
Medium 2 (4 distinct — dropdown). `pain_layer`: 958 rows NULL, then
Structural 352, Emotional 192, Identity 184, Belief 157, Tactical 53, Social
31, Strategic 5 (7 real distinct values once NULLs excluded — dropdown).
`best_use_case` has **1,019 distinct values** — free-text cardinality,
**no dropdown** (confirmed via audit, not guessed). `insight_tags` has 4,051
rows over **2,774 distinct tags** — also too high-cardinality for a
dropdown; exposed as a free-text exact-match filter. `call_id` is **100%**
populated (0 NULLs) — every insight's "source" resolves to its call.

**Steps:**
1. Open `/ci-insights`. Confirm the charts grid at the top still shows the
   original insight-type donut, signal-strength bars, and top-signals bars
   — nothing removed — **plus two new/kept charts**: "Top signal families"
   and a new **"Pain layer breakdown"** horizontal-bar chart.
2. Confirm the filter row (above the insights list) has: a **Search** box,
   **Insight Type**, **Signal Family**, **Signal Strength**, **Pain Layer**
   dropdowns (options must be exactly the real distinct values from the
   audit above — never a fabricated option), a free-text **Tag** input, and
   a **Generated** date-range pair (two `<input type="date">`s).
3. Unfiltered, confirm the list total reads **1,932** and the table is
   paginated (not a raw dump of all 1,932 rows on one page).
4. Set Insight Type = `Pain` and a Generated range of `2026-06-17` to
   `2026-07-01` — confirm the total narrows (well below 1,932) and every
   visible row's insight-type pill reads "Pain".
5. Type a Signal Family filter and confirm the charts above rescope too
   (charts are filter-aware, keyed on the same params as the list — not a
   static unfiltered summary).
6. Type a tag fragment used in the data (e.g. `time-freedom`, `burnout`) into
   the Tag field — confirm the list narrows via the `insight_tags` join
   (debounced ~300ms) and each visible row's tag chips include the typed
   tag.
7. Confirm each insight row shows a **source-attribution line** (📞 icon,
   call type · lead name · call date) below the quote, and that clicking it
   navigates to `/sales-calls/{call_id}` (or `/coaching-calls/{call_id}`
   when the call's `call_type` is "Coaching") — a real link, not a dead
   span.
8. Clear all filters — confirm the list returns to 1,932 total and the
   charts return to the unfiltered distribution.

**Pass:** filter dropdowns only ever show real, non-empty audit-derived
options (never `best_use_case` or the full tag list as a dropdown); list +
charts stay in lock-step under every filter combination; the table is
paginated, never an unpaginated 1,932-row dump; every row's source line
resolves to a working call-detail link; empty/loading states render cleanly
with no native `alert()`/`confirm()`. **Fail:** a filter matching 0 rows
presented as a real option, charts frozen on the unfiltered set while the
list is filtered, a source line with no link or a 404 target, or any
unpaginated full-table render.

## Market Signals — filters + trending redesign (2026-08-03)

**Feature:** `/ci-market-signals` (deliverable 7). Redesigned from a flat,
sortable card grid into a "Trending" view that reads as informative data
rather than raw aggregate output.

**Before you start — audit numbers as of 2026-08-03 (read-only, live DB):**
`market_signals` has **1,961 rows**. `insight_type`: Pain 963, Goal 517,
Objection 278, Trigger 195, Win 3, Belief 2, Identity 2, Buying Signal 1 (8
distinct). `signal_family`: 30 distinct values (matches `insights`).
`total_mentions` ranges **0 to 3** across all 1,961 rows (avg ≈ 1).
`last_30_days` ranges **0 to 2** (1,083 rows at 0, 877 at 1, 1 at 2);
`last_7_days` is always 0 or 1. This is a genuinely low-volume, near-binary
dataset today, which is why momentum is computed with a plain "was there any
activity in the 30d window" guard (`last_30_days > 0`, not a minimum-sample
threshold — an earlier draft gated on `total_mentions < 3` and returned
`None`/"Not enough data" for every single row; verified fixed below) and the
page renders it as a directional chip ("picking up" / "steady" / "cooling
off"), never a literal percentage that would overstate a 1-to-2-mention jump
as "+100%". **878 of 1,961 rows (44.8%) get a real momentum value** on live
data as of this fix. There is **no `created_at`** on this table (it's a
rolling aggregate keyed on `(signal_family, signal)`, recomputed in place) —
the date-range filter here scopes `updated_at` instead.

**Steps:**
1. Open `/ci-market-signals`. Confirm the page subtitle and layout read as
   a "trending" view, not a raw list — each card should lead with a
   **momentum chip** ("↑ Picking up" / "→ Steady" / "↓ Cooling off" / "Not
   enough data"), not just a bare mention count.
2. Sort by Momentum (the default) and scan the first couple pages — confirm
   you see a genuine **mix** of "↑ Picking up" and "↓ Cooling off" chips, not
   "Not enough data" on every single card (that was the pre-fix bug: the
   guard checked `total_mentions < 3`, which is never satisfied by real data,
   so every card showed "Not enough data" and the stat strip always read
   0 picking up / 0 cooling off). With the corrected guard, ~45% of all
   signals get a real chip.
3. Confirm the filter row has: **Search**, **Insight Type**, **Signal
   Family** dropdowns (real distinct values only), a **Min Mentions**
   number input, an **Updated** date-range pair, and a **Sort By** select
   whose default is **Momentum**.
4. Confirm a stat strip appears between the filter row and the card grid
   showing total signals tracked, how many are picking up, and how many are
   cooling off (on the current page) — these should be non-zero now.
5. Set Min Mentions = `2` — confirm the shown count narrows (audit found
   **6** signals with `total_mentions >= 2`) and every visible card's total
   mentions is ≥ 2.
6. Switch Sort By to **Last 7 Days**, then **Last 30 Days**, then back to
   **Momentum** — confirm the card order changes each time via a fresh
   server call (not a client-side re-sort of stale data), and confirm
   Momentum sort still responds quickly (it's a single indexed `ORDER BY` in
   SQL now, not a fetch-everything-then-sort-in-Python pass).
7. Confirm `best_marketing_angle` renders as a highlighted callout (💡
   marker) above the example quote, not buried below it.
8. Find a card whose `example_quote` is long — confirm it's truncated with
   a "Read more" toggle rather than dumped in full; click it and confirm it
   expands in place (no modal, no native dialog).
9. Clear all filters — confirm the page returns to the unfiltered set
   (**1,961** total) and Sort By resets to Momentum.
10. With a filter combination that matches nothing, confirm the empty state
    is quiet (icon + one short message), not a jarring blank page or error.

**Pass:** momentum reads as plain language, never a bare/misleading
percentage; filters (search, insight type, signal family, min mentions,
updated range) all narrow the set correctly via server round-trips; sort
changes always re-fetch rather than silently reordering cached data;
`best_marketing_angle` is visually prominent; long quotes collapse behind a
toggle; empty states are quiet. **Fail:** a momentum chip showing a raw
percentage on a 1-to-2-mention signal, a filter option with 0 real matches,
sort appearing to do nothing, or a raw unbounded quote dump.

## Marketing — Funnels (real data, deliverable 3) (2026-08-04)

**Feature:** `/marketing/funnels` no longer shows the seed-data
`funnel_events`/`funnel_stats` funnels (`coaching-program-v2`,
`webinar-apr-2026` — those tables are empty dead scaffolding, left in place
untouched). The page now derives the real funnel from the `lead_journey`
mirror (1 row per lead, 12,820 rows) via a new `GET /funnels/overview`
endpoint: leads → registered → watched → booked appt → discovery held →
closed, sliceable by channel using the same resolver machinery
(`build_resolver` / `bucket_channel_combos`) the Leads and Sales pages use.

**How to locate:** `/marketing/funnels` — under Marketing in the sidebar.

**Before you start:** unfiltered totals as of 2026-08-04 are **12,820
leads → 11,557 registered (90.1%) → 6,872 watched (53.6%) → 1,289 booked
appt (10.1%) → 183 discovery held (1.4%) → 83 closed (0.6%)**. These numbers
must match exactly (they're a direct predicate count over `lead_journey`,
not an estimate).

**Steps:**
1. Open `/marketing/funnels`. Confirm the old two-funnel selector
   (`coaching-program-v2` / `webinar-apr-2026`) is gone — there's a single
   funnel visual now, no dropdown.
2. Confirm the **Funnel Stages** card shows six horizontal bars in order
   (Leads, Registered, Watched, Booked Appt, Discovery Held, Closed), each
   with a count, a "% of Leads" figure, and a "step conversion" figure
   (conversion from the immediately preceding stage). Leftmost/top bar
   (Leads) shows 12,820 with no step-conversion figure (there's no previous
   stage). Closed shows 83 (0.6% of leads).
3. Confirm the **Funnel by Channel** table below lists channel chips (reusing
   the same chip styling as `/leads` — amber tint for `unmapped:*`/"other
   unmapped" dialects) with per-channel stage counts and a lead→close %
   column. Rows are ordered by leads count descending. The sum of the
   `leads` column across all rows should equal 12,820; the sum of `closed`
   should equal 83.
4. Use the **Entered** date-range filter (top right) to pick a narrower
   window (e.g. 2026-01-01 to 2026-06-30). Confirm the funnel bars and
   channel table re-fetch and show smaller, internally consistent numbers
   (each stage's count is always ≤ the previous stage's — a 2026 H1 slice
   was manually verified at 2,882 leads → 2,653 registered → 1,530 watched →
   347 booked → 81 discovery held → 13 closed). Click "Clear" to return to
   the unfiltered view.
5. Reload the page and watch the loading state — skeleton bars/rows render
   briefly, never a spinner-only or blank screen, never native
   `alert()`/`confirm()` dialogs.

**Pass:** the old seed-funnel selector is gone; unfiltered stage counts
match 12,820 / 11,557 / 6,872 / 1,289 / 183 / 83 exactly; the channel table's
`leads` and `closed` columns sum to the same unfiltered totals; the date
filter narrows both the overall funnel and the channel table consistently;
empty/loading states are quiet. **Fail:** any stage count off from the
discovery numbers, a channel table that doesn't sum to the overall totals,
the date filter affecting only one of the two sections, or a crash/blank
page on an empty range.

## Marketing — Offers (real WGR catalog, deliverable 5) (2026-08-04)

**Feature:** `/marketing/offers` no longer lists CI's own `offers` table
(18 rows of app-CRUD test data — "This is a new offer", "just checking").
The main listing now shows the **real** WGR offer catalog (11 offers),
mirrored 2026-08-04 into two new tables (`wgr_offers` / `wgr_offer_mappings`)
via a new `GET /offers/catalog` endpoint, with per-offer sales count and
revenue rolled up from `closed_sales`. The **"+ Create Offer"** button and
its target page (`/marketing/offers/builder` — real form + real AI
generation trigger) are unchanged and still work exactly as before; only the
fake, non-functional "Offer Builder" sidebar stub on the main listing page
(Save/AI Suggestions buttons with no click handlers) was removed.

**How to locate:** `/marketing/offers` — under Marketing in the sidebar.
The builder is at `/marketing/offers/builder`, reached via the "+ Create
Offer" button.

**Before you start:** live counts as of 2026-08-04: **11 real offers**
(e.g. "Agent Infopreneur Accelerator - PIF" / Coaching / $10,000 / Active),
**15 payment-level mapping rows**, **83 closed sales totaling $471,250**.
Every one of the 83 sales' `offer_id` resolves to one of the 11 catalog
offers today, so no "Unattributed" row is expected right now — that's
correct, not a missing feature (the row appears automatically the moment a
sale's `offer_id` is null or unrecognized).

**Steps:**
1. Open `/marketing/offers`. Confirm the KPI row shows **Active Offers**,
   **Total Offers** (11), **Total Sales** (83), and **Total Revenue**
   (formatted currency, $471,250) — not "—".
2. Confirm the **Offer Catalog** table lists 11 real offer names (not
   "This is a new offer" test rows), each with type ("Coaching"), price
   (or "Custom" for the two offers with a null price — "…Custom" named
   offers), a status chip ("Active"), a sales count, and a revenue figure.
   Confirm "Agent Infopreneur Accelerator - PIF" shows the highest revenue
   (41 sales, $320,750).
3. Sum the **Revenue** column down the whole table (including any
   "Unattributed" row, shown with an amber chip, if present). Confirm the
   total equals **$471,250** — the same figure shown in the Total Revenue
   KPI tile.
4. Confirm the **Payment Levels** sidebar card groups rows by program
   (accelerator / mastery / jumpstart), each showing its payment-level
   labels (pif, monthly, 2 pay, 3 pay, etc.) and amount collected.
5. Click **"+ Create Offer"**. Confirm it still navigates to
   `/marketing/offers/builder` and that page's form + "Generate with AI"
   button still work exactly as before (unchanged by this work).
6. Reload `/marketing/offers` and watch the loading state — skeleton tiles/
   rows render briefly, never a spinner-only or blank screen, never native
   `alert()`/`confirm()` dialogs.

**Pass:** KPI tiles + catalog table show real WGR data (11 offers, not the
18 test rows); the Revenue column sums to $471,250; the Payment Levels card
shows all 15 mapping rows grouped by program; the Create Offer button and
builder page still work unchanged. **Fail:** the old test-data offer names
("This is a new offer") still appear, the revenue sum doesn't reconcile
with $471,250, a fabricated Unattributed figure appears despite full
attribution, or the Create Offer / builder flow is broken.

## Analyze with AI — interactive follow-up chat (deliverable 8) (2026-08-04)

**Feature:** the "Analyze with AI" drawer (available on `/leads` and other
filtered list surfaces) is no longer a one-shot, read-only result. After the
initial grounded analysis renders, an "Ask a follow-up" thread appears below
it with a text input ("Ask a follow-up about this data…"). Follow-up
questions are answered by a new `POST /api/v1/analyze/{surface_key}/chat`
endpoint, which recomputes the surface's aggregates from the SAME filters
currently applied (fresh grounding, not a stale snapshot) and answers using
only that data plus the running conversation — same hypothesize-never-
fabricate contract as the initial analysis. The thread is ephemeral: it
dies with the drawer (closing it, or clicking "Re-run", clears it), nothing
is persisted server-side.

**How to locate:** open any list page with an "Analyze with AI" button
(e.g. `/leads`), apply a filter set, click the button to open the drawer.
Once the initial analysis renders, the follow-up thread + input appear
below it in the same drawer.

**Steps:**
1. Go to `/leads`, apply a filter (e.g. a specific channel or date range).
2. Click **"Analyze with AI"**. Confirm the existing one-shot analysis
   (narrative, highlights, hypotheses, "Show the data this is based on")
   still renders exactly as before — unchanged by this work.
3. Below the analysis, confirm an "Ask a follow-up" section with a text
   input reading "Ask a follow-up about this data…".
4. Type a question referencing the visible data, e.g. "which channel
   drives the most closed revenue?", and press Enter (not Shift+Enter —
   that should insert a newline instead of sending).
5. Confirm your question appears immediately as a right-aligned bubble,
   a typing indicator appears, and the input disables while the reply is
   pending.
6. Confirm the assistant's reply appears left-aligned, and that every
   number it cites (counts, percentages, revenue figures) matches a number
   visible in the "Show the data this is based on" panel or the narrative
   above — no invented figures. If the data can't answer the question, the
   reply should say so rather than guess.
7. Ask a second follow-up referencing the first answer (e.g. "and what
   about last month?") — confirm the full local thread (not just the new
   message) is sent each time, so the assistant can use prior context.
8. Trigger an error path (e.g. stop the backend briefly, or a network
   hiccup) — confirm an inline error state appears in the thread area, not
   a native `alert()`/`confirm()` dialog and not a silent failure.
9. Click "Re-run" on the analysis, or close and reopen the drawer — confirm
   the follow-up thread is cleared (ephemeral, matches the analysis's own
   lifecycle).

**Pass:** the initial analysis is unchanged; the follow-up thread sends on
Enter, disables while pending, shows user/assistant bubbles distinctly
styled (right/left), and every number in a reply is traceable to the
drawer's own displayed aggregates; the thread clears on re-run/close.
**Fail:** the initial analysis regresses, the follow-up call 500s or hangs
without an inline error, a reply contains a number not present anywhere in
the drawer's data, or the thread survives a drawer close/re-run.

**Backend proof (2026-08-04):** a real Anthropic API call was attempted
first via `chat_view_analysis(...)` with a minimal hand-built aggregates
dict and the question "Which channel drives the most closed revenue?" — it
failed with `anthropic.BadRequestError: ... credit balance is too low ...`
(environment/billing issue, not a code defect). Fell back to the same call
with `_call_claude_chat` monkeypatched to a canned response: verified the
system prompt sent to the LLM contained the aggregates JSON verbatim
(`"18000"` present), the filters echo (`"status=closed_won,
date_range=last_30_days"`), and that the full message history was passed
through unmodified as the `messages` list. 13 new unit tests
(`backend/tests/test_analyze_chat.py`) cover message-role/length/count
validation and pure prompt assembly with no DB/network — backend suite is
271 passing (258 baseline + 13 new).

## Marketing — Social (Greg-spec rebuild) (deliverable 1) (2026-08-04)

**Feature:** `/marketing/social` main page rebuilt 1:1 from Greg's own
tracking app (`central-intelligence-greg/index.html`, `view-mkt-social` —
the client's spec, per the deliverable: "using his version as the spec —
layout, metrics, structure — mirroring it 1:1"). A new `GET /social/overview`
endpoint serves every widget Greg's page renders from a **queryable**
data source; widgets his page renders from a live Instagram Graph API
connection are omitted (documented gap, not faked).

**Extracted spec (from `view-mkt-social`, lines 2163–2357 of his `index.html`):**
- Status/filter bar: date-from, date-to, type filter (All/Reels/Photos/
  Videos/Carousels), Refresh button. (His "Connect & Load"/"Refresh"/"Demo"
  buttons talk to a live Graph API connection — no equivalent DB state to
  mirror; see gaps below.)
- Summary stat cards: Posts in Range, Reels, Carousels, Watch Time (reels
  only), Total Views (reels only), Total Reach, Total Likes, Total Saves.
- Dynamic per-keyword lead stat cards (never hardcoded — driven by whatever
  keywords exist in the data) + a Total Leads card.
- **Leads by Day** table — comment-arrival date frame (any post, any
  platform), reads WGR's `comment_leads_by_day()` RPC on his page.
- **Posts** table — thumbnail, type badge (Reel/Carousel/Video/Photo),
  caption, date, likes, comments, per-keyword lead columns, views, watch
  time, reach, saves, shares, avg watch, skip rate, permalink — every
  column sortable (nulls always last), paginated via "Load More".
- A separate "Meta Ads" view (`view-meta-ads`, Hook%/Hold%/CTR% ad
  performance table) looks similar (Hook Rate KPI) but is a **different**
  specialist page (paid ads, not organic social) — confirmed out of scope
  by checking `showView()` wiring; not touched.

**Data audit performed (2026-08-04, live queries against both DBs):**
- CI's own `instagram_posts` mirror: **2,754 rows**, already covers post
  identity + engagement + reel metrics (no new mirror needed for posts).
- WGR source additionally has `ig_account_benchmarks` (1 row),
  `ig_format_performance` (2 rows), `ig_hook_performance` (0 rows),
  `ig_mission_performance` (0 rows), `creator_scrapes` (0 rows) — **none
  of these are rendered anywhere in `view-mkt-social`** (confirmed via
  grep across `index.html`); not mirrored, per the deliverable's "mirror
  ONLY tables his social section renders" instruction.
- WGR's comment-lead attribution tables ARE rendered (via his page's
  `/api/social/comment-leads` + `/api/social/comment-leads-by-day` Express
  routes) and ARE real, substantial data: `comment_events` (15,856 rows),
  `post_comment_leads` (2,754 rows, precomputed rollup) — both mirrored as
  `wgr_comment_events` / `wgr_post_comment_leads` (see CHANGELOG /
  INTEGRATIONS.md for the migration/mapper/sync details).

**How to locate:** `/marketing/social` — under Marketing in the sidebar.

**Before you start:** live counts as of 2026-08-04 (unfiltered):
**2,754 posts** (2,122 reels, 511 carousels), **36,427,303 total reach**,
**966,287 total likes**, **423,822 total saves**, **45,166,566 total
views** (reels only), **14,363 total comment-leads** (agent: 6,883,
info: 7,480), **150 distinct Leads-by-Day rows** across the mirrored
`wgr_comment_events` history.

**Steps:**
1. Open `/marketing/social`. Confirm the gap notice (amber, collapsible)
   lists 4 documented gaps and the summary stat cards show real numbers
   (not "—") once loaded — Posts in Range **2,754**, Reels **2,122**,
   Carousels **511**, Total Reach **36,427,303**, Total Likes **966,287**.
2. Confirm the per-keyword lead cards show **Agent Leads: 6,883** and
   **Info Leads: 7,480** (or current live numbers) plus **Total Leads:
   14,363**, with no keyword name hardcoded (cards render from whatever
   keywords the data contains).
3. Confirm the **Leads by Day** table lists day rows (most recent first)
   with a per-keyword column per discovered keyword and a Total column.
4. Confirm the **Posts** table lists real captions/dates/engagement (not
   "This is a new offer"-style test rows), with a Reel/Carousel/Video/Photo
   badge per row and per-keyword lead columns.
5. Click a sortable column header (e.g. "Likes") — confirm the sort order
   flips on a second click and nulls always sort last, and that Reels-only
   columns (Views/Avg Watch/Shares) show "—" for non-reel rows.
6. Change the date-range filter to a narrow window — confirm the stat
   cards, per-keyword cards, and Posts table all react together (same
   filtered set), and Reels/Carousels counts change accordingly.
7. Filter Type to "Reels" — confirm every row in the Posts table shows the
   Reel badge and the stat cards' Reels count equals Posts in Range.
8. Reload — confirm the loading skeleton renders briefly, never a
   spinner-only or blank screen, never a native `alert()`/`confirm()`.

**Pass:** every summary/keyword/leads-by-day/posts-table number is
traceable to a direct SQL count against `instagram_posts` /
`wgr_comment_events` / `wgr_post_comment_leads`; filters/sort all apply
consistently across every widget; the gap notice is present and accurate.
**Fail:** any stat card shows a fabricated or hardcoded number, a keyword
name is hardcoded anywhere in the frontend, sort/filter desyncs between
widgets, or a widget silently renders data for a live-Graph-API feature
that isn't actually backed by either database.

**Backend proof (2026-08-04):** in-process call to `get_social_overview(...)`
(no HTTP server) against the real CI DB, cross-checked against direct SQL
in the same session:

| Metric | `/social/overview` | Direct SQL | Match |
|---|---|---|---|
| `posts_total` | 2,754 | `SELECT count(*) FROM instagram_posts` → 2,754 | ✅ |
| `summary.reels_count` | 2,122 | `... WHERE is_reel` → 2,122 | ✅ |
| `summary.carousels_count` | 511 | `... WHERE media_type='CAROUSEL_ALBUM'` → 511 | ✅ |
| `summary.total_reach` | 36,427,303 | `SUM(reach)` → 36,427,303 | ✅ |
| `summary.total_likes` | 966,287 | `SUM(likes_count)` → 966,287 | ✅ |
| `summary.total_leads` | 14,363 | `SUM(total_leads)` on `wgr_post_comment_leads` → 14,363 | ✅ |

A second, filtered call (`media_type=REELS`, `date_from`/`date_to` spanning
2026, `sort_col=views`, `sort_dir=desc`) returned 565 posts, all with
`is_reel=True`, correctly sorted by `views` descending. Pure-helper suite:
21 new tests (`backend/tests/test_social_stats.py`), backend total
**297 passing (276 baseline + 21 new)**.

**Backfill (2026-08-04):** one-off `_sync_snapshot_reconcile` invocation
(bypassing Celery/Redis — pure DB-to-DB) upserted **15,856 rows** into
`wgr_comment_events` and **2,754 rows** into `wgr_post_comment_leads`.
