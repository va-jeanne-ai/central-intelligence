"""
CentralIntelligence — CEO/orchestrator agent for the Central Intelligence platform.

Sprint 1B: Database read access via query_database tool.
The tool returns business-friendly prose (never raw columns/rows) so
even a weaker model cannot accidentally leak schema details.
"""

import json
import logging
from datetime import datetime, timezone

from sqlalchemy import text

from app.agents.base import BaseAgent
from app.config import settings
from app.database import AsyncSessionLocal
from app.prompts.central_intelligence_v1 import CENTRAL_INTELLIGENCE_SYSTEM_PROMPT_V1
from app.services import voyage_client

logger = logging.getLogger(__name__)

# Maximum rows returned per query to keep context manageable.
_MAX_ROWS = 50

# Defaults for the knowledge-base tool. Top-K of 10 is a reasonable
# balance between recall and prompt bloat; the LLM can request more
# if the first batch didn't include what it needed.
_KB_DEFAULT_TOP_K = 10
_KB_MAX_TOP_K = 25
_KB_CHUNK_PREVIEW_CHARS = 1200

# ---------------------------------------------------------------------------
# Status translation — DB values → business-friendly labels
# ---------------------------------------------------------------------------
_STATUS_LABELS: dict[str, str] = {
    "new": "New",
    "contacted": "In Conversation",
    "qualified": "Qualified",
    "appointment-set": "Appointment Booked",
    "sale": "Closed Won",
    "lost": "Closed Lost",
    "stale": "Stale",
    "active": "Active",
    "inactive": "Inactive",
    "churned": "Churned",
    "draft": "Draft",
    "published": "Published",
    "planned": "Planned",
    "in review": "In Review",
}


def _humanize_value(value: str | None) -> str:
    """Translate a raw DB value to business language."""
    if value is None:
        return "—"
    return _STATUS_LABELS.get(value.lower().strip(), value)


def _format_results_as_prose(columns: list[str], rows: list[list]) -> str:
    """Convert raw query results into business-friendly prose.

    This is the critical privacy gate — the model never sees raw column
    names or DB internals.  Everything is translated into natural language.
    """
    if not rows:
        return "No matching records found."

    # Single aggregate value (e.g. SELECT COUNT(*))
    if len(columns) == 1 and len(rows) == 1:
        return f"Result: {_humanize_value(str(rows[0][0]))}"

    # Two-column results (e.g. GROUP BY queries) — format as a list
    if len(columns) == 2:
        lines = []
        for row in rows:
            label = _humanize_value(str(row[0]))
            value = _humanize_value(str(row[1]))
            lines.append(f"- {label}: {value}")
        return "\n".join(lines)

    # Multi-column results — format each row as a numbered entry
    # Use generic labels instead of column names
    _friendly_names: dict[str, str] = {
        "id": "",
        "name": "Name",
        "email": "Email",
        "phone": "Phone",
        "status": "Status",
        "source": "Source",
        "created_at": "Date",
        "enrollment_date": "Enrolled",
        "date": "Date",
        "call_type": "Type",
        "call_result": "Result",
        "call_duration_minutes": "Duration (min)",
        "notes": "Notes",
        "description": "Description",
        "priority": "Priority",
        "severity": "Severity",
        "impact": "Impact",
        "signal": "Signal",
        "signal_family": "Category",
        "insight_type": "Type",
        "content_format": "Format",
        "content_angle": "Angle",
        "content_premise": "Premise",
        "hook_opening_line": "Hook",
        "teaching_point": "Key Teaching",
        "cta_idea": "Call to Action",
        "best_platform": "Platform",
        "priority_level": "Priority",
        "idea_score": "Score",
        "market_audience": "Audience",
        "raw_quote": "Quote",
        "what_they_say": "What They Say",
        "the_real_problem": "Real Problem",
        "emotional_driver": "Emotional Driver",
        "core_fear_revealed": "Core Fear",
        "marketing_translation": "Marketing Angle",
        "hook_angle_example": "Hook Example",
        "detail": "Detail",
        "confidence": "Confidence",
        "speaker_name": "Speaker",
        "display_name": "Name",
        "role": "Role",
        "department": "Department",
        "membership_status": "Membership",
        "count": "Count",
    }

    entries = []
    for i, row in enumerate(rows, 1):
        parts = []
        for col, val in zip(columns, row):
            col_lower = col.lower()
            # Skip internal IDs and soft-delete markers
            if col_lower in ("id", "deleted_at", "updated_at", "created_by",
                             "coach_id", "member_id", "lead_id", "call_id",
                             "insight_id", "caller_id", "call_owner",
                             "transcript_source", "transcript_uid",
                             "transcript_quality", "transcript_link",
                             "processed_date", "repurpose_opportunities"):
                continue
            friendly = _friendly_names.get(col_lower, col_lower.replace("_", " ").title())
            if not friendly:
                continue
            parts.append(f"{friendly}: {_humanize_value(str(val) if val is not None else None)}")
        if parts:
            entries.append(f"{i}. " + " | ".join(parts))

    return "\n".join(entries) if entries else "No matching records found."


