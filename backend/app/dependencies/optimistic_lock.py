"""
FastAPI dependency for optimistic locking via the If-Match header.

Route handlers import :func:`require_if_match` and declare it as a
``Depends`` parameter.  The dependency validates that the header is present,
strips ETag quoting, and returns a timezone-aware ``datetime`` ready to pass
directly to ``repository.update_optimistic()``.

Usage
-----
Simplest form — the parsed datetime is injected automatically::

    from app.dependencies.optimistic_lock import require_if_match

    @router.put("/items/{item_id}")
    async def update_item(
        item_id: str,
        body: ItemUpdate,
        expected_updated_at: datetime = Depends(require_if_match),
        repo: ItemRepository = Depends(get_item_repo),
    ):
        item = await repo.update_optimistic(item_id, expected_updated_at, **body.model_dump())
        add_etag_header(response, item.updated_at)
        return item

If the ``If-Match`` header is absent the dependency raises HTTP 428.
If the header value cannot be parsed as an ISO 8601 timestamp it raises HTTP 400.
If the timestamp does not match the current DB row the repository raises HTTP 409.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import Header, HTTPException

from app.middleware.optimistic_lock import parse_if_match


def require_if_match(
    if_match: str | None = Header(None, alias="If-Match"),
) -> datetime:
    """FastAPI dependency that requires and parses the If-Match header.

    Declare this as a ``Depends`` on any PUT or PATCH route that should be
    protected by optimistic locking.  The returned ``datetime`` can be passed
    directly to ``repository.update_optimistic(id, expected_updated_at, ...)``.

    Parameters
    ----------
    if_match:
        Injected by FastAPI from the ``If-Match`` request header.

    Returns
    -------
    datetime
        The parsed, UTC-aware datetime encoded in the ETag.

    Raises
    ------
    HTTPException
        - **428 Precondition Required** — ``If-Match`` header is absent.
        - **400 Bad Request** — header is present but not a parseable ETag.
    """
    if if_match is None:
        raise HTTPException(
            status_code=428,
            detail={
                "error": {
                    "code": "PRECONDITION_REQUIRED",
                    "message": (
                        "PUT and PATCH requests require an If-Match header. "
                        "Fetch the resource first to obtain its current ETag."
                    ),
                    "timestamp": _now_iso(),
                    "request_id": None,
                }
            },
        )

    return parse_if_match(if_match)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    from datetime import timezone

    return datetime.now(timezone.utc).isoformat()
