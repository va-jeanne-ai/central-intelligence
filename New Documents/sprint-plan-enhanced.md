# Central Intelligence (Central Intelligence) - Sprint Plan v3.0

## Overview

- **Total Sprints**: 8 (2-week sprints + 1-week Sprint 1b)
- **Total Duration**: ~17 weeks
- **Total Story Points**: 701 (includes 49 pts for Central Intelligence integration tasks)
- **Team**: 3 roles (Backend Developer, Frontend Developer, AI/Integration Specialist)
- **Sprint Order**: Foundation → Auth → Marketing (with CI integration) → Sales → Fulfillment (with CI integration) → Data Migration → Polish
- **Tech Stack**: Python + FastAPI + Claude SDK, Next.js, Supabase (PostgreSQL), SQLAlchemy, Celery + Redis, Sentry

## Team Roles

| Role | Tag | Responsibility |
| ---- | --- | -------------- |
| Backend Developer | `[BE]` | FastAPI endpoints, agent classes, Claude SDK integration, Celery tasks, database queries |
| Frontend Developer | `[FE]` | Next.js pages, React components, charts, styling, WebSocket streaming |
| AI/Integration Specialist | `[AI]` | Prompt engineering, agent system prompts, tool definitions, Claude API optimization |

## Agentic Architecture (Central Intelligence → Directors → Specialists → Operators)

| Agent Level | Implementation | Sprint Usage |
| ----------- | -------------- | ------------ |
| **Central Intelligence** | Python agent class + Claude SDK | Sprint 1a (core), Sprint 8 (enhanced) |
| **Directors** (Marketing, Sales, Fulfillment) | Python agent classes with sub-tool routing | Sprint 2 (Marketing), Sprint 5 (Sales), Sprint 6 (Fulfillment) |
| **Specialists** (Social, Email, Leads, etc.) | Python agent classes with Claude tools | Sprints 3-4 (Marketing), Sprint 5 (Sales), Sprint 6 (Fulfillment) |
| **Operators** (Transcriber, Stats, ICP Gen) | Python task queue workers (Celery) | Sprint 2+ (all sprints) |

---

## Sprint 1a (Weeks 1-2): Foundation

**Goal**: FastAPI project setup, Supabase schema, SQLAlchemy models, base agent class, Central Intelligence skeleton

| Task ID | Task | Owner | Points |
| ------- | ---- | ----- | ------ |
| C00-7 | Create all 16 Supabase tables (PostgreSQL) + SQLAlchemy models (10 original + 6 new: objections, goals, icp, offers, comments, reference) | `[BE]` | 5 |
| C00-6 | Build base Agent class with Claude SDK integration and tool registry | `[BE]` | 5 |
| C00-1 | Central Intelligence agent class skeleton + router endpoint (FastAPI) | `[BE]` | 5 |
| C00-2 | Central Intelligence system prompt v1 | `[AI]` | 3 |
| C00-3 | WebSocket endpoint for streaming chat responses | `[BE]` | 3 |
| C00-8 | Next.js app shell + sidebar nav + layout | `[FE]` | 5 |
| C00-5 | API client library (fetch wrapper + auth) | `[FE]` | 3 |
| C00-4 | Central Intelligence Chat UI page (WebSocket streaming) | `[FE]` | 5 |
| C00-9 | Dashboard landing page | `[FE]` | 3 |

**Sprint 1a totals**: `[BE]` 18pts, `[FE]` 16pts, `[AI]` 3pts = **37pts**

**Acceptance Criteria**: Chat with Central Intelligence from web app and get streaming response. FastAPI server running. Supabase connection verified.

**Dependencies**: None (first sprint)

**Deliverables**:
- FastAPI project with SQLAlchemy ORM + Repository pattern
- Central Intelligence agent class with Claude SDK integration
- WebSocket endpoint for streaming responses
- Next.js app with sidebar navigation and 3 department sections (Marketing, Sales, Fulfillment)
- Chat page that sends messages via WebSocket and displays streaming responses
- Dashboard landing page with placeholder department summary cards
- All 16 Supabase PostgreSQL tables created with migrations
- Base Agent class with tool registry and Claude API error handling

---

## Sprint 1b (Week 3): Auth + Error Handling Core

**Goal**: Supabase Auth setup, error handling infrastructure, middleware

| Task ID | Task | Owner | Points |
| ------- | ---- | ----- | ------ |
| SEC-01 | Supabase Auth integration (JWT tokens, session management) | `[BE]` | 5 |
| SEC-02 | Auth middleware + protected routes (FastAPI) | `[BE]` | 3 |
| SEC-03 | Login page UI + signup flow (Next.js) | `[FE]` | 3 |
| SEC-04 | Session cookie handling (httpOnly, secure, SameSite) | `[FE]` | 2 |
| SEC-05 | Logout + password reset flows (Supabase Auth) | `[BE]` | 3 |
| ERR-01 | Error Handler agent + bee_error_log table (async logging) | `[BE]` | 5 |
| ERR-02 | Error boundary components (React) | `[FE]` | 3 |
| ERR-03 | Toast notification system (shadcn/ui) | `[FE]` | 2 |
| ERR-04 | API client interceptor (timeout, retry, error normalization) | `[FE]` | 3 |
| ERR-05 | Health check endpoint (GET /health) | `[BE]` | 1 |

**Sprint 1b totals**: `[BE]` 12pts, `[FE]` 13pts = **25pts**

**Acceptance Criteria**: Login required to access app. Failed worker logs to bee_error_log table. Toast notifications show on API errors. Signed-out users redirected to login.

**Dependencies**: Sprint 1a (app shell, data tables, API client)

**Deliverables**:
- Supabase Auth setup with JWT token generation
- FastAPI auth middleware protecting all routes except /login
- Login/signup page with email/password, "Remember me", session persistence
- Password reset flow via email
- Error Handler agent logging to bee_error_log with retry logic
- Error boundaries catching React errors gracefully
- Toast provider for success/error/warning feedback
- API client with AbortController timeouts, exponential backoff retry, 401→login redirect
- GET /health endpoint for connectivity checks

---

## Sprint 2 (Weeks 4-5): Marketing Director + Core Operators

**Goal**: Marketing Director agent, Transcriber operator, ICP Generator, shared data pipeline

| Task ID | Task | Owner | Points |
| ------- | ---- | ----- | ------ |
| DIR-M1 | Marketing Director agent class with specialist routing | `[BE]` | 5 |
| DIR-M2 | Marketing Director system prompt | `[AI]` | 3 |
| DIR-M3 | Shared table repository layer (goals, wins, pain_points, objections, content_ideas, icp, offers) | `[BE]` | 3 |
| DIR-M4 | Marketing summary endpoint (FastAPI, aggregates dept metrics) | `[BE]` | 2 |
| DIR-M5 | Marketing Director chat page | `[FE]` | 3 |
| DIR-M6 | Marketing department dashboard | `[FE]` | 5 |
| T01-1 | Transcriber agent (Celery task queue) | `[BE]` | 3 |
| T01-2 | Audio extraction & Whisper API integration | `[AI]` | 5 |
| T01-3 | Transcript storage in Supabase | `[BE]` | 2 |
| T01-4 | Call type routing logic (sales call, coaching, appointment) | `[BE]` | 3 |
| T01-5 | FastAPI webhook endpoint for transcription requests | `[BE]` | 2 |
| T01-6 | Register Transcriber as shared Operator | `[BE]` | 1 |
| T01-7 | Transcript upload UI + drag-drop support | `[FE]` | 5 |
| OPS-I1 | ICP Generator agent (Celery + Claude) | `[BE]` | 3 |
| OPS-I2 | ICP analysis prompt | `[AI]` | 5 |
| OPS-I3 | ICP table writes via Repository | `[BE]` | 2 |
| UX-01 | Skeleton loader components (card, table, chart) | `[FE]` | 3 |
| UX-02 | Empty state components with CTAs | `[FE]` | 2 |
| UX-03 | Confirm dialog for destructive actions | `[FE]` | 2 |
| EC-01 | Optimistic locking (updatedAt + If-Match header) | `[BE]` | 3 |
| EC-06 | Transcription edge cases (URL HEAD check, file size validation) | `[BE]` | 3 |
| EC-07 | Duplicate transcript detection (SHA-256 video_url_hash) | `[BE]` | 2 |
| CI-MKT-01 | Create FastAPI webhook endpoints for CI data (13 endpoints: calls, insights, content-ideas, market-signals, tags, offers, monthly-preferences) | `[BE]` | 8 |
| CI-MKT-02 | Build data sync bridge: CI insights → Central Intelligence shared intelligence tables (pain_points, wins, objections, goals) | `[BE]` | 5 |
| CI-MKT-03 | Build data sync bridge: CI content_ideas → Central Intelligence content_ideas table | `[BE]` | 3 |
| CI-MKT-04 | CI insights dashboard page (display insights by type, signal family, strength) | `[FE]` | 5 |
| CI-MKT-05 | CI market signals dashboard page (top pains, objections, trend charts) | `[FE]` | 5 |

