"""Read-only WGR table reader for the sync.

Thin wrapper over ``app.services.wgr_client`` (which forces read-only sessions).
Supports an optional ``since`` watermark on tables that have a usable change
timestamp, falling back to a full pull when ``since`` is None (backfill) or the
table has no watermark column.
"""

from __future__ import annotations

from typing import Any, Iterator, Optional

from app.services import wgr_client

# Per-table watermark column. Tables not listed here are always pulled in full
# (small/static, or no reliable change timestamp). leads has updated_at; the
# call-intelligence + activity tables use created_at/occurred_at.
WATERMARK_COLUMN: dict[str, str] = {
    "leads": "updated_at",
    "appointments": "created_at",
    "calls": "created_at",
    "insights": "created_at",
    "content_ideas": "created_at",
    "sales_call_scores": "scored_at",
    "sales_activities": "occurred_at",
    "sales_eod_reports": "generated_at",
    "webinar_engagements": "created_at",
    "lead_opt_in_events": "occurred_at",
    "sales": "created_at",
    "email_campaigns": "synced_at",
    "comment_events": "created_at",
    "instagram_posts": "synced_at",
    # insight_tags has created_at but is tiny/static; full pull is fine.
}


def read_table(
    table: str,
    *,
    since: Optional[str] = None,
    page_size: int = 1000,
) -> Iterator[dict[str, Any]]:
    """Yield rows from a WGR table, optionally only those changed since a
    watermark. ``since`` is an ISO timestamp string; ignored if the table has no
    watermark column."""
    col = WATERMARK_COLUMN.get(table)
    where = None
    params: tuple = ()
    order_by = None
    if col and since:
        where = f"{col} >= %s"
        params = (since,)
        order_by = f"{col} asc"
    elif col:
        order_by = f"{col} asc"
    yield from wgr_client.iter_rows(
        table, where=where, params=params, order_by=order_by, page_size=page_size,
    )


def count_table(table: str, *, since: Optional[str] = None) -> int:
    col = WATERMARK_COLUMN.get(table)
    if col and since:
        return wgr_client.count(table, where=f"{col} >= %s", params=(since,))
    return wgr_client.count(table)
