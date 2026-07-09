"""Central Intelligence (CI) webhook endpoints.

Implements 13 REST endpoints for the CI subsystem plus two data sync bridges:
- CI-MKT-01: 13 FastAPI webhook endpoints for CI data
- CI-MKT-02: Data sync bridge — CI insights -> shared intelligence tables
- CI-MKT-03: Data sync bridge — CI content_ideas -> content_ideas table
"""

import logging
import math
from datetime import datetime, timedelta, timezone
from uuid import UUID
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse, Response
from sqlalchemy import asc, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.team import RepRow, resolve_rep
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
    Lead,
    Objection,
    PainPoint,
    Win,
)
from app.models.sales import SalesRep
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
    CallAnalytics,
    CallFacets,
    CallListResponse,
    CallStats,
    CallSummary,
    LabeledCount,
    TimeBucket,
    ContentIdeaBrief,
    ContentIdeaDetail,
    ContentIdeaListResponse,
    ContentIdeaSummary,
    CreateCallFromTranscriptRequest,
    CreateCallFromTranscriptResponse,
    CreateContentIdeaRequest,
    InsightBrief,
    InsightDetail,
    InsightDetailResponse,
    InsightCount,
    InsightDistribution,
    InsightFacets,
    InsightListResponse,
    InsightSummary,
    InsightTopSignal,
    MarketSignalFacets,
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

# Columns the calls table may sort by — whitelisted to prevent injection and to
# keep the UI and API in lock-step. Maps the UI's sort key → Call column.
_CALL_SORTABLE = {
    "date": Call.date,
    "created_at": Call.created_at,  # "Date Added" — when CI ingested the row
    "call_type": Call.call_type,
    "call_result": Call.call_result,
    "call_owner": Call.call_owner,
    "source": Call.source,
}

# Insight types that count as "pain points" (drives the Pain Points KPI + badge).
_PAIN_TYPES = ("Pain", "Objection", "Belief")

# Max chars for the one-line transcript excerpt shown on the call card.
_EXCERPT_LEN = 240


def _excerpt(transcript: str | None) -> str | None:
    """First ~240 chars of the transcript, single-spaced, for the card preview."""
    if not transcript:
        return None
    text_ = " ".join(transcript.split())
    return text_[:_EXCERPT_LEN] + ("…" if len(text_) > _EXCERPT_LEN else "")


def call_owner_match_values(rep: RepRow) -> list[str]:
    """Every raw ``call_owner`` string variant that should resolve to ``rep``.

    Combines ``full_name`` with each comma-split ``historical_aliases`` entry
    (title-cased back to a plausible display form, since aliases are stored
    lowercase) so a SQL ``call_owner IN (...)`` (case-insensitive) filter can
    match the messy variants WGR actually wrote ('Colton', 'Colton  Lindsay').
    Pure — no DB access — so it's unit-testable against fixed rep rows.
    """
    values = {rep.full_name.strip().lower()}
    if rep.historical_aliases:
        for alias in rep.historical_aliases.split(","):
            a = alias.strip().lower()
            if a:
                values.add(a)
    return sorted(values)


def resolve_call_owner(call_owner: str | None, roster: list[RepRow]) -> RepRow | None:
    """Resolve a raw ``calls.call_owner`` display string against the roster.

    Thin wrapper over ``resolve_rep`` — same match semantics (exact rep_id,
    case-insensitive full_name, then historical_aliases containment) — kept as
    a distinct name at the call site since the input here is always the messy
    WGR ``call_owner`` string, never a user-typed rep query.
    """
    return resolve_rep(call_owner, roster) if call_owner else None


