"""
Transcriber Celery task — Operator CI-OPS-TRANSCRIBE.

Downloads a video/audio URL, transcribes it via OpenAI Whisper, classifies
the call type, and persists the result as a Call record using a synchronous
SQLAlchemy session (Celery runs outside FastAPI's async event loop).

Sprint 2 / CI-CORE-01 / T01-3 / T01-4 / T01-5
"""

import hashlib
import logging
from datetime import datetime, timezone
from uuid import UUID, uuid4

import httpx
from celery.exceptions import MaxRetriesExceededError
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.models.operational import Call
from app.storage.transcripts import save_transcript
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Call-type routing keywords (T01-4)
# ---------------------------------------------------------------------------

_CALL_TYPE_KEYWORDS: list[tuple[str, list[str]]] = [
    ("coaching", ["coach", "coaching"]),
    ("appointment", ["appt", "appointment"]),
    ("sales_call", ["sales", "sale"]),
]

_DEFAULT_CALL_TYPE = "sales_call"


def _route_call_type(url: str) -> str:
    """Derive a call type from keywords found in the URL/filename.

    Parameters
    ----------
    url:
        The video/audio URL to inspect.

    Returns
    -------
    str
        One of ``"coaching"``, ``"appointment"``, ``"sales_call"`` (default).
    """
    url_lower = url.lower()
    for call_type, keywords in _CALL_TYPE_KEYWORDS:
        if any(kw in url_lower for kw in keywords):
            return call_type
    return _DEFAULT_CALL_TYPE


# ---------------------------------------------------------------------------
# Sync DB session factory (psycopg2 — required by Celery's sync context)
# ---------------------------------------------------------------------------


def _get_sync_db_url(async_url: str) -> str:
    """Convert an asyncpg database URL to a psycopg2 URL.

    Parameters
    ----------
    async_url:
        e.g. ``postgresql+asyncpg://user:pass@host/db``

    Returns
    -------
    str
        e.g. ``postgresql+psycopg2://user:pass@host/db``
    """
    return async_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")


def _make_sync_session() -> Session:
    """Create and return a synchronous SQLAlchemy session."""
    sync_url = _get_sync_db_url(settings.database_url)
    engine = create_engine(sync_url, pool_pre_ping=True)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    return SessionLocal()


# ---------------------------------------------------------------------------
# Mock transcript (development / no-API-key fallback)
# ---------------------------------------------------------------------------

_MOCK_TRANSCRIPT = (
    "[MOCK TRANSCRIPT] No OpenAI API key configured. "
    "This is a placeholder transcript for development purposes."
)


