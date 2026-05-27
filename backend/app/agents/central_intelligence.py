"""
CentralIntelligence — CEO/orchestrator agent for the Central Intelligence platform.

Sprint 1B: Database read access via query_database tool.
The tool returns business-friendly prose (never raw columns/rows) so
even a weaker model cannot accidentally leak schema details.
"""

import json
import logging

from sqlalchemy import text

from app.agents.base import BaseAgent
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
            model="claude-sonnet-4-6",
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
