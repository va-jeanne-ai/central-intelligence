# Central Intelligence Enhanced Technical Documentation - Index

**Navigation Guide for Enhanced Technical Documents**

---

## Quick Links

### By Document

| Document | Size | Focus | Best For |
|---|---|---|---|
| [api-contract-enhanced.md](./api-contract-enhanced.md) | 13.2K words | API contract, versioning, SDKs, testing | API developers, frontend teams |
| [data-schema-enhanced.md](./data-schema-enhanced.md) | 12.8K words | Database design, migration, performance | Backend developers, DevOps, DBAs |
| [critical-fixes-enhanced.md](./critical-fixes-enhanced.md) | 15.4K words | Implementation tracking, testing, planning | Engineering managers, developers, QA |
| [north-star-data-intelligence.md](./north-star-data-intelligence.md) | — | **NEW DIRECTION** — data-analysis + statistical recommendation engine (the current goal) | Everyone — read first for "what's next" |
| [status-rebaseline.md](./status-rebaseline.md) | — | Current build state vs. 8-sprint plan, drift, gaps (as of 2026-06-29) | Anyone needing the feature-completeness picture |
| [README.md](./README.md) | 3.2K words | Overview, usage guide, relationships | Everyone (start here!) |

---

## By Role

### Product Managers & Engineering Leadership

