"""
Optimistic locking utilities for Central Intelligence.

This module provides the building blocks for ETag-based optimistic concurrency
control on PUT/PATCH endpoints, following RFC 7232.

ETag format
-----------
We use weak ETags backed by the ``updated_at`` timestamp::

    W/"2026-03-31T10:00:00.000000+00:00"

Weak ETags express *semantic* equivalence rather than byte-for-byte identity,
which is appropriate here: two responses with the same ``updated_at`` contain
the same logical resource state, even if whitespace differs.

Typical flow
------------
1.  Client fetches a resource — response carries ``ETag: W/"<timestamp>"``.
2.  Client sends ``PUT /resource/<id>`` with ``If-Match: W/"<timestamp>"``.
3.  ``require_if_match`` dependency extracts and parses the header value.
4.  Repository ``update_optimistic`` compares the parsed datetime against the
    DB row's ``updated_at``; raises 409 if they differ.
5.  On success the response includes a fresh ``ETag`` header.

Public API
----------
- :func:`etag_from_datetime` — datetime → quoted ETag string
- :func:`parse_if_match` — ETag string → datetime (raises 400 if invalid)
- :class:`StaleUpdateError` — HTTPException subclass for 409 Conflict
- :func:`add_etag_header` — attach an ETag header to a FastAPI Response
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.responses import Response

from fastapi import HTTPException

# ---------------------------------------------------------------------------
# ETag helpers
# ---------------------------------------------------------------------------

_WEAK_PREFIX = 'W/"'
_WEAK_SUFFIX = '"'


def etag_from_datetime(dt: datetime) -> str:
    """Convert a datetime to a weak ETag string.

    The datetime is normalised to UTC before formatting so that timestamps
    stored with or without explicit timezone info produce the same ETag.

    Example::

        etag_from_datetime(datetime(2026, 3, 31, 10, 0, 0, tzinfo=timezone.utc))
        # -> 'W/"2026-03-31T10:00:00+00:00"'

    Parameters
    ----------
    dt:
        The ``updated_at`` value from a database row.

    Returns
    -------
    str
        A properly quoted weak ETag, e.g. ``W/"2026-03-31T10:00:00+00:00"``.
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return f'{_WEAK_PREFIX}{dt.isoformat()}{_WEAK_SUFFIX}'


def parse_if_match(header_value: str) -> datetime:
    """Parse an If-Match header value back into a timezone-aware datetime.

    Handles both weak ETags (``W/"..."``) and strong ETags (``"..."``).
    Raises HTTP 400 if the value cannot be parsed.

    Parameters
    ----------
    header_value:
        The raw ``If-Match`` header string sent by the client.

    Returns
    -------
    datetime
        A UTC-aware datetime representing the client's last-known version.

    Raises
    ------
    HTTPException
        Status 400 when the header value is not a parseable ETag/timestamp.
    """
    raw = header_value.strip()

    # Strip weak prefix W/"..." or strong prefix "..."
    if raw.startswith('W/"') and raw.endswith('"'):
        timestamp_str = raw[3:-1]
    elif raw.startswith('"') and raw.endswith('"'):
        timestamp_str = raw[1:-1]
    else:
        # Tolerate bare timestamp without quotes (non-standard but lenient).
        timestamp_str = raw

    try:
        dt = datetime.fromisoformat(timestamp_str)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "INVALID_IF_MATCH",
                    "message": (
                        "If-Match header could not be parsed as a valid ETag. "
                        "Expected format: W/\"<ISO-8601 timestamp>\""
                    ),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "request_id": None,
                }
            },
        )

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    return dt


# ---------------------------------------------------------------------------
# StaleUpdateError — 409 Conflict
# ---------------------------------------------------------------------------


class StaleUpdateError(HTTPException):
    """Raised when a client attempts to update a stale version of a resource.

    Follows the standard Central Intelligence error envelope::

        {
            "error": {
                "code": "STALE_UPDATE",
                "message": "...",
                "timestamp": "...",
                "request_id": "..."
            }
        }

    Parameters
    ----------
    request_id:
        Optional correlation ID echoed from the ``X-Request-ID`` header.
    """

    def __init__(self, request_id: str | None = None) -> None:
        detail = {
            "error": {
                "code": "STALE_UPDATE",
                "message": (
                    "The resource has been modified since you last fetched it. "
                    "Retrieve the latest version and retry your update."
                ),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "request_id": request_id or str(uuid.uuid4()),
            }
        }
        super().__init__(status_code=409, detail=detail)


# ---------------------------------------------------------------------------
# FastAPI dependency — require If-Match on PUT/PATCH
# ---------------------------------------------------------------------------


async def require_if_match(request: Request) -> str:
    """FastAPI dependency that enforces the presence of an If-Match header.

    Only PUT and PATCH requests are checked; all other methods pass through
    with an empty string return value so the dependency can be wired globally
    if desired.

    Mount this on individual routes or as a router-level dependency::

        @router.put("/{id}", dependencies=[Depends(require_if_match)])

    Or capture the raw value for manual use::

        @router.put("/{id}")
        async def update(id: str, raw_etag: str = Depends(require_if_match)):
            ...

    Parameters
    ----------
    request:
        Injected by FastAPI.

    Returns
    -------
    str
        The raw ``If-Match`` header value (still quoted).

    Raises
    ------
    HTTPException
        Status 428 Precondition Required when the header is absent on a
        PUT or PATCH request.
    """
    if request.method not in ("PUT", "PATCH"):
        return ""

    header_value = request.headers.get("if-match") or request.headers.get("If-Match")

    if not header_value:
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        raise HTTPException(
            status_code=428,
            detail={
                "error": {
                    "code": "PRECONDITION_REQUIRED",
                    "message": (
                        "PUT and PATCH requests require an If-Match header. "
                        "Fetch the resource first to obtain its current ETag."
                    ),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "request_id": request_id,
                }
            },
        )

    return header_value


# ---------------------------------------------------------------------------
# Response helper — attach ETag to outgoing response
# ---------------------------------------------------------------------------


def add_etag_header(response: Response, updated_at: datetime) -> Response:
    """Set the ``ETag`` response header derived from ``updated_at``.

    Call this at the end of any GET, POST, PUT, or PATCH handler that returns
    a resource with an ``updated_at`` field so clients can capture the ETag
    for future conditional requests::

        @router.get("/{id}")
        async def get_item(id: str, response: Response):
            item = await repo.get(id)
            add_etag_header(response, item.updated_at)
            return item

    Parameters
    ----------
    response:
        The FastAPI ``Response`` object injected into the route handler.
    updated_at:
        The ``updated_at`` datetime of the resource being returned.

    Returns
    -------
    Response
        The same ``response`` object with the ``ETag`` header set (for
        convenience chaining).
    """
    response.headers["ETag"] = etag_from_datetime(updated_at)
    return response
