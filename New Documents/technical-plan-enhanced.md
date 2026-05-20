# Central Intelligence (Central Intelligence) - Technical Plan v3.0.0

## 1. System Architecture

### Overview

The Central Intelligence system consists of three parallel components:

1. **Python Agent Backend** - Central Intelligence orchestrator + 3 Directors + ~15 Specialists + ~7 Operators (powered by Claude SDK + FastAPI)
2. **Next.js Frontend** - Dashboard, chat interface, data visualization
3. **Central Intelligence** - Marketing intelligence engine (Python + Claude SDK + Supabase) that transforms call transcripts into structured VOC (Voice of Customer) data feeding the marketing department

All communication between frontend and backend happens via FastAPI RESTful endpoints with WebSocket support for streaming agent responses. The database layer is fully abstracted via SQLAlchemy ORM with Repository pattern. Central Intelligence operates as a specialized agent that accesses Supabase directly via the Supabase Python client, while the web app consumes CI data through FastAPI endpoints.

### 3-Level Org Chart Architecture

The system is modeled as an organizational chart with three levels below Central Intelligence:

```
                    ┌────────────────────────┐
                    │ CENTRAL INTELLIGENCE (CI-CORE-00)│
                    │   CEO / Central AI       │
                    └─────────┬──────────────┘
                              │
              ┌───────────────┼───────────────┐
              │               │               │
    ┌─────────▼─────┐ ┌──────▼──────┐ ┌──────▼──────┐
    │ MARKETING DIR │ │  SALES DIR  │ │FULFILLMENT  │
    │ (CI-MKT-DIR) │ │(CI-SLS-DIR) │ │   DIR       │
    │  Level 3      │ │  Level 3    │ │(CI-FUL-DIR) │
    └───────┬───────┘ └──────┬──────┘ └──────┬──────┘
            │                │               │
    ┌───────▼───────┐       ...             ...
    │ SPECIALISTS   │
    │ Level 2       │
    ├── Email       │
    ├── Social Media│
    ├── Funnels     │
    ├── Ads         │
    ├── DMs         │
    └── Offers      │
            │
    ┌───────▼───────┐
    │ OPERATORS     │
    │ Level 1       │  ← Shared "floaters" across departments
    ├── Transcriber │
    ├── Stats Update│
    ├── ICP Gen     │
    └── Offer Gen   │
```

**Note**: Central Intelligence (CI) is a separate subsystem that feeds VOC data into the Marketing Director level. It's not part of the agent org chart but serves as a data producer for the system.

### Level Definitions

| Level | Role | Agent Pattern | Example |
| ----- | ---- | ------------- | ------- |
| **Central Intelligence** | CEO — cross-department intelligence, strategic decisions | BaseAgent + Anthropic client + tool_use | CI-CORE-00 |
| **Level 3: Director** | Department head — knows everything about their domain, coordinates specialists | DirectorAgent with sub-agent tools | CI-MKT-DIR |
| **Level 2: Specialist** | Domain expert — deep knowledge of one area, generates content/analysis | SpecialistAgent with domain tools + DB access | CI-MKT-01 (Email) |
| **Level 1: Operator** | Data feeder — single-purpose utility that ingests/transforms data | OperatorTask (Celery) or synchronous function | CI-OPS-TRANSCRIBE |

### How Levels Interact

```
Central Intelligence  ──[Tool Call]──→  Directors (3)
Directors  ──[Tool Call]──→  Specialists (per department)
Specialists ──[Tool Call]──→  Operators (shared)
Operators  ──[Repository Pattern]──→  Supabase
```

- **Central Intelligence → Directors**: "What's happening in Marketing this week?"
- **Director → Specialists**: Routes to Email Specialist, Social Specialist, etc.
- **Specialist → Operators**: "Update the email stats" or "Transcribe this call"
- **Operators → Data**: Write to/read from shared Supabase tables

### Why This Pattern

| Alternative | Why Not |
| ----------- | ------- |
| Central Intelligence calls all 20+ workers directly | Too many tools, slow token overhead, poor routing |
| Single monolithic agent | Unmanageable at 20+ agents; no separation of concerns |
| Direct API-to-API | HTTP overhead, harder debugging, no intelligent routing |
| 2-level only (no Directors) | Central Intelligence can't specialize per department — generic answers |

### Benefits

- **Org chart metaphor** — maps directly to how businesses think about teams
- **Directors reduce Central Intelligence complexity** — 3 tools instead of 20+
- **Each level is independently deployable and testable**
- **Operators are reusable** — Transcriber serves Sales, Fulfillment, and Marketing
- **Adding a new specialist** = 1 agent class + 1 tool registration on its Director
- **Department-level intelligence** — Directors provide focused domain knowledge

## 2. Tech Stack

### Python Agent Backend

| Component | Technology |
| --------- | ---------- |
| Framework | FastAPI 0.104+ (async HTTP + WebSockets) |
| AI Models | Claude Sonnet 4.5 (Central Intelligence), Claude Haiku 4.5 (Workers) via Anthropic SDK |
| Agent SDK | Anthropic Python SDK with tool_use support |
| Agent Classes | Custom Python classes (BaseAgent, DirectorAgent, SpecialistAgent) |
| Task Queue | Celery 5.3+ with Redis backend |
| ORM | SQLAlchemy 2.0+ with Alembic migrations |
| Database | Supabase (PostgreSQL 15+) with RLS policies |
| API Client | Custom FastAPI client with async/await |
| Transcription | OpenAI Whisper API (or local Whisper) |
| Server | Uvicorn with Gunicorn for production |
| Monitoring | Sentry + custom observability middleware |

### Next.js Frontend

| Component | Technology |
| --------- | ---------- |
| Framework | Next.js 14+ (App Router) |
| Styling | Tailwind CSS + shadcn/ui |
| Charts | Recharts |
| State Management | TanStack Query (React Query) |
| API Client | Custom async fetch wrapper with retries |
| Authentication | Supabase Auth (JWT + RLS) |
| Realtime | WebSocket client for agent streaming |

### Central Intelligence Stack

| Component | Technology | Purpose |
| --------- | ---------- | ------- |
| Backend | Python + FastAPI | API and processing layer |
| AI Layer | Claude SDK (Anthropic) | Agentic analysis and extraction |
| Database | Supabase (PostgreSQL) | 9-table VOC intelligence schema |
| DB Client | Supabase Python client | Database access (credentials in .env) |
| Transcript Source | Cockatoo (manual upload) | Current transcript ingestion |
| Transcript Source | Fireflies (future) | Automated transcript ingestion via webhook |

**Environment Variables**: `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `ANTHROPIC_API_KEY`

## 3. Python Agent Class Hierarchy

| Agent Class | Python Module | Level | Purpose |
| ----------- | ------------- | ----- | ------- |
| BaseAgent | `agents/base.py` | Core | Abstract agent with Anthropic SDK, tool registration, response parsing |
| CentralIntelligence | `agents/central_intelligence.py` | Executive | CEO reasoning with Director coordination |
| DirectorAgent | `agents/directors/base.py` | Level 3 | Department-head with specialist tools |
| MarketingDirector | `agents/directors/marketing.py` | Level 3 | Coordinates 6 marketing specialists |
| SalesDirector | `agents/directors/sales.py` | Level 3 | Coordinates 3 sales specialists |
| FulfillmentDirector | `agents/directors/fulfillment.py` | Level 3 | Coordinates 4 fulfillment specialists |
| SpecialistAgent | `agents/specialists/base.py` | Level 2 | Domain expert with DB + operator tools |
| EmailSpecialist | `agents/specialists/email.py` | Level 2 | Email strategy, campaign generation |
| SocialMediaSpecialist | `agents/specialists/social.py` | Level 2 | Social scripts, captions, calendar |
| OperatorTask | `tasks/operators.py` | Level 1 | Data ingestion, transformation (Celery/async) |
| TranscriberTask | `tasks/transcriber.py` | Level 1 | Audio-to-text conversion |

## 4. FastAPI Endpoints Architecture

### Authentication Layer

```python
# middleware/auth.py
class JWTAuthMiddleware:
    """Validate Supabase JWT tokens, extract user_id, check RLS policies"""

# middleware/hmac.py
class HMACSignatureMiddleware:
    """Validate HMAC-SHA256 signatures on requests"""

# middleware/rate_limit.py
class RateLimitMiddleware:
    """Per-endpoint rate limiting with Redis backing"""
```

### Core Routes

```python
# routes/central_intelligence.py
@app.post("/api/v1/central-intelligence/chat")
async def central_intelligence_chat(request: ChatRequest) -> ChatResponse:
    """Stream agent response from Central Intelligence"""
    agent = CentralIntelligence(db_session=db)
    async for chunk in agent.stream_response(request.message):
        yield chunk

