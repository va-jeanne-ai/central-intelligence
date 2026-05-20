"""
ICP Generator Celery task — Operator CI-OPS-ICP.

Aggregates shared intelligence pool data (pain points, wins, objections,
goals, insights), synthesises ICP segments via Claude, and persists the
results to the ``icp`` table via ICPRepository logic.

Uses a synchronous SQLAlchemy session (psycopg2) because Celery workers
run outside FastAPI's async event loop.

Sprint 2 / VIR-24 / OPS-I1
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from celery.exceptions import MaxRetriesExceededError
from sqlalchemy import create_engine, func, select, update
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.models.operational import (
    ICP,
    Call,
    Goal,
    Insight,
    Lead,
    Member,
    Objection,
    PainPoint,
    Win,
)
from app.prompts.icp_generator_v1 import (
    ICP_GENERATOR_SYSTEM_PROMPT_V1,
    build_icp_user_prompt,
)
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Mock output for development / no-API-key fallback
# ---------------------------------------------------------------------------

_MOCK_ICP_OUTPUT = json.dumps([
    {
        "segment": "Primary",
        "description": "[MOCK] High-intent coaching buyer seeking rapid revenue growth.",
        "demographics": "Ages 32–45, online coaching/consulting, $5k–$50k/mo revenue stage.",
        "psychographics": "Identity-driven. Sees themselves as an expert but struggles with positioning.",
        "pain_summary": "1. Inconsistent lead flow. 2. Undercharging. 3. No scalable sales system.",
        "goal_summary": "Hit $20k/mo. Build a team. Become the go-to authority in their niche.",
        "buying_triggers": "Hit a revenue plateau. Just lost a client. Saw a competitor scale.",
        "common_objections": "Price: 'It's a lot of money' (real fear: won't get ROI).",
        "is_primary": True,
    }
])


# ---------------------------------------------------------------------------
# Sync DB session factory
# ---------------------------------------------------------------------------


def _get_sync_db_url(async_url: str) -> str:
    return async_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")


def _make_sync_session() -> Session:
    sync_url = _get_sync_db_url(settings.database_url)
    engine = create_engine(sync_url, pool_pre_ping=True)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    return SessionLocal()


# ---------------------------------------------------------------------------
# Intelligence pool aggregation (sync)
# ---------------------------------------------------------------------------


def _aggregate_intelligence(db: Session, date_range_days: int = 90) -> dict:
    """Aggregate shared intelligence pool data into a prompt-ready dict."""

    # Pain points
    pain_rows = db.execute(
        select(
            PainPoint.text,
            PainPoint.category,
            func.sum(PainPoint.frequency_count).label("frequency_count"),
        )
        .where(PainPoint.deleted_at.is_(None))
        .group_by(PainPoint.text, PainPoint.category)
        .order_by(func.sum(PainPoint.frequency_count).desc())
        .limit(50)
    ).all()
    pain_points = [
        {"text": r.text, "category": r.category, "frequency_count": r.frequency_count}
        for r in pain_rows
    ]

    # Wins
    win_rows = db.execute(
        select(Win)
        .where(Win.deleted_at.is_(None))
        .order_by(Win.created_at.desc())
        .limit(30)
    ).scalars().all()
    wins = [
        {
            "win_text": w.win_text,
            "impact_area": w.impact_area,
            "win_date": w.win_date.isoformat() if w.win_date else None,
        }
        for w in win_rows
    ]

    # Objections
    obj_rows = db.execute(
        select(Objection)
        .where(Objection.deleted_at.is_(None))
        .order_by(Objection.created_at.desc())
        .limit(30)
    ).scalars().all()
    objections = [
        {
            "objection_text": o.objection_text,
            "context": o.context,
            "resolution_offered": o.resolution_offered,
        }
        for o in obj_rows
    ]

    # Goals
    goal_rows = db.execute(
        select(Goal)
        .where(Goal.deleted_at.is_(None))
        .where(Goal.status == "active")
        .order_by(Goal.created_at.desc())
        .limit(50)
    ).scalars().all()
    goals = [{"goal_text": g.goal_text, "status": g.status} for g in goal_rows]

    # Insights
    ins_rows = db.execute(
        select(Insight)
        .order_by(Insight.frequency_score.desc())
        .limit(50)
    ).scalars().all()
    insights = [
        {
            "insight_type": i.insight_type,
            "signal_family": i.signal_family,
            "signal": i.signal,
            "frequency_score": i.frequency_score,
            "what_they_say": i.what_they_say,
            "the_real_problem": i.the_real_problem,
            "emotional_driver": i.emotional_driver,
            "core_fear_revealed": i.core_fear_revealed,
            "false_belief_revealed": i.false_belief_revealed,
            "buying_trigger": i.buying_trigger,
            "marketing_translation": i.marketing_translation,
        }
        for i in ins_rows
    ]

    lead_count = db.execute(
        select(func.count()).select_from(Lead).where(Lead.deleted_at.is_(None))
    ).scalar_one()
    member_count = db.execute(
        select(func.count()).select_from(Member).where(Member.deleted_at.is_(None))
    ).scalar_one()
    call_count = db.execute(
        select(func.count()).select_from(Call)
    ).scalar_one()

    return {
        "pain_points": pain_points,
        "wins": wins,
        "objections": objections,
        "goals": goals,
        "insights": insights,
        "total_leads": lead_count,
        "total_members": member_count,
        "total_calls_analyzed": call_count,
        "date_range_days": date_range_days,
    }


# ---------------------------------------------------------------------------
# Claude call (with mock fallback)
# ---------------------------------------------------------------------------


def _call_claude(user_prompt: str) -> list[dict]:
    """Call Claude with the ICP generator system prompt and return parsed segments.

    Falls back to mock output when ``ANTHROPIC_API_KEY`` is not configured or
    ``mock_mode`` is True.

    Returns
    -------
    list[dict]
        Parsed list of ICP segment dicts (1–3 items).
    """
    if not settings.anthropic_api_key or settings.mock_mode:
        logger.warning("Anthropic API key not configured — returning mock ICP output.")
        return json.loads(_MOCK_ICP_OUTPUT)

    import anthropic

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        system=ICP_GENERATOR_SYSTEM_PROMPT_V1,
        messages=[{"role": "user", "content": user_prompt}],
    )

    raw_text = message.content[0].text.strip()

    # Claude should return pure JSON per the output contract, but guard anyway.
    if raw_text.startswith("```"):
        raw_text = raw_text.split("```")[1]
        if raw_text.startswith("json"):
            raw_text = raw_text[4:]
        raw_text = raw_text.strip()

    return json.loads(raw_text)


# ---------------------------------------------------------------------------
# ICP persistence helpers (sync)
# ---------------------------------------------------------------------------


def _write_icp_segments(db: Session, segments: list[dict]) -> list[str]:
    """Persist ICP segments to the database and retire stale ones.

    Enforces the single-primary invariant: demotes all existing primary
    segments before inserting/updating the new primary.

    Parameters
    ----------
    segments:
        Parsed list of ICP segment dicts from Claude's JSON output.

    Returns
    -------
    list[str]
        Segment names that were written (used to retire stale segments).
    """
    segment_names = [s.get("segment", "") for s in segments]

    # Demote all existing primaries before writing
    db.execute(
        update(ICP)
        .where(ICP.deleted_at.is_(None))
        .where(ICP.is_primary.is_(True))
        .values(is_primary=False)
    )

    written_names: list[str] = []
    for seg_data in segments:
        segment = seg_data.get("segment", "")
        if not segment:
            logger.warning("Skipping ICP segment with empty name: %s", seg_data)
            continue

        existing = db.execute(
            select(ICP)
            .where(ICP.deleted_at.is_(None))
            .where(ICP.segment == segment)
        ).scalar_one_or_none()

        if existing is None:
            row = ICP(
                segment=segment,
                description=seg_data.get("description"),
                demographics=seg_data.get("demographics"),
                psychographics=seg_data.get("psychographics"),
                pain_summary=seg_data.get("pain_summary"),
                goal_summary=seg_data.get("goal_summary"),
                buying_triggers=seg_data.get("buying_triggers"),
                common_objections=seg_data.get("common_objections"),
                is_primary=bool(seg_data.get("is_primary", False)),
                status="active",
            )
            db.add(row)
        else:
            existing.description = seg_data.get("description", existing.description)
            existing.demographics = seg_data.get("demographics", existing.demographics)
            existing.psychographics = seg_data.get("psychographics", existing.psychographics)
            existing.pain_summary = seg_data.get("pain_summary", existing.pain_summary)
            existing.goal_summary = seg_data.get("goal_summary", existing.goal_summary)
            existing.buying_triggers = seg_data.get("buying_triggers", existing.buying_triggers)
            existing.common_objections = seg_data.get("common_objections", existing.common_objections)
            existing.is_primary = bool(seg_data.get("is_primary", False))
            existing.status = "active"

        written_names.append(segment)

    # Soft-delete stale segments not in this run's output
    stale_rows = db.execute(
        select(ICP)
        .where(ICP.deleted_at.is_(None))
        .where(ICP.segment.notin_(segment_names))
    ).scalars().all()

    now = datetime.now(tz=timezone.utc)
    for row in stale_rows:
        row.deleted_at = now

    db.commit()
    return written_names


# ---------------------------------------------------------------------------
# Celery task
# ---------------------------------------------------------------------------


@celery_app.task(bind=True, max_retries=3, default_retry_delay=120)
def generate_icp(self, date_range_days: int = 90) -> dict:
    """Aggregate intelligence data, synthesise ICP segments via Claude, persist results.

    This is the ICP Generator Operator (CI-OPS-ICP) as a Celery task.

    Parameters
    ----------
    date_range_days:
        Window of historical data to cover in the prompt context (default 90).

    Returns
    -------
    dict
        ``{"segments_written": N, "segment_names": [...], "status": "completed"|"mock"}``
    """
    task_id: str = self.request.id or "manual"
    logger.info("generate_icp started — task_id=%s date_range_days=%d", task_id, date_range_days)

    db: Session = _make_sync_session()
    try:
        # 1. Aggregate intelligence pool data
        intel_data = _aggregate_intelligence(db, date_range_days)
        logger.info(
            "Intelligence aggregated — leads=%d members=%d calls=%d pain_points=%d",
            intel_data["total_leads"],
            intel_data["total_members"],
            intel_data["total_calls_analyzed"],
            len(intel_data["pain_points"]),
        )

        # 2. Build prompt and call Claude
        user_prompt = build_icp_user_prompt(intel_data)
        segments = _call_claude(user_prompt)
        logger.info("Claude returned %d ICP segment(s)", len(segments))

        # 3. Persist to icp table
        written = _write_icp_segments(db, segments)
        logger.info("ICP segments written — names=%s", written)

        run_status = "mock" if (not settings.anthropic_api_key or settings.mock_mode) else "completed"
        return {
            "segments_written": len(written),
            "segment_names": written,
            "status": run_status,
        }

    except Exception as exc:
        db.rollback()
        logger.exception("generate_icp failed — task_id=%s error=%s", task_id, exc)
        try:
            raise self.retry(exc=exc)
        except MaxRetriesExceededError:
            logger.error("Max retries exceeded for generate_icp task_id=%s", task_id)
            raise

    finally:
        db.close()
