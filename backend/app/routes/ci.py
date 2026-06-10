"""Central Intelligence (CI) webhook endpoints.

Implements 13 REST endpoints for the CI subsystem plus two data sync bridges:
- CI-MKT-01: 13 FastAPI webhook endpoints for CI data
- CI-MKT-02: Data sync bridge — CI insights -> shared intelligence tables
- CI-MKT-03: Data sync bridge — CI content_ideas -> content_ideas table
"""

import logging
import math
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models.intelligence import (
    InsightTag,
    MarketSignal,
    MonthlyPreference,
    Offer,
    TagDictionary,
)
from app.models.operational import (
    Call,
    ContentIdea,
    Goal,
    Insight,
    Objection,
    PainPoint,
    Win,
)
from app.repositories.intelligence import (
    MarketSignalRepository,
    MonthlyPreferenceRepository,
    OfferRepository,
    TagDictionaryRepository,
)
from app.repositories.operational import (
    CallRepository,
    ContentIdeaRepository,
    GoalRepository,
    InsightRepository,
    ObjectionRepository,
    PainPointRepository,
    WinRepository,
)
from app.schemas.ci import (
    AnalyzeCallResponse,
    CallDetail,
    CallDetailResponse,
    CallListResponse,
    CallSummary,
    ContentIdeaBrief,
    ContentIdeaListResponse,
    ContentIdeaSummary,
    CreateCallFromTranscriptRequest,
    CreateCallFromTranscriptResponse,
    CreateContentIdeaRequest,
    InsightBrief,
    InsightDetail,
    InsightDetailResponse,
    InsightListResponse,
    InsightSummary,
    MarketSignalItem,
    MarketSignalListResponse,
    MonthlyPreferenceResponse,
    OfferItem,
    OfferListResponse,
    PaginationMeta,
    ProcessTranscriptRequest,
    ProcessTranscriptResponse,
    SyncResult,
    TagItem,
    TagListResponse,
    UpdateCallRequest,
    UpdateContentIdeaRequest,
    UpdateContentIdeaResponse,
    UpdateInsightRequest,
    UpdateMonthlyPreferencesRequest,
    UploadTranscriptRequest,
    UploadTranscriptResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ci", tags=["Central Intelligence"])


# ---------------------------------------------------------------------------
# EC-08: Content idea status transition table
# ---------------------------------------------------------------------------

# Maps each current status to the set of allowed next statuses.
# An empty list means the status is terminal (no further transitions).
CONTENT_IDEA_VALID_TRANSITIONS: dict[str, list[str]] = {
    "new": ["in_progress", "Idea"],
    "Idea": ["in_progress", "Scheduled", "Archived"],
    "in_progress": ["used", "Written", "Scheduled"],
    "Scheduled": ["Written", "Sent", "Archived", "in_progress"],
    "Written": ["Sent", "Archived", "used"],
    "used": ["archived", "Archived"],
    "Sent": ["Archived"],
    "Archived": [],
    "archived": [],
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _pagination(page: int, limit: int, total: int) -> PaginationMeta:
    total_pages = max(1, math.ceil(total / limit))
    return PaginationMeta(
        page=page,
        limit=limit,
        total=total,
        totalPages=total_pages,
        hasNextPage=page < total_pages,
        hasPreviousPage=page > 1,
    )


# ===================================================================
# 1. POST /ci/transcripts/upload
# ===================================================================

@router.post("/transcripts/upload", response_model=UploadTranscriptResponse, status_code=202)
async def upload_transcript(
    body: UploadTranscriptRequest,
    session: AsyncSession = Depends(get_session),
):
    """Upload a transcript file for processing (CI-MKT-01)."""
    import base64
    import hashlib
    import uuid

    try:
        decoded = base64.b64decode(body.file_content)
    except Exception:
        raise HTTPException(status_code=400, detail={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "file_content must be valid base64",
                "field": "file_content",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        })

    transcript_text = decoded.decode("utf-8", errors="replace")
    call_id = f"CALL_{uuid.uuid4().hex[:12].upper()}"

    # Optional entity links (best-effort: ignore malformed UUIDs rather than
    # 400, matching the POST /ci/calls create-from-transcript behaviour).
    lead_uuid: uuid.UUID | None = None
    if body.lead_id:
        try:
            lead_uuid = uuid.UUID(body.lead_id)
        except ValueError:
            lead_uuid = None
    member_uuid: uuid.UUID | None = None
    if body.member_id:
        try:
            member_uuid = uuid.UUID(body.member_id)
        except ValueError:
            member_uuid = None

    call_repo = CallRepository(session)
    await call_repo.create(
        id=call_id,
        call_type=body.call_type,
        call_owner=body.call_owner,
        transcript_source="ci_upload",
        transcript_text=transcript_text,
        date=datetime.now(timezone.utc),
        lead_id=lead_uuid,
        member_id=member_uuid,
    )

    return UploadTranscriptResponse(
        call_id=call_id,
        status="processing",
        message="Transcript queued for processing",
    )


# ===================================================================
# 2. POST /ci/transcripts/process
# ===================================================================

@router.post("/transcripts/process", response_model=ProcessTranscriptResponse)
async def process_transcript(
    body: ProcessTranscriptRequest,
    session: AsyncSession = Depends(get_session),
):
    """Trigger processing of a previously uploaded transcript (CI-MKT-01)."""
    call_repo = CallRepository(session)
    call = await call_repo.get(body.call_id)
    if call is None:
        raise HTTPException(status_code=404, detail={
            "error": {
                "code": "NOT_FOUND",
                "message": f"Call {body.call_id} not found",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        })

    # Mark as processed
    call.processed_date = datetime.now(timezone.utc)
    session.add(call)
    await session.flush()

    # Count associated insights, content ideas, tags
    insights_count = (await session.execute(
        select(func.count()).select_from(Insight).where(Insight.call_id == body.call_id)
    )).scalar_one()
    content_ideas_count = (await session.execute(
        select(func.count()).select_from(ContentIdea).where(ContentIdea.call_id == body.call_id)
    )).scalar_one()
    tags_count = (await session.execute(
        select(func.count()).select_from(InsightTag)
        .join(Insight, InsightTag.insight_id == Insight.id)
        .where(Insight.call_id == body.call_id)
    )).scalar_one()

    return ProcessTranscriptResponse(
        call_id=body.call_id,
        insights_count=insights_count,
        content_ideas_count=content_ideas_count,
        tags_count=tags_count,
        status="completed",
    )


# ===================================================================
# 3. GET /ci/calls
# ===================================================================

@router.get("/calls", response_model=CallListResponse)
async def list_calls(
    call_type: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    call_owner: str | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
):
    """List processed calls with filters (CI-MKT-01)."""
    stmt = select(Call)
    count_stmt = select(func.count()).select_from(Call)

    if call_type:
        stmt = stmt.where(Call.call_type == call_type)
        count_stmt = count_stmt.where(Call.call_type == call_type)
    if call_owner:
        stmt = stmt.where(Call.call_owner == call_owner)
        count_stmt = count_stmt.where(Call.call_owner == call_owner)
    if date_from:
        dt_from = datetime.fromisoformat(date_from)
        stmt = stmt.where(Call.date >= dt_from)
        count_stmt = count_stmt.where(Call.date >= dt_from)
    if date_to:
        dt_to = datetime.fromisoformat(date_to)
        stmt = stmt.where(Call.date <= dt_to)
        count_stmt = count_stmt.where(Call.date <= dt_to)

    total = (await session.execute(count_stmt)).scalar_one()

    stmt = stmt.order_by(Call.date.desc().nullslast()).offset((page - 1) * limit).limit(limit)
    result = await session.execute(stmt)
    calls = result.scalars().all()

    # Get insight counts per call
    data = []
    for c in calls:
        ins_count = (await session.execute(
            select(func.count()).select_from(Insight).where(Insight.call_id == c.id)
        )).scalar_one()
        data.append(CallSummary(
            call_id=c.id,
            date=c.date,
            call_type=c.call_type,
            call_result=c.call_result,
            call_owner=c.call_owner,
            transcript_quality=c.transcript_quality,
            processed_date=c.processed_date,
            insights_count=ins_count,
        ))

    return CallListResponse(data=data, pagination=_pagination(page, limit, total))


# ===================================================================
# 4. GET /ci/calls/:call_id
# ===================================================================

@router.get("/calls/{call_id}", response_model=CallDetailResponse)
async def get_call(
    call_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Get call detail with associated insights and content ideas (CI-MKT-01)."""
    call_repo = CallRepository(session)
    call = await call_repo.get(call_id)
    if call is None:
        raise HTTPException(status_code=404, detail={
            "error": {
                "code": "NOT_FOUND",
                "message": "Call not found",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        })

    insight_repo = InsightRepository(session)
    insights = await insight_repo.find_by_call(call_id)

    content_repo = ContentIdeaRepository(session)
    stmt = select(ContentIdea).where(ContentIdea.call_id == call_id)
    result = await session.execute(stmt)
    content_ideas = result.scalars().all()

    return CallDetailResponse(
        call=CallDetail(
            call_id=call.id,
            date=call.date,
            call_type=call.call_type,
            call_result=call.call_result,
            call_owner=call.call_owner,
            transcript_quality=call.transcript_quality,
            processed_date=call.processed_date,
            transcript=call.transcript_text,
            summary=call.summary,
            created_at=call.created_at,
        ),
        insights=[
            InsightBrief(
                insight_id=i.id,
                insight_type=i.insight_type,
                signal_family=i.signal_family,
                signal=i.signal,
                raw_quote=i.raw_quote,
            )
            for i in insights
        ],
        content_ideas=[
            ContentIdeaBrief(
                content_id=ci.id,
                content_format=ci.content_format,
                status=ci.status,
                priority_level=ci.priority_level,
                idea_score=ci.idea_score,
            )
            for ci in content_ideas
        ],
    )


# ===================================================================
# 4a. GET /ci/calls/{call_id}/transcript.txt — download transcript file
# ===================================================================


@router.get(
    "/calls/{call_id}/transcript.txt",
    response_class=PlainTextResponse,
)
async def download_call_transcript(
    call_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Stream the transcript .txt artifact for a Call.

    Reads from the on-disk file written by the transcriber/paste endpoints.
    Falls back to ``Call.transcript_text`` when the file is missing (covers
    calls ingested before the file-store feature shipped).
    """
    from app.storage.transcripts import get_transcript_path

    path = get_transcript_path(call_id)
    if path.exists():
        text = path.read_text(encoding="utf-8")
    else:
        call = await CallRepository(session).get(call_id)
        if call is None:
            raise HTTPException(status_code=404, detail="Call not found")
        if not call.transcript_text:
            raise HTTPException(status_code=404, detail="No transcript on file")
        text = call.transcript_text

    return Response(
        content=text,
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{call_id}.txt"'},
    )


# ===================================================================
# 4b. POST /ci/calls — create a call by pasting a transcript (F19)
# ===================================================================


@router.post("/calls", response_model=CreateCallFromTranscriptResponse, status_code=201)
async def create_call_from_transcript(
    body: CreateCallFromTranscriptRequest,
    session: AsyncSession = Depends(get_session),
):
    """Create a Call row with a pre-existing transcript and trigger the
    Sales Call Analyzer.

    This is the "paste transcript" ingestion path — skips Whisper entirely.
    Used for testing the analyzer, and for transcripts that came from a
    third-party source (Otter, Fireflies, manual stenography, etc.).

    F19 — Sales Call Analyzer pipeline.
    """
    from uuid import uuid4 as _uuid4

    text = body.transcript_text.strip()
    if not text:
        raise HTTPException(status_code=422, detail="transcript_text cannot be empty")

    call_id = f"CALL_{_uuid4().hex[:12].upper()}"
    call = Call(
        id=call_id,
        call_type=body.call_type or "sales_call",
        call_owner=body.call_owner,
        transcript_source="manual_paste",
        transcript_text=text,
        processed_date=None,  # set when analyze_call finishes
    )
    # Optional FK links — present when the caller knows the lineage.
    if body.lead_id:
        try:
            from uuid import UUID
            call.lead_id = UUID(body.lead_id)
        except ValueError:
            pass  # silently ignore malformed UUID; transcript still ingests
    if body.member_id:
        try:
            from uuid import UUID
            call.member_id = UUID(body.member_id)
        except ValueError:
            pass

    session.add(call)
    await session.commit()
    await session.refresh(call)

    # Persist the transcript as a browsable .txt artifact.
    try:
        from app.storage.transcripts import save_transcript
        save_transcript(call_id, text)
    except Exception as exc:
        logger.warning("Failed to save transcript file — call_id=%s error=%s", call_id, exc)

    # Chain the analyzer. .delay() is sync — Celery's broker queue write is
    # local Redis, fast — and returns the task object immediately.
    from app.tasks.call_analyzer import analyze_call

    try:
        task = analyze_call.delay(call_id)
        task_id: str | None = task.id
        status = "queued_for_analysis"
    except Exception as exc:
        logger.warning(
            "create_call_from_transcript: failed to enqueue analyzer — call_id=%s error=%s",
            call_id,
            exc,
        )
        task_id = None
        status = "created"  # Call exists, but analysis didn't queue.

    return CreateCallFromTranscriptResponse(
        call_id=call_id,
        analyzer_task_id=task_id,
        status=status,
    )


# ===================================================================
# 4c. POST /ci/calls/{call_id}/analyze — re-run analyzer on existing call (F19)
# ===================================================================


@router.post("/calls/{call_id}/analyze", response_model=AnalyzeCallResponse)
async def trigger_call_analysis(call_id: str):
    """Re-run the Sales Call Analyzer on an existing Call row.

    Useful for:
      - Iterating on the analyzer prompt and re-processing prior calls.
      - Manually triggering analysis if the auto-chain in transcribe_video
        failed (the chain is best-effort and logged-but-not-failed there).

    Does NOT delete prior insights — re-running appends new ones. To replace
    a call's insights cleanly, delete from `insights WHERE call_id = ...`
    first, then call this. (Soft-delete pattern would be cleaner; not done
    yet — Insight doesn't have a deleted_at column.)
    """
    from app.tasks.call_analyzer import analyze_call

    task = analyze_call.delay(call_id)
    logger.info("trigger_call_analysis — call_id=%s task_id=%s", call_id, task.id)
    return AnalyzeCallResponse(
        call_id=call_id,
        task_id=task.id,
        status="queued",
        message=(
            "Analysis queued. Poll GET /api/v1/ci/insights?call_id=... "
            "after ~30-60s to see results."
        ),
    )


# ===================================================================
# 4d. PATCH /ci/calls/{call_id} — inline-edit summary / metadata
# ===================================================================


@router.patch("/calls/{call_id}", response_model=CallDetail)
async def update_call(
    call_id: str,
    body: UpdateCallRequest,
    session: AsyncSession = Depends(get_session),
):
    """Partial update of a Call's editable fields.

    Used by the call detail page's inline editors. Only fields present in the
    request body are written — null vs unset is distinguished via
    ``model_dump(exclude_unset=True)``. Empty string is treated as "clear".
    """
    call = await CallRepository(session).get(call_id)
    if call is None:
        raise HTTPException(status_code=404, detail="Call not found")

    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(call, field, value)

    session.add(call)
    await session.commit()
    await session.refresh(call)

    return CallDetail(
        call_id=call.id,
        date=call.date,
        call_type=call.call_type,
        call_result=call.call_result,
        call_owner=call.call_owner,
        transcript_quality=call.transcript_quality,
        processed_date=call.processed_date,
        transcript=call.transcript_text,
        summary=call.summary,
        created_at=call.created_at,
    )


# ===================================================================
# 5. GET /ci/insights
# ===================================================================

@router.get("/insights", response_model=InsightListResponse)
async def list_insights(
    call_id: str | None = Query(None),
    insight_type: str | None = Query(None),
    signal_family: str | None = Query(None),
    signal_strength: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
):
    """Query insights with filters (CI-MKT-01)."""
    stmt = select(Insight)
    count_stmt = select(func.count()).select_from(Insight)

    if call_id:
        stmt = stmt.where(Insight.call_id == call_id)
        count_stmt = count_stmt.where(Insight.call_id == call_id)
    if insight_type:
        stmt = stmt.where(Insight.insight_type == insight_type)
        count_stmt = count_stmt.where(Insight.insight_type == insight_type)
    if signal_family:
        stmt = stmt.where(Insight.signal_family == signal_family)
        count_stmt = count_stmt.where(Insight.signal_family == signal_family)
    if signal_strength:
        stmt = stmt.where(Insight.signal_strength == signal_strength)
        count_stmt = count_stmt.where(Insight.signal_strength == signal_strength)
    if date_from:
        dt_from = datetime.fromisoformat(date_from)
        stmt = stmt.where(Insight.created_at >= dt_from)
        count_stmt = count_stmt.where(Insight.created_at >= dt_from)
    if date_to:
        dt_to = datetime.fromisoformat(date_to)
        stmt = stmt.where(Insight.created_at <= dt_to)
        count_stmt = count_stmt.where(Insight.created_at <= dt_to)

    total = (await session.execute(count_stmt)).scalar_one()

    stmt = (
        stmt.order_by(Insight.frequency_score.desc())
        .offset((page - 1) * limit)
        .limit(limit)
    )
    result = await session.execute(stmt)
    insights = result.scalars().all()

    return InsightListResponse(
        data=[
            InsightSummary(
                insight_id=i.id,
                call_id=i.call_id,
                speaker_name=i.speaker_name,
                insight_type=i.insight_type,
                signal_family=i.signal_family,
                signal=i.signal,
                signal_strength=i.signal_strength,
                raw_quote=i.raw_quote,
                marketing_translation=i.marketing_translation,
                hook_angle_example=i.hook_angle_example,
                best_use_case=i.best_use_case,
                quote_confidence=i.quote_confidence,
                frequency_score=i.frequency_score,
            )
            for i in insights
        ],
        pagination=_pagination(page, limit, total),
    )


# ===================================================================
# 6. GET /ci/insights/:insight_id
# ===================================================================

@router.get("/insights/{insight_id}", response_model=InsightDetailResponse)
async def get_insight(
    insight_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Get single insight with full detail (CI-MKT-01)."""
    insight_repo = InsightRepository(session)
    insight = await insight_repo.get(insight_id)
    if insight is None:
        raise HTTPException(status_code=404, detail={
            "error": {
                "code": "NOT_FOUND",
                "message": "Insight not found",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        })

    # Tags
    tag_stmt = select(InsightTag.tag).where(InsightTag.insight_id == insight_id)
    tag_result = await session.execute(tag_stmt)
    tags = [row[0] for row in tag_result.all() if row[0]]

    # Related content ideas
    ci_stmt = select(ContentIdea).where(ContentIdea.insight_id == insight_id)
    ci_result = await session.execute(ci_stmt)
    content_ideas = ci_result.scalars().all()

    return InsightDetailResponse(
        insight=InsightDetail(
            insight_id=insight.id,
            call_id=insight.call_id,
            speaker_name=insight.speaker_name,
            insight_type=insight.insight_type,
            signal_family=insight.signal_family,
            signal=insight.signal,
            signal_strength=insight.signal_strength,
            pain_layer=insight.pain_layer,
            raw_quote=insight.raw_quote,
            what_they_say=insight.what_they_say,
            the_real_problem=insight.the_real_problem,
            emotional_driver=insight.emotional_driver,
            core_fear_revealed=insight.core_fear_revealed,
            false_belief_revealed=insight.false_belief_revealed,
            structural_obstacle=insight.structural_obstacle,
            identity_signal=insight.identity_signal,
            buying_trigger=insight.buying_trigger,
            objection_created=insight.objection_created,
            marketing_translation=insight.marketing_translation,
            hook_angle_example=insight.hook_angle_example,
            best_use_case=insight.best_use_case,
            quote_confidence=insight.quote_confidence,
            frequency_score=insight.frequency_score,
            created_at=insight.created_at,
        ),
        tags=tags,
        related_content_ideas=[
            ContentIdeaBrief(
                content_id=ci.id,
                content_format=ci.content_format,
                status=ci.status,
                priority_level=ci.priority_level,
                idea_score=ci.idea_score,
            )
            for ci in content_ideas
        ],
    )


# ===================================================================
# 6b. PATCH /ci/insights/{insight_id} — inline-edit a single insight
# ===================================================================


@router.patch("/insights/{insight_id}", response_model=InsightBrief)
async def update_insight(
    insight_id: str,
    body: UpdateInsightRequest,
    session: AsyncSession = Depends(get_session),
):
    """Partial update of an Insight's editable fields shown on the call detail page."""
    insight_repo = InsightRepository(session)
    insight = await insight_repo.get(insight_id)
    if insight is None:
        raise HTTPException(status_code=404, detail="Insight not found")

    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(insight, field, value)

    session.add(insight)
    await session.commit()
    await session.refresh(insight)

    return InsightBrief(
        insight_id=insight.id,
        insight_type=insight.insight_type,
        signal_family=insight.signal_family,
        signal=insight.signal,
        raw_quote=insight.raw_quote,
    )


# ===================================================================
# 6c. DELETE /ci/insights/{insight_id} — remove an insight
# ===================================================================


@router.delete("/insights/{insight_id}", status_code=204)
async def delete_insight(
    insight_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Hard-delete an Insight. InsightTag rows cascade; ContentIdea links go to NULL."""
    deleted = await InsightRepository(session).delete(insight_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Insight not found")
    await session.commit()
    return None


# ===================================================================
# 7. POST /ci/content-ideas — manual create (added 2026-05-20 for F13)
# ===================================================================


@router.post("/content-ideas", response_model=ContentIdeaSummary)
async def create_content_idea(
    body: CreateContentIdeaRequest,
    session: AsyncSession = Depends(get_session),
):
    """Create a content idea manually from the UI.

    Maps frontend `{title, platform, status}` onto the richer `ContentIdea`
    model: `title` → `content_premise`, `platform` → `content_format`.
    Other fields (insight_id, call_id, raw_quote, etc.) are left null because
    a manual idea has no extraction lineage.
    """
    from uuid import uuid4

    idea = ContentIdea(
        id=f"CONT_{uuid4().hex[:12]}",
        content_premise=body.title,
        content_format=body.platform,
        status=body.status,
        source="manual",
    )
    session.add(idea)
    await session.commit()
    await session.refresh(idea)

    return ContentIdeaSummary(
        content_id=idea.id,
        insight_id=idea.insight_id,
        call_id=idea.call_id,
        content_format=idea.content_format,
        content_premise=idea.content_premise,
        status=idea.status,
        priority_level=idea.priority_level,
        idea_score=idea.idea_score,
        created_at=idea.created_at,
    )


# ===================================================================
# 7b. GET /ci/content-ideas
# ===================================================================

@router.get("/content-ideas", response_model=ContentIdeaListResponse)
async def list_content_ideas(
    status: str | None = Query(None),
    content_format: str | None = Query(None),
    priority_level: str | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
):
    """Query content ideas with filters (CI-MKT-01)."""
    base = select(ContentIdea).where(ContentIdea.deleted_at.is_(None))
    count_base = select(func.count()).select_from(ContentIdea).where(ContentIdea.deleted_at.is_(None))

    if status:
        base = base.where(ContentIdea.status == status)
        count_base = count_base.where(ContentIdea.status == status)
    if content_format:
        base = base.where(ContentIdea.content_format == content_format)
        count_base = count_base.where(ContentIdea.content_format == content_format)
    if priority_level:
        base = base.where(ContentIdea.priority_level == priority_level)
        count_base = count_base.where(ContentIdea.priority_level == priority_level)

    total = (await session.execute(count_base)).scalar_one()

    stmt = base.order_by(ContentIdea.created_at.desc()).offset((page - 1) * limit).limit(limit)
    result = await session.execute(stmt)
    ideas = result.scalars().all()

    return ContentIdeaListResponse(
        data=[
            ContentIdeaSummary(
                content_id=ci.id,
                insight_id=ci.insight_id,
                call_id=ci.call_id,
                content_format=ci.content_format,
                content_premise=ci.content_premise,
                status=ci.status,
                priority_level=ci.priority_level,
                idea_score=ci.idea_score,
                created_at=ci.created_at,
            )
            for ci in ideas
        ],
        pagination=_pagination(page, limit, total),
    )


# ===================================================================
# 8. PUT /ci/content-ideas/:content_id
# ===================================================================

@router.put("/content-ideas/{content_id}", response_model=UpdateContentIdeaResponse)
async def update_content_idea(
    content_id: str,
    body: UpdateContentIdeaRequest,
    session: AsyncSession = Depends(get_session),
):
    """Update content idea status (CI-MKT-01).

    EC-08: Status transitions are validated against CONTENT_IDEA_VALID_TRANSITIONS.
    Invalid transitions return 422 with a descriptive error.
    """
    content_repo = ContentIdeaRepository(session)
    idea = await content_repo.get(content_id)
    if idea is None:
        raise HTTPException(status_code=404, detail={
            "error": {
                "code": "NOT_FOUND",
                "message": "Content idea not found",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        })

    # EC-08: Validate the status transition
    current_status = idea.status or "new"
    allowed = CONTENT_IDEA_VALID_TRANSITIONS.get(current_status)
    if allowed is not None and body.status not in allowed:
        raise HTTPException(
            status_code=422,
            detail={
                "error": {
                    "code": "INVALID_TRANSITION",
                    "message": (
                        f"Cannot transition content idea from '{current_status}' "
                        f"to '{body.status}'. Allowed transitions: {allowed}"
                    ),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            },
        )

    idea.status = body.status
    session.add(idea)
    await session.flush()
    await session.refresh(idea)

    return UpdateContentIdeaResponse(
        content_id=idea.id,
        status=idea.status,
        updated_at=idea.created_at,
    )


# ===================================================================
# 9. GET /ci/market-signals
# ===================================================================

@router.get("/market-signals", response_model=MarketSignalListResponse)
async def list_market_signals(
    insight_type: str | None = Query(None),
    signal_family: str | None = Query(None),
    sort_by: str = Query("total_mentions"),
    limit: int = Query(50, ge=1, le=500),
    session: AsyncSession = Depends(get_session),
):
    """Get aggregated market signals (CI-MKT-01)."""
    stmt = select(MarketSignal)

    if insight_type:
        stmt = stmt.where(MarketSignal.insight_type == insight_type)
    if signal_family:
        stmt = stmt.where(MarketSignal.signal_family == signal_family)

    sort_col = {
        "total_mentions": MarketSignal.total_mentions,
        "last_30_days": MarketSignal.last_30_days,
        "last_7_days": MarketSignal.last_7_days,
    }.get(sort_by, MarketSignal.total_mentions)

    stmt = stmt.order_by(sort_col.desc()).limit(limit)
    result = await session.execute(stmt)
    signals = result.scalars().all()

    return MarketSignalListResponse(
        data=[
            MarketSignalItem(
                signal_family=s.signal_family,
                signal=s.signal,
                insight_type=s.insight_type,
                total_mentions=s.total_mentions,
                last_30_days=s.last_30_days,
                last_7_days=s.last_7_days,
                example_quote=s.example_quote,
                best_marketing_angle=s.best_marketing_angle,
            )
            for s in signals
        ]
    )


# ===================================================================
# 10. GET /ci/tags
# ===================================================================

@router.get("/tags", response_model=TagListResponse)
async def list_tags(
    session: AsyncSession = Depends(get_session),
):
    """List tag dictionary (CI-MKT-01)."""
    stmt = select(TagDictionary).order_by(TagDictionary.tag)
    result = await session.execute(stmt)
    tags = result.scalars().all()

    return TagListResponse(
        data=[
            TagItem(
                tag=t.tag,
                tag_type=t.tag_type,
                synonyms=t.synonyms.split(",") if t.synonyms else None,
                notes=t.notes,
            )
            for t in tags
        ]
    )


# ===================================================================
# 11. GET /ci/offers
# ===================================================================

@router.get("/offers", response_model=OfferListResponse)
async def list_offers(
    status: str | None = Query(None),
    offer_type: str | None = Query(None),
    session: AsyncSession = Depends(get_session),
):
    """List CI offers catalog (CI-MKT-01)."""
    stmt = select(Offer)

    if status:
        stmt = stmt.where(Offer.status == status)
    if offer_type:
        stmt = stmt.where(Offer.offer_type == offer_type)

    stmt = stmt.order_by(Offer.name)
    result = await session.execute(stmt)
    offers = result.scalars().all()

    return OfferListResponse(
        data=[
            OfferItem(
                offer_id=o.offer_id,
                name=o.name,
                offer_type=o.offer_type,
                status=o.status,
                description=o.description,
                created_at=o.created_at,
            )
            for o in offers
        ]
    )


# ===================================================================
# 12. GET /ci/monthly-preferences/:year/:month
# ===================================================================

@router.get("/monthly-preferences/{year}/{month}", response_model=MonthlyPreferenceResponse)
async def get_monthly_preferences(
    year: int,
    month: int,
    session: AsyncSession = Depends(get_session),
):
    """Get calendar configuration for a specific month (CI-MKT-01)."""
    mp_repo = MonthlyPreferenceRepository(session)
    pref = await mp_repo.find_by_month_year(month, year)
    if pref is None:
        raise HTTPException(status_code=404, detail={
            "error": {
                "code": "NOT_FOUND",
                "message": f"No preferences set for {_month_name(month)} {year}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        })

    return MonthlyPreferenceResponse(
        month=pref.month,
        year=pref.year,
        sending_days=pref.sending_days,
        emails_per_week=pref.emails_per_week,
        email_types=pref.email_types,
        primary_goal=pref.primary_goal,
        secondary_goal=pref.secondary_goal,
        active_offers=pref.active_offers,
    )


# ===================================================================
# 13. PUT /ci/monthly-preferences/:year/:month
# ===================================================================

@router.put("/monthly-preferences/{year}/{month}", response_model=MonthlyPreferenceResponse)
async def update_monthly_preferences(
    year: int,
    month: int,
    body: UpdateMonthlyPreferencesRequest,
    session: AsyncSession = Depends(get_session),
):
    """Create or update monthly calendar preferences (CI-MKT-01)."""
    mp_repo = MonthlyPreferenceRepository(session)
    pref = await mp_repo.find_by_month_year(month, year)

    if pref is None:
        pref = MonthlyPreference(
            month=month,
            year=year,
            sending_days=body.sending_days,
            emails_per_week=body.emails_per_week,
            email_types=body.email_types,
            primary_goal=body.primary_goal,
            secondary_goal=body.secondary_goal,
            active_offers=body.active_offers,
        )
        session.add(pref)
    else:
        pref.sending_days = body.sending_days
        pref.emails_per_week = body.emails_per_week
        pref.email_types = body.email_types
        pref.primary_goal = body.primary_goal
        pref.secondary_goal = body.secondary_goal
        pref.active_offers = body.active_offers
        session.add(pref)

    await session.flush()
    await session.refresh(pref)

    return MonthlyPreferenceResponse(
        month=pref.month,
        year=pref.year,
        sending_days=pref.sending_days,
        emails_per_week=pref.emails_per_week,
        email_types=pref.email_types,
        primary_goal=pref.primary_goal,
        secondary_goal=pref.secondary_goal,
        active_offers=pref.active_offers,
    )


# ===================================================================
# DATA SYNC BRIDGES
# ===================================================================

# CI-MKT-02: Sync CI insights -> shared intelligence tables
# CI-MKT-03: Sync CI content_ideas -> content_ideas table

@router.post("/sync/insights", response_model=SyncResult, tags=["CI Data Sync"])
async def sync_insights_to_shared_intelligence(
    session: AsyncSession = Depends(get_session),
):
    """CI-MKT-02: Sync CI insights to Central Intelligence shared intelligence tables.

    Maps insight_type to the appropriate shared intelligence table:
    - Pain / False Belief -> pain_points
    - Win / Breakthrough  -> wins
    - Objection           -> objections
    - Goal                -> goals
    """
    pain_repo = PainPointRepository(session)
    win_repo = WinRepository(session)
    obj_repo = ObjectionRepository(session)
    goal_repo = GoalRepository(session)

    # Fetch all insights that haven't been synced yet.
    # We use a convention: insights with a non-null `best_use_case` field
    # that haven't been mapped to shared tables yet. For robustness we
    # query all insights and check by type.
    stmt = select(Insight).order_by(Insight.created_at.desc()).limit(500)
    result = await session.execute(stmt)
    insights = result.scalars().all()

    synced = 0
    skipped = 0
    errors: list[str] = []

    _PAIN_TYPES = {"Pain", "False Belief"}
    _WIN_TYPES = {"Win", "Breakthrough"}
    _OBJ_TYPES = {"Objection"}
    _GOAL_TYPES = {"Goal"}

    for ins in insights:
        try:
            itype = ins.insight_type or ""

            if itype in _PAIN_TYPES:
                text = ins.what_they_say or ins.raw_quote or ins.signal
                if not text:
                    skipped += 1
                    continue
                # Check for duplicate by text match
                existing = await session.execute(
                    select(func.count()).select_from(PainPoint)
                    .where(PainPoint.deleted_at.is_(None))
                    .where(PainPoint.text == text)
                )
                if existing.scalar_one() > 0:
                    # Increment frequency on existing
                    upd_stmt = select(PainPoint).where(
                        PainPoint.deleted_at.is_(None),
                        PainPoint.text == text,
                    ).limit(1)
                    upd_result = await session.execute(upd_stmt)
                    pp = upd_result.scalar_one_or_none()
                    if pp:
                        pp.frequency_count = (pp.frequency_count or 0) + 1
                        session.add(pp)
                    skipped += 1
                    continue
                await pain_repo.create(
                    text=text,
                    category=ins.signal_family,
                )
                synced += 1

            elif itype in _WIN_TYPES:
                text = ins.what_they_say or ins.raw_quote or ins.signal
                if not text:
                    skipped += 1
                    continue
                existing = await session.execute(
                    select(func.count()).select_from(Win)
                    .where(Win.deleted_at.is_(None))
                    .where(Win.win_text == text)
                )
                if existing.scalar_one() > 0:
                    skipped += 1
                    continue
                await win_repo.create(
                    win_text=text,
                    impact_area=ins.signal_family,
                    win_date=ins.created_at,
                )
                synced += 1

            elif itype in _OBJ_TYPES:
                text = ins.what_they_say or ins.raw_quote or ins.signal
                if not text:
                    skipped += 1
                    continue
                existing = await session.execute(
                    select(func.count()).select_from(Objection)
                    .where(Objection.deleted_at.is_(None))
                    .where(Objection.objection_text == text)
                )
                if existing.scalar_one() > 0:
                    skipped += 1
                    continue
                await obj_repo.create(
                    objection_text=text,
                    context=ins.the_real_problem,
                    resolution_offered=ins.marketing_translation,
                )
                synced += 1

            elif itype in _GOAL_TYPES:
                text = ins.what_they_say or ins.raw_quote or ins.signal
                if not text:
                    skipped += 1
                    continue
                existing = await session.execute(
                    select(func.count()).select_from(Goal)
                    .where(Goal.deleted_at.is_(None))
                    .where(Goal.goal_text == text)
                )
                if existing.scalar_one() > 0:
                    skipped += 1
                    continue
                await goal_repo.create(goal_text=text)
                synced += 1

            else:
                skipped += 1

        except Exception as exc:
            errors.append(f"Insight {ins.id}: {exc}")
            logger.warning("Sync error for insight %s: %s", ins.id, exc)

    await session.flush()

    logger.info(
        "CI-MKT-02 sync complete: synced=%d skipped=%d errors=%d",
        synced, skipped, len(errors),
    )

    return SyncResult(synced_count=synced, skipped_count=skipped, errors=errors)


@router.post("/sync/content-ideas", response_model=SyncResult, tags=["CI Data Sync"])
async def sync_content_ideas(
    session: AsyncSession = Depends(get_session),
):
    """CI-MKT-03: Sync CI content_ideas to Central Intelligence content_ideas table.

    This bridge ensures content ideas generated by the CI pipeline are
    available in the shared Central Intelligence content_ideas table. Since both
    systems share the same table via the repository pattern, this endpoint
    validates data integrity and fills any missing fields.
    """
    stmt = (
        select(ContentIdea)
        .where(ContentIdea.deleted_at.is_(None))
        .order_by(ContentIdea.created_at.desc())
        .limit(500)
    )
    result = await session.execute(stmt)
    ideas = result.scalars().all()

    synced = 0
    skipped = 0
    errors: list[str] = []

    for ci in ideas:
        try:
            # Validate required fields; fill defaults for incomplete records
            if not ci.content_angle and not ci.content_premise:
                skipped += 1
                continue

            if ci.source is None:
                ci.source = "ci_pipeline"
                session.add(ci)
                synced += 1
            elif ci.source == "ci_pipeline":
                skipped += 1
            else:
                skipped += 1

        except Exception as exc:
            errors.append(f"ContentIdea {ci.id}: {exc}")
            logger.warning("Sync error for content idea %s: %s", ci.id, exc)

    await session.flush()

    logger.info(
        "CI-MKT-03 sync complete: synced=%d skipped=%d errors=%d",
        synced, skipped, len(errors),
    )

    return SyncResult(synced_count=synced, skipped_count=skipped, errors=errors)


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _month_name(month: int) -> str:
    import calendar
    return calendar.month_name[month] if 1 <= month <= 12 else str(month)
