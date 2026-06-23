"""
Call Analyzer Celery task — Operator CI-OPS-CALL-ANALYZER.

Reads a Call's ``transcript_text``, calls Claude with the v1 extraction
prompt, and writes one or more ``Insight`` rows linked to the call via
``call_id``. This is the heart of the Sales Call Analyzer pipeline: it
turns raw transcript text into the structured Voice-of-Customer signals
that downstream features (CI Insights page, Market Signals, ICP
generation, scorecards) all consume.

Triggered three ways:
  - **Automatically** chained from ``transcribe_video`` after a successful
    transcription (the canonical flow for new uploads).
  - **Manually** via ``POST /api/v1/ci/calls/{call_id}/analyze`` to re-run
    on existing calls (e.g. after prompt iteration).
  - **Implicitly** when a transcript is pasted via
    ``POST /api/v1/ci/calls`` (the paste-then-analyze flow for testing).

F19 / Sprint — Sales Call Analyzer
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from uuid import uuid4

from celery.exceptions import MaxRetriesExceededError
from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.models.operational import Call, ContentIdea, Insight
from app.prompts._taxonomy import normalize_best_use_case
from app.prompts.call_analyzer_v1 import (
    CALL_ANALYZER_SYSTEM_PROMPT_V1,
    MOCK_CALL_ANALYZER_OUTPUT,
    build_user_prompt,
)
from app.prompts.coaching_analyzer_v1 import (
    COACHING_ANALYZER_SYSTEM_PROMPT_V1,
    MOCK_COACHING_ANALYZER_OUTPUT,
    build_coaching_user_prompt,
)
from app.prompts.content_idea_generator_v1 import (
    CONTENT_IDEA_GENERATOR_SYSTEM_PROMPT_V1,
    MOCK_CONTENT_IDEA_OUTPUT,
    build_content_idea_user_prompt,
)
from app.tasks.celery_app import celery_app


def _is_coaching(call_type: str | None) -> bool:
    """True when the call should use the coaching-tuned analyzer prompt."""
    return bool(call_type) and "coaching" in call_type.lower()

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Sync DB session factory (same pattern as transcriber.py — Celery runs
# outside FastAPI's async event loop so we use psycopg2 directly)
# ---------------------------------------------------------------------------


def _get_sync_db_url(async_url: str) -> str:
    return async_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")


def _make_sync_session() -> Session:
    sync_url = _get_sync_db_url(settings.database_url)
    engine = create_engine(sync_url, pool_pre_ping=True)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    return SessionLocal()


# ---------------------------------------------------------------------------
# Claude invocation + JSON parsing
# ---------------------------------------------------------------------------

# Strip ```json … ``` (or plain ```) wrappers Claude sometimes adds despite
# the prompt explicitly forbidding them.
_JSON_FENCE_RE = re.compile(
    r"^\s*```(?:json)?\s*\n?(.*?)\n?```\s*$",
    re.DOTALL | re.IGNORECASE,
)


def _extract_json_object(raw_text: str) -> str:
    """Pull the JSON object out of Claude's response.

    Handles the two common deviations from "pure JSON":
      1. Wrapped in ```json fences
      2. Has leading/trailing prose around the JSON

    Returns the JSON-object substring. Raises if no `{`-balanced object found.
    """
    stripped = raw_text.strip()

    # Case 1: fenced
    match = _JSON_FENCE_RE.match(stripped)
    if match:
        return match.group(1).strip()

    # Case 2: locate the outermost { ... } via brace-counting. Tolerates
    # leading "Here are the insights:" or similar prose.
    start = stripped.find("{")
    if start == -1:
        raise ValueError("No JSON object found in Claude response.")
    depth = 0
    for i in range(start, len(stripped)):
        c = stripped[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return stripped[start : i + 1]
    raise ValueError("Unbalanced JSON object in Claude response.")


def _call_claude(transcript_text: str, call_type: str | None) -> tuple[str | None, list[dict]]:
    """Call Claude with the v1 extraction prompt and return (summary, insights).

    Falls back to mock output when ``ANTHROPIC_API_KEY`` is unset or
    ``mock_mode`` is enabled.

    Returns
    -------
    tuple[str | None, list[dict]]
        ``(summary, insights)`` — summary is a narrative paragraph (or None
        if the model omitted it), insights is the 0–N list of structured
        dicts with the 21 Claude-extracted fields each.
    """
    # Coaching calls use the wins-first coaching analyzer; everything else
    # (sales, discovery, appointment) uses the original sales-flavoured prompt.
    coaching = _is_coaching(call_type)

    if not settings.anthropic_api_key or settings.mock_mode:
        logger.warning(
            "call_analyzer: Anthropic API key missing or mock_mode=True — using mock output."
        )
        mock_raw = MOCK_COACHING_ANALYZER_OUTPUT if coaching else MOCK_CALL_ANALYZER_OUTPUT
        mock = json.loads(mock_raw)
        return mock.get("summary"), mock.get("insights", [])

    import anthropic  # lazy import — large module

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    if coaching:
        system_prompt = COACHING_ANALYZER_SYSTEM_PROMPT_V1
        user_prompt = build_coaching_user_prompt(transcript_text, call_type=call_type)
    else:
        system_prompt = CALL_ANALYZER_SYSTEM_PROMPT_V1
        user_prompt = build_user_prompt(transcript_text, call_type=call_type)

    message = client.messages.create(
        model="claude-sonnet-4-6",
        # The 21-field structured output for 3–8 insights can run long.
        # 8192 tokens gives ~6000 words of room — comfortable headroom.
        max_tokens=8192,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )

    raw_text = message.content[0].text
    json_text = _extract_json_object(raw_text)
    parsed = json.loads(json_text)

    insights = parsed.get("insights", [])
    if not isinstance(insights, list):
        raise ValueError("Expected 'insights' to be a list in Claude output.")
    summary = parsed.get("summary")
    if summary is not None and not isinstance(summary, str):
        summary = None  # tolerate malformed; just drop it
    return summary, insights


def _call_claude_content_ideas(
    insights: list[dict], call_type: str | None, summary: str | None
) -> list[dict]:
    """Turn extracted insights into content-idea dicts via Claude.

    Mirrors ``_call_claude`` (same mock fallback + JSON extraction). Returns the
    0–N list of content-idea dicts (each carrying ``insight_id`` linking it back
    to its source insight). Returns ``[]`` when there are no insights to work
    from.
    """
    if not insights:
        return []

    if not settings.anthropic_api_key or settings.mock_mode:
        logger.warning(
            "content_idea_generator: Anthropic API key missing or mock_mode=True — using mock output."
        )
        return json.loads(MOCK_CONTENT_IDEA_OUTPUT).get("content_ideas", [])

    import anthropic  # lazy import — large module

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    message = client.messages.create(
        model="claude-sonnet-4-6",
        # 16-field briefs × up to 8 ideas can run long; 8192 gives headroom.
        max_tokens=8192,
        system=CONTENT_IDEA_GENERATOR_SYSTEM_PROMPT_V1,
        messages=[
            {
                "role": "user",
                "content": build_content_idea_user_prompt(
                    insights, call_type=call_type, summary=summary
                ),
            }
        ],
    )

    raw_text = message.content[0].text
    parsed = json.loads(_extract_json_object(raw_text))
    ideas = parsed.get("content_ideas", [])
    if not isinstance(ideas, list):
        raise ValueError("Expected 'content_ideas' to be a list in Claude output.")
    return ideas


# ---------------------------------------------------------------------------
# DB write
# ---------------------------------------------------------------------------


# The 21 Claude-extracted fields → Insight column names. Identity mapping
# but spelled out so a typo in the prompt schema fails loudly here.
_INSIGHT_FIELDS: tuple[str, ...] = (
    "speaker_name",
    "insight_type",
    "signal_family",
    "signal",
    "signal_strength",
    "pain_layer",
    "raw_quote",
    "what_they_say",
    "the_real_problem",
    "emotional_driver",
    "core_fear_revealed",
    "false_belief_revealed",
    "structural_obstacle",
    "identity_signal",
    "buying_trigger",
    "objection_created",
    "marketing_translation",
    "hook_angle_example",
    "best_use_case",
    "quote_confidence",
    "frequency_score",
)


def _write_insights(
    db: Session, call_id: str, insights: list[dict]
) -> tuple[list[str], list[dict]]:
    """Persist a list of insight dicts as Insight rows linked to ``call_id``.

    Each row gets a fresh ``id`` (``INS_xxxxxxxxxxxx``). Fields missing from
    Claude's output are coerced to None (the model columns are nullable).

    Returns ``(inserted_ids, persisted)`` where ``persisted`` is each written
    insight's fields plus its assigned ``insight_id`` — fed to the content-idea
    generator so the briefs it produces link back to real insight rows.
    """
    inserted_ids: list[str] = []
    persisted: list[dict] = []
    for raw in insights:
        if not isinstance(raw, dict):
            logger.warning("call_analyzer: skipping non-dict insight: %r", raw)
            continue

        kwargs = {field: raw.get(field) for field in _INSIGHT_FIELDS}
        # Coerce frequency_score (Claude may emit it as str): default to 1.
        freq = kwargs.get("frequency_score")
        if not isinstance(freq, int):
            try:
                kwargs["frequency_score"] = int(freq) if freq is not None else 1
            except (TypeError, ValueError):
                kwargs["frequency_score"] = 1

        # Enforce the best_use_case shape rule (no slash-combos / sentences) even
        # if the model ignored the prompt. Clean new single-purpose values pass.
        kwargs["best_use_case"] = normalize_best_use_case(kwargs.get("best_use_case"))

        new_id = f"INS_{uuid4().hex[:12].upper()}"
        insight = Insight(id=new_id, call_id=call_id, **kwargs)
        db.add(insight)
        inserted_ids.append(new_id)
        persisted.append({"insight_id": new_id, **kwargs})

    db.commit()
    return inserted_ids, persisted


# Claude content-idea field → ContentIdea column. Identity mapping, spelled out
# so a prompt-schema typo fails loudly here rather than silently dropping data.
_CONTENT_IDEA_FIELDS: tuple[str, ...] = (
    "insight_id",
    "source",
    "market_audience",
    "content_format",
    "content_angle",
    "trigger_insight",
    "raw_quote",
    "content_premise",
    "hook_opening_line",
    "teaching_point",
    "cta_idea",
    "priority_level",
    "best_platform",
    "repurpose_opportunities",
    "idea_score",
    "status",
)


def _write_content_ideas(
    db: Session, call_id: str, ideas: list[dict], valid_insight_ids: set[str]
) -> list[str]:
    """Persist content-idea dicts as ContentIdea rows linked to ``call_id``.

    Each row gets a fresh ``id`` (``CONT_xxxxxxxxxxxx``). ``insight_id`` is kept
    only when it points at an insight we just wrote (else NULL — the FK is
    ON DELETE SET NULL and Claude can hallucinate ids). ``idea_score`` is coerced
    to float; ``status`` defaults to "Idea".
    """
    inserted_ids: list[str] = []
    for raw in ideas:
        if not isinstance(raw, dict):
            logger.warning("content_idea_generator: skipping non-dict idea: %r", raw)
            continue

        kwargs = {field: raw.get(field) for field in _CONTENT_IDEA_FIELDS}

        # Drop a dangling insight_id rather than violating the FK.
        if kwargs.get("insight_id") not in valid_insight_ids:
            kwargs["insight_id"] = None

        score = kwargs.get("idea_score")
        if score is not None and not isinstance(score, (int, float)):
            try:
                kwargs["idea_score"] = float(score)
            except (TypeError, ValueError):
                kwargs["idea_score"] = None

        if not kwargs.get("status"):
            kwargs["status"] = "Idea"

        idea = ContentIdea(
            id=f"CONT_{uuid4().hex[:12].upper()}",
            call_id=call_id,
            **kwargs,
        )
        db.add(idea)
        inserted_ids.append(idea.id)

    db.commit()
    return inserted_ids


# ---------------------------------------------------------------------------
# Celery task
# ---------------------------------------------------------------------------


@celery_app.task(bind=True, max_retries=2, default_retry_delay=60)
def analyze_call(self, call_id: str) -> dict:
    """Extract Insight rows from a Call's transcript.

    Parameters
    ----------
    call_id:
        The ``CALL_xxxxxxxx`` identifier of the Call row to analyse.

    Returns
    -------
    dict
        ``{"call_id": "...", "insights_written": N, "insight_ids": [...],
            "status": "completed" | "skipped" | "mock"}``

        - ``completed``: real Claude run, ≥0 insights written.
        - ``skipped``: call not found, no transcript text, or mock-transcript
          placeholder. Caller should treat as a no-op success.
        - ``mock``: insights came from MOCK_CALL_ANALYZER_OUTPUT because
          Anthropic API key was unset.
    """
    task_id = self.request.id or uuid4().hex
    logger.info("analyze_call started — task_id=%s call_id=%s", task_id, call_id)

    db = _make_sync_session()
    try:
        call = db.execute(select(Call).where(Call.id == call_id)).scalar_one_or_none()
        if call is None:
            logger.warning("analyze_call: call_id=%s not found", call_id)
            return {
                "call_id": call_id,
                "insights_written": 0,
                "insight_ids": [],
                "status": "skipped",
                "reason": "call_not_found",
            }

        transcript = (call.transcript_text or "").strip()
        if not transcript:
            logger.info("analyze_call: call_id=%s has empty transcript", call_id)
            return {
                "call_id": call_id,
                "insights_written": 0,
                "insight_ids": [],
                "status": "skipped",
                "reason": "empty_transcript",
            }

        # Skip the mock-transcript placeholder produced by transcribe_video
        # when OPENAI_API_KEY is missing. Avoids running Claude on the
        # literal string "[MOCK TRANSCRIPT] No OpenAI API key configured."
        if transcript.startswith("[MOCK TRANSCRIPT]"):
            logger.info("analyze_call: call_id=%s has mock transcript — skipping", call_id)
            return {
                "call_id": call_id,
                "insights_written": 0,
                "insight_ids": [],
                "status": "skipped",
                "reason": "mock_transcript",
            }

        # Run Claude — insight extraction, then content-idea generation from
        # those insights. Both are part of one analysis pass so "Re-analyze"
        # regenerates the full downstream (insights + content ideas).
        try:
            summary, insights = _call_claude(transcript, call_type=call.call_type)
        except Exception as exc:
            logger.exception(
                "analyze_call: Claude call failed — task_id=%s call_id=%s error=%s",
                task_id,
                call_id,
                exc,
            )
            try:
                raise self.retry(exc=exc)
            except MaxRetriesExceededError:
                logger.error(
                    "analyze_call: max retries exceeded for call_id=%s — aborting",
                    call_id,
                )
                raise

        # Re-analyze cleanly: drop this call's prior insights AND content ideas
        # before writing the new batch, so a regen doesn't leave stale rows.
        # InsightTag rows cascade-delete with their parent Insight. Content ideas
        # are scoped to this call_id (the unit being re-analyzed).
        deleted = db.execute(delete(Insight).where(Insight.call_id == call_id)).rowcount
        if deleted:
            logger.info("analyze_call: cleared %d prior insights for call_id=%s", deleted, call_id)
        deleted_ci = db.execute(
            delete(ContentIdea).where(ContentIdea.call_id == call_id)
        ).rowcount
        if deleted_ci:
            logger.info(
                "analyze_call: cleared %d prior content ideas for call_id=%s", deleted_ci, call_id
            )

        inserted_ids, persisted_insights = _write_insights(db, call_id, insights)

        # Generate content ideas from the just-written insights. Failure here is
        # non-fatal — the call is still successfully analyzed with its insights;
        # log and move on rather than retrying the whole task.
        content_idea_ids: list[str] = []
        try:
            ideas = _call_claude_content_ideas(
                persisted_insights, call_type=call.call_type, summary=summary
            )
            valid_ids = {i["insight_id"] for i in persisted_insights}
            content_idea_ids = _write_content_ideas(db, call_id, ideas, valid_ids)
        except Exception as exc:
            logger.exception(
                "analyze_call: content-idea generation failed (non-fatal) — "
                "call_id=%s error=%s",
                call_id,
                exc,
            )

        # Stamp the call as processed and overwrite the narrative summary.
        # summary is overwritten unconditionally on re-analyze (even to None)
        # so the UI never shows stale text after a regen.
        call.processed_date = datetime.now(timezone.utc)
        call.summary = summary
        db.add(call)
        db.commit()

        is_mock = not settings.anthropic_api_key or settings.mock_mode

        logger.info(
            "analyze_call completed — task_id=%s call_id=%s insights=%d content_ideas=%d mock=%s",
            task_id,
            call_id,
            len(inserted_ids),
            len(content_idea_ids),
            is_mock,
        )

        return {
            "call_id": call_id,
            "insights_written": len(inserted_ids),
            "content_ideas_written": len(content_idea_ids),
            "insight_ids": inserted_ids,
            "status": "mock" if is_mock else "completed",
        }

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
