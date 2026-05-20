# Central Intelligence (Central Intelligence) - Feature Breakdown

All Central Intelligences broken down by individual features with task IDs, owners, and descriptions.

## Legend

| Tag | Role |
| --- | ---- |
| `[PY]` | Python/Backend Developer - agent classes, FastAPI endpoints, Claude SDK integration |
| `[FE]` | Frontend Developer - Next.js pages, React components, charts, styling |
| `[AI]` | AI/Integration Specialist - prompt engineering, data modeling, transcription |

**Story Points Scale**: 1 (trivial) → 3 (small) → 5 (medium) → 8 (large)

---

## Core

### CI-CORE-00: Central Intelligence Orchestrator

Central AI orchestrator (CEO). Coordinates 3 Department Directors and provides cross-department business intelligence.

| # | Feature | Owner | Pts | Sprint | Description |
| - | ------- | ----- | --- | ------ | ----------- |
| C00-1 | Central Intelligence agent class | `[PY]` | 5 | 1 | Create agent with input/output tools, chat state management via Repository pattern |
| C00-2 | Central Intelligence system prompt | `[AI]` | 3 | 1 | Write system prompt defining Central Intelligence persona, tool usage rules, business context |
| C00-3 | FastAPI chat endpoint | `[PY]` | 3 | 1 | POST `/api/central-intelligence/chat` with auth header, session ID support, Claude SDK integration |
| C00-4 | Chat UI page | `[FE]` | 5 | 1 | `/chat` page - message input, response display, conversation history, loading states |
| C00-5 | API client library | `[FE]` | 3 | 1 | `lib/api-client.ts` - reusable HTTP client with auth, error handling, typing |
| C00-6 | Agent class templates (Director + Specialist + Operator) | `[PY]` | 5 | 1 | Three reusable base classes for each org chart level |
| C00-7 | Supabase tables setup | `[PY]` | 5 | 1 | Create all 16 tables: 10 original + objections, goals, icp, offers, comments, reference |
| C00-8 | App shell & navigation | `[FE]` | 5 | 1 | Next.js layout with sidebar (Marketing, Sales, Fulfillment, Chat sections), responsive |
| C00-9 | Dashboard landing page | `[FE]` | 3 | 1 | Main `/` page with department summary cards (placeholder data initially) |

**Subtotal**: 9 features, 37 points

---

## Directors (Level 3)

### CI-MKT-DIR: Marketing Director

Department-level AI orchestrator for Marketing. Knows everything about marketing data, coordinates 6 marketing specialists, provides department-level summaries and dashboards.

| # | Feature | Owner | Pts | Sprint | Description |
| - | ------- | ----- | --- | ------ | ----------- |
| DIR-M1 | Marketing Director agent class | `[PY]` | 5 | 2 | Agent with tool definitions for all 6 marketing specialists |
| DIR-M2 | Marketing Director system prompt | `[AI]` | 3 | 2 | Department expertise, specialist routing rules, marketing KPIs |
| DIR-M3 | Repository access (goals, wins, pain_points, objections, content_ideas, icp, offers) | `[PY]` | 3 | 2 | Repository queries for all cross-domain intelligence tables |
| DIR-M4 | Marketing summary endpoint | `[PY]` | 2 | 2 | GET `/api/marketing/summary` — department-level KPI aggregation |
| DIR-M5 | Register with Central Intelligence | `[PY]` | 1 | 2 | Add as tool definition on Central Intelligence agent |
| DIR-M6 | Marketing overview dashboard | `[FE]` | 5 | 2 | `/marketing` landing page — department KPIs, specialist status cards |

**Subtotal**: 6 features, 19 points

### CI-SLS-DIR: Sales Director

Department-level AI orchestrator for Sales. Coordinates 3 sales specialists, provides pipeline analytics and department summaries.

| # | Feature | Owner | Pts | Sprint | Description |
| - | ------- | ----- | --- | ------ | ----------- |
| DIR-S1 | Sales Director agent class | `[PY]` | 5 | 5 | Agent with tool definitions for all 3 sales specialists |
| DIR-S2 | Sales Director system prompt | `[AI]` | 3 | 5 | Sales pipeline expertise, specialist routing, revenue KPIs |
| DIR-S3 | Repository access | `[PY]` | 2 | 5 | Repository queries for cross-domain intelligence |
| DIR-S4 | Sales summary endpoint | `[PY]` | 2 | 5 | GET `/api/sales/summary` — pipeline metrics aggregation |
| DIR-S5 | Register with Central Intelligence | `[PY]` | 1 | 5 | Add as tool definition on Central Intelligence agent |
| DIR-S6 | Sales overview dashboard | `[FE]` | 5 | 5 | `/sales` landing page — pipeline KPIs, specialist status |

**Subtotal**: 6 features, 18 points

### CI-FUL-DIR: Fulfillment Director

Department-level AI orchestrator for Fulfillment. Coordinates 4 fulfillment specialists, tracks member success metrics.

| # | Feature | Owner | Pts | Sprint | Description |
| - | ------- | ----- | --- | ------ | ----------- |
| DIR-F1 | Fulfillment Director agent class | `[PY]` | 5 | 6 | Agent with tool definitions for all 4 fulfillment specialists |
| DIR-F2 | Fulfillment Director system prompt | `[AI]` | 3 | 6 | Member success expertise, specialist routing, retention KPIs |
| DIR-F3 | Repository access | `[PY]` | 2 | 6 | Repository queries for cross-domain intelligence |
| DIR-F4 | Fulfillment summary endpoint | `[PY]` | 2 | 6 | GET `/api/fulfillment/summary` — member success aggregation |
| DIR-F5 | Register with Central Intelligence | `[PY]` | 1 | 6 | Add as tool definition on Central Intelligence agent |
| DIR-F6 | Fulfillment overview dashboard | `[FE]` | 5 | 6 | `/fulfillment` landing page — member KPIs, specialist status |

**Subtotal**: 6 features, 18 points

---

## Operators (Level 1 — Shared "Floaters")

### CI-OPS-ICP: ICP Generator

Generates and updates Ideal Client Profiles from call data, pain points, objections, and wins.

| # | Feature | Owner | Pts | Sprint | Description |
| - | ------- | ----- | --- | ------ | ----------- |
| OPS-I1 | ICP Generator agent | `[PY]` | 3 | 2 | Celery task, read pain_points + objections + wins from repositories |
| OPS-I2 | ICP generation prompt | `[AI]` | 5 | 2 | AI prompt to synthesize ICP from aggregated client data |
| OPS-I3 | Store to icp table | `[PY]` | 2 | 2 | Write structured ICP to Supabase icp table via Repository |
| OPS-I4 | ICP endpoints | `[PY]` | 2 | 2 | POST `/api/icp/generate`, GET `/api/icp` |
| OPS-I5 | ICP viewer UI | `[FE]` | 3 | 3 | `/marketing/icp` - ICP cards with demographics, psychographics, triggers |

