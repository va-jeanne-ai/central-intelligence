"""Instagram (Meta Graph API) client — social-stats connector.

Thin httpx wrapper around the few Graph API endpoints needed by the
``update_social_stats`` Celery task to pull organic Instagram metrics for an
Instagram Business/Creator account:

  - ``GET /{ig_user_id}?fields=followers_count,media_count,username``
        — follower count + total posts
  - ``GET /{ig_user_id}/insights?metric=reach,impressions&period=days_28``
        — account-level reach + impressions over the trailing 28 days
  - ``GET /{ig_user_id}/media?fields=like_count,comments_count&limit=25``
        — recent posts, used to estimate an engagement rate

We deliberately do NOT use the facebook-sdk; httpx is already a project dep
and we only touch three endpoints.

Auth: the access token is passed as the ``access_token`` query param on every
request (standard Meta Graph API). Creds are resolved from the ``integrations``
row (provider='instagram') — decrypted token + ``ig_user_id`` from the blob —
mirroring how :mod:`app.services.instagram_credentials` reads them. The task
passes creds explicitly; :func:`verify` resolves them from the DB for the
integrations "Test" button.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_GRAPH_BASE = "https://graph.facebook.com/v19.0"
_DEFAULT_TIMEOUT = 30.0
_RECENT_MEDIA_LIMIT = 25


@dataclass(frozen=True)
class InstagramStats:
    """Normalised Instagram account metrics ready for upsert into SocialStats."""

    followers: int
    posts_count: int
    engagement_rate: float | None  # percentage, e.g. 3.2 for 3.2 %
    reach: int | None
    impressions: int | None
    username: str | None = None


# ---------------------------------------------------------------------------
# Credential resolution (DB-backed, for the Test button)
# ---------------------------------------------------------------------------


def _resolve_creds() -> tuple[str, str] | None:
    """Return ``(access_token, ig_user_id)`` from the integrations row, or None.

    Runs synchronously via ``make_sync_session`` so it works from both Celery
    (sync) and FastAPI handlers. Never raises — returns None on any failure so
    callers can gate via :func:`is_configured`.
    """
    try:
        from sqlalchemy import select as _select

        from app.models.integration import Integration as _Integration
        from app.services.instagram_credentials import load_instagram_credentials
        from app.tasks.db import make_sync_session as _make_sync_session

        db = _make_sync_session()
        try:
            row = db.execute(
                _select(_Integration).where(_Integration.provider == "instagram")
            ).scalar_one_or_none()
            if row is None or row.status != "connected":
                return None
            return load_instagram_credentials(row)
        finally:
            db.close()
    except Exception as exc:  # noqa: BLE001 — resolution must never crash callers
        logger.warning("Instagram DB resolve fallback: %s", exc)
        return None


def is_configured() -> bool:
    """True when a usable Instagram credential is resolvable from the DB."""
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


def _estimate_engagement_rate(
    media: list[dict[str, Any]], followers: int
) -> float | None:
    """Avg (likes + comments) per recent post, as a % of followers.

    Returns None when we lack the inputs (no media or zero followers) rather
    than emitting a misleading 0.0.
    """
    if not media or followers <= 0:
        return None
    total = 0
    counted = 0
    for m in media:
        likes = m.get("like_count")
        comments = m.get("comments_count")
        if likes is None and comments is None:
            continue
        total += int(likes or 0) + int(comments or 0)
        counted += 1
    if counted == 0:
        return None
    avg_interactions = total / counted
    return round((avg_interactions / followers) * 100, 2)


def fetch_instagram_stats(access_token: str, ig_user_id: str) -> InstagramStats:
    """Fetch live account metrics for one Instagram Business account.

    Profile + insights are required; recent media (for engagement) is
    best-effort — if that call fails we still return the rest with
    ``engagement_rate=None`` rather than failing the whole sync.
    """
    profile = _get(
        ig_user_id,
        access_token,
        {"fields": "followers_count,media_count,username"},
    )
    followers = int(profile.get("followers_count") or 0)
    posts_count = int(profile.get("media_count") or 0)
    username = profile.get("username")

    reach: int | None = None
    impressions: int | None = None
    try:
        insights = _get(
            f"{ig_user_id}/insights",
            access_token,
            {"metric": "reach,impressions", "period": "days_28"},
        )
        for entry in insights.get("data", []):
            name = entry.get("name")
            values = entry.get("values") or []
            value = int(values[0].get("value") or 0) if values else None
            if name == "reach":
                reach = value
            elif name == "impressions":
                impressions = value
    except Exception as exc:  # noqa: BLE001 — insights are optional
        logger.warning("Instagram insights fetch failed for %s: %s", ig_user_id, exc)

    engagement_rate: float | None = None
    try:
        media_resp = _get(
            f"{ig_user_id}/media",
            access_token,
            {"fields": "like_count,comments_count", "limit": str(_RECENT_MEDIA_LIMIT)},
        )
        engagement_rate = _estimate_engagement_rate(
            media_resp.get("data", []), followers
        )
    except Exception as exc:  # noqa: BLE001 — engagement is best-effort
        logger.warning("Instagram media fetch failed for %s: %s", ig_user_id, exc)

    return InstagramStats(
        followers=followers,
        posts_count=posts_count,
        engagement_rate=engagement_rate,
        reach=reach,
        impressions=impressions,
        username=username,
    )


def verify() -> tuple[bool, str]:
    """Light connectivity check for the integrations 'Test' button.

    Resolves creds from the DB, hits the profile endpoint, and returns
    ``(ok, message)``. Never raises.
    """
    creds = _resolve_creds()
    if creds is None:
        return False, "Instagram is not connected. Save credentials first."
    access_token, ig_user_id = creds
    try:
        profile = _get(
            ig_user_id, access_token, {"fields": "followers_count,username"}
        )
        handle = profile.get("username")
        followers = profile.get("followers_count")
        who = f"@{handle}" if handle else f"account {ig_user_id}"
        return True, f"Connected to {who} ({followers} followers)."
    except httpx.HTTPStatusError as exc:
        detail = ""
        try:
            detail = exc.response.json().get("error", {}).get("message", "")
        except Exception:  # noqa: BLE001
            detail = exc.response.text[:200]
        return False, f"Instagram API rejected the request: {detail or exc}"
    except Exception as exc:  # noqa: BLE001
        return False, f"Could not reach Instagram: {exc}"
