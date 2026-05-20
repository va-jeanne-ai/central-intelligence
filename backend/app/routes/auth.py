"""
Authentication routes.

All endpoints live under the ``/api/v1/auth`` prefix (applied when the
router is registered in ``main.py``).

Mock mode behaviour
-------------------
When ``SUPABASE_URL`` is not configured, every endpoint returns
pre-canned responses with ``mock=True`` (or an equivalent message).
No real credentials are validated and no Supabase API calls are made.
This allows the frontend to exercise auth flows end-to-end before a
Supabase project exists.

Real mode behaviour
-------------------
When Supabase credentials are present the router delegates to the
Supabase Auth API for every operation.  Errors from Supabase are caught
and translated into appropriate HTTP status codes.
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth.dependencies import CurrentUser, get_current_user
from app.auth.supabase_client import get_supabase_client
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    PasswordResetRequest,
    SignupRequest,
    TokenRefreshRequest,
    UserProfile,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

# ---------------------------------------------------------------------------
# Shared mock fixtures
# ---------------------------------------------------------------------------
_MOCK_ACCESS_TOKEN = "mock-access-token"
_MOCK_REFRESH_TOKEN = "mock-refresh-token"
_MOCK_USER = UserProfile(
    id="mock-user-id",
    email="admin@centralintelligence.ai",
    name="Mock Admin",
    role="admin",
)


def _mock_login_response() -> LoginResponse:
    """Return a synthetic LoginResponse for mock mode."""
    return LoginResponse(
        access_token=_MOCK_ACCESS_TOKEN,
        refresh_token=_MOCK_REFRESH_TOKEN,
        user=_MOCK_USER,
        mock=True,
    )


def _supabase_error_to_http(exc: Exception) -> HTTPException:
    """Convert a Supabase exception into a FastAPI HTTPException.

    Attempts to surface the original Supabase error message so clients
    receive actionable feedback.
    """
    message = str(exc)
    # Supabase raises ``AuthApiError`` with a ``status`` attribute when
    # the upstream HTTP call fails.
    http_status = getattr(exc, "status", None)
    if isinstance(http_status, int) and 400 <= http_status < 600:
        return HTTPException(status_code=http_status, detail=message)
    # Default to 400 for auth-related failures (invalid password, etc.)
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)


# ---------------------------------------------------------------------------
# POST /login
# ---------------------------------------------------------------------------


@router.post(
    "/login",
    response_model=LoginResponse,
    summary="Sign in with email and password",
    description=(
        "Authenticates a user with email and password credentials. "
        "Returns a JWT access token, a refresh token, and the resolved "
        "user profile.  In mock mode the ``mock`` flag is ``true`` and "
        "the tokens are synthetic."
    ),
)
async def login(body: LoginRequest) -> LoginResponse:
    """Authenticate a user and return session tokens."""
    supabase = get_supabase_client()

    if supabase is None:
        logger.debug("Mock login for %s", body.email)
        return _mock_login_response()

    try:
        response = supabase.auth.sign_in_with_password(
            {"email": body.email, "password": body.password}
        )
        session = response.session
        user = response.user

        if session is None or user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )

        role = (user.user_metadata or {}).get("role", "member")
        name = (user.user_metadata or {}).get("name", "")

        return LoginResponse(
            access_token=session.access_token,
            refresh_token=session.refresh_token,
            user=UserProfile(
                id=str(user.id),
                email=user.email or "",
                name=name,
                role=role,
            ),
            mock=False,
        )
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.warning("Login failed for %s: %s", body.email, exc)
        raise _supabase_error_to_http(exc) from exc


# ---------------------------------------------------------------------------
# POST /signup
# ---------------------------------------------------------------------------


@router.post(
    "/signup",
    response_model=LoginResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new account",
    description=(
        "Creates a new user account.  On success returns the same "
        "token envelope as ``/login``.  Supabase may require email "
        "confirmation depending on project settings — in that case the "
        "access token will be empty and the client should prompt the "
        "user to verify their email."
    ),
)
async def signup(body: SignupRequest) -> LoginResponse:
    """Create a new user account."""
    supabase = get_supabase_client()

    if supabase is None:
        logger.debug("Mock signup for %s", body.email)
        mock_user = UserProfile(
            id="mock-user-id",
            email=body.email,
            name=body.name,
            role="member",
        )
        return LoginResponse(
            access_token=_MOCK_ACCESS_TOKEN,
            refresh_token=_MOCK_REFRESH_TOKEN,
            user=mock_user,
            mock=True,
        )

    try:
        options: dict[str, Any] = {}
        if body.name:
            options["data"] = {"name": body.name}

        response = supabase.auth.sign_up(
            {"email": body.email, "password": body.password, "options": options}
        )
        session = response.session
        user = response.user

        # Session is None when email confirmation is required.
        access_token = session.access_token if session else ""
        refresh_token = session.refresh_token if session else ""
        role = (user.user_metadata or {}).get("role", "member") if user else "member"
        name = (user.user_metadata or {}).get("name", body.name) if user else body.name
        user_id = str(user.id) if user else ""
        user_email = user.email if user else body.email

        return LoginResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            user=UserProfile(
                id=user_id,
                email=user_email or "",
                name=name,
                role=role,
            ),
            mock=False,
        )
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.warning("Signup failed for %s: %s", body.email, exc)
        raise _supabase_error_to_http(exc) from exc


# ---------------------------------------------------------------------------
# POST /refresh
# ---------------------------------------------------------------------------


@router.post(
    "/refresh",
    response_model=LoginResponse,
    summary="Refresh an access token",
    description=(
        "Exchanges a valid refresh token for a new access/refresh token "
        "pair.  The old refresh token is invalidated."
    ),
)
async def refresh_token(body: TokenRefreshRequest) -> LoginResponse:
    """Exchange a refresh token for a new session."""
    supabase = get_supabase_client()

    if supabase is None:
        logger.debug("Mock token refresh")
        return _mock_login_response()

    try:
        response = supabase.auth.refresh_session(body.refresh_token)
        session = response.session
        user = response.user

        if session is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token",
            )

        role = (user.user_metadata or {}).get("role", "member") if user else "member"
        name = (user.user_metadata or {}).get("name", "") if user else ""

        return LoginResponse(
            access_token=session.access_token,
            refresh_token=session.refresh_token,
            user=UserProfile(
                id=str(user.id) if user else "",
                email=user.email or "" if user else "",
                name=name,
                role=role,
            ),
            mock=False,
        )
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.warning("Token refresh failed: %s", exc)
        raise _supabase_error_to_http(exc) from exc


# ---------------------------------------------------------------------------
# POST /logout
# ---------------------------------------------------------------------------


@router.post(
    "/logout",
    summary="Sign out the current session",
    description=(
        "Invalidates the current session on the Supabase side.  Clients "
        "should also discard their locally stored tokens regardless of "
        "the HTTP response status."
    ),
)
async def logout(
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, str]:
    """Invalidate the current user session."""
    supabase = get_supabase_client()

    if supabase is None:
        logger.debug("Mock logout for user %s", current_user.id)
        return {"message": "Logged out successfully (mock mode)"}

    try:
        supabase.auth.sign_out()
        logger.info("User %s logged out", current_user.id)
        return {"message": "Logged out successfully"}
    except Exception as exc:  # noqa: BLE001
        # Sign-out failures are non-critical — the client should clear
        # tokens locally regardless, so we log and return success.
        logger.warning("Supabase sign-out raised an error (ignored): %s", exc)
        return {"message": "Logged out successfully"}


# ---------------------------------------------------------------------------
# POST /password-reset
# ---------------------------------------------------------------------------


@router.post(
    "/password-reset",
    summary="Request a password-reset email",
    description=(
        "Sends a password-reset link to the provided email address.  "
        "Always returns HTTP 200 to prevent user-enumeration attacks — "
        "the response does not indicate whether the address is registered."
    ),
)
async def password_reset(body: PasswordResetRequest) -> dict[str, str]:
    """Trigger a password-reset email for the given address."""
    supabase = get_supabase_client()

    if supabase is None:
        logger.debug("Mock password reset requested for %s", body.email)
        return {
            "message": (
                "If that email address is registered you will receive a "
                "password-reset link shortly. (mock mode)"
            )
        }

    try:
        supabase.auth.reset_password_email(body.email)
        logger.info("Password reset email requested for %s", body.email)
    except Exception as exc:  # noqa: BLE001
        # Intentionally swallow errors to prevent user-enumeration.
        logger.warning(
            "Password reset email could not be sent to %s: %s", body.email, exc
        )

    return {
        "message": (
            "If that email address is registered you will receive a "
            "password-reset link shortly."
        )
    }


# ---------------------------------------------------------------------------
# GET /me
# ---------------------------------------------------------------------------


@router.get(
    "/me",
    response_model=UserProfile,
    summary="Return the authenticated user's profile",
    description=(
        "Protected endpoint — requires a valid Bearer token.  "
        "Returns the profile of the currently authenticated user.  "
        "In mock mode returns the synthetic admin profile."
    ),
)
async def me(
    current_user: CurrentUser = Depends(get_current_user),
) -> UserProfile:
    """Return the profile of the currently authenticated user."""
    return UserProfile(
        id=current_user.id,
        email=current_user.email,
        name="",  # Name is not stored on CurrentUser; extend if needed.
        role=current_user.role,
    )
