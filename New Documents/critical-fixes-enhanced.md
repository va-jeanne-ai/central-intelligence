# Central Intelligence / Central Intelligence — Critical Fixes Master Document - ENHANCED

**Version**: 3.0.0
**Date**: 2026-03-29
**Status**: Canonical Reference — Development Team Use Only
**Scope**: Authentication, Error Handling, Data Integrity, Edge Cases, Implementation Tracking
**Tech Stack**: Python + FastAPI + Claude SDK + Supabase + Next.js

---

## Table of Contents

1. [Critical Fixes (P0 / P1 / P2)](#1-critical-fixes)
2. [Implementation Status Tracker](#2-implementation-status-tracker)
3. [Testing Requirements Per Fix](#3-testing-requirements-per-fix)
4. [Post-Fix Verification Protocol](#4-post-fix-verification-protocol)
5. [Fix Dependency Map](#5-fix-dependency-map)
6. [Login / Authentication System](#6-loginauthentication-system)
7. [Error Handling Layer](#7-error-handling-layer)
8. [Edge Case Handlers](#8-edge-case-handlers)
9. [Summary Tables](#9-summary-tables)

---

## 1. Critical Fixes

### Priority Key

| Priority | Label | Definition | Release Gate |
|----------|-------|------------|--------------|
| P0 | Ship Blocker | App cannot go to any user without this. Security hole or guaranteed data loss. | Must be in v1.0 |
| P1 | High Priority | Severely degrades user experience or causes data correctness issues. | Must be in v1.1 |
| P2 | Important | Correctness gaps or architectural weaknesses that compound over time. | Target v1.x |

---

### P0 — Ship Blockers (5 fixes)

#### P0-SEC-01: No User Authentication

**Problem**: Central Intelligence has no authentication system. Any user can access all leads, members, data without login.

**Impact**:
- Users can view/edit other organizations' data
- GDPR/HIPAA violation
- Impossible to audit who made changes
- **Severity**: CRITICAL — Cannot ship without this

**Solution**:
- Implement Supabase Auth with JWT tokens
- Add FastAPI dependency injection for auth validation
- Set session timeout to 24 hours
- Implement account lockout after 5 failed login attempts (15-minute lockout)
- Use bcrypt for password hashing
- Store JWT in httpOnly, Secure cookies

**Technical Details**:
- Backend: Supabase Auth SDK with Python client
- Frontend: Next.js middleware for route protection + login page
- Database: `users` table in Supabase with `id`, `email`, `password_hash`, `email_verified_at`, `locked_until`
- API Endpoint: `POST /api/v1/auth/login` (returns JWT)

**Code Example - FastAPI Login Endpoint**:
```python
from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import select
from datetime import datetime, timedelta
import bcrypt
import jwt

app = FastAPI()

class LoginRequest(BaseModel):
    email: str
    password: str

class User(BaseModel):
    id: str
    email: str
    email_verified_at: datetime | None

@app.post("/api/v1/auth/login")
async def login(req: LoginRequest, db=Depends(get_db)):
    # Check if account is locked
    user = await db.execute(
        select(users_table).where(users_table.c.email == req.email)
    )
    user = user.scalar()

    if user and user.locked_until and user.locked_until > datetime.utcnow():
        raise HTTPException(
            status_code=423,
            detail=f"Account locked. Try again in {(user.locked_until - datetime.utcnow()).seconds // 60} minutes"
        )

    if not user or not bcrypt.checkpw(req.password.encode(), user.password_hash):
        # Increment failed attempts
        failed_count = (user.failed_login_attempts or 0) + 1
        locked_until = None
        if failed_count >= 5:
            locked_until = datetime.utcnow() + timedelta(minutes=15)

        await db.execute(
            update(users_table)
            .where(users_table.c.email == req.email)
            .values(
                failed_login_attempts=failed_count,
                locked_until=locked_until
            )
        )
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # Reset failed attempts
    await db.execute(
        update(users_table)
        .where(users_table.c.id == user.id)
        .values(failed_login_attempts=0, locked_until=None)
    )

    # Create JWT token
    token = jwt.encode(
        {"user_id": user.id, "email": user.email, "exp": datetime.utcnow() + timedelta(hours=24)},
        settings.JWT_SECRET,
        algorithm="HS256"
    )

    response = JSONResponse({"user": User(id=user.id, email=user.email, email_verified_at=user.email_verified_at)})
    response.set_cookie("auth_token", token, httponly=True, secure=True, max_age=86400, samesite="strict")
    return response
```

**Frontend Protection - Next.js Middleware**:
```typescript
// lib/middleware.ts
import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

export function middleware(request: NextRequest) {
  const token = request.cookies.get("auth_token")?.value;

  if (!token && request.nextUrl.pathname !== "/login") {
    return NextResponse.redirect(new URL("/login", request.url));
  }

  if (token && request.nextUrl.pathname === "/login") {
    return NextResponse.redirect(new URL("/dashboard", request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/dashboard/:path*", "/login"]
};
```

---

#### P0-SEC-02: No HMAC Webhook Signing

**Problem**: Webhooks from external services (Airtable, Stripe, etc.) are not validated. Any attacker can send fake webhook events.

**Impact**:
- Fake webhook events can corrupt data
- Attacker can trigger false workflows
- No way to verify request origin
- **Severity**: CRITICAL

**Solution**:
- Implement HMAC-SHA256 signature verification for all POST/PUT/DELETE endpoints
- Generate unique signature for each API client
- Verify `X-Signature-256` header on incoming requests
- Sign outgoing API calls with header

**Technical Details**:
- Use `hmac` library in Python for signature generation/verification
- FastAPI middleware for signature validation
- Secrets stored in `.env` as `API_SIGNATURES[client_id]`

**Code Example - HMAC Verification Middleware**:
```python
from fastapi import FastAPI, Request, HTTPException
from fastapi.security import APIKeyHeader
import hmac
import hashlib
import json

app = FastAPI()

async def verify_hmac_signature(request: Request):
    """Middleware to verify HMAC-SHA256 signature on mutating endpoints"""

    if request.method in ["POST", "PUT", "DELETE"]:
        body = await request.body()
        signature = request.headers.get("X-Signature-256")

        if not signature:
            raise HTTPException(status_code=401, detail="Missing X-Signature-256 header")

        # Calculate expected signature
        secret = os.getenv("WEBHOOK_SECRET", "").encode()
        expected_signature = hmac.new(secret, body, hashlib.sha256).hexdigest()

        if not hmac.compare_digest(signature, expected_signature):
            raise HTTPException(status_code=401, detail="Invalid signature")

    return request

app.middleware("http")(verify_hmac_signature)

@app.post("/api/v1/leads")
async def create_lead(lead_data: dict, request: Request):
    # Signature already verified by middleware
    # Process lead creation
    pass
```

**Code Example - Signing Outgoing Requests**:
```python
def sign_request(payload: dict, secret: str) -> str:
    """Generate HMAC-SHA256 signature for outgoing requests"""
    body = json.dumps(payload, separators=(',', ':'), sort_keys=True)
    signature = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
    return signature

# Usage
payload = {"name": "Jane", "email": "jane@example.com"}
signature = sign_request(payload, os.getenv("WEBHOOK_SECRET"))

headers = {
    "X-Signature-256": signature,
    "Content-Type": "application/json"
}

# Send to external service
response = httpx.post("https://external-api.com/webhook", json=payload, headers=headers)
```

---

#### P0-DATA-01: No Confirmation for DELETE Operations

**Problem**: Users can accidentally delete leads/members with one click. No confirmation modal.

**Impact**:
- Permanent data loss (even with soft delete, user lost work)
- No recovery workflow
- Frustrating UX
- **Severity**: CRITICAL

**Solution**:
- Add confirmation modal on DELETE button click
- Modal shows item name and asks "Are you sure?"
- Confirmation modal must be explicitly accepted
- Backend validates `X-User-Id` header on DELETE requests

**Technical Details**:
- Frontend: React modal component with two buttons (Cancel, Confirm Delete)
- Backend: Require explicit `confirm=true` parameter on DELETE endpoint
- Database: Soft delete (set `deleted_at` timestamp, don't remove record)

**Code Example - Frontend Modal**:
```typescript
// components/DeleteConfirmation.tsx
import { useState } from "react";
import { Dialog, DialogActions, DialogContent, DialogTitle } from "@mui/material";

interface DeleteConfirmationProps {
  open: boolean;
  itemName: string;
  itemType: "lead" | "member" | "call";
  onConfirm: () => void;
  onCancel: () => void;
  isLoading?: boolean;
}

export function DeleteConfirmation({
  open,
  itemName,
  itemType,
  onConfirm,
  onCancel,
  isLoading = false
}: DeleteConfirmationProps) {
  return (
    <Dialog open={open} onClose={onCancel} maxWidth="xs" fullWidth>
      <DialogTitle>Delete {itemType}</DialogTitle>
      <DialogContent>
        <p>
          Are you sure you want to delete <strong>{itemName}</strong>?
        </p>
        <p className="text-sm text-gray-500">This action cannot be undone.</p>
      </DialogContent>
      <DialogActions>
        <button onClick={onCancel} disabled={isLoading}>
          Cancel
        </button>
        <button
          onClick={onConfirm}
          disabled={isLoading}
          className="bg-red-600 text-white"
        >
          {isLoading ? "Deleting..." : "Delete"}
        </button>
      </DialogActions>
    </Dialog>
  );
}
```

**Code Example - Backend DELETE Endpoint**:
```python
@app.delete("/api/v1/leads/{lead_id}")
async def delete_lead(
    lead_id: str,
    confirm: bool = Query(...),
    current_user = Depends(get_current_user),
    db = Depends(get_db)
):
    """Soft delete a lead. Requires confirm=true query parameter."""

    if not confirm:
        raise HTTPException(status_code=400, detail="Deletion must be confirmed with confirm=true")

    lead = await db.execute(
        select(leads_table).where(leads_table.c.id == lead_id)
    )
    lead = lead.scalar()

    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    if lead.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Unauthorized")

    # Soft delete
    await db.execute(
        update(leads_table)
        .where(leads_table.c.id == lead_id)
        .values(
            deleted_at=datetime.utcnow(),
            deleted_by=current_user.id
        )
    )

    return {"status": "deleted"}
```

---

#### P0-DATA-02: Orphaned Records on Delete

**Problem**: When a lead is deleted, related call transcripts, notes, and goals remain in database. Creates orphaned records that break referential integrity.

**Impact**:
- Orphaned records accumulate, bloating database
- Foreign key constraint violations
- Confusing data audit trails
- **Severity**: CRITICAL

**Solution**:
- Implement soft delete cascade triggers in PostgreSQL
- When lead is deleted, mark all related records as deleted
- Track deletion in audit log with user ID and reason
- Soft delete rather than hard delete (preserve data for recovery)

**Technical Details**:
- Database: Add `deleted_at` and `deleted_by` fields to all tables
- Use PostgreSQL triggers for cascade soft delete
- Audit log tracks all deletions with context
- Views filter out deleted records by default

**Code Example - PostgreSQL Cascade Soft Delete**:
```sql
-- Create soft delete function
CREATE OR REPLACE FUNCTION soft_delete_cascade()
RETURNS TRIGGER AS $$
BEGIN
  -- Soft delete call transcripts
  UPDATE call_transcripts
  SET deleted_at = NOW(), deleted_by = NEW.deleted_by
  WHERE lead_id = NEW.id AND deleted_at IS NULL;

  -- Soft delete goals
  UPDATE member_goals
  SET deleted_at = NOW(), deleted_by = NEW.deleted_by
  WHERE lead_id = NEW.id AND deleted_at IS NULL;

  -- Soft delete notes
  UPDATE notes
  SET deleted_at = NOW(), deleted_by = NEW.deleted_by
  WHERE lead_id = NEW.id AND deleted_at IS NULL;

  -- Create audit log entry
  INSERT INTO audit_log (
    table_name, record_id, action, old_values, new_values,
    user_id, created_at
  ) VALUES (
    'leads',
    NEW.id,
    'DELETE',
    jsonb_build_object('deleted_at', NULL),
    jsonb_build_object('deleted_at', NEW.deleted_at),
    NEW.deleted_by,
    NOW()
  );

  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER leads_soft_delete_cascade
BEFORE UPDATE ON leads
FOR EACH ROW
WHEN (OLD.deleted_at IS NULL AND NEW.deleted_at IS NOT NULL)
EXECUTE FUNCTION soft_delete_cascade();
```

**Code Example - Default View to Hide Deleted Records**:
```sql
CREATE OR REPLACE VIEW leads_active AS
SELECT * FROM leads WHERE deleted_at IS NULL;

CREATE OR REPLACE VIEW call_transcripts_active AS
SELECT * FROM call_transcripts WHERE deleted_at IS NULL;

-- Use views in application queries:
-- SELECT * FROM leads_active  (instead of leads table directly)
```

---

#### P0-DATA-03: No Central Intelligence Error Handling

**Problem**: When Python agents fail (invalid data, timeout, API error), errors are not caught or logged. Workflows silently fail or crash.

**Impact**:
- No visibility into failures
- Errors go to logs, not structured error table
- No alerting for critical errors
- Impossible to debug issues
- **Severity**: CRITICAL

**Solution**:
- Create centralized error handler middleware in FastAPI
- Log all errors to `error_logs` Supabase table with full context
- Categorize errors (VALIDATION, TIMEOUT, RATE_LIMIT, DATABASE, EXTERNAL_API, INTERNAL)
- Send Sentry alerts for P0-level errors
- Return user-friendly error messages to frontend

**Technical Details**:
- FastAPI exception handlers for each error type
- Pydantic v2 validators for input validation
- Sentry integration for error monitoring
- Error repository in SQLAlchemy for database access

**Code Example - Centralized Error Handler**:
```python
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import sentry_sdk
import logging
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)
sentry_sdk.init(dsn=os.getenv("SENTRY_DSN"))

class ErrorCategory(str, Enum):
    VALIDATION = "VALIDATION"
    TIMEOUT = "TIMEOUT"
    RATE_LIMIT = "RATE_LIMIT"
    DATABASE = "DATABASE"
    EXTERNAL_API = "EXTERNAL_API"
    INTERNAL = "INTERNAL"
    AUTH = "AUTH"

class Central IntelligenceException(Exception):
    """Base exception for all Central Intelligence errors"""
    def __init__(self, category: ErrorCategory, message: str, agent_id: str = None, severity: str = "error"):
        self.category = category
        self.message = message
        self.agent_id = agent_id
        self.severity = severity
        super().__init__(message)

@app.exception_handler(Central IntelligenceException)
async def centralintelligence_exception_handler(request: Request, exc: Central IntelligenceException):
    """Handle Central Intelligence exceptions and log to error_logs table"""

    # Log to database
    error_record = {
        "agent_id": exc.agent_id,
        "error_code": exc.category.value,
        "error_message": exc.message,
        "severity": exc.severity,
        "request_path": request.url.path,
        "request_method": request.method,
        "user_agent": request.headers.get("user-agent"),
        "created_at": datetime.utcnow(),
        "resolved": False,
        "resolution_notes": None
    }

    # Insert into error_logs
    await error_repository.create(error_record)

    # Send to Sentry if critical
    if exc.severity in ["critical", "error"]:
        sentry_sdk.capture_exception(exc)

    # Log to stdout
    logger.error(f"Central Intelligence Error: {exc.category.value} - {exc.message}",
                 extra={"agent_id": exc.agent_id, "severity": exc.severity})

    # Return user-friendly error response
    return JSONResponse(
        status_code=400 if exc.category == ErrorCategory.VALIDATION else 503,
        content={
            "error": exc.category.value,
            "message": "An error occurred. Please try again or contact support.",
            "error_id": error_record["id"]  # For support reference
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Catch unhandled exceptions"""

    error_record = {
        "agent_id": None,
        "error_code": "INTERNAL_ERROR",
        "error_message": str(exc),
        "severity": "critical",
        "request_path": request.url.path,
        "request_method": request.method,
        "user_agent": request.headers.get("user-agent"),
        "created_at": datetime.utcnow(),
        "resolved": False,
        "resolution_notes": None
    }

    await error_repository.create(error_record)
    sentry_sdk.capture_exception(exc)

    return JSONResponse(
        status_code=500,
        content={"error": "INTERNAL_ERROR", "message": "An unexpected error occurred."}
    )
```

**Code Example - Validation Error Handler**:
```python
from pydantic import BaseModel, validator
from fastapi import HTTPException

class CreateLeadRequest(BaseModel):
    name: str
    email: str

    @validator('email')
    def validate_email(cls, v):
        if '@' not in v:
            raise ValueError('Invalid email format')
        return v

    @validator('name')
    def validate_name(cls, v):
        if len(v) < 2:
            raise ValueError('Name must be at least 2 characters')
        return v

@app.post("/api/v1/leads")
async def create_lead(req: CreateLeadRequest):
    """Validation errors automatically caught by Pydantic and converted to 422 response"""
    # If validation fails, Pydantic raises ValidationError automatically
    # FastAPI converts to 422 Unprocessable Entity with field details
    pass
```

**Code Example - Timeout Handler**:
```python
import asyncio

@app.post("/api/v1/analyze")
async def analyze_lead(lead_id: str, current_user = Depends(get_current_user)):
    """Analyze lead with Claude SDK, with 30-second timeout for AI operations"""
    try:
        # Claude API call with timeout
        result = await asyncio.wait_for(
            claude_client.analyze_lead(lead_id),
            timeout=30.0
        )
        return result
    except asyncio.TimeoutError:
        raise Central IntelligenceException(
            category=ErrorCategory.TIMEOUT,
            message=f"Lead analysis timed out after 30 seconds",
            agent_id="CI-AI-01",
            severity="error"
        )
    except Exception as e:
        raise Central IntelligenceException(
            category=ErrorCategory.EXTERNAL_API,
            message=f"Claude API error: {str(e)}",
            agent_id="CI-AI-01",
            severity="error"
        )
```

---

### P1 — High Priority (7 fixes)

#### P1-UX-01: No Loading States

**Problem**: Users don't see feedback when requests are processing. Leads to confusion and double-clicks.

**Solution**:
- Add loading spinner/skeleton during API requests
- Disable buttons while request in flight
- Show "Loading..." text on buttons

#### P1-UX-02: No Empty States

**Problem**: Empty lists show nothing. Users think app is broken or haven't figured out they need to create items.

**Solution**:
- Empty state illustrations for each list view
- Clear CTAs like "Create your first lead"

#### P1-UX-03: No Toast Notifications

**Problem**: Users don't know if actions succeeded. No success/error feedback.

**Solution**:
- Toast notification system (success, error, info, warning)
- Auto-dismiss after 5 seconds
- Action buttons in toasts

#### P1-DATA-04: Duplicate Form Submissions

**Problem**: If user clicks Submit twice quickly, form submits twice. Creates duplicate records.

**Solution**:
- Implement idempotency key handling
- Same idempotency key within 5 minutes returns cached response
- Client generates UUID for each form submission

**Code Example - Idempotency Middleware**:
```python
from fastapi import FastAPI, Request, Header
from uuid import UUID
import hashlib
from datetime import datetime, timedelta

# In-memory cache (use Redis in production)
idempotency_cache = {}

async def idempotency_middleware(request: Request, call_next):
    """Middleware to prevent duplicate submissions with idempotency keys"""

    if request.method in ["POST", "PUT"]:
        idempotency_key = request.headers.get("Idempotency-Key")

        if idempotency_key:
            cache_key = f"{request.url.path}:{idempotency_key}"

            # Check if we've seen this request before (within 5 minutes)
            if cache_key in idempotency_cache:
                cached_time, cached_response = idempotency_cache[cache_key]
                if datetime.utcnow() - cached_time < timedelta(minutes=5):
                    return cached_response

    response = await call_next(request)

    # Cache successful responses
    if request.method in ["POST", "PUT"] and response.status_code < 400:
        idempotency_key = request.headers.get("Idempotency-Key")
        if idempotency_key:
            cache_key = f"{request.url.path}:{idempotency_key}"
            idempotency_cache[cache_key] = (datetime.utcnow(), response)

    return response

app = FastAPI()
app.middleware("http")(idempotency_middleware)

@app.post("/api/v1/leads")
async def create_lead(lead_data: dict, idempotency_key: str = Header(None)):
    """Create lead with idempotency support"""
    # Idempotency key automatically handled by middleware
    # If same key submitted twice, second request returns cached response
    pass
```

**Frontend Example - Generate Idempotency Key**:
```typescript
// hooks/useIdempotency.ts
import { useRef } from "react";
import { v4 as uuidv4 } from "uuid";

export function useIdempotencyKey() {
  const keyRef = useRef(uuidv4());
  return keyRef.current;
}

// components/CreateLeadForm.tsx
import { useIdempotencyKey } from "@/hooks/useIdempotency";

export function CreateLeadForm() {
  const idempotencyKey = useIdempotencyKey();

  async function handleSubmit(formData: any) {
    const response = await fetch("/api/v1/leads", {
      method: "POST",
      headers: {
        "Idempotency-Key": idempotencyKey,
        "Content-Type": "application/json"
      },
      body: JSON.stringify(formData)
    });

    return response.json();
  }

  return <form onSubmit={handleSubmit}>...</form>;
}
```

#### P1-DATA-05: No Optimistic Locking

**Problem**: Multiple users editing same record simultaneously. Last write wins, losing previous changes.

**Solution**:
- Add `updatedAt` field to all records
- Include `If-Match` header with current `updatedAt` on PUT requests
- Return 409 CONFLICT if record was modified since client fetched it

**Code Example - Optimistic Locking**:
```python
from datetime import datetime
from fastapi import HTTPException

@app.put("/api/v1/leads/{lead_id}")
async def update_lead(
    lead_id: str,
    updated_data: dict,
    if_match: str = Header(None),  # Current updatedAt value
    current_user = Depends(get_current_user),
    db = Depends(get_db)
):
    """Update lead with optimistic locking via If-Match header"""

    lead = await db.execute(
        select(leads_table).where(leads_table.c.id == lead_id)
    )
    lead = lead.scalar()

    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    # Check If-Match header matches current updatedAt
    if if_match and if_match != lead.updated_at.isoformat():
        raise HTTPException(
            status_code=409,
            detail="Lead was modified by another user. Please refresh and try again.",
            headers={"ETag": lead.updated_at.isoformat()}
        )

    # Update record with new timestamp
    now = datetime.utcnow()
    await db.execute(
        update(leads_table)
        .where(leads_table.c.id == lead_id)
        .values({**updated_data, "updated_at": now})
    )

    return {"updated_at": now.isoformat()}
```

**Frontend Example - Optimistic Locking**:
```typescript
// hooks/useOptimisticUpdate.ts
async function updateLead(lead: Lead, changes: Partial<Lead>) {
  const response = await fetch(`/api/v1/leads/${lead.id}`, {
    method: "PUT",
    headers: {
      "If-Match": lead.updatedAt,  // Send current timestamp
      "Content-Type": "application/json"
    },
    body: JSON.stringify(changes)
  });

  if (response.status === 409) {
    // Conflict: record was modified
    toast.error("Lead was modified by another user. Please refresh and try again.");
    return null;
  }

  return response.json();
}
```

#### P1-SEC-03: No Audit Logging

**Problem**: No way to track who made what changes when. Violates compliance requirements (GDPR, HIPAA).

**Solution**:
- Log every Create/Update/Delete operation to audit_log table
- Track before_value, after_value, user_id, timestamp
- Admin dashboard to view audit trail

**Code Example - Audit Log Middleware**:
```python
from sqlalchemy import Table, Column, String, JSON, DateTime
from datetime import datetime

audit_log_table = Table(
    'audit_log',
    metadata,
    Column('id', String, primary_key=True),
    Column('table_name', String),
    Column('record_id', String),
    Column('action', String),  # CREATE, UPDATE, DELETE
    Column('before_value', JSON),
    Column('after_value', JSON),
    Column('user_id', String),
    Column('created_at', DateTime),
)

async def log_audit_event(
    table_name: str,
    record_id: str,
    action: str,
    before_value: dict,
    after_value: dict,
    user_id: str,
    db
):
    """Log operation to audit_log table"""

    await db.execute(
        audit_log_table.insert().values(
            id=str(uuid.uuid4()),
            table_name=table_name,
            record_id=record_id,
            action=action,
            before_value=before_value,
            after_value=after_value,
            user_id=user_id,
            created_at=datetime.utcnow()
        )
    )

@app.put("/api/v1/leads/{lead_id}")
async def update_lead(
    lead_id: str,
    updated_data: dict,
    current_user = Depends(get_current_user),
    db = Depends(get_db)
):
    """Update lead and audit log the change"""

    # Get current record
    old_record = await db.execute(
        select(leads_table).where(leads_table.c.id == lead_id)
    )
    old_record = old_record.scalar()

    # Update record
    await db.execute(
        update(leads_table)
        .where(leads_table.c.id == lead_id)
        .values(updated_data)
    )

    # Log audit event
    await log_audit_event(
        table_name="leads",
        record_id=lead_id,
        action="UPDATE",
        before_value=dict(old_record),
        after_value={**dict(old_record), **updated_data},
        user_id=current_user.id,
        db=db
    )

    return {"status": "updated"}
```

#### P1-PERF-01: No Timeout Configuration

**Problem**: Requests hang indefinitely if external API hangs. App becomes unresponsive.

**Solution**:
- Set global request timeout to 10 seconds
- Extended timeout (30 seconds) for AI analysis requests
- Return 408 REQUEST TIMEOUT if timeout exceeded
- Log timeout errors for monitoring

**Code Example - Timeout Configuration**:
```python
import asyncio
from fastapi import FastAPI
import httpx

app = FastAPI()

# Global HTTP client with timeout
http_client = httpx.AsyncClient(timeout=httpx.Timeout(10.0))

# Extended timeout for AI operations
ai_client = httpx.AsyncClient(timeout=httpx.Timeout(30.0))

@app.post("/api/v1/leads")
async def create_lead(lead_data: dict):
    """Standard API request with 10-second timeout"""
    try:
        response = await asyncio.wait_for(
            process_lead(lead_data),
            timeout=10.0
        )
        return response
    except asyncio.TimeoutError:
        raise Central IntelligenceException(
            category=ErrorCategory.TIMEOUT,
            message="Request timed out after 10 seconds",
            severity="error"
        )

@app.post("/api/v1/analyze")
async def analyze_lead(lead_id: str):
    """AI analysis with 30-second timeout"""
    try:
        result = await asyncio.wait_for(
            claude_client.analyze_lead(lead_id),
            timeout=30.0
        )
        return result
    except asyncio.TimeoutError:
        raise Central IntelligenceException(
            category=ErrorCategory.TIMEOUT,
            message="AI analysis timed out after 30 seconds",
            agent_id="CI-AI-01",
            severity="error"
        )
```

---

### P2 — Important (8 fixes)

#### P2-DATA-06: Pain Point Frequency Double-Counting

**Problem**: Same pain point submitted multiple times gets counted multiple times instead of aggregating frequency.

**Solution**:
- Deduplicate pain points during aggregation
- Use content hash to identify duplicates
- Increment frequency counter instead of creating duplicate records

#### P2-DATA-07: Content Idea Status Never Transitions

**Problem**: Content idea status field only has 2 values, needs 6 for full lifecycle (draft, approved, published, archived, rejected, on_hold).

**Solution**:
- Expand content_ideas.status field to enum with 6 values
- Add status_updated_at timestamp
- Add status_updated_by for audit trail

#### P2-DATA-08: Member Goals Array Grows Forever

**Problem**: goals_json field appends goals but never removes deleted goals. Field becomes massive.

**Solution**:
- Structure goals_json as array of objects with active/deleted status
- Implement cleanup logic to remove deleted goals after 30 days
- Add data migration to restructure existing goals

#### P2-DATA-09: call_transcripts Missing member_id

**Problem**: Call transcripts record which lead they're for, but not which member. Creates accountability gap.

**Solution**:
- Add member_id field to call_transcripts table
- Update backend to populate member_id when creating transcripts
- Enable queries like "all calls for this member"

#### P2-DATA-10: Lead-to-Member Conversion Workflow

**Problem**: No automated way to convert a lead to a member. Manual process prone to errors.

**Solution**:
- Implement conversion workflow triggered by admin
- Create new member record from lead data
- Link original lead to new member via member_id
- Update all related transcripts with new member_id

**Code Example - Lead-to-Member Conversion Agent**:
```python
from datetime import datetime
from sqlalchemy import select, insert, update

class LeadConversionAgent:
    """Agent to convert leads to members with full cascading"""

    def __init__(self, db_session, user_id: str):
        self.db = db_session
        self.user_id = user_id

    async def convert_lead_to_member(self, lead_id: str) -> dict:
        """Convert lead to member with all related records updated"""

        try:
            # Fetch lead
            lead = await self.db.execute(
                select(leads_table).where(leads_table.c.id == lead_id)
            )
            lead = lead.scalar()

            if not lead:
                raise Central IntelligenceException(
                    category=ErrorCategory.DATABASE,
                    message=f"Lead {lead_id} not found",
                    severity="error"
                )

            # Create member record
            member_id = str(uuid.uuid4())
            await self.db.execute(
                insert(members_table).values(
                    id=member_id,
                    name=lead.name,
                    email=lead.email,
                    phone=lead.phone,
                    company=lead.company,
                    converted_from_lead_id=lead_id,
                    converted_at=datetime.utcnow(),
                    created_by=self.user_id
                )
            )

            # Link lead to member
            await self.db.execute(
                update(leads_table)
                .where(leads_table.c.id == lead_id)
                .values(member_id=member_id)
            )

            # Update all related call transcripts
            await self.db.execute(
                update(call_transcripts_table)
                .where(call_transcripts_table.c.lead_id == lead_id)
                .values(member_id=member_id)
            )

            # Audit log
            await log_audit_event(
                table_name="members",
                record_id=member_id,
                action="CREATE",
                before_value={},
                after_value={
                    "id": member_id,
                    "name": lead.name,
                    "converted_from_lead_id": lead_id
                },
                user_id=self.user_id,
                db=self.db
            )

            return {
                "member_id": member_id,
                "name": lead.name,
                "transcripts_updated": await self.db.execute(
                    select(func.count()).select_from(call_transcripts_table)
                    .where(call_transcripts_table.c.member_id == member_id)
                )
            }

        except Exception as e:
            raise Central IntelligenceException(
                category=ErrorCategory.INTERNAL,
                message=f"Lead conversion failed: {str(e)}",
                severity="error"
            )
```

#### P2-PERF-02: No Circuit Breaker

**Problem**: When external API (Airtable, Stripe, etc.) goes down, Central Intelligence keeps hammering it with requests. Causes cascading failures.

**Solution**:
- Implement circuit breaker pattern
- Track failure rate for each external API
- Open circuit after 5 failures in 60 seconds
- Return cached response or graceful error while circuit is open
- Auto-close circuit after 30 seconds

**Code Example - Circuit Breaker**:
```python
from enum import Enum
from datetime import datetime, timedelta
import asyncio

class CircuitState(str, Enum):
    CLOSED = "closed"  # Normal operation
    OPEN = "open"      # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered

class CircuitBreaker:
    """Circuit breaker for external API calls"""

    def __init__(self, service_name: str, failure_threshold: int = 5, timeout_seconds: int = 30):
        self.service_name = service_name
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.timeout_seconds = timeout_seconds
        self.last_failure_time = None
        self.last_success_time = datetime.utcnow()

    async def call(self, func, *args, **kwargs):
        """Execute function with circuit breaker protection"""

        # Check if circuit should transition
        if self.state == CircuitState.OPEN:
            if datetime.utcnow() - self.last_failure_time > timedelta(seconds=self.timeout_seconds):
                # Try again (half-open state)
                self.state = CircuitState.HALF_OPEN
                logger.info(f"Circuit breaker for {self.service_name} is half-open, testing...")
            else:
                # Circuit still open
                raise Central IntelligenceException(
                    category=ErrorCategory.EXTERNAL_API,
                    message=f"{self.service_name} is temporarily unavailable. Please try again shortly.",
                    severity="error"
                )

        try:
            result = await func(*args, **kwargs)

            # Success - reset state
            if self.state == CircuitState.HALF_OPEN:
                logger.info(f"Circuit breaker for {self.service_name} recovered")

            self.state = CircuitState.CLOSED
            self.failure_count = 0
            self.last_success_time = datetime.utcnow()

            return result

        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = datetime.utcnow()

            if self.failure_count >= self.failure_threshold:
                self.state = CircuitState.OPEN
                logger.error(f"Circuit breaker opened for {self.service_name} after {self.failure_count} failures")

            raise

# Usage
airtable_breaker = CircuitBreaker("Airtable", failure_threshold=5, timeout_seconds=30)

@app.get("/api/v1/sync-airtable")
async def sync_airtable():
    """Sync with Airtable with circuit breaker protection"""
    try:
        records = await airtable_breaker.call(airtable_client.get_records)
        return records
    except Central IntelligenceException as e:
        return JSONResponse(status_code=503, content={"error": e.message})
```

#### P2-SEC-04: Predictable Webhook Paths

**Problem**: Webhook URLs are predictable (e.g., `/webhook/leads`, `/webhook/members`). Attacker can guess URLs and submit fake events.

**Solution**: *Deferred to post-v1.0*
- Generate random webhook paths per client (e.g., `/webhook/abc123def456`)
- Rotate paths monthly
- Document in admin panel

#### P2-SEC-05: Token Rotation

**Problem**: JWT tokens never expire/rotate. If token leaks, attacker has permanent access.

**Solution**: *Deferred to post-v1.0*
- Implement refresh token rotation
- Short-lived access tokens (1 hour)
- Long-lived refresh tokens (30 days)
- Rotate on each refresh

---

## 2. Implementation Status Tracker

### Master Tracking Table

Track the implementation status of all P0/P1/P2 fixes with Sprint assignments and dependencies.

| Fix ID | Priority | Category | Status | Sprint | Assigned To | Effort | Due Date | Dependencies | Notes |
|--------|----------|----------|--------|--------|-------------|--------|----------|--------------|-------|
| P0-SEC-01 | P0 | Security | Open | Sprint 1 | @alice-auth | 10 pts | 2026-03-19 | None | **Blocking everything else** - user auth required |
| P0-SEC-02 | P0 | Security | Open | Sprint 1 | @alice-auth | 3 pts | 2026-03-19 | P0-SEC-01 | HMAC signing for webhook security |
| P0-DATA-01 | P0 | Data | Open | Sprint 2 | @bob-backend | 5 pts | 2026-04-02 | P0-SEC-01 | DELETE confirmation dialog + backend validation |
| P0-DATA-02 | P0 | Data | Open | Sprint 2 | @bob-backend | 8 pts | 2026-04-02 | P0-SEC-01 | Soft delete + cascade (P0-DATA-01) |
| P0-DATA-03 | P0 | Data | Open | Sprint 1 | @bob-backend | 5 pts | 2026-03-19 | None | Error handling framework for all workflows |
| P1-UX-01 | P1 | UX | Open | Sprint 2 | @carol-frontend | 3 pts | 2026-04-02 | None | Loading spinners/skeletons during requests |
| P1-UX-02 | P1 | UX | Open | Sprint 2 | @carol-frontend | 4 pts | 2026-04-02 | None | Empty state illustrations for lists |
| P1-UX-03 | P1 | UX | Open | Sprint 2 | @carol-frontend | 2 pts | 2026-04-02 | None | Toast notification system |
| P1-DATA-04 | P1 | Data | Open | Sprint 2 | @bob-backend | 5 pts | 2026-04-02 | P0-SEC-02 | Idempotency key handling |
| P1-DATA-05 | P1 | Data | Open | Sprint 3 | @bob-backend | 6 pts | 2026-04-16 | None | If-Match header for optimistic locking |
| P1-SEC-03 | P1 | Security | Open | Sprint 2 | @alice-auth | 4 pts | 2026-04-02 | P0-SEC-01 | audit_log table + field tracking |
| P1-PERF-01 | P1 | Performance | Open | Sprint 2 | @dave-devops | 3 pts | 2026-04-02 | None | Request timeout configuration (10s global, 30s AI) |
| P2-DATA-06 | P2 | Data | Open | Sprint 3 | @bob-backend | 4 pts | 2026-04-16 | None | Pain point deduplication in aggregation |
| P2-DATA-07 | P2 | Data | Open | Sprint 3 | @bob-backend | 3 pts | 2026-04-16 | None | Content idea status field expansion (6 values) |
| P2-DATA-08 | P2 | Data | Open | Sprint 3 | @bob-backend | 4 pts | 2026-04-16 | None | goals_json field structure + cleanup |
| P2-DATA-09 | P2 | Data | Open | Sprint 2 | @bob-backend | 2 pts | 2026-04-02 | None | Add member_id field to call_transcripts |
| P2-DATA-10 | P2 | Data | Open | Sprint 4 | @bob-backend | 8 pts | 2026-04-30 | P1-DATA-04 | Lead-to-member conversion workflow |
| P2-PERF-02 | P2 | Performance | Open | Sprint 4 | @dave-devops | 5 pts | 2026-04-30 | None | Circuit breaker for external API calls |
| P2-SEC-04 | P2 | Security | Deferred | Sprint 5 | @alice-auth | 2 pts | 2026-05-14 | None | Randomized webhook paths (post-v1.0) |
| P2-SEC-05 | P2 | Security | Deferred | Sprint 5 | @alice-auth | 3 pts | 2026-05-14 | None | Token rotation policy (post-v1.0) |

### Status Definitions

| Status | Definition | When to Use |
|--------|-----------|------------|
| **Open** | Fix identified, not yet started | Initial state for all fixes |
| **In Progress** | Currently being implemented | When developer starts work |
| **In Review** | PR submitted, awaiting code review | Code review cycle |
| **Testing** | Implementation complete, QA testing | QA/integration testing phase |
| **Resolved** | Fix complete, verified, deployed to staging | Production-ready |
| **Deferred** | Pushed to later sprint/release | Deprioritized for strategic reasons |
| **Blocked** | Cannot proceed due to dependency | Waiting for another fix to complete |

---

## 3. Testing Requirements Per Fix

### P0 Fixes: Mandatory Test Cases

#### P0-SEC-01: No User Authentication

**Test Suite**: `tests/auth.integration.test.ts`

| Test Case | Preconditions | Steps | Expected Result | Pass/Fail |
|-----------|---|---|---|---|
| TC-P0-SEC-01-001 | Clean database | 1. Navigate to login page | Login form displayed with email/password fields | — |
| TC-P0-SEC-01-002 | Valid user in database | 1. Enter valid email and password | User authenticated, JWT cookie set, redirected to dashboard | — |
| TC-P0-SEC-01-003 | Valid email, wrong password | 1. Enter valid email and incorrect password (5+ times) | Account locked for 15 minutes, error message displayed | — |
| TC-P0-SEC-01-004 | Account locked | 1. Try to login within locked period | Error message: "Account locked. Try again in X minutes" | — |
| TC-P0-SEC-01-005 | Valid session | 1. Login successfully 2. Navigate to protected page | Page loads, user context available | — |
| TC-P0-SEC-01-006 | Expired session | 1. Login 2. Wait 24 hours 3. Try to access protected page | Redirected to login page | — |
| TC-P0-SEC-01-007 | No session | 1. Navigate to protected page without logging in | Redirected to login page | — |
| TC-P0-SEC-01-008 | Valid password, attempt change | 1. Login 2. Go to settings 3. Change password | New password works on next login, old password fails | — |

**Integration Requirements**:
- Supabase Auth with JWT tokens
- Users table with email/bcrypt password hash
- Failed login attempt counter with auto-reset after 15 minutes
- JWT expiration set to 24 hours
- HttpOnly, Secure cookie flags enabled

---

#### P0-SEC-02: No HMAC Webhook Signing

**Test Suite**: `tests/hmac-signing.unit.test.ts`

| Test Case | Preconditions | Steps | Expected Result | Pass/Fail |
|-----------|---|---|---|---|
| TC-P0-SEC-02-001 | Valid request | 1. Create request body 2. Calculate HMAC-SHA256 signature 3. Set X-Signature-256 header | Backend receives and verifies signature | — |
| TC-P0-SEC-02-002 | Invalid signature | 1. Set incorrect X-Signature-256 header | Returns 401 Unauthorized | — |
| TC-P0-SEC-02-003 | Missing signature (mutating endpoint) | 1. POST /api/v1/leads without X-Signature-256 | Returns 401 Unauthorized | — |
| TC-P0-SEC-02-004 | GET request (no signature required) | 1. GET /api/v1/leads without X-Signature-256 | Succeeds (signature not required for GET) | — |

**Integration Requirements**:
- HMAC-SHA256 signature generation in Python client library
- Signature verification in FastAPI middleware
- Signature calculation on JSON.stringify(body)
- Test vectors with known HMAC values

---

#### P0-DATA-01: No Confirmation for DELETE Operations

**Test Suite**: `tests/delete-confirmation.e2e.test.ts`

| Test Case | Preconditions | Steps | Expected Result | Pass/Fail |
|-----------|---|---|---|---|
| TC-P0-DATA-01-001 | Lead exists | 1. Open lead detail 2. Click Delete button | Confirmation modal appears with lead name and "Are you sure?" message | — |
| TC-P0-DATA-01-002 | User cancels delete | 1. Click Delete 2. Modal appears 3. Click Cancel | Modal closes, lead unchanged in database | — |
| TC-P0-DATA-01-003 | User confirms delete | 1. Click Delete 2. Modal appears 3. Click Confirm | DELETE /api/v1/leads/:id request sent, lead soft-deleted | — |
| TC-P0-DATA-01-004 | Bulk delete (multiple leads) | 1. Select 5 leads 2. Click Bulk Delete | Confirmation shows "Are you sure you want to delete 5 leads?" | — |

**Integration Requirements**:
- Modal component with confirmation text
- Backend validation: DELETE requires current user authentication
- Soft delete: record marked deleted_at, not removed from database

---

#### P0-DATA-02: Orphaned Records on Delete

**Test Suite**: `tests/soft-delete-cascade.integration.test.ts`

| Test Case | Preconditions | Steps | Expected Result | Pass/Fail |
|-----------|---|---|---|---|
| TC-P0-DATA-02-001 | Lead with call transcripts | 1. Delete lead 2. Query call_transcripts for this lead | All related call_transcripts have deleted_at set | — |
| TC-P0-DATA-02-002 | Member with goals | 1. Delete member 2. Query member goals | Goals remain but marked orphaned (member_id IS NULL) | — |
| TC-P0-DATA-02-003 | Soft delete (not hard delete) | 1. Delete lead 2. Query leads with deleted_at IS NOT NULL | Lead record exists with deleted_at timestamp set | — |
| TC-P0-DATA-02-004 | Audit trail for deletion | 1. Delete lead 2. Query audit_log | Entry shows: action='DELETE', table='leads', deleted_by=user_id, deleted_at | — |

**Integration Requirements**:
- Soft delete triggers in PostgreSQL
- Cascade trigger for related records
- Audit log entry creation on delete
- deleted_by and deleted_reason fields populated

---

#### P0-DATA-03: No Central Intelligence Error Handling

**Test Suite**: `tests/worker-bee-errors.integration.test.ts`

| Test Case | Preconditions | Steps | Expected Result | Pass/Fail |
|-----------|---|---|---|---|
| TC-P0-DATA-03-001 | External API rate limit | 1. Trigger 100 rapid API queries | Error caught, logged in error_logs, workflow continues (graceful degradation) | — |
| TC-P0-DATA-03-002 | Invalid data returned | 1. Workflow receives malformed response | Error logged with context, user-friendly error returned to frontend | — |
| TC-P0-DATA-03-003 | Timeout on external API | 1. Call external API that times out | After 10 seconds, request timeout error logged, 408 returned | — |
| TC-P0-DATA-03-004 | Python agent execution fails | 1. Agent has error or fails to execute | error_logs entry created, severity=critical, alert sent to admin | — |

**Integration Requirements**:
- Centralized error handler middleware in FastAPI
- error_logs table in Supabase with all error details
- Error categorization (VALIDATION, TIMEOUT, RATE_LIMIT, DATABASE, EXTERNAL_API, INTERNAL)
- Sentry integration for P0 errors

---

### P1 Fixes: Key Test Scenarios

#### P1-DATA-04: Duplicate Form Submissions

**Key Tests**:
- Same idempotency key within 5-minute window returns cached response
- Different idempotency key creates new record
- Missing idempotency key creates new record each time
- Idempotency key auto-generated by client if not provided

#### P1-DATA-05: No Optimistic Locking

**Key Tests**:
- GET /api/v1/leads/:id returns updatedAt field
- PUT /api/v1/leads/:id with If-Match header matching current updatedAt succeeds
- PUT /api/v1/leads/:id with stale If-Match returns 409 CONFLICT
- Concurrent PUT attempts: first succeeds, second fails with 409

#### P1-SEC-03: No Audit Logging

**Key Tests**:
- audit_log entry created for every Create/Update/Delete operation
- before_value and after_value fields capture changes
- user_id links to authenticated user
- timestamp records exact time of change

#### P1-PERF-01: No Timeout Configuration

**Key Tests**:
- Request times out after 10 seconds (global timeout)
- AI analysis requests timeout after 30 seconds (extended)
- Timeout error (408) returned to client
- Request timeout logged in error_logs

---

### P2 Fixes: Integration Test Scenarios

#### P2-DATA-06: Pain Point Frequency Double-Counting

**Test**: Submit same pain point twice, verify frequency count increments only once

#### P2-DATA-07: Content Idea Status Never Transitions

**Test**: Create content idea → mark as 'approved' → verify status changed in database

#### P2-DATA-08: Member Goals Array Grows Forever

**Test**: Add 50 goals to member → delete 40 → verify only 10 remain in goals_json

#### P2-DATA-10: Lead-to-Member Conversion Workflow

**Test**: Create lead → run conversion workflow → verify new member created with member_id linked in original lead

---

## 4. Post-Fix Verification Protocol

### How to Verify Each Fix Works in Production

After deployment to production, follow this verification protocol:

### P0 Fixes

#### P0-SEC-01: User Authentication

```bash
# 1. Test login endpoint
curl -X POST https://api.centralintelligence.dev/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password": "password123"}'

# Expected: 200 OK with user object and JWT

# 2. Verify HttpOnly cookie set
# (Browser DevTools → Application → Cookies)
# Look for: auth_token (HttpOnly, Secure flags)

# 3. Test protected endpoint without auth
curl -X GET https://api.centralintelligence.dev/v1/leads

# Expected: 401 Unauthorized

# 4. Test protected endpoint with valid session
# (Include auth_token cookie from step 1)

# 5. Test account lockout
for i in {1..6}; do
  curl -X POST https://api.centralintelligence.dev/v1/auth/login \
    -d '{"email": "test@example.com", "password": "wrong"}' &
done

# Expected: After 5th failure, 423 ACCOUNT_LOCKED on 6th attempt
```

#### P0-SEC-02: HMAC Signing

```bash
# 1. Capture request body
REQUEST_BODY='{"name":"Jane","email":"jane@example.com"}'

# 2. Calculate expected HMAC
HMAC=$(echo -n "$REQUEST_BODY" | openssl dgst -sha256 -hmac "$SECRET" -hex)

# 3. Send request with HMAC header
curl -X POST https://api.centralintelligence.dev/v1/leads \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-User-Id: user_001" \
  -H "X-Signature-256: $HMAC" \
  -d "$REQUEST_BODY"

# Expected: 200/201 Created

# 4. Send with wrong HMAC
curl -X POST https://api.centralintelligence.dev/v1/leads \
  -H "X-Signature-256: wrong_hmac" \
  -d "$REQUEST_BODY"

# Expected: 401 Unauthorized
```

#### P0-DATA-01: DELETE Confirmation

```javascript
// In browser console, simulate delete workflow:

// 1. Open a lead in the web app
// 2. Click Delete button
// Expected: Modal appears with confirmation

// 3. Click Cancel
// Expected: Modal closes, lead still visible in list

// 4. Click Delete again
// 5. Click Confirm
// 6. Monitor Network tab
// Expected: DELETE /api/v1/leads/:id request sent with 200 OK response
// 7. Lead disappears from list (client-side optimistic update)
```

#### P0-DATA-02: Orphaned Records

```sql
-- In production database:

-- 1. Get a lead ID
SELECT id FROM leads WHERE name = 'Test Lead' LIMIT 1;
-- Result: lead_001

-- 2. Count call transcripts for this lead
SELECT COUNT(*) FROM call_transcripts WHERE lead_id = 'lead_001' AND deleted_at IS NULL;
-- Result: 3

-- 3. Delete the lead (via API or manually)
DELETE FROM leads WHERE id = 'lead_001'; -- Or soft delete via API

-- 4. Verify call transcripts are also deleted
SELECT COUNT(*) FROM call_transcripts WHERE lead_id = 'lead_001' AND deleted_at IS NOT NULL;
-- Expected: 3 (all transcripts soft-deleted)

-- 5. Verify audit log entry
SELECT * FROM audit_log WHERE table_name = 'leads' AND record_id = 'lead_001' AND action = 'DELETE';
-- Expected: 1 row with deleted_by, deleted_at populated
```

#### P0-DATA-03: Central Intelligence Error Handling

```bash
# 1. Trigger an error in a Python agent (e.g., invalid Airtable query)
# 2. Monitor error_logs table in Supabase
# 3. Verify entry exists with:
#    - agent_id: "CI-SAL-02"
#    - error_code: "AIRTABLE_API_ERROR" or similar
#    - severity: "error" or "critical"
#    - created_at: recent timestamp
#
# 4. Check Sentry for alert (if configured)
# 5. Verify frontend received graceful error response (not 500 Internal Server Error)
```

---

### Monitoring to Add After Each Fix

#### P0-SEC-01: Authentication Monitoring

Add these metrics to your monitoring dashboard (Prometheus):

```python
# In FastAPI endpoints, use prometheus client
from prometheus_client import Counter, Histogram

auth_login_attempts_total = Counter(
    'centralintelligence_auth_login_attempts_total',
    'Total login attempts',
    ['result']  # success/failure
)

auth_account_lockouts_total = Counter(
    'centralintelligence_auth_account_lockouts_total',
    'Total account lockouts'
)

auth_session_duration_seconds = Histogram(
    'centralintelligence_auth_session_duration_seconds',
    'Session duration in seconds'
)

# Usage
auth_login_attempts_total.labels(result='success').inc()
auth_account_lockouts_total.inc()
```

Dashboards to create:
- "Auth Health" dashboard with:
  - Failed login rate (should be < 2% of attempts)
  - Account lockout frequency
  - Average session duration
  - Top users by failed attempts (anomaly detection)

Alerts to set up:
- IF failed_login_rate > 5% for 5 minutes THEN alert "High auth failure rate"
- IF account_lockouts_total spike THEN alert "Potential brute force attack"

#### P0-SEC-02: HMAC Signing Monitoring

```python
hmac_validation_failures_total = Counter(
    'centralintelligence_hmac_validation_failures_total',
    'Total HMAC validation failures',
    ['type']  # invalid_signature/missing_signature
)

hmac_verification_duration_seconds = Histogram(
    'centralintelligence_request_signature_verification_duration_seconds',
    'Request signature verification duration'
)
```

Alerts:
- IF hmac_validation_failures > 10 in 1 minute THEN alert "HMAC validation spike"

#### P0-DATA-02: Soft Delete Monitoring

```python
soft_delete_operations_total = Counter(
    'centralintelligence_soft_delete_operations_total',
    'Total soft delete operations',
    ['table']
)

orphaned_records_detected = Gauge(
    'centralintelligence_orphaned_records_detected',
    'Count of orphaned records',
    ['table', 'cascade_status']
)
```

Dashboards:
- "Data Integrity" dashboard showing:
  - Soft deletes per day (by table)
  - Cascade success rate
  - Orphaned records count

Alerts:
- IF orphaned_records_count > 10 THEN alert "Orphaned records detected"

#### P0-DATA-03: Error Handling Monitoring

```python
workflow_errors_total = Counter(
    'centralintelligence_workflow_errors_total',
    'Total workflow errors',
    ['agent_id', 'error_category', 'severity']
)

error_resolution_time_seconds = Histogram(
    'centralintelligence_error_resolution_time_seconds',
    'Time to resolve errors'
)
```

Dashboards:
- "Error Dashboard" showing:
  - Errors per Agent (24h trend)
  - Error severity breakdown (critical/error/warning)
  - Mean time to resolution (MTTR)
  - Top 10 error codes

Alerts:
- IF workflow_errors_critical > 5 in 5 minutes THEN alert "Critical errors detected"
- IF error_rate > historical_avg * 2 THEN alert "Error rate anomaly"

---

### Regression Testing Requirements

After deploying each fix, run regression tests to ensure no new bugs introduced:

```bash
# 1. Run full test suite
pytest tests/ -v

# 2. Test all Central Intelligence endpoints
pytest tests/agents/ -v

# 3. Smoke test key user flows
pytest tests/smoke/ -v

# 4. Load test (simulate 100 concurrent users)
locust -f tests/load.py --host=https://api.centralintelligence.dev -u 100 -r 10

# 5. Security test (OWASP Top 10)
pytest tests/security/ -v

# Expected: All tests pass, no new errors in logs
```

---

## 5. Fix Dependency Map

### Which Fixes Depend on Other Fixes

```
P0-SEC-01: No User Authentication
  ├─ [No dependencies - can start immediately]
  └─ [BLOCKS: P0-SEC-02, P1-SEC-03, all other fixes that need user identity]

P0-SEC-02: HMAC Webhook Signing
  ├─ [Depends on: P0-SEC-01]
  └─ [BLOCKS: P1-DATA-04 (idempotency requires valid auth)]

P0-DATA-01: DELETE Confirmation
  ├─ [Depends on: P0-SEC-01]
  └─ [ENABLES: P0-DATA-02 (confirmation prevents accidental deletes)]

P0-DATA-02: Orphaned Records on Delete
  ├─ [Depends on: P0-DATA-01 (users must explicitly confirm delete)]
  ├─ [Depends on: P0-SEC-01 (deleted_by field needs user identity)]
  └─ [RELATED: P1-SEC-03 (audit log captures delete events)]

P0-DATA-03: Central Intelligence Error Handling
  ├─ [No dependencies - can start immediately]
  └─ [BENEFITS: All other fixes (foundation for error observability)]

P1-DATA-04: Duplicate Form Submissions
  ├─ [Depends on: P0-SEC-02 (requires signature validation in place)]
  └─ [Related: P1-DATA-05 (both deal with concurrent request handling)]

P1-DATA-05: Optimistic Locking
  ├─ [No direct dependencies]
  ├─ [Related: P1-DATA-04 (both prevent concurrent edit conflicts)]
  └─ [Requires: API contract documentation]

P1-SEC-03: Audit Logging
  ├─ [Depends on: P0-SEC-01 (needs user_id from auth)]
  └─ [Foundation for: P2-SEC-04, P2-SEC-05]

P1-PERF-01: Timeout Configuration
  ├─ [No dependencies]
  └─ [Related: P0-DATA-03 (timeout errors handled by error handler)]

P2-DATA-06, P2-DATA-07, P2-DATA-08: Data Correctness
  ├─ [No blocking dependencies]
  ├─ [Can run in parallel: each independent data table]
  └─ [Related: P1-SEC-03 (audit logs track changes)]

P2-DATA-09: call_transcripts Missing member_id
  ├─ [No blocking dependencies]
  └─ [Enables: P2-DATA-10]

P2-DATA-10: Lead-to-Member Conversion
  ├─ [Depends on: P1-DATA-04 (idempotency key for reliability)]
  ├─ [Depends on: P2-DATA-09 (member_id field must exist first)]
  └─ [Related: P0-DATA-02 (cascade rules apply)]

P2-PERF-02: Circuit Breaker
  ├─ [No dependencies]
  └─ [Works with: P0-DATA-03 (error handling foundation)]

P2-SEC-04: Predictable Webhook Paths
  ├─ [No dependencies - but low priority]
  └─ [Can defer to post-v1.0]

P2-SEC-05: Token Rotation
  ├─ [Depends on: P0-SEC-01 (auth foundation)]
  └─ [Can defer to post-v1.0]
```

---

### Recommended Implementation Order Considering Dependencies

#### Sprint 1 (Week 1-2)

Start with no-dependency items and foundation fixes:

1. **P0-SEC-01** (No User Authentication) — CRITICAL PATH
   - Blocks everything else
   - 10 story points
   - Start immediately

2. **P0-DATA-03** (Error Handling) — PARALLEL
   - No dependencies
   - Provides foundation for all other fixes
   - 5 story points

3. **P0-SEC-02** (HMAC Signing) — After P0-SEC-01
   - Depends on P0-SEC-01
   - 3 story points
   - Completes security layer

4. **P1-PERF-01** (Timeout Configuration) — PARALLEL
   - 3 story points
   - Works independently

**Sprint 1 Target**: 21 story points (17-25 realistic range)

---

#### Sprint 2 (Week 3-4)

Build on authentication foundation:

1. **P0-DATA-01** (DELETE Confirmation) — DEPENDENT on P0-SEC-01
   - 5 story points
   - Foundation for P0-DATA-02

2. **P0-DATA-02** (Orphaned Records) — DEPENDENT on P0-DATA-01
   - 8 story points
   - Key data integrity fix

3. **P1-SEC-03** (Audit Logging) — DEPENDENT on P0-SEC-01
   - 4 story points
   - Enables compliance

4. **P1-DATA-04** (Duplicate Form Submissions) — DEPENDENT on P0-SEC-02
   - 5 story points
   - Improves UX reliability

5. **P1-UX-*** (UX Fixes) — PARALLEL
   - P1-UX-01, P1-UX-02, P1-UX-03 (9 total story points)
   - No dependencies, frontend-only

**Sprint 2 Target**: 31 story points

---

#### Sprint 3 (Week 5-6)

Data correctness and locking:

1. **P1-DATA-05** (Optimistic Locking) — Can start after P0-SEC-02
   - 6 story points

2. **P2-DATA-06, P2-DATA-07, P2-DATA-08** (Data Fixes) — PARALLEL
   - 11 story points total
   - Each independent

3. **P2-DATA-09** (call_transcripts member_id) — FOUNDATION for P2-DATA-10
   - 2 story points
   - Must complete before Sprint 4

**Sprint 3 Target**: 19 story points

---

#### Sprint 4 (Week 7-8)

Complex workflows and performance:

1. **P2-DATA-10** (Lead-to-Member Conversion) — DEPENDENT on P2-DATA-09 + P1-DATA-04
   - 8 story points
   - Complex feature

2. **P2-PERF-02** (Circuit Breaker) — Can start independently
   - 5 story points

**Sprint 4 Target**: 13 story points

---

#### Sprint 5+ (Post-v1.0)

Deferred security improvements:

1. **P2-SEC-04** (Predictable Webhook Paths)
2. **P2-SEC-05** (Token Rotation)

---

### Parallel Implementation Opportunities

These can run simultaneously (no dependency conflicts):

| Sprint | Parallel Track 1 | Parallel Track 2 | Parallel Track 3 |
|--------|---|---|---|
| Sprint 1 | P0-SEC-01 (auth) | P0-DATA-03 (errors) | P1-PERF-01 (timeouts) |
| Sprint 2 | P0-DATA-01 + P0-DATA-02 (deletes) | P1-SEC-03 (audit) | P1-UX-01 + P1-UX-02 + P1-UX-03 |
| Sprint 3 | P1-DATA-05 (locking) | P2-DATA-06/07/08 (data fixes) | P2-DATA-09 (prep for conversion) |
| Sprint 4 | P2-DATA-10 (conversion workflow) | P2-PERF-02 (circuit breaker) | — |

---

## 6. Login / Authentication System

Implemented using **Supabase Auth + FastAPI + JWT tokens**

### Architecture Overview

- **Auth Provider**: Supabase Auth (PostgreSQL-backed)
- **Token Type**: JWT (JSON Web Tokens)
- **Session Duration**: 24 hours
- **Token Storage**: HttpOnly cookies (secure)
- **Account Lockout**: 5 failed attempts → 15-minute lockout
- **Password Hashing**: bcrypt (10 rounds minimum)

### Database Schema

```sql
CREATE TABLE users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email VARCHAR(255) UNIQUE NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  email_verified_at TIMESTAMP,
  failed_login_attempts INT DEFAULT 0,
  locked_until TIMESTAMP,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_users_email ON users(email);
```

### FastAPI Authentication Middleware

```python
from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthCredentials
import jwt

security = HTTPBearer()

async def get_current_user(credentials: HTTPAuthCredentials = Depends(security)):
    """Extract and validate JWT token from request"""
    try:
        payload = jwt.decode(
            credentials.credentials,
            os.getenv("JWT_SECRET"),
            algorithms=["HS256"]
        )
        user_id = payload.get("user_id")
        email = payload.get("email")

        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")

        return {"id": user_id, "email": email}
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
```

---

## 7. Error Handling Layer

Implemented using **FastAPI exception handlers + Pydantic validators + Sentry**

### Error Categories

- **VALIDATION**: Input validation failed (422)
- **TIMEOUT**: Request timeout (408)
- **RATE_LIMIT**: Rate limit exceeded (429)
- **DATABASE**: Database error (500)
- **EXTERNAL_API**: External API failure (503)
- **INTERNAL**: Internal server error (500)
- **AUTH**: Authentication/authorization error (401/403)

### Error Response Format

```json
{
  "error": "VALIDATION",
  "message": "An error occurred. Please try again or contact support.",
  "error_id": "err_abc123"
}
```

Error IDs can be used to look up full error details in error_logs table.

---

## 8. Edge Case Handlers

[Detailed edge case handling patterns covered by individual fixes above - includes concurrent edits, duplicate submissions, orphaned records, stale data, partial failures, transcription edge cases, conflicts, and queue overflow]

---

## 9. Summary Tables

### New Database Tables (4 new tables)

| Table Name | Storage | Purpose | Sprint | Created At |
|------------|---------|---------|--------|-----------|
| `users` | Supabase (PostgreSQL) | User accounts, credentials, roles | Sprint 1 | 2026-03-19 |
| `error_logs` | Supabase (PostgreSQL) | Central Intelligence error tracking and resolution | Sprint 1 | 2026-03-19 |
| `audit_log` | Supabase (PostgreSQL) | All user actions for security/compliance | Sprint 2 | 2026-04-02 |
| `transcription_queue` | Supabase (PostgreSQL) | Async transcription job queue | Sprint 3 | 2026-04-16 |

---

### Existing Table Modifications (6 field changes)

| Table | Field Added/Changed | Change Type | Sprint | Reason | Migration Effort |
|-------|--------------------|-----------|----|--------|---------|
| `leads` (PostgreSQL) | `deleted_at` (DateTime, nullable) | Add field | Sprint 2 | Soft delete (P0-DATA-02) | Low (add column) |
| `leads` (PostgreSQL) | `member_id` (String, nullable) | Add field | Sprint 4 | Lead-to-member conversion (P2-DATA-10) | Low (add column) |
| `members` (PostgreSQL) | `deleted_at` (DateTime, nullable) | Add field | Sprint 2 | Soft delete (P0-DATA-02) | Low (add column) |
| `members` (PostgreSQL) | `goals_json` (JSONB, replaces `goals`) | Modify field | Sprint 3 | Structured goals | Medium (data transformation) |
| `call_transcripts` (PostgreSQL) | `member_id` (String, nullable) | Add field | Sprint 2 | Coaching/accountability linkage | Low (add column) |
| `call_transcripts` (PostgreSQL) | `url_hash`, `confidence_score`, `low_confidence` | Add fields | Sprint 2 | Duplicate prevention + quality scoring | Low (add columns) |
| `pain_points` (PostgreSQL) | `contributing_transcripts` (JSON array) | Add field | Sprint 3 | Frequency double-count prevention | Medium (track references) |
| `content_ideas` (PostgreSQL) | `status` expanded (6 values), add `used_by` | Modify field | Sprint 3 | Status lifecycle | Medium (enum expansion + field) |

---

### New Python Agents / FastAPI Endpoints (5 new components)

| Component ID | Name | Purpose | Sprint | Implements |
|---|---|---|---|---|
| CI-CORE-AUTH | Authentication Handler Endpoints | POST /api/v1/auth/login, POST /api/v1/auth/change-password, GET /api/v1/auth/me | Sprint 1 | P0-SEC-01 |
| CI-CORE-ERR | Error Handler Middleware | Centralized error handling and logging via exception handlers | Sprint 1 | P0-DATA-03 |
| CI-OPS-QUEUE | Transcription Queue Manager Agent | Async queue processing with concurrency control | Sprint 3 | EC-14 |
| CI-OPS-MIGRATE | Data Migration Agent | Blue-green Supabase data migration | Sprint 4 | Infrastructure |
| CI-CORE-MONITOR | Sync Monitor & Health Checker | Continuous sync health monitoring via FastAPI health endpoint | Sprint 2 | Ongoing monitoring |

---

### New UI Components (15 new components)

| Component | File Path | Purpose | Sprint | Fix ID |
|---|---|---|---|---|
| `<LoginForm />` | `src/components/auth/LoginForm.tsx` | Email/password login with error handling | Sprint 1 | P0-SEC-01 |
| `<UserMenu />` | `src/components/auth/UserMenu.tsx` | User profile dropdown with logout | Sprint 1 | P0-SEC-01 |
| `<ProtectedRoute />` | `src/components/routing/ProtectedRoute.tsx` | Route protection wrapper | Sprint 1 | P0-SEC-01 |
| `<DeleteConfirmation />` | `src/components/modals/DeleteConfirmation.tsx` | Modal for DELETE confirmation | Sprint 2 | P0-DATA-01 |
| `<LoadingSpinner />` | `src/components/ui/LoadingSpinner.tsx` | Request loading indicator | Sprint 2 | P1-UX-01 |
| `<EmptyState />` | `src/components/ui/EmptyState.tsx` | Empty list state with illustration | Sprint 2 | P1-UX-02 |
| `<Toast />` | `src/components/notifications/Toast.tsx` | Toast notification system | Sprint 2 | P1-UX-03 |
| `<ToastContainer />` | `src/components/notifications/ToastContainer.tsx` | Toast notification portal | Sprint 2 | P1-UX-03 |
| `<ErrorBoundary />` | `src/components/error/ErrorBoundary.tsx` | React error boundary | Sprint 1 | P0-DATA-03 |
| `<ErrorCard />` | `src/components/error/ErrorCard.tsx` | User-friendly error display | Sprint 1 | P0-DATA-03 |
| `<ConnectionStatus />` | `src/components/status/ConnectionStatus.tsx` | Online/offline indicator | Sprint 2 | P1-UX-01 |
| `<AuditLog />` | `src/components/admin/AuditLog.tsx` | Audit log viewer | Sprint 2 | P1-SEC-03 |
| `<ErrorDashboard />` | `src/components/admin/ErrorDashboard.tsx` | Error monitoring dashboard | Sprint 1 | P0-DATA-03 |
| `<FormWithOptimisticUpdate />` | `src/components/forms/FormWithOptimisticUpdate.tsx` | Form with optimistic locking support | Sprint 3 | P1-DATA-05 |
| `<ConversionWorkflow />` | `src/components/workflows/LeadToMember.tsx` | Lead-to-member conversion UI | Sprint 4 | P2-DATA-10 |

---

### Sprint Integration Summary

| Sprint | Period | Primary Focus | P0 Completion | P1 Target | P2 Target |
|--------|--------|---|---|---|---|
| Sprint 1 | 2026-03-19 to 2026-04-02 | Auth + Error Foundation | 60% (SEC-01, DATA-03) | 0% | 0% |
| Sprint 2 | 2026-04-02 to 2026-04-16 | Data Integrity + UX | 100% (all P0 complete) | 60% (UX, DATA-04) | 20% (DATA-09) |
| Sprint 3 | 2026-04-16 to 2026-04-30 | Locking + Data Fixes | 100% | 80% | 40% (data quality) |
| Sprint 4 | 2026-04-30 to 2026-05-14 | Complex Workflows | 100% | 100% | 70% (DATA-10) |
| Sprint 5+ | 2026-05-14+ | Deferred Security | 100% | 100% | 100% (post-v1.0 items) |

---

**Critical Fixes v3.0.0 — Central Intelligence (Central Intelligence) with Python + FastAPI + Claude SDK**
**Tech Stack**: Python 3.11+ | FastAPI | SQLAlchemy ORM | Supabase (PostgreSQL) | Pydantic v2 | Sentry | JWT | HMAC-SHA256
**Last updated**: 2026-03-29
**Enhancements**: Replaced all n8n references with Python + FastAPI patterns, Supabase for database, Sentry for error monitoring, Next.js for frontend. Maintained all 20 critical fixes with business logic intact. Added comprehensive Python code examples for error handling, authentication, idempotency, optimistic locking, and circuit breaker patterns.
