# Product Requirements Document (PRD)
## Central Intelligence / Central Intelligence AI Business Automation System

**Document Version**: 3.0.0
**Date**: March 29, 2026
**Status**: ACTIVE - Sprint Planning Phase
**Project Duration**: ~17 weeks (8 sprints across Marketing, Sales, Fulfillment departments)
**Total Scope**: 194 features, 635 story points, 25+ AI worker agents, 33+ API endpoints, Supabase PostgreSQL backend with SQLAlchemy ORM

**Changelog - v3.0.0**:
- **MAJOR**: Migrated from n8n workflow platform to Python + Claude SDK agentic architecture
- Replaced n8n webhook endpoints with FastAPI REST endpoints (async)
- Replaced n8n AI Agent nodes with Python agent classes using Anthropic Claude SDK
- Replaced n8n Data Tables with Supabase PostgreSQL tables + SQLAlchemy ORM (Repository pattern)
- Added Celery + Redis for async task queue and agent execution
- Added WebSocket endpoints for streaming Central Intelligence chat responses
- Upgraded to Sentry + custom agent observability for monitoring
- Central Intelligence subsystem now integrated as Python agents within Central Intelligence architecture

---

## Executive Summary

### The Problem

The business currently operates with **isolated, single-purpose AI tools**:
- Custom GPTs for email writing, social media scripts, funnel analysis, ads copy
- Separate systems for lead management, appointment setting, sales call analysis
- Disconnected member databases, coaching call tracking, accountability monitoring
- **No cross-domain intelligence** — marketing workers don't know about sales pain points, fulfillment wins aren't driving content ideas, decision-making is fragmented

This creates:
- **Siloed insights**: A social media specialist can't see what sales calls revealed about customer pain points
- **Redundant analysis**: Email specialist and funnel specialist analyze the same problems independently
- **Missed optimization opportunities**: No unified view of business health or strategic priorities
- **Manual data flows**: Transcripts, analytics, insights flow manually between spreadsheets and databases
- **CEO decision paralysis**: Business owner (Greg) can't ask a single AI "what should we focus on this week?" across all departments

### The Solution: Central Intelligence

A **unified AI automation platform** organized as a multi-tier intelligence hierarchy with:

**3-Level Hierarchy**:
- **Central Intelligence** (CEO level): Cross-department orchestrator answering strategic business questions
- **3 Directors** (Department heads): Marketing, Sales, Fulfillment — each coordinating 3-6 specialists
- **15+ Specialists** (Domain experts): Social media, email, funnels, ads, DM, offers, leads, appointments, sales analysis, member tracking, coaching, accountability, tech support
- **7 Operators** (Shared utilities): Transcriber, ICP generator, offer generator, stats updaters
- **Central Intelligence Engine**: A marketing intelligence subsystem that transforms call transcripts (sales, coaching, discovery, accountability) into structured Voice of Customer (VOC) data. Powers content calendars, email writing, and marketing strategy with real customer language. Runs as integrated Python agents and feeds intelligence into the Marketing department.

**Key Innovation**: A **shared intelligence pool** where all specialists read from common Supabase tables (pain points, wins, objections, content ideas, ICPs, offers, goals) — enabling marketing to write DMs informed by sales pain points, fulfillment to generate content from wins, leadership to make data-driven decisions.

### Business Value

| Metric | Impact |
|--------|--------|
| **Time Savings** | ~50 hours/week of manual analysis, transcription, copywriting |
| **Decision Quality** | Cross-domain insights → better strategic priorities |
| **Content Generation** | Email, social, ads informed by real customer data, not guessing |
| **Scalability** | Add new worker in 1-2 days instead of building custom GPT |
| **Data Accuracy** | Single source of truth (Supabase PostgreSQL) instead of scattered spreadsheets |
| **Team Adoption** | Single web interface vs. switching between 5+ tools |

### Timeline

**~17 weeks** across 8 two-week sprints (plus 1 auth/error handling sprint):
- Sprint 1a (Wk 1-2): Foundation + Central Intelligence shell + Supabase tables + FastAPI endpoints
- Sprint 1b (Wk 3): Authentication + Error handling
- Sprints 2-4: Marketing department (6 specialists)
- Sprint 5: Sales department (3 specialists + appointment/leads/calls)
- Sprint 6: Fulfillment department (4 specialists + members/coaching/accountability/tech support)
- Sprint 7: Data migration + Integration
- Sprint 8: Executive intelligence + Polish

---

## Section 1: Business Context

### Company Profile

**Organization**: Marketing/Sales/Fulfillment business
**Current State**:
- Multiple custom GPTs running independently
- Lead database in Airtable
- Call transcripts collected manually
- Analytics in Google Sheets
- Email, social media, ad performance tracked in various databases
- No unified business intelligence

**Size**: Solo founder (Greg) + distributed team
**Success Metric**: "Give Greg one AI to ask all business questions"

### Current State Assessment

| Department | Current Tools | Data Source | Manual Steps |
|------------|---------------|-------------|--------------|
| **Marketing** | 4 custom GPTs | Airtable, Google Sheets, LinkedIn | Email stats import, social upload, ad copy entry |
| **Sales** | 2 custom GPTs | Airtable, GoHighLevel | Lead entry, appointment notes, call transcription |
| **Fulfillment** | 1 custom GPT | Airtable, Slack | Member database, call notes, goal tracking |
| **Cross-Domain** | None | N/A | Greg manually synthesizes insights |

