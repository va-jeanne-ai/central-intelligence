# Changelog

All notable changes to the Central Intelligence project will be documented in this file.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added — CI chat resumes your last conversation on reload

Chat history was already persisted (DB-backed `chat_sessions`/`chat_messages` + a history sidebar; the agent re-hydrates full context on session resume), but the frontend minted a fresh session UUID on every mount — so a page reload dropped you onto a blank "New chat" and you had to re-pick the conversation from the sidebar.

- `frontend/src/hooks/use-chat.ts` — the active `sessionId` is now mirrored to `localStorage` (`ci-chat-session-id`) on every change and restored on mount, so a reload reconnects the WebSocket to the same session (backend re-hydrates the agent's memory). A one-time mount effect re-fetches that session's transcript so the on-screen bubbles reappear too. Guards: only restores when the id came from storage (a true first visit still starts blank, no needless fetch), degrades silently if the stored session was deleted server-side, and doesn't interfere with `startNewChat`/`loadSession`.

No backend changes — the persistence layer was already complete.

### Added — Connect buttons on the /marketing/social Platform Breakdown

Each platform row now reflects real connection state. Connected platforms show live metrics; an **unconnected** platform that has a connect form shows a **Connect →** button linking to `/integrations/{slug}`; platforms not yet wired (TikTok, LinkedIn) show a muted **Coming soon** tag instead of a dead button.

- `app/schemas/social.py` + `app/routes/social.py` — `SocialPlatformMetric` gains `connected` (from the `integrations` table, not merely a seed `social_stats` row) + `provider_status` (registry available/coming_soon); metric fields are now nullable and only populated when connected. The endpoint returns a row for all four display platforms.
- `frontend/.../marketing/social/page.tsx` — the breakdown card renders three states per row: connected → metrics; available + not connected → Connect button; coming_soon → disabled tag.

### Fixed — /marketing/social Platform Breakdown shows live per-platform data

The "Platform Breakdown" card rendered a **hardcoded** `PLATFORMS` array of `"—"` literals and never read any data — so Facebook (and every platform) always showed "—" no matter what synced. The `/social` endpoint also only returned summed totals, with no per-platform rows.

- `app/schemas/social.py` + `app/routes/social.py` — `SocialDataResponse` gains a `by_platform` list of `SocialPlatformMetric` (platform, followers, posts_count, engagement_rate); the GET handler populates it via `repo.find_latest_by_platform` for instagram/facebook/tiktok/linkedin (omitting platforms with no row).
- `frontend/.../marketing/social/page.tsx` — `PlatformMetricsCard` now takes `data` and merges live `by_platform` values onto the display scaffold (icons + order), formatting followers/posts/engagement; falls back to "—" only when a platform has no synced row. The top KPI tiles were already live; this fixes the per-platform breakdown beneath them.

### Fixed — Logout works (and stale sessions no longer strand you on the dashboard)

Clicking sign-out did nothing when the session was already invalid (expired JWT / missing user). `signOut` `await`ed `supabase.auth.signOut()` *before* clearing local state, so when that call threw/hung on an invalid session, execution never reached the token-clear + `setUser(null)` + redirect — the button silently no-op'd.

- `frontend/src/contexts/auth-context.tsx` — wrapped the Supabase sign-out in try/catch; local cleanup (clear token, clear cached user, null the user) + `router.push("/login")` now always run, so logout succeeds regardless of server-side session state.
- `frontend/src/components/layout/auth-guard.tsx` (new) + `frontend/src/app/(app)/layout.tsx` — added a client-side `AuthGuard` that redirects to `/login` once auth finishes loading and the user is null. The Next middleware only guards on navigation; this catches a session going invalid while you're already sitting on a protected page (the "stuck on dashboard" symptom).

### Fixed — Facebook Page Insights metric churn handled gracefully

Meta is deprecating the bare `page_impressions` Page-insights metric through mid-2026 (it now returns `(#100) The value must be a valid insights metric`). `facebook_client.fetch_facebook_stats` now tries `page_impressions_unique` then `page_impressions`, uses whichever the API accepts, and logs Meta's actual error message (via a new `_error_message` helper, also used by `verify()`) instead of a raw traceback. Insights stay best-effort — followers/posts still sync when the impressions metric is rejected or absent (e.g. a low-activity Page returns no insights). `reach` remains null (no comparable Page metric).

### Fixed — Social credential loaders read the account ID from `config`, not the blob

The Instagram/Facebook sync reported "credentials unusable" even with a valid token saved, because the save route stores the **secret** field (`access_token`) in the encrypted blob but the **non-secret** ID field (`ig_user_id` / `page_id`) in the `config` JSONB column — and the loaders only read both from the blob. `load_instagram_credentials` / `load_facebook_credentials` now read the token from the decrypted blob and the ID from `integration.config` (with a blob fallback for older rows). With this fix, a saved Facebook Page token syncs live.

### Added — Manual "Sync now" button for social + email connectors

The on-demand sync button on the integration detail page (previously GHL-only) now renders for every connector with a backing sync task — **Mailchimp, Instagram, Facebook**, and GHL. The backend `POST /integrations/{slug}/sync` was already generic (routes through `_trigger_sync`); this just surfaces the button with per-provider labels ("Sync metrics now" / "Sync campaigns now" / "Sync contacts now"). Lets an admin pull fresh data immediately after saving credentials instead of waiting for the next beat tick.

- `frontend/.../integrations/[slug]/page.tsx` — `SYNCABLE_SLUGS` set + `SYNC_BUTTON_LABEL` map drive the button's visibility/label; removed the `slug === "ghl"` gate.

### Added — Facebook Page integration (Meta Graph API)

Makes the `/marketing/social` **Facebook** column live, mirroring the Instagram connector. Manual long-lived **Page** token + Page ID; no migration. Unlike Instagram, Facebook needs no account-type conversion — any Page admin can read Page insights.

- `app/services/facebook_client.py` (new) — Graph API v19 wrapper: Page profile (`followers_count`/`fan_count`, `name`), Page Insights (`page_impressions` over `days_28`, summed across the window), and recent `/posts` (likes+comments summary) for an engagement-rate estimate. Profile required; insights + posts best-effort. `reach` left null (no Page metric comparable to IG reach). `verify()` powers the Test button.
- `app/services/facebook_credentials.py` (new) — decrypts `(access_token, page_id)` from the integration blob (mirrors `instagram_credentials.py`).
- `app/tasks/social_stats.py` — refactored the per-platform live sync into a generic `_sync_live_platform(db, platform, …)` driven by a `_LIVE_PLATFORMS` map `{instagram, facebook}` (each → its creds-loader + fetch fn). Facebook syncs live when connected, **skips** (no fake-data overwrite) when not connected or on error, stamping `last_sync_status`/`last_sync_error` + a `sync_log` row. Removed `facebook` from `_SEED_DATA` (linkedin/tiktok stay seeded). The task result dict now reports per-platform sync results.
- `app/services/integrations_registry.py` — new `facebook` provider (icon 📘, category social, `available`, fields `access_token` + `page_id`, `trigger_task: "facebook"`).
- `app/routes/integrations.py` — `_trigger_sync` enqueues the shared `update_social_stats` for both `instagram`/`facebook`; `test_integration` facebook branch calls `facebook_client.verify()`.
- `frontend/.../integrations/[slug]/page.tsx` — `FacebookSetupStepsCard`: collapsible steps for getting a long-lived Page token (Graph API Explorer → select Page → token-exchange) and the Page ID (`/me/accounts`).

No `/marketing/social` change — it already renders a Facebook row; it lights up once a sync writes real data. Verified structurally with zero API cost (registry/fields, creds-None-on-empty, engagement-rate math, insight-value summing, `verify()` not-connected message, task syncs both live platforms + skips gracefully with no rows). Live Graph test needs a user-provided long-lived Page token + Page ID.

### Added — Instagram social integration (Meta Graph API)

Makes the `/marketing/social` Instagram column **live**. Previously `update_social_stats` wrote hardcoded seed data for all platforms; now Instagram pulls real organic metrics from the Meta Graph API. Manual-token connector following the GHL/Mailchimp pattern — no migration (the `integrations` table already has every column needed).

- `app/services/integrations_registry.py` — Instagram flipped `coming_soon` → `available` with two fields (`access_token` secret, `ig_user_id`) and `trigger_task: "instagram"`. This is what makes the card clickable on `/integrations` and renders the connect form at `/integrations/instagram`.
- `app/services/instagram_client.py` (new) — Graph API v19 httpx wrapper: profile (`followers_count`, `media_count`), account insights (`reach`/`impressions`, `days_28`), recent-media engagement-rate estimate. Insights + media are best-effort; profile is required. `verify()` powers the Test button; `is_configured()`/`_resolve_creds()` read the DB.
- `app/services/instagram_credentials.py` (new) — decrypts `(access_token, ig_user_id)` from the integration blob (mirrors `ghl_credentials.py`); returns None on any failure.
- `app/tasks/social_stats.py` — `update_social_stats` syncs Instagram live when connected; **skips** it (no fake-data overwrite) when not connected or on error, stamping `last_sync_status`/`last_sync_error` + a `sync_log` row. facebook/linkedin/tiktok stay on seed values (clearly marked) so the dashboard stays populated.
- `app/routes/integrations.py` — `_trigger_sync("instagram")` enqueues `update_social_stats` (Sync button); `test_integration` instagram branch calls `instagram_client.verify()`.
- `INTEGRATIONS.md` — Instagram entry rewritten from ⬜ to ✅.

No frontend change to `/marketing/social` — it renders from the DB and lights up once credentials are saved and a sync runs. The `/integrations/instagram` detail page has a collapsible **Setup steps** panel walking through getting a long-lived access token (Graph API Explorer → token-exchange endpoint) and the IG Business account ID (`/me/accounts` → `instagram_business_account`). Verified structurally with zero API cost (registry/fields, creds-None-on-empty, engagement-rate math, `verify()` not-connected message, task skips IG gracefully with no row). Live Graph API test requires a user-provided Meta long-lived token + IG account ID (the user's token, not app-key spend).

> **Deferred:** a "Connect with Meta" OAuth button (single shared business account, long-lived-token auto-refresh) was built and then removed in favor of shipping the manual-token connector first. The implementation lives in git history (branch `feat/instagram-social-integration`, commits `1566abc`/`65b6e1b`/`22c36af`) for a future sprint.

### Added — Central Intelligence cross-department delegation (Sprint 8)

Connects the top-level Central Intelligence chat agent to the three department Directors so it can finally answer cross-department questions ("what should we focus on this week?") with real Sales/Marketing/Fulfillment intelligence. Previously CI's only tools were `query_database`/`search_knowledge_base`/`query_calendar`, and its prompt admitted Directors weren't connected.

**Strict hierarchy (deliberate invariant):** delegation flows strictly **down** — CI → Director → specialists. CI is the *only* cross-department agent; **Directors never delegate to each other** (enforced by omission — no peer-delegate tools are added to any Director, verified in tests). Specialists stay department-scoped.

#### Backend
- `app/agents/central_intelligence.py` — three new delegate tools: `delegate_to_marketing_director`, `delegate_to_sales_director`, `delegate_to_fulfillment_director` (CI now registers 6 tools). Each handler opens a **fresh `AsyncSessionLocal()`**, builds the Director on the spot, runs `director.execute(task)`, and returns its prose. Directors must be built per-call because CI is a long-lived per-session object while DB sessions are per-request — a Director held at `__init__` would carry a stale, closed session. Handlers are error-resilient (return a short JSON error string instead of crashing the CI tool loop).
- `app/prompts/central_intelligence_v1.py` — removed the false "Directors are not yet connected" limitation; added a **Delegating to Directors** section: a routing table (which Director per topic), scoped-vs-broad guidance (one Director for a scoped question; all three + synthesize for strategy), and a cross-department optimization framework (leads not being worked, fulfillment at capacity → pause sales, recurring call pain → content angle, member wins → proof). Existing secrecy guardrails retained (never name a Director/specialist/tool; present as one CEO synthesis).
- `app/routes/dashboard.py` + `app/schemas/dashboard.py` — `GET /dashboard/weekly-focus`: runs CI once with a fixed "what should we focus on this week?" prompt (asks for strict JSON), returns `{focus:[{title,detail}], summary, generated_at, cached}`. **Cached 15 min** because each run fans out to all three Directors (several chained model calls), and falls back to deterministic priorities (from the recommendation-metrics queries) when no API key is configured or the CI run fails. JSON extraction tolerates stray prose/fences.

#### Frontend
- `frontend/src/components/dashboard/weekly-focus.tsx` — new "This Week's Focus" panel (indigo CI accent matching `CIWidget`): fetches `/dashboard/weekly-focus` with the `apiClient.get(..., {silent:true})` + `authLoading` pattern, renders the synthesized summary + numbered priority list, with skeleton and graceful empty state.
- `frontend/src/app/(app)/dashboard/page.tsx` — renders `WeeklyFocus` as a full-width row above the existing snapshot/recommendations row; added a matching skeleton bar.

No migration, no new agent classes, no Director changes. Real-AI path (CI → 3 Directors → specialists) incurs app-key spend and is gated behind the 15-min cache; verified structurally with zero API cost (6-tool registration, Director isolation, deterministic weekly-focus fallback, tolerant JSON parse).

### Added — Market Signals aggregation job

Fills the missing engine for `market_signals` (handover §3.6): the table, read API, and UI surfaces existed, but nothing ever populated it from `insights`. Now a scheduled job recomputes it so the trend dashboards (`/ci-market-signals`, the Marketing Director's `get_market_signals` tool, `/marketing/summary`) show live data.

- `app/tasks/market_signals.py` — `update_market_signals` Celery task. Recomputes (not increments) from `insights` grouped by `(signal_family, signal)`: `total_mentions` + rolling `last_30_days`/`last_7_days` (windows must decay, so a full recompute each run), most-frequent `insight_type`, and the newest `raw_quote`/`call_id` as the example. Single `INSERT ... ON CONFLICT` upsert that **preserves the human-curated `best_marketing_angle`/`notes`**. Idempotent; no-ops cleanly on empty insights (never wipes the table).
- `app/models/intelligence.py` + migration `c4049d9dcf4c` — unique constraint `uq_market_signals_family_signal` on `(signal_family, signal)` (the aggregation key for `ON CONFLICT`).
- `app/tasks/celery_app.py` — task added to the worker include list + a `market-signals-hourly` beat entry (recompute hourly at :35).
- `app/routes/ci.py` — `POST /ci/market-signals/refresh` enqueues the job on demand (mirrors the GHL sync button).

No frontend change — the existing read surfaces light up once the job populates the table. Zero API cost (pure SQL aggregation).

### Added — Tech SOS (Fulfillment support tickets, F04)

Wires the last unbuilt Fulfillment sidebar link (`/tech-sos`) to a member support-ticket tracker. Greenfield (new table). AI categorization deferred (F04-2) — category is staff-set for now.

#### Backend
- `app/models/operational.py` — new `SupportTicket` model (`support_tickets` table): nullable `member_id` (SET NULL), contact snapshot, subject/description, category (login/billing/video/portal/access/other), status (open/in_progress/resolved/closed), priority, resolution, resolved_at, source ('staff'|'submit'). Migration `5310f9ce275a` (hand-trimmed).
- `app/repositories/tech_sos_stats.py` — `compute_ticket_stats` (KPIs incl. avg resolution hours, category + status breakdown, 8-week volume) + `get_open_tickets`.
- `app/schemas/tech_sos.py` + `app/routes/tech_sos.py` — `GET /tech-sos` (filters status/category/member/search), `/tech-sos/stats`, detail, history, `POST /tech-sos` (staff create), **`POST /tech-sos/submit` (public, unauthenticated — best-effort member link by email)**, `PATCH` (status→resolved stamps resolved_at; reopen clears; audited), `DELETE` (soft-delete).
- `app/main.py` mounts the router; `app/middleware/auth.py` exempts `/api/v1/tech-sos` (makes /submit public).
- `app/agents/specialists/members.py` — `get_tech_sos` read tool; `app/routes/fulfillment.py` — additive `tech_sos` block in `/fulfillment/summary` (member KPIs unchanged).

#### Frontend (Fulfillment orange #F97316)
- `components/tech-sos/ticket-modal.tsx` — shared create/edit modal (member dropdown on create; member-locked variant; edit fetches full ticket so description/resolution aren't blanked).
- `(app)/tech-sos/page.tsx` — admin page: KPI cards (open/in-progress/resolved/avg-resolution), patterns dashboard (category + status bars), ticket table (member link, category, status/priority badges) with Manage/Delete + filters + New Ticket.
- `(app)/members/[member_id]/page.tsx` — Tech SOS card (member's tickets + New + Manage).

#### Notes
- The public `POST /tech-sos/submit` is open (no token) for v1 — a rate-limit / submit-token guard is a sensible follow-up before exposing it on a real member form.
- AI categorization (auto-category + suggested resolution + pattern detection) deferred; the model has the fields for it.

### Added — Goals kanban board (Accountability)

A Table / Board view toggle on `/accountability` with drag-and-drop across kanban stages.

- `goals.stage` column (todo/in_progress/blocked/done) + migration (`cd767c18679b`). **Independent of `status`** (active/completed/abandoned) — orthogonal workflow dimension; `compute_goal_stats` (KPIs/funnel) stays status-based.
- `app/schemas/goals.py` + `app/routes/goals.py` thread `stage` through list/detail/create (defaults `todo`)/PATCH (audited `goal.stage_changed`); new `GET /goals?stage=` filter.
- `components/goals/goal-board.tsx` — dnd-kit board (4 columns; cards show member/goal/status/overdue/target). Dragging a card optimistically moves it then `PATCH /goals/{id}` with the new stage; reverts on error.
- `(app)/accountability/page.tsx` — Table/Board toggle (persisted to localStorage); same KPIs/funnel/filters apply to both. Added `@dnd-kit/core` + `@dnd-kit/utilities`.

### Added — Accountability (Goal tracking)

Wires the dead `/accountability` sidebar link to a goal-tracking dashboard (Sprint 6 F03). Built on the existing `Goal` model — no migration. Goals also still arrive via the CI insight-sync bridge (`insight_type='Goal'`); manual CRUD is additive.

#### Backend
- `app/repositories/goal_stats.py` — `compute_goal_stats()`: KPIs (total, in_progress, completed, overdue), 3-stage goal funnel (matches the fulfillment dashboard), status breakdown. Member-scoped.
- `app/schemas/goals.py` + `app/routes/goals.py` — goals CRUD: `GET /goals` (filters: member_id/status/overdue/search), `GET /goals/stats`, `GET /goals/{id}`, `GET /goals/{id}/history`, `POST /goals` (create for a member, `goal.created` audit), `PATCH /goals/{id}` (per-field audit incl. `goal.status_changed`; complete = status='completed'), `DELETE /goals/{id}` (soft-delete, `goal.deleted` audit).
- `app/main.py` mounts `goals_router`; `app/middleware/auth.py` exempts `/api/v1/goals`.
- `app/agents/specialists/members.py` — `get_goal_progress` read tool (funnel + overdue across members).

#### Frontend (Fulfillment orange #F97316)
- `components/goals/goal-modal.tsx` — shared Add/Edit Goal modal (member locked in member-detail context).
- `(app)/accountability/page.tsx` — dashboard: KPI cards (Total/In Progress/Completed/Overdue), goal-funnel bars, goals table (member link, status badge + overdue flag, target date) with Complete/Edit/Delete row actions, status + overdue + search filters, Add Goal.
- `(app)/members/[member_id]/page.tsx` — Goals section gained Add + per-goal Complete/Edit/Delete.

### Added — Coaching Calls (Fulfillment)

Wires the dead `/coaching-calls` sidebar link to a real page. Coaching calls are `calls` rows with `call_type='Coaching'` — same VOC pipeline as sales calls (transcript → insights incl. wins → content ideas), analyzed by the coaching-tuned analyzer built in Sprint 6a-lite. Mostly a themed frontend mirror of `/sales-calls` plus member-linking on upload.

#### Backend
- `app/routes/transcribe.py` — `POST /transcribe/upload` now accepts a `memberId` form field (validated UUID + existence check, mirroring `leadId`), so file-uploaded coaching calls attach to a member.
- `app/routes/ci.py` + `app/schemas/ci.py` — `POST /ci/transcripts/upload` (base64 transcript path) now accepts optional `lead_id`/`member_id` and sets them on the Call (previously it linked neither).

#### Frontend (Fulfillment orange #F97316)
- `components/upload/transcript-upload-widget.tsx` — new optional `memberId` prop, threaded into all three submit paths (multipart `/transcribe/upload`, URL `/transcribe`, base64 `/ci/transcripts/upload`).
- `(app)/coaching-calls/page.tsx` — list page mirroring `/sales-calls`: upload widget (callType=Coaching), table of analyzed coaching calls (`GET /ci/calls?call_type=Coaching`), download transcript.
- `(app)/coaching-calls/[call_id]/page.tsx` — orange-themed detail page (copy of the call-type-agnostic sales detail): summary + insights (inline edit) + content ideas + transcript + re-analyze.
- `(app)/members/[member_id]/page.tsx` — member call rows now link to `/coaching-calls/{id}` (coaching) or `/sales-calls/{id}` (else).
- Sidebar/header already routed `/coaching-calls` → Fulfillment Director (no change).

### Added — Sprint 5 S01: Appointments

Makes appointments a first-class entity (previously only a lead status / funnel proxy). Fed by an inbound GHL appointment webhook + manual entry. Outbound nightly GHL appointment pull is deferred (GHL calendar-API access unverified).

#### Backend — Model + migration
- `app/models/operational.py` — new `Appointment` model (`appointments` table): nullable `lead_id`/`member_id` FKs (SET NULL), contact snapshot (name/email/phone), `status` (booked/confirmed/showed/no-show/cancelled/rescheduled), `appointment_type`, `scheduled_at`/`end_at`, `source` ('ghl'|'manual'), `external_id` (GHL appt id — dedup key), `notes`. Registered in `models/__init__.py`.
- `alembic/versions/ca825332c707_add_appointments_table.py` — creates `appointments` + 6 indexes only (hand-trimmed autogenerate drift).

#### Backend — Inbound GHL webhook
- `app/services/ghl_upsert.py` — `upsert_ghl_appointment()` + `GHL_APPT_FIELD_VARIANTS` + `_GHL_APPT_STATUS_MAP` + tolerant datetime parse (ISO + epoch-ms). Dedup on `(source='ghl', external_id)`; best-effort link to a lead (external_id then email) and member (email). Refactored `_pick` → generic `_pick_from`. INSERT → `appointment.created`; UPDATE → `appointment.status_changed`/`rescheduled` only on real change (so book→reschedule→cancel reads cleanly).
- `app/routes/webhooks.py` — new `POST /webhooks/ghl/{webhook_token}/appointments` (LIVE), mirroring the lead webhook's constant-time token validation. Extracted shared `_resolve_ghl_integration` helper.

#### Backend — Stats, CRUD, surfaces
- `app/repositories/appointment_stats.py` — `compute_appointment_stats()` (KPIs: total, upcoming_this_week, show_rate, no_show_rate; 8-week volume; status breakdown) + `get_upcoming_appointments()`.
- `app/schemas/appointments.py` + `app/routes/appointments.py` — `GET /appointments` (filters: status/search/window/date), `GET /appointments/stats`, `GET /appointments/{id}`, `GET /appointments/{id}/history`, `POST /appointments` (manual booking), `PATCH /appointments/{id}` (per-field audit incl. rescheduled), `DELETE /appointments/{id}` (soft-cancel → status='cancelled', row stays visible).
- `app/routes/leads.py` — `GET /leads/{id}/appointments` for the lead-detail card.
- `app/routes/sales.py` — `/sales/summary` gains an additive `appointments` block (real booked counts). The funnel's "Appointments" stage is unchanged (still the lead-status proxy) — `/leads/stats` shape preserved.
- `app/agents/specialists/leads.py` — `get_appointments` tool so the Sales Director (via leads_analyst) can answer "what's booked this week?".
- `app/main.py` mounts `appointments_router`; `app/middleware/auth.py` exempts `/api/v1/appointments` (matches /leads, /members).

#### Frontend (Sales blue #3B82F6)
- `(app)/appointments/page.tsx` — directory: KPI cards (Total, Upcoming, Show Rate, No-Show Rate), table (contact → /leads/{id} when linked, scheduled time, status badge, type), status + window + search filters, "Book Appointment" modal (manual create).
- `(app)/leads/[lead_id]/page.tsx` — Appointments card (fetches `/leads/{id}/appointments`).

#### Notes
- Lead/member linking is best-effort; a webhook for an unknown contact lands with null FKs and renders via the contact snapshot (won't retro-link if the lead arrives later).
- Outbound nightly GHL appointment pull remains the one deferred GHL roadmap item.

### Added — Sprint 6a-lite: Fulfillment Department core (Fulfillment Director + Members/Coaching specialists)

Adds the Fulfillment Director coordination layer (post-sale: members, goals, wins, coaching intelligence) on top of the existing Member/Goal/Win/Call data layer. Deferred to Sprint 6b: Accountability specialist, Tech SOS (greenfield model), and the CI integrations (ActiveCampaign, Fireflies, content-calendar). Lead→Member conversion also deferred.

#### Backend — New model + migration
- `app/models/operational.py` — new `MemberNote` model (`member_notes` table), mirroring `LeadNote`; added `Member.staff_notes` relationship. Registered in `app/models/__init__.py`.
- `alembic/versions/6802177b2e45_add_member_notes_table.py` — creates `member_notes` only (hand-trimmed: autogenerate drift that would have dropped ~13 unrelated indexes was removed).

#### Backend — Shared aggregation
- `app/repositories/fulfillment_stats.py` — `compute_member_stats()` (member KPIs, 8-week enrollment volume, status breakdown, goal funnel) and `get_recent_wins()`. Reuses `get_top_pain_points`/`get_recent_insights` from `sales_stats.py`.

#### Backend — Coaching analyzer (wins-first)
- `app/prompts/coaching_analyzer_v1.py` — `COACHING_ANALYZER_SYSTEM_PROMPT_V1` (+ `build_coaching_user_prompt`, `MOCK_COACHING_ANALYZER_OUTPUT`). Same 22-field Insight schema as the sales analyzer but reframed for coaching: wins as first-class, coaching signal families, pain = blocks-to-progress.
- `app/tasks/call_analyzer.py` — `_call_claude` now routes by call_type: `coaching` → coaching prompt, everything else → the existing sales prompt (regression-safe). Coaching calls already flow through `analyze_call` with `member_id` attached.

#### Backend — Agents
- `app/agents/specialists/members.py` — `MembersSpecialist` (`fulfillment_members`): read-only tools `get_member_stats`, `get_member_list`, `get_member_goals`.
- `app/agents/specialists/coaching.py` — `CoachingSpecialist` (`fulfillment_coaching`): read-only tools `get_recent_coaching_calls`, `get_recent_wins`, `get_top_pain_points`. Distinct from the `coaching_analyzer_v1` Celery extractor.
- `app/prompts/fulfillment_director_v1.py` — `FULFILLMENT_DIRECTOR_SYSTEM_PROMPT_V1` (exported in `prompts/__init__.py`).
- `app/agents/directors/fulfillment.py` — `FulfillmentDirector` (`claude-sonnet-4-6`), registers `members_analyst` + `coaching` specialists and director tools `get_fulfillment_summary`, `get_top_pain_points`.

#### Backend — Routes & wiring
- `app/routes/members.py` + `app/schemas/members.py` — full CRUD: `GET /members` (list/filters), `GET /members/stats`, `GET /members/{id}` (detail with calls/goals/wins/pain/notes), `GET /members/{id}/history`, `PATCH /members/{id}` (per-field `member.*` audit via `record_event`, no GHL push), `POST`/`DELETE /members/{id}/notes`.
- `app/routes/fulfillment.py` — `GET /api/v1/fulfillment/summary` (auth-gated, like `/sales/summary`).
- `app/routes/directors.py` — registered `"fulfillment-director"` → `WS /ws/v1/fulfillment-director/{session_id}`.
- `app/main.py` — mounted `members_router` + `fulfillment_router` under `/api/v1`.
- `app/middleware/auth.py` — `/api/v1/members` added to exempt prefixes (matches `/leads`).

#### Frontend
- `frontend/src/components/chat/fulfillment-director-chat-view.tsx` + `(app)/fulfillment-director/page.tsx` — orange (#F97316) chat, 🏆, `useDirectorChat("fulfillment-director")`.
- `(app)/fulfillment/page.tsx` — dashboard: 4 orange KPI cards from `/fulfillment/summary`, tools card (Members, Coaching Calls), Director CTA.
- `(app)/members/page.tsx` + `(app)/members/[member_id]/page.tsx` — members directory (table + filters + KPIs) and detail (inline edit, goals/wins/pain, staff notes, history timeline).
- `frontend/src/components/layout/sidebar.tsx` — added Fulfillment Overview + Fulfillment Director links.
- `frontend/src/components/layout/header.tsx` — fulfillment-page CTA now routes to `/fulfillment-director`.

### Added — Sprint 5a: Sales Department core (Sales Director + specialists)

Adds the Sales Director coordination layer on top of the already-shipped Leads (S02) and Sales Calls / Call Analyzer (S03) data layer. Leads and Sales Calls were NOT rebuilt — their routes/UI stay as-is and are wrapped as read-only specialists. Appointments (S01) is deferred to Sprint 5b (planned to use a GHL appointment sync).

#### Backend — Shared aggregation (single source of truth)
- `app/repositories/sales_stats.py` — new module with `compute_lead_stats()` (KPIs, 8-week lead volume, source breakdown, 4-stage funnel — SQL lifted verbatim from the leads route), `get_top_pain_points()`, and `get_recent_insights()`. Both the leads route and the Sales surfaces consume it so the funnel definition can't drift.
- `app/routes/leads.py` — `GET /api/v1/leads/stats` now delegates to `compute_lead_stats()` and adapts the dict into `LeadsStatsResponse`. Behavior is identical (verified by before/after regression: 14 leads, same volume/funnel shape).

#### Backend — Agents
- `app/prompts/sales_director_v1.py` — `SALES_DIRECTOR_SYSTEM_PROMPT_V1`, mirroring the Marketing Director prompt structure (Role, How-to-Respond guardrails, Intelligence Pre-Flight, internal Routing, Response Structure). Exported from `app/prompts/__init__.py`.
- `app/agents/specialists/leads.py` — `LeadsSpecialist` (`sales_leads`), read-only tools `get_leads_summary`, `get_lead_list`. No write tools — lead CRUD stays in the route.
- `app/agents/specialists/call_analyzer.py` — `CallAnalyzerSpecialist` (`sales_calls`), read-only tools `get_recent_calls`, `get_call_insights`, `get_top_pain_points`. Distinct from the `call_analyzer_v1` Celery extractor — this only reads `insights` rows.
- `app/agents/directors/sales.py` — `SalesDirector` (model `claude-sonnet-4-6`, matching the Marketing Director). Registers `leads_analyst` + `call_analyzer` specialists (auto-creating `delegate_to_*` tools) and director-level data tools `get_sales_summary`, `get_top_pain_points`.

#### Backend — Routes & wiring
- `app/routes/sales.py` — `GET /api/v1/sales/summary` mirroring `/marketing/summary`: KPIs, lead volume, source breakdown, funnel, top pain points, recent insights. (Auth-gated, same as `/marketing/summary`.)
- `app/routes/directors.py` — registered `"sales-director"` in `_DIRECTOR_REGISTRY`; the WebSocket route `WS /ws/v1/sales-director/{session_id}` now resolves with no other change.
- `app/main.py` — mounted `sales_router` under `/api/v1`.

#### Frontend
- `frontend/src/components/chat/sales-director-chat-view.tsx` + `frontend/src/app/(app)/sales-director/page.tsx` — Sales Director chat, using `useDirectorChat("sales-director")`, blue (#3B82F6) accent, 💼 avatar.
- `frontend/src/app/(app)/sales/page.tsx` — Sales department dashboard: 4 blue KPI cards from `/sales/summary`, a Sales Tools card (Leads, Sales Calls), and a Sales Director CTA.
- `frontend/src/components/layout/sidebar.tsx` — added "Sales Overview" (`/sales`) and "Sales Director" (`/sales-director`) to the Sales section.
- `frontend/src/components/layout/header.tsx` — sales-page "Sales Director" CTA now routes to `/sales-director` (was `/chat`).

#### Notes (deliberate decisions)
- **CI awareness:** Central Intelligence left untouched — the Marketing Director isn't wired into CI either; matched that precedent.
- **No `__init__` re-exports** for the new director/specialists — the verified convention is import-by-dotted-path (registry / inline), not re-export. Matches Marketing.

### Fixed — Sprint 3 Data Connectivity: Database Persistence Pipeline

#### Backend — New Models & Repositories
- `app/models/marketing.py` — 5 new SQLAlchemy models: `SocialStats`, `SocialComment`, `EmailCampaign`, `FunnelEvent`, `FunnelStats` with proper indexes, timestamps, soft-delete, and unique constraints
- `app/repositories/marketing.py` — 5 new repository classes with domain-specific queries: `SocialStatsRepository` (aggregate_totals, upsert_stats), `SocialCommentRepository`, `EmailCampaignRepository` (aggregate_stats, upsert_campaign), `FunnelEventRepository` (count_by_funnel_and_stage), `FunnelStatsRepository` (find_all_latest, upsert_stats)
- `app/models/__init__.py` — registered all 5 marketing models for Alembic autodiscovery
- `app/repositories/__init__.py` — exported all 5 marketing repositories

#### Backend — Routes Wired to Database
- `app/routes/social.py` — `GET /api/v1/social` now queries `SocialStatsRepository.aggregate_totals()` instead of returning hardcoded zeros
- `app/routes/email.py` — `GET /api/v1/email` now queries `EmailCampaignRepository.aggregate_stats()` instead of returning hardcoded zeros
- `app/routes/funnels.py` — `POST /api/v1/funnels` now persists events to `funnel_events` table via `FunnelEventRepository`; added `GET /api/v1/funnels` endpoint returning aggregated stage stats via `FunnelStatsRepository`
- `app/schemas/funnels.py` — added `FunnelStageStats` and `FunnelDataResponse` Pydantic schemas

#### Backend — Celery Tasks Wired to Database
- `app/tasks/db.py` — new shared sync session helper (`make_sync_session()`) for Celery tasks
- `app/tasks/social_stats.py` — replaced placeholder with upsert loop writing seed data to `social_stats` table for 4 platforms
- `app/tasks/email_stats.py` — replaced placeholder with upsert loop writing seed campaign data to `email_campaigns` table
- `app/tasks/funnel_stats.py` — replaced placeholder with aggregation query on `funnel_events` → upsert into `funnel_stats`
- `app/tasks/comments_collector.py` — replaced placeholder with dedup-aware insert of seed comments into `social_comments` table

#### Backend — Bug Fix
- `app/tasks/celery_app.py` — added missing `"app.tasks.funnel_stats"` to Celery include list (task was never discovered by workers)

#### Frontend — Pages Wired to Backend APIs
- `marketing/social/page.tsx` — fetches `GET /api/v1/social`, populates KPI tiles with real followers/posts/engagement data
- `marketing/email/page.tsx` — fetches `GET /api/v1/email`, populates KPI tiles with real campaign count/open rate/CTR
- `marketing/funnels/page.tsx` — fetches `GET /api/v1/funnels`, populates KPI tiles and stale indicator with real funnel stage data
- `marketing/social/scripts/page.tsx` — wired Generate button to `POST /api/v1/social` (falls back to mock on error)
- `marketing/email/compose/page.tsx` — wired AI Assist button to `POST /api/v1/email` (falls back to mock on error)

### Added — VIR-39, VIR-40: Sprint 4a/4b — Ads, DM, and Offer Specialist Prompts

- `app/prompts/ad_analysis_v1.py` (M04-2) — `CI-MKT-ADS` analysis mode. ROAS-primary campaign health diagnostics (strong ≥3x, moderate 1.5-3x, weak <1.5x), layer-level diagnosis (creative/copy/targeting/landing page), cross-domain alerts for pain points and wins not in any ad creative. `build_ad_analysis_user_prompt`: ad_stats sorted by ROAS, pain_points, wins, content_ideas. 8-field output schema.
- `app/prompts/ad_copy_generation_v1.py` (M04-3) — `CI-MKT-ADS` copy generation mode. Platform-native rules (Facebook/Instagram hook-within-3-words, Google Ads 30-char headline hard limit). 4 angle types enforced as distinct categories. `ad_variants` minItems=3. Banned clichés list in system prompt. Includes `recommended_test_order` and `targeting_suggestion`.
- `app/prompts/dm_analysis_v1.py` (M05-2) — `CI-MKT-DM` analysis mode. Three-stage funnel diagnostics (response_rate / positive_response_rate / conversion_rate). Opener pattern analysis at structural DNA level. DM-calibrated health thresholds (>5% conversion = strong). `opener_pattern_analysis` array with `replication_advice` per sequence type.
- `app/prompts/dm_template_generation_v1.py` (M05-3) — `CI-MKT-DM` template generation mode. Per-message `message_job` field (psychological movement). Platform-context calibration (LinkedIn professional vs Instagram/Facebook social register). Cold outreach never-pitch rule enforced. Personalisation placeholders: [FIRST_NAME], [COMPANY], [SPECIFIC_OBSERVATION], [SHARED_CONTEXT].
- `app/prompts/offer_analysis_v1.py` (M06-2) — `CI-OFR` analysis mode. Per-offer audit: `pain_alignment_score` (1-10), `objection_coverage` (addressed/missed), `missing_value_props`, per-offer `optimization_recommendations`. `pricing_gap_analysis` across full portfolio. Offers sorted by conversion_rate ascending (failures first).
- `app/prompts/offer_creation_v1.py` (M06-3) — `CI-OFR` creation mode. Every offer element CI-grounded. Pricing tier rationale required. Bonuses each require `objection_addressed`. Guarantee with `objection_addressed`. `urgency_element` with `is_genuine` boolean. 3 typed copy angles.
- `app/prompts/offer_generator_v1.py` (OPS-O2) — `CI-OPS-OFR` Celery operator. Deterministic, autonomous. `status` field: success/insufficient_data/error. Data threshold enforcement (< 3 pain_points or wins → insufficient_data). Offer type auto-selection logic from CI signals. `generated_at_signal` data quality note.
- `app/prompts/__init__.py` — updated with all 18 new symbols from the 7 new prompt modules.

### Added — VIR-33, VIR-34: Sprint 3a/3b — Email + Funnel Specialist Prompts

- `app/prompts/email_analysis_v1.py` (M02-2) — `EMAIL_ANALYSIS_SYSTEM_PROMPT_V1`: CI-MKT-EMAIL analysis-mode prompt with 3 expertise areas, per-campaign-type analysis mandate, coaching-industry benchmarks, example output. `build_email_analysis_user_prompt(data)`: handles email_stats, content_ideas, market_signals, pain_points, ICP segments with graceful empty-data fallbacks. `EMAIL_ANALYSIS_OUTPUT_SCHEMA`: 8-field JSON Schema (summary, top_performing_campaign_type, overall_health, campaign_breakdown, subject_line_insights, content_gaps, cross_domain_insights, recommended_focus).
- `app/prompts/email_draft_v1.py` (M02-3) — `EMAIL_DRAFT_SYSTEM_PROMPT_V1`: CI-MKT-EMAIL draft-mode prompt with 5 enforced quality rules (CI anchor, one-email-one-CTA, subject line formula, body structure, preview text). `build_email_draft_user_prompt(data)`: handles email_type, subject_brief, sequence_position, brand_voice, icp_primary, CI data. `EMAIL_DRAFT_OUTPUT_SCHEMA`: 9-field schema including ps_line (nullable) and ci_anchor.
- `app/prompts/funnel_analysis_v1.py` (M03-2) — `FUNNEL_ANALYSIS_SYSTEM_PROMPT_V1`: CI-MKT-FUN Funnels Analyst prompt with 3 expertise areas (metrics analysis, conversion psychology, CI synthesis), coaching-industry drop-off severity benchmarks, full stage + source analysis mandate. `build_funnel_analysis_user_prompt(data)`: funnel_stages (sorted ascending by conversion to surface bottlenecks), lead_sources (sorted by conversion quality), pain_points, ICP segments, market_signals. `FUNNEL_ANALYSIS_OUTPUT_SCHEMA`: 8-field schema including critical_bottleneck, stage_analysis with drop_off_severity enum, optimization_priorities (ranked by revenue impact).
- `app/prompts/__init__.py` — exported all 6 new symbols from email_analysis_v1, email_draft_v1, and funnel_analysis_v1.

### Added — VIR-35: Sprint 3a — Social Media + Email Specialist Agents + Stats Operators
- `app/schemas/social.py` — Pydantic schemas: `SocialAnalyzeRequest`, `SocialPost`, `SocialAnalyzeResponse`, `SocialDataResponse`
- `app/schemas/email.py` — Pydantic schemas: `EmailAnalyzeRequest`, `EmailDraftRequest`, `EmailAnalyzeResponse`, `EmailDraftResponse`, `EmailDataResponse`
- `app/agents/specialists/social_media.py` — `SocialMediaSpecialist` (M01-1): extends `SpecialistAgent`, domain `social_media_marketing`, tools: `get_social_data`, `generate_social_script`
- `app/agents/specialists/email.py` — `EmailSpecialist` (M02-1): extends `SpecialistAgent`, domain `email_marketing`, tools: `get_email_metrics`, `draft_email`
- `app/routes/social.py` — FastAPI router (M01-4): `POST /api/v1/social` (analyze/script generation), `GET /api/v1/social` (social data)
- `app/routes/email.py` — FastAPI router (M02-4): `POST /api/v1/email` (analyze/draft), `GET /api/v1/email` (email data)
- `app/tasks/email_stats.py` — Celery task `update_email_stats` (OPS-SE1): scheduled task to pull/update email campaign metrics
- `app/tasks/social_stats.py` — Celery task `update_social_stats` (OPS-SS1): scheduled task for social media metrics
- `app/tasks/comments_collector.py` — Celery task `collect_social_comments` (OPS-SC1): polling task to collect and store social comments
- `app/agents/directors/marketing.py` — (M01-5, M02-5) registered `SocialMediaSpecialist` and `EmailSpecialist` with Marketing Director
- `app/main.py` — mounted `social_router` and `email_router` under `/api/v1`
- `app/tasks/celery_app.py` — added new task modules to Celery `include` list for worker autodiscovery

### Fixed — VIR-29: ORM table name mismatches causing SQL transaction failures
- `app/models/intelligence.py` — `BusinessProfile.__tablename__` changed from `business_profiles` to `business_profile` to match Supabase migration
- `app/models/audit.py` — `AuditLog.__tablename__` changed from `audit_logs` to `audit_log` to match Supabase migration
- `app/models/audit.py` — `ErrorLog.__tablename__` changed from `error_logs` to `error_log` to match Supabase migration
- `app/models/audit.py` — `SyncLog.__tablename__` changed from `sync_logs` to `sync_log` to match Supabase migration

### Changed — VIR-27: Prompt Audit Implementation
- `app/agents/directors/marketing.py` — Replaced 12-line placeholder system prompt with production-grade prompt adapted from workflow spec: routing decision table, parallel/sequential coordination rules, intelligence data pre-flight, structured JSON response format, and internal reasoning checklist
- `app/agents/operators/transcriber.py` — Replaced one-sentence system prompt with production version: call-type awareness (sales_call, coaching, accountability), error handling guidance, and output contract
- `app/prompts/central_intelligence_v1.py` — Fixed "honest about limitations" vs. secrecy section contradiction (now "honest about capabilities, not process"); added hallucination guard rule (never fabricate data overrides silence-on-errors); added empty-result guidance
- `app/agents/central_intelligence.py` — Upgraded model from `claude-3-haiku-20240307` to `claude-sonnet-4-6` (Haiku was too weak for SQL generation + CEO persona complexity)
- `app/prompts/icp_generator_v1.py` — Replaced instruction-placeholder JSON example with realistic fictional ICP examples; strengthened `is_primary` uniqueness constraint to "exactly one, hard constraint"

### Fixed — VIR-28: Director WebSocket endpoint missing

- `app/routes/directors.py` — New WebSocket route `WS /ws/v1/{director_slug}/{session_id}` for Director agents, mirroring the Central Intelligence WebSocket protocol. Supports `marketing-director` slug, in-memory session store keyed by `(slug, session_id)`, mock mode fallback, JWT auth, and DB session lifecycle management.
- `app/main.py` — Mounted `directors_router` at root (after `central_intelligence_router`) so Director WebSocket paths resolve correctly.

### Added — Sprint 2 / VIR-20: Central Intelligence Webhook Endpoints + Data Sync Bridges
- `app/schemas/ci.py` — Pydantic models for all 13 CI endpoints (transcripts, calls, insights, content-ideas, market-signals, tags, offers, monthly-preferences) plus pagination and sync result schemas
- `app/routes/ci.py` — CI router with 15 endpoints:
  - CI-MKT-01 (8pts): 13 webhook endpoints — `POST transcripts/upload`, `POST transcripts/process`, `GET/GET:id calls`, `GET/GET:id insights`, `GET/PUT content-ideas`, `GET market-signals`, `GET tags`, `GET offers`, `GET/PUT monthly-preferences`
  - CI-MKT-02 (5pts): `POST /ci/sync/insights` — data sync bridge mapping CI insights to shared intelligence tables (pain_points, wins, objections, goals) with dedup and frequency increment
  - CI-MKT-03 (3pts): `POST /ci/sync/content-ideas` — data sync bridge validating and tagging CI pipeline content ideas in the shared content_ideas table
- `app/main.py` — registered CI router under `/api/v1` (resolves to `/api/v1/ci/*`)

### Added — Sprint 2 / VIR-18: Optimistic Locking (updatedAt + If-Match)
- `app/middleware/optimistic_lock.py` — ETag utilities: `etag_from_datetime`, `parse_if_match`, `StaleUpdateError` (409), `require_if_match` dependency (428 on missing header), `add_etag_header` response helper
- `app/dependencies/optimistic_lock.py` — FastAPI Header-based dependency returning parsed `datetime` for route handler injection via `Depends(require_if_match)`
- `app/repositories/base.py` — `update_optimistic(id, expected_updated_at, **kwargs)` method on `RepositoryBase` with UTC normalization, 1µs tolerance, 404/409 error handling
- `app/schemas/common.py` — `ErrorDetail` and `ErrorResponse` standard error envelope schemas

### Added — Sprint 2 / VIR-17: UX Components (Skeleton Loaders, Empty States, Confirm Dialog)
- `components/ui/skeleton.tsx` — added `TableSkeleton` (props: rows, cols, showFilters), `ChartCardSkeleton` (prop: height), and `DonutChartSkeleton` reusable system-wide components
- `components/ui/empty-state.tsx` — new `EmptyState` component with icon, title, description, primary action (amber CTA), and secondary action (text link)
- `components/ui/confirm-dialog.tsx` — new `ConfirmDialog` modal with danger/warning/default variants, loading state, ESC key + backdrop dismiss, focus trap, and full ARIA support

### Added — Sprint 2 / CI-CORE-01 / T01-2: Transcriber Operator
- `app/agents/operators/transcriber.py` — `TranscriberOperator` extending `BaseAgent` with audio download, pydub MP3 extraction, OpenAI Whisper transcription, URL SHA-256 deduplication, and `transcribe_audio` tool registration
- `app/agents/operators/__init__.py` — operators package
- `app/schemas/transcribe.py` — `TranscribeRequest` / `TranscribeResponse` Pydantic models
- `app/routes/transcribe.py` — `POST /api/v1/transcribe` endpoint with deduplication check, error handling (422/502/500), and Call record persistence
- `app/models/operational.py` — added `video_url_hash` (unique indexed SHA-256) and `transcript_text` columns to `Call` model
- `app/config.py` — added `openai_api_key` setting
- `app/main.py` — registered transcribe router under `/api/v1`
- `requirements.txt` — added `openai>=1.30.0`, `pydub>=0.25.1`, `requests>=2.31.0`

## [0.2.0] - 2026-03-30 — Sprint 1B Auth + Error Handling Core

### Added

#### Backend
- **Supabase Auth integration** with full mock bypass mode:
  - Auth routes: `POST /api/v1/auth/login`, `/signup`, `/refresh`, `/logout`, `/password-reset`, `GET /me`
  - When `SUPABASE_URL` is empty, all auth routes return mock responses (fake tokens, mock user)
  - When credentials are provided, real Supabase auth activates with zero code changes
- **Auth middleware** (`AuthMiddleware`):
  - JWT verification via `python-jose` for zero-latency token checks
  - Exempt paths: `/auth/*`, `/health`, `/docs`, `/redoc`, `/openapi.json`
  - Mock mode bypass when `SUPABASE_URL` is empty or `MOCK_MODE=true`
  - Standard error envelope on 401: `{"error": {"code": "UNAUTHORIZED", ...}}`
  - WebSocket auth via `?token=` query parameter
- **Error Handler agent** (`ErrorHandlerAgent`):
  - Async error logging to `error_logs` database table
  - In-memory retry queue with exponential backoff (3 max retries)
  - Convenience methods: `log_error()`, `log_warning()`, `log_info()`, `flush_queue()`
  - Module-level singleton: `error_handler`
- **ErrorLog repository** with `list_by_severity()` and `list_recent()` queries
- **Health check enhancements**: `auth`, `redis`, `uptime` fields added to `GET /api/v1/health`
- Auth Pydantic schemas: `LoginRequest`, `LoginResponse`, `UserProfile`, `PasswordResetRequest`, `TokenRefreshRequest`
- New columns on `ErrorLog` model: `agent_id`, `request_id`, `user_id` (FK), `stack_trace`

#### Frontend
- **Login page** (`/login`) matching Screen 0 of webapp mockup:
  - Dark stage background with radial gold shimmer overlay
  - Centered 420px white card with bee icon, "Central Intelligence" branding
  - Email + password fields with gold focus ring, eye toggle for password
  - Remember me checkbox + Forgot password (wired to `resetPassword`)
  - Gold gradient Sign In button with loading spinner state
  - Error banner with attempt tracker (X of 5 dots), red input error states
  - Client-side validation before auth call
  - "Powered by Central Intelligence AI" footer
- **Route group restructure**: pages moved under `(app)/` for sidebar layout, `/login` renders standalone
- **Auth context** (`AuthProvider`) with mock mode:
  - Auto-signs in with mock user when Supabase is not configured
  - `useAuth()` hook: `user`, `signIn`, `signOut`, `resetPassword`, `isLoading`, `isMockMode`
  - Real mode: Supabase session hydration, `onAuthStateChange` listener, token sync to API client
- **Next.js middleware** for session refresh + auth redirects (pass-through in mock mode)
- **Supabase client wiring**: browser client + middleware client with modern `getAll`/`setAll` cookie API
- **Toast notification system** (sonner):
  - `<Toaster />` provider in top-right position with brand styling
  - Helpers: `showSuccess()`, `showError()`, `showWarning()`, `showInfo()`, `showApiError()`
- **Error boundaries**:
  - React class component `<ErrorBoundary>` with "Try again" + "Return to Dashboard"
  - Next.js `error.tsx` for `(app)` route group with error digest display in dev mode
- **API client interceptor** enhancements:
  - AbortController timeout (30s default)
  - Retry with exponential backoff (3 attempts on 5xx, no retry on 4xx)
  - 401 interceptor: clear token, toast "Session expired", redirect to `/login`
  - Auto-toast on errors (suppressible via `{ silent: true }`)
  - Error normalization to standard `ApiError` with `field` and `requestId`
- **WebSocket improvements**:
  - Connection state change events (`onStateChange` handler)
  - Toast notification on connection failure after max reconnect attempts
  - Token passed as `?token=` query parameter for backend auth
  - `useChat` hook now tracks real connection state (replaces blind timer)
- Dynamic sidebar user from `useAuth()` with logout button (replaces hardcoded "Jade Doe")

### Changed
- Root `layout.tsx` simplified to minimal html/body/Providers shell (sidebar grid moved to `(app)/layout.tsx`)
- `pydantic` dependency updated to `pydantic[email]` for `EmailStr` support
- `requirements.txt` now includes `supabase>=2.0.0` and `python-jose[cryptography]>=3.3.0`
- Frontend packages added: `@supabase/supabase-js`, `@supabase/ssr`, `sonner`, `lucide-react`

## [0.1.0] - 2026-03-29 — Sprint 1A Foundation

### Added

#### Backend (Python + FastAPI)
- FastAPI application with app factory pattern (`backend/app/main.py`)
- Pydantic-settings configuration with `.env` loading (`backend/app/config.py`)
- Async SQLAlchemy engine with asyncpg + NullPool for Supabase (`backend/app/database.py`)
- **21 SQLAlchemy ORM models** across 4 modules:
  - Operational (9): Lead, Member, Call, Insight, ContentIdea, Goal, PainPoint, Win, Objection
  - Meta (2): User, Team
  - Intelligence (6): InsightTag, TagDictionary, MarketSignal, Offer, BusinessProfile, MonthlyPreference
  - Audit (4): AuditLog, ErrorLog, SyncLog, IdempotencyKey
- Base mixins: TimestampMixin, SoftDeleteMixin
- **Generic RepositoryBase[T]** with async CRUD, soft-delete filtering, and count
- **15 concrete repositories** with domain-specific query methods (e.g., `LeadRepository.find_by_email`)
- IntelligenceRepository facade for cross-domain queries
- Alembic async migration configuration
- **BaseAgent class** with Anthropic AsyncAnthropic SDK integration:
  - Tool registration (schema separate from handlers)
  - Async streaming via `messages.stream()` with automatic tool-use loop
  - Conversation history management
  - Error handling for API, rate limit, and connection errors
- **DirectorAgent** skeleton with specialist registration and delegation tools
- **SpecialistAgent** skeleton with domain context and DB/operator tool hooks
- **CentralIntelligence agent** (CI-CORE-00) with comprehensive system prompt v1
- **API endpoints**:
  - `GET /api/v1/health` — database connectivity check
  - `POST /api/v1/central-intelligence/chat` — SSE streaming chat
  - `WS /ws/v1/central-intelligence/{session_id}` — WebSocket streaming chat
- In-memory session store for agent conversations (Redis planned for Sprint 1B)

#### Frontend (Next.js 14 + TypeScript + Tailwind CSS)
- Next.js 14 App Router project with TypeScript and Tailwind CSS
- TanStack Query (React Query) provider setup
- **Light color scheme** with department-colored accents:
  - White sidebar (228px) with colored section labels and active-state borders
  - Marketing (#10B981), Sales (#3B82F6), Fulfillment (#F97316) department colors
  - Gold (#F59E0B) accent for Central Intelligence elements
- **Sidebar navigation** matching mockup: Dashboard, Central Intelligence Chat, Sales (3), Fulfillment (4), Marketing (7), Admin (1)
- **Header component** with dynamic title, date display, and context-sensitive actions
- **Dashboard page** with:
  - 3-column department summary cards (white bg, colored left borders, KPI stats)
  - Weekly Performance Snapshot (4 KPI mini-cards + sparkline bar chart)
  - Central Intelligence Recommendations widget (light gold-tinted bg, 4 AI-generated focus areas)
- **Chat UI page** with:
  - WebSocket-based real-time streaming
  - `useChat` hook managing connection lifecycle, message state, and streaming
  - Message bubbles (Central Intelligence: white/left, User: blue/right) with avatar icons
  - Inline markdown rendering (bold, lists, code blocks)
  - Typing indicator with animated dots
  - Auto-growing textarea input with Enter-to-send
  - Auto-scroll to latest message
- **API client library** with fetch wrapper, SSE stream parsing, auth header injection
- **WebSocket client** with exponential backoff reconnection (max 5 attempts)
- App name stored in config constant (pending final naming decision)

#### Infrastructure
- WAT framework project isolation (per-project CLAUDE.md, .env, tools/, workflows/, .tmp/)
- Root CLAUDE.md rewritten as slim orchestrator with bootstrapping template
- `.gitignore` for credentials, .env, .tmp across all projects

### Changed

- All 14 documents in `New Documents/` migrated from n8n workflow architecture to Python + Claude SDK agentic architecture (v3.0.0)
- Architecture: n8n → FastAPI + Claude SDK + Celery + Redis
- Database: n8n Data Tables + Airtable → unified Supabase PostgreSQL with SQLAlchemy ORM
- Frontend framework confirmed: Next.js 14 (App Router)
- Auth strategy: Supabase Auth (JWT + RLS) replacing NextAuth.js

## [Sprint 2] Marketing Director + Shared Repository Layer + Summary Endpoint

### Added
- `app/models/operational.py` — `ICP` model (Ideal Customer Profile segments)
- `app/repositories/operational.py` — `ICPRepository` with `find_primary()` and `find_by_status()`
- `app/repositories/shared_intelligence.py` — `SharedIntelligenceRepository` facade composing all 7 shared intelligence tables (goals, wins, pain_points, objections, content_ideas, icp, offers)
- `app/agents/directors/marketing.py` — `MarketingDirector` extending `DirectorAgent` with 6 data tools and specialist routing
- `app/routes/marketing.py` — `GET /api/v1/marketing/summary` aggregating marketing dept metrics
- `app/main.py` — wired marketing router under `/api/v1`

**Tasks:** DIR-M1 (5pts), DIR-M3 (3pts), DIR-M4 (2pts) | Total: 10 story points
