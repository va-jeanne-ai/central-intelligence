"""
Transcription routes.

  POST /api/v1/transcribe             — sync, direct transcription (T01-2)
  POST /api/v1/transcribe/async       — enqueue Celery task (T01-5)
  GET  /api/v1/transcribe/{task_id}/status — poll Celery task status (T01-5)

Sprint 2 / CI-CORE-01 / T01-2, T01-5
"""

import hashlib
import logging
import tempfile
import uuid
from pathlib import Path
from uuid import uuid4

from celery.result import AsyncResult
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser, get_current_user
from app.database import get_session
from app.models.operational import Call
from app.schemas.transcribe import (
    TaskStatusResponse,
    TranscribeAsyncResponse,
    TranscribeRequest,
    TranscribeResponse,
)
from app.services.audit import record_event
from app.storage.transcripts import save_transcript
from app.tasks.transcriber import transcribe_video

_MAX_UPLOAD_BYTES = 500 * 1024 * 1024  # raw upload cap (local Whisper has none)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/transcribe", tags=["transcribe"])


# ---------------------------------------------------------------------------
# POST /api/v1/transcribe  —  synchronous (direct, no Celery)
# ---------------------------------------------------------------------------


@router.post("", response_model=TranscribeResponse)
async def transcribe(
    body: TranscribeRequest,
    db: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> TranscribeResponse:
    """Transcribe a video/audio URL synchronously and store the result.

    - Deduplicates by SHA-256 hash of the video URL.
    - Returns ``status="duplicate"`` if the URL was already processed.
    - Returns ``status="completed"`` with the transcript on success.
    """
    import hashlib
    video_url_hash = hashlib.sha256(body.video_url.encode()).hexdigest()

    # ------------------------------------------------------------------
    # Deduplication check
    # ------------------------------------------------------------------
    existing = await db.execute(
        select(Call).where(Call.video_url_hash == video_url_hash)
    )
    existing_call = existing.scalar_one_or_none()

    if existing_call is not None:
        logger.info(
            "Duplicate transcription request — call_id=%s url_hash=%s user_id=%s",
            existing_call.id,
            video_url_hash,
            current_user.id,
        )
        return TranscribeResponse(
            job_id=existing_call.id,
            status="duplicate",
            call_id=existing_call.id,
            message="Already transcribed",
        )

    # ------------------------------------------------------------------
    # Resolve call type (auto-route when omitted)
    # ------------------------------------------------------------------
    from app.tasks.transcriber import _route_call_type  # noqa: PLC0415

    resolved_call_type = (
        body.call_type if body.call_type else _route_call_type(body.video_url)
    )

    # ------------------------------------------------------------------
    # Transcribe via operator
    # ------------------------------------------------------------------
    try:
        from app.agents.operators.transcriber import TranscriberOperator  # lazy import (pydub optional)
        operator = TranscriberOperator()
        result = await operator.transcribe(body.video_url, resolved_call_type)
    except ValueError as exc:
        logger.warning("Transcription validation error: %s", exc)
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ConnectionError as exc:
        logger.error("Transcription connection error: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Unexpected transcription error: %s", exc)
        raise HTTPException(
            status_code=500, detail="Internal transcription error"
        ) from exc

    # ------------------------------------------------------------------
    # Persist Call record
    # ------------------------------------------------------------------
    call_id = f"CALL_{uuid4().hex[:8].upper()}"
    transcript_text = result["transcript"]

    call = Call(
        id=call_id,
        call_type=resolved_call_type,
        video_url_hash=video_url_hash,
        transcript_text=transcript_text,
        transcript_source="whisper",
        call_duration_minutes=(result.get("duration_seconds", 0) / 60.0),
        lead_id=body.lead_id if body.lead_id else None,
        member_id=body.member_id if body.member_id else None,
    )
    db.add(call)
    await db.flush()

    # Persist the transcript as a browsable .txt artifact (project file store).
    try:
        save_transcript(call_id, transcript_text)
    except Exception as exc:
        logger.warning("Failed to save transcript file — call_id=%s error=%s", call_id, exc)

    logger.info(
        "Call record created — call_id=%s call_type=%s duration=%ss user_id=%s",
        call_id,
        resolved_call_type,
        result.get("duration_seconds", 0),
        current_user.id,
    )

    return TranscribeResponse(
        job_id=call_id,
        status="completed",
        transcript=transcript_text,
        call_id=call_id,
    )


# ---------------------------------------------------------------------------
# POST /api/v1/transcribe/upload  —  multipart audio file upload
# ---------------------------------------------------------------------------


@router.post("/upload", response_model=TranscribeResponse)
async def transcribe_upload(
    file: UploadFile = File(...),
    callType: str | None = Form(default=None),
    leadId: str | None = Form(default=None),
    memberId: str | None = Form(default=None),
    db: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> TranscribeResponse:
    """Transcribe an uploaded audio/video file (m4a, mp3, mp4, etc.).

    Mirrors the sync URL path but reads bytes from the multipart body. The
    file is written to a tempfile, handed to OpenAI Whisper, then the Call
    row + .txt artifact are persisted and the analyzer is chained.
    """
    raw = await file.read()
    if len(raw) > _MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=422,
            detail=f"File exceeds 25 MB limit (got {len(raw)} bytes)",
        )
    if not raw:
        raise HTTPException(status_code=422, detail="Empty file upload")

    # Dedup on content hash so re-uploading the same recording returns the
    # existing call instead of double-paying Whisper.
    content_hash = hashlib.sha256(raw).hexdigest()
    existing = await db.execute(select(Call).where(Call.video_url_hash == content_hash))
    existing_call = existing.scalar_one_or_none()
    if existing_call is not None:
        return TranscribeResponse(
            job_id=existing_call.id,
            status="duplicate",
            call_id=existing_call.id,
            message="Already transcribed",
        )

    suffix = Path(file.filename or "audio.m4a").suffix or ".m4a"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(raw)
    tmp.close()
    tmp_path = Path(tmp.name)
    cleanup_paths: list[Path] = [tmp_path]

    try:
        from app.services.local_whisper import transcribe_file

        # Local Whisper happily reads m4a/mp4/etc. directly via ffmpeg — no
        # compression step needed (it has no 25 MB cap). Offload to a thread
        # so the async event loop isn't blocked during the CPU-bound decode.
        import anyio
        result = await anyio.to_thread.run_sync(transcribe_file, tmp_path)
        transcript_text = result["transcript"]
        duration_seconds = int(result.get("duration_seconds") or 0)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("transcribe_upload local-whisper error: %s", exc)
        raise HTTPException(status_code=502, detail=f"Transcription failure: {exc}") from exc
    finally:
        for p in cleanup_paths:
            p.unlink(missing_ok=True)

    # Validate the optional leadId form field. If the caller is logging
    # this call against a specific lead, the FK must resolve — otherwise
    # we'd silently orphan the call. Bad UUID or unknown lead → 422
    # (caller's input), not 500.
    lead_uuid: uuid.UUID | None = None
    if leadId:
        try:
            lead_uuid = uuid.UUID(leadId)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=f"Invalid leadId: {leadId!r}") from exc
        exists = (await db.execute(
            text("SELECT 1 FROM leads WHERE id = :id AND deleted_at IS NULL"),
            {"id": str(lead_uuid)},
        )).scalar_one_or_none()
        if exists is None:
            raise HTTPException(status_code=404, detail="Lead not found")

    # Same validation for the optional memberId — coaching calls are logged
    # against a member, sales calls against a lead. Both are optional and
    # independent; a call can carry either, both, or neither.
    member_uuid: uuid.UUID | None = None
    if memberId:
        try:
            member_uuid = uuid.UUID(memberId)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=f"Invalid memberId: {memberId!r}") from exc
        exists = (await db.execute(
            text("SELECT 1 FROM members WHERE id = :id AND deleted_at IS NULL"),
            {"id": str(member_uuid)},
        )).scalar_one_or_none()
        if exists is None:
            raise HTTPException(status_code=404, detail="Member not found")

    call_id = f"CALL_{uuid4().hex[:8].upper()}"
    call = Call(
        id=call_id,
        call_type=callType or "sales_call",
        # Default the call owner to the uploading user — they're the one
        # who had the call. Overridable later via the inline-edit on the
        # call detail page if it actually belonged to a teammate.
        call_owner=current_user.email,
        video_url_hash=content_hash,
        transcript_text=transcript_text,
        transcript_source="whisper_upload",
        call_duration_minutes=(duration_seconds / 60.0) if duration_seconds else None,
        lead_id=lead_uuid,
        member_id=member_uuid,
    )
    db.add(call)
    await db.flush()

    # Audit emit on the new-call path only (the dedup branch above returns
    # early). Lands in the same transaction as the Call INSERT — if the
    # commit rolls back, the audit row goes with it.
    if lead_uuid is not None:
        try:
            actor_uuid = uuid.UUID(str(current_user.id))
        except ValueError:
            actor_uuid = None  # mock-mode safety; record_event tolerates None
        await record_event(
            db,
            user_id=actor_uuid,
            action="lead.call_logged",
            table_name="leads",
            record_id=str(lead_uuid),
            after={"call_id": call_id, "call_type": callType or "sales_call"},
        )

    try:
        save_transcript(call_id, transcript_text)
    except Exception as exc:
        logger.warning("Failed to save transcript file — call_id=%s error=%s", call_id, exc)

    # Chain the Sales Call Analyzer. Best-effort enqueue.
    try:
        from app.tasks.call_analyzer import analyze_call
        analyze_call.delay(call_id)
    except Exception as exc:
        logger.warning("Failed to enqueue analyze_call — call_id=%s error=%s", call_id, exc)

    logger.info(
        "Upload transcribed — call_id=%s filename=%s bytes=%d user_id=%s",
        call_id, file.filename, len(raw), current_user.id,
    )

    return TranscribeResponse(
        job_id=call_id,
        status="completed",
        transcript=transcript_text,
        call_id=call_id,
    )