**Sprint 2 totals**: `[BE]` 50pts, `[FE]` 30pts, `[AI]` 13pts = **93pts**

**Acceptance Criteria**: Marketing Director responds to department queries. Transcriber processes video URLs into transcripts. ICP Generator creates ideal client profiles from call data. Skeleton loaders show during data fetch. CI data accessible via FastAPI webhook endpoints. Insights and content ideas visible in web app. Data sync between CI Supabase and Central Intelligence tables operational. Market signals dashboard showing aggregated trends.

**Dependencies**: Sprint 1a + 1b (Central Intelligence, app shell, data tables, auth)

**Note**: This is a heavy sprint (93pts). Includes Central Intelligence (CI) integration tasks for marketing insights and market signals. Consider splitting ICP Generator into Sprint 3 if capacity is constrained.

**Deliverables**:
- CI-MKT-DIR Marketing Director Agent with routing to 6 specialist agents
- CI-CORE-01 Transcriber Operator (Celery task) with Whisper integration
- CI-OPS-ICP ICP Generator Operator (analysis prompt + table write)
- Marketing department dashboard with KPI overview
- Marketing Director chat page for department-level Q&A
- Transcript upload UI component (shared across pages)
- Skeleton loaders, empty states, and confirm dialogs available system-wide
- Optimistic locking on all mutable endpoints
- URL validation, file size checks, and SHA-256 deduplication for transcripts
- Central Intelligence (CI) FastAPI webhook endpoints for 13 data sources
- CI insights dashboard page (display by type, signal family, strength)
- CI market signals dashboard page (top pains, objections, trend charts)
- Data sync bridges between CI Supabase and Central Intelligence shared intelligence tables

---

## Sprint 3 (Weeks 6-7): Marketing Specialists Batch 1

**Goal**: Social Media, Email, and Funnels specialists with cross-domain data access

| Task ID | Task | Owner | Points |
| ------- | ---- | ----- | ------ |
| M01-1 | Social Media specialist agent class | `[BE]` | 3 |
| M01-2 | Social analysis prompt | `[AI]` | 5 |
| M01-3 | Script generation prompt | `[AI]` | 5 |
| M01-4 | FastAPI webhook endpoints (POST /social, GET /social) | `[BE]` | 2 |
| M01-5 | Register with Marketing Director | `[BE]` | 1 |
| M01-6 | Social media dashboard | `[FE]` | 5 |
| M01-7 | Script generator UI | `[FE]` | 5 |
| M01-8 | Suggestions panel | `[FE]` | 3 |
| M02-1 | Email specialist agent class | `[BE]` | 3 |
| M02-2 | Email analysis prompt | `[AI]` | 3 |
| M02-3 | Email draft prompt | `[AI]` | 3 |
| M02-4 | FastAPI webhook endpoints (POST /email, GET /email) | `[BE]` | 2 |
| M02-5 | Register with Marketing Director | `[BE]` | 1 |
| M02-6 | Email dashboard | `[FE]` | 5 |
| M02-7 | Email drafting tool | `[FE]` | 5 |
| M03-1 | Funnels specialist agent class | `[BE]` | 3 |
| M03-2 | Funnel analysis prompt | `[AI]` | 5 |
| M03-3 | FastAPI webhook endpoint (POST /funnels) | `[BE]` | 2 |
| M03-4 | Register with Marketing Director | `[BE]` | 1 |
| M03-5 | Funnels dashboard | `[FE]` | 5 |
| M03-6 | Optimization suggestions | `[FE]` | 3 |
| OPS-I4 | ICP management endpoints (GET /icp, PUT /icp/:id) | `[BE]` | 2 |
| OPS-I5 | ICP management UI | `[FE]` | 3 |
| OPS-SE1 | Email Stats Updater (Celery task, scheduled) | `[BE]` | 2 |
| OPS-SS1 | Social Stats Updater (Celery task, scheduled) | `[BE]` | 2 |
| OPS-SF1 | Funnel Stats Updater (Celery task, scheduled) | `[BE]` | 2 |
| OPS-SC1 | Comments Collector (Celery task, polling) | `[BE]` | 3 |
| EC-03 | Soft delete with deleted_at field (all mutable tables) | `[BE]` | 3 |
| EC-04 | Stale data indicator ("last updated" + React Query staleTime) | `[FE]` | 2 |
| EC-08 | Content idea status transitions (new→in-progress→used→archived) | `[BE]` | 2 |
| CI-INT-04 | CI transcript upload page (drag-and-drop UI for manual uploads) | `[FE]` | 5 |
| CI-INT-05 | Content ideas management page (status lifecycle: Idea→Scheduled→Written→Sent→Archived) | `[FE]` | 5 |

**Sprint 3 totals**: `[BE]` 34pts, `[FE]` 46pts, `[AI]` 21pts = **101pts**

**Acceptance Criteria**: Social scripts generated using cross-domain data. Email drafts informed by content ideas. Funnel analysis identifies drop-offs. Stats operators pull live metrics via Celery. Marketing Director coordinates all 3 specialists. CI transcript upload page functional. Content ideas management page supports full status lifecycle.

**Dependencies**: Sprint 2 (Marketing Director, Transcriber, shared tables)

**Note**: This is the heaviest sprint at 101pts. Includes Central Intelligence (CI) UI tasks for transcript uploads and content ideas management. Strongly recommend splitting into Sprint 3a (Social + Email + Stats Operators + CI UI) and Sprint 3b (Funnels + ICP UI + Edge Cases).

**Deliverables**:
- CI-MKT-01 Social Media specialist Agent with cross-domain insights
- CI-MKT-02 Email specialist Agent with campaign analysis + AI drafting
- CI-MKT-03 Funnels specialist Agent with conversion analysis
- 4 Stats Updater Operators (Email, Social, Funnel, Comments) as Celery tasks
- ICP management UI and FastAPI endpoints
- Social media, email, and funnels dashboards
- Script generator, email composer, optimization suggestions UIs
- Soft delete on all mutable tables
- Content idea status lifecycle
- Stale data indicators with automatic refresh
- CI transcript upload page (drag-and-drop UI)
- CI content ideas management page with status lifecycle tracking

---

## Sprint 4 (Weeks 8-9): Marketing Specialists Batch 2

**Goal**: Ads, DM, and Offer specialists — complete Marketing department