**Pain Points**:
- Transcription is 100% manual (Greg uses Cockatoo, then copies to appropriate location) — *partially addressed by Central Intelligence's Transcript Processor skill (TXT/PDF/DOCX ingestion with 2-pass AI extraction)*
- Analytics require switching between 5+ tools to see full picture
- Content ideas generated in vacuum (social doesn't know sales pain points)
- Sales call insights (pain points, objections) are trapped in transcripts
- Coaching wins aren't being used for marketing inspiration
- No "what should we focus on?" — Greg decides based on gut feeling

### Desired State

One **unified Central Intelligence** where:
1. Greg asks Central Intelligence: "What should we focus on this week?"
2. Central Intelligence queries 3 Directors (Marketing, Sales, Fulfillment)
3. Each Director pulls from all Specialists and cross-domain intelligence
4. Central Intelligence synthesizes: "Your top 3 priorities are [data-driven recommendations]"

**All data flows are automated**:
- Sales calls transcribed → routed to analyzer → pain points → shared intelligence pool
- Coaching calls analyzed → wins extracted → available for marketing content ideas
- Email open rates imported → email specialist informed → better subject lines
- Member goals tracked → accountability analyzer watches progress → fulfillment director alerts if at risk

---

## Section 2: Stakeholders & User Personas

### Primary Stakeholder

**Greg** (Business Owner / Primary User)
- **Goals**:
  - Get strategic business insights without context switching
  - Make decisions based on cross-department data, not gut feeling
  - Automate 50+ hours/week of manual analysis
- **Pain Points**:
  - Fragmented tools require constant context switching
  - Can't see holistic picture fast enough
  - Manually transcribing calls burns hours weekly
- **Success Criteria**:
  - "Ask Central Intelligence anything, get actionable answer"
  - All departments' data flows automatically
  - Weekly digest shows what to focus on

### Secondary Stakeholders

**Team Members** (Marketing specialist, Sales person, Fulfillment coach)
- **Goals**:
  - See department-level dashboards and metrics
  - Access AI suggestions for their specialty
  - Use shared intelligence (pain points, wins, content ideas) in their work
- **Interaction Pattern**:
  - Open department dashboard (e.g., `/marketing`)
  - Use specialist AI tools (script generator, email composer, ICP viewer)
  - Add feedback to system (new pain point, content idea, win)

### System Actors (AI Workers)

**Central Intelligence** — CEO-level orchestrator
- Knows all 3 departments, cross-domain data
- Responds to strategic questions
- Prioritizes business opportunities
- Surfaces critical alerts

**Directors** (3)
- **Marketing Director**: Coordinates 6 marketing specialists, knows domain metrics
- **Sales Director**: Coordinates 3 sales specialists, knows pipeline health
- **Fulfillment Director**: Coordinates 4 fulfillment specialists, knows member success

**Specialists** (15)
- Deep domain expertise in one area
- Read from shared intelligence pool
- Generate content, analyze data, extract insights
- Specialist examples: Email, Social Media, Funnels, Ads, DM, Offers (Marketing); Appointments, Leads, Sales Calls (Sales); Members, Coaching, Accountability, Tech SOS (Fulfillment)

**Operators** (7 shared "floaters")
- Single-purpose utilities
- Shared across departments
- Examples: Call Transcriber (converts video→text), ICP Generator, Offer Generator, Stats Updaters

---

## Section 3: Product Scope — MVP

### In Scope (Phase 1: Foundation + Marketing + Sales + Fulfillment)

**Core Infrastructure**:
- Central Intelligence orchestrator (CEO-level AI chat)
- 3 Department Directors with AI coordination
- 15+ Domain Specialists across 3 departments
- 7 Shared Operators (transcriber, ICP generator, offer generator, stats updaters)
- 16 Supabase PostgreSQL tables (shared intelligence pool + analysis logs)
- Two-layer authentication (NextAuth.js + JWT + Supabase RLS)
- Error handler service with error logging to Supabase
- FastAPI backend with async endpoints (replaces n8n webhooks)
- Celery + Redis task queue for async agent execution

**Web Dashboard**:
- App shell with sidebar navigation (Marketing, Sales, Fulfillment sections + Chat)
- Central Intelligence chat interface (`/chat`) with WebSocket streaming
- Department dashboards (Marketing, Sales, Fulfillment)
- Specialist-specific pages (email dashboard, leads table, members directory, etc.)
- Admin pages (data import, error monitoring, health check)

**Marketing Department** (6 specialists + Central Intelligence Engine):
- CI-MKT-01: Social Media Specialist (script generation, metrics analysis)
- CI-MKT-02: Email Specialist (campaign analysis, email drafting)
- CI-MKT-03: Funnels Specialist (conversion analysis, bottleneck detection)
- CI-MKT-04: Ads Specialist (ROAS analysis, copy generation)
- CI-MKT-05: DM Specialist (conversation templates, DM metrics)
- CI-MKT-06: Offer Creation Specialist (offer generation, optimization)

**Central Intelligence Engine** (Integrated Marketing Subsystem):
- **VOC Data Pipeline**: Automated transcript processing extracts pains, goals, objections, wins, buying triggers, and marketing-ready copy from call transcripts
- **Content Calendar Generation**: Monthly email calendar built from VOC insights, active offers, and business goals
- **Email Writing from VOC**: Draft emails using actual customer language extracted from transcripts
- **Market Signal Analysis**: Aggregated trend reporting showing top pains, dominant objections, and emerging messaging angles across all processed calls

**Sales Department** (3 specialists):
- CI-SAL-01: Appointment Setting Bot (conversation analysis, script suggestions)
- CI-SAL-02: Leads Database Worker (lead tracking, pipeline funnel, CRUD)
- CI-SAL-03: Sales Call Analyzer (pain point/objection extraction, content ideas)

**Fulfillment Department** (4 specialists):
- CI-FUL-01: Members Database Worker (member tracking, submissions, goals)
- CI-FUL-02: Coaching Call Analyzer (wins extraction, pain points, content ideas)
- CI-FUL-03: Accountability Call Analyzer (goal tracking, progress monitoring)
- CI-FUL-04: Tech SOS Tracker (issue categorization, resolution tracking)

**Shared Operators**:
- CI-CORE-01: Call Transcriber (video→transcript via OpenAI Whisper)
- CI-OPS-ICP: ICP Generator (ideal client profile synthesis)
- CI-OPS-OFFER: Offer Generator (offer structure creation)
- CI-OPS-STATS-*: Email/Social/Funnel/Ads Stats Updaters

**Shared Intelligence Pool** (16 Supabase PostgreSQL tables):
1. `bee_analysis_log` — all AI analysis results
2. `bee_error_log` — error tracking + severity
3. `bee_registry` — worker bee metadata
4. `call_transcripts` — video transcripts + metadata
5. `pain_points` — extracted from sales/coaching calls
6. `wins` — extracted from coaching/fulfillment calls
7. `objections` — sales objections
8. `goals` — member goals from accountability calls
9. `content_ideas` — content suggestions from all sources
10. `icp` — ideal client profiles
11. `offers` — product/service offers
12. `comments` — social media comments (sentiment analyzed)
13. `audit_log` — all CRUD operations
14. `idempotency_keys` — prevent duplicate submissions
15. `users` — user profiles (owner, admin, team, viewer roles)
16. `reference` — domain-specific reference frameworks

### Out of Scope (Future Phases)

**Phase 2 (Weeks 18-24)**:
- Advanced Central Intelligence features (persistent memory, weekly digest workflow)
- Notification system with alert badges
- Persistent conversation history beyond sliding window
- Custom dashboards and reporting builder

**Phase 3 (Weeks 25-32)**:
- Multi-tenant support (vs. current single-tenant)
- Third-party integrations (Slack, email notifications, SMS alerts)
- Scheduled task automation (e.g., "send weekly digest every Friday")
- AI model swapping (GPT-4, Claude, Llama alternatives)

**Phase 4 (Future)**:
- Mobile app (iOS/Android)
- Voice interface
- Marketplace for community workers
- Advanced data visualization (custom dashboards, predictive charts)

---

## Section 4: User Stories with Acceptance Criteria

### Core Platform User Stories

#### US-001: Central Intelligence Chat Interface
**As a** business owner (Greg)
**I want to** ask Central Intelligence strategic questions and get cross-department insights
**So that** I can make data-driven decisions without context switching

**Acceptance Criteria**:
- [ ] Chat page loads at `/chat` with message input and conversation history
- [ ] Message sent to Central Intelligence triggers FastAPI endpoint, response appears in chat via WebSocket streaming
- [ ] Conversation history persists for session (5-7 days sliding window)
- [ ] Loading state shows while Central Intelligence thinks
- [ ] Error messages display if Central Intelligence fails
- [ ] "What should we focus on this week?" returns top 3 business priorities
- [ ] Can ask specific questions: "How's our sales funnel?" → Sales Director summary

---

#### US-002: Marketing Department Dashboard
**As a** business owner or marketing team member
**I want to** see all marketing KPIs (social reach, email open rates, funnel conversion, ad ROAS) on one dashboard
**So that** I can quickly assess marketing health

**Acceptance Criteria**:
- [ ] Dashboard loads at `/marketing` with department overview
- [ ] Shows 6 specialist status cards (Social, Email, Funnels, Ads, DM, Offers)
- [ ] Each card shows 2-3 key metrics (e.g., Email: avg open rate, last campaign date)
- [ ] "View Specialist" link navigates to specialist page
- [ ] Stats auto-refresh every 5 minutes (TanStack Query staleTime)
- [ ] Last updated timestamp visible
- [ ] Skeleton loaders show during first load

---

#### US-003: Leads Pipeline Dashboard
**As a** sales leader
**I want to** see leads funnel (leads → appointments → applications → sales) with metrics at each stage
**So that** I can identify bottlenecks and conversion rates

**Acceptance Criteria**:
- [ ] Leads dashboard at `/sales/leads` shows KPI cards (total leads, appt rate %, app rate %)
- [ ] Funnel visualization shows flow: leads → appointments → applications → sales
- [ ] Time-series chart shows lead volume by week/month
- [ ] Pie chart shows lead source breakdown (webinar, VSL, opt-in)
- [ ] Sortable/filterable leads table with inline editing
- [ ] Filters: date range, source, status
- [ ] Can add new lead, edit existing, delete (soft delete)
- [ ] Clicking lead shows detail view with engagement history

---

#### US-004: Transcription Automation
**As a** call analyzer (fulfillment coach or sales team member)
**I want to** upload a video/audio file and get transcript automatically
**So that** I don't manually transcribe using external tools

**Acceptance Criteria**:
- [ ] Transcript upload UI appears on multiple pages (coaching, accountability, sales calls)
- [ ] Can paste video URL or upload file
- [ ] Shows progress indicator during transcription (OpenAI Whisper)
- [ ] Transcript appears in transcript viewer once complete
- [ ] Transcript stored in `call_transcripts` table with metadata (call_type, uploader, duration)
- [ ] Duplicates detected via SHA-256 video_url_hash (don't transcribe twice)
- [ ] File size validated (max 25MB for Whisper)
- [ ] Error shown if video URL unreachable

---

#### US-005: Cross-Domain Intelligence Feed
**As a** marketing specialist (e.g., Email writer)
**I want to** see pain points from sales calls and wins from coaching calls in my content ideas
**So that** I can write more relevant content

**Acceptance Criteria**:
- [ ] Marketing dashboard shows aggregated "Content Ideas" feed
- [ ] Content ideas sourced from:
  - Sales Call Analyzer (extracted from sales calls)
  - Coaching Call Analyzer (extracted from coaching calls)
  - Fulfillment feedback
- [ ] Each idea shows: text, source (which call), creation date, status (new/in-progress/used/archived)
- [ ] Can click "use this idea" → status changes to in-progress
- [ ] Shared by all marketing specialists (accessed via Supabase table)

---

#### US-006: Member Goal Tracking
**As a** fulfillment director
**I want to** see each member's goals and track progress over accountability calls
**So that** I can spot who's at risk and who's succeeding

**Acceptance Criteria**:
- [ ] Members directory at `/fulfillment/members` with searchable list
- [ ] Click member → detail page showing:
  - Recent submissions
  - Current goals (from last accountability call)
  - Goal progress timeline (goals from previous calls)
  - Call history
- [ ] Goals have structure: description, target date, status (new/in-progress/completed/at-risk)
- [ ] "At risk" members flagged if goals stalled for 3+ weeks
- [ ] Can add/edit member record (inline editing)
- [ ] Soft delete (deleted_at) on member deletion

---

#### US-007: Appointment Conversation Analysis
**As a** sales team member
**I want to** see AI suggestions for improving appointment-setting conversations
**So that** I can increase appointment conversion rate

**Acceptance Criteria**:
- [ ] Appointments dashboard at `/sales/appointments` shows KPI cards (set rate, show rate, close rate)
- [ ] Charts show conversation patterns, response times
- [ ] "Analyze Conversation" button triggers CI-SAL-01 agent via FastAPI
- [ ] AI suggestions panel appears with before/after script comparisons
- [ ] Suggestions informed by pain points and wins from other calls
- [ ] Can mark suggestion as "implemented" for tracking

---

#### US-008: Social Media Script Generation
**As a** social media specialist
**I want to** generate social media scripts informed by content ideas and pain points
**So that** I can create better content faster

**Acceptance Criteria**:
- [ ] Social media dashboard at `/marketing/social` shows metrics (reach, engagement)
- [ ] "Generate Script" button opens form requesting:
  - Platform (Instagram, TikTok, LinkedIn, etc.)
  - Topic/theme
- [ ] AI generates 3 script options using:
  - Content ideas from `content_ideas` table
  - Pain points from `pain_points` table
  - Wins from `wins` table
  - ICP data from `icp` table
- [ ] Can copy script, save to clipboard, edit
- [ ] Shows which pain points/wins informed the script

---

#### US-009: Email Campaign Drafting
**As a** email marketing specialist
**I want to** generate email drafts informed by content ideas and customer insights
**So that** emails resonate better with audience

**Acceptance Criteria**:
- [ ] Email dashboard at `/marketing/email` shows campaign metrics (open rate, click rate, unsub rate)
- [ ] "Draft Email" form allows entering:
  - Campaign goal
  - Audience segment (if tracked)
  - Tone preference
- [ ] AI generates subject line, body, CTA using:
  - Content ideas from shared pool
  - Historical email performance (subject line patterns, CTA effectiveness)
  - Pain points and wins (for relevance)
- [ ] Can preview email in different templates
- [ ] Can export as .html or copy-paste to email service

---

#### US-010: Sales Call Pain Point Extraction
**As a** content marketer
**I want to** see pain points extracted from sales calls automatically
**So that** I can create targeted content addressing those pain points

**Acceptance Criteria**:
- [ ] Sales Calls page at `/sales/calls` shows list of analyzed calls
- [ ] Click call → detail view with:
  - Transcript viewer
  - Extracted pain points (with quotes from transcript)
  - Content ideas generated from call
  - Linked lead record
- [ ] Pain points stored in `pain_points` table with:
  - Text, source (call), creation date, contributor (sales person)
  - `contributing_transcripts` array (prevent duplicates)
- [ ] Can update pain point status or add notes
- [ ] Pain points visible to all marketing specialists

---

#### US-011: Coaching Wins Feed
**As a** content creator in fulfillment
**I want to** see wins extracted from coaching calls
**So that** I can create success stories and marketing content

**Acceptance Criteria**:
- [ ] Coaching calls page at `/fulfillment/coaching` shows list of analyzed calls
- [ ] Click call → detail view with:
  - Transcript viewer
  - Extracted wins (with member and date)
  - Pain points also extracted from call
  - Content ideas generated
- [ ] Wins stored in `wins` table, visible to all marketing specialists
- [ ] Can filter wins by member, date range, content type
- [ ] Wins can be marked as "used in content" for tracking

---

#### US-012: ICP (Ideal Client Profile) Management
**As a** marketing strategist
**I want to** view and manage the Ideal Client Profile built from sales and fulfillment data
**So that** all marketing can target the right audience

**Acceptance Criteria**:
- [ ] ICP viewer at `/marketing/icp` shows current profile
- [ ] Profile includes:
  - Demographics (age, industry, company size, role)
  - Psychographics (goals, values, pain points, objections)
  - Triggers (situations when they need solution)
  - Sourced from: pain_points, wins, objections, goals tables
- [ ] Can view ICP versions over time (updated weekly/monthly)
- [ ] ICP Generator (CI-OPS-ICP) runs on schedule or on-demand
- [ ] Shows which sources contributed to each section

---

#### US-013: Offer Management
**As a** offer strategist
**I want to** view, create, and optimize product/service offers
**So that** we maximize conversion and price appropriately

**Acceptance Criteria**:
- [ ] Offers dashboard at `/marketing/offers` shows offer library
- [ ] Each offer shows: name, pricing, conversion rate, last updated
- [ ] "Create Offer" form guided by AI suggestions:
  - Suggest features based on ICP + pain points + wins
  - Suggest pricing tiers
  - Suggest positioning
- [ ] "Optimize Offer" analyzes existing offer, suggests pricing/positioning changes
- [ ] Can view offer versions and performance over time
- [ ] Offers fed to all sales/marketing specialists for context

---

#### US-014: Authentication & Secure Access
**As a** business owner
**I want to** log in securely and have my session protected
**So that** my business data is safe

**Acceptance Criteria**:
- [ ] Login page at `/login` with email and password inputs
- [ ] "Remember me" option extends session to 7 days
- [ ] Session stores JWT in HttpOnly cookie (30-min sliding window)
- [ ] User validated against `users` Supabase table
- [ ] 5 failed login attempts → 15-minute account lockout
- [ ] Logout clears session and redirects to /login
- [ ] All authenticated API calls include Bearer token
- [ ] JWT signature prevents unauthorized API calls
- [ ] Session check on app startup (`GET /auth/me`)

---

#### US-015: Error Handling & Notifications
**As a** user
**I want to** see clear error messages and recovery options
**So that** I know what went wrong and what to do next

**Acceptance Criteria**:
- [ ] API errors shown as toast notifications (red background)
- [ ] Error toast shows: message + "Try again" or "Contact support" button
- [ ] Errors logged to `bee_error_log` table for debugging
- [ ] Critical errors (P0) trigger email alert to admin
- [ ] App crashes caught by error boundaries (displays "Something went wrong" gracefully)
- [ ] Network disconnection shown as banner with auto-retry indicator
- [ ] Loading skeletons show for slow network
- [ ] Empty states guide users: "No calls yet. Upload your first call →"

---

## Section 5: Functional Requirements Summary

### Organized by Component / Worker

#### Core Platform (CI-CORE-00 Central Intelligence)

| Requirement | Detail | Status |
|-------------|--------|--------|
| **CEO-Level AI Chat** | Accept natural language questions, route to Directors, synthesize responses | Sprint 1a |
| **Department Routing** | Understand "marketing" vs "sales" vs "fulfillment" questions, call appropriate Director | Sprint 1a |
| **Business Optimization** | "What should we focus on?" returns top 3 priorities based on metrics | Sprint 8 |
| **Cross-Domain Query** | Query multiple departments, aggregate insights (e.g., "How many pain points are we seeing in sales calls?") | Sprint 1a |
| **Dashboard Generation** | Format complex data into charts/KPIs for web app display | Sprint 1a |
| **Conversation Memory** | Remember context within session (Simple Memory in MVP, Postgres Chat Memory in v2) | Sprint 1a |

#### Directors (Level 3 - Marketing, Sales, Fulfillment)

| Requirement | Detail | Status |
|-------------|--------|--------|
| **Specialist Coordination** | Each Director knows all Specialists under them, routes work requests | Sprints 2, 5, 6 |
| **Department Summarization** | Aggregate specialist output into department-level summary | Sprints 2, 5, 6 |
| **Shared Intelligence Access** | Read from pain_points, wins, goals, content_ideas, icp, offers tables | Sprints 2, 5, 6 |
| **Function Tool Calls** | Call specialist agents via Python function definitions | Sprints 2, 5, 6 |
| **Metric Aggregation** | Combine KPIs from specialists (email: open rate, social: reach, etc.) | Sprints 2, 5, 6 |

#### Marketing Specialists (Level 2 - CI-MKT-01 to 06)

| Requirement | Detail | Status |
|-------------|--------|--------|
| **Social Media Analysis** | Extract engagement patterns, identify trending topics | Sprint 3 |
| **Script Generation** | Create social scripts informed by pain points + wins + ICP | Sprint 3 |
| **Email Analysis** | Analyze open rates, click rates, subject line patterns | Sprint 3 |
| **Email Drafting** | Generate subject lines, body copy, CTAs from content ideas | Sprint 3 |
| **Funnel Analysis** | Calculate conversion rates by stage, identify drop-offs | Sprint 3 |
| **Optimization Suggestions** | AI recommendations for each funnel stage | Sprint 3 |
| **Ads Analysis** | ROAS, CTR, CPC metrics analysis | Sprint 4 |
| **Ad Copy Generation** | Create ad copy/scripts from content ideas + pain points | Sprint 4 |
| **DM Templates** | Generate conversation templates from ICP + pain_points + objections | Sprint 4 |
| **Offer Creation** | Generate offer structures (features, pricing, positioning) | Sprint 4 |
| **Offer Optimization** | Suggest pricing/positioning improvements from data | Sprint 4 |

#### Sales Specialists (Level 2 - CI-SAL-01 to 03)

| Requirement | Detail | Status |
|-------------|--------|--------|
| **Appointment Analysis** | Analyze conversations, extract patterns, suggest script improvements | Sprint 5 |
| **GHL Integration** | Fetch contacts, opportunities, conversations from GoHighLevel | Sprint 5 |
| **Leads CRUD** | Create, read, update, delete leads with optimistic locking | Sprint 5 |
| **Funnel Metrics** | Calculate funnel conversion rates (leads→appt→app→sale) | Sprint 5 |
| **Source Tracking** | Track lead source (webinar, VSL, opt-in) and performance | Sprint 5 |
| **Pain Point Extraction** | Extract pain points from sales call transcripts | Sprint 5 |
| **Content Ideas from Calls** | Generate content ideas from sales call insights | Sprint 5 |
| **Lead-to-Member Sync** | Auto-create member when lead status changes to "sale" | Sprint 5 |

#### Fulfillment Specialists (Level 2 - CI-FUL-01 to 04)

| Requirement | Detail | Status |
|-------------|--------|--------|
| **Member CRUD** | Create, read, update, delete member records | Sprint 6 |
| **Submission Tracking** | Track member submissions and milestone progress | Sprint 6 |
| **Wins Extraction** | Extract wins from coaching call transcripts | Sprint 6 |
| **Pain Points from Coaching** | Extract pain points from coaching calls | Sprint 6 |
| **Goals Management** | Extract goals from accountability calls, track progress | Sprint 6 |
| **Accountability Tracking** | Compare goals across multiple accountability calls | Sprint 6 |
| **Progress Analytics** | Identify members at risk, celebrate progress | Sprint 6 |
| **Tech Issues Categorization** | AI categorizes tech SOS issues, suggests solutions | Sprint 6 |
| **Issue Resolution Tracking** | Track status and resolution time for tech issues | Sprint 6 |

#### Operators (Level 1 - Shared Utilities)

| Requirement | Detail | Status |
|-------------|--------|--------|
| **Call Transcription** | Download video, extract audio, transcribe via OpenAI Whisper | Sprint 2 |
| **Transcript Routing** | Route transcripts to appropriate analyzer (sales/coaching/accountability) | Sprint 2 |
| **ICP Generation** | Synthesize ICP from pain_points, wins, objections, goals | Sprint 2 |
| **Offer Generation** | Create offer structures using ICP + pain_points + objections | Sprint 4 |
| **Stats Updates** | Periodic import of email, social, funnel, ads metrics | Sprints 3-4 |
| **Comments Collection** | Pull social media comments, analyze sentiment | Sprint 3 |

#### Cross-Domain Flows (Shared Intelligence Pool)

| Requirement | Detail | Status |
|-------------|--------|--------|
| **Pain Points Table** | Aggregated from sales calls, coaching calls, feedback | Sprints 5-6 |
| **Wins Table** | Aggregated from coaching calls, member achievements | Sprint 6 |
| **Content Ideas Table** | Generated by all specialists, status-tracked (new→used→archived) | Sprints 3-6 |
| **Objections Table** | Extracted from sales calls, updated as objections resolved | Sprint 5 |
| **Goals Table** | Member goals from accountability calls with tracking | Sprint 6 |
| **ICP Table** | Single source of truth for Ideal Client Profile | Sprint 2 |
| **Offers Table** | All offers with performance metrics | Sprints 4-6 |
| **Comments Table** | Social media comments with sentiment analysis | Sprint 3 |

---

## Section 6: Non-Functional Requirements

### Performance

| Requirement | Target | Validation |
|-------------|--------|------------|
| API response time | <2s | Load testing with 50 concurrent requests |
| Chat message latency | <5s (including Central Intelligence AI) | End-to-end timing from send to response |
| Dashboard load | <1.5s (initial + data) | Lighthouse PageSpeed Insights |
| API client timeout | 15s (standard), 120s (transcription) | Implemented via FastAPI timeout handling |
| Database query | <500ms (1000+ rows) | Supabase/PostgreSQL performance testing |

### Reliability

| Requirement | Detail | Implementation |
|-------------|--------|-----------------|
| **Error Handling** | All Agent errors logged to `bee_error_log` | Exception handlers in all agent classes |
| **Retry Logic** | Exponential backoff on transient failures | 3 retries (external APIs), 2 retries (OpenAI), 3 retries (HTTP) |
| **Graceful Degradation** | Central Intelligence reports partial data if a Director fails | Try/catch in Central Intelligence orchestrator |
| **Circuit Breaker** | Stop cascading failures during external API outages | Circuit breaker pattern in agent utilities |
| **Health Checks** | Periodic endpoint verification | GET /api/health (1s response) |
| **Uptime Target** | 99.5% excluding external service outages | Monitored via Sentry + application logs |

### Security

| Requirement | Detail | Implementation |
|-------------|--------|-----------------|
| **User Authentication** | NextAuth.js Credentials Provider | JWT in HttpOnly cookie (30-min sliding) |
| **API Authentication** | Bearer token with JWT signature | Bearer token in Authorization header |
| **Authorization** | Role-based (owner, admin, team, viewer) | Enforced in FastAPI middleware + Supabase RLS |
| **Webhook Signing** | Prevent unauthorized API calls | HMAC-SHA256 on request body (future enhancement) |
| **Replay Protection** | Prevent request replay attacks | Timestamp validation (5-min window) |
| **CORS** | Restrict to web app origin | FastAPI CORS middleware |
| **No Direct Database Access** | All access through agents/APIs | SQLAlchemy ORM with Repository pattern |
| **Soft Delete** | Data recovery instead of hard delete | `deleted_at` field on all mutable tables |
| **Audit Logging** | Track all CRUD operations | `audit_log` table with user, action, resource, timestamp |
| **Account Lockout** | Prevent brute force attacks | 5 failed attempts → 15-min lock |
| **Password Requirements** | Minimum 8 characters (MVP) | Validated in auth endpoint |
| **Session Timeout** | 30-min sliding window | NextAuth.js configuration |
| **Token Rotation** | Rotate Bearer tokens safely | Planned for Sprint 8 |

### Scalability

| Requirement | Detail | Implementation |
|-------------|--------|-----------------|
| **Worker Addition** | Add new specialist in 1-2 days | Agent class registration on Director |
| **Data Volume Growth** | Support 1M+ records in Supabase | Implement pagination, lazy loading |
| **Concurrent Users** | Support 5-10 simultaneous users (MVP) | Tested via load testing |
| **API Rate Limiting** | Protect AI costs | Rate limit per endpoint (to be defined in Sprint 1b) |
| **Database Abstraction** | Swap database without app changes | SQLAlchemy ORM + Repository pattern |

### Data Integrity

| Requirement | Detail | Implementation |
|-------------|--------|-----------------|
| **Soft Delete** | All deletions use `deleted_at` instead of hard delete | Enforced in all DELETE operations |
| **Orphan Prevention** | Prevent child records with missing parent | Foreign key constraints in ORM |
| **Optimistic Locking** | Prevent concurrent edit data loss | `updated_at` + `If-Match` header validation |
| **Deduplication** | Prevent duplicate transcripts, pain points | SHA-256 hashing on video URLs, `contributing_transcripts` array |
| **Idempotency** | Prevent duplicate form submissions | `X-Idempotency-Key` header, stored in `idempotency_keys` table |
| **Transactional Consistency** | Multi-step operations atomic or rolled back | Implemented at agent/service level |

### Accessibility

| Requirement | Detail | WCAG Level |
|-------------|--------|-----------|
| Color Contrast | All text ≥4.5:1 ratio | AA |
| Keyboard Navigation | All interactive elements accessible via keyboard | AA |
| ARIA Labels | Buttons, forms, navigation labeled | AA |
| Alt Text | All images have alt text | AA |
| Focus Indicators | Visible focus state on all interactive elements | AA |
| Error Messages | Linked to form fields, descriptive | AA |
| Form Validation** | Real-time feedback without jarring redirects | AA |

### Browser Support

| Browser | Versions | Notes |
|---------|----------|-------|
| Chrome | Latest 2 versions | Primary target |
| Firefox | Latest 2 versions | Full support |
| Safari | Latest 2 versions | Mobile focus |
| Edge | Latest version | Secondary target |

---

## Section 7: System Architecture Overview

### 3-Tier Organizational Hierarchy

```
                         ┌──────────────────┐
                         │ CENTRAL INTELLIGENCE │
                         │ (CI-CORE-00)    │
                         │ CEO / Orchestrator
                         └────────┬─────────┘
                                  │
                ┌─────────────────┼─────────────────┐
                │                 │                 │
      ┌─────────▼─────────┐ ┌──────▼──────┐ ┌──────▼─────────┐
      │  MARKETING DIR    │ │  SALES DIR  │ │ FULFILLMENT    │
      │  (CI-MKT-DIR)    │ │(CI-SLS-DIR) │ │    DIR         │
      │   Level 3        │ │  Level 3    │ │ (CI-FUL-DIR)  │
      └────────┬─────────┘ └──────┬──────┘ └────────┬───────┘
               │                  │                 │
      ┌────────┴────────┐         │        ┌────────┴────────┐
      │                 │         │        │                 │
  ┌───▼─────┐  ┌───┐ ┌──▼────┐ ┌──▼────┐ ┌──▼────┐ ┌───┐ ┌──▼────┐
  │ Social  │  │Eml│ │Funnels│ │Appts  │ │Leads  │ │... │ │Members │
  │ Spec    │  │.. │ │Spec   │ │Bot    │ │DB     │ │    │ │DB     │
  │(Lvl 2)  │  │   │ │(Lvl 2)│ │(Lvl 2)│ │(Lvl 2)│ │    │ │(Lvl 2)│
  └─────────┘  └───┘ └───────┘ └───────┘ └───────┘ └───┘ └───────┘

                    └────────────────────────────────────────┘
                     Shared Intelligence Pool
                     (16 Supabase Tables):
        pain_points ─ wins ─ goals ─ content_ideas ─ icp ─ offers
        objections ─ comments ─ call_transcripts ─ reference
                    └────────────────────────────────────────┘

    ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐
    │Transcr-│  │  ICP   │  │ Offer  │  │ Stats  │  │ Error  │
    │ iber   │  │ Gener  │  │ Gener  │  │Updaters│  │Handler │
    │(CI-OPS)│  │(CI-OPS)│  │(CI-OPS)│  │(CI-OPS)│  │(CI-ERR)│
    │Lvl 1   │  │Lvl 1   │  │Lvl 1   │  │Lvl 1   │  │  Core  │
    └────────┘  └────────┘  └────────┘  └────────┘  └────────┘
```

### Central Intelligence Subsystem Integration

Central Intelligence operates as integrated Python agents within Central Intelligence:

```
Central Intelligence (Python Agents + Supabase)
     │
     ├─ Claude SDK Skills (Transcript Processor, Content Calendar, Email Writer...)
     │
     ├─ Supabase Database (9 tables: calls, insights, content_ideas, market_signals...)
     │
     └─ Data Sync / FastAPI Endpoints
          │
          v
    Central Intelligence Python Agents (Marketing Specialists consume CI data)
          │
          v
    Next.js Web App (displays CI insights, content calendar, market signals)
```

**Key Flow**:
1. Call transcripts ingested by CI Transcript Processor (TXT/PDF/DOCX)
2. 2-pass AI extraction: raw extraction + structured refinement
3. Insights stored in Supabase tables (calls, insights, content_ideas, market_signals, etc.)
4. FastAPI endpoints expose CI data to Marketing Specialists
5. Marketing Specialists use VOC data + market signals for content generation, email writing, strategy

**CI Data Integration Points**:
- Marketing Specialists query CI endpoints for voice-of-customer language
- Content ideas from CI feed into content calendar generation
- Market signals (top pains, objections, trends) inform marketing strategy
- Email writer uses actual customer language extracted by CI

### Data Flow Architecture

**External to Central Intelligence**:
```
Video URL / Call Recording
        ↓
   Transcriber (CI-CORE-01)
        ↓
call_transcripts table
        ↓
Router → Sales Call Analyzer (CI-SAL-03)
      → Coaching Analyzer (CI-FUL-02)
      → Accountability Analyzer (CI-FUL-03)
```

**Within Shared Intelligence**:
```
Sales Call Analyzer
        ↓ Extracts
pain_points + objections + content_ideas tables

Coaching Call Analyzer
        ↓ Extracts
wins + pain_points + content_ideas tables

ICP Generator
        ↓ Synthesizes from
pain_points + wins + objections + goals
        ↓ Writes to
icp table

ALL Marketing Specialists (Social, Email, Funnels, Ads, DM, Offers)
        ↓ Read from
pain_points, wins, objections, goals, content_ideas, icp, offers
        ↓ Generate
social scripts, email copy, ad copy, DM templates, content ideas
```

### Web App to FastAPI Communication

```
┌─────────────────────────────┐
│   Next.js Web Application   │
│   (Client-side + SSR)       │
└──────────────┬──────────────┘
               │
               │ HTTPS
               │ POST /api/[endpoint]
               │ Authorization: Bearer <token>
               │ X-User-Id: <user>
               │ X-Request-Id: <uuid>
               │
      ┌────────▼─────────────────────┐
      │ FastAPI Endpoint              │
      │ (33+ routes)                  │
      └────────┬──────────────────────┘
               │
      ┌────────▼──────────────────────────────┐
      │ Central Intelligence Agent (Python + Claude SDK)│
      │ - Validate auth                      │
      │ - Execute business logic             │
      │ - Query/write Supabase               │
      │ - Return structured JSON             │
      └────────┬──────────────────────────────┘
               │
               │ Structured JSON response
               │ {
               │   "success": true,
               │   "data": {...},
               │   "meta": {...}
               │ }
               │
      ┌────────▼──────────────────────────────┐
      │ Next.js API Route (optional middleware)
      │ - Response transformation             │
      │ - Caching (TanStack Query)            │
      │ - Error handling                      │
      └────────┬──────────────────────────────┘
               │
               │ JSON response
               ↓
      Browser / React Components
```

### Database Abstraction

```
All Workers speak to Database via SQLAlchemy ORM (Repository pattern)
(Only this layer knows database specifics)

PostgreSQL (Supabase) ← Primary implementation
Other Databases ← Swap without changing agent code
```

### Technology Stack

**Central Intelligence Core Platform**:
- **Orchestration**: Python + Claude SDK (Anthropic API)
- **Backend API**: FastAPI (async Python web framework)
- **Frontend**: Next.js + React + TypeScript
- **Authentication**: NextAuth.js + Supabase Auth (JWT + RLS)
- **Database**: Supabase/PostgreSQL with SQLAlchemy ORM
- **ORM Pattern**: Repository pattern for database abstraction
- **Task Queue**: Celery + Redis for async agent execution
- **AI/LLM**: Claude API (Anthropic) for all AI reasoning
- **Agent Framework**: Python agent classes (no external framework required)

**Central Intelligence Subsystem**:
- **Runtime**: Python + Claude SDK
- **Database**: Supabase/PostgreSQL (9 tables for CI data)
- **AI/Extraction**: Claude API (Anthropic)
- **Skills Framework**: Python functions with Claude tool definitions
- **Client Library**: `psycopg2` / `asyncpg` for database access
- **Transcript Sources**: Cockatoo (current), Fireflies (future automation)

**Supporting Services**:
- **Transcription**: OpenAI Whisper API
- **Email Delivery**: ActiveCampaign (Phase 2+)
- **CDN/Hosting**: Vercel (Next.js frontend)
- **Monitoring**: Sentry (error tracking) + custom observability

### 33+ API Endpoints (FastAPI Routes)

| Category | Count | Examples |
|----------|-------|----------|
| Central Intelligence | 2 | POST `/api/central-intelligence/chat`, GET `/api/central-intelligence/summary` |
| Directors | 6 | GET `/api/marketing/summary`, GET `/api/sales/summary`, GET `/api/fulfillment/summary` |
| Marketing Specialists | 12 | POST `/api/social/generate-script`, POST `/api/email/draft`, POST `/api/funnels/analyze`, POST `/api/ads/analyze`, POST `/api/dm/templates`, POST `/api/offers/generate`, GET endpoints |
| Sales Specialists | 9 | GET `/api/leads`, POST `/api/leads`, PUT `/api/leads/:id`, DELETE `/api/leads/:id`, GET `/api/appointments/stats`, POST `/api/appointments/analyze`, GET `/api/sales-calls`, POST `/api/sales-calls/analyze` |
| Fulfillment Specialists | 10 | GET `/api/members`, POST `/api/members`, GET `/api/members/:id`, POST `/api/coaching/analyze`, POST `/api/accountability/analyze`, GET `/api/tech-sos/issues`, POST `/api/tech-sos/submit` |
| Operators | 8 | POST `/api/transcribe`, GET `/api/icp`, POST `/api/icp/generate`, GET `/api/offers`, POST `/api/offers/generate` |
| Cross-Domain | 4 | GET `/api/pain-points`, GET `/api/wins`, GET `/api/content-ideas`, GET `/api/goals` |
| Auth & Admin | 6 | POST `/api/auth/login`, POST `/api/auth/change-password`, GET `/api/auth/me`, GET `/api/health`, GET `/api/errors`, POST `/api/admin/import` |

---

## Section 8: Success Metrics & KPIs

### Automation Reliability

| Metric | Target | How Measured |
|--------|--------|--------------|
| **Agent Execution Success Rate** | >98% | Successful tasks / total tasks |
| **Transcription Success** | >95% | Successful transcripts / upload attempts |
| **AI Analysis Quality** | >90% accuracy | Manual spot-check of extracted data (pain points, wins) |
| **Error Detection** | 100% | Errors logged to `bee_error_log` within 1 min |
| **MTTR (Mean Time to Recovery)** | <30 min for P0 errors | Time from error alert to fix |

### AI Response Quality

| Metric | Target | How Measured |
|--------|--------|--------------|
| **Script Relevance** | >80% user satisfaction | User feedback on generated scripts |
| **Email Draft Quality** | >75% adoption rate | % of drafts sent without major edits |
| **Content Idea Usefulness** | >70% used in content | Tracking content_idea status transitions |
| **Pain Point Accuracy** | >85% precision | Manual review of extracted pain points |
| **Central Intelligence Answer Accuracy** | >80% directional correctness | User assessment of business recommendations |

### Data Accuracy & Freshness

| Metric | Target | How Measured |
|--------|--------|--------------|
| **Leads Data Completeness** | >95% required fields filled | Database audit |
| **Stats Data Freshness** | <4 hours stale | Last updated timestamp in UI |
| **Cross-Domain Data Consistency** | 100% no conflicts | `audit_log` for all CRUD operations |
| **Soft Delete Integrity** | 100% preserved records | Verify all deletes use `deleted_at` |
| **Duplicate Detection** | >99% false negative rate | Monitor SHA-256 hashes for transcripts |

### User Adoption

| Metric | Target | How Measured |
|--------|--------|--------------|
| **Daily Active Users** | ≥1 (Greg initially, team later) | Session logs |
| **Feature Usage** | >80% of features used monthly | Page views by department |
| **Dashboard Load Frequency** | >2x per day | Analytics on `/marketing`, `/sales`, `/fulfillment` |
| **Chat Volume** | >10 Central Intelligence questions/week | Conversation history tracking |
| **Specialist AI Usage** | >5 script/email/offer generations/week | Endpoint hit tracking |

### Time Savings

| Metric | Target | How Measured |
|--------|--------|--------------|
| **Transcription Time Saved** | ~10 hours/week | 5 calls/week × 2hrs manual vs 10min automated |
| **Script Generation Speed** | <5 minutes per script | Timestamp from request to generation |
| **Dashboard Assembly Time** | <2 minutes | vs. 30 minutes manual Excel compilation |
| **Business Insights Time** | <10 minutes per decision | vs. 1-2 hours manual analysis |
| **Total Weekly Savings** | >50 hours | Aggregate time on transcription, analysis, content generation |

### System Health

| Metric | Target | How Measured |
|--------|--------|--------------|
| **Uptime** | >99.5% | Excluding external service outages |
| **API Response Time** | <2s p95 | FastAPI execution logs |
| **Error Rate** | <0.5% of requests | 500/503 errors divided by total requests |
| **Critical Issues** | 0 P0 unresolved >24h | Issue tracking |
| **Performance Regression** | <5% change month-over-month | API latency tracking |

---

## Section 9: MVP vs Future Phases

### Phase 1: Foundation + All Departments (Weeks 1-17)

**Delivers**:
- Central Intelligence orchestrator + Chat interface with WebSocket streaming
- 3 Directors (Marketing, Sales, Fulfillment) as Python agent classes
- 15+ Specialists across all departments as Python agent classes
- 7 Shared Operators as Python utility agents
- Web dashboard with all department pages
- Two-layer authentication (NextAuth + JWT)
- Error handling infrastructure with Sentry
- 16 Supabase PostgreSQL tables with SQLAlchemy ORM
- 33+ FastAPI endpoints
- Celery + Redis task queue
- Central Intelligence Subsystem:
  - CI Transcript Processor skill (already built)
  - 9 Supabase tables with full schemas (calls, insights, content_ideas, market_signals, etc.)
  - FastAPI endpoints exposing CI data to web app
  - Basic insights querying and content ideas display

**Not Included**:
- Persistent conversation history beyond session
- Scheduled workflows (weekly digest)
- Email/Slack notifications
- Multi-tenant support
- Advanced visualizations
- CI Content Calendar, Email Writer, Performance Tracker, Market Signal Analyzer skills

---

### Phase 2: Executive Intelligence + Central Intelligence Expansion (Weeks 18-24)

**Adds**:
- Enhanced Central Intelligence system prompt with business optimization framework
- Weekly digest agent (scheduled synthesis of all data)
- Persistent memory upgrade (Postgres Chat Memory instead of Simple Memory)
- Executive dashboard upgrade (cross-department trends, forecasting)
- Notification system with alert badges
- Weekly focus widget showing Central Intelligence's top priorities
- Mobile-responsive polish
- **Central Intelligence Expansion**:
  - CI Content Calendar agent
  - CI Email Marketing Specialist agent
  - CI Email Writer agent
  - CI Performance Tracker agent
  - CI Market Signal Analyzer agent
  - 6 additional CI tables: email_stats, funnel_stats, ads_stats, funnels, traffic_sources, written_emails
  - Multi-client architecture (client_id across all CI tables)
  - ActiveCampaign integration for email delivery
  - Fireflies webhook automation for transcript ingestion

**Estimated Effort**: 8-10 weeks, 2-3 developers

---

### Phase 3: Integration & Automation (Weeks 25-32)

**Adds**:
- Email notifications (weekly digest, critical alerts)
- Slack integration (daily summary, alert mentions)
- SMS notifications (critical alerts only)
- Scheduled task automation (e.g., "send weekly digest every Friday 9 AM") via APScheduler
- Google Calendar integration (sync meeting notes, attendees)
- Zapier/Make.com integration (webhook outbound for other tools)
- Advanced data export (CSV, PDF reports)

**Estimated Effort**: 6-8 weeks

---

### Phase 4: Scale & Marketplace (Future)

**Adds**:
- Multi-tenant SaaS version (vs. current single-tenant)
- Custom agent marketplace (community-built specialists)
- Advanced dashboard builder (drag-drop custom metrics)
- Predictive analytics (forecast next month's leads, revenue)
- AI model swapping (use GPT-4, Claude, Llama as alternatives)
- Mobile app (iOS/Android)
- Voice interface (ask Central Intelligence verbally)
- API marketplace for external integrations

**Estimated Effort**: Months 6-12 (significant engineering)

---

## Section 10: Assumptions & Constraints

### Assumptions

| Assumption | Impact | Risk If Wrong |
|-----------|--------|---------------|
| Python + Claude SDK availability | Core infrastructure | Use OpenAI API fallback (Sprint 8) |
| Supabase/PostgreSQL as primary database | Data abstraction pattern | Database migration feasible (scheduled for Phase 2) |
| OpenAI API availability | Transcription + AI agents | Use Claude/Llama fallback (Sprint 8) |
| Greg as primary user | MVP simplicity | Scale for team later (Phase 3) |
| ~5-10 concurrent users (MVP) | Performance targets | Implement caching + pagination if exceeded |
| REST API architecture sustainable | API design | Fully encapsulated, easy to swap to GraphQL later |
| Users have stable internet | App performance | Implement service worker offline mode (Sprint 8) |
| Call transcripts <25MB | Whisper file limit | Validate file size before upload (Sprint 2) |

### Constraints

| Constraint | Mitigation |
|-----------|-----------|
| **Single-Tenant (MVP)** | Multi-tenant planned for Phase 4; current architecture allows migration |
| **Python + Claude SDK** | Documented SDK usage; team has Claude SDK experience |
| **AI/Claude API Costs** | Use Claude 3.5 Haiku for Specialists/Operators, Claude 3.5 Sonnet for Directors/Central Intelligence; implement rate limiting (Sprint 1b) |
| **Supabase Rate Limits** | Implement caching, batch operations, async queue processor (Sprint 5) |
| **Manual Data Seeding** | Initially seed marketing tables with sample data; real data flows when Sales/Fulfillment come online (Sprint 5-6) |
| **Video File Hosting** | Assume videos hosted externally (YouTube, Vimeo, S3); transcriber downloads via URL |
| **Browser Support** | Target modern browsers (Chrome, Firefox, Safari, Edge); IE11 not supported |
| **Data Residency** | All data stays in Supabase (US servers); future on-prem option allows self-hosted deployment |

---

## Section 11: Risks & Mitigations

### High-Impact Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|-----------|
| **AI Hallucination** | Medium | Extracted pain points/wins inaccurate, poor content ideas | Manual review process; train AI with examples; fallback to human review for critical decisions |
| **API Rate Limiting** | Medium | Agent execution throttling during peak use | Implement caching, batch operations, async queue processor; monitor quotas daily |
| **Data Migration Complexity** | Medium | Historic data not imported, delays start | Dedicated Sprint 7; data mapping templates; sync verification workflow |
| **Scope Creep** | High | Timeline slips, quality drops | Strict feature freeze by Sprint 3; prioritize MVP only; track scope changes |
| **Critical P0 Fixes** | Medium | Launch blocked until auth/error handling resolved | Parallel work on auth + core in Sprint 1b; validation gates before each sprint |
| **Supabase Schema Changes** | Low | Agent code breaks | Document schema; version control all migrations; test migration process |
| **External API Outages** | Medium | Cascading failures (Supabase → OpenAI down) | Circuit breaker pattern (Sprint 8); graceful degradation in Central Intelligence; retry logic with exponential backoff |

### Medium-Impact Risks

| Risk | Mitigation |
|------|-----------|
| **Empty Marketing Tables at Start** | Seed with sample data; real data flows Sprint 5+ when Sales/Fulfillment come online |
| **GHL API Changes** | Abstract GHL calls behind CI-SAL-01; only 1 agent affected if API changes |
| **Whisper File Size (25MB Limit)** | Add file size validation in Transcriber agent; warn users before upload |
| **Concurrent Edit Data Loss** | Optimistic locking via `updated_at` + `If-Match` header; compare versions before save |
| **Duplicate Form Submissions** | Idempotency keys (`X-Idempotency-Key` header) stored in `idempotency_keys` table |
| **Accidental Data Destruction** | Soft delete (never hard delete); 90-day retention in soft-deleted state; confirm dialogs for all destructive actions |
| **Unauthorized Access** | Two-layer auth (NextAuth + JWT); bearer token validation; token rotation (Sprint 8) |

### Sprint-Specific Risks

| Sprint | Risk | Mitigation |
|--------|------|-----------|
| 1a-1b | Auth system not working → can't proceed | Parallel work; test auth flow early |
| 2 | Transcriber + ICP Generator scope too large | Split ICP into Sprint 3 if needed |
| 3 | 91 story points (heaviest sprint) → schedule slip | Consider 3-week sprint; pre-complete some ICP work |
| 5 | 147 story points + Sales complexity → major slip risk | Split 5a/5b; add buffer week after |
| 6 | 126 story points + Fulfillment coordination → overload | Split 6a/6b; use Sprint 7 for overflow |
| 7 | Data migration complexity → data loss | Careful mapping; verification workflow; dry run |
| 8 | Central Intelligence intelligence hard to implement → extended scope | MVP with basic Central Intelligence; enhance in Phase 2 |

### Mitigation Priorities (P0 Critical Fixes Required Before Launch)

From critical-fixes.md, these must be resolved:

| P0 Fix | Impact | Status | Deadline |
|--------|--------|--------|----------|
| Auth system two-layer architecture | Cannot proceed without secure login | Sprint 1b | Week 3 |
| Error handler (CI-CORE-ERR) | Cannot debug failures, cascading issues | Sprint 1b | Week 3 |
| Bearer token validation | Unauthorized API calls possible | Sprint 1b | Week 3 |
| All Agent classes have error handling | Silent failures, lost data | Per Sprint | Each sprint |
| Soft delete on all mutable tables | Data recovery not possible | Per Sprint | Each sprint |
| Cross-domain data visibility | Marketing can't use sales insights | Sprint 2+ | Per capability |

---

## Section 12: Release Criteria / Definition of Done

### Pre-Launch Validation (P0 Critical Path)

Before any code ships to production:

#### Authentication & Security
- [ ] NextAuth.js session working (JWT in HttpOnly cookie)
- [ ] Login page redirects unauthenticated users
- [ ] Bearer token validation on all API endpoints
- [ ] JWT signature verified on all requests
- [ ] Account lockout after 5 failed attempts
- [ ] Replay protection via timestamp validation (5-min window)
- [ ] 401 → login redirect working

#### Error Handling
- [ ] Try/catch blocks configured in all Agent classes
- [ ] CI-CORE-ERR error handler captures: agent_id, execution_id, error_type, severity, message, stack trace
- [ ] Errors logged to `bee_error_log` Supabase table
- [ ] P0 errors trigger email alert to admin
- [ ] Error boundaries catch React crashes gracefully
- [ ] Toast notifications display API errors

#### Data Integrity
- [ ] All 16 Supabase tables created with correct schemas
- [ ] Soft delete configured on all mutable tables (delete sets `deleted_at`, not hard delete)
- [ ] Optimistic locking implemented (`updated_at` + `If-Match` header)
- [ ] Idempotency keys prevent duplicate submissions
- [ ] Orphan prevention checks in agent code
- [ ] Audit log tracks all CRUD operations

#### API Contract
- [ ] 33+ FastAPI endpoints documented (OpenAPI/Swagger format)
- [ ] All endpoints return standardized response format:
  ```json
  {
    "success": true/false,
    "data": {...},
    "error": {...},
    "meta": {"request_id": "..."}
  }
  ```
- [ ] All endpoints include auth validation (Bearer token check)
- [ ] All endpoints include audit logging

#### Frontend Infrastructure
- [ ] App shell with navigation (Marketing, Sales, Fulfillment, Chat sections)
- [ ] Skeleton loaders for data fetch states
- [ ] Empty state screens with CTAs
- [ ] Confirm dialogs for destructive actions
- [ ] Error toast notifications working
- [ ] Session check on app startup (`GET /api/auth/me`)

### Core Functionality Validation (MVP Phase 1)

#### Central Intelligence (CI-CORE-00)
- [ ] Chat interface accepts messages and displays responses
- [ ] Routes "marketing" questions to Marketing Director agent
- [ ] Routes "sales" questions to Sales Director agent
- [ ] Routes "fulfillment" questions to Fulfillment Director agent
- [ ] Conversation history persists within session
- [ ] Loading state shows during AI processing
- [ ] Error messages display if agent fails
- [ ] WebSocket streaming works for real-time responses

#### Transcriber (CI-CORE-01)
- [ ] Accepts video URL or file upload
- [ ] Downloads video, extracts audio
- [ ] Sends to OpenAI Whisper
- [ ] Stores transcript in `call_transcripts` table
- [ ] Routes to correct analyzer agent (sales/coaching/accountability)
- [ ] Duplicates detected via SHA-256 hash
- [ ] File size validated <25MB
- [ ] Progress indicator shown during transcription

#### Marketing Director (CI-MKT-DIR)
- [ ] Agent class created with Claude SDK
- [ ] 6 specialist agents registered as callable tools
- [ ] System prompt trained on marketing domain
- [ ] Can be called by Central Intelligence agent
- [ ] Returns structured JSON response
- [ ] Has read access to all shared Supabase tables

#### Sales Director (CI-SLS-DIR)
- [ ] Same as Marketing Director (templates copied)
- [ ] 3 specialist agents for Sales specialists
- [ ] System prompt trained on sales/leads domain
- [ ] Registered as tool on Central Intelligence agent

#### Fulfillment Director (CI-FUL-DIR)
- [ ] Same as above
- [ ] 4 specialist agents for Fulfillment specialists
- [ ] System prompt trained on member success domain

#### Shared Intelligence Tables
- [ ] `pain_points` table: created, schema correct, populated from analyzers
- [ ] `wins` table: created, schema correct, populated from coaching analyzer
- [ ] `content_ideas` table: created, status lifecycle (new→used→archived)
- [ ] `objections` table: created, populated from sales calls
- [ ] `goals` table: created, structured format with status
- [ ] `icp` table: created, populated by ICP Generator agent
- [ ] `offers` table: created, populated by Offer Generator agent
- [ ] `comments` table: created, populated by Comments Collector agent
- [ ] `call_transcripts`: created, metadata schema correct
- [ ] `bee_analysis_log`: created, all analysis results logged
- [ ] `bee_error_log`: created, all errors logged
- [ ] `audit_log`: created, all CRUD operations logged
- [ ] `idempotency_keys`: created, duplicate prevention working
- [ ] `users`: created, auth users stored
- [ ] `reference`: created, domain frameworks stored

#### Web Dashboard
- [ ] Landing page (`/`) loads with placeholder department cards
- [ ] Marketing dashboard (`/marketing`) shows KPI overview
- [ ] Sales dashboard (`/sales`) shows pipeline metrics
- [ ] Fulfillment dashboard (`/fulfillment`) shows member success metrics
- [ ] Chat page (`/chat`) sends messages and receives responses via WebSocket
- [ ] All pages have proper error boundaries
- [ ] All pages load within 2 seconds
- [ ] Responsive design works on mobile (TBD - Sprint 8)

### Post-Launch Monitoring

**Day 1 Checklist**:
- [ ] Sentry error tracking connected
- [ ] FastAPI execution logs monitored for failures
- [ ] API latency monitored (target <2s)
- [ ] Supabase quota monitored (warn at 80%, alert at 95%)
- [ ] OpenAI API quota monitored
- [ ] Database backup configured + tested

**First Week**:
- [ ] No P0 errors unresolved >24 hours
- [ ] Uptime ≥98%
- [ ] User feedback collected (survey, direct message)
- [ ] Performance metrics baseline established
- [ ] Bug hotfixes deployed within 4 hours

**First Month**:
- [ ] Usage patterns analyzed
- [ ] Performance optimizations applied if needed
- [ ] User adoption metrics reviewed
- [ ] Roadmap adjusted based on feedback

---

## Section 13: Stakeholder Sign-Off

### Approval Matrix

| Role | Approval Authority | Status | Date |
|------|-------------------|--------|------|
| **Greg** (Product Owner) | Vision, scope, priorities | Pending | — |
| **Python/FastAPI Engineer** | Technical feasibility, sprints | Pending | — |
| **Frontend Developer** | UI/UX design, component library | Pending | — |
| **AI/Claude SDK Specialist** | Prompt engineering, agent design | Pending | — |

### Sign-Off Template

**I, [Name], understand and approve this PRD.**

- [x] Scope is clear and achievable in ~17 weeks
- [x] 194 features, 635 story points realistic for 3-person team
- [x] Success metrics are measurable
- [x] Risk mitigations are adequate
- [x] Data integrity and security architecture sound
- [x] Timeline accommodates Sprint 5/6 complexity
- [ ] Ready to begin Sprint 1a

---

## Section 14: Document References

### Internal Project Documents

| Document | Purpose | Link |
|----------|---------|------|
| **Technical Plan v3.0** | System architecture, tech stack, agent hierarchy, FastAPI patterns | `/projects/workerbee/technical-plan.md` |
| **Feature Breakdown** | 194 features × 635 story points, per-agent task lists | `/projects/workerbee/feature-breakdown.md` |
| **Sprint Plan v3.0** | 8 sprints, task allocation, risk mitigation, staffing | `/projects/workerbee/sprint-plan.md` |
| **API Contract v3.0** | 33+ FastAPI endpoints, authentication, request/response schemas | `/projects/workerbee/api-contract.md` |
| **Data Schema v3.0** | 16 Supabase PostgreSQL tables, SQLAlchemy ORM, Repository pattern | `/projects/workerbee/data-schema.md` |
| **Critical Fixes** | P0/P1/P2 issues, auth system, error handling requirements | `/projects/workerbee/critical-fixes.md` |
| **Client Requirements** | Project explanation transcript from Greg | `/projects/workerbee/template/project-explanation.md` |

### External References

| Resource | Purpose |
|----------|---------|
| [Anthropic Claude SDK](https://github.com/anthropics/anthropic-sdk-python) | Python client library for Claude API |
| [FastAPI Documentation](https://fastapi.tiangolo.com/) | Web framework for API endpoints |
| [Next.js Documentation](https://nextjs.org/docs) | React framework, App Router, API routes |
| [OpenAI API Docs](https://platform.openai.com/docs) | Whisper transcription API |
| [Supabase Documentation](https://supabase.com/docs) | PostgreSQL database, authentication, RLS |
| [SQLAlchemy Docs](https://docs.sqlalchemy.org/) | Python ORM for database access |
| [NextAuth.js Docs](https://next-auth.js.org/) | Authentication, session management, JWT |
| [TanStack Query Docs](https://tanstack.com/query/latest) | Server state management, caching |
| [shadcn/ui Components](https://ui.shadcn.com/) | UI component library (Tailwind + Radix) |
| [Celery Documentation](https://docs.celeryproject.io/) | Async task queue with Redis broker |

---

## Section 15: Glossary

### Core Concepts

| Term | Definition |
|------|-----------|
| **Central Intelligence / Central Intelligence** | Unified AI automation platform organized as organizational hierarchy (Central Intelligence + Directors + Specialists + Operators) |
| **Central Intelligence** | CEO-level AI agent (CI-CORE-00) answering strategic business questions across all departments |
| **Director** | Department-level AI agent coordinator (Marketing, Sales, Fulfillment) that routes work to specialists and aggregates insights |
| **Specialist** | Domain-expert AI agent with deep knowledge of one area (Email, Social, Leads, Members, etc.) |
| **Operator** | Single-purpose shared utility agent (Transcriber, ICP Generator, Stats Updater) used by multiple specialists |
| **Shared Intelligence Pool** | Set of 16 Supabase PostgreSQL tables (pain_points, wins, goals, content_ideas, icp, offers, etc.) accessible to all specialists |
| **Central Intelligence Registry** | Metadata table tracking all agent IDs, names, levels, system prompts |
| **FastAPI Endpoint** | HTTP endpoint provided by FastAPI, called by web app to trigger agent execution |
| **Claude SDK** | Python client library for communicating with Anthropic Claude API |
| **Agent Class** | Python class inheriting from base Agent, implements Claude interactions and business logic |

### Technical Terms

| Term | Definition |
|------|-----------|
| **JWT Session** | JSON Web Token stored in HttpOnly cookie, 30-minute sliding window |
| **Bearer Token** | JWT token sent in Authorization header for API authentication |
| **Soft Delete** | Mark record as deleted (`deleted_at = NOW()`) instead of removing from database, enables recovery |
| **Optimistic Locking** | Check `updated_at` + `If-Match` header before save, prevent concurrent edit conflicts |
| **Idempotency Key** | Unique key per form submission, stored to prevent duplicates on retry |
| **Graceful Degradation** | System continues functioning (partial data) if one component fails |
| **Circuit Breaker** | Stop sending requests to failing external API for cooldown period, prevent cascading failures |
| **Duplicate Detection** | SHA-256 hash of video URL to prevent re-transcribing same file |
| **Status Lifecycle** | State transitions (new → in-progress → used → archived) for content ideas, goals, etc. |
| **Repository Pattern** | Database abstraction layer allowing agent code to swap databases without changes |

### User Roles

| Role | Permissions | User Count (MVP) |
|------|-----------|-----------------|
| **Owner** | All operations, user management, settings | 1 (Greg) |
| **Admin** | All operations except user management | 0 (future) |
| **Team** | Read dashboards, generate content, add data | 2-5 (future) |
| **Viewer** | Read-only access to dashboards | 0 (future) |

### Data Entities

| Entity | Purpose |
|--------|---------|
| **Lead** | Prospect in sales funnel, tracked from source to sale |
| **Member** | Customer in fulfillment program, tracked for goals + submissions |
| **Pain Point** | Customer problem identified in calls, used for content strategy |
| **Win** | Customer success extracted from coaching calls |
| **Objection** | Sales resistance or concern from calls |
| **Goal** | Member objective from accountability calls |
| **Content Idea** | Suggestion for blog post, script, email, social content |
| **ICP** | Ideal Client Profile synthesized from sales/fulfillment data |
| **Offer** | Product/service offer with features, pricing, positioning |
| **Call Transcript** | Text extraction from video/audio via Whisper |

### Department-Specific Terminology

**Marketing**:
- **Reach**: Total audience size (social media followers, email subscribers)
- **Engagement**: Interactions (likes, comments, replies, clicks)
- **Conversion Rate**: % of audience taking desired action (link click, email open, form submission)
- **Content Calendar**: Schedule of planned posts/emails

**Sales**:
- **Pipeline**: Funnel of leads at different stages (prospect → appointment → application → sale)
- **Conversion Rate**: % moving from one stage to next (lead → appointment)
- **Lead Source**: Where lead came from (webinar, VSL, opt-in list)
- **Close Rate**: % of applications converted to sales

**Fulfillment**:
- **Member Retention**: % of members continuing program
- **Goal Attainment**: % of members achieving their goals
- **Submission Rate**: % of members completing required submissions
- **Accountability**: Member's commitment to goals tracked over calls

---

## Appendix A: Feature Count by Department

| Department | Specialists | Features | Story Points |
|-----------|-----------|----------|--------------|
| **Core** | Central Intelligence, Transcriber, Error Handler | 18 | 64 |
| **Marketing** | 6 (Social, Email, Funnels, Ads, DM, Offers) | 42 | 138 |
| **Sales** | 3 (Appointments, Leads, Sales Calls) | 32 | 118 |
| **Fulfillment** | 4 (Members, Coaching, Accountability, Tech SOS) | 31 | 99 |
| **Operators** | 7 (Transcriber, ICP, Offer, Stats × 4) | 14 | 38 |
| **Cross-Cutting** | Auth, Error Handling, Edge Cases, Migration, Intelligence | 39 | 125 |
| **Directors** | 3 (Marketing, Sales, Fulfillment) | 18 | 55 |
| **Totals** | **27 total agents** | **194 features** | **635 story points** |

---

## Appendix B: API Endpoint Summary

### Authentication (3 endpoints)
- `POST /api/auth/login` — Validate credentials
- `POST /api/auth/change-password` — Update password
- `GET /api/auth/me` — Return current user

### Central Intelligence (2 endpoints)
- `POST /api/central-intelligence/chat` — Accept message, return response (WebSocket for streaming)
- `GET /api/central-intelligence/summary` — Dashboard summary

### Directors (6 endpoints)
- `GET /api/marketing/summary` — Marketing KPI aggregation
- `GET /api/sales/summary` — Sales pipeline aggregation
- `GET /api/fulfillment/summary` — Member success aggregation

### Marketing Specialists (12 endpoints)
- `POST /api/social/analyze`, `POST /api/social/generate-script`, `GET /api/social/stats`
- `POST /api/email/analyze`, `POST /api/email/draft`, `GET /api/email/stats`
- `POST /api/funnels/analyze`, `GET /api/funnels/stats`
- `POST /api/ads/analyze`, `POST /api/ads/generate`, `GET /api/ads/stats`
- `POST /api/dm/analyze`, `POST /api/dm/templates`, `GET /api/dm/stats`
- `POST /api/offers/generate`, `POST /api/offers/optimize`, `GET /api/offers`

### Sales Specialists (9 endpoints)
- `GET /api/leads`, `POST /api/leads`, `PUT /api/leads/:id`, `DELETE /api/leads/:id`
- `GET /api/leads/stats`, `GET /api/leads/funnel`
- `GET /api/appointments/stats`, `POST /api/appointments/analyze`
- `GET /api/sales-calls`, `POST /api/sales-calls/analyze`

### Fulfillment Specialists (10 endpoints)
- `GET /api/members`, `POST /api/members`, `GET /api/members/:id`, `PUT /api/members/:id`
- `POST /api/coaching/analyze`, `GET /api/coaching`
- `POST /api/accountability/analyze`, `GET /api/accountability`
- `POST /api/tech-sos/submit`, `GET /api/tech-sos/issues`

### Shared Operators (8 endpoints)
- `POST /api/transcribe` — Video → transcript
- `GET /api/icp`, `POST /api/icp/generate` — ICP management
- `GET /api/offers`, `POST /api/offers/generate` — Offer management
- (Stats updaters called internally, not user-facing)

### Admin (3 endpoints)
- `GET /api/health` — System health check
- `GET /api/errors` — Error log viewer
- `POST /api/admin/import` — Data migration trigger

**Total: 33+ FastAPI endpoints**

---

## Document Control

| Item | Value |
|------|-------|
| **Document Version** | 3.0.0 |
| **Last Updated** | March 29, 2026 |
| **Version Notes** | Complete migration from n8n to Python + Claude SDK agentic architecture. Replaced all n8n workflows with Python agent classes. Replaced n8n Data Tables with Supabase PostgreSQL + SQLAlchemy ORM. Added FastAPI endpoints, Celery task queue, WebSocket streaming, and Sentry observability. |
| **Next Review** | After Sprint 1b (Week 4) |
| **Owner** | Product Management (Greg) |
| **Distribution** | Team (Python Engineer, Frontend Dev, AI Specialist) |
| **Status** | ACTIVE - Ready for Sprint Planning |

---

## Sign-Off (To Be Completed Before Sprint 1a Kickoff)

**By signing below, I confirm I have read and understand the PRD and commit to delivering the described features within the planned timeline.**

---

**Product Owner (Greg)**

Signature: ___________________________  Date: _______________

**Python/FastAPI Engineer**

Signature: ___________________________  Date: _______________

**Frontend Developer**

Signature: ___________________________  Date: _______________

**AI/Claude SDK Specialist**

Signature: ___________________________  Date: _______________

---

**END OF PRODUCT REQUIREMENTS DOCUMENT**

---

## Quick Navigation

- [Executive Summary](#executive-summary) — High-level overview
- [Business Context](#section-1-business-context) — Current state → desired state
- [User Stories](#section-4-user-stories-with-acceptance-criteria) — 15 detailed stories with acceptance criteria
- [Feature Summary](#section-5-functional-requirements-summary) — What each agent does
- [Non-Functional Requirements](#section-6-non-functional-requirements) — Performance, security, scalability
- [System Architecture](#section-7-system-architecture-overview) — 3-tier hierarchy diagram
- [Success Metrics](#section-8-success-metrics--kpis) — How we'll measure success
- [MVP Scope](#section-3-product-scope--mvp) — What's in Phase 1
- [Risk & Mitigation](#section-11-risks--mitigations) — Known issues and solutions
- [Release Criteria](#section-12-release-criteria--definition-of-done) — Launch validation checklist
- [Glossary](#section-15-glossary) — Key terms and definitions
- [References](#section-14-document-references) — Links to detailed docs

