"""Request / response schemas for the transcription endpoints.

Covers both the synchronous POST /api/v1/transcribe endpoint (T01-2) and
the asynchronous Celery-backed endpoints (T01-5):

  POST /api/v1/transcribe/async      — enqueue a transcription task
  GET  /api/v1/transcribe/{task_id}/status — poll task status

Sprint 2 / CI-CORE-01 / T01-2, T01-5
"""

from typing import Any, Optional

from pydantic import BaseModel, field_validator


class TranscribeRequest(BaseModel):
    """Payload for POST /api/v1/transcribe (sync) and /api/v1/transcribe/async."""

    video_url: str
    call_type: Optional[str] = None  # auto-routed when omitted
    lead_id: Optional[str] = None
    member_id: Optional[str] = None

    @field_validator("video_url")
    @classmethod
    def validate_video_url(cls, v: str) -> str:
        """Reject obviously invalid URLs before any network I/O."""
        v = v.strip()
        if not v:
            raise ValueError("video_url must not be empty")
        if not v.startswith(("http://", "https://")):
            raise ValueError(
                "video_url must be an HTTP or HTTPS URL"
            )
        return v


class TranscribeResponse(BaseModel):
    """Response from POST /api/v1/transcribe (sync)."""

    job_id: str
    status: str  # "queued" | "completed" | "duplicate"
    transcript: Optional[str] = None
    call_id: Optional[str] = None
    message: Optional[str] = None


class TranscribeAsyncResponse(BaseModel):
    """Response from POST /api/v1/transcribe/async (Celery-backed)."""

    task_id: str
    call_id: str
    status: str  # always "queued" at submission time
    message: str


class TaskStatusResponse(BaseModel):
    """Response from GET /api/v1/transcribe/{task_id}/status."""

    task_id: str
    status: str  # "PENDING" | "STARTED" | "SUCCESS" | "FAILURE" | "RETRY"
    result: Optional[Any] = None
