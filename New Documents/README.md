# Central Intelligence Technical Documentation - Enhanced Suite

**Version**: 3.0.0 / 1.2.0
**Date**: 2026-03-29
**Status**: Enhanced Reference Documentation

---

## Overview

This folder contains comprehensive enhanced technical documents for the Central Intelligence (Central Intelligence) business automation system. Each document has been significantly expanded with new sections and implementation guidance.

**System Components**:
- **Python Agent Backend**: Multi-tier agent orchestration powered by Claude SDK and FastAPI (Central Intelligence → Directors → Specialists → Operators)
- **Next.js Frontend**: Dashboard UI for system management and monitoring
- **Central Intelligence**: A marketing intelligence subsystem that transforms call transcripts (sales, coaching, discovery, accountability) into structured Voice of Customer (VOC) data. Powers content calendars, email writing, and marketing strategy. Runs on its own stack and feeds intelligence data into the Marketing department via REST API.
- **Task Queue**: Celery + Redis for async task processing and scheduling
- **Database**: Supabase (PostgreSQL) with SQLAlchemy ORM and Repository pattern for database-agnostic architecture

---

## Documents Included

### 1. api-contract-enhanced.md

**Original Sections Preserved**:
- Overview and architectural diagram
- Authentication (JWT + HMAC-SHA256 signing)
- Error format and standard error codes
- Pagination conventions and rate limiting
- Complete endpoint specifications for all Central Intelligence Workers
- Authentication, System, and Quick Reference endpoints

**New Sections Added** (Sections 6-10):

#### 6. Central Intelligence Endpoints (13 endpoints)
- **Transcript ingestion**: API endpoints for call recording upload and metadata
- **Insight extraction**: VOC data transformation from raw transcripts
- **Content ideas**: Generated content suggestions from customer insights
- **Market signals**: Competitive intelligence extraction from calls
- **Email intelligence**: Data feeding content calendar and email writing
- Full request/response specifications with examples
- REST API payload structures for transcript processing pipeline

#### 7. API Versioning Strategy
- **URL-based versioning** approach (`/v1/`, `/v2/`, etc.)
- **Breaking changes** definition and versioning triggers
- **Deprecation policy** with 3-stage timeline (Announcement → Support with Warnings → Removal)
- **Migration guides template** with example v1→v2 migration
- **Rollout timeline** and support windows

#### 8. WebSocket / Real-Time Events (Future)
- **Planned features** for v2 (Q4 2026) real-time layer
- **Real-time data subscriptions** architecture
- **Event types and payloads**:
  - Dashboard updates
  - Lead status changes
  - Central Intelligence chat streaming
  - Agent task completion
  - Error events
- **Connection lifecycle management** (init, heartbeat, disconnect, reconnection)
- **Exponential backoff retry strategy**

#### 9. SDK / Client Library Spec
- **TypeScript client library** (`@centralintelligence/client`) specification
- **Type definitions** for all endpoints with examples
- **Error handling patterns** with typed error classes
- **Request interceptor patterns**:
  - Automatic auth header injection
  - HMAC signature generation
  - Automatic retry logic with exponential backoff
  - Idempotency key support
- **Client configuration examples**

#### 10. API Testing Guide
- **Test data setup requirements**
- **cURL examples for key endpoints** (Central Intelligence, Leads, Auth, Transcriber, etc.)
- **Mock server configuration** using Mock Service Worker (MSW)
- **Integration test requirements** with database validation
- **Test case templates** for common scenarios

**Benefit**: Developers have clear guidance on versioning strategy, real-time integration roadmap, SDK usage patterns, and comprehensive testing approaches.

**Base API URL**: `https://api.centralintelligence.dev/v1`

---

### 2. data-schema-enhanced.md

**Original Sections Preserved**:
- Design philosophy (database-agnostic architecture)
- SQLAlchemy ORM models and Repository pattern
- Supabase PostgreSQL tables (26 tables across core system and Central Intelligence)
- Database migration guide (schema versioning strategies)
- Data relationships (5 major flows)
- Agent registry with role-based access

**New Sections Added** (Sections 5-9):

#### 5. Central Intelligence Supabase Schema (9 tables)
- **calls**: Raw call recordings with metadata (source, type, participant info)
- **insights**: Extracted VOC data from transcripts with confidence scores
- **insight_tags**: Categorical tags applied to insights (competitive, feature-request, etc.)
- **tag_dictionary**: Managed vocabulary for consistent tagging
- **content_ideas**: Generated content suggestions from customer insights
- **market_signals**: Competitive and market intelligence signals
- **offers**: Current and historical product offers mentioned in calls
- **business_profile**: Customer company profile data extracted from conversations
- **monthly_preferences**: Aggregated monthly preferences and trends
- Table relationships with deterministic ID strategy
- 15 database indexes for performance optimization
- Phase 2 future tables (email_stats, funnel_stats, ads_stats, funnels, traffic_sources, written_emails)

