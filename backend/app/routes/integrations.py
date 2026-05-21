"""Integrations CRUD — UI-driven activation of third-party connectors.

Endpoints (all require auth):
  GET    /api/v1/integrations               — list providers + connection state
  GET    /api/v1/integrations/{slug}        — detail incl. dynamic field schema
  POST   /api/v1/integrations/{slug}        — upsert credentials + trigger sync
  POST   /api/v1/integrations/{slug}/test   — quick connectivity probe
  DELETE /api/v1/integrations/{slug}        — disconnect (clear credentials)

Activation flow: a successful POST writes the encrypted blob and
immediately enqueues the matching Celery task so the dashboard reflects
the new connection within ~30s without waiting for the next beat tick.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser, get_current_user
from app.database import get_session
from app.models.integration import Integration
from app.schemas.integrations import (
    IntegrationDetail,
    ProviderFieldSchema,
    ProviderSummary,
    TestIntegrationResponse,
    UpsertIntegrationRequest,
)
from app.services import secrets
from app.services.integrations_registry import (
    get_provider,
    list_providers,
    required_keys,
    secret_keys,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/integrations", tags=["integrations"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_row(session: AsyncSession, slug: str) -> Integration | None:
    result = await session.execute(select(Integration).where(Integration.provider == slug))
    return result.scalar_one_or_none()


def _summary_from(provider: dict, row: Integration | None) -> ProviderSummary:
    connected = row is not None and row.status == "connected"
    return ProviderSummary(
        slug=provider["slug"],
        name=provider["name"],
        icon=provider.get("icon", ""),
        category=provider.get("category", ""),
        status=provider["status"],
        description=provider.get("description", ""),
        connected=connected,
        last_synced_at=row.last_synced_at if row else None,
        last_sync_status=row.last_sync_status if row else None,
        oauth_pending=bool(provider.get("oauth_pending", False)),
        webhook_only=bool(provider.get("webhook_only", False)),
    )


def _ghl_webhook_url(token: str) -> str:
    """Build the absolute URL the user copies into GHL's Custom Webhook action.

    Uses ``settings.public_api_base_url`` so dev/staging/prod each produce
    a URL that's actually reachable from GHL. Path matches the route in
    ``app/routes/webhooks.py``.
    """
    from app.config import settings as _settings
    base = _settings.public_api_base_url.rstrip("/")
    return f"{base}/api/v1/webhooks/ghl/{token}/leads"


def _decrypt_blob(ciphertext: str | None) -> dict[str, str]:
    """Decrypt the secret-fields blob to a plain dict. Returns {} on failure."""
    if not ciphertext:
        return {}
    try:
        return json.loads(secrets.decrypt(ciphertext))
    except (ValueError, json.JSONDecodeError) as exc:
        logger.warning("Failed to decrypt integration blob: %s", exc)
        return {}


async def _upsert_webhook_only(
    slug: str,
    provider: dict,
    session: AsyncSession,
    current_user: CurrentUser,
) -> "IntegrationDetail":
    """Generate-and-store flow for webhook-only providers (GHL, future Stripe/Calendly).

    Mints a fresh URL-safe token, encrypts it as ``{"webhook_token": ...}``,
    upserts the integration row with ``status='connected'``. Calling again
    rotates the token (old URL stops working). Caller already verified
    ``provider['webhook_only']`` is true.
    """
    # Use stdlib secrets module (not our app.services.secrets) for the
    # token. URL-safe means it slots into the path component without
    # encoding fiddling on the user's copy-paste.
    import secrets as _stdlib_secrets
    import json

    token = _stdlib_secrets.token_urlsafe(32)
    blob = secrets.encrypt(json.dumps({"webhook_token": token}))

    row = await _get_row(session, slug)
    if row is None:
        row = Integration(
            provider=slug,
            status="connected",
            credentials_encrypted=blob,
            config=None,
        )
        session.add(row)
        logger.info("upsert_webhook_only: INSERT for slug=%s", slug)
    else:
        row.status = "connected"
        row.credentials_encrypted = blob
        row.config = None
        row.last_sync_error = None  # rotation clears stale error context
        logger.info(
            "upsert_webhook_only: ROTATE for slug=%s row=%s", slug, row.id,
        )

    await session.commit()
    await session.refresh(row)

    # Build the detail payload directly (mirrors the form-style upsert path
    # at the bottom of upsert_integration).
    values: dict[str, str] = {}
    if slug == "ghl":
        values["webhook_url"] = _ghl_webhook_url(token)

    summary = _summary_from(provider, row)
    detail = IntegrationDetail(
        **summary.model_dump(),
        fields=[ProviderFieldSchema(**f) for f in provider.get("fields", [])],
        values=values,
        last_sync_error=row.last_sync_error,
    )
    logger.info(
        "upsert_webhook_only: returning detail slug=%s connected=%s",
        slug, detail.connected,
    )
    return detail


def _trigger_sync(slug: str) -> str | None:
    """Enqueue the Celery task matching this provider. Returns task id or None."""
    if slug == "mailchimp":
        try:
            from app.tasks.email_stats import update_email_stats
            task = update_email_stats.delay()
            return task.id
        except Exception as exc:
            logger.warning("Failed to enqueue update_email_stats: %s", exc)
            return None
    # No-op for providers without a backing task yet (google_calendar, etc.)
    return None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("", response_model=list[ProviderSummary])
async def list_integrations(
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
):
    """List all providers with their current connection state."""
    rows = await session.execute(select(Integration))
    by_slug = {r.provider: r for r in rows.scalars().all()}
    return [_summary_from(p, by_slug.get(p["slug"])) for p in list_providers()]


@router.get("/{slug}", response_model=IntegrationDetail)
async def get_integration(
    slug: str,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Get a single provider's detail incl. dynamic field schema + current (masked) values."""
    provider = get_provider(slug)
    if provider is None:
        raise HTTPException(status_code=404, detail=f"Unknown provider: {slug}")

    row = await _get_row(session, slug)

    # Build the masked-values dict for the form.
    values: dict[str, str] = {}
    secret_field_keys = secret_keys(slug)
    if row is not None:
        # Non-secret values come from config JSONB as-is.
        if row.config:
            values.update({k: str(v) for k, v in row.config.items() if v is not None})
        # Secret values come from the encrypted blob, then masked.
        for key, plain in _decrypt_blob(row.credentials_encrypted).items():
            if key in secret_field_keys:
                values[key] = secrets.mask(plain)
            else:
                values[key] = plain  # belt-and-braces — shouldn't happen

    # Webhook-only providers (GHL today, Stripe/Calendly later) surface a
    # full webhook URL the user copies into the upstream tool. The token is
    # NOT masked — the URL itself IS the secret, and the user needs the
    # actual value to paste. (Anyone with access to this auth'd endpoint
    # already controls the integration.) Rotate Secret regenerates it.
    if provider.get("webhook_only") and row is not None:
        blob = _decrypt_blob(row.credentials_encrypted)
        tok = blob.get("webhook_token")
        if tok:
            if slug == "ghl":
                values["webhook_url"] = _ghl_webhook_url(tok)

    summary = _summary_from(provider, row)
    return IntegrationDetail(
        **summary.model_dump(),
        fields=[ProviderFieldSchema(**f) for f in provider.get("fields", [])],
        values=values,
        last_sync_error=row.last_sync_error if row else None,
    )