**Subtotal**: 5 features, 15 points

### CI-OPS-OFFER: Offer Generator

Generates product/service offer structures using ICP data, pain points, and objections.

| # | Feature | Owner | Pts | Sprint | Description |
| - | ------- | ----- | --- | ------ | ----------- |
| OPS-O1 | Offer Generator agent | `[PY]` | 3 | 4 | Celery task, read icp + pain_points + objections from repositories |
| OPS-O2 | Offer generation prompt | `[AI]` | 5 | 4 | AI prompt to create offer structure (features, pricing, positioning) |
| OPS-O3 | Store to offers table | `[PY]` | 2 | 4 | Write offer to Supabase offers table via Repository |
| OPS-O4 | Offer endpoints | `[PY]` | 2 | 4 | POST `/api/offers/generate`, GET `/api/offers`, PUT `/api/offers/:id` |

**Subtotal**: 4 features, 12 points

### Stats Updater Operators

Per-domain stats importers that pull metrics from source databases. Shared across specialists.

| # | Feature | Owner | Pts | Sprint | Description |
| - | ------- | ----- | --- | ------ | ----------- |
| OPS-SE1 | Email Stats Updater | `[PY]` | 2 | 3 | Celery scheduled task: Pull email campaign metrics from Google Sheets/Airtable |
| OPS-SS1 | Social Stats Updater | `[PY]` | 2 | 3 | Celery scheduled task: Pull social media metrics from Airtable |
| OPS-SF1 | Funnel Stats Updater | `[PY]` | 2 | 3 | Celery scheduled task: Pull funnel conversion data from Airtable |
| OPS-SA1 | Ads Stats Updater | `[PY]` | 2 | 4 | Celery scheduled task: Pull ad metrics from Airtable |
| OPS-SC1 | Comments Collector | `[PY]` | 3 | 3 | Celery task: Pull social media comments, run sentiment analysis, store in comments table |

**Subtotal**: 5 features, 11 points

---

### CI-CORE-ERR: Error Handler

Centralized error logging. Every Central Intelligence's error routes here.

| # | Feature | Owner | Pts | Sprint | Description |
| - | ------- | ----- | --- | ------ | ----------- |
| ERR-01 | Error handler agent | `[PY]` | 5 | 1b | Centralized error capture → write to bee_error_log table → alert on critical |
| ERR-05 | Health check endpoint (GET /api/health) | `[PY]` | 1 | 1b | Lightweight connectivity check for frontend monitoring |

**Subtotal**: 2 features, 6 points

### CI-CORE-01: Call Transcriber

Video-to-transcript pipeline using OpenAI Whisper. Routes transcripts to appropriate analyzers.

| # | Feature | Owner | Pts | Sprint | Description |
| - | ------- | ----- | --- | ------ | ----------- |
| T01-1 | Transcriber agent | `[PY]` | 3 | 2 | Celery task, accept video URL, download video |
| T01-2 | Audio extraction & Whisper | `[AI]` | 5 | 2 | Download video, OpenAI Whisper transcription via API |
| T01-3 | Transcript storage | `[PY]` | 2 | 2 | Store transcript + metadata in Supabase call_transcripts table |
| T01-4 | Call type routing | `[PY]` | 3 | 2 | Route output to correct analyzer based on call_type parameter (sales/coaching/accountability) |
| T01-5 | Transcription endpoint | `[PY]` | 2 | 2 | POST `/api/transcribe` accepting video URL + call type |
| T01-6 | Register as shared operator | `[PY]` | 1 | 2 | Add as tool definition for any Director or Specialist agent |
| T01-7 | Transcript upload UI | `[FE]` | 5 | 2 | Shared component: video URL input form, progress indicator, transcript viewer |

**Subtotal**: 7 features, 21 points

---

## Sales

### CI-SAL-01: Appointment Setting Bot

Analyzes GHL appointment conversations and suggests script improvements.

| # | Feature | Owner | Pts | Sprint | Description |
| - | ------- | ----- | --- | ------ | ----------- |
| S01-1 | Appointment Setting agent | `[PY]` | 5 | 5 | Celery task, fetch conversation data from GHL via API |
| S01-2 | Conversation analysis prompt | `[AI]` | 5 | 5 | AI prompt to analyze appointment conversations, suggest improvements |
| S01-3 | Script suggestions | `[AI]` | 3 | 5 | Generate script improvement suggestions based on patterns |
| S01-4 | GHL data integration | `[PY]` | 5 | 5 | Fetch contacts, opportunities, conversations from HighLevel API |
| S01-5 | Appointment endpoints | `[PY]` | 2 | 5 | GET `/api/appointments/stats`, POST `/api/appointments/analyze` |
| S01-6 | Register with Sales Director | `[PY]` | 1 | 5 | Add tool definition to CI-SLS-DIR |
| S01-7 | Appointments dashboard | `[FE]` | 5 | 5 | `/sales/appointments` - KPI cards (set rate, show rate, close rate) |
| S01-8 | Conversation analytics | `[FE]` | 5 | 5 | Charts showing conversation patterns, response times |
| S01-9 | Script suggestions UI | `[FE]` | 3 | 5 | AI suggestions panel with before/after script comparisons |

**Subtotal**: 9 features, 34 points

### CI-SAL-02: Leads Database Worker

Queries, aggregates, and manages lead data. Tracks leads, appointments, applications, and sales.

| # | Feature | Owner | Pts | Sprint | Description |
| - | ------- | ----- | --- | ------ | ----------- |
| S02-1 | Leads Worker agent | `[PY]` | 5 | 5 | Celery task, Repository queries for leads/engagements/appointments/applications/sales |
| S02-2 | Leads query operations | `[PY]` | 5 | 5 | Filter by date range, source (webinar/VSL/opt-in), status, engagement type via Repository |
| S02-3 | Leads aggregation logic | `[PY]` | 5 | 5 | Python code to compute stats: totals, conversion rates, source breakdowns, funnel metrics |
| S02-4 | Lead endpoints | `[PY]` | 3 | 5 | GET `/api/leads`, GET `/api/leads/stats`, GET `/api/leads/funnel` with query params |
| S02-5 | Register with Sales Director | `[PY]` | 2 | 5 | Add tool definition to CI-SLS-DIR |
| S02-6 | Leads dashboard page | `[FE]` | 3 | 5 | `/sales/leads` - overview with KPI cards (total leads, conversion rate, etc.) |
| S02-7 | Lead volume chart | `[FE]` | 3 | 5 | Time-series chart (Recharts) showing leads by week/month |
| S02-8 | Source breakdown chart | `[FE]` | 3 | 5 | Pie/bar chart: webinar vs VSL vs opt-in breakdown |
| S02-9 | Conversion funnel viz | `[FE]` | 5 | 5 | Funnel chart: leads → appointments → applications → sales |
| S02-10 | Leads data table | `[FE]` | 5 | 5 | Sortable/filterable table with all leads, engagement details, scores |
| S02-11 | Date & source filters | `[FE]` | 3 | 5 | Filter bar component: date range picker, source multi-select, status dropdown |
| S02-12 | Leads CRUD operations | `[PY]` | 5 | 5 | FastAPI endpoints for creating, updating, and deleting leads (write-back to Supabase) |
| S02-13 | Inline edit UI | `[FE]` | 5 | 5 | Edit lead details directly from the table/detail view, add new leads, update statuses |