async def _query_database(sql: str) -> str:
    """Execute a read-only SQL query and return business-friendly prose.

    Raw column names and DB errors are never exposed to the model.
    """
    cleaned = sql.strip().rstrip(";").strip()

    first_word = cleaned.split()[0].upper() if cleaned else ""
    if first_word != "SELECT":
        return "This type of operation is not available."

    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(text(cleaned))
            columns = list(result.keys())
            rows = [
                [v for v in row]
                for row in result.fetchmany(_MAX_ROWS)
            ]
            total = len(rows)
            prose = _format_results_as_prose(columns, rows)
            if total == _MAX_ROWS:
                prose += f"\n(Showing first {_MAX_ROWS} results)"
            return prose
    except Exception as exc:
        logger.warning("query_database tool error: %s", exc)
        return "This information is not available right now."


def _strip_embedding_header(chunk: str) -> str:
    """Remove the bracket header + title-sentence block from a chunk.

    The Drive ingest pipeline prepends two layers of filename context
    to each chunk before embedding:

      1. ``[File: ...] [Folder: ...] [Type: ...]`` bracket lines.
      2. ``Document: <title>`` + ``This document is titled "<title>".``
         natural-prose lines.

    Both exist to give filename-keyword queries something to hit on in
    cosine search. When we hand the chunk to the LLM we want the clean
    body — the LLM gets the filename + Drive link as structured fields
    in the header we build separately.
    """
    if not chunk:
        return ""

    lines = chunk.splitlines()

    # Skip bracket-key header block.
    body_start = 0
    for i, line in enumerate(lines):
        s = line.strip()
        if not s:
            body_start = i + 1
            break
        if not (s.startswith("[") and s.endswith("]") and ":" in s):
            body_start = i
            break
    else:
        body_start = len(lines)

    # Skip the natural-prose title sentences if present (Document: …
    # and This document is titled "…".). They live immediately after
    # the bracket block, separated from the body by another blank line.
    while body_start < len(lines):
        s = lines[body_start].strip()
        if s.startswith("Document: ") or s.startswith(
            'This document is titled "'
        ):
            body_start += 1
            continue
        if not s:
            body_start += 1
            break
        break

    return "\n".join(lines[body_start:]).strip()