#### 6. Data Migration Playbook
Comprehensive 5-phase blue-green migration strategy:

**Phase 1: Preparation**
- Schema design in PostgreSQL/Supabase
- Schema compatibility validation
- Test data sync (10-record pilot)

**Phase 2: Initial Data Load**
- Full data export
- Data transformation pipeline
- Row count verification

**Phase 3: Dual-Write Mode**
- Agent workflows write to both systems simultaneously
- Sync monitoring dashboard
- Health metrics tracking

**Phase 4: Cutover**
- Final verification
- Switch read queries to PostgreSQL
- Rollback plan

**Phase 5: Cleanup**
- Disable legacy system access
- Archive read-only backups
- Remove migration code

**Includes**:
- SQL schema examples for PostgreSQL
- Python transformation code
- Complete checklist (15+ items)

#### 7. Data Integrity Rules
- **Referential integrity constraints** (Foreign key relationships with cascade rules)
- **Soft delete cascade rules** (PostgreSQL triggers with examples)
- **Duplicate detection strategies** per table:
  - Leads: email uniqueness
  - Call transcripts: URL hash + call_type
  - Content ideas: title + source
  - Pain points: text + category with frequency tracking
- **Data cleanup/archival policy** with automatic triggers
- **Retention schedule** by table (2-7 years depending on table)

#### 8. Performance Optimization

- **Indexing strategy per table**:
  - Leads table: 6 indexes (status, source, dates, email, fulltext)
  - Call transcripts: 5 indexes (member/lead linkage, URL hash, confidence)
  - Members table: 4 indexes (status, coach, active, enrollment)
  - Detailed SQL examples with WHERE clauses optimized
- **Query optimization patterns**:
  - Filter early, process late
  - Denormalization for read-heavy operations
  - Pagination for large result sets
  - Caching strategies
- **Caching strategy**:
  - What to cache with TTL values
  - Time-based cache invalidation
  - Event-based cache invalidation
  - Tag-based cache grouping
- **Pagination performance**:
  - Offset-based (simple but slow)
  - Cursor-based (fast for large datasets)
  - Implementation in FastAPI with code examples

#### 9. Backup & Recovery
- **Automated backup schedule**:
  - PostgreSQL: daily (14-day Supabase retention + manual backups)
  - Schedule via Celery tasks
- **Point-in-time recovery**:
  - Restore PostgreSQL to specific timestamp
  - Supabase dashboard walkthrough
- **Data export formats and frequency**:
  - CSV (for analysis)
  - JSON (for system integration)
  - Parquet (for data warehousing)
  - Frequency table: daily/weekly/monthly by dataset type
  - Retention by purpose (30 days to 7 years)

**Benefit**: Operations team has complete guidance on safe data architecture, integrity rules, performance optimization, and disaster recovery procedures, including Central Intelligence data lifecycle management.

---

### 3. critical-fixes-enhanced.md

**Original Sections Preserved**:
- Critical fix definitions (P0/P1/P2 priorities)
- All 20 fixes detailed:
  - 5 P0 (Ship Blockers)
  - 7 P1 (High Priority)
  - 8 P2 (Important)
- Authentication system (detailed architecture and code)
- Error handling layer (comprehensive strategy)
- 14 edge case handlers (EC-01 through EC-14)

**New Sections Added** (Sections 2-5):

#### 2. Implementation Status Tracker
Master tracking table with all 20 fixes:

**Columns**:
- Fix ID (P0-SEC-01, etc.)
- Priority
- Category (Security, Data, UX, Performance)
- Status (Open, In Progress, In Review, Testing, Resolved, Deferred, Blocked)
- Sprint assignment
- Assigned team member
- Story point effort estimate
- Due date
- Dependencies
- Notes

**Pre-populated Examples** (20 fixes total):
- P0-SEC-01: Open, Sprint 1, 10 pts, blocks everything
- P1-DATA-04: Open, Sprint 2, 5 pts, depends on P0-SEC-02
- etc.

**Benefit**: Project management teams can track progress, identify blockers, and manage sprint capacity.

---

#### 3. Testing Requirements Per Fix
Detailed test cases with expected outcomes for each fix:

**P0 Fixes** (Complete test matrices):
- **P0-SEC-01 (Auth)**: 8 test cases
  - Login success/failure
  - Account lockout after 5 attempts
  - Session expiration
  - Password change workflow
- **P0-SEC-02 (HMAC)**: 4 test cases
  - Valid signature acceptance
  - Invalid signature rejection
  - Missing signature behavior
- **P0-DATA-01 (DELETE)**: 4 test cases
  - Confirmation modal display
  - Cancel vs confirm flows
  - Bulk delete handling
- **P0-DATA-02 (Soft Delete)**: 4 test cases
  - Cascade to related records
  - Soft vs hard delete distinction
  - Audit trail creation
- **P0-DATA-03 (Errors)**: 4 test cases
  - Rate limit handling
  - Invalid data handling
  - Timeout behavior
  - Agent task failure handling

**P1 Fixes** (Key test scenarios):
- Duplicate form submissions
- Optimistic locking conflict resolution
- Audit log entry creation
- Request timeout configuration

**P2 Fixes** (Integration test scenarios):
- Pain point deduplication
- Content idea status transitions
- Member goals cleanup
- Lead-to-member conversion

**Benefit**: QA team has comprehensive test cases ready to execute for each fix.

---

#### 4. Post-Fix Verification Protocol
Step-by-step procedures to verify each fix works in production:

**P0 Fixes Verification**:
- Authentication: Login endpoint curl tests, token verification, protected endpoint tests
- HMAC: Request/response verification with signature validation
- DELETE: Browser console steps for modal interaction
- Soft Delete: SQL queries to verify cascade and audit logs
- Error Handling: Error log inspection and Slack alert verification

**Monitoring to Add**:
- **P0-SEC-01**: Failed login rates, account lockouts, session duration, anomaly detection
- **P0-SEC-02**: HMAC validation failures and verification duration
- **P0-DATA-02**: Soft delete counts, cascade success rates, orphaned records detection
- **P0-DATA-03**: Agent task errors by category, severity distribution, MTTR (mean time to resolution)

**Regression Testing**:
- Full integration test suite
- Agent endpoint tests
- Smoke tests for key flows
- Load testing (100 concurrent users)
- OWASP security testing

**Benefit**: Operations and QA teams can confidently verify fixes are working and maintain ongoing health.

---

#### 5. Fix Dependency Map
Complete visualization of fix interdependencies:

**Dependency Graph**:
```
P0-SEC-01 (Auth)
  ├─ [No dependencies - start immediately]
  └─ BLOCKS: P0-SEC-02, P1-SEC-03, others needing user identity

P0-SEC-02 (HMAC)
  ├─ Depends on: P0-SEC-01
  └─ BLOCKS: P1-DATA-04

P0-DATA-01 (DELETE)
  ├─ Depends on: P0-SEC-01
  └─ ENABLES: P0-DATA-02

[... 17 more fixes with clear dependency chains ...]
```

**Recommended Implementation Order**:

**Sprint 1** (21 pts target):
- P0-SEC-01 (10 pts) — CRITICAL PATH
- P0-DATA-03 (5 pts) — PARALLEL
- P0-SEC-02 (3 pts) — After P0-SEC-01
- P1-PERF-01 (3 pts) — PARALLEL

**Sprint 2** (31 pts target):
- P0-DATA-01 (5 pts)
- P0-DATA-02 (8 pts)
- P1-SEC-03 (4 pts)
- P1-DATA-04 (5 pts)
- P1-UX-01/02/03 (9 pts)

**Sprint 3** (19 pts target):
- P1-DATA-05 (6 pts)
- P2-DATA-06/07/08 (11 pts) — PARALLEL
- P2-DATA-09 (2 pts)

**Sprint 4** (13 pts target):
- P2-DATA-10 (8 pts)
- P2-PERF-02 (5 pts)

**Sprint 5+**: Deferred security items

**Parallel Implementation Opportunities**:
- Shows which fixes can run simultaneously without conflicts
- Enables efficient resource allocation across teams

**Benefit**: Engineering leadership can plan realistic sprint schedules and coordinate team efforts.

---

## Document Relationships

```
api-contract-enhanced.md
  ├─ Defines API contract and endpoints
  ├─ Specifies versioning strategy
  ├─ Describes WebSocket real-time layer (future)
  └─ Links to SDK testing guide

data-schema-enhanced.md
  ├─ Defines data structures
  ├─ Specifies schema migration process (5-phase playbook)
  ├─ Documents integrity rules
  ├─ Provides performance optimization guidance
  └─ Covers backup/recovery procedures

critical-fixes-enhanced.md
  ├─ Identifies required fixes
  ├─ Provides implementation tracking
  ├─ Specifies testing requirements
  ├─ Details post-fix verification
  ├─ Maps fix dependencies
  ├─ Recommends sprint planning
  └─ Links to authentication and error handling specs
      (which are referenced in api-contract-enhanced.md)
```