**Subtotal**: 13 features, 52 points

### CI-SAL-03: Sales Call Analyzer

Extracts pain points and content ideas from sales call transcripts.

| # | Feature | Owner | Pts | Sprint | Description |
| - | ------- | ----- | --- | ------ | ----------- |
| S03-1 | Sales Call Analyzer agent | `[PY]` | 3 | 5 | Celery task, accept transcript text |
| S03-2 | Pain points extraction prompt | `[AI]` | 5 | 5 | AI Agent prompt to extract pain points with structured output |
| S03-3 | Content ideas generation | `[AI]` | 3 | 5 | Generate content ideas from pain points, store in content_ideas table |
| S03-4 | Lead engagement linking | `[PY]` | 3 | 5 | Link analysis to lead record via Repository query |
| S03-5 | Store results | `[PY]` | 2 | 5 | Save to bee_analysis_log + pain_points tables via Repository |
| S03-6 | Sales call endpoint | `[PY]` | 2 | 5 | POST `/api/sales-calls/analyze` |
| S03-7 | Register with Sales Director | `[PY]` | 1 | 5 | Add tool definition to CI-SLS-DIR |
| S03-8 | Sales calls list page | `[FE]` | 5 | 5 | `/sales/calls` - list of analyzed calls with status badges |
| S03-9 | Call detail view | `[FE]` | 5 | 5 | Transcript viewer + extracted pain points + content ideas |
| S03-10 | Pain points feed component | `[FE]` | 3 | 5 | Reusable card component showing pain points (used across pages) |

**Subtotal**: 10 features, 32 points

---

## Fulfillment

### CI-FUL-01: Members Database Worker

Queries and manages member data. Tracks submissions, goals, and call history.

| # | Feature | Owner | Pts | Sprint | Description |
| - | ------- | ----- | --- | ------ | ----------- |
| F01-1 | Members Worker agent | `[PY]` | 3 | 6 | Celery task, Repository queries for members |
| F01-2 | Member query operations | `[PY]` | 3 | 6 | Search, filter by status, track submissions and goals via Repository |
| F01-3 | Member endpoints | `[PY]` | 2 | 6 | GET `/api/members`, GET `/api/members/:id` |
| F01-4 | Register with Fulfillment Director | `[PY]` | 1 | 6 | Add tool definition to CI-FUL-DIR |
| F01-5 | Members directory page | `[FE]` | 5 | 6 | `/fulfillment/members` - searchable member list with avatars |
| F01-6 | Member detail view | `[FE]` | 5 | 6 | Individual member page: submissions, goals, call history |
| F01-7 | Goals progress tracker | `[FE]` | 3 | 6 | Visual progress bars or timeline for member goals |
| F01-8 | Members CRUD operations | `[PY]` | 3 | 6 | FastAPI endpoints for creating, updating members |
| F01-9 | Members inline edit UI | `[FE]` | 3 | 6 | Edit member details directly from the directory/detail view |

**Subtotal**: 9 features, 28 points

### CI-FUL-02: Coaching Call Analyzer

Extracts wins, pain points, and content ideas from coaching call transcripts.

| # | Feature | Owner | Pts | Sprint | Description |
| - | ------- | ----- | --- | ------ | ----------- |
| F02-1 | Coaching Analyzer agent | `[PY]` | 3 | 6 | Celery task, accept transcript |
| F02-2 | Wins extraction prompt | `[AI]` | 5 | 6 | AI prompt to extract client wins, store in wins table |
| F02-3 | Pain points extraction | `[AI]` | 3 | 6 | Extract pain points, store in pain_points table |
| F02-4 | Content ideas generation | `[AI]` | 3 | 6 | Generate ideas from wins + pain points, store in content_ideas table |
| F02-5 | Coaching endpoint | `[PY]` | 2 | 6 | POST `/api/coaching/analyze` |
| F02-6 | Register with Fulfillment Director | `[PY]` | 1 | 6 | Add tool definition to CI-FUL-DIR |
| F02-7 | Coaching calls page | `[FE]` | 5 | 6 | `/fulfillment/coaching` - list of analyzed calls |
| F02-8 | Wins feed component | `[FE]` | 3 | 6 | Reusable wins card component (used across pages) |
| F02-9 | Content ideas feed | `[FE]` | 5 | 6 | Shared component: aggregated content ideas from all sources |

**Subtotal**: 9 features, 30 points

### CI-FUL-03: Accountability Call Analyzer

Extracts goals from accountability calls and tracks progress over time.

| # | Feature | Owner | Pts | Sprint | Description |
| - | ------- | ----- | --- | ------ | ----------- |
| F03-1 | Accountability Analyzer agent | `[PY]` | 3 | 6 | Celery task, accept transcript |
| F03-2 | Goals extraction prompt | `[AI]` | 5 | 6 | AI prompt to extract goals, compare against previous |
| F03-3 | Progress tracking logic | `[PY]` | 5 | 6 | Compare current goals vs previous accountability call goals |
| F03-4 | Accountability endpoint | `[PY]` | 2 | 6 | POST `/api/accountability/analyze` |
| F03-5 | Register with Fulfillment Director | `[PY]` | 1 | 6 | Add tool definition to CI-FUL-DIR |
| F03-6 | Accountability page | `[FE]` | 5 | 6 | `/fulfillment/accountability` - goals timeline per member |
| F03-7 | Progress charts | `[FE]` | 3 | 6 | Visual progress tracking over time |

**Subtotal**: 7 features, 24 points

### CI-FUL-04: Tech SOS Tracker

Tracks and categorizes tech support requests from members.

| # | Feature | Owner | Pts | Sprint | Description |
| - | ------- | ----- | --- | ------ | ----------- |
| F04-1 | Tech SOS agent | `[PY]` | 3 | 6 | Celery task, track incoming tech support requests from members |
| F04-2 | Issue categorization prompt | `[AI]` | 3 | 6 | AI categorizes tech issues, suggests resolutions, identifies patterns |
| F04-3 | Tech SOS endpoints | `[PY]` | 2 | 6 | POST `/api/tech-sos/submit`, GET `/api/tech-sos/issues` |
| F04-4 | Register with Fulfillment Director | `[PY]` | 1 | 6 | Add tool definition to CI-FUL-DIR |
| F04-5 | Tech SOS page | `[FE]` | 5 | 6 | `/fulfillment/tech-sos` - issue list, status tracking, resolution history |
| F04-6 | Issue patterns dashboard | `[FE]` | 3 | 6 | Charts showing common tech issues, resolution times |

