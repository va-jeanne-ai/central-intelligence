"""
Common Pydantic schemas shared across the Central Intelligence API.

These are not resource-specific — they represent structural envelopes and
error shapes that every endpoint can reference.

Error envelope example::

    {
        "error": {
            "code": "STALE_UPDATE",
            "message": "The resource has been modified since you last fetched it.",
            "timestamp": "2026-03-31T10:00:00.000000+00:00",
            "request_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6"
        }
    }
"""

from __future__ import annotations

from pydantic import BaseModel


class ErrorDetail(BaseModel):
    """Structured error body used in every non-2xx API response."""

    code: str
    """Machine-readable error code, e.g. ``STALE_UPDATE``, ``UNAUTHORIZED``."""

    message: str
    """Human-readable description suitable for display in a toast/alert."""

    timestamp: str
    """ISO 8601 UTC timestamp of when the error was generated."""

    request_id: str | None = None
    """Echo of the ``X-Request-ID`` header, when present, for log correlation."""


class ErrorResponse(BaseModel):
    """Top-level error envelope returned by all error responses."""

    error: ErrorDetail
