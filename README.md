# Central Intelligence

**AI-powered workforce management platform — the "Central Intelligence" system for task coordination and agent workflows.**

---

## Purpose

Central Intelligence is a webapp for workforce management that coordinates tasks, agents, and workflows. It provides a dashboard-driven interface for managing marketing, sales, and fulfillment operations with AI-powered suggestions and analytics.

---

## Architecture

```text
frontend/ (Next.js)
      |
      v
  Supabase (Auth + Database)
      |
      v
  backend/ (API layer)
      |
      v
  External Services
```

---

## Prerequisites

### Required Credentials

| #   | Service   | Auth Type  | Used By          |
| --- | --------- | ---------- | ---------------- |
| 1   | Supabase  | API Key    | Database + Auth  |

### Environment Variables

| Variable          | Description             | Where Used       |
| ----------------- | ----------------------- | ---------------- |
| See `.env`        | Project API keys        | Backend/Frontend |
| See `frontend/.env.local` | Frontend config | Next.js app      |

---

## Setup Instructions

### 1. Frontend

1. `cd frontend && npm install`
2. Configure `.env.local` with Supabase credentials
3. `npm run dev`

### 2. Backend

1. `cd backend`
2. Follow backend setup instructions

### 3. Supabase

1. Configure `supabase/` migrations and schema

---

## File Structure

```text
projects/workerbee/
  ├── CLAUDE.md                       # Project instructions
  ├── CHANGELOG.md                    # Version history
  ├── README.md                       # This file
  ├── MANUAL-ACTIONS.md               # Manual action items
  ├── .env                            # API keys (not committed)
  ├── frontend/                       # Next.js webapp
  ├── backend/                        # API layer
  ├── supabase/                       # Database schema + migrations
  ├── New Documents/                  # PRD, tech docs, sprint plan
  ├── template/                       # Original client mockups (read-only)
  ├── tools/                          # Deterministic scripts
  ├── workflows/                      # Markdown SOPs
  ├── graphify-out/                   # Knowledge graph output
  ├── project-flow.html               # Visual project flow
  ├── technical-documentation.html    # Technical docs
  ├── workflow-documentation.html     # Workflow docs
  └── .tmp/                           # Disposable intermediates
```

---

## Related Documents

- [PRD](New Documents/PRD.md) -- Full product requirements
- [Technical Plan](New Documents/technical-plan-enhanced.md) -- Technical architecture
- [Sprint Plan](New Documents/sprint-plan-enhanced.md) -- Implementation schedule
- [API Contract](New Documents/api-contract-enhanced.md) -- API specifications
- [Data Schema](New Documents/data-schema-enhanced.md) -- Database schema
- [Architecture Diagram](New Documents/architecture-diagram.html) -- Visual architecture
- [Webapp Mockup](New Documents/webapp-mockup.html) -- UI design source of truth