async def _search_knowledge_base(query: str, top_k: int = _KB_DEFAULT_TOP_K) -> str:
    """Semantic search across embedded Drive files, emails, notes, insights.

    Embeds the query with Voyage (input_type=query) → runs a cosine
    similarity lookup against the ``embeddings`` table → returns the
    top-K chunks as a flat string the LLM can quote from.

    Per source row we keep at most one chunk in the result set —
    duplicating long files would crowd out other matches.
    """
    if not query or not query.strip():
        return "No query supplied."

    try:
        k = max(1, min(int(top_k), _KB_MAX_TOP_K))
    except (TypeError, ValueError):
        k = _KB_DEFAULT_TOP_K

    try:
        vectors, _tokens = voyage_client.embed_batch(
            [query.strip()], input_type="query",
        )
    except voyage_client.VoyageError as exc:
        logger.warning("search_knowledge_base: embed failed — %s", exc)
        return "Knowledge base search is not available right now."

    if not vectors:
        return "Knowledge base search returned no results."

    query_vec = vectors[0]
    # pgvector cosine distance: smaller = closer. Cast to vector(1024)
    # so the operator binds correctly with parameter substitution.
    #
    # Two-stage query: the inner CTE ranks every chunk by distance and
    # numbers chunks within the same source row. The outer SELECT keeps
    # only rn=1 (the best chunk per source) and orders the survivors
    # by distance — so a top-K limit actually returns the K nearest
    # *source rows*, not the K source_ids that happen to sort first
    # alphabetically. (Earlier DISTINCT-ON-only version returned the
    # first K source_ids by UUID order, then re-sorted by distance —
    # which silently excluded the actual top hits.)
    sql = text("""
        WITH ranked AS (
            SELECT
                e.source_table,
                e.source_id,
                e.text_chunk,
                e.embedding <=> CAST(:q AS vector) AS distance,
                ROW_NUMBER() OVER (
                    PARTITION BY e.source_table, e.source_id
                    ORDER BY e.embedding <=> CAST(:q AS vector)
                ) AS rn
            FROM embeddings e
        )
        SELECT
            r.source_table,
            r.source_id,
            r.text_chunk,
            r.distance,
            gdf.name AS drive_name,
            gdf.web_view_link AS drive_link
        FROM ranked r
        LEFT JOIN google_drive_files gdf
          ON r.source_table = 'google_drive_files'
         AND gdf.id::text = r.source_id
        WHERE r.rn = 1
        ORDER BY r.distance
        LIMIT :k
    """)

    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                sql, {"q": str(query_vec), "k": k},
            )
            rows = result.fetchall()
    except Exception as exc:
        logger.warning("search_knowledge_base: query failed — %s", exc)
        return "Knowledge base search is not available right now."

    if not rows:
        return "No matching content found in the knowledge base."

    # SQL already returns rows in distance order with one row per
    # source. No additional sorting needed.
    lines: list[str] = []
    for row in rows:
        source_table = row[0]
        source_id = row[1]
        chunk = _strip_embedding_header(row[2] or "")
        drive_name = row[4]
        drive_link = row[5]
        if len(chunk) > _KB_CHUNK_PREVIEW_CHARS:
            chunk = chunk[:_KB_CHUNK_PREVIEW_CHARS].rsplit(" ", 1)[0] + "…"
        # Build a header the LLM can quote sensibly. Drive results get
        # a real filename + link; other sources fall back to the
        # polymorphic source-table tag so the LLM can still cite them.
        header_parts: list[str] = []
        if drive_name:
            header_parts.append(f"File: {drive_name}")
        if drive_link:
            header_parts.append(f"Link: {drive_link}")
        if not header_parts:
            header_parts.append(f"{source_table}#{source_id}")
        header = " | ".join(header_parts)
        lines.append(f"[{header}]\n{chunk}")

    return "\n\n---\n\n".join(lines)


# ---------------------------------------------------------------------------
# Calendar tool — structured time-window lookups
#
# Vector search alone can't answer "what's on Friday" (it doesn't
# understand temporal ranges). This tool gives the LLM a structured
# path to ask the calendar table directly. Semantic questions about
# events (e.g. "what was the budget review about") still go through
# search_knowledge_base — calendar events are embedded alongside Drive
# files and emails in the polymorphic embeddings table.
# ---------------------------------------------------------------------------