---

## How to Use These Documents

### For Product Managers & Leadership

1. **Read**: Section 5 of critical-fixes-enhanced.md (Fix Dependency Map)
2. **Review**: Sprint planning with 4-6 week timeline
3. **Track**: Implementation status in Section 2 (Master Tracker)

---

### For API Developers

1. **Start**: api-contract-enhanced.md → Sections 1-6 (existing API)
2. **Plan**: Sections 7-10 (versioning, WebSocket roadmap, SDK)
3. **Test**: Section 10 (API Testing Guide)

---

### For Backend/Infrastructure Team

1. **Start**: data-schema-enhanced.md → Sections 6-9
2. **Plan**: Section 6 (5-phase migration playbook)
3. **Secure**: Section 7 (Data integrity rules)
4. **Optimize**: Section 8 (Performance tuning)
5. **Protect**: Section 9 (Backup & recovery)

---

### For QA/Testing Team

1. **Prepare**: critical-fixes-enhanced.md → Section 3 (Test requirements)
2. **Execute**: Section 4 (Verification protocol)
3. **Monitor**: Monitor setup from Section 4

---

### For Full Stack Developers

1. **Overview**: Each document's Table of Contents
2. **Deep dive**: All sections of all three documents
3. **Implement**: Use critical-fixes-enhanced.md sprint planning

---

## Key Enhancements Summary

### api-contract-enhanced.md

| Enhancement | Value | Audience |
|---|---|---|
| API versioning strategy | Clear upgrade path for clients | API consumers, frontend teams |
| WebSocket spec (future) | Real-time integration roadmap | Frontend architects, QA |
| SDK client library | Developer productivity | Full-stack developers |
| Testing guide | Reduced QA prep time | QA engineers, contractors |

---

### data-schema-enhanced.md

| Enhancement | Value | Audience |
|---|---|---|
| 5-phase migration playbook | Safe, proven migration path | DBAs, DevOps, backend teams |
| Data integrity rules | Fewer data corruption bugs | Backend developers |
| Performance optimization | Faster queries, reduced costs | DevOps, database teams |
| Backup/recovery procedures | Disaster recovery confidence | Operations, DevOps |

---

### critical-fixes-enhanced.md

| Enhancement | Value | Audience |
|---|---|---|
| Status tracker | Clear progress visibility | Product managers, leadership |
| Test cases per fix | Faster QA, higher confidence | QA engineers, developers |
| Verification protocol | Proves fixes actually work | QA, operations |
| Dependency map | Realistic sprint planning | Engineering managers, scrum masters |
| Sprint recommendations | Resource allocation guidance | Technical leads, managers |

---

## Document Maintenance

### Update Frequency

- **api-contract-enhanced.md**: Update with each API version release (minor: quarterly, major: as needed)
- **data-schema-enhanced.md**: Update as schema changes (monthly review recommended)
- **critical-fixes-enhanced.md**: Update as fixes progress (daily/weekly during active development, monthly post-launch)

### Version Numbering

- Documents follow semantic versioning tied to Central Intelligence releases
- Current: **v3.0.0 / v1.2.0** (Python agentic backend + Central Intelligence integration)

### Ownership

- **api-contract-enhanced.md**: API/Backend Lead
- **data-schema-enhanced.md**: Database/Infrastructure Lead
- **critical-fixes-enhanced.md**: Engineering Manager / Scrum Master

---

## Related Documents in Main Project

These enhanced documents complement:
- `/Users/hans_ai/agentic-builder/projects/workerbee/New Documents/technical-plan-enhanced.md` (architecture)
- `/Users/hans_ai/agentic-builder/projects/workerbee/New Documents/PRD.md` (requirements)

---

## Questions & Support

For questions about these documents:

- **API Contract Questions**: Post in #api-design Slack channel
- **Data Schema Questions**: Post in #infrastructure Slack channel
- **Critical Fixes Questions**: Post in #engineering Slack channel
- **Documentation Issues**: Create GitHub issue in `docs/` folder

---

*Enhanced Central Intelligence Documentation Suite v3.0.0 / v1.2.0*
*Last updated: 2026-03-29*
*Location: `/Users/hans_ai/agentic-builder/projects/workerbee/New Documents/`*
