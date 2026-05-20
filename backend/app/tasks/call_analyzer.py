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
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.models.operational import Call, Insight
from app.prompts.call_analyzer_v1 import (
    CALL_ANALYZER_SYSTEM_PROMPT_V1,
    MOCK_CALL_ANALYZER_OUTPUT,
    build_user_prompt,
)
from app.tasks.celery_app import celery_app

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
    if not settings.anthropic_api_key or settings.mock_mode:
        logger.warning(
            "call_analyzer: Anthropic API key missing or mock_mode=True — using mock output."
        )
        mock = json.loads(MOCK_CALL_ANALYZER_OUTPUT)
        return mock.get("summary"), mock.get("insights", [])

    import anthropic  # lazy import — large module

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    user_prompt = build_user_prompt(transcript_text, call_type=call_type)

    message = client.messages.create(
        model="claude-sonnet-4-6",
        # The 21-field structured output for 3–8 insights can run long.
        # 8192 tokens gives ~6000 words of room — comfortable headroom.
        max_tokens=8192,
        system=CALL_ANALYZER_SYSTEM_PROMPT_V1,
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


def _write_insights(db: Session, call_id: str, insights: list[dict]) -> list[str]:
    """Persist a list of insight dicts as Insight rows linked to ``call_id``.

    Each row gets a fresh ``id`` (``INS_xxxxxxxxxxxx``). Fields missing from
    Claude's output are coerced to None (the model columns are nullable).
    """
    inserted_ids: list[str] = []
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

        insight = Insight(
            id=f"INS_{uuid4().hex[:12].upper()}",
            call_id=call_id,
            **kwargs,
        )
        db.add(insight)
        inserted_ids.append(insight.id)

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

        # Run Claude
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

        # Persist
        inserted_ids = _write_insights(db, call_id, insights)

        # Stamp the call as processed and write the narrative summary.
        call.processed_date = datetime.now(timezone.utc)
        if summary:
            call.summary = summary
        db.add(call)
        db.commit()

        is_mock = not settings.anthropic_api_key or settings.mock_mode

        logger.info(
            "analyze_call completed — task_id=%s call_id=%s insights=%d mock=%s",
            task_id,
            call_id,
            len(inserted_ids),
            is_mock,
        )

        return {
            "call_id": call_id,
            "insights_written": len(inserted_ids),
            "insight_ids": inserted_ids,
            "status": "mock" if is_mock else "completed",
        }

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