# ---------------------------------------------------------------------------
# POST /api/v1/transcribe/async  —  async, Celery-backed
# ---------------------------------------------------------------------------


@router.post("/async", response_model=TranscribeAsyncResponse)
async def transcribe_async(
    body: TranscribeRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> TranscribeAsyncResponse:
    """Enqueue a transcription job and return immediately.

    The Celery worker handles downloading, transcribing, and persisting the
    Call record in the background.  Poll
    ``GET /api/v1/transcribe/{task_id}/status`` to track progress.
    """
    call_id = f"CALL_{uuid4().hex[:12].upper()}"

    task = transcribe_video.delay(
        video_url=body.video_url,
        call_type=body.call_type,
        member_id=body.member_id,
        lead_id=body.lead_id,
    )

    logger.info(
        "Transcription task enqueued — task_id=%s call_id=%s url=%s user_id=%s",
        task.id,
        call_id,
        body.video_url,
        current_user.id,
    )

    return TranscribeAsyncResponse(
        task_id=task.id,
        call_id=call_id,
        status="queued",
        message="Transcription queued successfully",
    )


# ---------------------------------------------------------------------------
# GET /api/v1/transcribe/{task_id}/status  —  task status poll
# ---------------------------------------------------------------------------


@router.get("/{task_id}/status", response_model=TaskStatusResponse)
async def get_task_status(
    task_id: str,
    current_user: CurrentUser = Depends(get_current_user),
) -> TaskStatusResponse:
    """Return the current status of a queued transcription task.

    Status values mirror Celery task states:
    ``PENDING``, ``STARTED``, ``SUCCESS``, ``FAILURE``, ``RETRY``.

    On ``SUCCESS`` the ``result`` field contains the transcription payload.
    On ``FAILURE`` the ``result`` field contains the error message string.
    """
    async_result = AsyncResult(task_id)

    celery_status = async_result.status  # e.g. "PENDING", "SUCCESS"

    result_payload = None
    if celery_status == "SUCCESS":
        result_payload = async_result.result
    elif celery_status == "FAILURE":
        result_payload = str(async_result.result)

    logger.debug(
        "Task status queried — task_id=%s status=%s user_id=%s",
        task_id,
        celery_status,
        current_user.id,
    )

    return TaskStatusResponse(
        task_id=task_id,
        status=celery_status,
        result=result_payload,
    )