@router.post("/{slug}", response_model=IntegrationDetail)
async def upsert_integration(
    slug: str,
    body: UpsertIntegrationRequest,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Save credentials + trigger an immediate sync."""
    provider = get_provider(slug)
    if provider is None:
        raise HTTPException(status_code=404, detail=f"Unknown provider: {slug}")
    if provider["status"] != "available":
        raise HTTPException(status_code=400, detail=f"Provider {slug} is not yet available")

    # Webhook-only providers don't validate user-supplied fields — they
    # generate a server-side token on connect. Calling this endpoint again
    # rotates the token (old URL stops working). The form-validation +
    # encrypt-blob path below is for credential-style providers only.
    if provider.get("webhook_only"):
        return await _upsert_webhook_only(slug, provider, session, current_user)

    incoming = body.values or {}
    secret_field_keys = secret_keys(slug)
    config_field_keys = {f["key"] for f in provider.get("fields", [])} - secret_field_keys

    # Load existing row to know what secrets we have if the user only changed
    # non-secret fields (empty string in a secret means "keep existing").
    row = await _get_row(session, slug)
    existing_secrets = _decrypt_blob(row.credentials_encrypted) if row else {}

    # Validate required fields are present somewhere (incoming OR already
    # stored). This lets the user submit just a server_prefix tweak without
    # re-typing their API key.
    missing: list[str] = []
    for key in required_keys(slug):
        provided = (incoming.get(key) or "").strip()
        if not provided and not existing_secrets.get(key):
            missing.append(key)
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"Missing required field(s): {', '.join(missing)}",
        )

    # Build new secret blob: start from existing, overwrite with non-empty
    # incoming values for secret keys.
    new_secrets = dict(existing_secrets)
    for key in secret_field_keys:
        provided = (incoming.get(key) or "").strip()
        if provided:
            new_secrets[key] = provided

    new_config: dict[str, str] = {}
    for key in config_field_keys:
        provided = incoming.get(key)
        if provided is not None and provided != "":
            new_config[key] = provided

    ciphertext = secrets.encrypt(json.dumps(new_secrets)) if new_secrets else None

    if row is None:
        row = Integration(
            provider=slug,
            status="connected",
            credentials_encrypted=ciphertext,
            config=new_config or None,
        )
        session.add(row)
        logger.info("upsert_integration: INSERT new row for slug=%s", slug)
    else:
        row.status = "connected"
        row.credentials_encrypted = ciphertext
        row.config = new_config or None
        row.last_sync_error = None  # clear stale errors on successful save
        logger.info("upsert_integration: UPDATE existing row id=%s for slug=%s", row.id, slug)

    await session.commit()
    await session.refresh(row)
    logger.info(
        "upsert_integration: committed row id=%s provider=%s status=%s has_creds=%s",
        row.id, row.provider, row.status, row.credentials_encrypted is not None,
    )

    # Fire the matching Celery task so the dashboard updates without waiting
    # for the next beat tick. Best-effort — failure to enqueue doesn't roll
    # back the save.
    task_id = _trigger_sync(slug)
    if task_id:
        logger.info("Integration %s saved; sync task enqueued (id=%s)", slug, task_id)
    else:
        logger.info("Integration %s saved; no sync task wired", slug)

    # Re-render the detail payload for the response. Build it directly from
    # the row we just committed instead of recursing into get_integration —
    # the recursive call was harder to reason about and triggered a fresh
    # SELECT against the same session that might race with the just-finished
    # commit in some pooler modes.
    secret_field_keys = secret_keys(slug)
    values: dict[str, str] = {}
    if row.config:
        values.update({k: str(v) for k, v in row.config.items() if v is not None})
    for key, plain in _decrypt_blob(row.credentials_encrypted).items():
        if key in secret_field_keys:
            values[key] = secrets.mask(plain)
        else:
            values[key] = plain

    summary = _summary_from(provider, row)
    detail = IntegrationDetail(
        **summary.model_dump(),
        fields=[ProviderFieldSchema(**f) for f in provider.get("fields", [])],
        values=values,
        last_sync_error=row.last_sync_error,
    )
    logger.info(
        "upsert_integration: returning detail connected=%s values_keys=%s",
        detail.connected, list(detail.values.keys()),
    )
    return detail


@router.post("/{slug}/test", response_model=TestIntegrationResponse)
async def test_integration(
    slug: str,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Quick connectivity check against the upstream API without persisting state."""
    provider = get_provider(slug)
    if provider is None:
        raise HTTPException(status_code=404, detail=f"Unknown provider: {slug}")
    if provider["status"] != "available":
        return TestIntegrationResponse(ok=False, message=f"{slug} is not yet wired for live testing.")

    if slug == "mailchimp":
        # Lazy import to avoid pulling httpx into route module-load time.
        from app.services import mailchimp_client
        if not mailchimp_client.is_configured():
            return TestIntegrationResponse(
                ok=False,
                message="Mailchimp is not connected. Save credentials first.",
            )
        try:
            campaigns = mailchimp_client.list_recent_sent_campaigns(limit=1)
            return TestIntegrationResponse(
                ok=True,
                message=f"Connected. Found {len(campaigns)} recent sent campaign(s).",
            )
        except Exception as exc:
            return TestIntegrationResponse(
                ok=False,
                message=f"Mailchimp API rejected the request: {exc}",
            )

    if slug == "google_calendar":
        return TestIntegrationResponse(
            ok=False,
            message="Google Calendar OAuth flow is not yet wired.",
        )

    return TestIntegrationResponse(ok=False, message=f"No test handler for {slug}.")


@router.delete("/{slug}", status_code=204)
async def disconnect_integration(
    slug: str,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
):
    """Disconnect: flip status, null credentials + config."""
    provider = get_provider(slug)
    if provider is None:
        raise HTTPException(status_code=404, detail=f"Unknown provider: {slug}")

    row = await _get_row(session, slug)
    if row is None:
        # Nothing to disconnect — return 204 idempotently.
        return None

    row.status = "disconnected"
    row.credentials_encrypted = None
    row.config = None
    row.last_synced_at = None
    row.last_sync_status = None
    row.last_sync_error = None
    await session.commit()

    logger.info("Integration %s disconnected", slug)
    return None


# Re-export for app/main.py
__all__ = ["router"]
