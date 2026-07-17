"""
AuthMiddleware — request-level authentication gate.

This middleware sits immediately after CORS in the middleware stack and
enforces Bearer-token authentication on every HTTP request that is not in
the exempt path list.

Exempt paths (no auth required)
--------------------------------
- /api/v1/auth/*      — login, signup, token refresh
- /api/v1/health      — liveness probe
- /docs               — Swagger UI
- /redoc              — ReDoc UI
- /openapi.json       — OpenAPI schema
- WebSocket upgrades  — auth handled per-connection via query param ?token=

Mock / unconfigured mode
-------------------------
When ``settings.supabase_url`` is empty or ``settings.mock_mode`` is True,
every request passes through without any token inspection.  This allows
fully functional local development with zero Supabase setup.

Real mode
----------
Expects ``Authorization: Bearer <jwt>`` on every non-exempt request.
The JWT is verified locally with ``python-jose``. Two signing schemes are
supported:

* Asymmetric (Supabase default since 2024): ES256 / RS256 tokens are
  verified with the matching public key from the project's JWKS endpoint
  at ``{SUPABASE_URL}/auth/v1/.well-known/jwks.json``. Keys are cached by
  ``kid`` and refreshed hourly or on unknown-kid miss.
* Symmetric (legacy): HS256 tokens are verified with
  ``settings.supabase_jwt_secret``.

A successful decode attaches a :class:`~app.auth.dependencies.CurrentUser`
to ``request.state.user`` so that downstream route handlers can read it
without issuing a second network call.

Error responses use the standard Central Intelligence error envelope::

    {
        "error": {
            "code": "UNAUTHORIZED",
            "message": "...",
            "timestamp": "<ISO-8601>",
            "requestId": "<uuid>"
        }
    }
"""

import json
import logging
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx
from jose import JWTError, jwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from app.auth.dependencies import CurrentUser
from app.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths that skip authentication entirely.
# ---------------------------------------------------------------------------
_EXEMPT_PREFIXES: tuple[str, ...] = (
    "/api/v1/auth/",
    # Inbound webhooks (GHL, Stripe, etc.) — third parties have no JWT.
    # The route handler performs its own token check via secrets.compare_digest
    # against the per-integration secret stored in the integrations row.
    "/api/v1/webhooks/",
    # OAuth callbacks — Google hits these directly with no JWT. The
    # callback validates the `state` parameter (which encodes the
    # initiating user_id, signed by the integrations encryption key)
    # to know who's connecting.
    "/api/v1/integrations/google_workspace/oauth/callback",
    "/docs",
    "/redoc",
    "/openapi.json",
)
# /config/branding is public: the login page renders the white-label
# app name/logo before any user is authenticated. It only ever exposes the
# branding subset of instance_profile — never prompts/terminology/benchmarks.
_EXEMPT_EXACT: frozenset[str] = frozenset({"/api/v1/health", "/api/v1/config/branding"})

# Supabase JWTs since 2024 use asymmetric ES256 (signed with project key,
# verified with public key from JWKS).  Older / legacy Supabase projects
# still use HS256 with the shared JWT secret.  We support both:
#   - asymmetric: ES256 / RS256 → fetch the matching key from JWKS by `kid`
#   - symmetric:  HS256 → verify with `settings.supabase_jwt_secret`
# python-jose's `algorithms=` arg also acts as an allow-list, so listing
# all three is safe; the alg in the token header decides which path runs.
_JWT_ALGORITHMS = ["ES256", "RS256", "HS256"]

# ---------------------------------------------------------------------------
# JWKS cache — fetched once, refreshed when an unknown `kid` is seen.
# ---------------------------------------------------------------------------
_JWKS_CACHE: dict[str, Any] = {"keys_by_kid": {}, "fetched_at": 0.0}
_JWKS_LOCK = threading.Lock()
_JWKS_TTL_SECONDS = 60 * 60  # refresh hourly; also force-refresh on unknown kid
_JWKS_TIMEOUT_SECONDS = 5.0


def _jwks_url() -> str:
    """The Supabase JWKS endpoint for the project named in settings."""
    base = settings.supabase_url.rstrip("/")
    return f"{base}/auth/v1/.well-known/jwks.json"