**Subtotal**: 6 features, 17 points

---

## Marketing

### CI-MKT-01: Social Media Worker

Analyzes social media metrics and generates scripts informed by cross-domain insights.

| # | Feature | Owner | Pts | Sprint | Description |
| - | ------- | ----- | --- | ------ | ----------- |
| M01-1 | Social Media Worker agent | `[PY]` | 3 | 3 | Celery task, Repository queries for social metrics |
| M01-2 | Social analysis prompt | `[AI]` | 5 | 3 | AI prompt to analyze metrics, pull from content_ideas table |
| M01-3 | Script generation prompt | `[AI]` | 5 | 3 | Generate social media scripts informed by pain points + wins |
| M01-4 | Social endpoints | `[PY]` | 2 | 3 | POST `/api/social/analyze`, POST `/api/social/generate-script` |
| M01-5 | Register with Marketing Director | `[PY]` | 1 | 3 | Add tool definition to CI-MKT-DIR |
| M01-6 | Social media dashboard | `[FE]` | 5 | 3 | `/marketing/social` - metrics charts (reach, engagement, etc.) |
| M01-7 | Script generator UI | `[FE]` | 5 | 3 | Form to request script, display AI-generated scripts |
| M01-8 | Suggestions panel | `[FE]` | 3 | 3 | AI improvement suggestions based on metrics analysis |

**Subtotal**: 8 features, 29 points

### CI-MKT-02: Email Worker

Analyzes email campaigns and drafts emails informed by content ideas.

| # | Feature | Owner | Pts | Sprint | Description |
| - | ------- | ----- | --- | ------ | ----------- |
| M02-1 | Email Worker agent | `[PY]` | 3 | 3 | Celery task, Repository queries for email metrics |
| M02-2 | Email analysis prompt | `[AI]` | 3 | 3 | Analyze open rates, click rates, subject lines, CTAs |
| M02-3 | Email draft prompt | `[AI]` | 3 | 3 | Generate email drafts informed by content_ideas |
| M02-4 | Email endpoints | `[PY]` | 2 | 3 | POST `/api/email/analyze`, POST `/api/email/draft` |
| M02-5 | Register with Marketing Director | `[PY]` | 1 | 3 | Add tool definition to CI-MKT-DIR |
| M02-6 | Email dashboard | `[FE]` | 5 | 3 | `/marketing/email` - campaign metrics, open/click charts |
| M02-7 | Email drafting tool | `[FE]` | 5 | 3 | AI email composer with subject line, body, CTA generation |

**Subtotal**: 7 features, 22 points

### CI-MKT-03: Funnels Worker

Analyzes funnel conversion rates and suggests optimizations.

| # | Feature | Owner | Pts | Sprint | Description |
| - | ------- | ----- | --- | ------ | ----------- |
| M03-1 | Funnels Worker agent | `[PY]` | 3 | 3 | Celery task, Repository queries for funnel data |
| M03-2 | Funnel analysis prompt | `[AI]` | 5 | 3 | Analyze conversion rates, identify drop-offs, suggest fixes |
| M03-3 | Funnels endpoint | `[PY]` | 2 | 3 | POST `/api/funnels/analyze` |
| M03-4 | Register with Marketing Director | `[PY]` | 1 | 3 | Add tool definition to CI-MKT-DIR |
| M03-5 | Funnels dashboard | `[FE]` | 5 | 3 | `/marketing/funnels` - funnel visualization, drop-off charts |
| M03-6 | Optimization suggestions | `[FE]` | 3 | 3 | AI suggestions panel for funnel improvements |

**Subtotal**: 6 features, 19 points

### CI-MKT-04: Ads Worker

Analyzes ad performance and generates ad copy from cross-domain insights.

| # | Feature | Owner | Pts | Sprint | Description |
| - | ------- | ----- | --- | ------ | ----------- |
| M04-1 | Ads Worker agent | `[PY]` | 3 | 4 | Celery task, Repository queries for ad metrics |
| M04-2 | Ad analysis prompt | `[AI]` | 3 | 4 | Analyze ROAS, CTR, CPC, suggest optimizations |
| M04-3 | Ad copy generation prompt | `[AI]` | 3 | 4 | Generate ad copy/scripts from content_ideas + pain_points |
| M04-4 | Ad endpoints | `[PY]` | 2 | 4 | POST `/api/ads/analyze`, POST `/api/ads/generate` |
| M04-5 | Register with Marketing Director | `[PY]` | 1 | 4 | Add tool definition to CI-MKT-DIR |
| M04-6 | Ads dashboard | `[FE]` | 5 | 4 | `/marketing/ads` - ad performance charts |
| M04-7 | Ad copy generator UI | `[FE]` | 5 | 4 | AI copy/script generator with platform targeting |

**Subtotal**: 7 features, 22 points

### CI-MKT-05: DM Specialist

Direct message strategy, conversation templates, and DM performance metrics across platforms.

| # | Feature | Owner | Pts | Sprint | Description |
| - | ------- | ----- | --- | ------ | ----------- |
| M05-1 | DM Specialist agent | `[PY]` | 3 | 4 | Agent with tool definitions for shared intelligence pool + DM-specific context |
| M05-2 | DM analysis prompt | `[AI]` | 3 | 4 | Analyze DM conversations, identify patterns, suggest improvements |
| M05-3 | DM template generation prompt | `[AI]` | 3 | 4 | Generate conversation templates from ICP + pain_points + objections |
| M05-4 | DM endpoints | `[PY]` | 2 | 4 | POST `/api/marketing/dm/analyze`, POST `/api/marketing/dm/templates`, GET `/api/marketing/dm/stats` |
| M05-5 | Register with Marketing Director | `[PY]` | 1 | 4 | Add tool definition to CI-MKT-DIR |
| M05-6 | DM dashboard | `[FE]` | 5 | 4 | `/marketing/dm` — DM metrics, response rates, conversion tracking |
| M05-7 | DM template builder UI | `[FE]` | 5 | 4 | Template library with AI generation, copy-to-clipboard, platform tags |

**Subtotal**: 7 features, 22 points

### CI-MKT-06: Offer Creation Specialist

Creates and optimizes product/service offers using ICP data, pain points, wins, and market insights.

