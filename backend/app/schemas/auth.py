"""
Pydantic schemas for authentication request/response contracts.

These models define the public API surface for all auth endpoints.
Keep them stable across minor releases; version-bump when breaking
changes are required.

Mock mode note
--------------
``LoginResponse`` and related response models carry a ``mock`` flag that
is set to ``True`` when the server is running without a live Supabase
project.  Frontend code can inspect this flag to display a development
banner or skip token persistence.
"""

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    """Credentials submitted to ``POST /api/v1/auth/login``."""

    email: EmailStr = Field(..., description="User's email address.")
    password: str = Field(..., min_length=1, description="User's password.")


class SignupRequest(BaseModel):
    """Registration payload submitted to ``POST /api/v1/auth/signup``."""

    email: EmailStr = Field(..., description="Desired email address.")
    password: str = Field(
        ...,
        min_length=8,
        description="Password — must be at least 8 characters.",
    )
    name: str = Field(default="", description="Display name (optional).")


class UserProfile(BaseModel):
    """Portable user representation embedded in auth responses."""

    id: str = Field(..., description="Supabase user UUID.")
    email: str = Field(..., description="User's email address.")
    name: str = Field(default="", description="Display name.")
    role: str = Field(default="member", description="Application-level role.")


class LoginResponse(BaseModel):
    """Response body for successful login and token-refresh operations."""

    access_token: str = Field(..., description="JWT access token.")
    refresh_token: str = Field(..., description="Opaque refresh token.")
    user: UserProfile = Field(..., description="Resolved user profile.")
    mock: bool = Field(
        default=False,
        description=(
            "True when the server is operating in mock mode (no live "
            "Supabase project).  Tokens are synthetic and must not be "
            "sent to real Supabase endpoints."
        ),
    )


class PasswordResetRequest(BaseModel):
    """Payload for ``POST /api/v1/auth/password-reset``."""

    email: EmailStr = Field(
        ...,
        description="Email address associated with the account to reset.",
    )


class TokenRefreshRequest(BaseModel):
    """Payload for ``POST /api/v1/auth/refresh``."""

    refresh_token: str = Field(..., description="Valid refresh token issued at login.")