_CALENDAR_MAX_ROWS = 25


def _format_event_for_llm(row) -> str:
    """One human-readable line per event for the agent's response.

    Includes title + start time + organizer + attendee list. The LLM
    quotes from this without exposing the schema.
    """
    title = (row[0] or "(untitled event)").strip()
    start = row[1]
    end = row[2]
    is_all_day = bool(row[3])
    cal_name = row[4] or ""
    organizer = row[5] or ""
    attendees_json = row[6] or []
    location = row[7] or ""

    when = ""
    if start is not None:
        if is_all_day:
            when = f"All-day on {start.date().isoformat()}"
        elif end is not None:
            when = f"{start.isoformat()} → {end.isoformat()}"
        else:
            when = start.isoformat()

    attendee_emails = [
        a.get("email", "") for a in attendees_json if a.get("email")
    ]
    attendees_line = (
        f"attendees={', '.join(attendee_emails)}" if attendee_emails else ""
    )

    parts = [f'"{title}"']
    if when:
        parts.append(when)
    if cal_name:
        parts.append(f"on {cal_name}")
    if organizer:
        parts.append(f"organizer={organizer}")
    if attendees_line:
        parts.append(attendees_line)
    if location:
        parts.append(f"location={location}")
    return " | ".join(parts)


async def _query_calendar(
    start: str,
    end: str,
    attendee_email_contains: str = "",
) -> str:
    """Look up calendar events within a time window.

    Parameters
    ----------
    start, end : ISO 8601 timestamps (RFC 3339 ok). Window bounds.
    attendee_email_contains : optional case-insensitive substring match
        against attendee emails (e.g. "@lazaderm.com" to find every
        meeting with that domain).

    Returns a human-readable list of up to 25 events, one per line.
    """
    if not start or not end:
        return "Please supply both start and end timestamps."

    def _parse(s: str) -> datetime | None:
        try:
            v = s.replace("Z", "+00:00") if s.endswith("Z") else s
            dt = datetime.fromisoformat(v)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except (ValueError, TypeError):
            return None

    start_dt = _parse(start)
    end_dt = _parse(end)
    if start_dt is None or end_dt is None:
        return "Couldn't parse the start/end timestamps. Use ISO 8601 (e.g. '2026-05-30T00:00:00Z')."
    if end_dt < start_dt:
        return "End must be greater than or equal to start."

    params: dict[str, object] = {
        "start": start_dt,
        "end": end_dt,
        "limit": _CALENDAR_MAX_ROWS,
    }
    attendee_clause = ""
    if attendee_email_contains and attendee_email_contains.strip():
        params["addr"] = f"%{attendee_email_contains.strip().lower()}%"
        attendee_clause = """
            AND EXISTS (
                SELECT 1
                FROM jsonb_array_elements(coalesce(attendees, '[]'::jsonb)) a
                WHERE a->>'email' ILIKE :addr
            )
        """

    try:
        async with AsyncSessionLocal() as session:
            rows = (await session.execute(
                text(f"""
                    SELECT
                        title,
                        start_time,
                        end_time,
                        is_all_day,
                        calendar_name,
                        organizer_email,
                        attendees,
                        location
                    FROM google_calendar_events
                    WHERE start_time IS NOT NULL
                      AND start_time >= :start
                      AND start_time <= :end
                      {attendee_clause}
                    ORDER BY start_time ASC
                    LIMIT :limit
                """),
                params,
            )).fetchall()
    except Exception as exc:  # noqa: BLE001
        logger.warning("query_calendar tool error: %s", exc)
        return "Calendar lookup is not available right now."

    if not rows:
        return "No events in that window."

    lines = [_format_event_for_llm(row) for row in rows]
    out = "\n".join(lines)
    if len(rows) == _CALENDAR_MAX_ROWS:
        out += f"\n(Showing first {_CALENDAR_MAX_ROWS} results — narrow the window for more.)"
    return out