| # | Feature | Owner | Pts | Sprint | Description |
| - | ------- | ----- | --- | ------ | ----------- |
| M06-1 | Offer Specialist agent | `[PY]` | 3 | 4 | Agent with tool definitions for offers, icp, pain_points, wins, objections repositories |
| M06-2 | Offer optimization prompt | `[AI]` | 5 | 4 | Analyze existing offers, suggest pricing/positioning improvements from data |
| M06-3 | Offer creation prompt | `[AI]` | 3 | 4 | Generate new offer structures (features, pricing tiers, positioning, bonuses) |
| M06-4 | Offer endpoints | `[PY]` | 2 | 4 | POST `/api/marketing/offers/create`, POST `/api/marketing/offers/optimize`, GET `/api/marketing/offers` |
| M06-5 | Register with Marketing Director | `[PY]` | 1 | 4 | Add tool definition to CI-MKT-DIR |
| M06-6 | Offers dashboard | `[FE]` | 5 | 4 | `/marketing/offers` — offer library, performance comparison |
| M06-7 | Offer builder UI | `[FE]` | 5 | 4 | Guided offer creation form with AI suggestions, preview, versioning |

**Subtotal**: 7 features, 24 points

---

## Data Migration

### Data Migration Worker (One-Time + Ongoing Sync)

Imports existing data from current systems into the new platform.

| # | Feature | Owner | Pts | Sprint | Description |
| - | ------- | ----- | --- | ------ | ----------- |
| DM-1 | Data import agent | `[PY]` | 5 | 7 | Python script/Celery task: Import existing data from Airtable/GHL/Google Sheets into Supabase |
| DM-2 | Data mapping logic | `[PY]` | 3 | 7 | Map fields from current databases to standardized schema |
| DM-3 | Sync verification | `[PY]` | 2 | 7 | Validate imported data matches source, report discrepancies |
| DM-4 | Data import admin page | `[FE]` | 3 | 7 | `/admin/import` - trigger imports, view status, review mapping |

**Subtotal**: 4 features, 13 points

---

## Authentication & Security (Sprint 1b)

### Login System + API Security

User authentication via NextAuth.js + HMAC-signed FastAPI requests.

| # | Feature | Owner | Pts | Sprint | Description |
| - | ------- | ----- | --- | ------ | ----------- |
| SEC-01 | NextAuth.js setup (Credentials Provider + JWT) | `[FE]` | 5 | 1b | NextAuth config, JWT strategy, HttpOnly cookie session |
| SEC-02 | Login page UI | `[FE]` | 3 | 1b | `/login` page with email/password, "Remember me", error states |
| SEC-03 | Auth middleware + protected routes | `[FE]` | 2 | 1b | Middleware redirecting unauthenticated users to /login |
| SEC-04 | FastAPI auth endpoints (login, password, me) | `[PY]` | 3 | 1b | POST /api/auth/login, POST /api/auth/change-password, GET /api/auth/me |
| SEC-05 | HMAC request signing (X-Signature-256) | `[PY]` | 3 | 1b | Request signing + replay protection (5-min window) |
| SEC-06 | Endpoint path obfuscation | `[PY]` | 2 | 8 | Random prefix on endpoint paths to prevent enumeration |
| SEC-07 | Token rotation mechanism | `[PY]` | 2 | 8 | Rotate Bearer tokens without downtime |

**Subtotal**: 7 features, 20 points

---

## Error Handling & UX Infrastructure (Sprints 1b, 2, 6)

### Frontend Error Handling + API Client Hardening

Comprehensive error handling across all application layers.

| # | Feature | Owner | Pts | Sprint | Description |
| - | ------- | ----- | --- | ------ | ----------- |
| ERR-02 | Error boundary components (root + section) | `[FE]` | 3 | 1b | React error boundaries catching crashes gracefully |
| ERR-03 | Toast notification system | `[FE]` | 2 | 1b | Success/error/warning toasts via shadcn/ui |
| ERR-04 | API client interceptor (timeout, retry, errors) | `[FE]` | 3 | 1b | AbortController timeouts, exponential backoff, error normalization |
| ERR-06 | Admin error monitoring dashboard | `[FE]` | 3 | 6 | `/admin/errors` - errors by worker/severity with resolution |
| UX-01 | Skeleton loader components (card, table, chart) | `[FE]` | 3 | 2 | Loading placeholders during data fetch |
| UX-02 | Empty state components with CTAs | `[FE]` | 2 | 2 | "No data yet" screens guiding new users |
| UX-03 | Confirm dialog for destructive actions | `[FE]` | 2 | 2 | AlertDialog wrapper required before delete/archive |

**Subtotal**: 7 features, 18 points

---

## Edge Cases & Data Integrity (Sprints 2-7)

### Cross-Cutting Edge Case Handlers

Systematic handling of data integrity, concurrency, and reliability edge cases.

| # | Feature | Owner | Pts | Sprint | Description |
| - | ------- | ----- | --- | ------ | ----------- |
| EC-01 | Optimistic locking (updatedAt + If-Match) | `[PY]` | 3 | 2 | 409 Conflict when stale data submitted |
| EC-02 | Circuit breaker pattern | `[PY]` | 3 | 8 | Stop cascading failures during Airtable/OpenAI outages |
| EC-03 | Soft delete with deleted_at | `[PY]` | 3 | 3 | All mutable tables use soft delete instead of hard delete |
| EC-04 | Stale data indicator | `[FE]` | 2 | 3 | "Last updated" + TanStack Query staleTime config |
| EC-06 | Transcription edge cases | `[PY]` | 3 | 2 | URL HEAD check, file size validation before Whisper |
| EC-07 | Duplicate transcript detection | `[PY]` | 2 | 2 | SHA-256 video_url_hash dedup |
| EC-08 | Content idea status lifecycle | `[PY]` | 2 | 3 | Auto + manual status transitions (new→used→archived) |
| EC-09 | Pain point frequency dedup | `[PY]` | 2 | 5 | contributing_transcripts array prevents double-counting |
| EC-10 | Structured member goals | `[PY]` | 3 | 6 | Goal objects with status replacing free-text JSON array |
| EC-11 | Add member_id to call_transcripts | `[PY]` | 1 | 5 | Link calls to specific members |
| EC-12 | Lead-to-member conversion workflow | `[PY]` | 3 | 5 | Auto-create member when lead status = "sale" |
| EC-13 | GHL sync conflict resolution | `[PY]` | 3 | 7 | Timestamp-based resolution + conflict logging |
| EC-14 | Transcript queue processor | `[PY]` | 3 | 5 | Async processing with configurable concurrency limit |

**Subtotal**: 13 features, 33 points

---

## Central Intelligence Intelligence (Phase 8)

Final enhancement phase for cross-domain business optimization.

| # | Feature | Owner | Pts | Sprint | Description |
| - | ------- | ----- | --- | ------ | ----------- |
| Q6-1 | Enhanced system prompt | `[AI]` | 5 | 8 | Business optimization framework, prioritization logic |
| Q6-2 | Weekly digest workflow | `[PY]` | 5 | 8 | Scheduled Celery task → aggregate all data → generate weekly summary |
| Q6-3 | Persistent memory | `[PY]` | 3 | 8 | Store conversation history in Supabase chat_memory table |
| Q6-4 | Executive dashboard | `[FE]` | 8 | 8 | `/` page upgrade - cross-department KPIs, trends, charts |
| Q6-5 | Weekly focus widget | `[FE]` | 5 | 8 | Central Intelligence's prioritized "focus this week" recommendations |
| Q6-6 | Notification system | `[FE]` | 5 | 8 | Alert badges for important insights across departments |
| Q6-7 | Error handling workflows | `[PY]` | 5 | 8 | Error handler agent for each worker bee |
| Q6-8 | Responsive polish | `[FE]` | 5 | 8 | Mobile-friendly, loading states, error states, empty states |