| Task ID | Task | Owner | Points |
| ------- | ---- | ----- | ------ |
| M04-1 | Ads specialist agent class | `[BE]` | 3 |
| M04-2 | Ad analysis prompt | `[AI]` | 3 |
| M04-3 | Ad copy generation prompt | `[AI]` | 3 |
| M04-4 | FastAPI webhook endpoints (POST /ads, GET /ads) | `[BE]` | 2 |
| M04-5 | Register with Marketing Director | `[BE]` | 1 |
| M04-6 | Ads dashboard | `[FE]` | 5 |
| M04-7 | Ad copy generator UI | `[FE]` | 5 |
| M05-1 | DM specialist agent class | `[BE]` | 3 |
| M05-2 | DM analysis prompt | `[AI]` | 3 |
| M05-3 | DM template generation prompt | `[AI]` | 3 |
| M05-4 | FastAPI webhook endpoints (POST /dm, GET /dm) | `[BE]` | 2 |
| M05-5 | Register with Marketing Director | `[BE]` | 1 |
| M05-6 | DM dashboard | `[FE]` | 5 |
| M05-7 | DM template builder UI | `[FE]` | 5 |
| M06-1 | Offer specialist agent class | `[BE]` | 3 |
| M06-2 | Offer optimization prompt | `[AI]` | 5 |
| M06-3 | Offer creation prompt | `[AI]` | 3 |
| M06-4 | FastAPI webhook endpoints (POST /offers, GET /offers) | `[BE]` | 2 |
| M06-5 | Register with Marketing Director | `[BE]` | 1 |
| M06-6 | Offers dashboard | `[FE]` | 5 |
| M06-7 | Offer builder UI | `[FE]` | 5 |
| OPS-O1 | Offer Generator operator (Celery + Claude) | `[BE]` | 3 |
| OPS-O2 | Offer generation prompt | `[AI]` | 5 |
| OPS-O3 | Store to offers table | `[BE]` | 2 |
| OPS-O4 | FastAPI webhook endpoint (POST /offer-generate) | `[BE]` | 2 |
| OPS-SA1 | Ads Stats Updater (Celery task) | `[BE]` | 2 |

**Sprint 4 totals**: `[BE]` 27pts, `[FE]` 30pts, `[AI]` 25pts = **82pts**

**Acceptance Criteria**: All 6 Marketing specialists operational. Marketing Director can coordinate any specialist. Ad copy uses cross-domain insights. DM templates generated from ICP data. Offers optimized from pain points + wins.

**Dependencies**: Sprint 3 (Marketing batch 1, Stats Operators)

**Note**: Heavy sprint at 82pts. Consider splitting into Sprint 4a (Ads + DM) and Sprint 4b (Offers + Offer Generator).

**Deliverables**:
- CI-MKT-04 Ads specialist Agent with ROAS/CTR analysis and AI copy generation
- CI-MKT-05 DM specialist Agent with conversation analysis and template generation
- CI-MKT-06 Offer specialist Agent with optimization and creation
- CI-OPS-OFFER Offer Generator Operator (Celery task)
- Ads Stats Updater Operator
- Ads, DM, and Offers dashboards
- Ad copy generator, DM template builder, offer builder UIs
- All 6 Marketing specialists registered with Marketing Director
- Complete Marketing department operational

---

## Sprint 5 (Weeks 10-11): Sales Department

**Goal**: Sales Director + all 3 Sales specialists

| Task ID | Task | Owner | Points |
| ------- | ---- | ----- | ------ |
| DIR-S1 | Sales Director agent class with specialist routing | `[BE]` | 5 |
| DIR-S2 | Sales Director system prompt | `[AI]` | 3 |
| DIR-S3 | Shared table repository access | `[BE]` | 3 |
| DIR-S4 | Sales summary endpoint (FastAPI) | `[BE]` | 2 |
| DIR-S5 | Sales Director chat page | `[FE]` | 3 |
| DIR-S6 | Sales department dashboard | `[FE]` | 5 |
| S01-1 | Appointment Setting specialist agent class | `[BE]` | 5 |
| S01-2 | Conversation analysis prompt | `[AI]` | 5 |
| S01-3 | Script suggestions prompt | `[AI]` | 3 |
| S01-4 | GHL API integration (client list, appointment scheduling) | `[BE]` | 5 |
| S01-5 | FastAPI webhook endpoints (POST /appointments, GET /appointments) | `[BE]` | 2 |
| S01-6 | Register with Sales Director | `[BE]` | 1 |
| S01-7 | Appointments dashboard | `[FE]` | 5 |
| S01-8 | Conversation analytics charts | `[FE]` | 5 |
| S01-9 | Script suggestions UI | `[FE]` | 3 |
| S02-1 | Leads specialist agent class | `[BE]` | 5 |
| S02-2 | Leads query operations (via Repository) | `[BE]` | 5 |
| S02-3 | Leads aggregation logic (funnel, source breakdown) | `[BE]` | 5 |
| S02-4 | FastAPI webhook endpoints (GET /leads, POST /leads, PUT /leads/:id, DELETE /leads/:id) | `[BE]` | 3 |
| S02-5 | Register with Sales Director | `[BE]` | 2 |
| S02-6 | Leads dashboard page | `[FE]` | 3 |
| S02-7 | Lead volume chart | `[FE]` | 3 |
| S02-8 | Source breakdown chart | `[FE]` | 3 |
| S02-9 | Conversion funnel viz | `[FE]` | 5 |
| S02-10 | Leads data table | `[FE]` | 5 |
| S02-11 | Date & source filters | `[FE]` | 3 |
| S02-12 | Leads CRUD operations (create, edit, delete) | `[BE]` | 5 |
| S02-13 | Inline edit UI (React Query integration) | `[FE]` | 5 |
| S03-1 | Sales Call Analyzer specialist agent class | `[BE]` | 3 |
| S03-2 | Pain points extraction prompt | `[AI]` | 5 |
| S03-3 | Content ideas generation prompt | `[AI]` | 3 |
| S03-4 | Lead engagement linking (via Repository) | `[BE]` | 3 |
| S03-5 | Store results in Supabase | `[BE]` | 2 |
| S03-6 | FastAPI webhook endpoint (POST /call-analysis) | `[BE]` | 2 |
| S03-7 | Register with Sales Director | `[BE]` | 1 |
| S03-8 | Sales calls list page | `[FE]` | 5 |
| S03-9 | Call detail view | `[FE]` | 5 |
| S03-10 | Pain points feed component | `[FE]` | 3 |
| EC-09 | Pain point frequency dedup (contributing_transcripts array) | `[BE]` | 2 |
| EC-11 | Add member_id to call_transcripts table | `[BE]` | 1 |
| EC-12 | Lead-to-member conversion (Celery task) | `[BE]` | 3 |
| EC-14 | Transcript queue processor (Celery with concurrency limit) | `[BE]` | 3 |

**Sprint 5 totals**: `[BE]` 67pts, `[FE]` 61pts, `[AI]` 19pts = **147pts**

**Acceptance Criteria**: Sales Director coordinates all 3 specialists. Leads dashboard shows live data with CRUD. Sales calls extract pain points and content ideas. Appointment analytics from GHL. Central Intelligence can query Sales Director.

**Dependencies**: Sprint 2 (Transcriber for call analysis), Sprint 1b (auth, error handling)

**IMPORTANT**: This sprint is massive (147pts). **Must split into sub-sprints**:
- **Sprint 5a (Wk 10)**: Sales Director + Leads specialist + CRUD (DIR-S*, S02-*, EC-12) = ~75pts
- **Sprint 5b (Wk 11)**: Appointments + Sales Call Analyzer (S01-*, S03-*, EC-09, EC-11, EC-14) = ~72pts

**Deliverables**:
- CI-SLS-DIR Sales Director Agent with specialist routing
- CI-SAL-01 Appointment Setting specialist with GHL integration
- CI-SAL-02 Leads Database specialist with full CRUD
- CI-SAL-03 Sales Call Analyzer specialist with pain point extraction
- Sales department dashboard, leads dashboard, appointments dashboard, sales calls page
- Leads data table with inline editing, date/source filters, funnel visualization
- Pain points feed component (reusable across pages)
- Pain point frequency dedup, member_id on transcripts, lead-to-member conversion
- Async transcript queue processor (Celery)

---

## Sprint 6 (Weeks 12-13): Fulfillment Department

**Goal**: Fulfillment Director + all 4 Fulfillment specialists