# ---------------------------------------------------------------------------
# Cross-department delegation
# ---------------------------------------------------------------------------
# Central Intelligence is the ONLY agent that reaches across departments. It
# delegates DOWN to the three Directors; Directors never call each other. Each
# delegate opens a FRESH AsyncSessionLocal and builds its director on the spot
# — CI is a long-lived per-session object, but DB sessions are per-request, so
# directors can't be held on the CI instance. The director runs its own tool
# loop (its specialists + data tools) and returns synthesized prose.


async def _delegate_to_director(task: str, dotted_path: str, label: str) -> str:
    """Run a Director against `task` with a fresh session and return its prose."""
    import importlib

    try:
        module_path, class_name = dotted_path.rsplit(".", 1)
        director_class = getattr(importlib.import_module(module_path), class_name)
        async with AsyncSessionLocal() as db:
            director = director_class(session=db)
            result = await director.execute(task)
        return result.get("response") or f"(The {label} returned no response.)"
    except Exception as exc:  # noqa: BLE001 — never crash the CI tool loop
        logger.exception("CI delegate to %s failed: %s", label, exc)
        return json.dumps({"error": f"Could not reach the {label} right now."})


async def _delegate_to_marketing_director(task: str) -> str:
    return await _delegate_to_director(
        task, "app.agents.directors.marketing.MarketingDirector", "Marketing Director"
    )


async def _delegate_to_sales_director(task: str) -> str:
    return await _delegate_to_director(
        task, "app.agents.directors.sales.SalesDirector", "Sales Director"
    )


async def _delegate_to_fulfillment_director(task: str) -> str:
    return await _delegate_to_director(
        task, "app.agents.directors.fulfillment.FulfillmentDirector", "Fulfillment Director"
    )


# ─── Analytics verdicts tool — the data-intelligence engine, as structured JSON ──
# Answers "how is the business / a department / a metric doing, what's improving or
# declining, what should be acted on" from the SAME engine that backs the Insights
# dashboard (app/routes/analytics.py). Returns strict JSON built ONLY from the
# engine's real computed values (registry.py catalog → trends.evaluate() verdicts →
# recommend.fetch_recommendation_rows() open findings) — the tool never fabricates
# a number; the LLM may only phrase what's returned.
#
# This is the ONLY analytics tool on CI. There is no separate ad-hoc prose reader —
# folding the previous helper in here avoids two paths to the same engine data.

_ANALYTICS_VALID_WINDOWS = {"7d", "30d", "90d", "all"}
_ANALYTICS_VALID_AREAS = {"sales", "marketing", "fulfillment"}


