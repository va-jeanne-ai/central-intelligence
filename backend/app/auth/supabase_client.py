"""
Supabase client factory.

Returns a configured ``supabase.Client`` instance when Supabase
credentials are present in settings, or ``None`` when running in mock
mode (i.e. ``SUPABASE_URL`` is empty or unset).

The client is constructed once at module import time and reused for the
lifetime of the process.  This avoids the overhead of re-initialising the
HTTP session on every request.
"""

import logging
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level singleton.  Initialised once; ``None`` in mock mode.
# ---------------------------------------------------------------------------
_client = None  # type: Optional[object]  # supabase.Client | None


def _build_client():
    """Attempt to build a Supabase client from settings.

    Returns the client on success, or ``None`` if Supabase is not
    configured or the ``supabase`` package is unavailable.
    """
    if not settings.supabase_url:
        logger.info(
            "SUPABASE_URL is not set — auth running in mock mode. "
            "Configure SUPABASE_URL and SUPABASE_ANON_KEY to activate real auth."
        )
        return None

    try:
        from supabase import create_client  # type: ignore[import]

        client = create_client(settings.supabase_url, settings.supabase_anon_key)
        logger.info("Supabase client initialised for project: %s", settings.supabase_url)
        return client
    except ImportError:
        logger.warning(
            "supabase package not installed — falling back to mock mode. "
            "Run `pip install supabase` to enable real auth."
        )
        return None
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to initialise Supabase client: %s", exc)
        return None


_client = _build_client()


def get_supabase_client():
    """Return the module-level Supabase client, or ``None`` in mock mode.

    This function is the single access point for the client throughout the
    application.  Callers should treat a ``None`` return value as an
    indication that mock mode is active.

    Returns
    -------
    supabase.Client | None
        A live Supabase client when credentials are configured, otherwise
        ``None``.
    """
    return _client