@router.get("/calls/stats", response_model=CallStats)
async def call_stats(session: AsyncSession = Depends(get_session)):
    """KPI tiles for the Sales Calls page: totals + this-month + pain points + ideas."""
    total = (await session.execute(
        select(func.count()).select_from(Call).where(Call.deleted_at.is_(None))
    )).scalar_one()

    # This month / last month on call date, for the count + delta. Boundaries
    # computed in Python (UTC) so we don't depend on a SQL interval expression.
    now = datetime.now(tz=timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    last_month_start = (month_start - timedelta(days=1)).replace(day=1)
    this_month = (await session.execute(
        select(func.count()).select_from(Call)
        .where(Call.deleted_at.is_(None), Call.date >= month_start)
    )).scalar_one()
    last_month = (await session.execute(
        select(func.count()).select_from(Call)
        .where(
            Call.deleted_at.is_(None),
            Call.date >= last_month_start,
            Call.date < month_start,
        )
    )).scalar_one()

    pain = (await session.execute(
        select(func.count()).select_from(Insight)
        .where(Insight.insight_type.in_(_PAIN_TYPES))
    )).scalar_one()

    ideas = (await session.execute(
        select(func.count()).select_from(ContentIdea)
    )).scalar_one()

    return CallStats(
        total_calls=total,
        calls_this_month=this_month,
        pain_points_found=pain,
        content_ideas=ideas,
        this_month_delta=this_month - last_month,
    )


@router.get("/calls/analytics", response_model=CallAnalytics)
async def call_analytics(session: AsyncSession = Depends(get_session)):
    """Aggregates for the Sales Calls Analytics page: calls/month trend, result
    breakdown, top pain-point signals, and most active call owners."""
    # Calls per month, last 6 months (incl. current), in chronological order.
    now = datetime.now(tz=timezone.utc)
    months: list[datetime] = []
    cursor = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    for _ in range(6):
        months.append(cursor)
        cursor = (cursor - timedelta(days=1)).replace(day=1)
    months.reverse()  # oldest → newest

    calls_by_month: list[TimeBucket] = []
    for i, m_start in enumerate(months):
        m_end = months[i + 1] if i + 1 < len(months) else None
        clause = [Call.deleted_at.is_(None), Call.date >= m_start]
        if m_end is not None:
            clause.append(Call.date < m_end)
        cnt = (await session.execute(
            select(func.count()).select_from(Call).where(*clause)
        )).scalar_one()
        calls_by_month.append(TimeBucket(label=m_start.strftime("%b"), value=cnt))

    # Result breakdown (call_result distribution).
    result_rows = (await session.execute(
        select(Call.call_result, func.count())
        .where(Call.deleted_at.is_(None), Call.call_result.is_not(None))
        .group_by(Call.call_result)
        .order_by(func.count().desc())
    )).all()
    result_breakdown = [LabeledCount(label=r or "—", count=c) for r, c in result_rows]

    # Top pain-point signals (the actual signal text on pain-type insights).
    pain_rows = (await session.execute(
        select(Insight.signal, func.count())
        .where(Insight.insight_type.in_(_PAIN_TYPES), Insight.signal.is_not(None))
        .group_by(Insight.signal)
        .order_by(func.count().desc())
        .limit(10)
    )).all()
    top_pain_points = [LabeledCount(label=s, count=c) for s, c in pain_rows]

    # Most active call owners.
    owner_rows = (await session.execute(
        select(Call.call_owner, func.count())
        .where(Call.deleted_at.is_(None), Call.call_owner.is_not(None))
        .group_by(Call.call_owner)
        .order_by(func.count().desc())
        .limit(8)
    )).all()
    top_call_owners = [LabeledCount(label=o, count=c) for o, c in owner_rows]

    return CallAnalytics(
        calls_by_month=calls_by_month,
        result_breakdown=result_breakdown,
        top_pain_points=top_pain_points,
        top_call_owners=top_call_owners,
    )


@router.get("/calls", response_model=CallListResponse)
async def list_calls(
    call_type: str | None = Query(
        None,
        description="Filter by call_type. Accepts a single value or a comma-separated "
        "list (e.g. 'Sales,Discovery'); matches any of the given types.",
    ),
    call_result: str | None = Query(
        None,
        description="Filter by call_result. Accepts a single value or a comma-separated "
        "list (e.g. 'Booked,Pending'); matches any of the given results.",
    ),
    call_owner: str | None = Query(None, description="Filter by exact call_owner."),
    source: str | None = Query(None, description="Filter by provenance ('wgr' / 'ci_upload')."),
    search: str | None = Query(
        None,
        description="Case-insensitive match on call_id, rep (call_owner), or the "
        "linked lead's name/email.",
    ),
    date_from: str | None = Query(None, description="Call date >= (ISO)."),
    date_to: str | None = Query(None, description="Call date <= (ISO)."),
    start: str | None = Query(None, description="Call date >= (ISO date/datetime)."),
    end: str | None = Query(None, description="Call date <= (ISO date/datetime)."),
    rep: str | None = Query(
        None,
        description="Filter by rep_id. Matches calls whose call_owner resolves "
        "(via the sales_reps roster + historical_aliases) to this rep.",
    ),
    sort_by: str = Query("date", description="Sort column (see _CALL_SORTABLE)."),
    sort_dir: Literal["asc", "desc"] = Query("desc", description="Sort direction."),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
):
    """List processed calls with filters + sort (CI-MKT-01)."""
    stmt = select(Call)
    count_stmt = select(func.count()).select_from(Call)

    def _both(clause):
        nonlocal stmt, count_stmt
        stmt = stmt.where(clause)
        count_stmt = count_stmt.where(clause)

    # Full roster fetched once — used both for the optional `rep` filter and to
    # resolve each returned row's call_owner → rep_id/rep_name (avoids N+1).
    roster_rows = (await session.execute(
        select(SalesRep.rep_id, SalesRep.full_name, SalesRep.role, SalesRep.status,
               SalesRep.historical_aliases)
    )).all()
    roster = [
        RepRow(rep_id=r[0], full_name=r[1], role=r[2], status=r[3], historical_aliases=r[4])
        for r in roster_rows
    ]

    if call_type:
        types = [t.strip() for t in call_type.split(",") if t.strip()]
        if types:
            _both(Call.call_type.in_(types))
    if call_result:
        # Accept a single value or a comma-separated list (multi-select on the
        # Sales Calls page) — matches any of the given results.
        results = [r.strip() for r in call_result.split(",") if r.strip()]
        if len(results) == 1:
            _both(Call.call_result == results[0])
        elif results:
            _both(Call.call_result.in_(results))
    if call_owner:
        _both(Call.call_owner == call_owner)
    if source:
        _both(Call.source == source)
    if search:
        like = f"%{search.strip()}%"
        # Match the call id, the rep (call_owner), OR the linked lead (the
        # prospect) by name/email — the card leads with the prospect, so people
        # search by who they talked to. Lead match via a subquery on lead ids.
        lead_match = select(Lead.id).where(
            or_(Lead.name.ilike(like), Lead.email.ilike(like))
        )
        _both(or_(
            Call.id.ilike(like),
            Call.call_owner.ilike(like),
            Call.lead_id.in_(lead_match),
        ))
    if date_from:
        _both(Call.date >= datetime.fromisoformat(date_from))
    if date_to:
        _both(Call.date <= datetime.fromisoformat(date_to))
    if start:
        _both(Call.date >= datetime.fromisoformat(start))
    if end:
        # Bare 'YYYY-MM-DD' (native <input type="date">) needs its end boundary
        # pushed to the end of that day, else "end=2026-06-30" excludes every
        # call that happened during the 30th (midnight-only comparison).
        end_dt = datetime.fromisoformat(end)
        if len(end) <= 10:
            end_dt = end_dt.replace(hour=23, minute=59, second=59, microsecond=999999)
        _both(Call.date <= end_dt)
    if rep:
        rep_row = next((r for r in roster if r.rep_id == rep), None)
        if rep_row is None:
            # Unknown rep_id — no calls can match; short-circuit to an empty
            # page rather than erroring (mirrors the appointments rep filter,
            # which is similarly permissive of an unresolvable rep_id).
            _both(Call.id.is_(None))
        else:
            match_values = call_owner_match_values(rep_row)
            _both(func.lower(func.trim(Call.call_owner)).in_(match_values))

    total = (await session.execute(count_stmt)).scalar_one()

    # Resolve sort to a whitelisted column; fall back to date desc.
    sort_col = _CALL_SORTABLE.get(sort_by, Call.date)
    direction = asc if sort_dir == "asc" else desc
    # Stable tiebreaker on id so equal-keyed rows paginate deterministically.
    stmt = (
        stmt.order_by(direction(sort_col).nullslast(), Call.id.asc())
        .offset((page - 1) * limit)
        .limit(limit)
    )
    result = await session.execute(stmt)
    calls = result.scalars().all()

    # Batch the per-call counts for just this page's call ids (avoids N+1).
    call_ids = [c.id for c in calls]
    insight_counts: dict[str, int] = {}
    pain_counts: dict[str, int] = {}
    idea_counts: dict[str, int] = {}
    if call_ids:
        rows = (await session.execute(
            select(
                Insight.call_id,
                func.count().label("total"),
                func.count().filter(Insight.insight_type.in_(_PAIN_TYPES)).label("pain"),
            )
            .where(Insight.call_id.in_(call_ids))
            .group_by(Insight.call_id)
        )).all()
        # NOTE: loop var deliberately not named `total` — it previously shadowed
        # the outer pagination `total` (the count_stmt result), so any response
        # page with at least one call silently corrupted `pagination.total` to
        # the last row's per-call insight count instead of the true match count.
        for cid, insight_total, pain in rows:
            insight_counts[cid] = insight_total
            pain_counts[cid] = pain
        idea_rows = (await session.execute(
            select(ContentIdea.call_id, func.count())
            .where(ContentIdea.call_id.in_(call_ids))
            .group_by(ContentIdea.call_id)
        )).all()
        idea_counts = {cid: n for cid, n in idea_rows}

    # Resolve the lead (prospect) name per call in one query — the card shows
    # the LEAD as its primary identity, not the call_owner (the rep).
    lead_uuids = {c.lead_id for c in calls if c.lead_id is not None}
    lead_names: dict = {}
    if lead_uuids:
        lead_rows = (await session.execute(
            select(Lead.id, Lead.name).where(Lead.id.in_(lead_uuids))
        )).all()
        lead_names = {lid: name for lid, name in lead_rows}

    data = []
    for c in calls:
        resolved = resolve_call_owner(c.call_owner, roster)
        data.append(CallSummary(
            call_id=c.id,
            date=c.date,
            call_type=c.call_type,
            call_result=c.call_result,
            call_owner=c.call_owner,
            rep_id=resolved.rep_id if resolved else None,
            rep_name=resolved.full_name if resolved else None,
            lead_id=str(c.lead_id) if c.lead_id is not None else None,
            lead_name=lead_names.get(c.lead_id),
            transcript_quality=c.transcript_quality,
            processed_date=c.processed_date,
            insights_count=insight_counts.get(c.id, 0),
            pain_points_count=pain_counts.get(c.id, 0),
            content_ideas_count=idea_counts.get(c.id, 0),
            duration_minutes=c.call_duration_minutes,
            transcript_excerpt=_excerpt(c.transcript_text),
            source=c.source,
            created_at=c.created_at,
        ))

    return CallListResponse(data=data, pagination=_pagination(page, limit, total))


# ===================================================================
# 3b. GET /ci/calls/facets
# ===================================================================
# NOTE: declared before /calls/{call_id} so the literal "facets" path
# isn't swallowed by the dynamic call_id route.

@router.get("/calls/facets", response_model=CallFacets)
async def call_facets(
    session: AsyncSession = Depends(get_session),
):
    """Distinct filterable values present in the calls table.

    Drives the calls-table filter dropdowns so the options can never drift
    from the WGR sync / CI upload taxonomy. NULLs and blanks are excluded;
    values are returned sorted. (`source` is a fixed provenance set —
    'wgr' / 'ci_upload' — so it is not derived here.)
    """

    async def _distinct(column) -> list[str]:
        stmt = (
            select(column)
            .where(column.is_not(None))
            .where(func.trim(column) != "")
            .distinct()
            .order_by(column.asc())
        )
        rows = (await session.execute(stmt)).scalars().all()
        return [r for r in rows if r and r.strip()]

    return CallFacets(
        call_type=await _distinct(Call.call_type),
        call_result=await _distinct(Call.call_result),
    )


# ===================================================================
# 4. GET /ci/calls/:call_id
# ===================================================================

def _insight_detail(i: Insight) -> InsightDetail:
    """Build the full InsightDetail payload from an Insight ORM row.

    Shared by GET /ci/calls/{id} (embedded list) and GET /ci/insights/{id}
    so both surface the complete analysis, not a truncated brief.
    """
    return InsightDetail(
        insight_id=i.id,
        call_id=i.call_id,
        speaker_name=i.speaker_name,
        insight_type=i.insight_type,
        signal_family=i.signal_family,
        signal=i.signal,
        signal_strength=i.signal_strength,
        pain_layer=i.pain_layer,
        raw_quote=i.raw_quote,
        what_they_say=i.what_they_say,
        the_real_problem=i.the_real_problem,
        emotional_driver=i.emotional_driver,
        core_fear_revealed=i.core_fear_revealed,
        false_belief_revealed=i.false_belief_revealed,
        structural_obstacle=i.structural_obstacle,
        identity_signal=i.identity_signal,
        buying_trigger=i.buying_trigger,
        objection_created=i.objection_created,
        marketing_translation=i.marketing_translation,
        hook_angle_example=i.hook_angle_example,
        best_use_case=i.best_use_case,
        quote_confidence=i.quote_confidence,
        frequency_score=i.frequency_score,
        created_at=i.created_at,
    )


def _content_idea_detail(ci: ContentIdea) -> ContentIdeaDetail:
    """Build the full ContentIdeaDetail payload from a ContentIdea ORM row."""
    return ContentIdeaDetail(
        content_id=ci.id,
        insight_id=ci.insight_id,
        call_id=ci.call_id,
        source=ci.source,
        market_audience=ci.market_audience,
        content_format=ci.content_format,
        content_angle=ci.content_angle,
        trigger_insight=ci.trigger_insight,
        raw_quote=ci.raw_quote,
        content_premise=ci.content_premise,
        hook_opening_line=ci.hook_opening_line,
        teaching_point=ci.teaching_point,
        cta_idea=ci.cta_idea,
        priority_level=ci.priority_level,
        best_platform=ci.best_platform,
        repurpose_opportunities=ci.repurpose_opportunities,
        idea_score=ci.idea_score,
        status=ci.status,
        created_at=ci.created_at,
    )


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
            source=call.source,
        ),
        insights=[_insight_detail(i) for i in insights],
        content_ideas=[_content_idea_detail(ci) for ci in content_ideas],
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
        source="ci_upload",  # provenance: analyzed in CI (vs 'wgr' mirror)
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

    # lead_id is a UUID FK — handle it specially (the rest are plain str cols).
    # "" / null clears the link; a valid UUID that exists links the call; an
    # unknown lead 404s so the UI can't silently point a call at nothing.
    if "lead_id" in updates:
        raw_lead = updates.pop("lead_id")
        if not raw_lead:
            call.lead_id = None
        else:
            try:
                lead_uuid = UUID(raw_lead)
            except (ValueError, TypeError):
                raise HTTPException(status_code=422, detail="Invalid lead_id")
            exists = (await session.execute(
                select(Lead.id).where(Lead.id == lead_uuid, Lead.deleted_at.is_(None))
            )).first()
            if exists is None:
                raise HTTPException(status_code=404, detail="Lead not found")
            call.lead_id = lead_uuid

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
        source=call.source,
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
# 5b. GET /ci/insights/facets
# ===================================================================
# NOTE: declared before /insights/{insight_id} so the literal "facets"
# path isn't swallowed by the dynamic insight_id route.

