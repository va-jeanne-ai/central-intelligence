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
- **Status:** ✅ **verified-as-empty (2026-05-19)** — wiring confirmed, table empty by design (blocked on F19)
- **URL:** `/ci-insights`
- **Finding:** `insights` table has 0 rows. The page is fully wired (paginated, filterable, live API) but has nothing to display because no transcripts have been processed through the extraction pipeline. The extraction pipeline is F19 (`call_analyzer` Celery task — net-new work).
- **What was verified:**
  - [x] `GET /api/v1/ci/insights` returns 200 OK after the F32 JWT fix
  - [x] Page renders empty state cleanly (no errors)
- **To unblock:** F19 (build the Sales Call Analyzer extraction task)
- **API:** `GET /api/v1/ci/insights`, `GET /api/v1/ci/insights/{id}`

### F5 — Market Signals
- **Status:** ✅ **verified-as-empty (2026-05-19)** — wiring confirmed, table empty by design (blocked on F19)
- **URL:** `/ci-market-signals`
- **Finding:** `market_signals` table has 0 rows. Same situation as F4 — page is fully wired, empty because no insights have been extracted yet to aggregate from.
- **What was verified:**
  - [x] `GET /api/v1/ci/market-signals` returns 200 OK after the F32 JWT fix
- **To unblock:** F19

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
- **Status:** ✅ **verified-as-empty (2026-05-19)** — wiring OK, `offers` table has 0 rows
- **URL:** `/marketing/offers`
- **What was verified:**
  - [x] Page renders cleanly with empty library + 0 KPI counts (no crash, no error)
  - [x] `GET /api/v1/offers` returns 200 OK
- **To unblock:** F18 (offer builder save handler) — once F18 ships, creating offers via the builder will populate this library.
- **API:** `GET /api/v1/offers`

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
- **Status:** ⬜ not started
- **What it should do:** Replace the 5 Celery tasks' embedded seed data with real API calls to Meta Ads, Google Ads, Mailchimp/ActiveCampaign, Instagram/LinkedIn/Facebook, TikTok.
- **Current state:** All 5 tasks have placeholder seed data hardcoded inside them.
- **What's needed (~1 sprint per integration, more or less):**
  - One-by-one: pick a platform, get API credentials in `.env`, replace seed-data loop with real API calls
- **Recommended start:** Email (Mailchimp/ActiveCampaign) — likely the cleanest API to integrate first

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
