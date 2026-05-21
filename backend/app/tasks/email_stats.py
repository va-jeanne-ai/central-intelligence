"""
Email Stats Celery task — Operator OPS-SE1.

Scheduled task that pulls and updates email campaign metrics. When
``settings.mailchimp_api_key`` is set, hits the Mailchimp Marketing API
for real data; otherwise falls back to baked-in seed data so dev / demo
environments still render a populated dashboard.

Uses a synchronous SQLAlchemy session because Celery runs outside
FastAPI's async event loop.

Sprint 3a / OPS-SE1 — Email Stats Updater
F28 — Real-platform connectors
"""

import logging
from datetime import datetime, timezone
from uuid import uuid4

import httpx
from celery.exceptions import MaxRetriesExceededError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.integration import Integration
from app.models.marketing import EmailCampaign
from app.services import mailchimp_client
from app.tasks.celery_app import celery_app
from app.tasks.db import make_sync_session

logger = logging.getLogger(__name__)

_SEED_CAMPAIGNS = [
    {"name": "Weekly Newsletter #42", "subject": "This Week in Coaching", "campaign_type": "nurture", "status": "sent", "recipients_count": 2450, "open_count": 882, "click_count": 196, "unsubscribe_count": 12, "bounce_count": 8, "open_rate": 36.0, "click_rate": 8.0},
    {"name": "New Program Launch", "subject": "Introducing: Scale Your Practice", "campaign_type": "broadcast", "status": "sent", "recipients_count": 3100, "open_count": 1178, "click_count": 341, "unsubscribe_count": 25, "bounce_count": 15, "open_rate": 38.0, "click_rate": 11.0},
    {"name": "Re-engagement Sequence", "subject": "We miss you! Here's what's new", "campaign_type": "sequence", "status": "sent", "recipients_count": 890, "open_count": 178, "click_count": 45, "unsubscribe_count": 8, "bounce_count": 3, "open_rate": 20.0, "click_rate": 5.1},
]


def _stamp_integration_sync(
    db: Session,
    provider: str,
    *,
    when: datetime,
    status: str,
    error: str | None = None,
) -> None:
    """Update integrations.{last_synced_at, last_sync_status, last_sync_error}.

    Only writes when a row already exists for the provider — we don't want a
    seed-only run to create an integration record the user never configured.
    Best-effort: any DB error is logged and swallowed so the parent task
    completes normally.
    """
    try:
        row = db.execute(
            select(Integration).where(Integration.provider == provider)
        ).scalar_one_or_none()
        if row is None:
            return
        row.last_synced_at = when
        row.last_sync_status = status
        row.last_sync_error = error
    except Exception as exc:
        logger.warning("Failed to stamp integration sync for %s: %s", provider, exc)


def _upsert_campaign(db, campaign_data: dict, sent_at_default: datetime) -> None:
    """Upsert one campaign row keyed on ``name``.

    Same dedup key as the seed-data path, so re-running the task is
    idempotent and Mailchimp / seed rows don't fight each other when the
    user flips MAILCHIMP_API_KEY on or off.
    """
    existing = db.execute(
        select(EmailCampaign).where(
            EmailCampaign.name == campaign_data["name"],
            EmailCampaign.deleted_at.is_(None),
        )
    ).scalar_one_or_none()

    if existing:
        for key, value in campaign_data.items():
            if hasattr(existing, key) and value is not None:
                setattr(existing, key, value)
    else:
        sent_at = campaign_data.pop("sent_at", None) or sent_at_default
        db.add(EmailCampaign(sent_at=sent_at, **campaign_data))


# OPS-SE1: Scheduled Celery task to pull/update email campaign metrics
@celery_app.task(bind=True, max_retries=3, default_retry_delay=300)
def update_email_stats(self) -> dict:
    """Scheduled Celery task that pulls and updates email campaign metrics.

    Sprint 3a / OPS-SE1 — Email Stats Updater
    Runs on a schedule (configured in Celery beat schedule).

    Behaviour:
      - When ``MAILCHIMP_API_KEY`` is set: hit Mailchimp, upsert real rows
      - Otherwise: fall back to ``_SEED_CAMPAIGNS`` so the dashboard still
        renders something in dev / demo / pre-integration environments

    Returns
    -------
    dict
        ``{task_id, status, message, campaigns_checked, source, updated_at}``
        where ``source`` is ``"mailchimp"`` or ``"seed"``.
    """
    task_id = self.request.id or uuid4().hex
    logger.info("update_email_stats started — task_id=%s", task_id)

    try:
        db = make_sync_session()
        try:
            now = datetime.now(timezone.utc)
            source = "seed"
            campaigns_to_write: list[dict] = []

            mailchimp_error: str | None = None
            if mailchimp_client.is_configured():
                try:
                    rows = mailchimp_client.fetch_normalised_campaigns(limit=50)
                    source = "mailchimp"
                    for row in rows:
                        sent_at: datetime | None = None
                        if row.sent_at_iso:
                            try:
                                sent_at = datetime.fromisoformat(
                                    row.sent_at_iso.replace("Z", "+00:00")
                                )
                            except ValueError:
                                sent_at = None
                        campaigns_to_write.append({
                            "name": row.name,
                            "subject": row.subject,
                            "campaign_type": row.campaign_type,
                            "status": row.status,
                            "sent_at": sent_at,
                            "recipients_count": row.recipients_count,
                            "open_count": row.open_count,
                            "click_count": row.click_count,
                            "unsubscribe_count": row.unsubscribe_count,
                            "bounce_count": row.bounce_count,
                            "open_rate": row.open_rate,
                            "click_rate": row.click_rate,
                        })
                    logger.info(
                        "update_email_stats — fetched %d campaigns from Mailchimp",
                        len(campaigns_to_write),
                    )
                except httpx.HTTPError as exc:
                    # API outage / bad key / network. Don't bring down the
                    # task — fall through to seed data so the dashboard keeps
                    # rendering. The Celery retry mechanism will pick up the
                    # next tick.
                    logger.exception(
                        "Mailchimp fetch failed — falling back to seed (task_id=%s): %s",
                        task_id, exc,
                    )
                    mailchimp_error = str(exc)[:500]

            if source == "seed":
                campaigns_to_write = [dict(c) for c in _SEED_CAMPAIGNS]

            for campaign_data in campaigns_to_write:
                _upsert_campaign(db, campaign_data, sent_at_default=now)

            # Stamp the integration row with this sync's outcome so the UI's
            # "Last synced" / "Last sync error" surface reflects reality.
            # Only when the user has actually configured Mailchimp via the
            # integrations page — we don't want a pure-seed run to fabricate
            # an integration record.
            if mailchimp_client.is_configured():
                _stamp_integration_sync(
                    db,
                    "mailchimp",
                    when=now,
                    status="ok" if mailchimp_error is None and source == "mailchimp" else "error",
                    error=mailchimp_error,
                )

            db.commit()
            checked = len(campaigns_to_write)
        finally:
            db.close()

        logger.info(
            "update_email_stats completed — task_id=%s source=%s checked=%d",
            task_id, source, checked,
        )

        return {
            "task_id": task_id,
            "status": "completed",
            "message": f"Email stats updated for {checked} campaigns",
            "campaigns_checked": checked,
            "source": source,
            "updated_at": now.isoformat(),
        }

    except Exception as exc:
        logger.exception(
            "update_email_stats failed — task_id=%s error=%s", task_id, exc
        )
        try:
            raise self.retry(exc=exc)
        except MaxRetriesExceededError:
            logger.error(
                "Max retries exceeded for update_email_stats task_id=%s", task_id
            )
            raise