| Task ID | Task | Owner | Points |
| ------- | ---- | ----- | ------ |
| DIR-F1 | Fulfillment Director agent class with specialist routing | `[BE]` | 5 |
| DIR-F2 | Fulfillment Director system prompt | `[AI]` | 3 |
| DIR-F3 | Shared table repository access | `[BE]` | 3 |
| DIR-F4 | Fulfillment summary endpoint (FastAPI) | `[BE]` | 2 |
| DIR-F5 | Fulfillment Director chat page | `[FE]` | 3 |
| DIR-F6 | Fulfillment department dashboard | `[FE]` | 5 |
| F01-1 | Members specialist agent class | `[BE]` | 3 |
| F01-2 | Member query operations (via Repository) | `[BE]` | 3 |
| F01-3 | FastAPI webhook endpoints (GET /members, POST /members) | `[BE]` | 2 |
| F01-4 | Register with Fulfillment Director | `[BE]` | 1 |
| F01-5 | Members directory page | `[FE]` | 5 |
| F01-6 | Member detail view | `[FE]` | 5 |
| F01-7 | Goals progress tracker | `[FE]` | 3 |
| F01-8 | Members CRUD operations (create, edit, delete) | `[BE]` | 3 |
| F01-9 | Members inline edit UI | `[FE]` | 3 |
| F02-1 | Coaching Call Analyzer specialist agent class | `[BE]` | 3 |
| F02-2 | Wins extraction prompt | `[AI]` | 5 |
| F02-3 | Pain points extraction prompt | `[AI]` | 3 |
| F02-4 | Content ideas generation prompt | `[AI]` | 3 |
| F02-5 | FastAPI webhook endpoint (POST /coaching-analysis) | `[BE]` | 2 |
| F02-6 | Register with Fulfillment Director | `[BE]` | 1 |
| F02-7 | Coaching calls page | `[FE]` | 5 |
| F02-8 | Wins feed component | `[FE]` | 3 |
| F02-9 | Content ideas feed | `[FE]` | 5 |
| F03-1 | Accountability specialist agent class | `[BE]` | 3 |
| F03-2 | Goals extraction prompt | `[AI]` | 5 |
| F03-3 | Progress tracking logic (via Repository) | `[BE]` | 5 |
| F03-4 | FastAPI webhook endpoint (POST /accountability-check) | `[BE]` | 2 |
| F03-5 | Register with Fulfillment Director | `[BE]` | 1 |
| F03-6 | Accountability page | `[FE]` | 5 |
| F03-7 | Progress charts | `[FE]` | 3 |
| F04-1 | Tech SOS specialist agent class | `[BE]` | 3 |
| F04-2 | Issue categorization prompt | `[AI]` | 3 |
| F04-3 | FastAPI webhook endpoints (POST /tech-sos, GET /tech-sos) | `[BE]` | 2 |
| F04-4 | Register with Fulfillment Director | `[BE]` | 1 |
| F04-5 | Tech SOS page | `[FE]` | 5 |
| F04-6 | Issue patterns dashboard | `[FE]` | 3 |
| EC-10 | Structured member goals with status tracking | `[BE]` | 3 |
| ERR-06 | Admin error monitoring dashboard | `[FE]` | 3 |
| CI-INT-01 | Integrate CI Content Calendar skill output with email scheduling (Celery task) | `[AI]` | 5 |
| CI-INT-02 | Configure ActiveCampaign integration endpoints (FastAPI) for email delivery | `[BE]` | 5 |
| CI-INT-03 | Set up Fireflies webhook → CI transcript ingestion automation (FastAPI listener) | `[BE]` | 3 |

**Sprint 6 totals**: `[BE]` 56pts, `[FE]` 56pts, `[AI]` 27pts = **139pts**

**Acceptance Criteria**: Fulfillment Director coordinates all 4 specialists. Coaching calls produce wins + pain points + content ideas. Accountability goals tracked over time. Tech SOS issues categorized. Central Intelligence can query Fulfillment Director. CI Content Calendar integrations operational. ActiveCampaign endpoints configured for email delivery. Fireflies webhook automation active for CI transcript ingestion.

**Dependencies**: Sprint 2 (Transcriber), Sprint 1b (auth, error handling)

**IMPORTANT**: This sprint is very heavy (139pts). Includes Central Intelligence (CI) integration tasks for content calendar and email delivery. **Must split into sub-sprints**:
- **Sprint 6a (Wk 12)**: Director + Members + Coaching + CI Tasks (DIR-F*, F01-*, F02-*, CI-INT-*) = ~78pts
- **Sprint 6b (Wk 13)**: Accountability + Tech SOS + Edge Cases (F03-*, F04-*, EC-10, ERR-06) = ~61pts

**Deliverables**:
- CI-FUL-DIR Fulfillment Director Agent with specialist routing
- CI-FUL-01 Members Database specialist with full CRUD
- CI-FUL-02 Coaching Call Analyzer specialist (wins, pain points, content ideas)
- CI-FUL-03 Accountability specialist with goal tracking
- CI-FUL-04 Tech SOS specialist with AI categorization
- Fulfillment department dashboard, members directory, coaching/accountability/tech-sos pages
- Wins feed, content ideas feed, goals progress tracker components
- Structured member goals with status lifecycle
- Admin error monitoring dashboard
- CI Content Calendar Celery task for email scheduling integration
- ActiveCampaign FastAPI integration endpoints for email delivery automation
- Fireflies webhook listener for CI transcript ingestion

---

## Sprint 7 (Weeks 14-15): Data Migration + Integration

**Goal**: Import existing data, cross-domain flows active, GHL sync

| Task ID | Task | Owner | Points |
| ------- | ---- | ----- | ------ |
| DM-1 | Data import Celery task (Airtable/GHL/Google Sheets → Supabase) | `[BE]` | 5 |
| DM-2 | Data mapping logic (transform legacy schema → new schema) | `[BE]` | 3 |
| DM-3 | Sync verification (record counts, spot-check samples) | `[BE]` | 2 |
| DM-4 | Data import admin page (trigger imports, view status) | `[FE]` | 3 |
| EC-13 | GHL sync conflict resolution (timestamp-based + conflict logging) | `[BE]` | 3 |

**Sprint 7 totals**: `[BE]` 13pts, `[FE]` 3pts = **16pts**

**Acceptance Criteria**: Existing data imported from Airtable/GHL/Google Sheets. Cross-domain data flows active across all departments. GHL sync handles conflicts.

**Dependencies**: Sprints 5-6 (all workers must be built)

**Note**: This is intentionally a lighter sprint to allow breathing room after the heavy Sprints 5-6. Use extra capacity for bug fixes and stabilization.

**Deliverables**:
- Data migration Celery task importing from Airtable/GHL/Google Sheets
- Data mapping logic and sync verification
- Admin import page for triggering imports and reviewing status
- GHL bidirectional sync with timestamp-based conflict resolution
- Cross-domain data flow fully operational (all departments feeding shared intelligence pool)

---

## Sprint 8 (Weeks 16-17): Central Intelligence Intelligence + Polish

**Goal**: Executive dashboard, business optimization, production hardening

| Task ID | Task | Owner | Points |
| ------- | ---- | ----- | ------ |
| Q6-1 | Enhanced Central Intelligence system prompt | `[AI]` | 5 |
| Q6-2 | Weekly digest Celery task (scheduled, aggregates all department data) | `[BE]` | 5 |
| Q6-3 | Persistent memory upgrade (Redis conversation history + context window optimization) | `[BE]` | 3 |
| Q6-4 | Executive dashboard (cross-department KPIs, trends) | `[FE]` | 8 |
| Q6-5 | Weekly focus widget | `[FE]` | 5 |
| Q6-6 | Notification system (alerts for important insights) | `[FE]` | 5 |
| Q6-7 | Error handling improvements (retry logic, fallbacks) | `[BE]` | 5 |
| Q6-8 | Responsive design polish | `[FE]` | 5 |
| SEC-06 | Webhook endpoint path obfuscation (randomized prefixes) | `[BE]` | 2 |
| SEC-07 | API key rotation mechanism (Supabase secrets) | `[BE]` | 2 |
| EC-02 | Circuit breaker pattern (external API outage protection) | `[BE]` | 3 |