**Subtotal**: 8 features, 41 points

---

## Summary

### By Central Intelligence / Feature Group

| Central Intelligence / Group | Features | Points | Sprint |
| ---------- | -------- | ------ | ------ |
| **Core** | | | |
| CI-CORE-00: Central Intelligence Orchestrator | 9 | 37 | 1a |
| CI-CORE-01: Call Transcriber | 7 | 21 | 2 |
| CI-CORE-ERR: Error Handler | 2 | 6 | 1b |
| **Directors** | | | |
| CI-MKT-DIR: Marketing Director | 6 | 19 | 2 |
| CI-SLS-DIR: Sales Director | 6 | 18 | 5 |
| CI-FUL-DIR: Fulfillment Director | 6 | 18 | 6 |
| **Operators** | | | |
| CI-OPS-ICP: ICP Generator | 5 | 15 | 2-3 |
| CI-OPS-OFFER: Offer Generator | 4 | 12 | 4 |
| Stats Updater Operators | 5 | 11 | 3-4 |
| **Sales Specialists** | | | |
| CI-SAL-01: Appointment Setting Bot | 9 | 34 | 5 |
| CI-SAL-02: Leads Database Worker | 13 | 52 | 5 |
| CI-SAL-03: Sales Call Analyzer | 10 | 32 | 5 |
| **Fulfillment Specialists** | | | |
| CI-FUL-01: Members Database Worker | 9 | 28 | 6 |
| CI-FUL-02: Coaching Call Analyzer | 9 | 30 | 6 |
| CI-FUL-03: Accountability Call Analyzer | 7 | 24 | 6 |
| CI-FUL-04: Tech SOS Tracker | 6 | 17 | 6 |
| **Marketing Specialists** | | | |
| CI-MKT-01: Social Media Worker | 8 | 29 | 3 |
| CI-MKT-02: Email Worker | 7 | 22 | 3 |
| CI-MKT-03: Funnels Worker | 6 | 19 | 3 |
| CI-MKT-04: Ads Worker | 7 | 22 | 4 |
| CI-MKT-05: DM Specialist | 7 | 22 | 4 |
| CI-MKT-06: Offer Creation Specialist | 7 | 24 | 4 |
| **Cross-Cutting** | | | |
| Data Migration Worker | 4 | 13 | 7 |
| Central Intelligence Intelligence | 8 | 41 | 8 |
| Authentication & Security | 7 | 20 | 1b, 8 |
| Error Handling & UX Infrastructure | 7 | 18 | 1b, 2, 6 |
| Edge Cases & Data Integrity | 13 | 33 | 2-7 |
| **Total** | **194** | **635** | |

### By Owner

| Owner | Features | Points |
| ----- | -------- | ------ |
| `[PY]` Python/Backend Developer | 117 | 281 |
| `[FE]` Frontend Developer | 54 | 261 |
| `[AI]` AI/Integration Specialist | 23 | 93 |
| **Total** | **194** | **635** |

### By Department

| Department | Workers / Groups | Features | Points |
| ---------- | ----------- | -------- | ------ |
| Core | 3 (Central Intelligence + Transcriber + Error Handler) | 18 | 64 |
| Directors | 3 (Marketing + Sales + Fulfillment Directors) | 18 | 55 |
| Operators | 3 (ICP Generator + Offer Generator + Stats Updaters) | 14 | 38 |
| Sales | 3 (Appointments + Leads + Sales Calls) | 32 | 118 |
| Fulfillment | 4 (Members + Coaching + Accountability + Tech SOS) | 31 | 99 |
| Marketing | 6 (Social + Email + Funnels + Ads + DM + Offers) | 42 | 138 |
| Cross-Cutting | 5 (Migration + Intelligence + Auth + Error + Edge Cases) | 39 | 125 |
| **Total** | **27** | **194** | **635** |

---

# ENHANCED SECTIONS

## Feature Priority Matrix

**Scoring Method**: Each feature scored on three dimensions, then multiplied for priority ranking.

| Feature ID | Feature Name | Business Impact (1-5) | Implementation Risk (1-5) | Dependency Count | Priority Score | Rank | Critical? |
| --- | --- | --- | --- | --- | --- | --- | --- |
| C00-1 | Central Intelligence agent class | 5 | 1 | 0 | 25 | 1 | P0 |
| C00-7 | Supabase tables setup | 5 | 1 | 0 | 25 | 1 | P0 |
| C00-6 | Agent class templates | 5 | 2 | 1 | 50 | 2 | P0 |
| C00-8 | App shell & navigation | 5 | 2 | 1 | 50 | 2 | P0 |
| SEC-01 | NextAuth.js setup | 5 | 2 | 2 | 100 | 3 | P0 |
| SEC-04 | FastAPI auth endpoints | 5 | 2 | 2 | 100 | 3 | P0 |
| SEC-05 | HMAC request signing | 5 | 3 | 2 | 150 | 4 | P0 |
| T01-2 | Audio extraction & Whisper | 4 | 3 | 3 | 108 | 5 | P0 |
| DIR-M1 | Marketing Director agent | 4 | 2 | 5 | 80 | 6 | P1 |
| S02-1 | Leads Worker agent | 5 | 3 | 4 | 180 | 7 | P1 |
| S02-12 | Leads CRUD operations | 4 | 3 | 5 | 180 | 7 | P1 |
| OPS-I2 | ICP generation prompt | 4 | 3 | 6 | 144 | 8 | P1 |
| M01-3 | Script generation prompt | 3 | 3 | 8 | 72 | 9 | P1 |
| S01-2 | Conversation analysis prompt | 4 | 3 | 7 | 144 | 8 | P1 |
| F02-2 | Wins extraction prompt | 4 | 3 | 7 | 144 | 8 | P1 |
| M06-2 | Offer optimization prompt | 4 | 3 | 8 | 144 | 8 | P1 |
| DIR-S1 | Sales Director agent | 4 | 2 | 9 | 72 | 9 | P1 |
| DIR-F1 | Fulfillment Director agent | 4 | 2 | 10 | 80 | 6 | P1 |
| Q6-4 | Executive dashboard | 5 | 3 | 25 | 375 | 10 | P2 |
| M01-7 | Script generator UI | 3 | 2 | 4 | 24 | 11 | P2 |
| M02-7 | Email drafting tool | 3 | 2 | 4 | 24 | 11 | P2 |
| S02-10 | Leads data table | 4 | 2 | 6 | 48 | 12 | P2 |
| EC-03 | Soft delete | 3 | 2 | 3 | 18 | 13 | P2 |
| EC-02 | Circuit breaker | 3 | 4 | 4 | 48 | 12 | P2 |
| M03-2 | Funnel analysis prompt | 3 | 2 | 5 | 30 | 14 | P2 |
| M04-2 | Ad analysis prompt | 2 | 2 | 5 | 20 | 15 | P2 |