@router.get("/insights/facets", response_model=InsightFacets)
async def insight_facets(
    session: AsyncSession = Depends(get_session),
):
    """Distinct filterable values present in the insights table.

    Drives the insights-page filter dropdowns so the options can never
    drift from the analyzer/WGR taxonomy. NULLs and blanks are excluded;
    values are returned sorted.
    """

    async def _distinct(column) -> list[str]:
        stmt = (
            select(column)
            .where(column.is_not(None))
            .where(func.trim(column) != "")
            .distinct()
            .order_by(column.asc())
        )
        rows = (await session.execute(stmt)).scalars().all()
        return [r for r in rows if r and r.strip()]

    return InsightFacets(
        insight_type=await _distinct(Insight.insight_type),
        signal_family=await _distinct(Insight.signal_family),
        signal_strength=await _distinct(Insight.signal_strength),
    )


# ===================================================================
# 5c. GET /ci/insights/summary
# ===================================================================
# NOTE: declared before /insights/{insight_id} so the literal "summary"
# path isn't swallowed by the dynamic insight_id route.

@router.get("/insights/summary", response_model=InsightDistribution)
async def insight_summary(
    insight_type: str | None = Query(None),
    signal_family: str | None = Query(None),
    signal_strength: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    session: AsyncSession = Depends(get_session),
):
    """Pre-aggregated distributions for the CI Insights charts (CI-MKT-01).

    Aggregation runs in the database over the whole table (after applying the
    same filters the list endpoint accepts), so the charts reflect the full
    dataset rather than a single page. Each distribution carries both a raw
    row ``count`` and a ``mentions`` sum (frequency_score); NULL/blank group
    keys are excluded so they never render as an empty chart slice.
    """

    # Build the shared filter predicate once and apply it to every query so
    # the charts stay consistent with each other and with the list view.
    filters = []
    if insight_type:
        filters.append(Insight.insight_type == insight_type)
    if signal_family:
        filters.append(Insight.signal_family == signal_family)
    if signal_strength:
        filters.append(Insight.signal_strength == signal_strength)
    if date_from:
        filters.append(Insight.created_at >= datetime.fromisoformat(date_from))
    if date_to:
        filters.append(Insight.created_at <= datetime.fromisoformat(date_to))

    def _apply(stmt):
        for f in filters:
            stmt = stmt.where(f)
        return stmt

    total = (
        await session.execute(_apply(select(func.count()).select_from(Insight)))
    ).scalar_one()

    async def _distribution(column) -> list[InsightCount]:
        """Group by ``column``, summing mentions and counting rows.

        Excludes NULL and whitespace-only keys; sorted by mentions desc so the
        biggest bucket leads the chart.
        """
        stmt = (
            select(
                column.label("label"),
                func.count().label("count"),
                func.coalesce(func.sum(Insight.frequency_score), 0).label("mentions"),
            )
            .where(column.is_not(None))
            .where(func.trim(column) != "")
            .group_by(column)
            .order_by(func.coalesce(func.sum(Insight.frequency_score), 0).desc())
        )
        rows = (await session.execute(_apply(stmt))).all()
        return [
            InsightCount(label=r.label, count=r.count, mentions=r.mentions)
            for r in rows
        ]

    # Top signals by total mentions — the headline "what comes up most" chart.
    top_stmt = (
        select(
            Insight.signal.label("signal"),
            Insight.signal_family.label("signal_family"),
            Insight.insight_type.label("insight_type"),
            func.coalesce(func.sum(Insight.frequency_score), 0).label("mentions"),
        )
        .where(Insight.signal.is_not(None))
        .where(func.trim(Insight.signal) != "")
        .group_by(Insight.signal, Insight.signal_family, Insight.insight_type)
        .order_by(func.coalesce(func.sum(Insight.frequency_score), 0).desc())
        .limit(10)
    )
    top_rows = (await session.execute(_apply(top_stmt))).all()

    return InsightDistribution(
        total=total,
        by_insight_type=await _distribution(Insight.insight_type),
        by_signal_family=await _distribution(Insight.signal_family),
        by_signal_strength=await _distribution(Insight.signal_strength),
        top_signals=[
            InsightTopSignal(
                signal=r.signal,
                signal_family=r.signal_family,
                insight_type=r.insight_type,
                mentions=r.mentions,
            )
            for r in top_rows
        ],
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
        insight=_insight_detail(insight),
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
# 9a. GET /ci/market-signals/facets
# ===================================================================

@router.get("/market-signals/facets", response_model=MarketSignalFacets)
async def market_signal_facets(
    session: AsyncSession = Depends(get_session),
):
    """Distinct filterable values present in the market_signals table.

    Drives the market-signals page filter dropdowns so the options can
    never drift from the aggregated data. NULLs and blanks are excluded;
    values are returned sorted.
    """

    async def _distinct(column) -> list[str]:
        stmt = (
            select(column)
            .where(column.is_not(None))
            .where(func.trim(column) != "")
            .distinct()
            .order_by(column.asc())
        )
        rows = (await session.execute(stmt)).scalars().all()
        return [r for r in rows if r and r.strip()]

    return MarketSignalFacets(
        insight_type=await _distinct(MarketSignal.insight_type),
        signal_family=await _distinct(MarketSignal.signal_family),
    )


# ===================================================================
# 9b. POST /ci/market-signals/refresh — on-demand recompute
# ===================================================================


@router.post("/market-signals/refresh", status_code=202)
async def refresh_market_signals() -> dict:
    """Enqueue the market-signals recompute job (aggregates insights → market_signals).

    Mirrors the GHL on-demand sync pattern. The job also runs hourly via Celery
    beat; this lets staff force an immediate refresh. Returns the task id when the
    broker is reachable, otherwise a graceful "unavailable" status.
    """
    try:
        from app.tasks.market_signals import update_market_signals

        task = update_market_signals.delay()
        return {"task_id": task.id, "status": "queued"}
    except Exception as exc:  # noqa: BLE001 — broker/redis may be down; don't 500
        logger.warning("refresh_market_signals: enqueue failed — %s", exc)
        return {"task_id": None, "status": "unavailable"}


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
