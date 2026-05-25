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
break it; Voyage's docs recommend always specifying. On 429 the
caller sleeps according to the response's ``Retry-After`` header
(seconds). Other 5xx responses surface as exceptions so the embed
worker can record ``last_error`` and retry on the next tick.
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


class VoyageError(RuntimeError):
    """Raised when the Voyage API returns a non-retryable error."""


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

    On 429 we honor ``Retry-After`` once and retry. If we 429 again,
    we raise — the worker will reschedule the row on the next tick.
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

    attempts = 0
    while True:
        attempts += 1
        with httpx.Client(timeout=_DEFAULT_TIMEOUT) as client:
            response = client.post(VOYAGE_EMBEDDINGS_URL, json=body, headers=headers)

        if response.status_code == 429 and attempts == 1:
            retry_after = _parse_retry_after(response.headers.get("Retry-After"))
            logger.warning(
                "voyage: rate-limited, sleeping %.1fs before retry", retry_after,
            )
            time.sleep(retry_after)
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


def _parse_retry_after(header: str | None) -> float:
    """Voyage's Retry-After is a number of seconds. Default to 5s."""
    if not header:
        return 5.0
    try:
        return max(0.5, float(header))
    except (TypeError, ValueError):
        return 5.0