**Legend**:
- **P0**: Critical path — must complete before system is usable
- **P1**: High priority — enable core workflows, required by P0
- **P2**: Medium priority — enhance workflows, can parallelize
- **P3**: Low priority — nice-to-have features, can defer

**Dependency Rules**:
- Features with 0 dependencies are parallelizable (start immediately)
- Features with 1-3 dependencies can start when prerequisites completed
- Features with 4+ dependencies must wait for sprint sequence or run in parallel sub-sprints

---

## Feature Dependencies Graph

### Critical Path Sequence

```
Sprint 1a Foundation (No dependencies):
  C00-7 (Supabase tables)
  C00-6 (Agent templates)
  C00-1 (Central Intelligence agent)
  C00-8 (App shell)
  C00-2 (QB system prompt)
  C00-3 (FastAPI endpoints)
  C00-5 (API client)
  C00-4 (Chat UI)
  C00-9 (Dashboard)

Sprint 1b Auth (Depends: Sprint 1a):
  SEC-01 → NextAuth.js setup
  SEC-02 → Login page
  SEC-03 → Auth middleware
  SEC-04 → FastAPI auth endpoints
  SEC-05 → HMAC signing
  ERR-01 → Error Handler
  ERR-02 → Error boundaries
  ERR-03 → Toast system
  ERR-04 → API client enhancements

Sprint 2 Marketing Director + Transcriber (Depends: Sprint 1b):
  T01-1 → Transcriber agent
    ├── T01-2 → Whisper integration
    ├── T01-3 → Transcript storage
    ├── T01-4 → Call routing
    ├── T01-5 → Endpoint
    └── T01-6 → Register operator

  DIR-M1 → Marketing Director agent
    ├── DIR-M2 → System prompt
    ├── DIR-M3 → Repository access
    ├── DIR-M4 → Summary endpoint
    └── DIR-M5 → Register with QB

  OPS-I1 → ICP Generator agent
    ├── OPS-I2 → Generation prompt
    ├── OPS-I3 → Table storage
    └── OPS-I4 → Endpoints

Sprint 3 Marketing Batch 1 (Depends: Sprint 2 + OPS-I1):
  M01-1, M01-2, M01-3 → Social Worker
  M02-1, M02-2, M02-3 → Email Worker
  M03-1, M03-2, M03-3 → Funnels Worker
  OPS-SE1, OPS-SS1, OPS-SF1 → Stats Updaters

Sprint 4 Marketing Batch 2 (Depends: Sprint 3):
  M04-1, M04-2, M04-3 → Ads Worker
  M05-1, M05-2, M05-3 → DM Specialist
  M06-1, M06-2, M06-3 → Offer Specialist
  OPS-O1, OPS-O2, OPS-O3 → Offer Generator
  OPS-SA1 → Ads Stats Updater

Sprint 5 Sales (Depends: Sprint 2 Transcriber + Sprint 4 Offers):
  DIR-S1 → Sales Director
  S01-1 to S01-9 → Appointments Bot (depends: T01 for potential call analysis)
  S02-1 to S02-13 → Leads Worker (highest dependency count)
  S03-1 to S03-10 → Sales Call Analyzer (depends: T01)

Sprint 6 Fulfillment (Depends: Sprint 2 Transcriber + Shared tables):
  DIR-F1 → Fulfillment Director
  F01-1 to F01-9 → Members Worker
  F02-1 to F02-9 → Coaching Analyzer (depends: T01)
  F03-1 to F03-7 → Accountability Analyzer (depends: T01)
  F04-1 to F04-6 → Tech SOS Tracker

Sprint 7 Data Migration (Depends: All Sprints 1-6):
  DM-1, DM-2, DM-3, DM-4 → Data Migration

Sprint 8 Intelligence + Polish (Depends: All workers registered):
  Q6-1 to Q6-8 → Central Intelligence Intelligence
  SEC-06, SEC-07 → Security hardening
  EC-02 → Circuit breaker
```

### External Dependencies

| External Dependency | Worker Affected | Blocker? | Mitigation |
| --- | --- | --- | --- |
| OpenAI API availability | CI-CORE-00, All Specialists | Yes | Fallback to Claude, alert system |
| OpenAI Whisper API | T01 (Transcriber) | Yes | Queue system, retry logic |
| Airtable API | All Workers reading/writing | Yes | Circuit breaker, cache layer |
| GoHighLevel API | S01 (Appointments) | Yes | Fallback to manual sync |
| Google Sheets API | M02 (Email), various | No | Skip if unavailable, serve cached data |
| Supabase platform stability | All | Critical | Backup + recovery procedures |

### Circular Dependencies

**None identified** — Dependency graph is acyclic. All workers can be built in the specified sprint order without circular blocking.

---

## Acceptance Criteria Summary

### Core Feature Group

**"Central Intelligence + Directors + Operators + Authentication working end-to-end"**

Acceptance Criteria:
1. User can log in with email/password (SEC-01 + SEC-04 completed)
2. User can see department summary cards on landing page (C00-9)
3. User can send message to Central Intelligence and receive response within 5 seconds (C00-1, C00-2, C00-3, C00-4)
4. Central Intelligence can query Marketing Director and receive response (DIR-M1 + DIR-M2 completed)
5. All 16 Supabase tables created and accessible (C00-7)
6. HMAC signatures validate on all requests (SEC-05)
7. Failed requests write to error log (ERR-01)
8. Health check endpoint returns 200 with worker statuses (ERR-05)

**Definition of Done**: Sprint 1a + 1b complete, system accessible, basic workflows operational

---

### Marketing Feature Group

**"All 6 Marketing Specialists operational + Director coordination"**

Acceptance Criteria:
1. Marketing Director agent receives queries and coordinates 6 specialists (DIR-M1)
2. Email Specialist generates email drafts informed by content ideas (M02-3, M02-7)
3. Social Specialist generates scripts using pain points + wins (M01-3, M01-7)
4. Funnels Specialist identifies bottlenecks (M03-2)
5. Ads Specialist generates ad copy (M04-3)
6. DM Specialist generates conversation templates (M05-3)
7. Offer Specialist creates offers from ICP + pain points (M06-2, M06-3)
8. ICP Generator produces structured client profiles (OPS-I2)
9. All specialists read from shared intelligence pool (DIR-M3)
10. Stats Updaters pull live metrics (OPS-SE1, OPS-SS1, OPS-SF1, OPS-SA1)
11. Marketing dashboard displays all KPIs (DIR-M6 + specialist dashboards)
12. Central Intelligence can request "Give me email strategies" and Director routes to Email Specialist