def _fetch_jwks() -> dict[str, dict]:
    """Fetch and parse JWKS, returning a dict keyed by `kid`. Best-effort."""
    if not settings.supabase_url or not settings.supabase_anon_key:
        return {}
    try:
        resp = httpx.get(
            _jwks_url(),
            headers={"apikey": settings.supabase_anon_key},
            timeout=_JWKS_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        payload = resp.json()
    except Exception as exc:  # noqa: BLE001 — network call, treat all failures uniformly
        logger.warning("AuthMiddleware: JWKS fetch failed: %s", exc)
        return {}

    keys_by_kid: dict[str, dict] = {}
    for key in payload.get("keys", []):
        kid = key.get("kid")
        if kid:
            keys_by_kid[kid] = key
    return keys_by_kid


def _get_jwks_key(kid: str) -> dict | None:
    """Return the JWK for the given `kid`, fetching/refreshing as needed."""
    with _JWKS_LOCK:
        cached = _JWKS_CACHE.get("keys_by_kid", {})
        fetched_at = _JWKS_CACHE.get("fetched_at", 0.0)
        # Hit: cached key exists and is fresh enough.
        if kid in cached and time.time() - fetched_at < _JWKS_TTL_SECONDS:
            return cached[kid]
        # Miss or stale: refresh.
        fresh = _fetch_jwks()
        if fresh:
            _JWKS_CACHE["keys_by_kid"] = fresh
            _JWKS_CACHE["fetched_at"] = time.time()
        return _JWKS_CACHE["keys_by_kid"].get(kid)


def verify_supabase_jwt(token: str) -> dict | None:
    """Verify a Supabase JWT (ES256/RS256 via JWKS, or HS256 via shared secret).

    Returns the decoded claims dict on success, or None on failure.

    Used by both the middleware and the WebSocket auth paths, which can't go
    through the middleware (they bypass HTTP request handling).
    """
    try:
        unverified_header = jwt.get_unverified_header(token)
    except (JWTError, Exception):  # noqa: BLE001
        return None

    alg = unverified_header.get("alg", "")
    kid = unverified_header.get("kid", "")
    verification_key: Any
    if alg in ("ES256", "RS256"):
        jwk = _get_jwks_key(kid) if kid else None
        if jwk is None:
            return None
        verification_key = jwk
    else:
        verification_key = settings.supabase_jwt_secret

    try:
        return jwt.decode(
            token,
            verification_key,
            algorithms=_JWT_ALGORITHMS,
            options={"verify_aud": False},
        )
    except (JWTError, Exception):  # noqa: BLE001
        return None


def _build_error_response(message: str, request_id: str) -> JSONResponse:
    """Return a 401 JSON response using the standard error envelope."""
    body = {
        "error": {
            "code": "UNAUTHORIZED",
            "message": message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "requestId": request_id,
        }
    }
    return JSONResponse(status_code=401, content=body)


def _is_websocket_upgrade(request: Request) -> bool:
    """Return True when the request is a WebSocket upgrade handshake."""
    upgrade = request.headers.get("upgrade", "").lower()
    connection = request.headers.get("connection", "").lower()
    return upgrade == "websocket" and "upgrade" in connection


def _is_exempt(request: Request) -> bool:
    """Return True when the path does not require Bearer-token auth."""
    path = request.url.path

    if path in _EXEMPT_EXACT:
        return True

    for prefix in _EXEMPT_PREFIXES:
        if path.startswith(prefix):
            return True

    return False


class AuthMiddleware(BaseHTTPMiddleware):
    """Starlette middleware that validates Bearer JWTs on protected routes.

    Parameters
    ----------
    app:
        The inner ASGI application passed by the Starlette/FastAPI
        middleware stack machinery.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[override]
        # ----------------------------------------------------------------
        # Determine the request ID early — used in logs and error bodies.
        # ----------------------------------------------------------------
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())

        # ----------------------------------------------------------------
        # Mock / unconfigured mode — pass every request through as-is.
        # ----------------------------------------------------------------
        mock_mode = (not settings.supabase_url) or settings.mock_mode
        if mock_mode:
            logger.debug(
                "AuthMiddleware: mock mode active, skipping auth (request_id=%s)",
                request_id,
            )
            return await call_next(request)

        # ----------------------------------------------------------------
        # CORS preflight — browsers send OPTIONS with no auth header.
        # Must pass through so the CORS middleware can respond with the
        # appropriate Access-Control-Allow-* headers.
        # ----------------------------------------------------------------
        if request.method == "OPTIONS":
            return await call_next(request)

        # ----------------------------------------------------------------
        # WebSocket upgrades — auth is handled inside the WS endpoint via
        # the ?token= query parameter.  Pass through here.
        # ----------------------------------------------------------------
        if _is_websocket_upgrade(request):
            logger.debug(
                "AuthMiddleware: WebSocket upgrade, deferring auth to endpoint "
                "(request_id=%s path=%s)",
                request_id,
                request.url.path,
            )
            return await call_next(request)

        # ----------------------------------------------------------------
        # Exempt paths — no auth required.
        # ----------------------------------------------------------------
        if _is_exempt(request):
            logger.debug(
                "AuthMiddleware: exempt path %s (request_id=%s)",
                request.url.path,
                request_id,
            )
            return await call_next(request)

        # ----------------------------------------------------------------
        # Real mode — extract and verify the Bearer token.
        # ----------------------------------------------------------------
        authorization = request.headers.get("authorization", "")
        parts = authorization.split(" ", 1)
        if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
            logger.warning(
                "AuthMiddleware: missing/malformed Authorization header "
                "(request_id=%s path=%s)",
                request_id,
                request.url.path,
            )
            return _build_error_response(
                "Missing or invalid authentication token", request_id
            )

        token = parts[1].strip()

        claims = verify_supabase_jwt(token)
        if claims is None:
            logger.warning(
                "AuthMiddleware: JWT verification failed (request_id=%s path=%s)",
                request_id,
                request.url.path,
            )
            return _build_error_response(
                "Missing or invalid authentication token", request_id
            )

        # Attach a CurrentUser to request.state so route handlers can
        # read the principal without an additional Supabase network call.
        user_id = claims.get("sub", "")
        email = claims.get("email", "")
        role = (
            claims.get("user_metadata", {}).get("role")
            or claims.get("app_metadata", {}).get("role")
            or "member"
        )
        request.state.user = CurrentUser(id=user_id, email=email, role=role)

        logger.debug(
            "AuthMiddleware: authenticated user_id=%s role=%s "
            "(request_id=%s path=%s)",
            user_id,
            role,
            request_id,
            request.url.path,
        )

        return await call_next(request)
