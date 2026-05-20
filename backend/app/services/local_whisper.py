"""Local Whisper transcription via faster-whisper (CTranslate2 backend).

Replaces the OpenAI Whisper API. Free, offline, no quota. First call lazy-
loads the ``small`` model (~244 MB) from HuggingFace and caches it process-
wide so subsequent calls reuse the same in-memory model.

Public surface:
  - ``transcribe_file(path) -> {"transcript": str, "duration_seconds": int,
    "language": str}`` — matches the prior OpenAI response shape so callers
    don't have to change.

Notes:
  - Threadsafe enough for our use: model load is wrapped in a lock; each
    transcribe call holds the GIL while CTranslate2 runs native code, which
    is fine for one-call-at-a-time uvicorn/Celery workloads.
  - For Apple Silicon, default device "auto" picks CPU (CTranslate2 doesn't
    have Metal; CPU is still fast — ~real-time on small).
"""

from __future__ import annotations

import logging
import os
import threading
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_MODEL_SIZE = "small"
_DEVICE = "auto"
_COMPUTE_TYPE = "int8"  # int8 keeps memory low; quality drop is minimal at small/medium

# Cache the model under the project's .tmp/ so we don't fight macOS perms on
# ~/.cache (which is sometimes root-owned on shared/managed Macs). Setting
# HF_HOME redirects every layer of the huggingface_hub download stack
# (including the xet downloader) before its first import.
_BACKEND_DIR = Path(__file__).resolve().parents[2]
_MODEL_CACHE_DIR = _BACKEND_DIR / ".tmp" / "whisper-models"
_HF_HOME = _BACKEND_DIR / ".tmp" / "hf-home"
os.environ.setdefault("HF_HOME", str(_HF_HOME))
os.environ.setdefault("XDG_CACHE_HOME", str(_BACKEND_DIR / ".tmp" / "xdg-cache"))

_model: Any | None = None
_model_lock = threading.Lock()


def _get_model() -> Any:
    """Lazily load and cache the WhisperModel."""
    global _model
    if _model is not None:
        return _model
    with _model_lock:
        if _model is not None:
            return _model
        from faster_whisper import WhisperModel  # lazy — heavy import
        _MODEL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        logger.info(
            "Loading faster-whisper model — size=%s device=%s compute=%s cache=%s",
            _MODEL_SIZE, _DEVICE, _COMPUTE_TYPE, _MODEL_CACHE_DIR,
        )
        _model = WhisperModel(
            _MODEL_SIZE,
            device=_DEVICE,
            compute_type=_COMPUTE_TYPE,
            download_root=str(_MODEL_CACHE_DIR),
        )
        logger.info("faster-whisper model loaded")
        return _model


def transcribe_file(path: Path) -> dict:
    """Transcribe a local audio file. Returns ``{transcript, duration_seconds, language}``."""
    model = _get_model()
    # vad_filter trims long silences — speeds up transcription on real calls
    # without hurting accuracy. beam_size=5 is the library default.
    segments, info = model.transcribe(str(path), vad_filter=True, beam_size=5)
    text = " ".join(seg.text.strip() for seg in segments).strip()
    return {
        "transcript": text,
        "duration_seconds": int(getattr(info, "duration", 0) or 0),
        "language": getattr(info, "language", "en") or "en",
    }
