# Central Intelligence/Central Intelligence — Implementation Strategy & Platform Plan

**Version**: 3.0.0
**Date**: March 29, 2026
**Status**: Approved

## Architecture: 2 Components (Agentic Backend + Frontend)

```text
Component 1: Python Agentic Backend (VPS, Supabase-backed)
  ├── Agent Framework (Central Intelligence → Directors → Specialists → Operators)
  │   └── Custom Python agent classes inheriting from base Agent
  ├── FastAPI REST API (33+ endpoints)
  ├── Claude SDK Integration (Anthropic API for AI reasoning)
  ├── Task Queue (Celery + Redis for concurrent workflow execution)
  ├── Transcript Processing (core workflow)
  └── Market Signal Aggregation (core workflow)

Component 2: Next.js Frontend + API Layer (Vercel or self-hosted)
  ├── Next.js 14+ (React + Server Components)
  ├── Vercel AI SDK (streaming support for real-time agent responses)
  ├── Supabase Auth (JWT, RLS, user management)
  ├── Server Actions + Route Handlers (API middleware)
  └── Supabase Client (direct reads for dashboard data)

Shared Database: Supabase PostgreSQL
  ├── All persistent business data (ICP, offers, goals, wins, pain points, etc.)
  ├── Agent state and execution history
  ├── VOC intelligence tables
  ├── Auth/user tables (managed by Supabase Auth)
  └── Backend writes via SQLAlchemy ORM
```

## Platform Decisions

| Layer | Choice | Why |
|-------|--------|-----|
| **Backend** | Python + FastAPI + Claude SDK | Type-safe, async-native REST API; Claude SDK enables multi-turn reasoning; full version control of agent logic; no vendor lock-in |
| **Agent Framework** | Custom Python agent classes (Central Intelligence hierarchy) | Testable, version-controlled agent definitions; easy to iterate and debug; composable agent architecture matching business logic |
| **Task Queue** | Celery + Redis | Distributed task processing for concurrent agent workflows; proven horizontal scalability |
| **Database** | Supabase PostgreSQL + SQLAlchemy | SQLAlchemy provides database-agnostic repository pattern; RLS for multi-tenant data isolation; managed auth with JWT |
| **Frontend** | Next.js 14+ (React + RSC) | Best-in-class agentic ecosystem (Vercel AI SDK for streaming); React Server Components reduce client-side complexity; excellent TypeScript support |
| **API Streaming** | Vercel AI SDK + Next.js streaming | Real-time agent reasoning display; users see thought process as it happens |
| **Auth** | Supabase Auth | Free, managed, JWT + RLS + MFA. Supabase client libraries for seamless integration |
| **Frontend Hosting** | Vercel (free tier) | Zero-ops deployment; native Next.js optimization; streaming support built-in |
| **Monitoring** | Sentry + custom agent observability | Track errors across backend; instrument agent decisions and reasoning steps |
| **Chat UX (v1)** | Polling (2s interval) | Ship fast. Upgrade to Server-Sent Events (SSE) in v2 |

## Key Architectural Advantages

### 1. Testable Agent Logic

All agent behavior lives in version-controlled Python code, not a proprietary workflow editor:

```
agents/
  base.py                  # Base Agent class with standard interface
  central_intelligence.py            # Central Intelligence agent (orchestrator)
  directors/
    marketing_director.py  # Director specialization
    sales_director.py
  specialists/
    market_researcher.py   # Specialist implementations
    competitor_analyst.py
  operators/
    transcript_processor.py
    signal_aggregator.py
```

Each agent:

- Has unit tests (pytest)
- Runs against real database (test fixtures)
- Can be debugged locally
- Deploys to production with zero vendor friction

### 2. Claude SDK for Multi-Turn Reasoning

Unlike hardcoded workflows, agents use Claude for:

- Complex decision trees (instead of if/then branches)
- Multi-step reasoning with context
- Adaptive responses based on market signals
- Learning from past decisions

```python
# Example: Director agent making decisions
response = client.messages.create(
    model="claude-3-5-sonnet-20241022",
    max_tokens=2048,
    system=self.system_prompt(),
    messages=self.conversation_history
)
```

### 3. Next.js for Agentic UI

- **React Server Components**: Fetch agent state server-side, stream results to client
- **Streaming responses**: Display agent reasoning in real-time
- **Type safety**: Full TypeScript across frontend and backend
- **Vercel deployment**: Automatic optimization for streaming endpoints

## Backend Tech Stack Detail

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Framework | FastAPI | Async REST API, auto-OpenAPI docs, dependency injection |
| Agent Framework | Custom Python classes | Composable agent hierarchy with standard interface |
| LLM Integration | Anthropic Claude SDK | Multi-turn conversations, function calling, streaming |
| Task Queue | Celery + Redis | Background job processing for long-running workflows |
| Database ORM | SQLAlchemy 2.x | Database-agnostic queries; easily swap PostgreSQL for another DB |
| Database | Supabase PostgreSQL | Managed PostgreSQL with RLS, auth, real-time subscriptions |
| Validation | Pydantic v2 | Request/response validation with auto-documentation |
| Auth | Supabase JWT | Middleware validates JWT tokens |
| Monitoring | Sentry | Error tracking and performance monitoring |
| Observability | Custom telemetry | Agent decision logging and trace-ability |
| Testing | pytest + pytest-asyncio | Unit and integration tests for all agents |

