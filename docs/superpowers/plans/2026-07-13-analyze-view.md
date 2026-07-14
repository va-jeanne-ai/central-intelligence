# "Analyze this view" Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** On the Appointments, Sales Calls, Leads, and Members pages, an "Analyze this view" button opens a drawer with an LLM narrative grounded entirely in server-computed aggregates of the currently filtered dataset.

**Architecture:** The frontend serializes the page's current filter state (same query params as the list endpoint) to `POST /api/v1/analyze/{surface}`. A per-surface aggregator registry re-runs the filtered query server-side and computes aggregates; a shared narrative step (reusing `call_claude_for_json` from `overall_insight.py`) turns aggregates into `{narrative, highlights, hypotheses}`. Filter WHERE-building is extracted into a shared module so the list endpoints and aggregators use identical semantics by construction.

**Tech Stack:** FastAPI + SQLAlchemy (async) + raw SQL via `text()`, Anthropic SDK (existing plumbing), Next.js App Router + the project's atomic UI components.

**Spec:** `docs/superpowers/specs/2026-07-13-analyze-view-design.md`

## Global Constraints

- **NO automated tests** (user's standing rule): no pytest files, no mock mode. Verification = curl / browser against the real running stack with real data, plus the manual test doc in Task 12. The user performs final verification personally.
- **No mock_mode in new code**: missing `settings.anthropic_api_key` → HTTP 503 with a clear message. Never a canned response.
- **Branch:** all work on `feat/analyze-view` (already created). Commit at the end of every task. **NO `Co-Authored-By: Claude` trailer on any commit.**
- **Frontend rules (project CLAUDE.md):** use atomic components from `frontend/src/components/ui/` (`Button`, `Card`, `Skeleton`, `EmptyState`); never `window.alert/confirm/prompt`; toasts via `@/lib/toast`. Next dev server always on port 3000 (kill stale process first, never auto-bump).
- **Refactor rule:** when extracting filter builders out of routes, MOVE code verbatim — do not "improve" the SQL semantics. Behavior of the four list endpoints must be byte-identical.
- **PII rule:** aggregates only go to the LLM — breakdown labels (rep names, statuses, sources) yes; contact emails/phones/raw rows never.

### Verification prereqs (used by every task's verify step)

```bash
# Terminal 1 — backend
cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000
# Terminal 2 — frontend (port 3000, kill stale first)
lsof -ti:3000 | xargs kill -9 2>/dev/null; cd frontend && npm run dev
# Get a token: log in at http://localhost:3000, then in DevTools → Network,
# copy the Authorization header value (Bearer …) from any /api/v1 request.
export TOKEN="<paste the raw token, without the 'Bearer ' prefix>"
```

---

### Task 1: Shared filter-builder module + appointments extraction

**Files:**
- Create: `backend/app/repositories/list_filters.py`
- Modify: `backend/app/routes/appointments.py` (the `_parse_date_boundary` helper and the WHERE-building block inside `list_appointments`, ~lines 80–195)

**Interfaces:**
- Produces: `build_appointment_where(*, status, search, window, from_date, to_date, start, end, rep) -> tuple[str, dict]` returning `(where_sql, params)`; constant `APPOINTMENTS_FROM_SQL`; helper `parse_date_boundary(value, *, end_of_day) -> datetime | None`. Tasks 5 and the route refactor consume these.

- [ ] **Step 1: Create `backend/app/repositories/list_filters.py`**

Move `_parse_date_boundary` out of `appointments.py` (public name `parse_date_boundary`, same body — it raises `HTTPException(400)` on invalid dates, keep that) and add the appointments builder. The WHERE-building lines are MOVED verbatim from `list_appointments`:

```python
"""Shared list-filter builders.

Single source of truth for the WHERE semantics of the filterable list
endpoints (appointments, leads, team directory, calls). Both the list
routes and the analyze-view aggregators (app.analytics.view_analysis)
build their filters here, so "analyze this view" aggregates exactly the
dataset the list shows — by construction, not by parallel maintenance.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException

# FROM clause the appointments WHERE parts are written against (aliases a/l/r).
APPOINTMENTS_FROM_SQL = (
    "FROM appointments a "
    "LEFT JOIN leads l ON l.id = a.lead_id "
    "LEFT JOIN sales_reps r ON r.rep_id = a.rep_id"
)


def parse_date_boundary(value: str | None, *, end_of_day: bool) -> datetime | None:
    # ← moved verbatim from app/routes/appointments.py::_parse_date_boundary
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid date: {value!r}") from exc
    if end_of_day and len(str(value)) <= 10:
        dt = dt.replace(hour=23, minute=59, second=59, microsecond=999999)
    return dt


def build_appointment_where(
    *,
    status: str | None = None,
    search: str | None = None,
    window: str = "all",
    from_date: str | None = None,
    to_date: str | None = None,
    start: str | None = None,
    end: str | None = None,
    rep: str | None = None,
) -> tuple[str, dict]:
    """(where_sql, params) for the appointments list — see APPOINTMENTS_FROM_SQL."""
    where_parts: list[str] = ["a.deleted_at IS NULL"]
    params: dict[str, object] = {}

    if status:
        where_parts.append("LOWER(a.status) = :status_filter")
        params["status_filter"] = status.lower()
    if search:
        where_parts.append(
            "(LOWER(COALESCE(a.contact_name, l.name)) LIKE :search "
            "OR LOWER(a.contact_email) LIKE :search)"
        )
        params["search"] = f"%{search.lower()}%"
    if window == "upcoming":
        where_parts.append("a.scheduled_at >= NOW() AND LOWER(a.status) <> 'cancelled'")
    elif window == "this_week":
        where_parts.append(
            "a.scheduled_at >= NOW() AND a.scheduled_at < NOW() + INTERVAL '7 days' "
            "AND LOWER(a.status) <> 'cancelled'"
        )
    if from_date:
        where_parts.append("a.scheduled_at >= :from_date")
        params["from_date"] = from_date
    if to_date:
        where_parts.append("a.scheduled_at <= :to_date")
        params["to_date"] = to_date
    start_dt = parse_date_boundary(start, end_of_day=False)
    end_dt = parse_date_boundary(end, end_of_day=True)
    if start_dt:
        where_parts.append("a.scheduled_at >= :start_date")
        params["start_date"] = start_dt
    if end_dt:
        where_parts.append("a.scheduled_at <= :end_date")
        params["end_date"] = end_dt
    if rep:
        where_parts.append("a.rep_id = :rep_id")
        params["rep_id"] = rep

    return " AND ".join(where_parts), params
```

- [ ] **Step 2: Refactor `list_appointments` to use the builder**

In `backend/app/routes/appointments.py`: delete `_parse_date_boundary` and the moved WHERE block; add the import and replace the block with:

```python
from app.repositories.list_filters import (
    APPOINTMENTS_FROM_SQL,
    build_appointment_where,
)
```

Inside `list_appointments`, after the sort sanitization, replace everything from `where_parts: list[str] = […]` down to `where_sql = " AND ".join(where_parts)` with:

```python
    where_sql, params = build_appointment_where(
        status=status, search=search, window=window,
        from_date=from_date, to_date=to_date, start=start, end=end, rep=rep,
    )
```

And replace the local `from_sql = "FROM appointments a LEFT JOIN …"` line with `from_sql = APPOINTMENTS_FROM_SQL`. Everything below (COUNT, page fetch, response assembly) is untouched. If anything else in the file referenced `_parse_date_boundary`, update it to the imported `parse_date_boundary`.

- [ ] **Step 3: Verify the list endpoint is unchanged**

```bash
curl -s -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/appointments?status=booked&per_page=5" | python3 -m json.tool | head -30
curl -s -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/appointments?start=2026-06-01&end=2026-06-30&per_page=1" | python3 -c "import sys,json; print(json.load(sys.stdin)['total'])"
```
Expected: first returns appointments with the filtered status and a sane `total`; second prints the June count. Both must match the values these same URLs returned BEFORE the refactor (run them once before editing and note the totals).

- [ ] **Step 4: Commit**

```bash
git add backend/app/repositories/list_filters.py backend/app/routes/appointments.py
git commit -m "refactor: extract appointments list WHERE-building into shared list_filters"
```

---

### Task 2: Extract leads + team-directory filter builders

**Files:**
- Modify: `backend/app/repositories/list_filters.py` (append)
- Modify: `backend/app/routes/leads.py` (move `_API_TO_DB_STATUSES` [~line 186] and `_parse_date` [~line 143] out; refactor WHERE block in `list_leads` ~lines 235–283)
- Modify: `backend/app/routes/members.py` (refactor WHERE block in `team_directory` ~lines 271–300)

**Interfaces:**
- Produces: `build_lead_where(*, status, source, search, entry_from, entry_to) -> tuple[str, dict]` (FROM is plain `FROM leads`); `build_team_where(*, search, status) -> tuple[str, dict]`; constant `TEAM_FROM_SQL`; moved public names `API_TO_DB_STATUSES` and `parse_plain_date`. Tasks 7–8 consume these.

- [ ] **Step 1: Append to `list_filters.py`**

`_API_TO_DB_STATUSES` and `_parse_date` are MOVED from `leads.py` (public names below); `leads.py` line 1270 also uses the mapping, so it will import it back. The WHERE bodies are moved verbatim from `list_leads` / `team_directory`:

```python
from datetime import date

# ── Leads ────────────────────────────────────────────────────────────────────

API_TO_DB_STATUSES: dict[str, list[str]] = {
    # ← moved verbatim from app/routes/leads.py::_API_TO_DB_STATUSES,
    #    including the "applications" composite entry and its comment
    "appointment_set": ["appointment-set"],
    "closed_won": ["sale"],
    "closed_lost": ["lost"],
    "new": ["new"],
    "contacted": ["contacted"],
    "qualified": ["qualified"],
    "stale": ["stale"],
    "applications": ["qualified", "appointment-set"],
}


def parse_plain_date(value: str | None) -> date | None:
    # ← moved verbatim from app/routes/leads.py::_parse_date (invalid → None)
    if not value:
        return None
    try:
        return date.fromisoformat(value.strip())
    except (TypeError, ValueError):
        return None


def build_lead_where(
    *,
    status: str | None = None,
    source: str | None = None,
    search: str | None = None,
    entry_from: str | None = None,
    entry_to: str | None = None,
) -> tuple[str, dict]:
    """(where_sql, params) for the leads list — FROM leads, unqualified columns."""
    where_parts: list[str] = ["deleted_at IS NULL"]
    params: dict[str, object] = {}

    if status:
        db_statuses = API_TO_DB_STATUSES.get(status.lower())
        if db_statuses:
            if len(db_statuses) == 1:
                where_parts.append("LOWER(status) = :status_filter")
                params["status_filter"] = db_statuses[0]
            else:
                placeholders = ", ".join(f":status_{i}" for i in range(len(db_statuses)))
                where_parts.append(f"LOWER(status) IN ({placeholders})")
                for i, s in enumerate(db_statuses):
                    params[f"status_{i}"] = s
        else:
            where_parts.append("1 = 0")
    if source:
        where_parts.append("LOWER(source) = :source_filter")
        params["source_filter"] = source.lower()
    if search:
        where_parts.append(
            "(LOWER(name) LIKE :search_pattern OR LOWER(email) LIKE :search_pattern)"
        )
        params["search_pattern"] = f"%{search.lower()}%"
    entry_lo = parse_plain_date(entry_from)
    if entry_lo is not None:
        where_parts.append("entry_date >= :entry_from")
        params["entry_from"] = entry_lo
    entry_hi = parse_plain_date(entry_to)
    if entry_hi is not None:
        where_parts.append("entry_date <= :entry_to")
        params["entry_to"] = entry_hi

    return " AND ".join(where_parts), params


# ── Team directory (the /members page) ──────────────────────────────────────

TEAM_FROM_SQL = "FROM sales_reps sr LEFT JOIN rep_overrides ro ON ro.rep_id = sr.rep_id"

_EFF_NAME = "COALESCE(ro.full_name, sr.full_name)"
_EFF_EMAIL = "COALESCE(ro.email, sr.email)"
_EFF_STATUS = "COALESCE(ro.status, sr.status)"


def build_team_where(
    *, search: str | None = None, status: str | None = None
) -> tuple[str, dict]:
    """(where_sql, params) for the team directory — see TEAM_FROM_SQL."""
    where = ["1 = 1"]
    params: dict[str, object] = {}
    if search:
        where.append(f"({_EFF_NAME} ILIKE :q OR {_EFF_EMAIL} ILIKE :q)")
        params["q"] = f"%{search.strip()}%"
    if status and status != "all":
        where.append(f"LOWER({_EFF_STATUS}) = :status")
        params["status"] = status.lower()
    return " AND ".join(where), params
```

- [ ] **Step 2: Refactor `list_leads`**

In `leads.py`: delete `_API_TO_DB_STATUSES` and `_parse_date`; import `from app.repositories.list_filters import API_TO_DB_STATUSES, build_lead_where`; update the line-1270 usage to `API_TO_DB_STATUSES`; replace the WHERE block in `list_leads` (from `where_parts: list[str] = […]` through `where_sql = " AND ".join(where_parts)`) with:

```python
    where_sql, params = build_lead_where(
        status=status, source=source, search=search,
        entry_from=entry_from, entry_to=entry_to,
    )
```

Grep first: `grep -n "_parse_date\|_API_TO_DB" backend/app/routes/leads.py` — every remaining reference must be updated to the imported names.

- [ ] **Step 3: Refactor `team_directory`**

In `members.py`: import `from app.repositories.list_filters import TEAM_FROM_SQL, build_team_where`; inside `team_directory` replace the `eff_*` locals + `where`/`params` construction with `where_sql, params = build_team_where(search=search, status=status)`, and use them in the query. The SELECT's column expressions still need the effective coalesces — keep them inline in the SELECT (only the WHERE + FROM move):

```python
    where_sql, params = build_team_where(search=search, status=status)
    rows = (await session.execute(text(
        f"""
        SELECT
            sr.rep_id,
            COALESCE(ro.full_name, sr.full_name) AS name,
            COALESCE(ro.email, sr.email)         AS email,
            COALESCE(ro.role, sr.role)           AS role,
            COALESCE(ro.status, sr.status)       AS status,
            sr.hired_at, sr.capabilities,
            (SELECT COUNT(*) FROM calls c
             WHERE c.deleted_at IS NULL AND c.call_owner = sr.full_name) AS calls_count
        {TEAM_FROM_SQL}
        WHERE {where_sql}
        ORDER BY calls_count DESC, name ASC
        """
    ), params)).mappings().all()
```

- [ ] **Step 4: Verify both endpoints unchanged**

```bash
curl -s -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/leads?status=applications&per_page=1" | python3 -c "import sys,json; print(json.load(sys.stdin)['total'])"
curl -s -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/members/team?status=active" | python3 -c "import sys,json; print(json.load(sys.stdin)['total'])"
```
Expected: same totals as before the refactor (capture them first).

- [ ] **Step 5: Commit**

```bash
git add backend/app/repositories/list_filters.py backend/app/routes/leads.py backend/app/routes/members.py
git commit -m "refactor: extract leads + team-directory WHERE-building into list_filters"
```

---

### Task 3: Extract the calls filter clauses (ORM)

**Files:**
- Modify: `backend/app/analytics/team.py` (receive `call_owner_match_values`, moved from `ci.py` ~line 284)
- Modify: `backend/app/repositories/list_filters.py` (append `build_call_filters`)
- Modify: `backend/app/routes/ci.py` (refactor `list_calls` ~lines 450–530)

**Interfaces:**
- Produces: `build_call_filters(*, call_type, call_result, call_owner, source, search, date_from, date_to, start, end, rep, roster) -> list` of SQLAlchemy clause elements to splat into `.where(*clauses)`; `call_owner_match_values(rep: RepRow) -> list[str]` now lives in `app.analytics.team`. Task 6 consumes these.

- [ ] **Step 1: Move `call_owner_match_values` to `app/analytics/team.py`**

Cut the function from `ci.py` (verbatim, it's pure) and paste it into `team.py` next to `RepRow`/`resolve_rep`. In `ci.py`, extend the existing import: `from app.analytics.team import RepRow, call_owner_match_values, resolve_rep`. Grep `call_owner_match_values` across `backend/` and fix every import site.

- [ ] **Step 2: Append `build_call_filters` to `list_filters.py`**

The clause bodies are MOVED verbatim from `list_calls` (each `_both(x)` becomes `clauses.append(x)`):

```python
from sqlalchemy import func, or_, select

from app.analytics.team import RepRow, call_owner_match_values
from app.models.operational import Call, Lead   # ← mirror ci.py's model imports;
                                                #   check with: grep -n "^from app.models" backend/app/routes/ci.py


def build_call_filters(
    *,
    call_type: str | None = None,
    call_result: str | None = None,
    call_owner: str | None = None,
    source: str | None = None,
    search: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    start: str | None = None,
    end: str | None = None,
    rep: str | None = None,
    roster: list[RepRow],
) -> list:
    """SQLAlchemy filter clauses for the calls list — apply with .where(*clauses)."""
    clauses: list = []
    if call_type:
        types = [t.strip() for t in call_type.split(",") if t.strip()]
        if types:
            clauses.append(Call.call_type.in_(types))
    if call_result:
        results = [r.strip() for r in call_result.split(",") if r.strip()]
        if len(results) == 1:
            clauses.append(Call.call_result == results[0])
        elif results:
            clauses.append(Call.call_result.in_(results))
    if call_owner:
        clauses.append(Call.call_owner == call_owner)
    if source:
        clauses.append(Call.source == source)
    if search:
        like = f"%{search.strip()}%"
        lead_match = select(Lead.id).where(
            or_(Lead.name.ilike(like), Lead.email.ilike(like))
        )
        clauses.append(or_(
            Call.id.ilike(like),
            Call.call_owner.ilike(like),
            Call.lead_id.in_(lead_match),
        ))
    if date_from:
        clauses.append(Call.date >= datetime.fromisoformat(date_from))
    if date_to:
        clauses.append(Call.date <= datetime.fromisoformat(date_to))
    if start:
        clauses.append(Call.date >= datetime.fromisoformat(start))
    if end:
        end_dt = datetime.fromisoformat(end)
        if len(end) <= 10:
            end_dt = end_dt.replace(hour=23, minute=59, second=59, microsecond=999999)
        clauses.append(Call.date <= end_dt)
    if rep:
        rep_row = next((r for r in roster if r.rep_id == rep), None)
        if rep_row is None:
            clauses.append(Call.id.is_(None))
        else:
            match_values = call_owner_match_values(rep_row)
            clauses.append(func.lower(func.trim(Call.call_owner)).in_(match_values))
    return clauses
```

- [ ] **Step 3: Refactor `list_calls`**

In `ci.py`, keep the roster fetch (still needed for per-row owner resolution), delete the `_both` helper and every inline `if <filter>:` block, and after the roster fetch write:

```python
    clauses = build_call_filters(
        call_type=call_type, call_result=call_result, call_owner=call_owner,
        source=source, search=search, date_from=date_from, date_to=date_to,
        start=start, end=end, rep=rep, roster=roster,
    )
    stmt = select(Call).where(*clauses)
    count_stmt = select(func.count()).select_from(Call).where(*clauses)
```

Import: `from app.repositories.list_filters import build_call_filters`. `.where(*[])` is a no-op, so the unfiltered case is preserved.

- [ ] **Step 4: Verify**

```bash
curl -s -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/ci/calls?call_type=Sales,Discovery,Outbound&limit=1" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['pagination']['total'])"
```
Expected: same total as pre-refactor (capture first). Also spot-check a `rep=` and a `search=` filter the same way.

- [ ] **Step 5: Commit**

```bash
git add backend/app/analytics/team.py backend/app/repositories/list_filters.py backend/app/routes/ci.py
git commit -m "refactor: extract calls filter clauses into list_filters"
```

---

### Task 4: view_analysis package — registry + narrative step

**Files:**
- Create: `backend/app/analytics/view_analysis/__init__.py`
- Create: `backend/app/analytics/view_analysis/narrative.py`

**Interfaces:**
- Produces: `Surface` dataclass; `register(surface)`; `get_surface(key) -> Surface | None`; `all_surfaces() -> list[Surface]`; `async synthesize_view_analysis(*, label, describe, filters_echo, aggregates) -> dict` returning `{"narrative": str, "highlights": list[str], "hypotheses": list[str], "model": str}`. Raises `HTTPException(503)` when no API key. Tasks 5–9 consume these.
- Consumes: `call_claude_for_json` from `app.analytics.overall_insight` (existing: `(system_prompt, user_prompt, *, max_tokens) -> dict`, sync).

- [ ] **Step 1: Write `__init__.py`**

```python
"""View analysis — grounded LLM narrative over the current filtered list view.

Each filterable list surface registers a Surface here. The /analyze/{surface}
route looks the surface up, re-runs the filtered query via its aggregate()
(which builds filters from app.repositories.list_filters — the same builders
the list endpoints use), and hands the aggregates to the narrative step.
Numbers in the narrative can only come from the aggregates.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True)
class Surface:
    key: str                 # URL segment: /analyze/{key}
    label: str               # human label: "appointments"
    describe: str            # one paragraph telling the LLM what the fields mean
    parse_filters: Callable[[Mapping[str, str]], dict]      # query params -> builder kwargs
    echo: Callable[[dict], str]                             # kwargs -> human-readable filter echo
    aggregate: Callable[[AsyncSession, dict], Awaitable[dict]]


_REGISTRY: dict[str, Surface] = {}


def register(surface: Surface) -> Surface:
    _REGISTRY[surface.key] = surface
    return surface


def get_surface(key: str) -> Surface | None:
    return _REGISTRY.get(key)


def all_surfaces() -> list[Surface]:
    return list(_REGISTRY.values())


# Import for side effect: each module registers its Surface at import time.
# These imports MUST stay at the bottom (they import this module back).
from app.analytics.view_analysis import (  # noqa: E402,F401
    appointments,
    leads,
    sales_calls,
    team_members,
)
```

Note: Tasks 5–8 create those four modules. Until they exist this `__init__` won't import — that's fine; Task 5 is the first point where anything imports the package. If you must import it standalone before Task 5, comment the bottom import block temporarily and restore it in Task 5.

- [ ] **Step 2: Write `narrative.py`**

```python
"""Shared narrative step for view analysis — aggregates in, grounded JSON out."""

from __future__ import annotations

import asyncio
import json
import logging

from fastapi import HTTPException

from app.analytics.overall_insight import call_claude_for_json
from app.config import settings

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are the Central Intelligence analyst for a coaching/consulting business. "
    "The user is looking at a filtered list view; you are given the ONLY facts you "
    "may use: a JSON block of aggregates computed from that filtered dataset.\n\n"
    "Hard rules:\n"
    "1. Every number you write must appear verbatim in the aggregates JSON (counts, "
    "percentages, averages). Never derive, extrapolate, or invent numbers.\n"
    "2. Facts go in the narrative and highlights. Interpretations, guesses, and "
    "possible explanations go ONLY in hypotheses, phrased as hypotheses "
    "(e.g. 'One possible explanation is …').\n"
    "3. If row_count is small, say the data is too thin for strong conclusions "
    "rather than stretching.\n\n"
    "Respond with ONLY a JSON object, no prose around it, of exactly this shape:\n"
    "{\n"
    '  "narrative": "2-4 short paragraphs separated by a blank line (\\n\\n)",\n'
    '  "highlights": ["3-5 one-line factual takeaways"],\n'
    '  "hypotheses": ["0-3 clearly speculative interpretations"]\n'
    "}"
)


def _build_user_prompt(label: str, describe: str, filters_echo: str, aggregates: dict) -> str:
    return (
        f"Surface: {label}\n"
        f"What the fields mean: {describe}\n"
        f"Active filters: {filters_echo}\n\n"
        "=== Aggregates of the filtered dataset (JSON) ===\n"
        + json.dumps(aggregates, default=str, indent=2)
    )


async def synthesize_view_analysis(
    *, label: str, describe: str, filters_echo: str, aggregates: dict
) -> dict:
    """Return {narrative, highlights, hypotheses, model}. 503 when no API key.

    Deliberately NO mock_mode handling — every analyze call is a real LLM call
    (per the 2026-07-13 spec decision).
    """
    if not settings.anthropic_api_key:
        raise HTTPException(
            status_code=503,
            detail="Anthropic API key not configured — view analysis unavailable.",
        )
    user_prompt = _build_user_prompt(label, describe, filters_echo, aggregates)
    # call_claude_for_json is sync (used from Celery elsewhere) — off the event loop.
    parsed = await asyncio.to_thread(
        call_claude_for_json, _SYSTEM_PROMPT, user_prompt, max_tokens=1500
    )
    narrative = str(parsed.get("narrative", "")).strip()
    if not narrative:
        raise HTTPException(status_code=502, detail="Analysis came back empty — try again.")
    highlights = [str(x) for x in parsed.get("highlights", []) if str(x).strip()][:5]
    hypotheses = [str(x) for x in parsed.get("hypotheses", []) if str(x).strip()][:3]
    from app.analytics.overall_insight import MODEL  # single source for the model id
    return {
        "narrative": narrative,
        "highlights": highlights,
        "hypotheses": hypotheses,
        "model": MODEL,
    }
```

- [ ] **Step 3: Verify it compiles**

```bash
cd backend && .venv/bin/python -c "from app.analytics.view_analysis.narrative import synthesize_view_analysis; print('ok')"
```
Expected: `ok` (narrative.py has no dependency on the four surface modules).

- [ ] **Step 4: Commit**

```bash
git add backend/app/analytics/view_analysis/
git commit -m "feat: view_analysis registry + grounded narrative step"
```

---

### Task 5: Appointments aggregator

**Files:**
- Create: `backend/app/analytics/view_analysis/appointments.py`

**Interfaces:**
- Consumes: `APPOINTMENTS_FROM_SQL`, `build_appointment_where` (Task 1); `Surface`, `register` (Task 4).
- Produces: registered surface `key="appointments"`. Aggregate dict shape (same for all surfaces): `{"row_count": int, "breakdowns": {name: [{"label": str, "count": int, "pct": float}]}, "series": {"bucket": "week", "points": [{"week_start": "YYYY-MM-DD", "count": int}]} | None, "extras": dict}`.

- [ ] **Step 1: Write the module**

```python
"""Analyze-view aggregator: appointments (mirrors GET /appointments filters)."""

from __future__ import annotations

from collections.abc import Mapping

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.view_analysis import Surface, register
from app.repositories.list_filters import APPOINTMENTS_FROM_SQL, build_appointment_where

_DESCRIBE = (
    "Appointments booked with sales reps. Each row has a status (e.g. booked, "
    "completed, cancelled, no-show), a scheduled date/time, the rep it belongs to, "
    "and a source. 'unassigned' means no rep is linked."
)


def _parse_filters(qp: Mapping[str, str]) -> dict:
    return {
        "status": qp.get("status") or None,
        "search": qp.get("search") or None,
        "window": qp.get("window") or "all",
        "from_date": qp.get("from") or None,
        "to_date": qp.get("to") or None,
        "start": qp.get("start") or None,
        "end": qp.get("end") or None,
        "rep": qp.get("rep") or None,
    }


def _echo(f: dict) -> str:
    parts: list[str] = []
    if f["status"]:
        parts.append(f"status = {f['status']}")
    if f["window"] != "all":
        parts.append(f"window = {f['window']}")
    if f["start"] or f["end"]:
        parts.append(f"scheduled {f['start'] or '…'} to {f['end'] or '…'}")
    if f["rep"]:
        parts.append(f"rep = {f['rep']}")
    if f["search"]:
        parts.append(f"search '{f['search']}'")
    return "Appointments — " + ("; ".join(parts) if parts else "no filters (all)")


def _pct(count: int, total: int) -> float:
    return round(100.0 * count / total, 1) if total else 0.0


async def _breakdown(
    session: AsyncSession, label_expr: str, where_sql: str, params: dict, total: int
) -> list[dict]:
    rows = (await session.execute(text(
        f"SELECT {label_expr} AS label, COUNT(*) AS n "
        f"{APPOINTMENTS_FROM_SQL} WHERE {where_sql} "
        f"GROUP BY 1 ORDER BY n DESC LIMIT 15"  # noqa: S608 — label_expr is a code constant
    ), params)).mappings().all()
    return [{"label": r["label"], "count": int(r["n"]), "pct": _pct(int(r["n"]), total)} for r in rows]


async def _aggregate(session: AsyncSession, f: dict) -> dict:
    where_sql, params = build_appointment_where(**f)
    total = int((await session.execute(text(
        f"SELECT COUNT(*) {APPOINTMENTS_FROM_SQL} WHERE {where_sql}"  # noqa: S608
    ), params)).scalar() or 0)
    if total == 0:
        return {"row_count": 0, "breakdowns": {}, "series": None, "extras": {}}

    by_status = await _breakdown(
        session, "COALESCE(LOWER(a.status), 'unknown')", where_sql, params, total)
    by_rep = await _breakdown(
        session, "COALESCE(r.full_name, a.appointment_owner, 'unassigned')",
        where_sql, params, total)
    by_source = await _breakdown(
        session, "COALESCE(LOWER(a.source), 'unknown')", where_sql, params, total)

    series_rows = (await session.execute(text(
        f"SELECT date_trunc('week', a.scheduled_at)::date AS week_start, COUNT(*) AS n "
        f"{APPOINTMENTS_FROM_SQL} WHERE {where_sql} GROUP BY 1 ORDER BY 1"  # noqa: S608
    ), params)).mappings().all()
    series = {
        "bucket": "week",
        "points": [
            {"week_start": r["week_start"].isoformat(), "count": int(r["n"])}
            for r in series_rows if r["week_start"] is not None
        ],
    }

    return {
        "row_count": total,
        "breakdowns": {"status": by_status, "rep": by_rep, "source": by_source},
        "series": series,
        "extras": {},
    }


register(Surface(
    key="appointments",
    label="appointments",
    describe=_DESCRIBE,
    parse_filters=_parse_filters,
    echo=_echo,
    aggregate=_aggregate,
))
```

Also: in `view_analysis/__init__.py`'s bottom import block, keep only the modules that exist so far (this task: `appointments`); Tasks 6–8 each add theirs back. The block must list all four after Task 8.

- [ ] **Step 2: Verify**

```bash
cd backend && .venv/bin/python - <<'EOF'
import asyncio
from app.database import get_session_factory  # if this helper doesn't exist, check app/database.py
# Simplest smoke: registry import + filter parity via SQL echo
from app.analytics.view_analysis import get_surface
s = get_surface("appointments"); assert s, "not registered"
f = s.parse_filters({"status": "booked", "start": "2026-06-01", "end": "2026-06-30"})
print(s.echo(f))
EOF
```
Expected: prints `Appointments — status = booked; scheduled 2026-06-01 to 2026-06-30`. (DB-backed parity is verified end-to-end in Task 9.)

- [ ] **Step 3: Commit**

```bash
git add backend/app/analytics/view_analysis/
git commit -m "feat: appointments analyze-view aggregator"
```

---

### Task 6: Sales-calls aggregator

**Files:**
- Create: `backend/app/analytics/view_analysis/sales_calls.py`

**Interfaces:**
- Consumes: `build_call_filters` (Task 3); `RepRow` from `app.analytics.team`; `Call`, `SalesRep` models (mirror `ci.py` imports); `Surface`, `register` (Task 4).
- Produces: registered surface `key="sales_calls"`; same aggregate dict shape as Task 5; `extras` carries `avg_duration_minutes`.

- [ ] **Step 1: Write the module**

```python
"""Analyze-view aggregator: sales calls (mirrors GET /ci/calls filters)."""

from __future__ import annotations

from collections.abc import Mapping

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.team import RepRow
from app.analytics.view_analysis import Surface, register
from app.models.operational import Call        # mirror ci.py's import path
from app.models.sales import SalesRep
from app.repositories.list_filters import build_call_filters

_DESCRIBE = (
    "Processed sales calls. Each row has a call_type (Sales/Discovery/Outbound), a "
    "call_result (e.g. Booked, Pending, No Show), the rep who took it (call_owner), "
    "a source ('wgr' synced vs 'ci_upload' manual), a date, and a duration in minutes."
)


def _parse_filters(qp: Mapping[str, str]) -> dict:
    return {
        "call_type": qp.get("call_type") or None,
        "call_result": qp.get("call_result") or None,
        "call_owner": qp.get("call_owner") or None,
        "source": qp.get("source") or None,
        "search": qp.get("search") or None,
        "date_from": qp.get("date_from") or None,
        "date_to": qp.get("date_to") or None,
        "start": qp.get("start") or None,
        "end": qp.get("end") or None,
        "rep": qp.get("rep") or None,
    }


def _echo(f: dict) -> str:
    parts: list[str] = []
    if f["call_type"]:
        parts.append(f"type in [{f['call_type']}]")
    if f["call_result"]:
        parts.append(f"result in [{f['call_result']}]")
    if f["start"] or f["end"]:
        parts.append(f"date {f['start'] or '…'} to {f['end'] or '…'}")
    if f["rep"]:
        parts.append(f"rep = {f['rep']}")
    if f["source"]:
        parts.append(f"source = {f['source']}")
    if f["search"]:
        parts.append(f"search '{f['search']}'")
    return "Sales calls — " + ("; ".join(parts) if parts else "no filters (all)")


def _pct(count: int, total: int) -> float:
    return round(100.0 * count / total, 1) if total else 0.0


async def _fetch_roster(session: AsyncSession) -> list[RepRow]:
    rows = (await session.execute(
        select(SalesRep.rep_id, SalesRep.full_name, SalesRep.role, SalesRep.status,
               SalesRep.historical_aliases)
    )).all()
    return [RepRow(rep_id=r[0], full_name=r[1], role=r[2], status=r[3],
                   historical_aliases=r[4]) for r in rows]


async def _group(session: AsyncSession, col, clauses: list, total: int) -> list[dict]:
    rows = (await session.execute(
        select(func.coalesce(col, "unknown").label("label"), func.count().label("n"))
        .select_from(Call).where(*clauses).group_by("label")
        .order_by(func.count().desc()).limit(15)
    )).all()
    return [{"label": r[0], "count": int(r[1]), "pct": _pct(int(r[1]), total)} for r in rows]


async def _aggregate(session: AsyncSession, f: dict) -> dict:
    roster = await _fetch_roster(session)
    clauses = build_call_filters(**f, roster=roster)
    total = int((await session.execute(
        select(func.count()).select_from(Call).where(*clauses)
    )).scalar_one())
    if total == 0:
        return {"row_count": 0, "breakdowns": {}, "series": None, "extras": {}}

    by_result = await _group(session, Call.call_result, clauses, total)
    by_type = await _group(session, Call.call_type, clauses, total)
    by_owner = await _group(session, Call.call_owner, clauses, total)
    by_source = await _group(session, Call.source, clauses, total)

    series_rows = (await session.execute(
        select(func.date_trunc("week", Call.date).label("w"), func.count().label("n"))
        .select_from(Call).where(*clauses).group_by("w").order_by("w")
    )).all()
    series = {
        "bucket": "week",
        "points": [
            {"week_start": r[0].date().isoformat(), "count": int(r[1])}
            for r in series_rows if r[0] is not None
        ],
    }

    avg_duration = (await session.execute(
        select(func.avg(Call.call_duration_minutes)).select_from(Call).where(*clauses)
    )).scalar()

    return {
        "row_count": total,
        "breakdowns": {
            "call_result": by_result, "call_type": by_type,
            "rep": by_owner, "source": by_source,
        },
        "series": series,
        "extras": {
            "avg_duration_minutes": round(float(avg_duration), 1) if avg_duration else None,
        },
    }


register(Surface(
    key="sales_calls",
    label="sales calls",
    describe=_DESCRIBE,
    parse_filters=_parse_filters,
    echo=_echo,
    aggregate=_aggregate,
))
```

Add `sales_calls` to the bottom import block in `view_analysis/__init__.py`.

- [ ] **Step 2: Verify compile + registration**

```bash
cd backend && .venv/bin/python -c "
from app.analytics.view_analysis import get_surface
assert get_surface('sales_calls'), 'not registered'; print('ok')"
```
Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add backend/app/analytics/view_analysis/
git commit -m "feat: sales-calls analyze-view aggregator"
```

---

### Task 7: Leads aggregator

**Files:**
- Create: `backend/app/analytics/view_analysis/leads.py`

**Interfaces:**
- Consumes: `build_lead_where` (Task 2); `Surface`, `register` (Task 4).
- Produces: registered surface `key="leads"`; same aggregate dict shape.

- [ ] **Step 1: Write the module**

```python
"""Analyze-view aggregator: leads (mirrors GET /leads filters)."""

from __future__ import annotations

from collections.abc import Mapping

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.view_analysis import Surface, register
from app.repositories.list_filters import build_lead_where

_DESCRIBE = (
    "Sales leads (prospects). Each row has a pipeline status (raw DB vocabulary: new, "
    "contacted, qualified, appointment-set, sale, lost, stale), a source (where the "
    "lead came from), and an entry_date (when it entered the funnel)."
)


def _parse_filters(qp: Mapping[str, str]) -> dict:
    return {
        "status": qp.get("status") or None,
        "source": qp.get("source") or None,
        "search": qp.get("search") or None,
        "entry_from": qp.get("entry_from") or None,
        "entry_to": qp.get("entry_to") or None,
    }


def _echo(f: dict) -> str:
    parts: list[str] = []
    if f["status"]:
        parts.append(f"status = {f['status']}")
    if f["source"]:
        parts.append(f"source = {f['source']}")
    if f["entry_from"] or f["entry_to"]:
        parts.append(f"entered {f['entry_from'] or '…'} to {f['entry_to'] or '…'}")
    if f["search"]:
        parts.append(f"search '{f['search']}'")
    return "Leads — " + ("; ".join(parts) if parts else "no filters (all)")


def _pct(count: int, total: int) -> float:
    return round(100.0 * count / total, 1) if total else 0.0


async def _breakdown(
    session: AsyncSession, label_expr: str, where_sql: str, params: dict, total: int
) -> list[dict]:
    rows = (await session.execute(text(
        f"SELECT {label_expr} AS label, COUNT(*) AS n FROM leads "
        f"WHERE {where_sql} GROUP BY 1 ORDER BY n DESC LIMIT 15"  # noqa: S608
    ), params)).mappings().all()
    return [{"label": r["label"], "count": int(r["n"]), "pct": _pct(int(r["n"]), total)} for r in rows]


async def _aggregate(session: AsyncSession, f: dict) -> dict:
    where_sql, params = build_lead_where(**f)
    total = int((await session.execute(text(
        f"SELECT COUNT(*) FROM leads WHERE {where_sql}"  # noqa: S608
    ), params)).scalar() or 0)
    if total == 0:
        return {"row_count": 0, "breakdowns": {}, "series": None, "extras": {}}

    by_status = await _breakdown(session, "COALESCE(LOWER(status), 'unknown')", where_sql, params, total)
    by_source = await _breakdown(session, "COALESCE(LOWER(source), 'unknown')", where_sql, params, total)

    series_rows = (await session.execute(text(
        f"SELECT date_trunc('week', entry_date)::date AS week_start, COUNT(*) AS n "
        f"FROM leads WHERE {where_sql} GROUP BY 1 ORDER BY 1"  # noqa: S608
    ), params)).mappings().all()
    series = {
        "bucket": "week",
        "points": [
            {"week_start": r["week_start"].isoformat(), "count": int(r["n"])}
            for r in series_rows if r["week_start"] is not None
        ],
    }

    return {
        "row_count": total,
        "breakdowns": {"status": by_status, "source": by_source},
        "series": series,
        "extras": {},
    }


register(Surface(
    key="leads",
    label="leads",
    describe=_DESCRIBE,
    parse_filters=_parse_filters,
    echo=_echo,
    aggregate=_aggregate,
))
```

Add `leads` to the bottom import block in `view_analysis/__init__.py`.

- [ ] **Step 2: Verify compile + registration**

```bash
cd backend && .venv/bin/python -c "
from app.analytics.view_analysis import get_surface
assert get_surface('leads'), 'not registered'; print('ok')"
```
Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add backend/app/analytics/view_analysis/
git commit -m "feat: leads analyze-view aggregator"
```

---

### Task 8: Team-members aggregator

**Files:**
- Create: `backend/app/analytics/view_analysis/team_members.py`

**Interfaces:**
- Consumes: `TEAM_FROM_SQL`, `build_team_where` (Task 2); `Surface`, `register` (Task 4).
- Produces: registered surface `key="team"`; same aggregate dict shape (no series — roster data has no natural time axis); `extras` carries `total_calls` and `top_reps_by_calls`.

- [ ] **Step 1: Write the module**

```python
"""Analyze-view aggregator: team directory (mirrors GET /members/team filters)."""

from __future__ import annotations

from collections.abc import Mapping

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.view_analysis import Surface, register
from app.repositories.list_filters import TEAM_FROM_SQL, build_team_where

_DESCRIBE = (
    "The sales team roster (the Members page). Each row is a rep with a role, a "
    "status (active/probation/terminated), a hire date, and calls_count — how many "
    "calls in the system are attributed to them."
)


def _parse_filters(qp: Mapping[str, str]) -> dict:
    return {
        "search": qp.get("search") or None,
        "status": qp.get("status") or None,
    }


def _echo(f: dict) -> str:
    parts: list[str] = []
    if f["status"]:
        parts.append(f"status = {f['status']}")
    if f["search"]:
        parts.append(f"search '{f['search']}'")
    return "Team members — " + ("; ".join(parts) if parts else "no filters (all)")


def _pct(count: int, total: int) -> float:
    return round(100.0 * count / total, 1) if total else 0.0


async def _aggregate(session: AsyncSession, f: dict) -> dict:
    where_sql, params = build_team_where(**f)
    # Roster is small — fetch effective rows once, aggregate in Python.
    rows = (await session.execute(text(
        f"""
        SELECT
            COALESCE(ro.full_name, sr.full_name) AS name,
            LOWER(COALESCE(ro.role, sr.role, 'unknown'))     AS role,
            LOWER(COALESCE(ro.status, sr.status, 'unknown')) AS status,
            (SELECT COUNT(*) FROM calls c
             WHERE c.deleted_at IS NULL AND c.call_owner = sr.full_name) AS calls_count
        {TEAM_FROM_SQL}
        WHERE {where_sql}
        """  # noqa: S608 — where_sql parametrised
    ), params)).mappings().all()

    total = len(rows)
    if total == 0:
        return {"row_count": 0, "breakdowns": {}, "series": None, "extras": {}}

    def _count_by(field: str) -> list[dict]:
        counts: dict[str, int] = {}
        for r in rows:
            counts[r[field]] = counts.get(r[field], 0) + 1
        return [
            {"label": k, "count": v, "pct": _pct(v, total)}
            for k, v in sorted(counts.items(), key=lambda kv: -kv[1])
        ]

    top_reps = sorted(rows, key=lambda r: -int(r["calls_count"]))[:5]
    return {
        "row_count": total,
        "breakdowns": {"status": _count_by("status"), "role": _count_by("role")},
        "series": None,
        "extras": {
            "total_calls": sum(int(r["calls_count"]) for r in rows),
            "top_reps_by_calls": [
                {"name": r["name"], "calls": int(r["calls_count"])} for r in top_reps
            ],
        },
    }


register(Surface(
    key="team",
    label="team members",
    describe=_DESCRIBE,
    parse_filters=_parse_filters,
    echo=_echo,
    aggregate=_aggregate,
))
```

Add `team_members` to the bottom import block in `view_analysis/__init__.py` — all four modules are now listed.

- [ ] **Step 2: Verify all four register**

```bash
cd backend && .venv/bin/python -c "
from app.analytics.view_analysis import all_surfaces
keys = sorted(s.key for s in all_surfaces())
assert keys == ['appointments', 'leads', 'sales_calls', 'team'], keys
print('ok:', keys)"
```
Expected: `ok: ['appointments', 'leads', 'sales_calls', 'team']`.

- [ ] **Step 3: Commit**

```bash
git add backend/app/analytics/view_analysis/
git commit -m "feat: team-members analyze-view aggregator"
```

---

### Task 9: The /analyze route

**Files:**
- Create: `backend/app/schemas/analyze.py`
- Create: `backend/app/routes/analyze.py`
- Modify: `backend/app/main.py` (register router alongside the others, ~lines 83–150)

**Interfaces:**
- Consumes: `get_surface` (Task 4), `synthesize_view_analysis` (Task 4), `get_session` from `app.database`.
- Produces: `POST /api/v1/analyze/{surface_key}` returning `AnalyzeViewResponse` — the exact JSON contract Task 10's client types mirror:

```json
{
  "surface": "appointments", "label": "appointments",
  "filters_echo": "Appointments — status = booked", "row_count": 214, "empty": false,
  "stats": {"row_count": 214, "breakdowns": {...}, "series": {...}, "extras": {...}},
  "narrative": "…", "highlights": ["…"], "hypotheses": ["…"],
  "generated_at": "2026-07-13T09:00:00Z", "model": "claude-…"
}
```

- [ ] **Step 1: Write `backend/app/schemas/analyze.py`**

```python
"""Response schema for the analyze-view endpoint."""

from pydantic import BaseModel


class AnalyzeViewResponse(BaseModel):
    surface: str
    label: str
    filters_echo: str
    row_count: int
    empty: bool = False
    stats: dict
    narrative: str
    highlights: list[str]
    hypotheses: list[str]
    generated_at: str
    model: str | None = None
```

- [ ] **Step 2: Write `backend/app/routes/analyze.py`**

```python
"""Analyze the current filtered view.

POST /api/v1/analyze/{surface} — accepts the SAME filter query params as the
surface's list endpoint (pagination/sort params are ignored), re-runs the
filtered query via the surface's registered aggregator, and returns an LLM
narrative grounded exclusively in the computed aggregates.

Ephemeral by design: nothing is persisted; one real LLM call per invocation
(row_count == 0 short-circuits without calling the LLM). Auth comes from the
global AuthMiddleware like every other /api/v1 route.
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.view_analysis import get_surface
from app.analytics.view_analysis.narrative import synthesize_view_analysis
from app.database import get_session
from app.schemas.analyze import AnalyzeViewResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["analyze"])


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@router.post(
    "/analyze/{surface_key}",
    response_model=AnalyzeViewResponse,
    summary="Grounded LLM analysis of the current filtered list view",
)
async def analyze_view(
    surface_key: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> AnalyzeViewResponse:
    surface = get_surface(surface_key)
    if surface is None:
        raise HTTPException(status_code=404, detail=f"Unknown surface: {surface_key!r}")

    filters = surface.parse_filters(request.query_params)
    aggregates = await surface.aggregate(session, filters)
    echo = surface.echo(filters)

    if aggregates["row_count"] == 0:
        return AnalyzeViewResponse(
            surface=surface.key, label=surface.label, filters_echo=echo,
            row_count=0, empty=True, stats=aggregates,
            narrative="", highlights=[], hypotheses=[],
            generated_at=_now_iso(), model=None,
        )

    parsed = await synthesize_view_analysis(
        label=surface.label, describe=surface.describe,
        filters_echo=echo, aggregates=aggregates,
    )
    return AnalyzeViewResponse(
        surface=surface.key, label=surface.label, filters_echo=echo,
        row_count=aggregates["row_count"], empty=False, stats=aggregates,
        narrative=parsed["narrative"], highlights=parsed["highlights"],
        hypotheses=parsed["hypotheses"],
        generated_at=_now_iso(), model=parsed["model"],
    )
```

- [ ] **Step 3: Register in `main.py`**

Follow the existing pattern exactly — add with the other imports and includes:

```python
    from app.routes.analyze import router as analyze_router
    ...
    app.include_router(analyze_router, prefix="/api/v1")
```

- [ ] **Step 4: Verify end-to-end with real data (this is the first real LLM call — one paid request)**

```bash
# Parity check: analyze row_count must equal the list total for identical filters.
curl -s -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/appointments?status=booked&per_page=1" \
  | python3 -c "import sys,json; print('list total:', json.load(sys.stdin)['total'])"
curl -s -X POST -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/analyze/appointments?status=booked" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('analyze row_count:', d['row_count']); print(d['narrative'][:300])"
# Unknown surface → 404; impossible filter → empty:true and NO LLM latency
curl -s -o /dev/null -w "%{http_code}\n" -X POST -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/analyze/nope"
curl -s -X POST -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/analyze/leads?status=zzz_not_a_status" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('empty:', d['empty'], 'count:', d['row_count'])"
```
Expected: the two counts match exactly; a real narrative prints; `404`; `empty: True count: 0` returning near-instantly.

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/analyze.py backend/app/routes/analyze.py backend/app/main.py
git commit -m "feat: POST /analyze/{surface} — grounded analysis of the filtered view"
```

---

### Task 10: Frontend client + drawer component

**Files:**
- Create: `frontend/src/lib/analyze-client.ts`
- Create: `frontend/src/components/analyze/AnalyzeViewDrawer.tsx`

**Interfaces:**
- Consumes: `apiClient.post<T>(path, body, options)` from `@/lib/api-client`; `Button` from `@/components/ui/button`; `Skeleton` from `@/components/ui/skeleton`.
- Produces: `analyzeView(surface: string, params: URLSearchParams): Promise<AnalyzeViewResponse>`; `<AnalyzeViewDrawer surface={string} params={URLSearchParams | null} open={boolean} onClose={() => void} />`. Task 11 consumes both.

- [ ] **Step 1: Write `frontend/src/lib/analyze-client.ts`**

```typescript
import { apiClient } from "@/lib/api-client";

export interface BreakdownItem {
  label: string;
  count: number;
  pct: number;
}

export interface AnalyzeStats {
  row_count: number;
  breakdowns: Record<string, BreakdownItem[]>;
  series: { bucket: string; points: { week_start: string; count: number }[] } | null;
  extras: Record<string, unknown>;
}

export interface AnalyzeViewResponse {
  surface: string;
  label: string;
  filters_echo: string;
  row_count: number;
  empty: boolean;
  stats: AnalyzeStats;
  narrative: string;
  highlights: string[];
  hypotheses: string[];
  generated_at: string;
  model: string | null;
}

/**
 * Run a grounded analysis of the current filtered view. `params` must be the
 * same filter params the page's list fetch uses (minus pagination/sort).
 * One real LLM call per invocation — only call on explicit user action.
 */
export function analyzeView(
  surface: string,
  params: URLSearchParams,
): Promise<AnalyzeViewResponse> {
  const qs = params.toString();
  return apiClient.post<AnalyzeViewResponse>(
    `/analyze/${surface}${qs ? `?${qs}` : ""}`,
    {},
    { silent: true, timeoutMs: 90_000 },
  );
}
```

Note: check `RequestOptions` in `@/types` for the timeout option's real name (`timeoutMs` assumed — grep `DEFAULT_TIMEOUT_MS` usage in `api-client.ts`); LLM calls can exceed the default 30s.

- [ ] **Step 2: Write `frontend/src/components/analyze/AnalyzeViewDrawer.tsx`**

```tsx
"use client";

/**
 * AnalyzeViewDrawer — right-side drawer showing a grounded LLM analysis of the
 * current filtered list view. Ephemeral: fetches on open, discards on close.
 * Every number in the narrative is verifiable against the "Data this is based
 * on" section (the raw aggregates the backend computed and prompted with).
 */

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { analyzeView, type AnalyzeViewResponse } from "@/lib/analyze-client";

interface AnalyzeViewDrawerProps {
  surface: string;
  /** Snapshot of the page's current filter params; null = drawer closed. */
  params: URLSearchParams | null;
  open: boolean;
  onClose: () => void;
}

export function AnalyzeViewDrawer({ surface, params, open, onClose }: AnalyzeViewDrawerProps) {
  const [result, setResult] = useState<AnalyzeViewResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showData, setShowData] = useState(false);
  const [runKey, setRunKey] = useState(0);

  useEffect(() => {
    if (!open || !params) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    setResult(null);
    analyzeView(surface, params)
      .then((r) => { if (!cancelled) setResult(r); })
      .catch((e: unknown) => {
        if (!cancelled) setError(e instanceof Error ? e.message : "Analysis failed.");
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [open, params, surface, runKey]);

  useEffect(() => {
    if (!open) { setResult(null); setError(null); setShowData(false); }
  }, [open]);

  if (!open) return null;

  return (
    <>
      <div className="fixed inset-0 bg-black/30 z-40" onClick={onClose} aria-hidden />
      <aside
        className="fixed inset-y-0 right-0 w-full max-w-[460px] bg-white shadow-xl z-50 flex flex-col"
        role="dialog"
        aria-label="View analysis"
      >
        <div className="flex items-center justify-between border-b border-gray-200 px-5 py-4">
          <h2 className="text-sm font-semibold text-gray-900">Analyze this view</h2>
          <div className="flex gap-2">
            <Button variant="ghost" size="sm" onClick={() => setRunKey((k) => k + 1)} disabled={loading}>
              Re-run
            </Button>
            <Button variant="ghost" size="sm" onClick={onClose}>Close</Button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-5">
          {result && (
            <p className="text-xs text-gray-500">
              Analyzing {result.row_count.toLocaleString()} {result.label} · {result.filters_echo}
            </p>
          )}

          {loading && (
            <div className="space-y-3">
              <Skeleton className="h-4 w-3/4" />
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-5/6" />
              <p className="text-xs text-gray-400">Computing aggregates and writing the analysis…</p>
            </div>
          )}

          {error && (
            <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {error}
              <div className="mt-2">
                <Button variant="ghost" size="sm" onClick={() => setRunKey((k) => k + 1)}>Retry</Button>
              </div>
            </div>
          )}

          {result?.empty && (
            <p className="text-sm text-gray-500">
              No data in this view — adjust the filters and try again. (No analysis was run.)
            </p>
          )}

          {result && !result.empty && (
            <>
              <section className="space-y-3">
                {result.narrative.split("\n\n").map((para, i) => (
                  <p key={i} className="text-sm leading-6 text-gray-800">{para}</p>
                ))}
              </section>

              {result.highlights.length > 0 && (
                <section>
                  <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">
                    Highlights
                  </h3>
                  <ul className="list-disc space-y-1 pl-5 text-sm text-gray-800">
                    {result.highlights.map((h, i) => <li key={i}>{h}</li>)}
                  </ul>
                </section>
              )}

              {result.hypotheses.length > 0 && (
                <section className="rounded-md border border-amber-200 bg-amber-50 px-4 py-3">
                  <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-amber-700">
                    Hypotheses — speculative, verify before acting
                  </h3>
                  <ul className="list-disc space-y-1 pl-5 text-sm text-amber-900">
                    {result.hypotheses.map((h, i) => <li key={i}>{h}</li>)}
                  </ul>
                </section>
              )}

              <section>
                <button
                  type="button"
                  className="text-xs font-medium text-gray-600 underline"
                  onClick={() => setShowData((s) => !s)}
                >
                  {showData ? "Hide" : "Show"} the data this is based on
                </button>
                {showData && (
                  <div className="mt-3 space-y-4">
                    {Object.entries(result.stats.breakdowns).map(([name, items]) => (
                      <div key={name}>
                        <h4 className="mb-1 text-xs font-semibold capitalize text-gray-600">
                          By {name.replace(/_/g, " ")}
                        </h4>
                        <table className="w-full text-xs text-gray-700">
                          <tbody>
                            {items.map((it) => (
                              <tr key={it.label} className="border-b border-gray-100">
                                <td className="py-1 pr-2">{it.label}</td>
                                <td className="py-1 pr-2 text-right tabular-nums">{it.count}</td>
                                <td className="py-1 text-right tabular-nums text-gray-400">{it.pct}%</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    ))}
                    {result.stats.series && result.stats.series.points.length > 0 && (
                      <div>
                        <h4 className="mb-1 text-xs font-semibold text-gray-600">By week</h4>
                        <table className="w-full text-xs text-gray-700">
                          <tbody>
                            {result.stats.series.points.map((p) => (
                              <tr key={p.week_start} className="border-b border-gray-100">
                                <td className="py-1 pr-2">{p.week_start}</td>
                                <td className="py-1 text-right tabular-nums">{p.count}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                    {Object.keys(result.stats.extras).length > 0 && (
                      <div>
                        <h4 className="mb-1 text-xs font-semibold text-gray-600">Extras</h4>
                        <pre className="overflow-x-auto rounded bg-gray-50 p-2 text-[11px] text-gray-600">
                          {JSON.stringify(result.stats.extras, null, 2)}
                        </pre>
                      </div>
                    )}
                  </div>
                )}
              </section>

              <p className="text-[11px] text-gray-400">
                Generated {result.generated_at}{result.model ? ` · ${result.model}` : ""} · not saved
              </p>
            </>
          )}
        </div>
      </aside>
    </>
  );
}
```

Check `skeleton.tsx` for the actual `Skeleton` props (`className` assumed); adjust if its API differs.

- [ ] **Step 3: Verify it compiles**

```bash
cd frontend && npx tsc --noEmit 2>&1 | grep -E "analyze|Drawer" ; echo "exit: $?"
```
Expected: no errors mentioning the new files (grep finds nothing, exit 1 from grep is fine — no output = clean).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/lib/analyze-client.ts frontend/src/components/analyze/
git commit -m "feat: analyze-view client + drawer component"
```

---

### Task 11: Wire the button into the four pages

**Files:**
- Modify: `frontend/src/app/(app)/appointments/page.tsx` (filter state ~lines 271–283, filter bar ~line 440)
- Modify: `frontend/src/app/(app)/sales-calls/page.tsx` (filter state ~lines 408–429, list fetch params ~lines 470–495)
- Modify: `frontend/src/app/(app)/leads/page.tsx` (filter state ~lines 1112–1122, list fetch params ~lines 1195–1205)
- Modify: `frontend/src/app/(app)/members/page.tsx` (filter state ~lines 158–162, list fetch params ~lines 181–183)

Each page gets the same three additions — (a) imports, (b) drawer state + a params-snapshot builder that mirrors the page's own list fetch **minus pagination/sort**, (c) the button + drawer JSX. The params builder MUST stay next to the list-fetch params code so future filter additions update both.

- [ ] **Step 1: Appointments page**

Add imports:

```tsx
import { AnalyzeViewDrawer } from "@/components/analyze/AnalyzeViewDrawer";
```

Add state next to the other `useState` calls (~line 283) and a snapshot builder (mirrors the effect at ~lines 331–338, minus `page`/`per_page`):

```tsx
  const [analyzeOpen, setAnalyzeOpen] = useState(false);
  const [analyzeParams, setAnalyzeParams] = useState<URLSearchParams | null>(null);

  const openAnalyze = () => {
    const params = new URLSearchParams();
    if (statusFilter !== "all") params.set("status", statusFilter);
    if (windowFilter !== "all") params.set("window", windowFilter);
    if (search) params.set("search", search);
    if (startDate) params.set("start", startDate);
    if (endDate) params.set("end", endDate);
    if (repFilter !== "all") params.set("rep", repFilter);
    setAnalyzeParams(params);
    setAnalyzeOpen(true);
  };
```

In the filter-bar JSX (~line 440), add at the end of the filter row:

```tsx
            <Button variant="ghost" size="sm" onClick={openAnalyze}>
              Analyze this view
            </Button>
```

(`Button` may already be imported; add the import if not.) And before the component's closing tag:

```tsx
      <AnalyzeViewDrawer
        surface="appointments"
        params={analyzeParams}
        open={analyzeOpen}
        onClose={() => setAnalyzeOpen(false)}
      />
```

- [ ] **Step 2: Sales Calls page**

Same pattern. The snapshot builder mirrors the fetch effect (~lines 470–495) — note this page ALWAYS pins `call_type` and conditionally sends `call_result`:

```tsx
  const openAnalyze = () => {
    const params = new URLSearchParams();
    params.set("call_type", "Sales,Discovery,Outbound");
    if (
      selectedResults &&
      selectedResults.size > 0 &&
      selectedResults.size < resultOptions.length
    ) {
      params.set("call_result", Array.from(selectedResults).join(","));
    }
    if (debouncedSearch) params.set("search", debouncedSearch);
    if (startDate) params.set("start", startDate);
    if (endDate) params.set("end", endDate);
    if (repFilter !== "all") params.set("rep", repFilter);
    setAnalyzeParams(params);
    setAnalyzeOpen(true);
  };
```

Button in the filter row; drawer with `surface="sales_calls"`.

- [ ] **Step 3: Leads page**

Snapshot builder mirrors the list fetch (~lines 1197–1201):

```tsx
  const openAnalyze = () => {
    const params = new URLSearchParams();
    if (statusFilter !== "all") params.set("status", statusFilter);
    if (sourceFilter !== "all") params.set("source", sourceFilter);
    if (search) params.set("search", search);
    if (entryFrom) params.set("entry_from", entryFrom);
    if (entryTo) params.set("entry_to", entryTo);
    setAnalyzeParams(params);
    setAnalyzeOpen(true);
  };
```

Button in the filter row; drawer with `surface="leads"`.

- [ ] **Step 4: Members page**

Snapshot builder mirrors the team fetch (~lines 181–183):

```tsx
  const openAnalyze = () => {
    const params = new URLSearchParams();
    if (debounced) params.set("search", debounced);
    if (statusFilter !== "all") params.set("status", statusFilter);
    setAnalyzeParams(params);
    setAnalyzeOpen(true);
  };
```

Button in the filter row; drawer with `surface="team"`.

- [ ] **Step 5: Verify in the browser (four paid LLM calls)**

With backend + frontend running, on each of `/appointments`, `/sales-calls`, `/leads`, `/members`: apply a filter, click **Analyze this view**, confirm the drawer opens, the header count matches the list's total, a narrative renders, and "Show the data this is based on" reveals breakdown tables. `npx tsc --noEmit` is clean.

- [ ] **Step 6: Commit**

```bash
git add "frontend/src/app/(app)/appointments/page.tsx" "frontend/src/app/(app)/sales-calls/page.tsx" "frontend/src/app/(app)/leads/page.tsx" "frontend/src/app/(app)/members/page.tsx"
git commit -m "feat: Analyze-this-view button + drawer on the four filtered list pages"
```

---

### Task 12: Test documentation + changelog + graph refresh

**Files:**
- Create: `docs/testing/2026-07-13-analyze-view-test.md`
- Modify: `CHANGELOG.md` (prepend an entry, matching the file's existing format)

- [ ] **Step 1: Write the test doc**

This is the user's manual verification document (their standing rule: no seeded/mock tests; they test personally on real data). Use the FEATURE-VERIFICATION.md conventions:

```markdown
# Test Doc — "Analyze this view" (2026-07-13)

> **Feature:** On Appointments, Sales Calls, Leads, and Members, an
> "Analyze this view" button opens a drawer with an LLM narrative grounded in
> server-computed aggregates of the currently filtered dataset. Ephemeral —
> nothing is saved; one real LLM call per click.
>
> **Status legend:** ⬜ pending · ✅ pass · ⚠️ partial: <note> · ❌ fail: <note>
>
> **Prereqs:** backend on :8000, frontend on :3000, logged in.
> `ANTHROPIC_API_KEY` must be set in backend/.env — there is NO mock fallback.
> **Cost note:** every Analyze click is one real Claude call.

## T1 — Appointments
- **Status:** ⬜ pending
- **How to locate:** `/appointments` → "Analyze this view" button at the right end of the filter bar.
- **Steps to test:**
  - [ ] Set a date range + a rep filter. Note the list's total count.
  - [ ] Click Analyze. Drawer header shows "Analyzing N appointments" — N equals the list total.
  - [ ] The filter echo names the same status/window/date range/rep you set.
  - [ ] Open "Show the data this is based on": every number in the narrative and
        highlights appears in these tables (counts and percentages).
  - [ ] Hypotheses (if any) are in the amber box and phrased speculatively.
  - [ ] Set a filter combination with zero results → "No data in this view" appears
        instantly (no LLM wait).
  - [ ] Close and reopen the drawer → previous analysis is gone (ephemeral).
- **Rating:** ⬜

## T2 — Sales Calls
- **Status:** ⬜ pending
- **How to locate:** `/sales-calls` → "Analyze this view" in the filter bar.
- **Steps to test:**
  - [ ] Pick a call-result subset + date range. List total = drawer N.
  - [ ] Narrative numbers all verifiable in the data section (incl. avg duration in Extras).
  - [ ] Rep filter: pick a rep, re-run — breakdown "rep" table shows only that rep's aliases.
- **Rating:** ⬜

## T3 — Leads
- **Status:** ⬜ pending
- **How to locate:** `/leads` → "Analyze this view" in the filter bar.
- **Steps to test:**
  - [ ] Filter status = Applications + this week's entry dates. List total = drawer N.
  - [ ] Status breakdown uses DB vocabulary (qualified / appointment-set) — expected, noted in describe.
  - [ ] Weekly series matches the entry-date window you set.
- **Rating:** ⬜

## T4 — Members (team)
- **Status:** ⬜ pending
- **How to locate:** `/members` → "Analyze this view" in the filter bar.
- **Steps to test:**
  - [ ] Filter status = active. Drawer N = number of rows in the directory.
  - [ ] Extras shows total_calls and top 5 reps by calls — spot-check one rep's
        calls count against their directory row.
- **Rating:** ⬜

## T5 — Cross-cutting
- **Status:** ⬜ pending
- **Steps to test:**
  - [ ] Analysis is ephemeral: nothing appears in the DB (`overall_insights` etc. unchanged).
  - [ ] While the drawer loads, the page behind stays usable after closing.
  - [ ] Kill the backend mid-analysis → drawer shows the error state with a Retry button.
  - [ ] Re-run button produces a fresh analysis (may word things differently; numbers identical).
- **Rating:** ⬜

## Regression checks (filter extraction refactor)
- **Status:** ⬜ pending
- **Why:** Tasks 1–3 moved the list endpoints' WHERE-building into
  `app/repositories/list_filters.py`. The lists must behave identically.
- **Steps to test:**
  - [ ] `/appointments`: each filter (status, window, date range, rep, search) still
        constrains the list and the calendar view.
  - [ ] `/sales-calls`: result multi-select, rep, dates, search still work.
  - [ ] `/leads`: status (incl. Applications composite), source, entry dates, search still work.
  - [ ] `/members`: status + search still constrain the directory.
- **Rating:** ⬜
```

- [ ] **Step 2: CHANGELOG entry**

Prepend to `CHANGELOG.md` following its existing entry format: date-headed entry describing the feature (analyze endpoint + registry + drawer + four pages), the filter-builder extraction refactor, and a pointer to the test doc.

- [ ] **Step 3: Refresh the graphify graph (project CLAUDE.md rule)**

```bash
python3 -c "from graphify.watch import _rebuild_code; from pathlib import Path; _rebuild_code(Path('.'))"
```

- [ ] **Step 4: Commit**

```bash
git add docs/testing/2026-07-13-analyze-view-test.md CHANGELOG.md
git commit -m "docs: analyze-view test doc + changelog"
```

---

## Self-review notes (already applied)

- **Spec coverage:** endpoint + registry (T4/T9), four aggregators (T5–T8), shared-filter guarantee (T1–T3), drawer + buttons (T10–T11), zero-row short-circuit and 404 (T9), no-mock-mode 503 (T4), PII rule (aggregates only — no row-level fields selected anywhere), ephemeral (no persistence anywhere), test doc (T12). ✓
- **Type consistency:** `Surface` fields consumed by route match T4's dataclass; `AnalyzeViewResponse` JSON contract in T9 matches T10's TS types; aggregate dict shape identical across T5–T8. ✓
- **Known judgment calls:** rep filter echoes the raw `rep_id` (drawer users picked the rep by name in the dropdown, and the aggregates show rep names — acceptable for wave 1). Members surface analyzes the team directory (`/members/team`) because that is what the page actually renders.
```
