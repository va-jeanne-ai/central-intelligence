# Changelog

All notable changes to the Central Intelligence project will be documented in this file.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

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
