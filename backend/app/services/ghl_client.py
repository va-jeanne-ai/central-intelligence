"""GHL REST API client — read-only contact fetch for the sync task.

Wraps ``httpx.Client`` with a paginated contact iterator. Sync style
(not async) because Celery tasks run in worker threads and the analyzer
codebase uses the same sync-client convention as ``mailchimp_client``.

Auth: ``Authorization: Bearer <access_token>`` + ``Version: 2021-07-28``
header (GHL's v2 API pins to a header-versioned date).

Rate limits: on HTTP 429 we sleep for the ``Retry-After`` header (or 5
seconds if absent) and retry the same request once. Repeated 429s on the
same page raise — Celery's task-level retry catches it.

The output is a stream of raw contact dicts. Field normalization happens
downstream in ``ghl_upsert.upsert_ghl_lead`` so the webhook + sync paths
parse the same shapes.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Iterator

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEFAULT_BASE_URL = "https://services.leadconnectorhq.com"
_API_VERSION_HEADER = "2021-07-28"  # required for GHL v2 endpoints
_DEFAULT_PAGE_SIZE = 100  # GHL caps at 100 per request
_DEFAULT_TIMEOUT = 30.0  # seconds
_RATE_LIMIT_DEFAULT_BACKOFF = 5.0  # seconds, when Retry-After is absent
_MAX_429_RETRIES = 3  # per request


def _base_url() -> str:
    """Allow overriding via env for testing or future region pinning."""
    return os.getenv("GHL_API_BASE_URL", _DEFAULT_BASE_URL).rstrip("/")


def _headers(access_token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {access_token}",
        "Version": _API_VERSION_HEADER,
        "Accept": "application/json",
    }


def _client() -> httpx.Client:
    return httpx.Client(timeout=_DEFAULT_TIMEOUT)


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------


def _fetch_page_with_retry(
    client: httpx.Client,
    url: str,
    *,
    headers: dict[str, str],
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """GET ``url`` with up to 3 retries on 429. Returns parsed JSON.

    Other 4xx/5xx errors raise via ``response.raise_for_status()`` —
    the caller (the Celery task) decides whether to retry the whole
    sync job or surface the error.
    """
    attempts = 0
    while True:
        response = client.get(url, headers=headers, params=params)
        if response.status_code == 429:
            attempts += 1
            if attempts > _MAX_429_RETRIES:
                response.raise_for_status()  # let caller see the 429
            retry_after = response.headers.get("Retry-After")
            try:
                wait = float(retry_after) if retry_after else _RATE_LIMIT_DEFAULT_BACKOFF
            except ValueError:
                wait = _RATE_LIMIT_DEFAULT_BACKOFF
            logger.info("ghl 429 on %s — sleeping %.1fs (attempt %d)", url, wait, attempts)
            time.sleep(wait)
            continue
        response.raise_for_status()
        return response.json()


def fetch_contacts(
    access_token: str,
    location_id: str,
    *,
    page_size: int = _DEFAULT_PAGE_SIZE,
) -> Iterator[dict[str, Any]]:
    """Yield every contact under the given GHL location.

    Pagination follows ``meta.nextPageUrl`` until exhausted. GHL's
    response shape:

        {
          "contacts": [ {...}, {...} ],
          "meta": {
            "total": 1234,
            "nextPageUrl": "https://.../contacts/?startAfterId=..."  (or null)
          }
        }

    The startAfterId cursor approach matches GHL's v2 contracts.
    """
    base = _base_url()
    initial_url = f"{base}/contacts/"
    headers = _headers(access_token)
    params: dict[str, Any] | None = {
        "locationId": location_id,
        "limit": page_size,
    }
    page_count = 0
    next_url: str | None = initial_url

    with _client() as client:
        while next_url:
            body = _fetch_page_with_retry(
                client, next_url, headers=headers, params=params
            )
            # After the first page GHL returns a fully-qualified
            # nextPageUrl that already carries locationId + limit, so
            # we stop sending params on subsequent calls to avoid
            # duplicate-parameter quirks.
            params = None

            contacts = body.get("contacts") or []
            for contact in contacts:
                if isinstance(contact, dict):
                    yield contact

            page_count += 1
            next_url = (body.get("meta") or {}).get("nextPageUrl")
            logger.debug(
                "ghl fetch_contacts: page=%d count=%d has_next=%s",
                page_count, len(contacts), bool(next_url),
            )

    logger.info("ghl fetch_contacts: drained %d pages from location=%s", page_count, location_id)
