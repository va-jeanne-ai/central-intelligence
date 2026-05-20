"""Transcript file storage on local disk.

Saves the plain-text transcript for each Call as a browsable artifact under
``backend/.tmp/transcripts/{call_id}.txt``. Served back to the UI via
``GET /api/v1/ci/calls/{call_id}/transcript.txt`` so users can download or
re-read past calls without round-tripping through the DB.

The directory lives under ``.tmp`` so it follows the project's disposable-
intermediate convention. For prod we'd swap this for Supabase Storage; the
public surface is just ``save_transcript()`` / ``get_transcript_path()``,
so that's a one-file change.
"""

from __future__ import annotations

from pathlib import Path

# Repo layout: this file is at backend/app/storage/transcripts.py,
# so backend/ is parents[2].
_BACKEND_DIR = Path(__file__).resolve().parents[2]
TRANSCRIPTS_DIR = _BACKEND_DIR / ".tmp" / "transcripts"


def _ensure_dir() -> None:
    TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)


def get_transcript_path(call_id: str) -> Path:
    """Return the on-disk path for a call's transcript file (may not exist)."""
    return TRANSCRIPTS_DIR / f"{call_id}.txt"


def save_transcript(call_id: str, text: str) -> Path:
    """Persist the transcript text. Returns the written path.

    Overwrites any existing file for the same call_id (re-runs of the
    analyzer/transcriber are expected to re-emit the canonical text).
    Empty or mock-placeholder transcripts still get written — the UI
    treats presence/absence of the file as "is there anything to read".
    """
    _ensure_dir()
    path = get_transcript_path(call_id)
    path.write_text(text or "", encoding="utf-8")
    return path
