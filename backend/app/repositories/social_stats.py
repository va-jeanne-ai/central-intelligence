"""Pure social-page rollup helpers, built on the real WGR mirrors
(``instagram_posts``, ``wgr_post_comment_leads``, ``wgr_comment_events``).

Greg's own tracking page (``central-intelligence-greg/index.html``,
``view-mkt-social`` — deliverable 1) computes these same rollups client-side
in JS against the live Instagram Graph API + two Express routes
(``/api/social/comment-leads``, ``/api/social/comment-leads-by-day``). This
module reproduces the SAME metric semantics server-side against the mirrored
data so ``GET /social/overview`` can serve one consistent payload:

  * Posts in Range / Reels / Carousels — counts by ``is_reel`` / ``media_type``.
  * Watch Time / Total Views — reel-only rollups (``avg_watch_time_sec``;
    CI's mirror has no total-watch-time column — see docstring on
    ``build_summary_stats``).
  * Total Reach / Likes / Saves — sums across the filtered post set.
  * Per-keyword lead cards + Total Leads — from ``wgr_post_comment_leads.
    keyword_counts`` joined by ``ig_media_id``.
  * Leads by Day — from ``wgr_comment_events`` bucketed by ``occurred_at``
    date, mirroring WGR's own ``comment_leads_by_day()`` RPC frame (leads
    that ARRIVED each day, any post, any platform) — distinct from the
    post-date frame used by the per-post/keyword counts above.

Pure (no DB) so these are unit-testable against fake rows, mirroring
``test_offer_stats.py`` / ``test_funnel_stats.py`` style. The route layer
does the DB reads and hands plain dicts/rows to these functions.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timezone
from typing import Any, Sequence


def _int(value: object) -> int:
    """Return value as int, falling back to 0 for None or non-numeric values."""
    try:
        return int(value) if value is not None else 0
    except (TypeError, ValueError):
        return 0


def _float(value: object) -> float:
    """Return value as float, falling back to 0.0 for None or non-numeric values."""
    try:
        return float(value) if value is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def _post_date(value: Any) -> date | None:
    """Coerce a post's posted_at (datetime or ISO string) to a plain date."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
    except ValueError:
        return None


def filter_posts(
    posts: Sequence[dict],
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    media_type: str | None = None,
) -> list[dict]:
    """Apply the social page's date-range + type filter to a post list.

    Mirrors ``applyIgFilter()`` in Greg's page: inclusive date bounds on
    ``posted_at``, and a type filter matching either ``is_reel`` (for
    "REELS") or ``media_type`` (for "IMAGE"/"VIDEO"/"CAROUSEL_ALBUM").
    """
    out = []
    for p in posts:
        d = _post_date(p.get("posted_at"))
        if date_from is not None and (d is None or d < date_from):
            continue
        if date_to is not None and (d is None or d > date_to):
            continue
        if media_type:
            if media_type == "REELS":
                if not p.get("is_reel"):
                    continue
            elif (p.get("media_type") or "").upper() != media_type.upper():
                continue
        out.append(p)
    return out


def build_summary_stats(posts: Sequence[dict]) -> dict[str, Any]:
    """Roll up the social page's summary stat cards from a filtered post set.

    Reel-only fields (Watch Time, Total Views) are computed only over rows
    with ``is_reel`` true, matching Greg's page (which shows "—" for
    non-reels in those columns). ``total_watch_time_sec`` sums
    ``avg_watch_time_sec`` per reel as a **stated approximation** — WGR's
    mirror does not carry Greg's page's ``ig_reels_video_view_total_time``
    (total watch time), only the average per-post; see
    FEATURE-VERIFICATION.md "Documented gaps" for the exact wording.
    """
    reels = [p for p in posts if p.get("is_reel")]
    carousels = [p for p in posts if (p.get("media_type") or "").upper() == "CAROUSEL_ALBUM"]
    return {
        "posts_in_range": len(posts),
        "reels_count": len(reels),
        "carousels_count": len(carousels),
        "total_watch_time_sec": sum(_int(p.get("avg_watch_time_sec")) for p in reels),
        "total_views": sum(_int(p.get("views")) for p in reels),
        "total_reach": sum(_int(p.get("reach")) for p in posts),
        "total_likes": sum(_int(p.get("likes_count")) for p in posts),
        "total_saves": sum(_int(p.get("saves_count")) for p in posts),
    }