async def _get_analytics_verdicts(
    area: str | None = None,
    metric_key: str | None = None,
    window: str = "30d",
    rep: str | None = None,
) -> str:
    """Return the engine's trend verdicts + open recommendations as structured JSON.

    Every field is read straight off ``TrendResult`` / the ``recommendations`` table —
    nothing here is computed or guessed by this function or the LLM.

    ``rep`` (optional) scopes the result to one sales rep, resolved against
    ``sales_reps`` by rep_id / full_name / historical_aliases (see
    ``app.analytics.team.resolve_rep``). Unresolvable input returns a structured
    error with the known roster rather than guessing which rep was meant.
    """
    from app.analytics.trends import evaluate
    from app.analytics.registry import all_metrics, get_metric
    from app.analytics.recommend import fetch_recommendation_rows
    from app.analytics.team import RepRow, resolve_rep
    from app.database import AsyncSessionLocal
    from sqlalchemy import text

    window = window if window in _ANALYTICS_VALID_WINDOWS else "30d"

    if area is not None and area not in _ANALYTICS_VALID_AREAS:
        return json.dumps({
            "error": f"Unknown area '{area}'. Valid areas: "
                     f"{sorted(_ANALYTICS_VALID_AREAS)}.",
        })

    if metric_key is not None and get_metric(metric_key) is None:
        return json.dumps({"error": f"Unknown metric_key '{metric_key}'."})

    try:
        async with AsyncSessionLocal() as s:
            resolved_rep: RepRow | None = None
            scope = "global"
            if rep is not None and rep.strip():
                roster_rows = (await s.execute(text(
                    "SELECT rep_id, full_name, role, status, historical_aliases FROM sales_reps"
                ))).mappings().all()
                roster = [
                    RepRow(
                        rep_id=r["rep_id"], full_name=r["full_name"], role=r["role"],
                        status=r["status"], historical_aliases=r["historical_aliases"],
                    )
                    for r in roster_rows
                ]
                resolved_rep = resolve_rep(rep, roster)
                if resolved_rep is None:
                    return json.dumps({
                        "error": f"Could not match '{rep}' to a known sales rep.",
                        "known_reps": sorted(r.full_name for r in roster),
                    })
                scope = f"rep:{resolved_rep.rep_id}"

            metrics = [m for m in all_metrics() if area is None or m.area == area]
            if metric_key is not None:
                metrics = [m for m in metrics if m.key == metric_key]
            if resolved_rep is not None:
                # Rep scoping only makes sense for metrics with a per-rep breakdown.
                metrics = [m for m in metrics if m.rep_sql is not None]
            if not metrics:
                return json.dumps({
                    "window": window,
                    "metrics": [],
                    "recommendations": [],
                    "note": "No metrics are registered for the given filter(s).",
                })

            metric_out: list[dict] = []
            for m in metrics:
                rows = (await s.execute(text(
                    'SELECT value, sample_size, captured_date FROM metric_snapshots '
                    'WHERE metric_key = :k AND "window" = :w AND scope = :scope '
                    "ORDER BY captured_date ASC"
                ), {"k": m.key, "w": window, "scope": scope})).mappings().all()
                t = evaluate(m, [dict(r) for r in rows], window)
                metric_out.append({
                    "metric_key": t.metric_key,
                    "area": t.area,
                    "label": t.label,
                    "unit": t.unit,
                    "higher_is_better": t.higher_is_better,
                    "window": t.window,
                    "verdict": t.verdict,
                    "latest_value": t.latest_value,
                    "baseline_value": t.baseline_value,
                    "rel_change": t.rel_change,
                    "latest_sample": t.latest_sample,
                    "baseline_sample": t.baseline_sample,
                    "latest_date": t.latest_date,
                    "baseline_date": t.baseline_date,
                    "reason": t.reason,
                })

            # Open recommendations — same shared helper the HTTP API uses, so the
            # chat surface and the Insights dashboard never disagree.
            rec_rows = await fetch_recommendation_rows(
                s, area=area, scope=scope,
            )
            if metric_key is not None:
                rec_rows = [r for r in rec_rows if r["metric_key"] == metric_key]

            recommendations_out = [
                {
                    "metric_key": r["metric_key"],
                    "area": r["area"],
                    "window": r["window"],
                    "verdict": r["verdict"],
                    "severity": r["severity"],
                    "title": r["title"],
                    "body": r["body"],
                    "evidence": r["evidence"],
                    "status": r["status"],
                    "updated_at": r["updated_at"].isoformat() if r["updated_at"] else None,
                }
                for r in rec_rows
            ]

            result: dict = {
                "window": window,
                "metrics": metric_out,
                "recommendations": recommendations_out,
            }
            if resolved_rep is not None:
                result["rep"] = {
                    "rep_id": resolved_rep.rep_id,
                    "full_name": resolved_rep.full_name,
                    "role": resolved_rep.role,
                    "status": resolved_rep.status,
                }
            return json.dumps(result)
    except Exception as exc:  # noqa: BLE001 — never crash the CI tool loop
        logger.warning("get_analytics_verdicts tool error: %s", exc)
        return json.dumps({"error": "Couldn't read the analytics engine right now."})