# routes/directors.py
@app.post("/api/v1/directors/{director_id}/query")
async def director_query(director_id: str, request: DirectorRequest) -> DirectorResponse:
    """Query specific Director for department summary"""

# routes/specialists.py
@app.post("/api/v1/specialists/{spec_id}/analyze")
async def specialist_analyze(spec_id: str, request: AnalysisRequest) -> AnalysisResponse:
    """Trigger specialist analysis workflow"""
    task = SpecialistTask.delay(spec_id, request.dict())

# routes/operators.py
@app.post("/api/v1/transcribe")
async def transcribe_audio(file: UploadFile) -> TranscribeResponse:
    """Queue async transcription task"""
    task = TranscriberTask.delay(file.filename, file.read())

# routes/health.py
@app.get("/api/v1/health")
async def health_check() -> HealthResponse:
    """System health + worker status"""

# routes/auth.py
@app.post("/api/v1/auth/login")
async def login(credentials: LoginRequest) -> AuthResponse:
    """Validate user, return JWT from Supabase"""
```

### WebSocket for Agent Streaming

```python
# routes/ws.py
@app.websocket("/ws/agent-stream/{session_id}")
async def websocket_agent_stream(websocket: WebSocket, session_id: str):
    """Stream agent responses in real-time as they're generated"""
    await websocket.accept()
    agent = CentralIntelligence()
    async for chunk in agent.stream_response(message):
        await websocket.send_json({"type": "token", "data": chunk})
    await websocket.close()
```

## 5. Python Agent Implementation Templates

### 5.1 BaseAgent Template

```python
# agents/base.py
from anthropic import Anthropic
from typing import Iterator, Any
import json

class BaseAgent:
    """Abstract agent with Anthropic SDK integration"""

    def __init__(self, agent_id: str, name: str, model: str = "claude-sonnet-4-5-20250514"):
        self.agent_id = agent_id
        self.name = name
        self.model = model
        self.client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self.tools: list[dict] = []
        self.system_prompt = ""
        self.conversation_history: list[dict] = []

    def register_tool(self, name: str, description: str, input_schema: dict, handler_func):
        """Register a callable tool for this agent"""
        self.tools.append({
            "name": name,
            "description": description,
            "input_schema": input_schema,
            "_handler": handler_func
        })

    def stream_response(self, message: str) -> Iterator[str]:
        """Stream response tokens from Claude, handling tool_use"""
        self.conversation_history.append({"role": "user", "content": message})

        while True:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=2048,
                system=self.system_prompt,
                tools=self.tools,
                messages=self.conversation_history,
                stream=True
            )

            collected_text = ""
            tool_calls = []

            for event in response:
                if event.type == "content_block_delta":
                    if event.delta.type == "text_delta":
                        collected_text += event.delta.text
                        yield event.delta.text
                elif event.type == "content_block_start":
                    if event.content_block.type == "tool_use":
                        tool_calls.append({"id": event.content_block.id, "name": event.content_block.name})

            # If no tool calls, conversation is done
            if not tool_calls:
                self.conversation_history.append({"role": "assistant", "content": collected_text})
                break

            # Handle tool calls
            tool_results = []
            for tool_call in tool_calls:
                tool = next((t for t in self.tools if t["name"] == tool_call["name"]), None)
                if tool:
                    result = tool["_handler"]()  # Execute the tool
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_call["id"],
                        "content": json.dumps(result)
                    })

            self.conversation_history.append({"role": "assistant", "content": collected_text})
            self.conversation_history.append({"role": "user", "content": tool_results})

    async def execute(self, message: str) -> dict:
        """Non-streaming execution"""
        full_response = "".join(self.stream_response(message))
        return {"agent_id": self.agent_id, "response": full_response}
```

### 5.2 DirectorAgent Template

```python
# agents/directors/base.py
class DirectorAgent(BaseAgent):
    """Department head coordinating specialists"""

    def __init__(self, director_id: str, name: str, db_session):
        super().__init__(director_id, name, model="claude-sonnet-4-5-20250514")
        self.db = db_session
        self.specialists: dict[str, SpecialistAgent] = {}
        self.system_prompt = f"""
You are the {name}, CEO of your department in the Central Intelligence automation system.
Your role is to coordinate your specialists and provide department-level insights.
Always delegate detailed work to appropriate specialists rather than doing it yourself.
"""
        self._register_specialist_tools()
        self._register_data_tools()

    def _register_specialist_tools(self):
        """Register sub-agents as tools"""
        for spec_id, specialist in self.specialists.items():
            self.register_tool(
                name=f"call_{specialist.name}",
                description=f"Request analysis from {specialist.name}",
                input_schema={"type": "object", "properties": {"query": {"type": "string"}}},
                handler_func=lambda q=None: specialist.execute(q or "analyze").get("response")
            )

    def _register_data_tools(self):
        """Register read-only data access"""
        self.register_tool(
            name="query_shared_intelligence",
            description="Query cross-domain intelligence (goals, wins, pain_points, etc)",
            input_schema={"type": "object", "properties": {"table": {"type": "string"}, "filters": {"type": "object"}}},
            handler_func=self._fetch_shared_data
        )

    def _fetch_shared_data(self, table: str, filters: dict = None) -> list:
        """Fetch from shared intelligence tables"""
        repo = IntelligenceRepository(self.db)
        return repo.find_by_filters(table, filters or {})
```

### 5.3 SpecialistAgent Template

```python
# agents/specialists/base.py
class SpecialistAgent(BaseAgent):
    """Domain expert with deep knowledge of one area"""

    def __init__(self, spec_id: str, name: str, domain: str, db_session):
        super().__init__(spec_id, name, model="claude-haiku-4-5-20251001")
        self.domain = domain
        self.db = db_session
        self.system_prompt = f"""
You are {name}, a specialist in {domain} within the Central Intelligence automation system.
You have access to cross-domain intelligence (all specialists' data) plus domain-specific expertise.
Your role is to generate actionable insights, content, and analysis within your domain.
Format all outputs as structured JSON matching the expected response schema.
"""
        self._register_db_tools()
        self._register_operator_tools()

    def _register_db_tools(self):
        """Register database read/write access via Repository pattern"""
        self.register_tool(
            name="query_shared_tables",
            description="Query shared intelligence tables: goals, wins, pain_points, objections, content_ideas, icp, offers",
            input_schema={"type": "object", "properties": {"table": {"type": "string"}}},
            handler_func=lambda table: IntelligenceRepository(self.db).find_all(table)
        )
        self.register_tool(
            name="store_result",
            description=f"Store analysis result to {self.domain} table",
            input_schema={"type": "object", "properties": {"data": {"type": "object"}}},
            handler_func=lambda data: AnalysisRepository(self.db).create(self.spec_id, data)
        )

    def _register_operator_tools(self):
        """Register operator tasks as tools"""
        self.register_tool(
            name="queue_transcription",
            description="Queue an async transcription task",
            input_schema={"type": "object", "properties": {"video_url": {"type": "string"}}},
            handler_func=self._queue_transcription_task
        )

    def _queue_transcription_task(self, video_url: str):
        """Delegate to Celery task"""
        task = TranscriberTask.delay(video_url)
        return {"task_id": task.id, "status": "queued"}
```

### 5.4 OperatorTask Template

```python
# tasks/operators.py
from celery import shared_task
from sqlalchemy.orm import Session

@shared_task(bind=True, max_retries=3)
def transcriber_task(self, video_url: str) -> dict:
    """Transcribe audio from video using Whisper API"""
    try:
        # Download or process video
        audio = download_audio(video_url)

        # Call Whisper API
        transcript = transcribe_with_whisper(audio)

        # Store result to database
        db = SessionLocal()
        repo = TranscriptRepository(db)
        result = repo.create({
            "url": video_url,
            "transcript": transcript,
            "status": "completed"
        })
        db.close()

        return {"transcript_id": result.id, "transcript": transcript}
    except Exception as exc:
        # Exponential backoff retry
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)
```

## 6. Database Layer: Supabase + SQLAlchemy

### Repository Pattern for Database Abstraction

```python
# repositories/base.py
class BaseRepository(Generic[T]):
    """Generic repository for database-agnostic CRUD"""

    def __init__(self, session: Session, model_class: Type[T]):
        self.session = session
        self.model_class = model_class

    def create(self, data: dict) -> T:
        obj = self.model_class(**data)
        self.session.add(obj)
        self.session.commit()
        self.session.refresh(obj)
        return obj

    def find_by_id(self, id: str) -> T:
        return self.session.query(self.model_class).filter(
            self.model_class.id == id,
            self.model_class.deleted_at == None
        ).first()

    def find_all(self, skip: int = 0, limit: int = 100) -> list[T]:
        return self.session.query(self.model_class).filter(
            self.model_class.deleted_at == None
        ).offset(skip).limit(limit).all()

    def update(self, id: str, data: dict) -> T:
        obj = self.find_by_id(id)
        for key, value in data.items():
            setattr(obj, key, value)
        self.session.commit()
        self.session.refresh(obj)
        return obj

    def soft_delete(self, id: str):
        obj = self.find_by_id(id)
        obj.deleted_at = datetime.utcnow()
        self.session.commit()

