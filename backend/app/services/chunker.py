"""Token-aware text chunking for the embed pipeline.

``chunk_text`` splits a body of text into overlapping windows of at
most ``max_tokens`` tokens, with ``overlap_tokens`` of overlap between
adjacent chunks. We use ``tiktoken`` with the ``cl100k_base`` encoding
— Voyage doesn't expose a public tokenizer, but cl100k tracks closely
enough for budgeting purposes (the actual token spend reported by the
API is what we charge the daily cap against).

Sentence boundaries are preferred when they fit inside the budget; we
fall back to a hard token-window split on inputs without sentence
punctuation (e.g. CSV-exported spreadsheets).
"""

from __future__ import annotations

import re

import tiktoken

_ENCODER = tiktoken.get_encoding("cl100k_base")

# Simple sentence splitter — splits on `.`, `!`, `?` followed by whitespace,
# plus newline-newline (paragraph break). Good enough for English prose +
# Google Doc exports.
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+|\n{2,}")


def _tokens(text: str) -> list[int]:
    return _ENCODER.encode(text)


def _detokens(tokens: list[int]) -> str:
    return _ENCODER.decode(tokens)


def chunk_text(
    text: str,
    *,
    max_tokens: int = 1024,
    overlap_tokens: int = 200,
) -> list[str]:
    """Return ``text`` split into chunks of at most ``max_tokens`` tokens.

    Empty / whitespace-only inputs return ``[]`` (no embeddings to do).
    """
    if not text or not text.strip():
        return []
    if max_tokens <= 0:
        return []
    if overlap_tokens < 0 or overlap_tokens >= max_tokens:
        overlap_tokens = max(0, max_tokens // 5)

    sentences = _split_into_sentences(text)
    if not sentences:
        return _hard_window_chunks(text, max_tokens, overlap_tokens)

    chunks: list[str] = []
    current_tokens: list[int] = []

    for sentence in sentences:
        s_tokens = _tokens(sentence)
        # A single sentence larger than the budget — split it on raw
        # token boundaries rather than dropping it.
        if len(s_tokens) > max_tokens:
            if current_tokens:
                chunks.append(_detokens(current_tokens).strip())
                current_tokens = []
            chunks.extend(_hard_window_chunks(sentence, max_tokens, overlap_tokens))
            continue

        if len(current_tokens) + len(s_tokens) <= max_tokens:
            current_tokens.extend(s_tokens)
        else:
            chunks.append(_detokens(current_tokens).strip())
            # Carry overlap tail into the next chunk for context continuity.
            tail = current_tokens[-overlap_tokens:] if overlap_tokens else []
            current_tokens = tail + s_tokens

    if current_tokens:
        chunks.append(_detokens(current_tokens).strip())

    return [c for c in chunks if c]


def _split_into_sentences(text: str) -> list[str]:
    """Split text into sentences keeping the punctuation attached."""
    raw = _SENTENCE_RE.split(text)
    return [s.strip() for s in raw if s and s.strip()]


def _hard_window_chunks(
    text: str, max_tokens: int, overlap_tokens: int,
) -> list[str]:
    """Token-boundary sliding window — used when sentence splitting fails."""
    tokens = _tokens(text)
    if not tokens:
        return []
    out: list[str] = []
    step = max(1, max_tokens - overlap_tokens)
    for start in range(0, len(tokens), step):
        window = tokens[start:start + max_tokens]
        if not window:
            break
        out.append(_detokens(window).strip())
        if start + max_tokens >= len(tokens):
            break
    return [c for c in out if c]