**Sprint 8 totals**: `[BE]` 20pts, `[FE]` 23pts, `[AI]` 5pts = **48pts**

**Acceptance Criteria**: "What should we focus on this week?" returns actionable priorities. Executive dashboard shows cross-department KPIs. System degrades gracefully when external APIs are down. All ~25 agents registered and operational.

**Dependencies**: All previous sprints (all agents must be built)

**Deliverables**:
- Enhanced Central Intelligence system prompt with business optimization framework
- Scheduled weekly digest Celery task aggregating all department data
- Persistent memory system using Redis + conversation history
- Executive dashboard with cross-department KPIs, trends, and charts
- Weekly focus widget showing Central Intelligence's prioritized recommendations
- Notification system with alert badges for important insights
- Improved error handling and retry logic across all agents
- Responsive design polish across all pages
- Obfuscated FastAPI webhook paths preventing endpoint enumeration
- API key rotation mechanism for leaked credential recovery
- Circuit breaker pattern preventing cascading failures during external API outages

---

## Sprint Summary

| Sprint | Weeks | Focus | BE pts | FE pts | AI pts | Total |
| ------ | ----- | ----- | ------ | ------ | ------ | ----- |
| 1a | 1-2 | Foundation + Central Intelligence + 16 Tables | 18 | 16 | 3 | 37 |
| 1b | 3 | Auth + Error Handling Core | 12 | 13 | 0 | 25 |
| 2 | 4-5 | Marketing Director + Transcriber + ICP + CI Integration | 50 | 30 | 13 | 93 |
| 3 | 6-7 | Marketing Batch 1 (Social + Email + Funnels + Stats Ops + CI UI) | 34 | 46 | 21 | 101 |
| 4 | 8-9 | Marketing Batch 2 (Ads + DM + Offers + Offer Generator) | 27 | 30 | 25 | 82 |
| 5 | 10-11 | Sales Department (Director + 3 Specialists) | 67 | 61 | 19 | 147 |
| 6 | 12-13 | Fulfillment + CI Integrations (Director + 4 Specialists + Email/Fireflies) | 56 | 56 | 27 | 139 |
| 7 | 14-15 | Data Migration + Integration | 13 | 3 | 0 | 16 |
| 8 | 16-17 | Intelligence + Polish + Hardening | 20 | 23 | 5 | 48 |
| **Total** | **~17 weeks** | | **297** | **281** | **113** | **701** |

**Notes**:
- Total increased from 496 (v1.1 n8n plan) to ~701 points (v3.0 with Python + Claude SDK + CI integration)
- CI integration adds 49 story points across Sprint 2 (26 pts), Sprint 3 (10 pts), and Sprint 6 (13 pts)
- Sprints 5 and 6 must split into sub-sprints (5a/5b, 6a/6b) to be manageable
- Sprint 7 is intentionally light as a stabilization sprint
- Python + FastAPI + Claude SDK architecture replaces all n8n workflows with agent-based implementation
- Celery + Redis used for async task processing (Transcriber, Stats Updaters, Data Migration)
- Supabase (PostgreSQL) replaces n8n Data Tables as primary database
- SQLAlchemy ORM + Repository pattern provides consistent data access layer
- Claude SDK integration replaces OpenAI API calls for more consistent AI model usage

## Staffing Recommendations

### Minimum Team (1 developer)
- One full-stack developer handling all roles
- Timeline extends to ~30-40 weeks (more agents + AI tasks)
- Best for: Budget-constrained projects

### Recommended Team (2 developers)
- 1 Backend Developer (`[BE]` + `[AI]` tasks) — ~397 pts
- 1 Frontend Developer (`[FE]` tasks) — ~281 pts
- Timeline: ~17-20 weeks as planned
- Best for: Balanced speed and cost

### Fast Track Team (3 developers)
- 1 Backend Developer (`[BE]` tasks) — ~297 pts
- 1 Frontend Developer (`[FE]` tasks) — ~281 pts
- 1 AI/Integration Specialist (`[AI]` tasks) — ~113 pts
- Timeline: 17 weeks as planned (AI specialist works ahead on prompts)
- Best for: Fastest delivery

### Capacity Notes
- Sprints 3-6 are the heaviest block. Consider extending to 3-week sprints or adding a week buffer between Sales and Fulfillment.
- `[AI]` tasks peak in Sprints 3-6 (Marketing + Sales + Fulfillment prompt engineering). AI specialist should work 1-2 sprints ahead.
- Sprint 7 is deliberately light to absorb schedule slip from Sprints 5-6.
- Backend developer tasks include both FastAPI endpoints and Celery task implementation; parallelization helps reduce load.

---

## Risk Mitigation

| Risk | Mitigation |
| ---- | ---------- |
| Marketing tables empty at start | Seed with manual/sample data; real data flows when Sales/Fulfillment come online (Sprint 5-6) |
| Sprint 5/6 overload | Split into sub-sprints (5a/5b, 6a/6b); Sprint 7 acts as buffer |
| Supabase connection or query errors | Implement comprehensive error handling + Circuit breaker pattern (Sprint 8) |
| GHL API integration unstable | Abstract GHL calls behind Specialist agent (only CI-SAL-01 affected) |
| Claude API costs | Use claude-3-5-sonnet for Specialists/Operators, claude-3-opus for Directors/Central Intelligence |
| Whisper file size limit (25MB) | Add file size validation in Transcriber task (Sprint 2) |
| Database migration complexity | Dedicated Sprint 7 for data import with stabilization time |
| Cross-domain data consistency | PostgreSQL foreign keys + transactions via SQLAlchemy ensure integrity |
| Unauthorized access | Two-layer auth: Supabase JWT + protected FastAPI routes (Sprint 1b) |
| Silent agent failures | Error Handler agent + bee_error_log table + Sentry monitoring |
| Concurrent edit data loss | Optimistic locking via updatedAt + If-Match header (Sprint 2) |
| Duplicate form submissions | Idempotency keys + button disable on submit |
| Accidental data destruction | Soft delete with deleted_at + confirm dialogs for destructive actions |
| External API outages | Circuit breaker pattern + exponential backoff retry (Sprint 8) |
| Agent routing failures | Director system prompts include fallback: escalate to Central Intelligence if specialist unavailable |
| Celery task queue backlog | Monitor Redis queue depth; scale workers if needed |
| WebSocket connection drops | Implement reconnection logic with exponential backoff |

---

# ENHANCED SECTIONS

## Risk Mitigation Strategies

Detailed mitigation plan for each identified risk, with escalation paths, resolution deadlines, and fallback plans.

### Sprint-Specific Risks

#### Sprint 1a/1b: Foundation + Auth (Weeks 1-3)

| Risk ID | Risk | Probability | Impact | Escalation | Deadline | Fallback Plan |
| --- | --- | --- | --- | --- | --- | --- |
| R1-1 | Supabase Auth integration complex | Medium | High | Consult Supabase docs + community | End Week 2 | Use simpler token-based auth instead |
| R1-2 | FastAPI middleware and SQLAlchemy ORM learning curve | Medium | Medium | Pair backend dev with FastAPI expert | End Week 2 | Use simpler data access layer (raw SQL) |
| R1-3 | Base Agent class design unclear | Low | Medium | Design review with team | End Week 1 | Implement minimal base class, refactor later |
| R1-4 | Supabase schema migration issues | Low | High | Test migrations in staging first | End Week 2 | Recreate schema manually if migration fails |

#### Sprint 2: Marketing Director + Transcriber (Weeks 4-5)

