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

from cryptography.fernet import Fernet, InvalidToken

from app.config import settings

logger = logging.getLogger(__name__)

_fernet: Fernet | None = None
_lock = threading.Lock()
_dev_key_warned = False


def _get_fernet() -> Fernet:
    """Return a process-wide Fernet, lazily initialised.

    Behaviour by environment:

    - ``integrations_encryption_key`` set → use it (preferred).
    - empty key + ``settings.debug=True`` → generate a stable in-process dev
      key and emit a one-time WARNING. Anything encrypted with this key
      cannot be decrypted after a process restart (the key is regenerated).
    - empty key + ``settings.debug=False`` → raise ``RuntimeError`` so prod
      doesn't silently lose credentials on restart.
    """
    global _fernet, _dev_key_warned
    if _fernet is not None:
        return _fernet
    with _lock:
        if _fernet is not None:
            return _fernet
        key = settings.integrations_encryption_key.strip()
        if not key:
            if not settings.debug:
                raise RuntimeError(
                    "INTEGRATIONS_ENCRYPTION_KEY is not set. Generate one with: "
                    "python -c 'from cryptography.fernet import Fernet; "
                    "print(Fernet.generate_key().decode())'"
                )
            if not _dev_key_warned:
                logger.warning(
                    "INTEGRATIONS_ENCRYPTION_KEY not set — using an ephemeral dev key. "
                    "Anything encrypted now will be UNREADABLE after a process restart."
                )
                _dev_key_warned = True
            _fernet = Fernet(Fernet.generate_key())
            return _fernet
        _fernet = Fernet(key.encode())
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