# repositories/intelligence.py
class IntelligenceRepository(BaseRepository):
    """Query shared intelligence tables"""

    def find_by_filters(self, table_name: str, filters: dict) -> list:
        model = self._get_model_by_table(table_name)
        query = self.session.query(model).filter(model.deleted_at == None)
        for key, value in filters.items():
            if hasattr(model, key):
                query = query.filter(getattr(model, key) == value)
        return query.all()
```

### SQLAlchemy Models

```python
# models/intelligence.py
from sqlalchemy import Column, String, Text, DateTime, Boolean
from sqlalchemy.sql import func

class Goal(Base):
    __tablename__ = "goals"
    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    description = Column(Text)
    department = Column(String)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime, nullable=True)

class ContentIdea(Base):
    __tablename__ = "content_ideas"
    id = Column(String, primary_key=True)
    title = Column(String)
    content = Column(Text)
    status = Column(String, default="new")  # new | used | archived
    created_by = Column(String)  # specialist_id
    created_at = Column(DateTime, server_default=func.now())
    deleted_at = Column(DateTime, nullable=True)

class CallTranscript(Base):
    __tablename__ = "call_transcripts"
    id = Column(String, primary_key=True)
    transcript_text = Column(Text)
    transcript_source = Column(String)  # cockatoo | fireflies
    created_at = Column(DateTime, server_default=func.now())
    deleted_at = Column(DateTime, nullable=True)
```

## 7. Workflow Templates (by Level)

### 7.1 Director Template (Level 3)

Directors are Python agents that coordinate their department's specialists via tool_use.

```python
# agents/directors/marketing.py
class MarketingDirector(DirectorAgent):
    def __init__(self, db_session):
        super().__init__(
            director_id="CI-MKT-DIR",
            name="Marketing Director",
            db_session=db_session
        )

        # Initialize specialists
        self.specialists = {
            "email": EmailSpecialist(db_session),
            "social": SocialMediaSpecialist(db_session),
            "funnels": FunnelsSpecialist(db_session),
            "ads": AdsSpecialist(db_session),
            "dm": DMSpecialist(db_session),
            "offers": OfferSpecialist(db_session),
        }

        self.system_prompt = """
You are the Marketing Director of Central Intelligence. You coordinate 6 specialists:
- Email Specialist: Email campaigns, sequences, templates
- Social Media Specialist: Social content, scheduling, captions
- Funnels Specialist: Landing page optimization, conversion analysis
- Ads Specialist: Ad copy, audience targeting, performance
- DM Specialist: Direct message templates and strategy
- Offer Specialist: Pricing, positioning, special offers

You have read access to all shared intelligence tables (goals, wins, pain_points, objections, content_ideas, icp, offers).
You coordinate specialist requests and synthesize department-wide insights.
Always route specific work to appropriate specialists.
"""
        self._register_specialist_tools()
        self._register_data_tools()
```

**Director Workflow**:
1. Receive query via FastAPI endpoint
2. Validate input (operation type, context)
3. Initialize agent with system prompt
4. Call Claude with tool_use enabled
5. If tool called: execute specialist agent or query shared data
6. Aggregate responses
7. Return structured JSON response

**Example Request/Response**:
```json
Request:
{
  "operation": "summary",
  "context": "What's the marketing status this week?"
}

Response:
{
  "director_id": "CI-MKT-DIR",
  "director_name": "Marketing Director",
  "operation": "summary",
  "summary": "Email campaigns up 15%, social engagement down 8%...",
  "specialist_insights": {
    "email": "3 new campaigns drafted",
    "social": "Posted 12 pieces, engagement tracking...",
    "offers": "Q2 positioning ready for review"
  },
  "recommendations": ["Boost social organic reach", "Test email variants"]
}
```

### 7.2 Specialist Template (Level 2)

Specialists are domain-expert agents with deep knowledge of one area.

```python
# agents/specialists/email.py
class EmailSpecialist(SpecialistAgent):
    def __init__(self, db_session):
        super().__init__(
            spec_id="CI-MKT-01",
            name="Email Specialist",
            domain="Email Marketing",
            db_session=db_session
        )

        self.system_prompt = """
You are the Email Specialist in Central Intelligence's Marketing department.
You design email campaigns, sequences, and templates based on customer insights.
You have access to:
- Shared intelligence: goals, wins, pain_points, objections, content_ideas, icp, offers
- Email-specific stats: open rates, click rates, unsubscribe rates
- Frameworks: campaign templates, subject line patterns, CTAs

Supported operations:
1. "analyze" - Analyze email performance and suggest improvements
2. "generate" - Generate new email copy or campaign
3. "optimize" - Optimize existing email for higher engagement

Always output structured JSON with subject, preview_text, body_html, cta_text.
"""

        # Register data tools
        self.register_tool(
            name="get_email_stats",
            description="Fetch email performance metrics (open rate, click rate, etc)",
            input_schema={},
            handler_func=self._get_email_stats
        )

        self.register_tool(
            name="save_email_draft",
            description="Save generated email to database for review",
            input_schema={"type": "object", "properties": {"email_data": {"type": "object"}}},
            handler_func=self._save_email_draft
        )

    def _get_email_stats(self) -> dict:
        repo = EmailStatsRepository(self.db)
        return {
            "avg_open_rate": 0.25,
            "avg_click_rate": 0.08,
            "recent_campaigns": repo.find_all(limit=5)
        }

    def _save_email_draft(self, email_data: dict) -> dict:
        repo = EmailDraftRepository(self.db)
        draft = repo.create({
            "subject": email_data.get("subject"),
            "body_html": email_data.get("body_html"),
            "cta_text": email_data.get("cta_text"),
            "status": "draft"
        })
        return {"draft_id": draft.id, "status": "saved"}
```

**Specialist Workflow**:
1. Receive operation (analyze | suggest | generate | query | update)
2. Validate operation matches handler
3. Initialize agent with domain-specific prompt
4. Call Claude with tool_use
5. Execute tools (DB queries, operators)
6. Store results via Repository
7. Return structured response with insights

### 7.3 Operator Template (Level 1)

Operators are lightweight, single-purpose tasks for data ingestion/transformation.

```python
# tasks/operators.py
@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def transcriber_task(self, video_url: str) -> dict:
    """
    Transcribe audio using Whisper API
    Callable from any specialist or director
    """
    try:
        # Download audio from URL
        audio_path = download_video(video_url)

        # Transcribe
        client = Anthropic()
        with open(audio_path, "rb") as f:
            transcript = transcribe_whisper(f)  # Via OpenAI Whisper API

        # Store to database
        db = SessionLocal()
        transcript_repo = TranscriptRepository(db)
        result = transcript_repo.create({
            "transcript_text": transcript,
            "transcript_source": "manual_upload",
            "video_url": video_url,
            "status": "completed"
        })
        db.close()

        return {
            "transcript_id": result.id,
            "status": "completed",
            "word_count": len(transcript.split()),
            "duration_seconds": get_video_duration(audio_path)
        }
    except Exception as exc:
        # Retry with exponential backoff (2s, 4s, 8s)
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)
```

**Operator Tasks**:
- `TranscriberTask`: Convert video/audio to text
- `StatsUpdaterTask`: Ingest email/social/funnel/ads metrics
- `ICPGeneratorTask`: Build ideal customer profile from insights
- `OfferGeneratorTask`: Create/optimize offers

**Standardized Input Contract**:
```json
{
  "operation": "analyze | suggest | generate | query | update",
  "context": "free text describing what the user wants",
  "data": {},
  "filters": {}
}
```

**Standardized Output Contract**:
```json
{
  "worker_id": "CI-MKT-01",
  "worker_name": "Email Specialist",
  "level": "specialist",
  "operation": "generate",
  "result": {},
  "content_ideas": [],
  "pain_points": [],
  "objections": [],
  "summary": "Human-readable summary"
}
```

## 8. Central Intelligence Design

### Two Access Modes

1. **HTTP API** - RESTful endpoint for structured JSON requests
2. **WebSocket Streaming** - Real-time token streaming for chat interface

### Connected Tools (3 Directors + Data Tables)

Central Intelligence now connects to **3 Directors** instead of 12+ individual workers:

- **CI-MKT-DIR** — Marketing Director (coordinates 6 marketing specialists)
- **CI-SLS-DIR** — Sales Director (coordinates 3 sales specialists)
- **CI-FUL-DIR** — Fulfillment Director (coordinates 4 fulfillment specialists)
- Repository layer for cross-domain data (direct read when needed)

This reduces Central Intelligence's tool count from 12+ to ~5, improving routing accuracy and reducing token overhead.

### System Prompt Requirements

The Central Intelligence system prompt must define:
1. Identity and persona (CEO of the Central Intelligence)
2. Knowledge of the 3-level org chart (Directors → Specialists → Operators)
3. When to call which Director (department routing)
4. When to query data directly (cross-department questions)
5. Dashboard formatting instructions (structured JSON for charts)
6. Business optimization framework (prioritization logic)

```python
# agents/central_intelligence.py
class CentralIntelligence(BaseAgent):
    SYSTEM_PROMPT = """
You are Central Intelligence, the CEO of Central Intelligence automation. Your role is to provide cross-department intelligence and strategic insights.

You have access to 3 Department Directors:
1. Marketing Director (CI-MKT-DIR) - Email, social, funnels, ads, DMs, offers
2. Sales Director (CI-SLS-DIR) - Leads, appointments, sales calls
3. Fulfillment Director (CI-FUL-DIR) - Members, coaching, accountability, tech support

Always delegate department-specific requests to appropriate Directors.
Use cross-domain data queries for strategic questions spanning multiple departments.

Format responses as structured JSON with:
- summary: High-level insight (2-3 sentences)
- department_insights: {director_id: summary} for each director queried
- recommendations: List of actionable next steps
- metrics: Key numbers/trends
"""

    def __init__(self, db_session):
        super().__init__(
            agent_id="CI-CORE-00",
            name="Central Intelligence",
            model="claude-sonnet-4-5-20250514"
        )
        self.db = db_session
        self.directors = {
            "marketing": MarketingDirector(db_session),
            "sales": SalesDirector(db_session),
            "fulfillment": FulfillmentDirector(db_session),
        }

        # Register director tools
        for dept, director in self.directors.items():
            self.register_tool(
                name=f"query_{dept}_director",
                description=f"Request insights from {director.name}",
                input_schema={"type": "object", "properties": {"query": {"type": "string"}}},
                handler_func=lambda q=None: director.execute(q or "summary").get("response")
            )

        # Register cross-domain data queries
        self.register_tool(
            name="query_cross_domain_data",
            description="Query shared intelligence across all departments",
            input_schema={
                "type": "object",
                "properties": {
                    "tables": {"type": "array", "items": {"type": "string"}},
                    "filters": {"type": "object"}
                }
            },
            handler_func=self._query_cross_domain
        )

    def _query_cross_domain(self, tables: list[str], filters: dict) -> dict:
        repo = IntelligenceRepository(self.db)
        results = {}
        for table in tables:
            results[table] = repo.find_by_filters(table, filters)
        return results