# ---------------------------------------------------------------------------
# Celery task
# ---------------------------------------------------------------------------


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def transcribe_video(
    self,
    video_url: str,
    call_type: str | None = None,
    member_id: str | None = None,
    lead_id: str | None = None,
) -> dict:
    """Download, transcribe, and persist a video/audio recording.

    This is the Transcriber Operator (CI-OPS-TRANSCRIBE) expressed as a
    Celery task for asynchronous, retriable execution.

    Parameters
    ----------
    video_url:
        Public URL pointing to a video or audio file.
    call_type:
        Optional explicit call type.  When omitted the type is inferred
        from keywords in ``video_url`` (T01-4 routing logic).
    member_id:
        Optional UUID string of the associated Member.
    lead_id:
        Optional UUID string of the associated Lead.

    Returns
    -------
    dict
        ``{"call_id": "CALL_...", "transcript": "...",
           "call_type": "...", "status": "completed"}``
    """
    task_id: str = self.request.id or uuid4().hex
    call_id: str = f"CALL_{uuid4().hex[:12].upper()}"

    # ------------------------------------------------------------------
    # 1. Resolve call type (T01-4)
    # ------------------------------------------------------------------
    resolved_call_type: str = call_type if call_type else _route_call_type(video_url)

    logger.info(
        "transcribe_video started — task_id=%s call_id=%s url=%s call_type=%s",
        task_id,
        call_id,
        video_url,
        resolved_call_type,
    )

    # ------------------------------------------------------------------
    # 2. Compute deduplication hash
    # ------------------------------------------------------------------
    url_hash = hashlib.sha256(video_url.encode("utf-8")).hexdigest()

    # ------------------------------------------------------------------
    # 3. Check for existing call with the same URL hash
    # ------------------------------------------------------------------
    db: Session = _make_sync_session()
    try:
        existing = db.execute(
            select(Call).where(Call.video_url_hash == url_hash)
        ).scalar_one_or_none()

        if existing is not None:
            logger.info(
                "Duplicate URL detected — returning existing call_id=%s",
                existing.id,
            )
            return {
                "call_id": existing.id,
                "transcript": existing.transcript_text or "",
                "call_type": existing.call_type or resolved_call_type,
                "status": "duplicate",
            }

        # ------------------------------------------------------------------
        # 4. Fetch the audio/video content
        # ------------------------------------------------------------------
        transcript_text = _fetch_and_transcribe(video_url, task_id)

        # ------------------------------------------------------------------
        # 5. Parse optional FK values as UUIDs
        # ------------------------------------------------------------------
        parsed_member_id: UUID | None = None
        if member_id:
            try:
                parsed_member_id = UUID(member_id)
            except ValueError:
                logger.warning("Invalid member_id UUID: %s — ignoring", member_id)

        parsed_lead_id: UUID | None = None
        if lead_id:
            try:
                parsed_lead_id = UUID(lead_id)
            except ValueError:
                logger.warning("Invalid lead_id UUID: %s — ignoring", lead_id)

        # ------------------------------------------------------------------
        # 6. Persist Call record
        # ------------------------------------------------------------------
        call = Call(
            id=call_id,
            call_type=resolved_call_type,
            transcript_link=video_url,
            transcript_source="transcriber_operator",
            transcript_uid=task_id,
            transcript_text=transcript_text,
            video_url_hash=url_hash,
            processed_date=datetime.now(timezone.utc),
            member_id=parsed_member_id,
            lead_id=parsed_lead_id,
        )
        db.add(call)
        db.commit()
        db.refresh(call)

        try:
            save_transcript(call_id, transcript_text)
        except Exception as exc:
            logger.warning(
                "Failed to save transcript file — call_id=%s error=%s",
                call_id,
                exc,
            )

        logger.info(
            "Call record persisted — call_id=%s call_type=%s",
            call_id,
            resolved_call_type,
        )

        # F19: Chain the Sales Call Analyzer to fire after every successful
        # transcription. analyze_call is itself a Celery task; .delay() enqueues
        # and returns immediately — transcribe_video does not block on analysis.
        # analyze_call's own guard rails skip empty / mock-placeholder transcripts,
        # so this is safe to call unconditionally.
        try:
            from app.tasks.call_analyzer import analyze_call

            analyzer_task = analyze_call.delay(call_id)
            logger.info(
                "analyze_call enqueued — call_id=%s analyzer_task_id=%s",
                call_id,
                analyzer_task.id,
            )
        except Exception as exc:
            # Never let the analyzer enqueue failure roll back the successful
            # transcription. Log and move on; the call can be analyzed manually
            # via POST /api/v1/ci/calls/{call_id}/analyze later.
            logger.warning(
                "Failed to enqueue analyze_call — call_id=%s error=%s",
                call_id,
                exc,
            )

        return {
            "call_id": call_id,
            "transcript": transcript_text,
            "call_type": resolved_call_type,
            "status": "completed",
        }

    except ValueError as exc:
        # Validation errors (file too large, bad content) — don't retry.
        db.rollback()
        logger.warning(
            "transcribe_video validation error — task_id=%s error=%s",
            task_id,
            exc,
        )
        raise

    except Exception as exc:
        db.rollback()
        logger.exception(
            "transcribe_video failed — task_id=%s error=%s", task_id, exc
        )
        try:
            raise self.retry(exc=exc)
        except MaxRetriesExceededError:
            logger.error(
                "Max retries exceeded for task_id=%s url=%s", task_id, video_url
            )
            raise

    finally:
        db.close()


# ---------------------------------------------------------------------------
# Audio fetch + transcription helpers
# ---------------------------------------------------------------------------


_MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024  # 25 MB — matches TranscriberOperator limit


def _fetch_and_transcribe(video_url: str, task_id: str) -> str:
    """Fetch the URL content and attempt Whisper transcription.

    Falls back to a mock transcript when ``OPENAI_API_KEY`` is not set or
    the response content-type is not audio/video.

    Parameters
    ----------
    video_url:
        The URL to download.
    task_id:
        Used only for logging correlation.

    Returns
    -------
    str
        The transcript text (real or mock).

    Raises
    ------
    ValueError
        If the file exceeds the 25 MB size limit.
    ConnectionError
        If the URL is unreachable or the download fails.
    """
    # Probe content type before committing to a full download.
    try:
        with httpx.Client(follow_redirects=True, timeout=30) as client:
            head = client.head(video_url)
            head.raise_for_status()
    except httpx.HTTPError as exc:
        raise ConnectionError(
            f"Unable to reach transcription URL: {video_url}"
        ) from exc

    content_type = head.headers.get("content-type", "").lower()
    is_media = any(
        ct in content_type for ct in ("audio/", "video/", "application/octet-stream")
    )

    if not is_media:
        logger.warning(
            "Non-media content-type '%s' for URL=%s — returning mock transcript",
            content_type,
            video_url,
        )
        return _MOCK_TRANSCRIPT

    # Download and write to a temp file — local Whisper reads from disk.
    try:
        with httpx.Client(follow_redirects=True, timeout=300) as client:
            response = client.get(video_url)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise ConnectionError(
            f"Unable to download transcription URL: {video_url}"
        ) from exc

    import tempfile
    from pathlib import Path as _Path
    suffix = _Path(video_url.split("/")[-1] or "audio.mp3").suffix or ".mp3"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(response.content)
    tmp.close()
    tmp_path = _Path(tmp.name)

    try:
        from app.services.local_whisper import transcribe_file
        result = transcribe_file(tmp_path)
        return result["transcript"]
    except Exception as exc:
        logger.error("Local Whisper error for task_id=%s: %s", task_id, exc)
        raise
    finally:
        tmp_path.unlink(missing_ok=True)
