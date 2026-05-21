"""
Symmetric encryption for third-party integration credentials.

Used by the ``/api/v1/integrations`` routes and the integration-aware
service clients (e.g. ``mailchimp_client``) so API keys live encrypted
at rest in the ``integrations`` table.

Backed by Fernet (AES-128-CBC + HMAC-SHA256) from the ``cryptography``
package. The master key comes from ``settings.integrations_encryption_key``;
in debug mode an empty key triggers a one-shot dev key with a loud warning
so local boot doesn't fail before the operator generates a real key.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from app.config import settings

logger = logging.getLogger(__name__)

# Project-local sentinel for the dev key. Persists across uvicorn reloads so
# data encrypted in dev doesn't vanish on every restart. Mirrors the pattern
# used for the whisper model cache (backend/.tmp/whisper-models/).
_BACKEND_DIR = Path(__file__).resolve().parents[2]
_DEV_KEY_FILE = _BACKEND_DIR / ".tmp" / "integrations.dev.key"

_fernet: Fernet | None = None
_lock = threading.Lock()
_dev_key_warned = False


def _load_or_create_dev_key() -> bytes:
    """Return a stable dev-only Fernet key, persisted to .tmp/ so it
    survives uvicorn reloads. The dev key is NEVER appropriate for prod;
    operators must set INTEGRATIONS_ENCRYPTION_KEY in .env."""
    try:
        if _DEV_KEY_FILE.exists():
            return _DEV_KEY_FILE.read_bytes().strip()
        _DEV_KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
        key = Fernet.generate_key()
        _DEV_KEY_FILE.write_bytes(key)
        return key
    except OSError as exc:
        # Filesystem unavailable — fall back to in-process key for this run.
        logger.warning("Failed to persist dev key to %s: %s", _DEV_KEY_FILE, exc)
        return Fernet.generate_key()


def _get_fernet() -> Fernet:
    """Return a process-wide Fernet, lazily initialised.

    Resolution order:

    1. ``settings.integrations_encryption_key`` set → use it (the production path).
    2. Empty key → load or create a per-project dev key persisted at
       ``backend/.tmp/integrations.dev.key``. This keeps the local dev
       experience friction-free without losing data across uvicorn reloads.
       A one-time WARNING is logged so operators know to set the real env
       var before going to prod.

    The previous behaviour raised ``RuntimeError`` when the env var was
    unset and ``debug=False``. That made every Save break in production-
    like local setups (``debug`` defaults to False) before the operator had
    a chance to generate a key. The persisted dev key sidesteps that
    silent footgun.
    """
    global _fernet, _dev_key_warned
    if _fernet is not None:
        return _fernet
    with _lock:
        if _fernet is not None:
            return _fernet
        key_str = settings.integrations_encryption_key.strip()
        if key_str:
            _fernet = Fernet(key_str.encode())
            return _fernet

        # Dev-key fallback path.
        if not _dev_key_warned:
            logger.warning(
                "INTEGRATIONS_ENCRYPTION_KEY not set — using project-local dev key "
                "at %s. NOT FOR PRODUCTION: set INTEGRATIONS_ENCRYPTION_KEY in .env "
                "before deploying.",
                _DEV_KEY_FILE,
            )
            _dev_key_warned = True
        _fernet = Fernet(_load_or_create_dev_key())
        return _fernet


def encrypt(plaintext: str) -> str:
    """Return a base64-urlsafe Fernet ciphertext for ``plaintext``."""
    return _get_fernet().encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt(ciphertext: str) -> str:
    """Inverse of ``encrypt``. Raises ``ValueError`` on bad token / key mismatch."""
    try:
        return _get_fernet().decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError(
            "Cannot decrypt integration credential — token invalid or master "
            "key changed since encryption."
        ) from exc


def mask(plaintext: str, *, keep: int = 4) -> str:
    """Return a display-safe rendering of a secret: ``********xxxx``.

    Empty or short strings return ``********`` to avoid leaking length-based
    fingerprints for very short keys.
    """
    if not plaintext or len(plaintext) <= keep:
        return "********"
    return "********" + plaintext[-keep:]