```

## 9. Cross-Domain Data Flow

### Shared Intelligence Tables

All specialists across all departments have read access to these shared tables:

```
┌─────────────────────────────────────────────────────────────┐
│                    SHARED INTELLIGENCE POOL                  │
│                                                              │
│  goals ─ wins ─ pain_points ─ objections ─ content_ideas    │
│                    icp ─ offers ─ comments                   │
│                                                              │
│  Written by: Operators + Sales/Fulfillment Specialists       │
│  Read by: ALL Specialists (Marketing, Sales, Fulfillment)    │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow Diagram

```
Central Intelligence (External Agent System):
  Transcript Processor Agent ──→ calls + insights + content_ideas
  Market Signal Aggregation ──→ market_signals

Operators (Level 1 - Celery Tasks):
  TranscriberTask ──→ call_transcripts
  StatsUpdaterTasks ──→ domain-specific stats
  ICPGeneratorTask ──→ icp table
  OfferGeneratorTask ──→ offers table

Sales Specialists (Level 2):
  SalesCallAnalyzer ──→ pain_points + objections + content_ideas
  LeadsSpecialist ──→ leads database

Fulfillment Specialists (Level 2):
  CoachingAnalyzer ──→ wins + pain_points + content_ideas + goals
  AccountabilityAnalyzer ──→ goals + wins
  TechSOSTracker ──→ tech_sos_issues

Marketing Specialists (Level 2):
  EmailSpecialist ←── reads ALL shared tables ──→ emails, calendar
  SocialMediaSpecialist ←── reads ALL shared tables ──→ scripts, captions
  FunnelsSpecialist ←── reads ALL shared tables ──→ bottlenecks
  AdsSpecialist ←── reads ALL shared tables ──→ ad copy
  DMSpecialist ←── reads ALL shared tables ──→ DM templates
  OfferSpecialist ←── reads ALL shared tables ──→ offers

Directors (Level 3):
  MarketingDirector ←── aggregates from 6 marketing specialists
  SalesDirector ←── aggregates from 3 sales specialists
  FulfillmentDirector ←── aggregates from 4 fulfillment specialists

Central Intelligence:
  ←── queries Directors for department summaries
  ←── reads shared tables directly for cross-department analysis
  ←── accesses CI's market_signals for trend data
```

**Note**: CI's data flow is ONE-WAY: CI produces insights → Central Intelligence consumes them. CI operates independently as a specialized agent system.

## 10. Authentication Model

### Two-Layer Architecture

The system uses two distinct authentication layers:

```
Layer 1: User → App (Supabase Auth)
┌──────────┐   email/password   ┌──────────────┐   JWT session   ┌──────────────┐
│  Browser  │ ──────────────────→│ Supabase Auth│ ──────────────→│  Next.js App  │
└──────────┘                    └──────────────┘                 └──────────────┘

Layer 2: App → FastAPI (JWT + HMAC Signing)
┌──────────────┐   Authorization: Bearer + X-Signature-256   ┌──────────────┐
│  Next.js App  │ ──────────────────────────────────────────→│  FastAPI API  │
└──────────────┘                                             └──────────────┘
```

**Layer 1 — User Authentication**:
- Supabase Auth with JWT strategy
- Session stored in HttpOnly cookie (30-min sliding window, 7-day with "Remember me")
- User credentials validated against Supabase `auth.users` table
- Account lockout: 5 failed attempts → 15-minute lock
- Roles: `owner` (Greg), `admin`, `team`, `viewer`

**Layer 2 — API Authentication**:
- Every FastAPI request carries `Authorization: Bearer <JWT>` header
- HMAC-SHA256 signature in `X-Signature-256` header (signs request body with shared secret)
- `X-User-Id` header for audit trail
- `X-Request-Id` header for request correlation
- Replay protection via timestamp validation (5-minute window)

### Auth Endpoints

| Endpoint | Method | Purpose |
| -------- | ------ | ------- |
| `/api/v1/auth/login` | POST | Validate credentials via Supabase, return JWT |
| `/api/v1/auth/logout` | POST | Revoke session |
| `/api/v1/auth/refresh` | POST | Refresh JWT token |
| `/api/v1/auth/me` | GET | Return current user profile from session |

## 11. Error Handling Strategy

### Three-Layer Error Handling

**FastAPI Layer**:
- Exception handlers for common errors (validation, auth, database)
- Structured error responses with correlation IDs
- Logging to Sentry for monitoring

```python
# middleware/error_handler.py
@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    return JSONResponse(
        status_code=400,
        content={
            "error": {"code": "VALIDATION_ERROR", "message": str(exc)},
            "request_id": request.state.request_id
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unexpected error: {exc}", extra={"request_id": request.state.request_id})
    sentry_sdk.capture_exception(exc)
    return JSONResponse(
        status_code=500,
        content={
            "error": {"code": "INTERNAL_ERROR", "message": "An unexpected error occurred"},
            "request_id": request.state.request_id
        }
    )
```

**Agent Layer**:
- BaseAgent catches Anthropic API errors
- Tool execution failures logged with context
- Graceful degradation (partial responses if some tools fail)

```python
# agents/base.py
def stream_response(self, message: str) -> Iterator[str]:
    try:
        response = self.client.messages.create(...)
    except APIError as e:
        logger.error(f"Anthropic API error: {e}", extra={"agent_id": self.agent_id})
        yield f"Error: {e.message}"
    except RateLimitError:
        logger.warning(f"Rate limited", extra={"agent_id": self.agent_id})
        yield "Rate limited. Please try again in a moment."
```

**Task Queue Layer** (Celery):
- Task errors logged to database
- Exponential backoff retry on failure
- Dead letter queue for persistent failures

```python
# tasks/base.py
@shared_task(bind=True, max_retries=3)
def base_task(self, *args, **kwargs):
    try:
        return execute(*args, **kwargs)
    except Exception as exc:
        # Log to database
        ErrorRepository().create({
            "task_id": self.request.id,
            "error": str(exc),
            "retry_count": self.request.retries
        })
        # Exponential backoff
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)
```

### Standardized Error Response

```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR | AUTH_ERROR | NOT_FOUND | RATE_LIMIT | INTERNAL_ERROR",
    "message": "Human-readable error description",
    "details": {}
  },
  "meta": {
    "request_id": "req-abc-123",
    "timestamp": "2026-03-12T10:30:00Z"
  }
}
```