| Risk ID | Risk | Probability | Impact | Escalation | Deadline | Fallback Plan |
| --- | --- | --- | --- | --- | --- | --- |
| R2-1 | Transcriber fails on large files (>25MB) | Medium | Medium | Add file size validation + HEAD check | Mid Week 5 | Document max file size, ask users to compress |
| R2-2 | Whisper API rate limit hit during testing | Low | Medium | Stagger test runs, use queuing | Mid Week 5 | Pre-upload test videos in batches |
| R2-3 | Claude API prompts too vague | Medium | Medium | AI specialist refines prompt with real data | Mid Week 5 | Use template prompts from Anthropic docs |
| R2-4 | Marketing Director not routing to specialists correctly | Medium | High | Test routing logic with explicit prompts | End Week 5 | Add explicit operation parameter override |

#### Sprint 3: Marketing Batch 1 (Weeks 6-7)

| Risk ID | Risk | Probability | Impact | Escalation | Deadline | Fallback Plan |
| --- | --- | --- | --- | --- | --- | --- |
| R3-1 | Sprint 3 at 101pts TOO HEAVY | High | Critical | SPLIT into 3a (Social + Email + Stats) + 3b (Funnels + ICP UI) | Mid Week 6 | Defer Funnels + ICP UI to Sprint 4 |
| R3-2 | Multiple specialists trying to update same table | Medium | Medium | Implement optimistic locking (EC-01) + conflict resolution | Mid Week 7 | Add manual conflict review step |
| R3-3 | Content idea status transitions break | Low | Medium | Test status workflow with real transitions | Mid Week 7 | Simplify to 3 states (new, used, archived) |
| R3-4 | Stats operators pulling stale data from Supabase | Medium | Medium | Add refresh buttons + stale data indicators | End Week 7 | Use 1-hour cache TTL as default |

#### Sprint 4: Marketing Batch 2 (Weeks 8-9)

| Risk ID | Risk | Probability | Impact | Escalation | Deadline | Fallback Plan |
| --- | --- | --- | --- | --- | --- | --- |
| R4-1 | Offer optimization prompt underperforms | Medium | Medium | AB test different prompt variations | Mid Week 9 | Use Offer Generation prompt as fallback |
| R4-2 | DM templates too generic for platform-specific use | Low | Medium | Add platform field to template generation | End Week 9 | Store platform tags separately |
| R4-3 | Offer Generator not creating enough variants | Low | Medium | Increase Claude API call count (costs +$) | End Week 9 | Limit to 3 offers per generation |

#### Sprint 5: Sales (Weeks 10-11)

| Risk ID | Risk | Probability | Impact | Escalation | Deadline | Fallback Plan |
| --- | --- | --- | --- | --- | --- | --- |
| R5-1 | **Sprint 5 at 147pts CRITICAL OVERLOAD** | **Critical** | **Critical** | **MUST SPLIT 5a/5b immediately** | **Start Week 10** | **Defer Appointments + Sales Calls to Sprint 6** |
| R5-2 | GHL API integration unstable | Medium | High | Test GHL calls extensively, add error handling | Mid Week 10 | Switch to manual sync (CSV upload) |
| R5-3 | Leads database huge (1000s of records) | Medium | Medium | Add pagination + filtering on frontend | Mid Week 10 | Limit initial load to 100 records |
| R5-4 | Lead-to-member conversion logic mismatches | Medium | High | Validate conversion logic with business rules | End Week 11 | Manual member creation from confirmed sales |
| R5-5 | Transcript queue processor causes performance issues | Low | Medium | Tune Celery concurrency, add monitoring | Mid Week 11 | Process one transcript at a time (slower but stable) |

#### Sprint 6: Fulfillment (Weeks 12-13)

| Risk ID | Risk | Probability | Impact | Escalation | Deadline | Fallback Plan |
| --- | --- | --- | --- | --- | --- | --- |
| R6-1 | **Sprint 6 at 139pts HEAVY** | **High** | **High** | **MUST SPLIT 6a/6b immediately** | **Start Week 12** | **Defer Tech SOS + Accountability edge cases** |
| R6-2 | Member goals structure too complex | Medium | Medium | Simplify to goal name + status | Mid Week 12 | Use JSON field initially, migrate later |
| R6-3 | Accountability comparison logic fragile | Medium | Medium | Add validation + manual review step | Mid Week 13 | Alert on goal mismatch, require verification |
| R6-4 | Tech SOS categorization inaccurate | Low | Medium | Refine categorization rules with real issues | Mid Week 13 | Manual categorization fallback |

#### Sprint 7: Data Migration (Weeks 14-15)

| Risk ID | Risk | Probability | Impact | Escalation | Deadline | Fallback Plan |
| --- | --- | --- | --- | --- | --- | --- |
| R7-1 | Data mapping logic breaks on edge cases | Medium | High | Test with full dataset from Airtable | Mid Week 14 | Manual data cleanup after import |
| R7-2 | GHL sync conflicts (stale data) | Medium | Medium | Implement timestamp-based resolution (EC-13) | End Week 14 | Prioritize recent updates, alert on conflicts |
| R7-3 | Data import takes longer than Sprint 7 | Low | Medium | Pre-test export/import cycle | Early Week 14 | Run import async, monitor progress in admin UI |

#### Sprint 8: Intelligence + Polish (Weeks 16-17)

| Risk ID | Risk | Probability | Impact | Escalation | Deadline | Fallback Plan |
| --- | --- | --- | --- | --- | --- | --- |
| R8-1 | Central Intelligence weekly digest too slow (>10s) | Medium | Medium | Optimize data aggregation, cache results | Mid Week 16 | Run digest async, email results instead of realtime |
| R8-2 | Circuit breaker causes user confusion | Low | Medium | Add clear messaging: "Retrying connection" | End Week 16 | Disable circuit breaker if too noisy |
| R8-3 | Executive dashboard too crowded | Low | Low | Move secondary charts to tabs | End Week 17 | Simple KPI card view as default |

---

## Contingency Plans: Scenario-Based

### Scenario 1: Claude API Unavailable (Outage or Quota Exceeded)

**Trigger Condition**: Claude API returns 500+ error or 429 rate limit for > 5 consecutive requests

**Immediate Actions** (within 15 min):
1. Circuit breaker activates: Stop sending requests to Claude API
2. Show user message: "AI features temporarily offline. Serving cached results."
3. Switch AI responses to cached results from last 24 hours
4. Alert ops team: Slack message + email + Sentry alert

**Monitoring** (ongoing):
- Check Anthropic status page every 5 minutes
- Log all attempts, plan recovery
- Escalate to PagerDuty if outage > 1 hour

**Long-Term Resolution** (hours):
- If outage on Anthropic side: Wait for recovery + test resumption
- If quota exceeded: Reduce model usage (switch to claude-3-5-sonnet instead of claude-3-opus), increase API budget
- If API key invalid: Rotate to backup key (store in Supabase secrets)

**Fallback Plan**:
- Use cached responses for non-critical features (script generation, offer optimization)
- Disable non-critical features temporarily
- Notify user: "AI features degraded; some features may not work"

**Recovery**:
- Once Claude API recovers: Circuit breaker tests with 1 request → if success, resume normal
- Backfill missed insights from queued requests

---

### Scenario 2: Database Migration Delays

**Trigger Condition**: Data import takes > 50% longer than planned, or > 20% of data fails validation

**Immediate Actions** (within 1 day):
1. Stop new data entry into Airtable (freeze current state)
2. Switch read-only mode: Agents can query but not write
3. Debug data mapping logic, identify failed records
4. Check Supabase query logs for issues

**Contingency Actions** (if expected to delay > 1 week):
1. Roll back to previous day's backup (lose recent data entry)
2. Resume with manual + automated sync (hybrid approach)
3. Set realistic deadline (add 1-2 weeks to plan)
4. Prioritize core data (leads, members, transcripts) over secondary (comments, stats)

**Fallback Plan**:
- Keep current (legacy) system running in parallel
- Don't wait for perfect migration: Accept 80% completeness, fix remaining manually post-launch
- Use "data synchronization" mode: Both systems live until cutover week

**Recovery**:
- Once data mapping fixed: Re-run import with corrected logic
- Compare record counts: new system vs legacy
- Spot-check 10 records per table for accuracy
- Launch with acknowledgment: "Some data may not be 100% current; synchronizing daily"

