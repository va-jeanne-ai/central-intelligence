"""Facebook (Meta Graph API) client — social-stats connector.

Thin httpx wrapper around the Graph API endpoints needed by the
``update_social_stats`` Celery task to pull organic Facebook Page metrics:

  - ``GET /{page_id}?fields=followers_count,fan_count,name``
        — follower count (fan_count is the legacy "likes" total; we prefer
        followers_count and fall back to fan_count)
  - ``GET /{page_id}/insights?metric=page_impressions,page_post_engagements&period=days_28``
        — Page impressions + post engagements over the trailing 28 days
        (Page Insights return a time series; we sum the window)
  - ``GET /{page_id}/posts?fields=...&limit=25``
        — recent posts: count + likes/comments to estimate an engagement rate

We deliberately do NOT use the facebook-sdk; httpx is already a project dep.

Auth: a long-lived **Page** access token is passed as the ``access_token``
query param on every request. Creds are resolved from the ``integrations`` row
(provider='facebook') — decrypted token + ``page_id`` from the blob — mirroring
:mod:`app.services.facebook_credentials`. The task passes creds explicitly;
:func:`verify` resolves them from the DB for the integrations "Test" button.

Note: Facebook has no "reach" Page metric directly comparable to Instagram's;
we map ``page_impressions`` to both reach and impressions is wrong, so we leave
``reach=None`` and populate ``impressions`` from ``page_impressions``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_GRAPH_BASE = "https://graph.facebook.com/v19.0"
_DEFAULT_TIMEOUT = 30.0
_RECENT_POSTS_LIMIT = 25


@dataclass(frozen=True)
class FacebookStats:
    """Normalised Facebook Page metrics ready for upsert into SocialStats."""

    followers: int
    posts_count: int
    engagement_rate: float | None  # percentage, e.g. 1.8 for 1.8 %
    reach: int | None
    impressions: int | None
    name: str | None = None


# ---------------------------------------------------------------------------
# Credential resolution (DB-backed, for the Test button)
# ---------------------------------------------------------------------------


def _resolve_creds() -> tuple[str, str] | None:
    """Return ``(access_token, page_id)`` from the integrations row, or None.

    Runs synchronously via ``make_sync_session`` so it works from both Celery
    (sync) and FastAPI handlers. Never raises — returns None on any failure so
    callers can gate via :func:`is_configured`.
    """
    try:
        from sqlalchemy import select as _select

        from app.models.integration import Integration as _Integration
        from app.services.facebook_credentials import load_facebook_credentials
        from app.tasks.db import make_sync_session as _make_sync_session

        db = _make_sync_session()
        try:
            row = db.execute(
                _select(_Integration).where(_Integration.provider == "facebook")
            ).scalar_one_or_none()
            if row is None or row.status != "connected":
                return None
            return load_facebook_credentials(row)
        finally:
            db.close()
    except Exception as exc:  # noqa: BLE001 — resolution must never crash callers
        logger.warning("Facebook DB resolve fallback: %s", exc)
        return None


def is_configured() -> bool:
    """True when a usable Facebook credential is resolvable from the DB."""
    return _resolve_creds() is not None


# ---------------------------------------------------------------------------
# Graph API calls
# ---------------------------------------------------------------------------


def _get(path: str, access_token: str, params: dict[str, Any] | None = None) -> dict:
    """Issue a GET against the Graph API and return parsed JSON.

    Raises ``httpx.HTTPStatusError`` on a non-2xx (Meta returns rich error JSON;
    the caller logs it). The access token is appended as a query param.
    """
    query: dict[str, Any] = dict(params or {})
    query["access_token"] = access_token
    url = f"{_GRAPH_BASE}/{path.lstrip('/')}"
    with httpx.Client(timeout=_DEFAULT_TIMEOUT) as c:
        resp = c.get(url, params=query)
        resp.raise_for_status()
        return resp.json()


def _sum_insight_values(entry: dict[str, Any]) -> int:
    """Sum the time-series ``values`` of one Page Insights metric entry."""
    total = 0
    for v in entry.get("values") or []:
        try:
            total += int(v.get("value") or 0)
        except (TypeError, ValueError):
            continue
    return total


def _estimate_engagement_rate(
    posts: list[dict[str, Any]], followers: int
) -> float | None:
    """Avg (likes + comments) per recent post, as a % of followers.

    Returns None when we lack the inputs (no posts or zero followers) rather
    than emitting a misleading 0.0. Likes/comments come back as
    ``summary.total_count`` when requested with ``.summary(true).limit(0)``.
    """
    if not posts or followers <= 0:
        return None
    total = 0
    counted = 0
    for p in posts:
        likes = (p.get("likes") or {}).get("summary", {}).get("total_count")
        comments = (p.get("comments") or {}).get("summary", {}).get("total_count")
        if likes is None and comments is None:
            continue
        total += int(likes or 0) + int(comments or 0)
        counted += 1
    if counted == 0:
        return None
    avg_interactions = total / counted
    return round((avg_interactions / followers) * 100, 2)


def fetch_facebook_stats(access_token: str, page_id: str) -> FacebookStats:
    """Fetch live metrics for one Facebook Page.

    The profile call (followers) is required; insights and recent posts are
    best-effort — if either fails we still return the rest rather than failing
    the whole sync.
    """
    profile = _get(
        page_id,
        access_token,
        {"fields": "followers_count,fan_count,name"},
    )
    followers = int(profile.get("followers_count") or profile.get("fan_count") or 0)
    name = profile.get("name")

    impressions: int | None = None
    try:
        insights = _get(
            f"{page_id}/insights",
            access_token,
            {"metric": "page_impressions", "period": "days_28"},
        )
        for entry in insights.get("data", []):
            if entry.get("name") == "page_impressions":
                impressions = _sum_insight_values(entry)
    except Exception as exc:  # noqa: BLE001 — insights are optional
        logger.warning("Facebook insights fetch failed for %s: %s", page_id, exc)

    posts_count = 0
    engagement_rate: float | None = None
    try:
        posts_resp = _get(
            f"{page_id}/posts",
            access_token,
            {
                "fields": "likes.summary(true).limit(0),comments.summary(true).limit(0)",
                "limit": str(_RECENT_POSTS_LIMIT),
            },
        )
        posts = posts_resp.get("data", [])
        posts_count = len(posts)
        engagement_rate = _estimate_engagement_rate(posts, followers)
    except Exception as exc:  # noqa: BLE001 — posts are best-effort
        logger.warning("Facebook posts fetch failed for %s: %s", page_id, exc)

    return FacebookStats(
        followers=followers,
        posts_count=posts_count,
        engagement_rate=engagement_rate,
        reach=None,  # no direct Page "reach" metric comparable to IG's
        impressions=impressions,
        name=name,
    )


def verify() -> tuple[bool, str]:
    """Light connectivity check for the integrations 'Test' button.

    Resolves creds from the DB, hits the Page profile endpoint, and returns
    ``(ok, message)``. Never raises.
    """
    creds = _resolve_creds()
    if creds is None:
        return False, "Facebook is not connected. Save credentials first."
    access_token, page_id = creds
    try:
        profile = _get(
            page_id, access_token, {"fields": "name,followers_count,fan_count"}
        )
        name = profile.get("name")
        followers = profile.get("followers_count") or profile.get("fan_count")
        who = f"“{name}”" if name else f"page {page_id}"
        return True, f"Connected to {who} ({followers} followers)."
    except httpx.HTTPStatusError as exc:
        detail = ""
        try:
            detail = exc.response.json().get("error", {}).get("message", "")
        except Exception:  # noqa: BLE001
            detail = exc.response.text[:200]
        return False, f"Facebook API rejected the request: {detail or exc}"
    except Exception as exc:  # noqa: BLE001
        return False, f"Could not reach Facebook: {exc}"