## 12. Security Considerations

- **Two-layer authentication**: Supabase JWT (user→app) + HMAC-signed Bearer tokens (app→FastAPI)
- **No direct database access** from the web app — all access through FastAPI endpoints
- **Environment variables** for all credentials (ANTHROPIC_API_KEY, SUPABASE_SERVICE_ROLE_KEY, HMAC_SECRET)
- **CORS configuration** restricted to the web app origin
- **Rate limiting** on AI-powered endpoints (to control API costs)
- **HMAC-SHA256 webhook signing** prevents unauthorized API calls
- **Soft delete** on all mutable tables — data is recoverable
- **Audit logging** on all CRUD operations (user, action, resource, timestamp)
- **Idempotency keys** prevent duplicate form submissions
- **Token rotation mechanism** — JWT can be revoked without downtime
- **Account lockout** — 5 failed login attempts triggers 15-minute lock
- **Row-Level Security (RLS)** on Supabase to enforce data boundaries

## 13. Soft Delete Strategy

All mutable tables include `deleted_at` (nullable datetime) and `updated_at` fields:

- **Delete operation**: Sets `deleted_at = NOW()` instead of removing the row
- **All queries**: Include `WHERE deleted_at IS NULL` filter by default (enforced in Repository)
- **Cascade awareness**: When a parent record is soft-deleted, child records are flagged
- **Permanent purge**: Scheduled Celery task removes records where `deleted_at < NOW() - 90 days`
- **Restore**: Admin can set `deleted_at = NULL` to recover accidentally deleted records

```python
# repositories/base.py
def find_all(self, skip: int = 0, limit: int = 100) -> list[T]:
    return self.session.query(self.model_class).filter(
        self.model_class.deleted_at == None  # Always filter soft-deletes
    ).offset(skip).limit(limit).all()

@shared_task
def purge_soft_deleted_records():
    """Permanently delete records soft-deleted > 90 days ago"""
    cutoff = datetime.utcnow() - timedelta(days=90)
    session = SessionLocal()
    for model in [Goal, ContentIdea, CallTranscript, ...]:
        session.query(model).filter(model.deleted_at < cutoff).delete()
    session.commit()
```

## 14. Circuit Breaker Pattern

Protects against cascading failures when external APIs (Anthropic, Supabase) are down:

```
States: CLOSED → OPEN → HALF_OPEN → CLOSED

CLOSED:   Normal operation, requests flow through
OPEN:     After 5 consecutive failures, stop sending requests for 60s
HALF_OPEN: After cooldown, allow 1 test request through
          - If success → CLOSED (resume normal)
          - If failure → OPEN (restart cooldown)
```

Implemented as a decorator on agent methods:

```python
# middleware/circuit_breaker.py
class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "CLOSED"

    def call(self, func, *args, **kwargs):
        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.timeout:
                self.state = "HALF_OPEN"
            else:
                raise CircuitBreakerOpenError()

        try:
            result = func(*args, **kwargs)
            self.failure_count = 0
            self.state = "CLOSED"
            return result
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()
            if self.failure_count >= self.failure_threshold:
                self.state = "OPEN"
            raise
```

---

# ENHANCED SECTIONS

## 15. Security Hardening Specifications

### HMAC-SHA256 Implementation Spec

**Request Signing Flow**:

1. **Header Generation** (Next.js Client):
   - Timestamp: `X-Timestamp = ISO8601 now (e.g., "2026-03-12T10:30:00.000Z")`
   - Nonce: `X-Nonce = random UUID (prevents replay + duplicate detection)`
   - Request ID: `X-Request-Id = UUID (request correlation across logs)`
   - Message to sign: `${method}|${path}|${timestamp}|${body_json_stringified}`
   - Signature: `X-Signature-256 = HMAC-SHA256(message, HMAC_SECRET)`

2. **Header Format** (Request):
   ```
   Authorization: Bearer <JWT>
   X-Timestamp: 2026-03-12T10:30:00.000Z
   X-Nonce: 550e8400-e29b-41d4-a716-446655440000
   X-Request-Id: req-abc-123-def-456
   X-Signature-256: a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0
   X-User-Id: user_123 (audit trail)
   Content-Type: application/json
   ```

3. **Replay Protection**:
   - Accept only timestamps within 5-minute window (configurable)
   - Track all received nonces in `idempotency_keys` table
   - Reject duplicate nonces (exact message already processed)
   - Error response: `409 Conflict` with message "Request already processed"

4. **Validation Logic** (FastAPI middleware):
   ```python
   async def validate_request_signature(request: Request):
       timestamp = request.headers.get("X-Timestamp")
       nonce = request.headers.get("X-Nonce")
       signature = request.headers.get("X-Signature-256")

       # Check timestamp within window
       ts = datetime.fromisoformat(timestamp)
       if abs((datetime.utcnow() - ts).total_seconds()) > 300:
           return 401, "Timestamp outside valid window"

       # Check nonce not seen before
       if repository.find_nonce(nonce):
           return 409, "Request already processed"

       # Verify signature
       body = await request.body()
       expected_sig = hmac.new(
           HMAC_SECRET.encode(),
           f"{request.method}|{request.url.path}|{timestamp}|{body.decode()}".encode(),
           hashlib.sha256
       ).hexdigest()

       if signature != expected_sig:
           return 401, "Invalid signature"

       # Store nonce
       repository.create_nonce(nonce, timestamp)
       return 200, "OK"
   ```