## Frontend Tech Stack Detail

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Framework | Next.js 14+ (React 18) | Full-stack React with streaming and server components |
| Server Components | React RSC | Server-side data fetching reduces client bundle |
| HTTP Client | Fetch API + Server Actions | Type-safe API calls with automatic serialization |
| Streaming | Vercel AI SDK | Real-time agent response streaming |
| State Management | React Context + SWR | Lightweight client state with built-in caching |
| Styling | Tailwind CSS 4.x + shadcn/ui | Utility-first CSS with accessible components |
| Charts | Chart.js + react-chartjs-2 | Dashboard KPI visualizations |
| Auth | Supabase Auth + middleware | JWT verification in server routes and middleware |
| Form Handling | React Hook Form + Zod | Schema-based form validation |
| Database Client | Supabase client-js | Direct reads for dashboard data (read-only subscriptions) |

## Hosting & Cost Estimate

| Service | Tier | Monthly Cost |
|---------|------|-------------|
| Backend VPS (DigitalOcean/Hetzner/Linode) | 4GB RAM, Ubuntu 22.04 | $20-48 |
| Supabase | Free tier (500MB storage, unlimited auth) | $0 |
| Redis (Upstash or on VPS) | Free tier or shared VPS | $0-10 |
| Vercel (Next.js frontend) | Pro ($20) or free with limits | $0-20 |
| Claude API | ~500K tokens/day (streaming included) | $40-100 |
| Sentry | Free tier (5K events/month) | $0 |
| **Total** | | **$60-178/mo** |

*Note*: Cost scales with Claude usage. Optimizations (caching, batch processing) reduce API spend.

## What Changes from Current Plan

1. **Replace n8n**: All workflow logic moves to Python agents (version-controlled, testable, debuggable)
2. **Replace Nuxt 3**: Frontend now Next.js 14+ (best agentic ecosystem; Vercel AI SDK)
3. **Drop NextAuth.js → Supabase Auth**: Simplified auth, RLS for multi-tenancy
4. **Backend is now Python + FastAPI**: Not Node.js; enables seamless Claude SDK integration
5. **Agent reasoning is code, not JSON workflow**: Each agent is a Python class; decisions use Claude API, not hardcoded rules
6. **Task queue added**: Celery + Redis for concurrent agent execution (no longer tied to n8n execution model)
7. **Database is database-agnostic**: SQLAlchemy Repository pattern lets us swap PostgreSQL anytime
8. **Streaming built-in**: Next.js routes stream agent responses in real-time (no polling in v2+)
9. **Full version control**: Entire agent architecture is in Git; no proprietary workflow editor

## Why This Stack (Decision Rationale)

### Against n8n

- **Lock-in risk**: Proprietary workflow editor; moving to different platform costs months
- **Non-standard**: Workflows are JSON in a database; no Git history, no easy diffing
- **Testing nightmare**: Hard to unit test workflows; must spin up n8n to verify
- **Scaling cost**: n8n licensing adds up as workflows grow; each new workflow is a licensing consideration

### For Python + FastAPI

- **Testable**: Each agent is a Python class; write tests before deploying
- **Version control**: Entire logic in Git; track changes, revert easily, code review before merge
- **Claude SDK native**: Python has first-class Claude SDK; Anthropic maintains it actively
- **Performance**: FastAPI is faster than Node.js; async-native request handling
- **Ecosystem**: NumPy, pandas, scikit-learn; excellent data science tools if we expand later

### For Next.js (not Nuxt)

- **Vercel AI SDK**: Purpose-built for streaming agent responses; no equivalent in Vue ecosystem
- **Server Components**: Fetch agent state server-side; cleaner separation of concerns
- **React ecosystem**: More mature agentic libraries; OpenAI Assistants, LangChain, etc. all target React first
- **Deployment**: Vercel is native; automatic edge function optimization

### For Supabase

- **RLS**: Row-level security for multi-tenant isolation (users only see their data)
- **Managed**: No database ops burden
- **Auth included**: Eliminates separate auth service
- **Real-time**: Subscription support for live dashboards (phase 2)

## Scope Recommendation

Cut v1 to ~80-100 story points (Python agent complexity slightly higher than n8n, but offset by testability and fewer surprises):

- **Sprint 1**: Foundation (FastAPI scaffold, Supabase schema, SQLAlchemy models, Next.js app, auth integration)
- **Sprint 2**: Central Intelligence shell agent + Director base class + basic chat UI with polling
- **Sprint 3**: Marketing Director specialist agents (3-4 most impactful) + dashboard
- **Sprint 4**: Remaining specialists + error handling + observability setup
- **Sprint 5+**: Sales Director + Fulfillment agents (phase 2)

## Verification

After decisions are locked:

1. **Scaffold backend**: `pip install fastapi uvicorn sqlalchemy pydantic anthropic celery redis`
2. **Create agent base class**: `agents/base.py` with standard interface (think, act, observe)
3. **Verify Supabase integration**: Test SQLAlchemy connection, RLS policies, JWT middleware
4. **Scaffold frontend**: `npx create-next-app@latest centralintelligence --typescript --tailwind`
5. **Test streaming**: Verify Vercel AI SDK streams agent responses without blocking
6. **Load test**: Celery task queue processes 10+ concurrent agent workflows
7. **Deploy dev instance**: Docker container on VPS; test end-to-end flow

## Development Workflow

```text
Local development:
  1. Agent changes → pytest runs tests
  2. Pass tests → git push
  3. PR review → merged to main
  4. Main branch → Docker build + push to registry
  5. VPS pulls latest image → zero-downtime deploy

Frontend:
  1. Component changes → tested locally
  2. git push → Vercel auto-preview
  3. Approve PR → Vercel auto-deploys to production
```

## Migration Path (If Needed)

If we need to move away from Supabase later:

- SQLAlchemy makes swapping databases trivial (PostgreSQL → MySQL → SQLite for testing)
- Frontend uses Supabase client library; can be replaced with fetch API calls
- Claude API is vendor-agnostic; switching LLM provider is API swap + prompt tuning

This architecture trades vendor lock-in for operational simplicity and developer velocity.