**Start Here**: [README.md - Section: How to Use](./README.md#how-to-use-these-documents)

**Then Read**:

1. critical-fixes-enhanced.md - [Section 2: Implementation Status Tracker](./critical-fixes-enhanced.md#2-implementation-status-tracker)
2. critical-fixes-enhanced.md - [Section 5: Fix Dependency Map](./critical-fixes-enhanced.md#5-fix-dependency-map)

**Deliverables to Expect**:
- Sprint assignments (4-6 week timeline)
- Story point estimates (100 total)
- Dependency graph for task sequencing
- Resource allocation recommendations

---

### API Developers & Frontend Teams

**Start Here**: [README.md - Section: For API Developers](./README.md#for-api-developers)

**Then Read**:

1. api-contract-enhanced.md - [Section 7: API Versioning Strategy](./api-contract-enhanced.md#7-api-versioning-strategy)
2. api-contract-enhanced.md - [Section 9: SDK / Client Library Spec](./api-contract-enhanced.md#9-sdk--client-library-spec)
3. api-contract-enhanced.md - [Section 10: API Testing Guide](./api-contract-enhanced.md#10-api-testing-guide)

**Deliverables**:
- TypeScript SDK interface and type definitions
- Testing procedures with mock server setup
- API versioning roadmap
- WebSocket real-time events specification

---

### Backend Developers

**Start Here**: [README.md - Section: For Backend/Infrastructure Team](./README.md#for-backendinfrastructure-team)

**Then Read** (in order):

1. data-schema-enhanced.md - [Section 6: Data Migration Playbook](./data-schema-enhanced.md#6-data-migration-playbook)
2. data-schema-enhanced.md - [Section 7: Data Integrity Rules](./data-schema-enhanced.md#7-data-integrity-rules)
3. critical-fixes-enhanced.md - [Section 3: Testing Requirements Per Fix](./critical-fixes-enhanced.md#3-testing-requirements-per-fix)

**Deliverables**:
- 5-phase migration strategy (blue-green deployment)
- PostgreSQL schema with indexes
- Referential integrity constraints
- Soft delete cascade triggers
- Test cases (20+ mandatory tests)

---

### DevOps / Database Administrators

**Start Here**: [data-schema-enhanced.md - Section 6: Data Migration Playbook](./data-schema-enhanced.md#6-data-migration-playbook)

**Then Read**:

1. data-schema-enhanced.md - [Section 8: Performance Optimization](./data-schema-enhanced.md#8-performance-optimization)
2. data-schema-enhanced.md - [Section 9: Backup & Recovery](./data-schema-enhanced.md#9-backup--recovery)
3. critical-fixes-enhanced.md - [Section 4: Post-Fix Verification Protocol](./critical-fixes-enhanced.md#4-post-fix-verification-protocol)

**Deliverables**:
- Migration checklist (15+ items)
- Indexing strategy for 3 major tables
- Caching configuration (TTL, invalidation)
- Backup schedule and point-in-time recovery
- Monitoring metrics (30+ Prometheus metrics)

---

### QA / Testing Teams

**Start Here**: [critical-fixes-enhanced.md - Section 3: Testing Requirements Per Fix](./critical-fixes-enhanced.md#3-testing-requirements-per-fix)

**Then Read**:

1. critical-fixes-enhanced.md - [Section 4: Post-Fix Verification Protocol](./critical-fixes-enhanced.md#4-post-fix-verification-protocol)
2. api-contract-enhanced.md - [Section 10: API Testing Guide](./api-contract-enhanced.md#10-api-testing-guide)
3. critical-fixes-enhanced.md - [Section 2: Implementation Status Tracker](./critical-fixes-enhanced.md#2-implementation-status-tracker) (for tracking)

**Deliverables**:
- Test case matrices (50+ test cases across 20 fixes)
- Verification procedures for P0 fixes
- Mock server setup for integration tests
- Regression testing requirements
- Monitoring alerts to verify (30+ metrics)

---

### Full Stack / Generalist Developers

**Start Here**: [README.md](./README.md) (read all of it)

**Then Deep Dive**:

1. Read [api-contract-enhanced.md](./api-contract-enhanced.md) completely (API contract + SDK + testing)
2. Read [data-schema-enhanced.md](./data-schema-enhanced.md) completely (database design + migration + performance)
3. Read [critical-fixes-enhanced.md](./critical-fixes-enhanced.md) completely (implementation plan + testing)

**Result**:
- Complete understanding of entire system architecture
- Ready to contribute across all layers
- Can handle full-stack features from API design through database

---

## By Topic

### API & Integration

| Topic | Document | Section |
|---|---|---|
| API contract baseline | api-contract-enhanced.md | Sections 1-5 |
| Central Intelligence endpoints | api-contract-enhanced.md | Section 6 |
| API versioning strategy | api-contract-enhanced.md | Section 7 |
| Real-time events (future) | api-contract-enhanced.md | Section 8 |
| TypeScript SDK spec | api-contract-enhanced.md | Section 9 |
| API testing procedures | api-contract-enhanced.md | Section 10 |

### Database & Data

| Topic | Document | Section |
|---|---|---|
| Database design | data-schema-enhanced.md | Sections 1-4 |
| Central Intelligence schema (9 tables) | data-schema-enhanced.md | Section 5 |
| Migration strategy | data-schema-enhanced.md | Section 6 |
| Data integrity rules | data-schema-enhanced.md | Section 7 |
| Performance optimization | data-schema-enhanced.md | Section 8 |
| Backup & recovery | data-schema-enhanced.md | Section 9 |

### Implementation & Planning

| Topic | Document | Section |
|---|---|---|
| Critical fixes list | critical-fixes-enhanced.md | Section 1 |
| Status tracking | critical-fixes-enhanced.md | Section 2 |
| Test requirements | critical-fixes-enhanced.md | Section 3 |
| Verification procedures | critical-fixes-enhanced.md | Section 4 |
| Sprint planning | critical-fixes-enhanced.md | Section 5 |
| Authentication system | critical-fixes-enhanced.md | Section 6 |
| Error handling | critical-fixes-enhanced.md | Section 7 |
| Edge case handlers | critical-fixes-enhanced.md | Section 8 |

### Operations & DevOps

| Topic | Document | Section |
|---|---|---|
| Backup schedule | data-schema-enhanced.md | Section 9 |
| Point-in-time recovery | data-schema-enhanced.md | Section 9 |
| Monitoring & metrics | critical-fixes-enhanced.md | Section 4 |
| Verification protocol | critical-fixes-enhanced.md | Section 4 |

---

## Key Sections by Importance

### Must Read (Critical Path)

1. **critical-fixes-enhanced.md - Section 5: Fix Dependency Map**
   - Why: Shows what blocks what, sprint sequence
   - Who: Everyone involved in development
   - Time: 30 minutes

2. **data-schema-enhanced.md - Section 6: Data Migration Playbook**
   - Why: Safe migration path, zero downtime approach
   - Who: Backend/DevOps planning migration
   - Time: 1 hour

3. **critical-fixes-enhanced.md - Section 2: Implementation Status Tracker**
   - Why: Current status and assignments
   - Who: Project managers, engineering leads
   - Time: 15 minutes

### Should Read (High Value)

4. **api-contract-enhanced.md - Section 9: SDK / Client Library Spec**
   - Why: Reduces frontend development time
   - Who: Frontend developers
   - Time: 45 minutes

5. **critical-fixes-enhanced.md - Section 3: Testing Requirements Per Fix**
   - Why: Clear test cases eliminate ambiguity
   - Who: QA engineers, developers
   - Time: 2 hours

6. **data-schema-enhanced.md - Section 8: Performance Optimization**
   - Why: Faster queries, better scalability
   - Who: Backend developers, DevOps
   - Time: 1 hour

### Nice to Have (Reference)

7. **api-contract-enhanced.md - Section 7: API Versioning Strategy**
   - Why: Long-term API evolution plan
   - Who: API architects, senior developers
   - Time: 30 minutes

8. **critical-fixes-enhanced.md - Section 4: Post-Fix Verification Protocol**
   - Why: Proves fixes work in production
   - Who: QA, operations, developers
   - Time: 1 hour (can skip initially)

---

## Common Questions & Where to Find Answers

| Question | Answer Location |
|---|---|
| What is Central Intelligence? | technical-plan-enhanced.md — Section 8 |
| What are CI's database tables? | data-schema-enhanced.md — Section 5 |
| How does CI connect to Central Intelligence? | technical-plan-enhanced.md — Section 8 (Integration Points) |
| What CI API endpoints exist? | api-contract-enhanced.md — Section 6 |
| How should we implement authentication? | critical-fixes-enhanced.md - Section 6 (Login/Auth System) |
| What is the sprint plan? | critical-fixes-enhanced.md - Section 5 (Fix Dependency Map) |
| How do we migrate data? | data-schema-enhanced.md - Section 6 (Migration Playbook) |
| What are the API versioning rules? | api-contract-enhanced.md - Section 7 (Versioning Strategy) |
| What needs to be tested for P0-SEC-01? | critical-fixes-enhanced.md - Section 3 (Testing Requirements) |
| How do we verify fixes in production? | critical-fixes-enhanced.md - Section 4 (Verification Protocol) |
| What indexes should we create? | data-schema-enhanced.md - Section 8 (Indexing Strategy) |
| How should we cache data? | data-schema-enhanced.md - Section 8 (Caching Strategy) |
| What is the TypeScript SDK interface? | api-contract-enhanced.md - Section 9 (SDK Spec) |
| How do we test the API? | api-contract-enhanced.md - Section 10 (Testing Guide) |
| Which fixes depend on others? | critical-fixes-enhanced.md - Section 5 (Dependency Map) |
| What monitoring should we add? | critical-fixes-enhanced.md - Section 4 (Monitoring Metrics) |

---

## Document Cross-References

### api-contract-enhanced.md References

- **To critical-fixes-enhanced.md**: Section 9 (SDK types match P0-SEC-02 HMAC signing)
- **To data-schema-enhanced.md**: Section 6 (API testing requires test data setup from migration guide)
- **To README.md**: For usage guide and role-based reading order

### data-schema-enhanced.md References

- **To critical-fixes-enhanced.md**: Section 5 (Sprint planning depends on migration completion)
- **To api-contract-enhanced.md**: Section 10 (Test data setup requires API endpoints)
- **To README.md**: For usage guide

### critical-fixes-enhanced.md References

- **To api-contract-enhanced.md**: Section 9 (SDK implements P0-SEC-02 HMAC)
- **To data-schema-enhanced.md**: Section 6 (P0-DATA-02 soft delete affects schema)
- **To README.md**: For role-based reading order

---

## How to Keep These Documents Updated

### Weekly Review

- Check critical-fixes-enhanced.md Section 2 (status tracker)
- Update fix statuses (Open → In Progress → Testing → Resolved)
- Update "Assigned To" if team changes

### Monthly Review

- Review all three documents for completeness
- Add new sections if scope changes
- Update section links if reorganizing

### Per Release

- Update version numbers in document headers
- Add new sections for new fixes or features
- Update sprint planning section with actual vs planned
- Archive old status trackers

### Ownership

- **api-contract-enhanced.md**: API/Backend Lead (reviews quarterly or per major version)
- **data-schema-enhanced.md**: Database/Infrastructure Lead (reviews monthly)
- **critical-fixes-enhanced.md**: Engineering Manager / Scrum Master (reviews weekly during active development)

---

## Getting Help

### Documentation Issues

- **Typos, clarity issues**: Create GitHub issue in `docs/` folder
- **Missing sections**: Post in #engineering Slack channel
- **Outdated information**: Tag document owner (@api-lead, @infra-lead, @eng-manager)

### Content Questions

- **API questions**: Post in #api-design Slack channel
- **Database questions**: Post in #infrastructure Slack channel
- **Implementation questions**: Post in #engineering Slack channel
- **Testing questions**: Post in #qa-testing Slack channel

### Suggestions

- **New sections to add**: Discuss with document owner
- **Better examples**: Submit pull request to update documents
- **Process improvements**: Raise in engineering standup

---

## Print-Friendly Sections

For printing or offline reading, here are recommended page ranges:

| Document | Section | Pages | Best For |
|---|---|---|---|
| critical-fixes-enhanced.md | Section 5 (Dependencies) | ~15 pages | Printing + pinning on wall |
| data-schema-enhanced.md | Section 6 (Migration) | ~12 pages | DBA reference guide |
| api-contract-enhanced.md | Section 9 (SDK Spec) | ~8 pages | Developer reference card |

---

## Version History

| Version | Date | Changes |
|---|---|---|
| 3.0.0 / 1.2.0 | 2026-03-29 | Complete architecture migration from n8n to Python agentic framework with Claude SDK |
| 2.2.0 / 1.1.0 | 2026-03-12 | Central Intelligence integration: 9-table Supabase schema, 13 CI endpoints, 6 CI skills, integration tasks across sprints 2, 3, 6 |
| 2.1.0 / 1.1.0 | 2026-03-12 | Initial enhanced version with 4 new sections per document, 44.6K words added |
| — | — | Future versions tracked in document headers |

---

## Document Statistics

**Total Content**: 48,500+ words
**Code Examples**: 55+ samples (SQL, JavaScript, TypeScript, Python, Bash)
**Tables**: 45+ reference tables
**Diagrams**: 6+ architecture diagrams
**Checklists**: 22+ actionable checklists
**Test Cases**: 55+ test case specifications
**Procedures**: 18+ step-by-step procedures
**Database Tables**: 26 total (PostgreSQL/Supabase core + CI tables)

**Effort to Read by Role**:
- Product Manager: 1.5 hours
- API Developer: 2 hours
- Backend Developer: 3 hours
- DevOps Engineer: 2.5 hours
- QA Engineer: 2.5 hours
- Full Stack Developer: 4-5 hours

---

*Index v1.1 — Central Intelligence Enhanced Technical Documentation*
*Last updated: 2026-03-29*
*Use this index to navigate quickly to the information you need!*