**Failure Scenarios**:
- Missing signature header → 401
- Invalid signature → 401
- Stale timestamp → 401
- Replay attempt (duplicate nonce) → 409
- Tampered body → 401 (signatures won't match)

---

### Session Management: JWT Token Lifecycle

**Token Structure** (Supabase JWT):
```json
{
  "sub": "user_123",
  "email": "greg@example.com",
  "role": "owner",
  "aud": "authenticated",
  "iat": 1710240600,
  "exp": 1710327000,
  "refresh_exp": 1712572200
}
```

**Lifecycle**:

1. **Initial Login**:
   - User submits email/password at `/auth/login`
   - Validate against Supabase Auth (`supabase.auth.signInWithPassword`)
   - Supabase returns JWT + refresh token
   - Set HttpOnly cookie `next-auth.session-token = JWT`
   - Return user profile + role

2. **Sliding Window** (30-min session):
   - Every request resets the 30-min timer
   - Session extends automatically if user is active
   - No additional "refresh token" flow needed for sliding window
   - Cookie rotated on each response

3. **"Remember Me"** (7-day):
   - If user checks "Remember me", set longer cookie lifespan
   - Session extends to 7 days from last activity
   - Still validates user exists + role hasn't changed
   - User can revoke "Remember me" sessions from account settings

4. **Concurrent Sessions**:
   - **Limit**: Max 3 concurrent sessions per user (configurable)
   - **Conflict Resolution**: If 4th login attempts, oldest session revoked + user notified
   - **Tracking**: Store active session tokens in `user_sessions` table with IP + user agent
   - **Logout**: Invalidate specific session token or all sessions (device logout vs full logout)

5. **Token Refresh** (explicit refresh endpoint):
   - POST `/auth/refresh` with current JWT
   - FastAPI validates JWT signature
   - Issues new JWT from Supabase with fresh expiry
   - Return new token to client (update cookie)

6. **Session Validation** (GET /auth/me):
   - Validates JWT signature matches Supabase public key
   - Checks user still exists in Supabase `auth.users`
   - Checks user not soft-deleted in `public.users`
   - Checks user role hasn't changed since token issued
   - Returns 401 if any check fails → client redirects to /login

**Expiry Handling**:
- Before expiry (within 5 min): NextAuth auto-refreshes in background
- At expiry: Client-side, redirect to /login + clear cookie
- Stale cookie: GET /auth/me returns 401 → login page

---

### Input Validation: Per-Endpoint Rules

**Global Validation Rules** (apply to all endpoints):
```
1. All request bodies must be valid JSON
2. All string fields: max length 10,000 chars
3. All arrays: max 1,000 items
4. All numeric fields: within reasonable ranges (no infinity, no NaN)
5. All dates: valid ISO8601 format
6. All emails: RFC 5322 compliant
7. All URLs: valid HTTP/HTTPS only (no file://, javascript:, etc.)
```

**AI Prompt Injection Prevention**:

When accepting user input destined for AI prompts (context, data, filters):
1. **Whitelist approach**: Define allowed field names
2. **Escaping**: Remove control characters (null bytes, form feeds)
3. **Prompt wrapping**: User input treated as DATA, not instructions

```python
def sanitize_for_prompt(user_input: str) -> str:
    """Remove control characters and potential injection vectors"""
    return user_input.replace('\x00', '').replace('\f', '').replace('\x1f', ' ')

# In agent prompt:
user_context = sanitize_for_prompt(request.context)
system_prompt = f"User asked: {user_context}\nRespond helpfully."
```

**Per-Endpoint Rules**:

| Endpoint | Field | Type | Rules | Example |
| -------- | ----- | ---- | ----- | ------- |
| POST `/api/v1/central-intelligence/chat` | `message` | string | 1-2000 chars, no null bytes | "What's the marketing status?" |
| POST `/api/v1/transcribe` | `video_url` | string | Valid HTTPS URL only, domain whitelist | "https://example.com/video.mp4" |
| POST `/api/v1/sales-calls/analyze` | `transcript` | string | 100-100,000 chars, check for prompt injection | [call transcript] |
| POST `/api/v1/leads` | `email` | string | Valid RFC5322 email | "john@example.com" |
| POST `/api/v1/leads` | `source` | enum | "webinar" \| "vsl" \| "opt-in" only | "webinar" |
| GET `/api/v1/leads?date_from=...` | `date_from` | ISO8601 | Within last 2 years | "2024-03-12" |
| PUT `/api/v1/content-ideas/:id` | `status` | enum | "new" \| "used" \| "archived" only | "used" |
| POST `/api/v1/marketing/offers/:id` | `price` | number | 0 < price <= 1,000,000 | 297 |

---

### Data Classification Matrix

**PII (Personally Identifiable Information)** — Highest sensitivity:
- User email, name, phone, address
- Member personal info (goals, coaching notes)
- Conversation transcripts (contain personal context)
- Payment information (never stored; marked as PII if present)
- **Access Control**: Owner + Admin only
- **Audit**: All access logged
- **Encryption**: At rest (database) + in transit (HTTPS)
- **Soft Delete**: 90-day retention after delete

**Business-Sensitive** — Medium sensitivity:
- Sales metrics, revenue data, funnel rates
- Client pain points, objections, wins
- Offer pricing, positioning strategy
- Marketing performance data
- **Access Control**: Owner + Admin + Team (role-based)
- **Audit**: All modification logged
- **Encryption**: At rest (database) + in transit (HTTPS)
- **Soft Delete**: 90-day retention

**Public / Marketing** — Low sensitivity:
- Published content ideas, scripts
- Archived case studies, testimonials
- Public-facing offer descriptions
- Aggregate statistics (no identifiable data)
- **Access Control**: Owner + Admin + Team + Viewer
- **Audit**: Modification logged
- **Encryption**: In transit (HTTPS)
- **Soft Delete**: 30-day retention (or permanent)

**System Metadata** — For operations:
- Workflow execution logs, error logs
- API request logs (timestamps, user IDs, not bodies)
- Performance metrics
- System health data
- **Access Control**: Owner + Admin only
- **Audit**: N/A (operational logs are audit trail)
- **Encryption**: In transit (HTTPS)
- **Retention**: 30-day default, configurable

**Access Control Matrix**:

| Resource | Owner | Admin | Team | Viewer | Anonymous |
| -------- | ----- | ----- | ---- | ------ | --------- |
| PII (members, emails) | RW | R | - | - | - |
| Business-Sensitive (metrics, offers) | RW | RW | R | R | - |
| Public Content (scripts, ideas) | RW | RW | RW | R | - |
| System Logs (errors, API) | R | R | - | - | - |
| User Management | RW | RW | - | - | - |
| Audit Trail | R | R | - | - | - |

---

### Webhook Endpoint Protection: Rate Limiting

**Rate Limit Strategy**:

1. **By Endpoint** (cost-aware):
   ```
   POST /api/v1/central-intelligence/chat → 10 req/min (AI heavy)
   POST /api/v1/transcribe → 5 req/min (file heavy)
   GET /api/v1/leads → 100 req/min (data fetch)
   POST /api/v1/leads → 20 req/min (write heavy)
   GET /api/v1/health → unlimited (internal only)
   ```

2. **By User** (fairness):
   - Authenticated user: Subject to per-endpoint limits
   - Unauthenticated: Blocked entirely (return 401)
   - Admin user: 2x limits (configurable)

3. **By IP** (abuse prevention):
   - Track failed auth attempts per IP
   - After 5 failed attempts: 15-min lockout for that IP
   - After 50 failed attempts in 1 hour: 1-hour lockout
   - Whitelist internal IPs (office, VPN)

4. **Implementation** (Redis-backed):
   ```python
   # middleware/rate_limit.py
   class RateLimitMiddleware:
       def __init__(self, redis_client):
           self.redis = redis_client

       async def __call__(self, request: Request, call_next):
           user_id = request.state.user_id
           endpoint = request.url.path
           key = f"rate_limit:{user_id}:{endpoint}"

           count = self.redis.incr(key)
           self.redis.expire(key, 60)

           limit = self.get_endpoint_limit(endpoint)
           remaining = max(0, limit - count)

           response = await call_next(request)
           response.headers["X-RateLimit-Limit"] = str(limit)
           response.headers["X-RateLimit-Remaining"] = str(remaining)
           response.headers["X-RateLimit-Reset"] = str(int(time.time()) + 60)

           if count > limit:
               return JSONResponse(status_code=429, content={
                   "error": "TOO_MANY_REQUESTS",
                   "message": f"Rate limit exceeded: {limit} req/min",
                   "retry_after": 60
               })

           return response
   ```

5. **Exceeded Response** (429 Too Many Requests):
   ```json
   {
     "error": "TOO_MANY_REQUESTS",
     "message": "Rate limit exceeded: 10 req/min",
     "retry_after": 45
   }
   ```

**IP Allowlisting** (for trusted integrations):
- Whitelist option: Only allow requests from specific IPs (e.g., office, client VPN)
- Configured in `webhook_access_control` table with IP ranges
- Skip rate limiting for whitelisted IPs
- Admin dashboard to manage whitelist

---

## 16. Monitoring & Observability

### Health Check Endpoints Per Agent

**GET /api/v1/health** (global system health):
```json
{
  "status": "healthy" | "degraded" | "unhealthy",
  "timestamp": "2026-03-12T10:30:00Z",
  "services": {
    "anthropic": { "status": "healthy", "response_time_ms": 800 },
    "supabase": { "status": "healthy", "response_time_ms": 120 },
    "redis": { "status": "healthy", "response_time_ms": 5 }
  },
  "agents": {
    "total": 25,
    "active": 24,
    "failed": 1
  }
}
```

**GET /api/v1/health/agents** (detailed agent status):
```json
{
  "agents": [
    {
      "id": "CI-CORE-00",
      "name": "Central Intelligence",
      "status": "healthy",
      "last_execution": "2026-03-12T10:25:00Z",
      "response_time_avg_ms": 2340,
      "error_rate_24h": 0.02,
      "ai_cost_24h": 45.67
    },
    {
      "id": "CI-MKT-01",
      "name": "Email Specialist",
      "status": "healthy",
      "last_execution": "2026-03-12T10:28:30Z",
      "response_time_avg_ms": 1240,
      "error_rate_24h": 0.0,
      "ai_cost_24h": 12.34
    }
  ]
}
```

**Per-Agent Response Time Expectations**:

| Agent Type | Expected Response Time | SLA |
| ----------- | ---------------------- | --- |
| Director (CI-*-DIR) | < 5 seconds | 99% uptime |
| Specialist (CI-*-*) | < 10 seconds | 99.5% uptime |
| Operator (CI-OPS-*) | < 30 seconds for transcription, < 5s for others | 99.5% uptime |
| Central Intelligence (CI-CORE-00) | < 8 seconds (depends on Director responses) | 99.9% uptime |

**Health Check Logic** (FastAPI endpoint):
```python
@app.get("/api/v1/health")
async def health_check():
    """Perform health checks on all services and agents"""
    results = {
        "anthropic": await check_anthropic(),
        "supabase": await check_supabase(),
        "redis": await check_redis(),
    }

    # If any critical service down, system is unhealthy
    if any(r["status"] == "unhealthy" for r in results.values()):
        overall_status = "unhealthy"
    elif any(r["status"] == "degraded" for r in results.values()):
        overall_status = "degraded"
    else:
        overall_status = "healthy"

    return {
        "status": overall_status,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "services": results,
        "agents": {"total": 25, "active": count_active(), "failed": count_failed()}
    }
```

---

### Error Rate Thresholds & Alerting Rules

**Error Tracking** (Supabase table: `agent_error_log`):
```json
{
  "id": "uuid",
  "timestamp": "2026-03-12T10:30:00Z",
  "agent_id": "CI-MKT-01",
  "execution_id": "exec_123",
  "error_type": "API_ERROR | TIMEOUT | VALIDATION_ERROR | UNKNOWN",
  "severity": "critical | high | medium | low",
  "message": "Error message",
  "stack_trace": "...",
  "user_id": "user_123",
  "request_id": "req-abc-123"
}
```

**Alerting Rules**:

| Condition | Severity | Action |
| --------- | -------- | ------ |
| Error rate > 5% in 5 min | critical | Email + Slack → immediately |
| Error rate > 2% in 30 min | high | Slack → ops channel |
| Any critical error | critical | Slack + SMS (if configurable) |
| Anthropic API unavailable | critical | Alert + engage circuit breaker |
| Agent response time > 2x threshold | high | Log + monitor (no alert yet) |
| 429 rate limit errors > 10 in 5 min | medium | Log + increase rate limit if needed |

**Resolution Escalation**:
- Level 1: Auto-retry with exponential backoff
- Level 2: Circuit breaker activates (stop requests for 60s)
- Level 3: Alert sent to on-call team
- Level 4: Fallback agent activated (if available)
- Level 5: Manual intervention (PagerDuty, etc.)

---

### Performance Baselines & SLOs

**Response Time Baselines**:

| Agent | Operation | Baseline | P95 | P99 |
| ------ | --------- | -------- | --- | --- |
| CI-CORE-00 | Chat | 2000-3000ms | 4500ms | 6000ms |
| CI-MKT-DIR | Summary | 2500-3500ms | 5000ms | 7000ms |
| CI-MKT-01 | Generate Script | 1500-2500ms | 3500ms | 5000ms |
| CI-OPS-TRANSCRIBE | Transcribe (5min video) | 15000-25000ms | 30000ms | 40000ms |
| CI-OPS-ICP | Generate ICP | 3000-5000ms | 7000ms | 10000ms |
| CI-SLS-02 | Leads Query | 1000-2000ms | 3000ms | 4000ms |

**SLO Targets**:
- 99.9% uptime (Central Intelligence)
- 99.5% uptime (Directors + key Specialists)
- 99.0% uptime (other Specialists + Operators)
- P95 response time met 95% of the time
- Error rate < 0.5% (excluding intentional 4xx responses)

---

### Logging Strategy: What to Log, Format, Retention

**What to Log**:

1. **Request Entry**: timestamp, method, path, user_id, source_ip
2. **Authentication**: success/failure, reason if failure
3. **Authorization**: decision (allow/deny), user role, resource accessed
4. **Business Logic**: operation, inputs, outputs (non-sensitive)
5. **Errors**: error type, message, stack trace, recovery action
6. **Data Mutations**: CRUD operation, old value, new value, user_id
7. **External API Calls**: service, method, response time, status
8. **Performance**: endpoint response time, AI token usage, file size
9. **Security Events**: failed auth, rate limit exceeded, suspicious patterns

**Log Format** (structured JSON for easy parsing):
```json
{
  "timestamp": "2026-03-12T10:30:00.123Z",
  "request_id": "req-abc-123",
  "user_id": "user_123",
  "agent_id": "CI-MKT-01",
  "operation": "analyze",
  "level": "info" | "warn" | "error" | "critical",
  "message": "Email analysis completed",
  "response_time_ms": 1240,
  "status": 200,
  "data": {
    "input_tokens": 450,
    "output_tokens": 230,
    "ai_cost": 0.45
  }
}
```

**Log Levels**:
- **INFO**: Normal operations, successful requests
- **WARN**: Degraded performance, retry attempts, non-critical errors
- **ERROR**: Operational errors (temporary), user input errors
- **CRITICAL**: Unrecoverable errors, security events, data loss risks

**Retention Policy**:
- **Operational Logs** (INFO, WARN): 30 days
- **Error Logs**: 90 days
- **Audit Logs** (CRUD, auth): 1 year
- **Security Events**: 1 year + export to SIEM
- **Cost Logs** (AI usage): 1 year (for billing)

**Export & Analysis**:
- Push logs to Sentry for error tracking
- Push logs to DataDog for APM
- Query via DataDog/Sentry dashboard
- Set up alerts for error spikes
- Daily digest of key metrics (email to team)

---

### Dashboard Metrics: System Health, AI Usage/Costs, Data Throughput

**System Health Dashboard**:
```
[Overall Status: Healthy]

Agent Status Grid:
  CI-CORE-00: Healthy (last 5min) | 2.5s avg response
  CI-MKT-DIR: Healthy | 3.2s avg response
  CI-MKT-01: Healthy | 1.8s avg response
  ...

Error Rate Trend (last 24h):
  [Graph] Current: 0.2% | Peak: 1.5% | Target: < 0.5%

API Response Times (percentiles):
  P50: 1200ms
  P95: 3400ms
  P99: 5800ms

Active Tasks:
  Running: 3
  Queued: 0
  Failed (last 24h): 2
```

**AI Usage & Costs Dashboard**:
```
[AI Spending - March 2026]

Daily Cost Trend:
  [Graph] $0 ... $150 | Today: $45.60

Model Usage:
  Claude Sonnet (Central Intelligence + Directors): 12,450 tokens | $0.62
  Claude Haiku (Specialists): 45,120 tokens | $0.23
  Claude Haiku (Operators): 8,900 tokens | $0.04
  Whisper (Transcription): 45 min audio | $0.90
  Total: $1.79

Cost per Agent:
  CI-CORE-00: $0.89 (49%)
  CI-MKT-01: $0.34 (19%)
  CI-OPS-TRANSCRIBE: $0.38 (21%)
  Others: $0.18 (11%)

Projected Monthly Cost:
  At current rate: $1,368 | Budget: $2,000 | Headroom: 46%
```

**Data Throughput Dashboard**:
```
[Data Pipeline - Last 24h]

Records Processed by Type:
  Call Transcripts: 14 | 2.1 MB
  Leads Created: 234 | 0.8 MB
  Content Ideas: 456 | 0.3 MB
  Pain Points: 89 | 0.2 MB
  Wins: 67 | 0.1 MB

Supabase Operations:
  Read: 12,450 | 1.2 MB
  Write: 2,340 | 0.4 MB
  Total: 14,790 ops | 1.6 MB

Agent Storage:
  Agent Logs: 45 MB | 12,450 rows
  Call Transcripts: 210 MB | 1,240 rows
  Content Ideas: 8 MB | 4,560 rows
  Total: ~800 MB | ~50,000 rows
  Quota: 2 GB | Usage: 40%

Peak Activity: 10:30 AM - 11:00 AM (234 ops/min)
```

---

## 17. Disaster Recovery & Rollback

### Agent Isolation: Disabling Individual Agents Without Affecting Others

**Graceful Shutdown Strategy**:

1. **Method 1: FastAPI Disable** (immediate):
   - Set agent status to "disabled" in `agent_registry` table
   - Incoming requests to that agent get 503 "Service Unavailable"
   - Other agents unaffected
   - Users can retry or escalate to Central Intelligence/Director

2. **Method 2: Circuit Breaker Engagement** (automatic):
   - If an agent fails 5 consecutive times, circuit breaker opens
   - Requests bypass that agent → 503 + escalate
   - After 60s cooldown, test request is sent
   - If test passes, circuit closes → resume normal operation

3. **Method 3: Dependency De-registration** (admin):
   - Remove agent from Director's tool registry
   - Director/Central Intelligence no longer calls disabled agent
   - Agent still exists (can be re-enabled)
   - Other agents in same department continue normal

4. **Communication**:
   - Disable agent → broadcast message to admin
   - Admin receives Slack alert with reason + estimated recovery time
   - If user tries disabled agent, friendly message: "Agent is temporarily unavailable. Please try again in 5 minutes."

**Example Isolation Scenario**:
- CI-MKT-01 (Email Specialist) crashes due to bad query
- Circuit breaker engages → stop sending requests
- CI-MKT-DIR continues to call other 5 specialists (Social, Funnels, etc.)
- Central Intelligence still operational (calls CI-MKT-DIR successfully, just no email data)
- Admin notified → fixes Email Specialist code → re-enable
- Circuit breaker tests → passes → resume normal

---

### Data Backup Strategy: Supabase Snapshots, Agent State Export

**Backup Schedule**:

| Data Source | Backup Frequency | Retention | Method |
| ----------- | ---------------- | --------- | ------ |
| Supabase (all tables) | Daily 12:00 AM UTC | 30 days | Supabase API backup |
| Agent Code | After every deployment | 90 days | Git + S3 archive |
| Agent State (conversation history) | Daily 1:00 AM UTC | 7 days | Supabase export (store in separate table) |
| Execution Logs | Daily | 30 days | Dump to CSV + upload to S3 |

**Backup Process** (automated via Celery):

1. **Supabase Backup** (backup_supabase_task):
   ```python
   @shared_task(bind=True)
   def backup_supabase_task(self):
       """Backup Supabase database"""
       # Use Supabase API to export
       backup = supabase.backup.create()
       # Upload to S3
       s3.upload(backup, f"s3://ci-backups/supabase/{date}/")
       # Email admin
       send_email_notification("Backup complete", ...)
   ```

2. **Agent State Export** (backup_agent_state_task):
   ```python
   @shared_task(bind=True)
   def backup_agent_state_task(self):
       """Export agent conversation histories"""
       states = db.query(AgentState).all()
       export = json.dumps([s.to_dict() for s in states])
       s3.upload(export, f"s3://ci-backups/agent-state/{date}/")
   ```

3. **Code & Config Backup**:
   ```
   Git tags on every deployment
   S3 archive: s3://ci-backups/code/{version}/
   ```

**Backup Verification**:
- Monthly restore test: Restore from backup to staging environment
- Verify all records match original
- Document any discrepancies
- Alert if restore fails

---

### Rollback Procedure Per Deployment

**Rollback Levels**:

**Level 1: Single Agent Rollback** (< 1 minute downtime):
- Identify failed agent (via alerts + error logs)
- Git: Revert to previous commit
- Redeploy agent code via Docker
- Test 3 requests manually
- Monitor error logs for 10 minutes
- If stable, mark as resolved

**Level 2: Sprint Rollback** (< 5 minutes downtime):
- Issue detected in Sprint 8 deployment affecting critical functionality
- Actions:
  1. Disable all new Sprint 8 agents (circuit breaker + manual disable)
  2. Restore previous Supabase backup (same-day backup from before Sprint 8)
  3. Re-deploy previous agent versions from git
  4. Test all 3 departments (Central Intelligence, Directors, Specialists)
  5. Monitor for 30 minutes
- Communication: Slack alert to team + email to user

**Level 3: Full System Rollback** (< 30 minutes downtime):
- Catastrophic failure (e.g., database corruption, major security breach)
- Actions:
  1. Take system offline (return 503 for all endpoints)
  2. Restore Supabase from 24-hour backup
  3. Restore all agent code to known-good version (git tag)
  4. Restore authentication secrets + user sessions
  5. Run full health check (all endpoints)
  6. Bring system back online
- Communication: Customer notification + post-mortem

**Rollback Decision Tree**:
```
Issue Detected
├─ Single Agent Error?
│  └─ Level 1: Revert agent code + test (1 min)
├─ Multiple Agents in Same Sprint?
│  └─ Level 2: Disable sprint + restore backup + test (5 min)
├─ Data Corruption / Widespread Impact?
│  └─ Level 3: Full system restore + smoke test (30 min)
└─ Security Breach?
   └─ Level 3 + Audit + Key Rotation
```

---

### Emergency Procedures: Complete Shutdown, Partial Shutdown, Data Freeze

**Complete System Shutdown** (entire system offline):

**When to Use**: Severe security breach, data corruption, cascading failure affecting all departments

**Steps**:
1. Admin dashboard → System Control → "Emergency Shutdown"
2. FastAPI: Return 503 Service Unavailable with maintenance message
3. Stop all Celery workers
4. Email + Slack alert to all users: "System undergoing emergency maintenance. Expected duration: 2-4 hours."
5. Begin restoration process (Level 3 rollback above)
6. Test all critical paths before re-opening
7. Notify users when system is back online

**Data Freeze** (accept no new writes, serve read-only):

**When to Use**: Data corruption detected, need to audit before rollback

**Steps**:
1. Admin dashboard → System Control → "Data Freeze"
2. FastAPI: Block all write operations (POST/PUT/DELETE return 503)
3. Allow reads (GET endpoints work normally)
4. Users see message: "System in read-only mode while we investigate. No new data can be saved."
5. Admin investigates logs + error
6. Restore backup if needed, or fix issue + resume writes
7. Return to normal operations

**Partial Shutdown** (disable AI only):

**When to Use**: Anthropic API issues / excessive costs / quota exceeded

**Steps**:
1. Admin dashboard → AI Services → "Disable AI"
2. FastAPI: All agent endpoints return cached results or graceful degradation
3. Directors/Specialists continue to work without AI insights (serving stale data)
4. Email alert: "AI features temporarily unavailable. Data view is read-only."
5. Once Anthropic recovers, re-enable AI
6. Resume normal operations

---

## 18. Naming Conventions

### Python Agent Classes

**Directors (Level 3):**
```
class WB[AREA]DirectorAgent(DirectorAgent):
    agent_id = "CI-[AREA]-DIR"
```
Examples: `WBMKTDirectorAgent`, `WBSLSDirectorAgent`, `WBFULDirectorAgent`

**Specialists (Level 2):**
```
class WB[AREA][NUMBER]Agent(SpecialistAgent):
    agent_id = "CI-[AREA]-[NUMBER]"
```
Examples: `WBMKT01Agent`, `WBSLS01Agent`

**Operators (Level 1):**
```
@shared_task
def wb_ops_[name]_task(...)
    task_id = "CI-OPS-[NAME]"
```
Examples: `wb_ops_transcribe_task`, `wb_ops_icp_task`

**Core:**
```
class WBCOREAgent(BaseAgent):
    agent_id = "CI-CORE-[NAME]"
```
Examples: `WBCORECentralIntelligenceAgent`, `WBCOREErrorHandlerAgent`

Areas: CORE, MKT, SLS, FUL, OPS

### FastAPI Routes

```
/api/v1/[domain]/[operation]
```

Examples: `/api/v1/leads`, `/api/v1/leads/stats`, `/api/v1/social/analyze`, `/api/v1/central-intelligence/chat`, `/api/v1/marketing/summary`, `/api/v1/offers`, `/api/v1/icp`

### Supabase Tables

Snake_case: `goals`, `wins`, `pain_points`, `objections`, `content_ideas`, `call_transcripts`, `agent_registry`, `icp`, `offers`, `comments`, `reference`, `users`, `agent_error_log`, `audit_log`, `idempotency_keys`

### Complete Agent Registry

| ID | Name | Level | Department |
| -- | ---- | ----- | ---------- |
| CI-CORE-00 | Central Intelligence | CEO | Core |
| CI-MKT-DIR | Marketing Director | Director | Marketing |
| CI-SLS-DIR | Sales Director | Director | Sales |
| CI-FUL-DIR | Fulfillment Director | Director | Fulfillment |
| CI-MKT-01 | Email Specialist | Specialist | Marketing |
| CI-MKT-02 | Social Media Specialist | Specialist | Marketing |
| CI-MKT-03 | Funnels Specialist | Specialist | Marketing |
| CI-MKT-04 | Ads Specialist | Specialist | Marketing |
| CI-MKT-05 | DM Specialist | Specialist | Marketing |
| CI-MKT-06 | Offer Creation Specialist | Specialist | Marketing |
| CI-SLS-01 | Appointment Setting Specialist | Specialist | Sales |
| CI-SLS-02 | Leads Database Specialist | Specialist | Sales |
| CI-SLS-03 | Sales Call Analyzer | Specialist | Sales |
| CI-FUL-01 | Members Database Specialist | Specialist | Fulfillment |
| CI-FUL-02 | Coaching Call Analyzer | Specialist | Fulfillment |
| CI-FUL-03 | Accountability Call Analyzer | Specialist | Fulfillment |
| CI-FUL-04 | Tech SOS Tracker | Specialist | Fulfillment |
| CI-OPS-TRANSCRIBE | Call Transcriber | Operator | Shared |
| CI-OPS-ICP | ICP Generator | Operator | Shared |
| CI-OPS-OFFER | Offer Generator | Operator | Shared |
| CI-OPS-STATS-EMAIL | Email Stats Updater | Operator | Marketing |
| CI-OPS-STATS-SOCIAL | Social Stats Updater | Operator | Marketing |
| CI-OPS-STATS-FUNNEL | Funnel Stats Updater | Operator | Marketing |
| CI-OPS-STATS-ADS | Ads Stats Updater | Operator | Marketing |

---

## Summary of Enhancements

The **Security Hardening Specifications** section provides:
- Detailed HMAC-SHA256 request signing with replay protection
- JWT token lifecycle with sliding windows and concurrent session limits
- Per-endpoint input validation rules with AI prompt injection prevention
- Data classification matrix defining access control per data sensitivity
- FastAPI rate limiting with IP allowlisting options

The **Monitoring & Observability** section provides:
- Per-agent health check endpoints with expected response times
- Error rate thresholds and automated alerting rules
- Performance baselines (P95/P99 response times) and SLOs
- Structured logging strategy with retention policies
- Dashboards for system health, AI costs, and data throughput

The **Disaster Recovery & Rollback** section provides:
- Agent isolation strategies to prevent cascading failures
- Automated backup procedures for Supabase, agent code, and state
- Multi-level rollback procedures (single agent → sprint → full system)
- Emergency procedures for complete shutdown, partial shutdown, and data freeze

All sections integrate with the Python + Claude SDK architecture, using FastAPI middleware, Celery tasks, and Supabase for data persistence.
