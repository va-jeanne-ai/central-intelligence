# Central Intelligence (Central Intelligence) Business Automation System
# Data Schema Reference - ENHANCED

**Version**: 3.0.0
**Date**: 2026-03-29
**Project**: Central Intelligence AI Automation System

---

## Table of Contents

1. [Design Philosophy](#1-design-philosophy)
2. [Architecture: Repository Pattern & SQLAlchemy](#2-architecture-repository-pattern--sqlalchemy)
3. [Unified Data Schema (Central Intelligence + CI)](#3-unified-data-schema-workerbe--ci)
4. [SQLAlchemy Model Definitions](#4-sqlalchemy-model-definitions)
5. [Repository Pattern Interface & Implementation](#5-repository-pattern-interface--implementation)
6. [Database Configuration & Supabase Setup](#6-database-configuration--supabase-setup)
7. [Alembic Migrations & Schema Management](#7-alembic-migrations--schema-management)
8. [Row Level Security (RLS) & Multi-Tenant Data](#8-row-level-security-rls--multi-tenant-data)
9. [Redis Caching Strategy](#9-redis-caching-strategy)
10. [Data Migration Playbook](#10-data-migration-playbook)
11. [Data Integrity Rules](#11-data-integrity-rules)
12. [Performance Optimization](#12-performance-optimization)
13. [Backup & Recovery](#13-backup--recovery)

---

## 1. Design Philosophy

### Database-Agnostic Architecture with Repository Pattern

The Central Intelligence system enforces strict separation of concerns through the **Repository Pattern**, ensuring no application layer (agents, services, or external consumers) directly executes database queries.

```
[Agent Classes / Services]
        |
        | Service method calls
        v
[Repository Interface]  <--- Defines all database operations
        |
        | Abstracted operations
        v
[SQLAlchemy Models]     <--- ORM layer abstracts SQL
        |
        | SQL + Parameterized queries
        v
[Database Adapter]      <--- Currently: Supabase PostgreSQL
                            Extensible: Raw PostgreSQL, MySQL, MongoDB, etc.
```

**Key Guarantees:**

1. **Swappable Storage**: Implementing a new database adapter requires only creating a new Repository concrete class. SQLAlchemy models and agent code remain unchanged.

2. **Consistent Contracts**: All database operations flow through the Repository interface, producing stable output contracts that agents depend on.

3. **Centralized Access Control**: Only Repository classes hold credentials and connection strings. Agents never touch database drivers directly.

4. **Async-First Design**: All database operations use async/await for non-blocking I/O, essential for agent scalability.

### Technology Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Primary Database** | Supabase (PostgreSQL) | Unified data store for Central Intelligence + CI |
| **ORM** | SQLAlchemy 2.0 (async) | Database abstraction, model validation |
| **Database Driver** | asyncpg | High-performance async PostgreSQL driver |
| **Migrations** | Alembic | Version-controlled schema changes |
| **Repository Layer** | Custom Python classes | Database-agnostic CRUD operations |
| **Auth & Access Control** | Supabase Auth + RLS | Row-level security, multi-tenant isolation |
| **Caching** | Redis | Hot data caching, session management |
| **Connection Pool** | SQLAlchemy connection pooling | Efficient resource management |

### Naming Conventions

| Entity | Convention | Example |
|--------|-----------|---------|
| SQLAlchemy table class | PascalCase | `class Lead(Base):` |
| Database table name | snake_case | `leads` |
| Repository class | `{Entity}Repository` | `LeadRepository` |
| Async method | verb prefix | `async def get_by_id()`, `async def create()` |
| Boolean column | `is_` or `has_` prefix | `is_active`, `has_coaching` |
| Timestamp column | `_at` suffix | `created_at`, `deleted_at`, `updated_at` |
| Foreign key column | `{table}_id` | `lead_id`, `member_id`, `coach_id` |

---

## 2. Architecture: Repository Pattern & SQLAlchemy

### Data Access Layer Architecture

```
┌─────────────────────────────────────────────────┐
│          Agent Classes / Services               │
│  (Pure business logic, no DB awareness)         │
└────────────────┬────────────────────────────────┘
                 │ calls methods
                 v
┌─────────────────────────────────────────────────┐
│      Repository Interface (Abstract Base)       │
│  RepositoryBase[T]                              │
│  - async def get(id: T_id) -> T                 │
│  - async def create(data: CreateSchema) -> T    │
│  - async def update(id, data: UpdateSchema)    │
│  - async def delete(id)                         │
│  - async def list(filters, limit, offset)      │
└────────────────┬────────────────────────────────┘
                 │ inherits
                 v
┌─────────────────────────────────────────────────┐
│    Concrete Repositories (Supabase impl)        │
│  - LeadRepository(RepositoryBase[Lead])         │
│  - MemberRepository(RepositoryBase[Member])    │
│  - CallRepository(RepositoryBase[Call])        │
│  etc.                                           │
└────────────────┬────────────────────────────────┘
                 │ uses
                 v
┌─────────────────────────────────────────────────┐
│        SQLAlchemy Models & Session              │
│  - Lead ORM model                               │
│  - Member ORM model                             │
│  - Pydantic schemas for validation              │
└────────────────┬────────────────────────────────┘
                 │ queries/writes
                 v
┌─────────────────────────────────────────────────┐
│    Database: Supabase PostgreSQL (asyncpg)     │
│    - Tables with constraints, indexes, RLS      │
│    - Automatic backups, point-in-time recovery │
└─────────────────────────────────────────────────┘
```

### Connection & Session Management

```python
# database.py
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool
import os

# Initialize async engine (Supabase connection)
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SECRET_KEY = os.getenv("SUPABASE_SECRET_KEY")
DATABASE_URL = f"postgresql+asyncpg://postgres.{SUPABASE_URL.split('/')[-1]}:{SUPABASE_SECRET_KEY}@db.{SUPABASE_URL.split('/')[-1]}/postgres"

engine = create_async_engine(
    DATABASE_URL,
    echo=False,  # Set to True for SQL logging
    future=True,
    pool_pre_ping=True,  # Verify connections before using
    pool_size=20,
    max_overflow=10,
    poolclass=NullPool,  # Supabase recommends NullPool for serverless
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    future=True
)

async def get_session() -> AsyncSession:
    """Dependency injection: provides session to repositories."""
    async with AsyncSessionLocal() as session:
        yield session
```

---

## 3. Unified Data Schema (Central Intelligence + CI)

The Central Intelligence system consolidates three separate data sources into a single PostgreSQL database:

- **Central Intelligence Operational Data** (formerly n8n Data Tables, 16 tables)
- **Central Intelligence Primary Data** (formerly Airtable, 7 tables)
- **Central Intelligence** (Supabase, 9 tables)

### Unified Table Map

| Table | Source | Purpose | Row Count (est) |
|-------|--------|---------|-----------------|
| **Operational** | — | — | — |
| leads | Central Intelligence | Sales pipeline prospects | 10K |
| members | Central Intelligence | Active cohort members | 500 |
| calls | Unified (Central Intelligence + CI) | Call transcripts & analysis | 50K |
| insights | CI | VOC signals extracted from calls | 100K |
| content_ideas | Unified (Central Intelligence + CI) | Generated content opportunities | 5K |
| goals | Central Intelligence | Member/lead goals | 2K |
| pain_points | Central Intelligence | Customer pain points | 10K |
| wins | Central Intelligence | Member wins/achievements | 5K |
| objections | Central Intelligence | Sales objections encountered | 3K |
| **Meta & Config** | — | — | — |
| users | Central Intelligence | System users & coaches | 50 |
| teams | Central Intelligence | Team/group associations | 10 |
| **Intelligence & Marketing** | — | — | — |
| insight_tags | CI | Tag assignments for insights | 50K |
| tag_dictionary | CI | Canonical tag vocabulary | 200 |
| market_signals | CI | Aggregated trend data | 2K |
| offers | CI/Central Intelligence | Products, services, promotions | 50 |
| business_profile | CI | Brand voice & business context | 1 |
| monthly_preferences | CI | Email calendar configuration | 12 |
| **Audit & Logging** | — | — | — |
| audit_log | Central Intelligence | Data change audit trail | 1M+ |
| error_log | Central Intelligence | Workflow errors & exceptions | 100K |
| sync_log | Central Intelligence | Migration/sync events | 50K |
| idempotency_keys | Central Intelligence | Deduplication for retried ops | 100K |

### High-Level Schema

```sql
-- Core operational tables
CREATE TABLE leads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE,
    phone VARCHAR(20),
    status VARCHAR(50),  -- new, contacted, appointment-set, qualified, sale, lost
    source VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMPTZ NULL,
    created_by UUID REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE members (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE,
    enrollment_date TIMESTAMPTZ,
    coach_id UUID REFERENCES users(id) ON DELETE SET NULL,
    status VARCHAR(50) DEFAULT 'active',  -- active, paused, graduated, churned
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMPTZ NULL
);

CREATE TABLE calls (
    id TEXT PRIMARY KEY,  -- Format: CALL_<TranscriptUID> or CALL_<YYYYMMDD_HHMMSS>
    date DATE,
    call_type VARCHAR(50),  -- Sales, Discovery, Coaching, Accountability, Support
    call_result VARCHAR(50),  -- Closed, No Decision, Lost, Qualified, N/A
    call_owner VARCHAR(255),
    member_id UUID REFERENCES members(id) ON DELETE CASCADE,
    lead_id UUID REFERENCES leads(id) ON DELETE CASCADE,
    transcript_source VARCHAR(50),  -- Cockatoo, Otter, Fireflies, Manual
    transcript_uid VARCHAR(255),
    transcript_quality VARCHAR(50),  -- Clean, Moderate, Messy
    transcript_link TEXT,
    processed_date DATE,
    call_duration_minutes INTEGER,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMPTZ NULL
);

CREATE TABLE insights (
    id TEXT PRIMARY KEY,  -- Format: INS_<CallID>_01
    call_id TEXT NOT NULL REFERENCES calls(id) ON DELETE CASCADE,
    speaker_name VARCHAR(255),
    insight_type VARCHAR(50),  -- Pain, Goal, Objection, False Belief, Win, Breakthrough, Product Issue, Feature Request
    signal_family VARCHAR(255),  -- Dynamically inferred
    signal TEXT,  -- Dynamically inferred
    signal_strength VARCHAR(50),  -- Strong, Moderate, Weak
    pain_layer VARCHAR(50),  -- Surface, Emotional, Existential (Pains only)
    raw_quote TEXT,
    what_they_say TEXT,
    the_real_problem TEXT,
    emotional_driver TEXT,
    core_fear_revealed TEXT,
    false_belief_revealed TEXT,
    structural_obstacle TEXT,
    identity_signal TEXT,
    buying_trigger TEXT,
    objection_created TEXT,
    marketing_translation TEXT,
    hook_angle_example TEXT,
    best_use_case VARCHAR(100),  -- Email, Webinar, VSL, Ads, Social
    quote_confidence VARCHAR(50),  -- High, Medium, Low
    frequency_score INTEGER DEFAULT 1,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE content_ideas (
    id TEXT PRIMARY KEY,  -- Format: CONT_<CallID>_01
    insight_id TEXT REFERENCES insights(id) ON DELETE SET NULL,
    call_id TEXT REFERENCES calls(id) ON DELETE SET NULL,
    source VARCHAR(100),  -- AI Extraction, Manual Entry, Brainstorm
    market_audience VARCHAR(255),
    content_format VARCHAR(100),  -- Email, Reel, YouTube, Webinar, Ad, VSL, Post
    content_angle TEXT,
    trigger_insight TEXT,
    raw_quote TEXT,
    content_premise TEXT,
    hook_opening_line TEXT,
    teaching_point TEXT,
    cta_idea TEXT,
    priority_level VARCHAR(50),  -- High, Medium, Low
    best_platform VARCHAR(100),  -- Email, LinkedIn, YouTube, etc.
    repurpose_opportunities TEXT,
    idea_score INTEGER CHECK (idea_score >= 0 AND idea_score <= 10),
    status VARCHAR(50) DEFAULT 'Idea',  -- Idea, Scheduled, Written, Sent, Archived
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMPTZ NULL
);

CREATE TABLE insight_tags (
    id SERIAL PRIMARY KEY,
    insight_id TEXT NOT NULL REFERENCES insights(id) ON DELETE CASCADE,
    tag VARCHAR(100) NOT NULL REFERENCES tag_dictionary(tag) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE tag_dictionary (
    tag VARCHAR(100) PRIMARY KEY,
    tag_type VARCHAR(50),  -- Theme, Pain, Goal, Objection, Identity, Other
    synonyms TEXT,  -- Comma-separated
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE market_signals (
    id SERIAL PRIMARY KEY,
    signal_family VARCHAR(255),
    signal TEXT,
    insight_type VARCHAR(50),
    total_mentions INTEGER DEFAULT 0,
    last_30_days INTEGER DEFAULT 0,
    last_7_days INTEGER DEFAULT 0,
    example_quote TEXT,
    example_call_id TEXT REFERENCES calls(id) ON DELETE SET NULL,
    best_marketing_angle TEXT,
    notes TEXT,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Support tables
CREATE TABLE goals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    member_id UUID REFERENCES members(id) ON DELETE CASCADE,
    lead_id UUID REFERENCES leads(id) ON DELETE CASCADE,
    goal_text TEXT NOT NULL,
    target_date DATE,
    status VARCHAR(50) DEFAULT 'active',
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMPTZ NULL
);

CREATE TABLE pain_points (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    member_id UUID REFERENCES members(id) ON DELETE CASCADE,
    lead_id UUID REFERENCES leads(id) ON DELETE CASCADE,
    text TEXT NOT NULL,
    category VARCHAR(100),
    frequency_count INTEGER DEFAULT 1,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMPTZ NULL
);

CREATE TABLE wins (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    member_id UUID REFERENCES members(id) ON DELETE CASCADE,
    win_text TEXT NOT NULL,
    win_date DATE,
    impact_area VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMPTZ NULL
);

CREATE TABLE objections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id UUID REFERENCES leads(id) ON DELETE CASCADE,
    objection_text TEXT NOT NULL,
    context VARCHAR(255),
    resolution_offered TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMPTZ NULL
);

-- Config tables
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255),
    role VARCHAR(50),  -- admin, coach, agent, viewer
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE teams (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Marketing config
CREATE TABLE offers (
    offer_id TEXT PRIMARY KEY,  -- OFFER_001, OFFER_MENTORSHIP_10K
    name VARCHAR(255) NOT NULL,
    offer_type VARCHAR(50),  -- Product, Service, Webinar, VSL, Course, Coaching
    description TEXT,
    price NUMERIC(10, 2),
    status VARCHAR(50) DEFAULT 'Active',  -- Active, Inactive, Coming Soon
    url TEXT,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE business_profile (
    id SERIAL PRIMARY KEY,
    business_name VARCHAR(255),
    mission TEXT,
    target_audience TEXT,
    brand_voice TEXT,
    core_values TEXT,
    key_differentiators TEXT,
    primary_market VARCHAR(255),
    notes TEXT,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE monthly_preferences (
    id SERIAL PRIMARY KEY,
    month INTEGER,
    year INTEGER,
    sending_days TEXT[],
    emails_per_week INTEGER,
    email_types TEXT[],
    primary_goal TEXT,
    secondary_goal TEXT,
    active_offers TEXT[],  -- Array of offer_ids
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(month, year)
);

-- Audit tables
CREATE TABLE audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    action VARCHAR(50),  -- CREATE, UPDATE, DELETE, EXPORT
    table_name VARCHAR(100),
    record_id TEXT,
    before_value JSONB,
    after_value JSONB,
    ip_address INET,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE error_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    error_message TEXT,
    error_code VARCHAR(50),
    context JSONB,
    severity VARCHAR(50),  -- ERROR, WARNING, INFO
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE sync_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operation VARCHAR(50),  -- migrate, import, export
    table_name VARCHAR(100),
    record_count INTEGER,
    status VARCHAR(50),  -- success, failed, partial
    details JSONB,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE idempotency_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operation_key VARCHAR(255) UNIQUE,
    result JSONB,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT cleanup_old CHECK (created_at > NOW() - INTERVAL '24 hours')
);

-- Create all indexes (see Performance Optimization section)
```

---

## 4. SQLAlchemy Model Definitions

### Base Model Setup

```python
# models/base.py
from sqlalchemy import Column, DateTime, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from datetime import datetime
from typing import Optional
import uuid

class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass

class TimestampMixin:
    """Mixin for created_at/updated_at timestamps."""
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), onupdate=func.now()
    )

class SoftDeleteMixin:
    """Mixin for soft deletes."""
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
```

### Core Models

```python
# models/operational.py
from sqlalchemy import Column, String, Text, Integer, Date, ForeignKey, Boolean, Numeric, ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from datetime import datetime, date
from typing import Optional, List
from uuid import uuid4
from models.base import Base, TimestampMixin, SoftDeleteMixin

class Lead(Base, TimestampMixin, SoftDeleteMixin):
    """Sales pipeline prospect."""
    __tablename__ = "leads"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    source: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_by: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    calls = relationship("Call", back_populates="lead", cascade="all, delete-orphan")
    goals = relationship("Goal", back_populates="lead", cascade="all, delete-orphan")
    pain_points = relationship("PainPoint", back_populates="lead", cascade="all, delete-orphan")
    objections = relationship("Objection", back_populates="lead", cascade="all, delete-orphan")

class Member(Base, TimestampMixin, SoftDeleteMixin):
    """Active cohort member."""
    __tablename__ = "members"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True)
    enrollment_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    coach_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="active")

    # Relationships
    calls = relationship("Call", back_populates="member", cascade="all, delete-orphan")
    goals = relationship("Goal", back_populates="member", cascade="all, delete-orphan")
    pain_points = relationship("PainPoint", back_populates="member", cascade="all, delete-orphan")
    wins = relationship("Win", back_populates="member", cascade="all, delete-orphan")

class Call(Base, TimestampMixin, SoftDeleteMixin):
    """Call transcript (Central Intelligence + CI unified)."""
    __tablename__ = "calls"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)  # CALL_<TranscriptUID>
    date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    call_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    call_result: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    call_owner: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    member_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=True), ForeignKey("members.id", ondelete="CASCADE"), nullable=True)
    lead_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=True)
    transcript_source: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    transcript_uid: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    transcript_quality: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    transcript_link: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    processed_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    call_duration_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    member = relationship("Member", back_populates="calls")
    lead = relationship("Lead", back_populates="calls")
    insights = relationship("Insight", back_populates="call", cascade="all, delete-orphan")
    content_ideas = relationship("ContentIdea", back_populates="call", cascade="all, delete-orphan")

class Insight(Base, TimestampMixin):
    """Voice-of-customer signal extracted from call."""
    __tablename__ = "insights"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)  # INS_<CallID>_01
    call_id: Mapped[str] = mapped_column(String(255), ForeignKey("calls.id", ondelete="CASCADE"), nullable=False)
    speaker_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    insight_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    signal_family: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    signal: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    signal_strength: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    pain_layer: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    raw_quote: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    what_they_say: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    the_real_problem: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    emotional_driver: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    core_fear_revealed: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    false_belief_revealed: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    structural_obstacle: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    identity_signal: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    buying_trigger: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    objection_created: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    marketing_translation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    hook_angle_example: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    best_use_case: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    quote_confidence: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    frequency_score: Mapped[int] = mapped_column(Integer, default=1)

    # Relationships
    call = relationship("Call", back_populates="insights")
    tags = relationship("InsightTag", back_populates="insight", cascade="all, delete-orphan")
    content_ideas = relationship("ContentIdea", back_populates="insight", cascade="all, delete-orphan")

class ContentIdea(Base, TimestampMixin, SoftDeleteMixin):
    """Marketing content idea generated from insights."""
    __tablename__ = "content_ideas"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)  # CONT_<CallID>_01
    insight_id: Mapped[Optional[str]] = mapped_column(String(255), ForeignKey("insights.id", ondelete="SET NULL"), nullable=True)
    call_id: Mapped[Optional[str]] = mapped_column(String(255), ForeignKey("calls.id", ondelete="SET NULL"), nullable=True)
    source: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    market_audience: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    content_format: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    content_angle: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    trigger_insight: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    raw_quote: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content_premise: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    hook_opening_line: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    teaching_point: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cta_idea: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    priority_level: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    best_platform: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    repurpose_opportunities: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    idea_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="Idea")

    # Relationships
    insight = relationship("Insight", back_populates="content_ideas")
    call = relationship("Call", back_populates="content_ideas")

class InsightTag(Base, TimestampMixin):
    """Tag assignment linking insights to tag vocabulary."""
    __tablename__ = "insight_tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    insight_id: Mapped[str] = mapped_column(String(255), ForeignKey("insights.id", ondelete="CASCADE"), nullable=False)
    tag: Mapped[str] = mapped_column(String(100), ForeignKey("tag_dictionary.tag", ondelete="RESTRICT"), nullable=False)

    # Relationships
    insight = relationship("Insight", back_populates="tags")
    tag_def = relationship("TagDictionary", back_populates="usages")

class TagDictionary(Base, TimestampMixin):
    """Canonical vocabulary for insights."""
    __tablename__ = "tag_dictionary"

    tag: Mapped[str] = mapped_column(String(100), primary_key=True)
    tag_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    synonyms: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    usages = relationship("InsightTag", back_populates="tag_def")

class Goal(Base, TimestampMixin, SoftDeleteMixin):
    """Member or lead goal."""
    __tablename__ = "goals"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    member_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=True), ForeignKey("members.id", ondelete="CASCADE"), nullable=True)
    lead_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=True)
    goal_text: Mapped[str] = mapped_column(Text, nullable=False)
    target_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="active")

    # Relationships
    member = relationship("Member", back_populates="goals")
    lead = relationship("Lead", back_populates="goals")

class PainPoint(Base, TimestampMixin, SoftDeleteMixin):
    """Customer pain point."""
    __tablename__ = "pain_points"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    member_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=True), ForeignKey("members.id", ondelete="CASCADE"), nullable=True)
    lead_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    frequency_count: Mapped[int] = mapped_column(Integer, default=1)

    # Relationships
    member = relationship("Member", back_populates="pain_points")
    lead = relationship("Lead", back_populates="pain_points")

class Win(Base, TimestampMixin):
    """Member win/achievement."""
    __tablename__ = "wins"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    member_id: Mapped[str] = mapped_column(UUID(as_uuid=True), ForeignKey("members.id", ondelete="CASCADE"), nullable=False)
    win_text: Mapped[str] = mapped_column(Text, nullable=False)
    win_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    impact_area: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Relationships
    member = relationship("Member", back_populates="wins")

class Objection(Base, TimestampMixin, SoftDeleteMixin):
    """Sales objection encountered."""
    __tablename__ = "objections"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    lead_id: Mapped[str] = mapped_column(UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False)
    objection_text: Mapped[str] = mapped_column(Text, nullable=False)
    context: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    resolution_offered: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    lead = relationship("Lead", back_populates="objections")

# Additional models: User, Team, Offer, BusinessProfile, MonthlyPreferences, AuditLog, ErrorLog, SyncLog, IdempotencyKey
# (Full definitions follow same pattern)

class User(Base, TimestampMixin):
    """System user."""
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    role: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

class Offer(Base, TimestampMixin):
    """Product, service, or promotional offer."""
    __tablename__ = "offers"

    offer_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    offer_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    price: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="Active")
    url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

class BusinessProfile(Base, TimestampMixin):
    """Brand voice and business context."""
    __tablename__ = "business_profile"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    business_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    mission: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    target_audience: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    brand_voice: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    core_values: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    key_differentiators: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    primary_market: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

class MonthlyPreference(Base, TimestampMixin):
    """Email calendar configuration per month."""
    __tablename__ = "monthly_preferences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    sending_days: Mapped[Optional[List[str]]] = mapped_column(ARRAY(String), nullable=True)
    emails_per_week: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    email_types: Mapped[Optional[List[str]]] = mapped_column(ARRAY(String), nullable=True)
    primary_goal: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    secondary_goal: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    active_offers: Mapped[Optional[List[str]]] = mapped_column(ARRAY(String), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

class AuditLog(Base):
    """Data change audit trail."""
    __tablename__ = "audit_log"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    table_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    record_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    before_value: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    after_value: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())
```

---

## 5. Repository Pattern Interface & Implementation

### Repository Base Class

```python
# repositories/base.py
from typing import Generic, TypeVar, List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import Query
from pydantic import BaseModel

T = TypeVar('T')  # Model type
CreateSchemaT = TypeVar('CreateSchemaT', bound=BaseModel)
UpdateSchemaT = TypeVar('UpdateSchemaT', bound=BaseModel)

class RepositoryBase(Generic[T]):
    """Abstract repository interface for all data access operations."""

    def __init__(self, db_session: AsyncSession, model_class: type[T]):
        self.db_session = db_session
        self.model_class = model_class

    async def get(self, id: Any) -> Optional[T]:
        """Fetch single record by ID."""
        stmt = select(self.model_class).where(self.model_class.id == id)
        result = await self.db_session.execute(stmt)
        return result.scalars().first()

    async def list(
        self,
        skip: int = 0,
        limit: int = 100,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[T]:
        """Fetch multiple records with filtering."""
        stmt = select(self.model_class)

        # Apply filters if provided
        if filters:
            for key, value in filters.items():
                if hasattr(self.model_class, key):
                    stmt = stmt.where(getattr(self.model_class, key) == value)

        stmt = stmt.offset(skip).limit(limit)
        result = await self.db_session.execute(stmt)
        return result.scalars().all()

    async def create(self, obj_in: CreateSchemaT) -> T:
        """Create new record."""
        db_obj = self.model_class(**obj_in.model_dump())
        self.db_session.add(db_obj)
        await self.db_session.flush()
        await self.db_session.refresh(db_obj)
        return db_obj

    async def update(self, id: Any, obj_in: UpdateSchemaT) -> Optional[T]:
        """Update existing record."""
        db_obj = await self.get(id)
        if db_obj:
            update_data = obj_in.model_dump(exclude_unset=True)
            for field, value in update_data.items():
                setattr(db_obj, field, value)
            await self.db_session.flush()
            await self.db_session.refresh(db_obj)
        return db_obj

    async def delete(self, id: Any) -> bool:
        """Hard delete record."""
        db_obj = await self.get(id)
        if db_obj:
            await self.db_session.delete(db_obj)
            await self.db_session.flush()
            return True
        return False

    async def soft_delete(self, id: Any) -> Optional[T]:
        """Soft delete (set deleted_at timestamp)."""
        db_obj = await self.get(id)
        if db_obj and hasattr(db_obj, 'deleted_at'):
            from datetime import datetime
            db_obj.deleted_at = datetime.utcnow()
            await self.db_session.flush()
            await self.db_session.refresh(db_obj)
        return db_obj

    async def exists(self, id: Any) -> bool:
        """Check if record exists."""
        stmt = select(self.model_class.id).where(self.model_class.id == id)
        result = await self.db_session.execute(stmt)
        return result.scalars().first() is not None
```

### Concrete Repository Implementations

```python
# repositories/lead.py
from typing import Optional, List, Dict, Any
from sqlalchemy import and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from models.operational import Lead
from repositories.base import RepositoryBase
from pydantic import BaseModel

class LeadCreate(BaseModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    status: Optional[str] = None
    source: Optional[str] = None
    notes: Optional[str] = None
    created_by: Optional[str] = None

class LeadUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None

class LeadRepository(RepositoryBase[Lead]):
    """Repository for Lead operations."""

    async def get_by_email(self, email: str) -> Optional[Lead]:
        """Fetch lead by email."""
        stmt = select(Lead).where(
            and_(Lead.email == email.lower(), Lead.deleted_at == None)
        )
        result = await self.db_session.execute(stmt)
        return result.scalars().first()

    async def list_by_status(
        self,
        status: str,
        skip: int = 0,
        limit: int = 100
    ) -> List[Lead]:
        """List leads by status."""
        stmt = select(Lead).where(
            and_(Lead.status == status, Lead.deleted_at == None)
        ).offset(skip).limit(limit)
        result = await self.db_session.execute(stmt)
        return result.scalars().all()

    async def search(self, query: str, skip: int = 0, limit: int = 100) -> List[Lead]:
        """Search leads by name or email."""
        search_term = f"%{query}%"
        stmt = select(Lead).where(
            and_(
                or_(
                    Lead.name.ilike(search_term),
                    Lead.email.ilike(search_term)
                ),
                Lead.deleted_at == None
            )
        ).offset(skip).limit(limit)
        result = await self.db_session.execute(stmt)
        return result.scalars().all()

    async def count_by_status(self) -> Dict[str, int]:
        """Get count of leads by each status."""
        stmt = select(
            Lead.status,
            func.count(Lead.id).label('count')
        ).where(Lead.deleted_at == None).group_by(Lead.status)
        result = await self.db_session.execute(stmt)
        return {row[0]: row[1] for row in result.all()}

# Similar repositories for Member, Call, Insight, ContentIdea, etc.
# Key principle: All database logic encapsulated, agents never execute raw SQL

class MemberRepository(RepositoryBase[Member]):
    async def list_by_coach(self, coach_id: str, skip: int = 0, limit: int = 100) -> List[Member]:
        stmt = select(Member).where(
            and_(Member.coach_id == coach_id, Member.deleted_at == None, Member.status == "active")
        ).offset(skip).limit(limit)
        result = await self.db_session.execute(stmt)
        return result.scalars().all()

    async def count_active(self) -> int:
        stmt = select(func.count(Member.id)).where(
            and_(Member.deleted_at == None, Member.status == "active")
        )
        result = await self.db_session.execute(stmt)
        return result.scalar()

class CallRepository(RepositoryBase[Call]):
    async def list_by_member(self, member_id: str, skip: int = 0, limit: int = 100) -> List[Call]:
        stmt = select(Call).where(
            and_(Call.member_id == member_id, Call.deleted_at == None)
        ).order_by(desc(Call.date)).offset(skip).limit(limit)
        result = await self.db_session.execute(stmt)
        return result.scalars().all()

    async def get_by_transcript_uid(self, transcript_uid: str) -> Optional[Call]:
        stmt = select(Call).where(Call.transcript_uid == transcript_uid)
        result = await self.db_session.execute(stmt)
        return result.scalars().first()

class InsightRepository(RepositoryBase[Insight]):
    async def list_by_call(self, call_id: str, skip: int = 0, limit: int = 100) -> List[Insight]:
        stmt = select(Insight).where(Insight.call_id == call_id).offset(skip).limit(limit)
        result = await self.db_session.execute(stmt)
        return result.scalars().all()

    async def list_by_type(self, insight_type: str, skip: int = 0, limit: int = 100) -> List[Insight]:
        stmt = select(Insight).where(Insight.insight_type == insight_type).offset(skip).limit(limit)
        result = await self.db_session.execute(stmt)
        return result.scalars().all()

    async def list_by_signal_family(self, family: str, skip: int = 0, limit: int = 100) -> List[Insight]:
        stmt = select(Insight).where(Insight.signal_family == family).offset(skip).limit(limit)
        result = await self.db_session.execute(stmt)
        return result.scalars().all()

class ContentIdeaRepository(RepositoryBase[ContentIdea]):
    async def list_by_status(self, status: str, skip: int = 0, limit: int = 100) -> List[ContentIdea]:
        stmt = select(ContentIdea).where(
            and_(ContentIdea.status == status, ContentIdea.deleted_at == None)
        ).order_by(desc(ContentIdea.created_at)).offset(skip).limit(limit)
        result = await self.db_session.execute(stmt)
        return result.scalars().all()

    async def list_by_format(self, format: str, skip: int = 0, limit: int = 100) -> List[ContentIdea]:
        stmt = select(ContentIdea).where(
            and_(ContentIdea.content_format == format, ContentIdea.deleted_at == None)
        ).offset(skip).limit(limit)
        result = await self.db_session.execute(stmt)
        return result.scalars().all()
```

### Repository Service Locator

```python
# repositories/__init__.py
from sqlalchemy.ext.asyncio import AsyncSession
from repositories.base import RepositoryBase
from repositories.lead import LeadRepository
from repositories.member import MemberRepository
from repositories.call import CallRepository
from repositories.insight import InsightRepository
from repositories.content_idea import ContentIdeaRepository
# ... import all repository classes

class RepositoryFactory:
    """Factory for creating repository instances."""

    @staticmethod
    def get_lead_repo(session: AsyncSession) -> LeadRepository:
        return LeadRepository(session, Lead)

    @staticmethod
    def get_member_repo(session: AsyncSession) -> MemberRepository:
        return MemberRepository(session, Member)

    @staticmethod
    def get_call_repo(session: AsyncSession) -> CallRepository:
        return CallRepository(session, Call)

    @staticmethod
    def get_insight_repo(session: AsyncSession) -> InsightRepository:
        return InsightRepository(session, Insight)

    @staticmethod
    def get_content_idea_repo(session: AsyncSession) -> ContentIdeaRepository:
        return ContentIdeaRepository(session, ContentIdea)

    # ... factories for all repositories
```

### Agent Usage Example

```python
# agents/sales_agent.py
from repositories import RepositoryFactory
from database import AsyncSessionLocal

class SalesAgent:
    """Agent for sales operations."""

    async def find_unqualified_leads(self, limit: int = 100):
        """Find leads that haven't been contacted in 30 days."""
        async with AsyncSessionLocal() as session:
            lead_repo = RepositoryFactory.get_lead_repo(session)
            leads = await lead_repo.list_by_status("new", limit=limit)
            return leads

    async def qualify_lead(self, lead_id: str, qualification_data: dict):
        """Qualify a lead and update status."""
        async with AsyncSessionLocal() as session:
            lead_repo = RepositoryFactory.get_lead_repo(session)
            lead = await lead_repo.update(
                lead_id,
                LeadUpdate(status="qualified", **qualification_data)
            )
            await session.commit()
            return lead

# Key principle: Agent never writes SQL, never handles database connections
# Agent calls repository methods, repository handles all database logic
```

---

## 6. Database Configuration & Supabase Setup

### Environment Configuration

```bash
# .env
DATABASE_URL=postgresql+asyncpg://postgres.{PROJECT_ID}:{PASSWORD}@db.{PROJECT_ID}.supabase.co/postgres
SUPABASE_URL=https://{PROJECT_ID}.supabase.co
SUPABASE_PUBLISHABLE_KEY={PUBLISHABLE_KEY}
SUPABASE_SECRET_KEY={SECRET_KEY}

REDIS_URL=redis://{HOST}:{PORT}/{DB}

# Database connection pool settings
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=10
DB_POOL_RECYCLE=3600
DB_ECHO=false  # Set to true for SQL logging
```

### Supabase Setup Guide

```python
# setup/supabase_init.py
"""Initialize Supabase project with required tables and configurations."""

import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from models.base import Base
from models.operational import *  # Import all models

async def init_database():
    """Create all tables and indexes."""
    engine = create_async_engine(
        DATABASE_URL,
        echo=True,
        future=True
    )

    async with engine.begin() as conn:
        # Create all tables
        await conn.run_sync(Base.metadata.create_all)

        # Create indexes (see Performance Optimization section)
        await conn.run_sync(create_indexes)

        # Enable RLS (Row Level Security)
        await conn.run_sync(enable_rls_policies)

    await engine.dispose()

async def create_indexes(connection):
    """Create all performance indexes."""
    indexes = [
        # Leads indexes
        "CREATE INDEX IF NOT EXISTS idx_leads_status ON leads(status) WHERE deleted_at IS NULL",
        "CREATE INDEX IF NOT EXISTS idx_leads_source ON leads(source) WHERE deleted_at IS NULL",
        "CREATE INDEX IF NOT EXISTS idx_leads_created_at ON leads(created_at DESC) WHERE deleted_at IS NULL",
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_leads_email ON leads(LOWER(email)) WHERE deleted_at IS NULL",

        # Members indexes
        "CREATE INDEX IF NOT EXISTS idx_members_status ON members(status) WHERE deleted_at IS NULL",
        "CREATE INDEX IF NOT EXISTS idx_members_coach ON members(coach_id) WHERE deleted_at IS NULL",
        "CREATE INDEX IF NOT EXISTS idx_members_active ON members(id) WHERE deleted_at IS NULL AND status = 'active'",

        # Calls indexes
        "CREATE INDEX IF NOT EXISTS idx_calls_member ON calls(member_id) WHERE deleted_at IS NULL",
        "CREATE INDEX IF NOT EXISTS idx_calls_lead ON calls(lead_id) WHERE deleted_at IS NULL",
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_calls_transcript_uid ON calls(transcript_uid) WHERE deleted_at IS NULL",
        "CREATE INDEX IF NOT EXISTS idx_calls_date ON calls(date DESC) WHERE deleted_at IS NULL",

        # Insights indexes
        "CREATE INDEX IF NOT EXISTS idx_insights_call ON insights(call_id)",
        "CREATE INDEX IF NOT EXISTS idx_insights_type ON insights(insight_type)",
        "CREATE INDEX IF NOT EXISTS idx_insights_family ON insights(signal_family)",
        "CREATE INDEX IF NOT EXISTS idx_insights_strength ON insights(signal_strength)",

        # Content Ideas indexes
        "CREATE INDEX IF NOT EXISTS idx_content_ideas_status ON content_ideas(status) WHERE deleted_at IS NULL",
        "CREATE INDEX IF NOT EXISTS idx_content_ideas_format ON content_ideas(content_format) WHERE deleted_at IS NULL",
        "CREATE INDEX IF NOT EXISTS idx_content_ideas_insight ON content_ideas(insight_id) WHERE deleted_at IS NULL",

        # Market Signals indexes
        "CREATE INDEX IF NOT EXISTS idx_market_signals_family ON market_signals(signal_family)",
        "CREATE INDEX IF NOT EXISTS idx_market_signals_type ON market_signals(insight_type)",
    ]

    for idx_sql in indexes:
        await connection.execute(idx_sql)

async def enable_rls_policies(connection):
    """Enable Row Level Security policies (see RLS section)."""
    # RLS policies defined in Section 8
    pass

if __name__ == "__main__":
    asyncio.run(init_database())
```

### Connection Pooling Best Practices

```python
# database.py (enhanced for production)
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool, QueuePool
import os
from contextlib import asynccontextmanager

class DatabaseConfig:
    """Database configuration management."""

    @staticmethod
    def get_engine():
        """Create async engine with Supabase-optimized settings."""
        return create_async_engine(
            os.getenv("DATABASE_URL"),
            echo=os.getenv("DB_ECHO", "false").lower() == "true",
            future=True,
            # Supabase recommends NullPool for serverless environments
            # For persistent servers, use QueuePool with appropriate settings
            poolclass=NullPool if os.getenv("SERVERLESS", "true").lower() == "true" else QueuePool,
            pool_size=int(os.getenv("DB_POOL_SIZE", 20)),
            max_overflow=int(os.getenv("DB_MAX_OVERFLOW", 10)),
            pool_recycle=int(os.getenv("DB_POOL_RECYCLE", 3600)),
            pool_pre_ping=True,  # Verify connections
            connect_args={
                "server_settings": {
                    "application_name": "centralintelligence-app",
                    "jit": "off"  # Disable JIT for predictable performance
                }
            }
        )

async_engine = DatabaseConfig.get_engine()
AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    future=True
)

@asynccontextmanager
async def get_session():
    """Context manager for database sessions."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
```

---

## 7. Alembic Migrations & Schema Management

### Alembic Setup

```bash
# Initialize Alembic
alembic init -t async migrations

# Edit alembic.ini
# sqlalchemy.url should match DATABASE_URL from environment
```

### Base Migration Template

```python
# migrations/env.py
"""Alembic environment configuration."""

from logging.config import fileConfig
from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context
from alembic.operations import Operations
import os
from models.base import Base

# Include all models
from models.operational import *

# this is the Alembic Config object, which provides
# the values of the [alembic] section of the setup.py file.
config = context.config

# Interpret the config file for Python logging.
fileConfig(config.config_file_name)

# Model's MetaData object for 'autogenerate' support
target_metadata = Base.metadata

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = os.getenv('DATABASE_URL')
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = os.getenv('DATABASE_URL')

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()

    connectable.dispose()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

### Creating Migrations

```bash
# Auto-generate migration after model changes
alembic revision --autogenerate -m "Add new fields to leads table"

# Edit generated migration if needed
# migrations/versions/001_add_fields.py

# Apply migration to database
alembic upgrade head

# Rollback last migration if needed
alembic downgrade -1

# View migration history
alembic history
```

### Sample Migration

```python
# migrations/versions/001_initial_schema.py
"""Initial schema creation."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

def upgrade() -> None:
    op.create_table(
        'leads',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('email', sa.String(255), nullable=True),
        sa.Column('phone', sa.String(20), nullable=True),
        sa.Column('status', sa.String(50), nullable=True),
        sa.Column('source', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL')
    )

    # Create indexes
    op.create_index('idx_leads_status', 'leads', ['status'],
                    postgresql_where=sa.text('deleted_at IS NULL'))
    op.create_index('idx_leads_source', 'leads', ['source'],
                    postgresql_where=sa.text('deleted_at IS NULL'))
    # ... more indexes

def downgrade() -> None:
    op.drop_table('leads')
```

---

## 8. Row Level Security (RLS) & Multi-Tenant Data

### RLS Policy Setup

```sql
-- Enable RLS on all tables
ALTER TABLE leads ENABLE ROW LEVEL SECURITY;
ALTER TABLE members ENABLE ROW LEVEL SECURITY;
ALTER TABLE calls ENABLE ROW LEVEL SECURITY;
ALTER TABLE insights ENABLE ROW LEVEL SECURITY;
ALTER TABLE content_ideas ENABLE ROW LEVEL SECURITY;
-- ... enable on all tables

-- Leads: Users see leads they created or are assigned to
CREATE POLICY leads_user_isolation ON leads
  FOR SELECT USING (
    auth.uid() = created_by OR
    EXISTS (
      SELECT 1 FROM teams t
      WHERE t.id = (auth.jwt() ->> 'team_id')::uuid
    )
  );

CREATE POLICY leads_insert_policy ON leads
  FOR INSERT WITH CHECK (
    auth.uid() = created_by
  );

CREATE POLICY leads_update_policy ON leads
  FOR UPDATE USING (
    auth.uid() = created_by OR
    (auth.jwt() ->> 'role' = 'admin')
  );

-- Calls: Users see calls for members they coach or leads they own
CREATE POLICY calls_user_isolation ON calls
  FOR SELECT USING (
    EXISTS (
      SELECT 1 FROM members m
      WHERE m.id = calls.member_id AND m.coach_id = auth.uid()
    ) OR
    EXISTS (
      SELECT 1 FROM leads l
      WHERE l.id = calls.lead_id AND l.created_by = auth.uid()
    )
  );

-- Insights: Read access to insights for corresponding calls
CREATE POLICY insights_read ON insights
  FOR SELECT USING (
    EXISTS (
      SELECT 1 FROM calls c
      WHERE c.id = insights.call_id AND (
        EXISTS (
          SELECT 1 FROM members m
          WHERE m.id = c.member_id AND m.coach_id = auth.uid()
        ) OR
        EXISTS (
          SELECT 1 FROM leads l
          WHERE l.id = c.lead_id AND l.created_by = auth.uid()
        )
      )
    )
  );

-- Admin override: Admins see everything
CREATE POLICY admin_override ON leads
  FOR SELECT USING (auth.jwt() ->> 'role' = 'admin');

CREATE POLICY admin_override_calls ON calls
  FOR SELECT USING (auth.jwt() ->> 'role' = 'admin');
```

### RLS in Python (Supabase Client)

```python
# auth/rls.py
"""Row Level Security utilities."""

from supabase import create_client
from supabase.client import Client
import os

class RLSManager:
    """Manage Row Level Security policies."""

    def __init__(self):
        self.supabase: Client = create_client(
            os.getenv("SUPABASE_URL"),
            os.getenv("SUPABASE_SECRET_KEY")
        )

    async def get_user_leads(self, user_id: str):
        """Fetch leads visible to user (respects RLS)."""
        response = self.supabase.table("leads").select("*").eq("created_by", user_id).execute()
        return response.data

    async def get_team_members(self, coach_id: str):
        """Fetch members coached by user (respects RLS)."""
        response = self.supabase.table("members").select("*").eq("coach_id", coach_id).execute()
        return response.data
```

---

## 9. Redis Caching Strategy

### Cache Configuration

```python
# cache/redis.py
"""Redis caching layer."""

import redis.asyncio as redis
from typing import Optional, Any
import json
import os

class RedisCache:
    """Redis-backed cache for frequently accessed data."""

    def __init__(self):
        self.redis: Optional[redis.Redis] = None

    async def init(self):
        """Initialize Redis connection."""
        self.redis = await redis.from_url(
            os.getenv("REDIS_URL", "redis://localhost:6379/0"),
            encoding="utf8",
            decode_responses=True
        )

    async def get(self, key: str) -> Optional[Any]:
        """Fetch from cache."""
        value = await self.redis.get(key)
        return json.loads(value) if value else None

    async def set(self, key: str, value: Any, ttl: int = 300):
        """Store in cache with TTL (seconds)."""
        await self.redis.setex(
            key,
            ttl,
            json.dumps(value)
        )

    async def delete(self, key: str):
        """Remove from cache."""
        await self.redis.delete(key)

    async def invalidate_pattern(self, pattern: str):
        """Invalidate cache keys matching pattern."""
        keys = await self.redis.keys(pattern)
        if keys:
            await self.redis.delete(*keys)

cache = RedisCache()
```

### Cache Usage in Repositories

```python
# repositories/lead.py (with caching)
class LeadRepository(RepositoryBase[Lead]):

    async def get(self, id: str) -> Optional[Lead]:
        """Fetch lead with caching."""
        cache_key = f"lead:{id}"

        # Try cache first
        cached = await cache.get(cache_key)
        if cached:
            return Lead(**cached)

        # Cache miss: query database
        lead = await super().get(id)
        if lead:
            await cache.set(cache_key, lead.to_dict(), ttl=600)

        return lead

    async def list_by_status(self, status: str, skip: int = 0, limit: int = 100) -> List[Lead]:
        """List leads by status with caching."""
        cache_key = f"leads:status:{status}:{skip}:{limit}"

        cached = await cache.get(cache_key)
        if cached:
            return [Lead(**item) for item in cached]

        leads = await super().list_by_status(status, skip, limit)
        await cache.set(cache_key, [lead.to_dict() for lead in leads], ttl=300)

        return leads

    async def update(self, id: str, obj_in: LeadUpdate) -> Optional[Lead]:
        """Update with cache invalidation."""
        lead = await super().update(id, obj_in)

        # Invalidate relevant caches
        await cache.delete(f"lead:{id}")
        await cache.invalidate_pattern(f"leads:status:*")

        return lead

# Cache invalidation strategy
# - Single record cache: 10 minutes
# - List cache: 5 minutes
# - Invalidate on every write (create/update/delete)
# - Use cache.invalidate_pattern() for dependent lists
```

---

## 10. Data Migration Playbook

### Migration from Airtable/n8n to Supabase

#### Phase 1: Preparation (1-2 weeks)

1. **Schema Design**: Complete (see Section 3, 4, 5)
2. **Connection Setup**: Supabase project created, DATABASE_URL configured
3. **Test Environment**: Separate Supabase instance for validation

#### Phase 2: Initial Load (1-2 days)

```python
# scripts/migrate_airtable_to_supabase.py
"""Migrate all data from Airtable/n8n to Supabase."""

import asyncio
from airtable import Airtable
from sqlalchemy.ext.asyncio import AsyncSession
from repositories import RepositoryFactory
from database import AsyncSessionLocal
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def migrate_leads():
    """Migrate leads from Airtable to Supabase."""

    # 1. Export from Airtable
    airtable = Airtable(os.getenv("AIRTABLE_API_KEY"))
    airtable_leads = airtable.get_all(
        table=os.getenv("AIRTABLE_TABLE_LEADS"),
        view="Grid view"
    )
    logger.info(f"Exported {len(airtable_leads)} leads from Airtable")

    # 2. Transform data
    transformed = []
    for record in airtable_leads:
        transformed.append({
            "name": record["fields"].get("Name"),
            "email": record["fields"].get("Email"),
            "phone": record["fields"].get("Phone"),
            "status": record["fields"].get("Status", [None])[0],
            "source": record["fields"].get("Source"),
            "notes": record["fields"].get("Notes"),
            "created_at": record["createdTime"]
        })

    # 3. Load into Supabase
    async with AsyncSessionLocal() as session:
        lead_repo = RepositoryFactory.get_lead_repo(session)

        for lead_data in transformed:
            try:
                lead = await lead_repo.create(LeadCreate(**lead_data))
                logger.info(f"Created lead: {lead.id}")
            except Exception as e:
                logger.error(f"Failed to create lead {lead_data['name']}: {e}")

        await session.commit()

    logger.info(f"Completed migration of {len(transformed)} leads")

async def migrate_all():
    """Migrate all tables."""
    await migrate_leads()
    await migrate_members()
    await migrate_calls()
    # ... migrate all tables

if __name__ == "__main__":
    asyncio.run(migrate_all())
```

#### Phase 3: Dual-Write Validation (1-2 weeks)

```python
# agents/migration_validator.py
"""Validate data consistency during migration."""

class MigrationValidator:

    async def validate_record_counts(self):
        """Compare Airtable vs Supabase record counts."""
        airtable = Airtable(os.getenv("AIRTABLE_API_KEY"))
        at_count = len(airtable.get_all(table=os.getenv("AIRTABLE_TABLE_LEADS")))

        async with AsyncSessionLocal() as session:
            lead_repo = RepositoryFactory.get_lead_repo(session)
            stmt = select(func.count(Lead.id))
            pg_count = (await session.execute(stmt)).scalar()

        logger.info(f"Airtable: {at_count}, Supabase: {pg_count}")
        assert at_count == pg_count, "Record count mismatch!"

    async def validate_sample_records(self, sample_size: int = 10):
        """Spot-check sample records for data integrity."""
        airtable = Airtable(os.getenv("AIRTABLE_API_KEY"))
        at_records = airtable.get_all(
            table=os.getenv("AIRTABLE_TABLE_LEADS"),
            max_records=sample_size
        )

        async with AsyncSessionLocal() as session:
            lead_repo = RepositoryFactory.get_lead_repo(session)

            for at_record in at_records:
                email = at_record["fields"].get("Email")
                pg_lead = await lead_repo.get_by_email(email)

                assert pg_lead is not None, f"Lead {email} not found in Supabase!"
                assert pg_lead.name == at_record["fields"].get("Name"), f"Name mismatch for {email}"

        logger.info(f"Validated {sample_size} records successfully")
```

#### Phase 4: Cutover (1 day)

```python
# agents/cutover_agent.py
"""Execute migration cutover."""

class CutoverAgent:

    async def execute_cutover(self):
        """Switch all operations to Supabase."""

        logger.info("Starting cutover...")

        # 1. Final validation
        validator = MigrationValidator()
        await validator.validate_record_counts()
        await validator.validate_sample_records(sample_size=100)

        # 2. Disable Airtable writes (if using dual-write)
        # Set environment variable or feature flag

        # 3. Test Supabase reads
        async with AsyncSessionLocal() as session:
            lead_repo = RepositoryFactory.get_lead_repo(session)
            test_leads = await lead_repo.list_by_status("new", limit=10)
            assert len(test_leads) > 0, "No leads found!"

        # 4. Alert team
        logger.info("Cutover complete! All operations now on Supabase")

    async def rollback(self):
        """Rollback to Airtable if critical issues."""
        logger.warn("Rolling back to Airtable...")
        # Re-enable Airtable reads, disable Supabase writes
```

---

## 11. Data Integrity Rules

### Referential Integrity Constraints

```sql
-- Already defined in models (SQLAlchemy handles via ForeignKey)
-- Additional SQL-level constraints for safety:

-- Lead cannot be deleted if calls exist (RESTRICT)
ALTER TABLE calls
ADD CONSTRAINT fk_calls_lead
FOREIGN KEY (lead_id) REFERENCES leads(id)
ON DELETE RESTRICT;

-- Member cannot be deleted if calls or goals exist
ALTER TABLE calls
ADD CONSTRAINT fk_calls_member
FOREIGN KEY (member_id) REFERENCES members(id)
ON DELETE RESTRICT;

-- Call can be deleted if member deleted (CASCADE)
ALTER TABLE insights
ADD CONSTRAINT fk_insights_call
FOREIGN KEY (call_id) REFERENCES calls(id)
ON DELETE CASCADE;
```

### Soft Delete Cascade Triggers

```sql
-- Trigger to cascade soft deletes
CREATE OR REPLACE FUNCTION soft_delete_cascade()
RETURNS TRIGGER AS $$
BEGIN
  -- When a lead is soft-deleted, soft-delete all related calls
  IF TG_TABLE_NAME = 'leads' AND NEW.deleted_at IS NOT NULL THEN
    UPDATE calls
    SET deleted_at = NEW.deleted_at
    WHERE lead_id = NEW.id AND deleted_at IS NULL;
  END IF;

  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER lead_soft_delete_trigger
AFTER UPDATE ON leads
FOR EACH ROW
EXECUTE FUNCTION soft_delete_cascade();
```

### Duplicate Detection

```python
# repositories/lead.py - Duplicate prevention
class LeadRepository(RepositoryBase[Lead]):

    async def create(self, obj_in: LeadCreate) -> Lead:
        """Create lead, checking for duplicates first."""

        # Check if email exists
        if obj_in.email:
            existing = await self.get_by_email(obj_in.email)
            if existing and existing.deleted_at is None:
                raise ValueError(f"Lead with email {obj_in.email} already exists")

        return await super().create(obj_in)

    async def upsert_by_email(self, obj_in: LeadCreate) -> Lead:
        """Create or update lead if email exists."""
        existing = await self.get_by_email(obj_in.email)

        if existing:
            return await self.update(existing.id, LeadUpdate(**obj_in.model_dump()))
        else:
            return await self.create(obj_in)
```

---

## 12. Performance Optimization

### Index Strategy

All indexes are created during schema initialization (see Section 6). Key indexes by table:

**Leads**:
- `idx_leads_status` — Common filter for UI
- `idx_leads_source` — Analytics grouping
- `idx_leads_created_at` — Sorting, date range queries
- `idx_leads_email` — Unique constraint, lookup

**Calls**:
- `idx_calls_member` — Fetch calls for member
- `idx_calls_lead` — Fetch calls for lead
- `idx_calls_date` — Sorting, trending
- `idx_calls_transcript_uid` — Prevent duplicates

**Insights**:
- `idx_insights_call` — Fetch insights per call
- `idx_insights_family` — Filter by signal type
- `idx_insights_strength` — Filter by confidence

**Content Ideas**:
- `idx_content_ideas_status` — Filter by status
- `idx_content_ideas_format` — Filter by type

### Query Optimization Patterns

```python
# ✓ GOOD: Filtering at database level
async def get_active_members(limit: int = 100):
    async with AsyncSessionLocal() as session:
        repo = RepositoryFactory.get_member_repo(session)
        members = await repo.list(
            filters={"status": "active"},
            limit=limit
        )
    return members

# ✗ BAD: Filtering in application
async def get_active_members_bad():
    async with AsyncSessionLocal() as session:
        repo = RepositoryFactory.get_member_repo(session)
        all_members = await repo.list(limit=10000)  # Fetch all!
        return [m for m in all_members if m.status == "active"]
```

### Pagination Pattern

```python
# Cursor-based pagination (efficient for large datasets)
class PaginatedResponse(BaseModel):
    data: List[Any]
    cursor: Optional[str] = None
    has_more: bool = False

async def list_leads_paginated(cursor: Optional[str] = None, limit: int = 20):
    async with AsyncSessionLocal() as session:
        repo = RepositoryFactory.get_lead_repo(session)

        stmt = select(Lead).where(Lead.deleted_at == None)

        if cursor:
            # cursor = ID of last item from previous page
            stmt = stmt.where(Lead.created_at < (
                select(Lead.created_at).where(Lead.id == cursor).correlate(None).scalar_subquery()
            ))

        stmt = stmt.order_by(desc(Lead.created_at)).limit(limit + 1)
        result = await session.execute(stmt)
        leads = result.scalars().all()

        has_more = len(leads) > limit
        leads = leads[:limit]

        return PaginatedResponse(
            data=leads,
            cursor=leads[-1].id if leads else None,
            has_more=has_more
        )
```

### Caching Best Practices

See Section 9 (Redis Caching Strategy) for full cache patterns.

---

## 13. Backup & Recovery

### Automated Backups

```python
# scripts/backup_manager.py
"""Manage database backups."""

import subprocess
import os
from datetime import datetime

class BackupManager:

    async def create_backup(self):
        """Create PostgreSQL backup."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"ci_backup_{timestamp}.sql.gz"

        # Using Supabase CLI
        subprocess.run([
            "supabase", "db", "pull",
            "--output", filename
        ])

        logger.info(f"Backup created: {filename}")
        return filename

    async def upload_to_s3(self, filename: str):
        """Upload backup to S3."""
        import boto3

        s3 = boto3.client('s3')
        s3.upload_file(
            filename,
            os.getenv("AWS_BACKUP_BUCKET"),
            f"backups/{filename}"
        )
        logger.info(f"Backup uploaded to S3: {filename}")

# Schedule daily backups (use APScheduler or similar)
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()
scheduler.add_job(BackupManager().create_backup, 'cron', hour=2, minute=0)
scheduler.add_job(BackupManager().upload_to_s3, 'cron', hour=2, minute=30)
scheduler.start()
```

### Point-in-Time Recovery

```python
# Recovery via Supabase dashboard or CLI
# supabase db pull --recovery-to "2026-03-29T12:00:00"

# Or programmatically:
async def restore_from_backup(backup_time: str):
    """Restore database to specific point in time."""
    # Contact Supabase support or use PITR API
    logger.info(f"Restoring database to {backup_time}...")
```

---

## Conclusion

**Version 3.0.0** represents a complete redesign of the Central Intelligence data layer, transitioning from n8n Data Tables and Airtable to a unified Supabase PostgreSQL database with:

✓ **Repository Pattern**: All database access abstracted, enabling swappable storage
✓ **SQLAlchemy ORM**: Type-safe models with async support
✓ **Alembic Migrations**: Version-controlled schema changes
✓ **RLS Security**: Multi-tenant data isolation at database level
✓ **Redis Caching**: Hot data optimization
✓ **Unified Schema**: 32 tables consolidating Central Intelligence + CI data
✓ **Async-First**: Non-blocking operations for agent scalability
✓ **Migration Playbook**: Step-by-step Airtable to Supabase transition
✓ **Full Testing**: Validation patterns for data integrity

All agents interact exclusively through the Repository interface, maintaining clean separation of concerns and enabling future database migrations with minimal code changes.

---

*Data Schema v3.0.0 — Central Intelligence (Central Intelligence) Business Automation System*
*Last updated: 2026-03-29*
*Architecture: Supabase PostgreSQL with SQLAlchemy 2.0 ORM, Repository Pattern, Alembic migrations, Row Level Security, Redis caching. Consolidated 32 tables from n8n Data Tables, Airtable, and Central Intelligence into single unified schema. Async-first design with asyncpg driver. Full migration playbook from legacy systems.*