**Definition of Done**: Sprints 2-4 complete, all 6 specialists registered with Director, cross-domain data flowing

---

### Sales Feature Group

**"Sales pipeline visible + leads tracked + calls analyzed"**

Acceptance Criteria:
1. Leads Worker pulls all lead records with source, status, engagement (S02-1, S02-2)
2. Leads can be created, updated, deleted via UI (S02-12, S02-13)
3. Leads dashboard shows KPIs: total leads, conversion rate, funnel (S02-6 to S02-11)
4. Appointments Bot analyzes GHL conversations (S01-1, S01-4)
5. Appointment scripts improved based on pattern analysis (S01-2, S01-3, S01-9)
6. Sales Call Analyzer extracts pain points from transcripts (S03-2)
7. Content ideas generated from sales calls (S03-3)
8. Lead-to-member conversion triggered when status = "sale" (EC-12)
9. Sales Director coordinates all 3 specialists (DIR-S1)
10. Central Intelligence can query "How many sales this month?" and receive aggregation

**Definition of Done**: Sprint 5 complete (both 5a + 5b), sales dashboards populated, lead funnel visible

---

### Fulfillment Feature Group

**"Members tracked + coaching insights + accountability progress"**

Acceptance Criteria:
1. Members database populated with all records (F01-1, F01-2)
2. Members can be created/updated/viewed (F01-5, F01-6, F01-8, F01-9)
3. Coaching Call Analyzer extracts wins + pain points (F02-2, F02-3)
4. Content ideas generated from coaching calls (F02-4, F02-9)
5. Accountability Analyzer tracks goal progress (F03-2, F03-3)
6. Accountability timeline shows goal evolution (F03-6)
7. Tech SOS issues categorized + pattern analysis (F04-2)
8. Members see their progress on dashboard (F01-7)
9. Fulfillment Director coordinates all 4 specialists (DIR-F1)
10. Central Intelligence can query "Which members are struggling?" and Director provides insights

**Definition of Done**: Sprint 6 complete (both 6a + 6b), member pages operational, goal tracking active

---

### Cross-Cutting Feature Group (Security, Error Handling, Data Integrity)

**"System is secure, recoverable, and handles failures gracefully"**

Acceptance Criteria:
1. HMAC signatures prevent unauthorized requests (SEC-05)
2. Account lockout after 5 failed login attempts (SEC-04)
3. Rate limiting enforced per endpoint (Rate limiting in monitoring section)
4. All errors logged to bee_error_log (ERR-01)
5. Admin error dashboard shows errors by worker (ERR-06)
6. Error boundaries prevent app crashes (ERR-02)
7. Toast notifications display on API errors (ERR-03)
8. Soft delete preserves data (EC-03)
9. Duplicate transcripts prevented via SHA-256 hash (EC-07)
10. Stale data indicators show refresh status (EC-04)
11. Optimistic locking prevents concurrent edit conflicts (EC-01)
12. Circuit breaker stops cascading failures (EC-02)
13. Daily backups of Supabase + workflows (Backup strategy in disaster recovery)
14. Rollback procedures documented and tested (Rollback procedures in disaster recovery)

**Definition of Done**: Sprint 1b complete, ongoing through all sprints, security + error handling infrastructure in place

---

## Mapping to P0/P1/P2 from Critical Fixes

### P0 Critical Fixes (Must have for MVP)

| Fix ID | Description | Responsible Feature(s) |
| --- | --- | --- |
| P0-1 | System cannot crash on unhandled exceptions | ERR-02 (Error boundaries) |
| P0-2 | Unauthorized users cannot access data | SEC-01, SEC-03, SEC-05 |
| P0-3 | Data is never lost due to soft deletes | EC-03 (Soft delete) |
| P0-4 | Duplicate transcripts detected + prevented | EC-07 (Dedup) |
| P0-5 | Central Intelligence can respond to user queries | C00-1, C00-2, C00-3, C00-4 |
| P0-6 | Marketing Director coordinates specialists | DIR-M1, DIR-M2 |
| P0-7 | Call data flows through shared intelligence | OPS-I1, OPS-I2, Shared tables |

**Impact**: All P0 features must be completed before production launch

### P1 High Priority (Essential for revenue + operations)

| Fix ID | Description | Responsible Feature(s) |
| --- | --- | --- |
| P1-1 | Sales pipeline is visible with KPIs | S02-1 to S02-11 |
| P1-2 | Leads can be CRUD'd via UI | S02-12, S02-13 |
| P1-3 | Members tracked + goals monitored | F01-1 to F01-7 |
| P1-4 | Marketing can generate content | M01-3, M02-3, M03-2, M04-3, M05-3, M06-2 |
| P1-5 | Transcribed calls analyzed for insights | T01-1 to T01-6 + S03-1 to S03-3 + F02-1 to F02-4 |
| P1-6 | ICP + Offers auto-generated | OPS-I1 to OPS-I4, OPS-O1 to OPS-O4 |

**Impact**: P1 features required for team to use platform operationally

### P2 Medium Priority (Nice-to-have, can defer)

| Fix ID | Description | Responsible Feature(s) |
| --- | --- | --- |
| P2-1 | Executive dashboard with cross-dept KPIs | Q6-4 |
| P2-2 | Weekly digest emailed to team | Q6-2 |
| P2-3 | Admin error monitoring dashboard | ERR-06 |
| P2-4 | Data import from legacy systems | DM-1 to DM-4 |
| P2-5 | Mobile responsive design | Q6-8 |

**Impact**: P2 features enhance experience, can be deferred to post-launch

---

## Feature Interdependencies Table

| Feature | Blocks | Blocked By | Can Run in Parallel With |
| --- | --- | --- | --- |
| C00-7 (Supabase tables) | All features | None | C00-1, C00-6, C00-8 |
| C00-1 (QB agent) | C00-2, C00-3, C00-4 | C00-7, C00-6 | C00-8, C00-9 |
| SEC-04 (Auth endpoints) | All auth features | C00-7 | M01-1, M02-1, ... |
| T01-2 (Whisper) | S03-1, F02-1, F03-1 | SEC-04 | Marketing specialists |
| DIR-M1 (MKT Dir) | M01-5, M02-5, ... | T01-6, SEC-04 | Sales/Fulfillment work |
| S02-1 (Leads) | S02-2 to S02-13 | T01-6, SEC-04 | M01-1, M02-1, ... |
| OPS-I1 (ICP) | M06-2, M05-3, S01-2 | DIR-M1, pain_points table | Email/Social workers |
| OPS-O1 (Offer Gen) | M06-2, OPS-O4 | OPS-I1 | Ads/DM workers |
