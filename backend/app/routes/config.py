"""
Instance configuration endpoints — the per-company profile of this deployment.

GET  /api/v1/config/branding — public-safe white-label subset (auth-exempt:
                               the login page renders it pre-auth)
GET  /api/v1/config/profile  — full profile (any authenticated user)
PUT  /api/v1/config/profile  — partial update (admin only); re-primes the
                               in-process prompt-profile cache so agent system
                               prompts pick the change up immediately in the
                               API process. Celery workers re-read per task
                               (icp) or pick changes up on restart.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser, get_current_user
from app.database import get_session
from app.models.instance import InstanceProfile
from app.prompts.context import prime_profile_cache
from app.schemas.config import (
    BrandingResponse,
    InstanceProfileResponse,
    UpdateInstanceProfileRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/config", tags=["config"])

_PROFILE_FIELDS = tuple(UpdateInstanceProfileRequest.model_fields)


async def _get_row(session: AsyncSession) -> InstanceProfile | None:
    return (await session.execute(select(InstanceProfile).limit(1))).scalar_one_or_none()


@router.get("/branding", response_model=BrandingResponse)
async def get_branding(session: AsyncSession = Depends(get_session)) -> BrandingResponse:
    """White-label branding for the frontend shell. Public — see middleware exempt list."""
    row = await _get_row(session)
    if row is None:
        return BrandingResponse()
    defaults = BrandingResponse()
    return BrandingResponse(
        app_name=row.app_name or defaults.app_name,
        tagline=row.tagline or defaults.tagline,
        logo_url=row.logo_url,
        colors=row.colors or {},
        currency_code=row.currency_code or defaults.currency_code,
        currency_symbol=row.currency_symbol or defaults.currency_symbol,
        locale=row.locale or defaults.locale,
    )


@router.get("/profile", response_model=InstanceProfileResponse)
async def get_profile(
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> InstanceProfileResponse:
    row = await _get_row(session)
    if row is None:
        return InstanceProfileResponse(exists=False)
    return InstanceProfileResponse(
        **{f: getattr(row, f) for f in _PROFILE_FIELDS}, exists=True
    )


@router.put("/profile", response_model=InstanceProfileResponse)
async def update_profile(
    payload: UpdateInstanceProfileRequest,
    user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> InstanceProfileResponse:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")

    row = await _get_row(session)
    if row is None:
        row = InstanceProfile(id=1)
        session.add(row)

    changed = payload.model_dump(exclude_unset=True)
    for field, value in changed.items():
        setattr(row, field, value)
    await session.commit()
    await session.refresh(row)

    await prime_profile_cache(session)
    logger.info("instance_profile updated by %s (fields=%s)", user.email, sorted(changed))

    return InstanceProfileResponse(
        **{f: getattr(row, f) for f in _PROFILE_FIELDS}, exists=True
    )
