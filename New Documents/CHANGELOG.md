# Changelog - Central Intelligence (Central Intelligence) Business Automation System

All notable changes to this project are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [3.0.0] - 2026-03-29

### Added

- **Complete architecture migration from n8n to Python agentic framework**
  - Python FastAPI backend replacing n8n workflow engine
  - Claude SDK integration for AI-powered agent decision-making
  - Multi-tier agent architecture: Central Intelligence → Directors → Specialists → Operators
  - SQLAlchemy ORM with Repository pattern for database-agnostic code
  - REST API replacing n8n webhooks (`https://api.centralintelligence.dev/v1`)

- **Task Queue & Async Processing**
  - Celery + Redis for asynchronous task processing
  - Scheduled jobs for recurring operations
  - Improved scalability and concurrency handling

- **Enhanced Database Layer**
  - Supabase PostgreSQL as primary datastore
  - 26 total tables (15 core + 9 Central Intelligence + 2 shared)
  - Foreign key constraints and referential integrity enforcement
  - Soft delete cascade triggers for data consistency
  - 15+ database indexes for query optimization

- **API Versioning & SDK**
  - URL-based API versioning (`/v1/`, `/v2/`, etc.)
  - TypeScript SDK (@centralintelligence/client) for frontend integration
  - HMAC-SHA256 request signing for security
  - Comprehensive error handling and typed responses

- **Central Intelligence Subsystem** (fully integrated)
  - 9-table Supabase schema with deterministic ID strategy
  - Voice of Customer (VOC) data extraction from call transcripts
  - Content calendar and email writing intelligence
  - Competitive market signal tracking
  - REST API endpoints for CI operations

- **Documentation Updates**
  - api-contract-enhanced.md: API versioning, WebSocket roadmap, SDK spec, testing guide
  - data-schema-enhanced.md: Migration playbook, integrity rules, performance optimization, backup/recovery
  - critical-fixes-enhanced.md: Status tracker, test requirements, verification protocol, dependency mapping

### Changed

- **System Architecture**
  - From n8n workflow orchestration to Python agent coordination
  - From Airtable-first to PostgreSQL-first architecture
  - From webhook-based integration to REST API-based
  - From n8n Data Tables to Supabase PostgreSQL tables

- **Authentication & Security**
  - JWT tokens for session management (replacing NextAuth.js basic implementation)
  - HMAC-SHA256 request signing for API endpoints
  - Rate limiting at FastAPI middleware level
  - Request validation using Pydantic models

- **Database Strategy**
  - From n8n managed tables to self-hosted PostgreSQL/Supabase
  - Implemented soft delete pattern with cascade triggers
  - Added referential integrity constraints
  - Introduced database indexing strategy (15+ indexes across major tables)

- **Development Workflows**
  - From n8n visual workflow editor to Python code with git version control
  - From n8n templates to Python agent classes
  - From n8n logging to structured logging with Python logging module
  - From n8n scheduling to Celery beat scheduler

- **API Contract**
  - Updated all endpoint specifications for FastAPI framework
  - New versioning strategy (URL-based)
  - Expanded error codes to match REST standards
  - Added pagination cursors for large datasets

### Removed

- n8n workflow platform (all workflows migrated to Python agents)
- n8n Data Tables (migrated to PostgreSQL/Supabase)
- Airtable primary dependency (kept as backup/sync source only)
- NextAuth.js implementation (replaced with JWT)
- n8n webhook endpoints (replaced with FastAPI REST endpoints)
- Direct Airtable write operations in workflows (replaced with Supabase)

### Fixed

- All 20 critical fixes (P0/P1/P2) addressed in Python implementation
- Data consistency issues via soft delete cascade triggers
- Authentication gaps via JWT + HMAC dual-layer security
- Error handling via typed exceptions and structured logging

### Technical Details

**Base API URL**: `https://api.centralintelligence.dev/v1`

**Framework Stack**:
- Backend: Python 3.11+ with FastAPI
- Database: Supabase PostgreSQL with SQLAlchemy ORM
- Task Queue: Celery + Redis
- Frontend: Next.js (unchanged)
- Authentication: JWT + HMAC-SHA256
- AI Engine: Claude SDK (Anthropic API)

**Migration Path**:
1. Existing n8n workflows archived for reference
2. All workflows reimplemented as Python agent classes
3. Data migrated from Airtable to Supabase via 5-phase playbook
4. API endpoints tested for backward compatibility with Next.js frontend
5. All critical fixes implemented in new architecture

---

## [2.2.0] - 2026-03-12

### Added

- Central Intelligence (CI) subsystem documentation integrated across all technical documents
- CI 9-table Supabase schema (calls, insights, insight_tags, tag_dictionary, content_ideas, market_signals, offers, business_profile, monthly_preferences) in data-schema-enhanced.md
- CI table relationships, deterministic ID strategy, and 15 indexes in data-schema-enhanced.md
- CI Phase 2 future tables (email_stats, funnel_stats, ads_stats, funnels, traffic_sources, written_emails)
- CI skills architecture (6 skills) and data pipeline in technical-plan-enhanced.md
- 13 CI webhook endpoints with full request/response specs in api-contract-enhanced.md
- CI TypeScript SDK types (CICall, CIInsight, CIContentIdea, CIMarketSignal) in api-contract-enhanced.md
- CI integration tasks woven into Sprints 2, 3, and 6 in sprint-plan-enhanced.md
- Central Intelligence visual component in architecture-diagram.html
- CI capabilities (VOC pipeline, content calendar, email writing, market signals) in PRD.md