class CentralIntelligence(BaseAgent):
    """CEO agent — orchestrates all departments.

    Each instance maintains its own conversation history, so callers
    are responsible for holding a reference per session.  Use the
    ``session_store`` in the route layer to map session_id → CentralIntelligence.
    """

    def __init__(self) -> None:
        super().__init__(
            agent_id="CI-CORE-00",
            name="Central Intelligence",
            model=settings.anthropic_model_default,
        )
        self.system_prompt = CENTRAL_INTELLIGENCE_SYSTEM_PROMPT_V1
        self._register_tools()
        logger.info("CentralIntelligence agent ready (agent_id=%s)", self.agent_id)

    # ------------------------------------------------------------------
    # Tool registration
    # ------------------------------------------------------------------

    def _register_tools(self) -> None:
        """Register tools that give Central Intelligence read access to the database."""
        self.register_tool(
            name="query_database",
            description=(
                "Look up business data: leads, members, calls, content ideas, "
                "insights, market signals, goals, pain points, wins, objections. "
                "Pass a PostgreSQL SELECT query. Results come back as a "
                "business-friendly summary, not raw data. "
                "Always use deleted_at IS NULL on tables that support it."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": (
                            "A PostgreSQL SELECT query. Always filter with "
                            "deleted_at IS NULL on tables that have soft-delete. "
                            "Return at most 50 rows."
                        ),
                    }
                },
                "required": ["sql"],
            },
            handler=_query_database,
        )

        self.register_tool(
            name="get_analytics_verdicts",
            description=(
                "Call this when the user asks how the business, a department, or a "
                "specific metric is doing, what's improving or declining, or what "
                "should be acted on. Returns the data-intelligence engine's "
                "statistical verdicts (improving / declining / flat / "
                "insufficient_data) for each outcome metric — with the exact change "
                "%, sample sizes, and dates behind each verdict — plus the engine's "
                "open recommendations (severity, title, evidence). This is the SAME "
                "engine that powers the Insights dashboard: every number is computed "
                "directly from real data, never guessed or estimated. Relay the "
                "returned verdicts, numbers, and recommendation text as-is — you may "
                "only rephrase them into natural language, never invent, adjust, or "
                "round a figure the tool didn't return. If a metric's verdict is "
                "'insufficient_data', say so rather than implying a trend exists. "
                "Pass the optional 'rep' field for rep-level questions (e.g. 'how is "
                "Makyla doing?') — it resolves the name against the sales roster and "
                "scopes the verdicts/recommendations to that one rep; an unresolvable "
                "name comes back as a structured error with the known rep names, "
                "which you should relay rather than guessing who was meant."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "area": {
                        "type": "string",
                        "description": "Optional area filter: 'sales', 'marketing', or "
                        "'fulfillment'. Omit for all areas.",
                    },
                    "metric_key": {
                        "type": "string",
                        "description": "Optional exact metric key to scope to a single "
                        "metric (e.g. 'sales.lead_to_close_rate'). Omit to get every "
                        "metric in the selected area(s).",
                    },
                    "window": {
                        "type": "string",
                        "description": "Lookback window: '7d', '30d' (default), '90d', or 'all'.",
                    },
                    "rep": {
                        "type": "string",
                        "description": "Optional sales rep name to scope the verdicts/"
                        "recommendations to just that rep (e.g. 'Makyla', 'Makyla "
                        "Thompson', or a known alias). Matched case-insensitively "
                        "against the sales roster. Omit for company-wide (global) "
                        "results.",
                    },
                },
                "required": [],
            },
            handler=_get_analytics_verdicts,
        )

        self.register_tool(
            name="search_knowledge_base",
            description=(
                "Semantic search across the org's knowledge base — Google "
                "Drive files (Docs, Sheets, Slides, PDFs, DOCX), email "
                "threads, lead staff-notes, and call insights. Use this "
                "for unstructured / 'find me anything about...' questions "
                "like \"what's our refund policy\", \"find files about Q3 "
                "budgets\", \"what did Jane say about pricing\". For "
                "structured business data (counts, status filters, lead "
                "lists) use query_database instead. Returns the top "
                "matching content chunks tagged with their source row."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "Natural-language search query. Be specific — "
                            "vector search rewards descriptive phrases over "
                            "single keywords."
                        ),
                    },
                    "top_k": {
                        "type": "integer",
                        "description": (
                            "How many source rows to return (default 10, max 25). "
                            "Increase if the first batch doesn't cover the answer."
                        ),
                    },
                },
                "required": ["query"],
            },
            handler=_search_knowledge_base,
        )

        self.register_tool(
            name="query_calendar",
            description=(
                "Look up calendar events in a specific time window. Use "
                "this for temporal questions like \"what's on my calendar "
                "Friday\", \"do I have anything with @lazaderm.com next "
                "week\", \"what meetings did I have last month\". Pass "
                "ISO 8601 timestamps for start + end. Optional "
                "attendee_email_contains does a case-insensitive substring "
                "match against attendee emails (e.g. \"@partner.com\" "
                "filters to events with that domain). Returns a "
                "human-readable list of up to 25 events. For semantic "
                "questions about what was discussed in a specific meeting "
                "(\"find the budget review meeting\"), use "
                "search_knowledge_base instead — events are embedded."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "start": {
                        "type": "string",
                        "description": (
                            "ISO 8601 lower bound (e.g. '2026-05-28T00:00:00Z'). "
                            "Pass the same date for both start and end to look "
                            "up a single day."
                        ),
                    },
                    "end": {
                        "type": "string",
                        "description": (
                            "ISO 8601 upper bound. Must be >= start."
                        ),
                    },
                    "attendee_email_contains": {
                        "type": "string",
                        "description": (
                            "Optional case-insensitive substring match on "
                            "any attendee's email. Empty string = no "
                            "attendee filter."
                        ),
                    },
                },
                "required": ["start", "end"],
            },
            handler=_query_calendar,
        )

        # --- Cross-department delegation to the three Directors --------------
        # CI is the only agent that spans departments. Use these for
        # department-specific questions (delegate to one) or broad strategy
        # questions like "what should we focus on this week?" (delegate to all
        # three, then synthesize). Directors run their own specialists.
        _DIRECTOR_DELEGATES = (
            (
                "delegate_to_marketing_director",
                "the Marketing Director — campaigns, content, email, social, ads, "
                "DM, offers, market signals, and content ideas",
                _delegate_to_marketing_director,
            ),
            (
                "delegate_to_sales_director",
                "the Sales Director — pipeline, leads, conversion, appointments, "
                "and sales-call insights",
                _delegate_to_sales_director,
            ),
            (
                "delegate_to_fulfillment_director",
                "the Fulfillment Director — members, coaching calls, accountability "
                "goals, wins, and tech-support tickets",
                _delegate_to_fulfillment_director,
            ),
        )
        for tool_name, scope, handler in _DIRECTOR_DELEGATES:
            self.register_tool(
                name=tool_name,
                description=(
                    f"Delegate a question or task to {scope}. Send a clear, "
                    "detailed instruction as 'task'. The director analyzes its "
                    "department (using its own specialists and data) and returns "
                    "findings. Use one director for a department-specific question; "
                    "delegate to all three for broad cross-department strategy, then "
                    "synthesize their answers into one response."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "task": {
                            "type": "string",
                            "description": (
                                "A detailed natural-language instruction for the "
                                "director (e.g. 'Summarize pipeline health and the "
                                "top reasons leads are stalling this week')."
                            ),
                        }
                    },
                    "required": ["task"],
                },
                handler=handler,
            )