---

### Scenario 3: Auth Implementation Overruns (Supabase Auth + FastAPI Middleware)

**Trigger Condition**: Auth features hit Week 3 with < 50% completion, or blocking critical path

**Immediate Actions** (end of Week 3):
1. Pause sprint goals, focus 100% on auth completion
2. Simplify auth scope:
   - Defer "Remember me" (7-day session) to Sprint 8
   - Defer account lockout (5 failed attempts) to Sprint 8
   - Keep: email/password login + JWT tokens
3. Use simpler FastAPI middleware (basic bearer token, defer HMAC to Sprint 8)

**Contingency Actions** (if still blocked mid-Week 3):
1. Implement temporary auth (demo-only, no validation)
2. Focus on building agents (non-auth-dependent work)
3. Circle back to auth in Week 4

**Fallback Plan**:
- Use Supabase Auth default session management (no custom JWT)
- Skip advanced security features for now
- Rebuild auth properly post-launch (Sprint 8)

**Recovery**:
- Once basic auth working: Add advanced features incrementally
- Test with real user account
- Document auth flow for future improvements

---

### Scenario 4: Scope Creep from Client

**Trigger Condition**: Client requests new features mid-sprint, or adds high-priority requirements

**Immediate Actions** (within 1 day):
1. Halt sprint work, gather requirements in detail
2. Estimate new feature points
3. Show client impact: "If we add X, we must defer Y (add 2 weeks)"
4. Get explicit trade-off decision from client

**Options**:
- **Option A**: Add feature, extend timeline (delay launch by X weeks)
- **Option B**: Defer feature to post-launch (Phase 2)
- **Option C**: Remove lower-priority feature (swap scope)

**Fallback Plan**:
- Maintain sprint commitment: Complete planned features on schedule
- Create "Phase 2 backlog" for scope creep items
- Launch with Phase 1 as planned
- Deliver Phase 2 features in follow-up sprints

**Recovery**:
- Weekly check-in with client: confirm scope is locked
- Any new requests go to Phase 2
- Use written scope agreement to prevent disputes

---

### Scenario 5: Key Developer Unavailable

**Trigger Condition**: Backend Developer or Frontend Developer becomes unavailable (sick, emergency, quit)

**Immediate Actions** (within 1 day):
1. Assess which tasks are blocked (high dependency)
2. Redistribute tasks to remaining team
3. If full-time replacement not available: Reduce sprint scope

**Contingency Actions** (depending on role):

**If Backend Developer unavailable (affects most work)**:
- Frontend developer pauses, waits for APIs
- Freeze new agent features mid-sprint
- Complete existing agents to 100% done
- Postpone remaining features to next sprint

**If Frontend Developer unavailable**:
- Backend developer continues with agents + APIs
- Create stub dashboards (placeholder UI)
- Frontend developer completes UI in next sprint

**If AI Specialist unavailable**:
- Use template prompts from Anthropic docs
- Iterate on prompts in next sprint
- Agents still functional, just less optimized

**Fallback Plan**:
- Hire contract contractor within 1 week
- Temporarily reduce sprint scope by 30%
- Push non-critical features to Sprint 8

**Recovery**:
- Once new dev onboarded: Resume full sprint scope
- Pair new dev with existing team for knowledge transfer
- Update documentation for handoff

---

## Contingency Plans Summary Table

| Scenario | Probability | Time to Trigger | Days to Resolve | Impact | Team Lead |
| --- | --- | --- | --- | --- | --- |
| Claude API outage | 5% | Anytime | 0.5 - 8 hours | Medium (cached mode) | Backend Lead |
| Database migration delay | 20% | Sprint 7 | 1-7 days | High (defer features) | Backend Lead |
| Auth implementation delay | 15% | Sprint 1b | 1-3 days | Critical (blocks launch) | Backend Lead |
| Scope creep (client request) | 40% | Any sprint | 0.25 days (decision) | Medium (timeline impact) | Project Manager |
| Key developer unavailable | 10% | Any sprint | 1-7 days | Critical (schedule impact) | Project Manager |
| Whisper file size exceeded | 8% | Sprint 2 | 0.5 days | Low (validation added) | Backend Lead |
| Circuit breaker false positives | 5% | Sprint 8 | 1-2 days | Low (toggle option) | Backend Lead |
| Data validation fails at import | 15% | Sprint 7 | 3-5 days | High (defer launch) | Backend Lead |

---

## Sprint Retrospective Template

To be completed at end of each sprint. Helps identify patterns, improve velocity, and track improvements.

### Section 1: Metrics

```
Sprint: [5a, 5b, 6a, etc.]
Duration: 2 weeks (10 working days)
Planned Points: [X]
Completed Points: [Y]
Completion Rate: [Y/X %]
```

**Velocity Tracking**:
| Sprint | Planned | Completed | Rate | Trend |
| --- | --- | --- | --- | --- |
| 1a | 37 | 37 | 100% | Baseline |
| 1b | 25 | 25 | 100% | Stable |
| 2 | 93 | 86 | 92% | -8% (Transcriber + API integration complex) |
| 3 | 101 | 87 | 86% | -6% (prompt engineering iterations) |

### Section 2: What Went Well

List 3-5 wins from the sprint:

1. **[Feature name]** — Completed 2 days early. Implementation was straightforward.
2. **[Process improvement]** — Daily standup reduced blockers from 5 to 2 per day.
3. **[Team collaboration]** — Frontend + backend pairing for WebSocket integration accelerated delivery.
4. **[Unexpected success]** — Claude API integration simpler than expected; only 1 day of debugging needed.
5. **[Customer feedback]** — User loved the Leads dashboard; minimal revision requests.

### Section 3: What Didn't Go Well

List 2-4 challenges and root causes:

1. **[Feature name] overrun** — Estimated 5pts, took 8pts.
   - Root cause: Underestimated prompt engineering iterations (2 days of testing).
   - Fix: Add AI review day to prompt estimates; allocate +40% for iteration.

2. **[Process bottleneck]** — API client changes broke 3 tests.
   - Root cause: Insufficient test coverage + communication gap between backend + frontend.
   - Fix: Code review required before API changes; add integration tests.

3. **[Blocker]** — Waiting for GHL API docs delayed S01 Appointments by 1 day.
   - Root cause: Didn't pre-research API beforehand.
   - Fix: Pre-research all external APIs in Sprint 0.

4. **[Tech debt]** — Prompts not version-controlled; hard to track changes.
   - Root cause: No prompts Git repo.
   - Fix: Create `/prompts` directory in repo; version all prompt changes.

### Section 4: Action Items (Next Sprint)

List specific changes to implement:

| Action | Owner | Deadline | Status |
| --- | --- | --- | --- |
| Create AI prompt versioning system | AI Specialist | Sprint 4 start | Pending |
| Add integration tests for API client | Backend Lead | Sprint 4 start | Pending |
| Pre-research GHL API (S01) | Backend Developer | Before Sprint 5 | Pending |
| Adjust point estimates: +40% for prompts | Project Manager | Ongoing | Active |
| Document GHL API integration patterns | Backend Developer | Sprint 5 end | Pending |

### Section 5: Velocity Forecast

Based on completion rate, forecast future sprints:

```
Completed 92pts in Sprint 2 (planned 93pts)
Completed 87pts in Sprint 3 (planned 101pts, -14% shortfall)
Average velocity: (92 + 87) / 2 = 89.5pts

Sprint 4 planned: 82pts
Forecast: 82pts * 89% = 73pts

Sprint 5a planned: 75pts
Forecast: 75pts * 89% = 67pts

Risk: At 89% velocity, Sprint 5a may slip 1-2 days. Recommend 1-week buffer before Sprint 5b.
```

### Section 6: Demo/Review Notes

Notes from sprint demo to stakeholder:

```
Attendees: Greg (client), Frontend Lead, Backend Lead, Project Manager

Demos:
- Marketing batch 1 (Social + Email + Funnels) — clients loved the analytics
- Feedback: "Can we add export to CSV?" → Added to Phase 2

Issues raised:
- Content ideas feed was confusing (duplicate rows) → Fixed soft delete logic

Next priorities:
- Sprint 4: Complete Marketing batch 2 (Ads, DM, Offers)
- Client wants Leads dashboard before Sales specialists → Prioritize in Sprint 5a
```

### Section 7: Lessons Learned

Longer-form reflections:

**What we learned**:
1. Prompt engineering iterations are the biggest unknown variable. AI tasks need +40% buffer.
2. Pre-research external APIs (GHL, Whisper, Supabase) in Sprint 0 to avoid surprises.
3. Backend + frontend pairing sessions are highly effective (2x velocity for integration tasks).
4. Skeleton loaders + empty states increase perceived speed; users prefer waiting over blank screens.
5. Soft delete edge cases (with-deleted vs without-deleted queries) need explicit testing.
6. Claude SDK integration smoother than manual API calls; consider model routing for cost optimization.

**How we'll improve**:
1. AI tasks: Add "prompt iteration" as a task; estimate separately from implementation.
2. API research: Create pre-sprint API checklist; verify access, rate limits, auth before sprint starts.
3. Pairing: Schedule 1-2 pairing sessions per sprint for high-dependency tasks (not all work).
4. Testing: Add integration tests for data layer (soft delete, optimistic locking, etc.).
5. Documentation: Keep living prompt changelog; tie to Git commits.
6. Celery monitoring: Set up task queue alerts; monitor Redis depth to prevent backlog buildup.

---

## Quality Gates per Sprint

Checklist to verify before moving to next sprint. If any gate fails, extend sprint or fix first.

### Gate 1: Code Quality

- [ ] All code changes code-reviewed by at least 1 team member
- [ ] No `TODO` or `FIXME` comments left behind (or tracked in Issues)
- [ ] No console.error/console.log left in production code
- [ ] Test coverage for new features: >= 80%
- [ ] No TypeScript errors (`npm run type-check` passes)
- [ ] No ESLint warnings (`npm run lint` passes)
- [ ] All FastAPI endpoints match OpenAPI spec
- [ ] Python code passes black formatter + pylint checks

**Owner**: Tech Lead
**Failure Action**: Tag issues, schedule follow-up tasks for next sprint; don't block sprint completion

### Gate 2: Testing & QA

- [ ] All new features manually tested by QA
- [ ] All critical paths tested end-to-end (user login → agent query → data save)
- [ ] Performance baseline met (page load < 2s, API response < 5s)
- [ ] No regressions in existing features (smoke test)
- [ ] Error scenarios tested (network down, timeout, 500 error)
- [ ] Mobile responsiveness verified (Chrome DevTools)
- [ ] Accessibility check (WAVE tool, keyboard navigation)
- [ ] WebSocket streaming tested with large payloads

**Owner**: QA Lead
**Failure Action**: Log bugs, prioritize by severity; P0 bugs block sprint, P1/P2 go to backlog

### Gate 3: Agent Validation

- [ ] All Python agent classes instantiate without errors
- [ ] All agents tested: POST request → agent query → response received
- [ ] Error handlers registered on all new agents
- [ ] Tool definitions properly registered (agent can call tools)
- [ ] Claude API calls working (model responses received)
- [ ] Rate limiting tested (concurrent requests within quota)
- [ ] Celery tasks enqueued and processed successfully

**Owner**: Backend Lead
**Failure Action**: Fix validation errors, test again; don't deploy if validation fails

### Gate 4: Documentation

- [ ] Agent system prompts documented (README in agents/ folder)
- [ ] API endpoint documentation updated (OpenAPI)
- [ ] Prompt changes documented (prompt changelog)
- [ ] Configuration updated (env vars, Supabase schema)
- [ ] Deployment notes written (what to deploy, order, manual steps)
- [ ] CHANGELOG.md updated with sprint changes
- [ ] Celery task queue documentation updated

**Owner**: Tech Lead / Documentation Owner
**Failure Action**: Add to task list, complete before release

### Gate 5: Security

- [ ] No secrets in code (API keys, passwords) — use env vars
- [ ] JWT validation on all protected routes
- [ ] Auth required on all protected FastAPI endpoints
- [ ] CORS headers correct (only allow app origin)
- [ ] Rate limiting tested (attempted abuse, rate limit triggered)
- [ ] Soft delete tested (deleted records don't appear in queries)
- [ ] SQL injection / prompt injection tested (inputs sanitized)
- [ ] Supabase RLS policies configured correctly

**Owner**: Security Lead / Tech Lead
**Failure Action**: Fix before sprint completion; don't deploy if security issues

### Gate 6: Data Integrity

- [ ] Optimistic locking tested (concurrent edits handled)
- [ ] Soft deletes work correctly (no orphaned records)
- [ ] Backup created (daily Supabase backup)
- [ ] Data consistency verified (shared table updates visible across agents)
- [ ] No duplicate transcripts (SHA-256 dedup working)
- [ ] Idempotency tested (duplicate requests result in single operation)
- [ ] Foreign key constraints working (cascade deletes as intended)

**Owner**: Backend Lead
**Failure Action**: Fix data consistency issues before moving to next sprint

### Gate 7: Performance

- [ ] Page load time: < 2 seconds (measured via lighthouse)
- [ ] API response time: < 5 seconds (excluding Whisper)
- [ ] Whisper transcription: < 2 min for 30-min video (baseline)
- [ ] Database query time: < 1 second (measured in slow logs)
- [ ] Memory usage: No leaks (Chrome DevTools → Memory → take heap snapshots)
- [ ] Bundle size: < 500KB (gzip, excluding vendor libs)
- [ ] Celery task processing latency: < 30s for typical tasks

**Owner**: Tech Lead
**Failure Action**: Profile bottleneck, optimize before sprint completion

### Gate 8: Deployment Readiness

- [ ] Deployment runbook written and tested
- [ ] Rollback procedure tested (restore from backup, verify)
- [ ] All dependencies documented (Python version, FastAPI, Claude SDK version)
- [ ] Staging environment matches production
- [ ] Smoke test checklist completed (login, Central Intelligence chat, agent query)
- [ ] Monitoring + alerting configured (error rate, response time, Claude API usage)
- [ ] Support runbook updated (troubleshooting common issues)
- [ ] Sentry monitoring configured for error tracking

**Owner**: DevOps Lead
**Failure Action**: Complete before sprint demo; don't release if gates fail

### Gate 9: Stakeholder Sign-Off

- [ ] Sprint demo completed (features demoed to client)
- [ ] Client feedback captured (change requests documented)
- [ ] No blocking feedback (P0 issues resolved, P1/P2 documented)
- [ ] Backlog updated (new requests added to Phase 2)
- [ ] Timeline confirmed (on track, no surprises)

**Owner**: Project Manager
**Failure Action**: Resolve blocking feedback before next sprint starts

---

### Quality Gate Scoring

If ALL gates pass: **READY TO MOVE TO NEXT SPRINT**
If 7/9 gates pass: **MOVE WITH CAUTION** (monitor closely, plan fixes)
If < 7/9 gates pass: **DO NOT MOVE** (extend sprint or defer features)

**Gate Status Report** (end of each sprint):

```
Sprint 3 Gate Status:
  Code Quality: PASS (all lints, no TODOs)
  Testing & QA: PASS (85% coverage, no regressions)
  Agent Validation: PASS (all agents tested)
  Documentation: FAIL (prompts not documented) → Task added to Sprint 4
  Security: PASS (auth tested, rate limiting working)
  Data Integrity: PASS (soft deletes, dedup working)
  Performance: PASS (all page loads < 2s)
  Deployment Readiness: PASS (runbook tested)
  Stakeholder Sign-Off: PASS (demo completed, feedback captured)

Summary: 8/9 gates passed. READY TO MOVE TO SPRINT 4.
Action: Complete prompt documentation early in Sprint 4.
```
