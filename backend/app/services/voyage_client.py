"""Thin HTTP wrapper around Voyage AI's embeddings endpoint.

One public function — :func:`embed_batch` — POSTs a list of text
chunks to ``https://api.voyageai.com/v1/embeddings`` and returns the
list of 1024-d float vectors plus the API's reported token usage.

``input_type`` distinguishes ingest from retrieval:

  * ``"document"`` — when embedding source content for storage.
  * ``"query"``    — when embedding a user query before the
    ``ORDER BY embedding <=> :q`` lookup in
    ``search_knowledge_base``.

Mismatching the input_type degrades retrieval quality but doesn't
break it; Voyage's docs recommend always specifying.

Rate-limit handling: 429s retry up to 5 times with exponential
backoff (5s, 10s, 20s, 40s, 60s capped). If all retries 429 the
caller gets a :class:`VoyageRateLimited` (distinct from the generic
:class:`VoyageError`) so the embed worker can leave the row in the
queue without burning a retry-attempt budget. Other 4xx/5xx surface
as :class:`VoyageError`.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


VOYAGE_EMBEDDINGS_URL = "https://api.voyageai.com/v1/embeddings"
VOYAGE_MODEL = "voyage-3"
VOYAGE_DIMS = 1024
_DEFAULT_TIMEOUT = 60.0

# Exponential backoff schedule for 429s. Each entry is the sleep in
# seconds before that attempt. Total worst case: 5+10+20+40+60 = 135s.
_RATE_LIMIT_BACKOFF = [5.0, 10.0, 20.0, 40.0, 60.0]


class VoyageError(RuntimeError):
    """Raised when the Voyage API returns a non-retryable error."""


class VoyageRateLimited(VoyageError):
    """Raised when 429s persist after exhausting the backoff schedule.

    The embed worker treats this differently from :class:`VoyageError`:
    the row stays in the queue with its ``attempts`` counter unchanged,
    so a temporary rate limit doesn't three-strike a perfectly valid
    source row out of the queue.
    """


def embed_batch(
    texts: list[str],
    *,
    input_type: str = "document",
) -> tuple[list[list[float]], int]:
    """Embed a batch of texts. Returns (vectors, tokens_used).

    Each vector is a 1024-element list of floats; ``vectors[i]``
    corresponds to ``texts[i]``. ``tokens_used`` comes from the API
    response's ``usage.total_tokens`` — the embed worker uses it to
    decrement the daily budget.
    """
    if not texts:
        return [], 0
    if not settings.voyage_api_key:
        raise VoyageError(
            "VOYAGE_API_KEY is not configured. Set it in backend/.env.",
        )
    if input_type not in ("document", "query"):
        raise ValueError("input_type must be 'document' or 'query'")

    body: dict[str, Any] = {
        "input": texts,
        "model": VOYAGE_MODEL,
        "input_type": input_type,
    }
    headers = {
        "Authorization": f"Bearer {settings.voyage_api_key}",
        "Content-Type": "application/json",
    }

    max_attempts = len(_RATE_LIMIT_BACKOFF) + 1  # initial try + N retries
    for attempt in range(1, max_attempts + 1):
        with httpx.Client(timeout=_DEFAULT_TIMEOUT) as client:
            response = client.post(VOYAGE_EMBEDDINGS_URL, json=body, headers=headers)

        if response.status_code == 429:
            if attempt >= max_attempts:
                # Out of retries — let the worker re-queue without
                # bumping attempts.
                raise VoyageRateLimited(
                    f"Voyage 429 after {attempt} attempts: "
                    f"{response.text[:200]}"
                )
            # Honor Retry-After if present, else fall through the
            # exponential backoff schedule.
            header_retry = _parse_retry_after(response.headers.get("Retry-After"))
            backoff = _RATE_LIMIT_BACKOFF[attempt - 1]
            sleep_for = max(header_retry, backoff)
            logger.warning(
                "voyage: 429 (attempt %d/%d) — sleeping %.1fs",
                attempt, max_attempts, sleep_for,
            )
            time.sleep(sleep_for)
            continue

        if response.status_code >= 400:
            raise VoyageError(
                f"Voyage API {response.status_code}: {response.text[:300]}",
            )

        payload = response.json()
        data = payload.get("data") or []
        vectors = [row.get("embedding") or [] for row in data]
        tokens = int((payload.get("usage") or {}).get("total_tokens") or 0)

        if len(vectors) != len(texts):
            raise VoyageError(
                f"Voyage returned {len(vectors)} vectors for {len(texts)} inputs",
            )
        return vectors, tokens

    # Unreachable — the loop either returns or raises.
    raise VoyageError("voyage: exhausted retry loop unexpectedly")


def _parse_retry_after(header: str | None) -> float:
    """Voyage's Retry-After is a number of seconds. Default to 0 so the
    backoff schedule controls the wait."""
    if not header:
        return 0.0
    try:
        return max(0.0, float(header))
    except (TypeError, ValueError):
        return 0.0