def build_keyword_totals(
    posts: Sequence[dict],
    lead_rows: Sequence[dict],
) -> dict[str, Any]:
    """Per-keyword lead totals + grand total, scoped to the filtered post set.

    ``lead_rows`` are ``wgr_post_comment_leads`` rows (``ig_media_id`` +
    ``keyword_counts`` jsonb + ``total_leads``). Only leads for posts present
    in ``posts`` (the date/type-filtered set) are counted — matches Greg's
    page, where the per-keyword stat cards react to the same filter bar as
    the Posts table. Keywords are discovered dynamically from the data
    (never hardcoded), matching the "keyword-generic" comment-leads route.
    """
    post_ids = {p.get("ig_media_id") for p in posts if p.get("ig_media_id")}
    per_keyword: dict[str, int] = defaultdict(int)
    total = 0
    for row in lead_rows:
        if row.get("ig_media_id") not in post_ids:
            continue
        counts = row.get("keyword_counts") or {}
        if isinstance(counts, dict):
            for kw, n in counts.items():
                per_keyword[str(kw).lower()] += _int(n)
        total += _int(row.get("total_leads"))
    return {
        "keywords": sorted(per_keyword.keys()),
        "per_keyword": dict(per_keyword),
        "total_leads": total,
    }


def attach_post_lead_counts(
    posts: Sequence[dict],
    lead_rows: Sequence[dict],
) -> list[dict]:
    """Return posts with a ``lead_counts`` (per-keyword dict) + ``lead_total``
    field merged in from ``wgr_post_comment_leads``, keyed by ``ig_media_id``.
    Posts with no matching lead row get an empty dict / 0 total."""
    by_media_id = {
        row.get("ig_media_id"): row for row in lead_rows if row.get("ig_media_id")
    }
    out = []
    for p in posts:
        row = by_media_id.get(p.get("ig_media_id"))
        counts = row.get("keyword_counts") if row else {}
        out.append({
            **p,
            "lead_counts": counts if isinstance(counts, dict) else {},
            "lead_total": _int(row.get("total_leads")) if row else 0,
        })
    return out


def sort_posts(posts: Sequence[dict], *, sort_col: str, sort_dir: str = "desc") -> list[dict]:
    """Sort posts by any of the Posts table's sortable columns, nulls always
    last — mirrors ``renderIgTable``'s sort semantics exactly (including the
    "timestamp" alias for ``posted_at``)."""
    col = "posted_at" if sort_col == "timestamp" else sort_col
    reverse = sort_dir != "asc"

    def key(p: dict) -> tuple[int, Any]:
        v = p.get(col)
        if v is None:
            return (1, 0)
        if col == "posted_at":
            d = _post_date(v)
            return (0, d or date.min)
        if isinstance(v, (int, float)):
            return (0, v)
        return (0, v)

    # Nulls-last regardless of direction: sort by (is_null, value), value
    # comparison only applied within the non-null group.
    non_null = [p for p in posts if p.get(col) is not None]
    null = [p for p in posts if p.get(col) is None]
    non_null.sort(key=lambda p: key(p)[1], reverse=reverse)
    return non_null + null


def paginate_posts(
    posts: Sequence[dict], *, limit: int, offset: int,
) -> tuple[list[dict], int]:
    """Slice an already-sorted post list for the Posts table's pagination.

    Returns ``(page, total)`` where ``total`` is the PRE-slice count (the
    full filtered/sorted set, not the page length) — the frontend's
    ``Pagination`` component needs the true total to compute page count and
    the "X-Y of N" label. A negative or zero ``limit``/``offset`` is not
    expected here (the route's ``Query(ge=...)`` bounds already reject
    those before this is called) — this function trusts its inputs and
    just slices.
    """
    total = len(posts)
    page = posts[offset:offset + limit]
    return page, total


def build_leads_by_day(
    events: Sequence[dict],
    *,
    date_from: date | None = None,
    date_to: date | None = None,
) -> dict[str, Any]:
    """Bucket ``wgr_comment_events`` rows by the UTC date of ``occurred_at``.

    Mirrors WGR's ``comment_leads_by_day()`` RPC frame: "how many leads
    ARRIVED on day X, from any post, any platform" (distinct from the
    per-post/keyword frame in ``build_keyword_totals``, which is "how many
    leads has THIS post generated, ever"). Timezone note: WGR buckets in the
    tenant's configured timezone (``ac_timezone``, default America/Denver);
    this mirrors in UTC — a documented, minor day-boundary difference (see
    FEATURE-VERIFICATION.md).
    """
    per_day: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    keywords: set[str] = set()
    for ev in events:
        occurred = ev.get("occurred_at")
        if occurred is None:
            continue
        d = occurred.date() if isinstance(occurred, datetime) else _post_date(occurred)
        if d is None:
            continue
        if date_from is not None and d < date_from:
            continue
        if date_to is not None and d > date_to:
            continue
        kw = (ev.get("keyword") or "").strip().lower()
        if not kw:
            continue
        keywords.add(kw)
        day_key = d.isoformat()
        per_day[day_key][kw] += 1
        per_day[day_key]["total"] += 1

    days = [
        {"day": day, **counts}
        for day, counts in sorted(per_day.items(), key=lambda kv: kv[0], reverse=True)
    ]
    return {"keywords": sorted(keywords), "days": days}