### Changed

- Updated system architecture from 2 to 3 parallel components (added CI alongside n8n Backend and Next.js Frontend)
- Updated data schema with dual-database architecture (n8n/Airtable + Supabase)
- Updated PRD product scope and phase planning to include CI capabilities
- Updated sprint plan point totals (635 → 684 story points)
- Updated architecture diagram with CI subsystem and data flow connections

### Fixed

- N/A

---

## [1.1.0] - 2026-03-12

### Added

- **PRD.md** — Comprehensive Product Requirements Document covering 15 sections, 15 user stories,
  and 635 story points documented across all departments and the core platform
- **architecture-diagram.html** — Interactive single-file HTML architecture diagram visualizing
  the full 3-tier Central Intelligence hierarchy (Central Intelligence, 3 Directors, 15 Specialists, 7 Operators),
  Data Layer (16 n8n tables, Airtable, Shared Intelligence Pool), and Web App Layer;
  clickable nodes with detail panels, dark theme, SVG-based, no external dependencies
- **README.md** — Project navigation hub with links to all documentation, setup overview,
  and quick-start guide for the full documentation suite
- **INDEX.md** — Quick reference guide mapping all 25 workers to their IDs, roles, and
  primary data tables; includes cross-reference tables for rapid lookup

### Changed

- **technical-plan-enhanced.md** — Added three new major sections:
  - Security Hardening (HMAC verification, credential rotation, rate limiting)
  - Monitoring & Observability (execution metrics, alerting thresholds, log retention)
  - Disaster Recovery (RTO/RPO targets, backup schedules, failover procedures)
- **feature-breakdown-enhanced.md** — Added three new sections:
  - Feature Priority Matrix (MoSCoW classification across all 194 features)
  - Dependencies Graph (inter-worker and cross-department dependencies)
  - Acceptance Criteria (definition of done for each feature category)
- **sprint-plan-enhanced.md** — Added four new sections:
  - Risk Mitigation register with probability/impact scoring
  - Contingency Plans for critical-path delays
  - Retrospective Template for end-of-sprint reviews
  - Quality Gates checklist required before sprint sign-off
- **api-contract-enhanced.md** — Added four new sections:
  - API Versioning strategy and deprecation policy
  - WebSocket specification for real-time dashboard updates
  - SDK/Client Library reference for Next.js integration
  - Testing Guide with Postman collection structure and test cases
- **data-schema-enhanced.md** — Added four new sections:
  - Migration Playbook for schema version upgrades
  - Integrity Rules and referential constraint definitions
  - Performance Optimization (indexing strategy, query patterns)
  - Backup & Recovery procedures for all 16 n8n Data Tables
- **critical-fixes-enhanced.md** — Added four new sections:
  - Status Tracker with current state of all 20 P0/P1/P2 fixes
  - Testing Requirements per fix category
  - Verification Protocol (how to confirm a fix is complete)
  - Dependency Map (which fixes block which features)

---

## [1.0.0] - 2026-03-05

### Added

- **technical-plan.md** — Technical architecture document defining the Sub-Workflow Tool pattern
  (Central Intelligence as orchestrator + Central Intelligence Workers as callable sub-workflows), n8n workflow structure,
  credential management strategy, and deployment topology
- **sprint-plan.md** — 8-sprint development roadmap totaling approximately 17 weeks and
  635 story points; covers infrastructure setup through production hardening
- **feature-breakdown.md** — 194 features catalogued across 27 worker bees (25 workers +
  2 directors + Central Intelligence), organized by department with effort estimates
- **api-contract.md** — 33+ webhook endpoint specifications covering all worker bee operations;
  includes full request/response schemas, authentication headers, and error codes
- **data-schema.md** — Complete data model for 16 n8n Data Tables and 6 Airtable bases;
  includes field definitions, data types, relationships, and sample records
- **critical-fixes.md** — 20 identified critical fixes categorized as P0 (5), P1 (9), and
  P2 (6); covers authentication gaps, data validation, error handling, and performance issues
- Two-layer authentication design: NextAuth.js for dashboard sessions + HMAC-SHA256 request
  signing for all n8n webhook endpoints
- Database-agnostic architecture: Airtable as default primary database with documented
  swap procedures for alternative datastores (Notion, Google Sheets, PostgreSQL)

---

## [0.1.0] - 2026-03-04

### Added

- Initial project planning session and scope definition
- Central Intelligence Worker registry: 25 workers across 3 departments (Marketing, Sales, Fulfillment)
  plus Core workers; full ID scheme established (CI-CORE-XX, CI-MKT-XX, CI-SLS-XX,
  CI-FUL-XX, CI-OPS-XX)
- **project-explanation.md** — Client requirements capture document recording the
  business context, goals, and constraints for the Central Intelligence automation platform
- 3-tier hierarchy defined: Central Intelligence (CI-CORE-00) → Directors (3) → Specialists (15+)
- Shared Intelligence Pool concept established: 7 cross-department n8n Data Tables
  (wins, pain_points, objections, content_ideas, icp_profiles, offers, goals)
