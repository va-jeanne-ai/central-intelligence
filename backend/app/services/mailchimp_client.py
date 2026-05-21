"""
Mailchimp Marketing API client — F28 connector for email stats.

Thin httpx wrapper around the three endpoints needed by the
``update_email_stats`` Celery task:

  - ``GET /3.0/campaigns`` — list sent campaigns (with paging)
  - ``GET /3.0/reports/{campaign_id}`` — open/click/bounce/unsubscribe rollup

We deliberately do NOT use the official ``mailchimp_marketing`` SDK. It
pulls heavy deps for three endpoints; httpx is already in the project.

Auth: HTTP Basic with username ``any-string`` and password equal to the
API key. The server prefix (e.g. ``us21``) lives in the API key suffix
after the ``-`` and is auto-derived when not explicitly configured.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = 30.0
_DEFAULT_PAGE_SIZE = 50


@dataclass(frozen=True)
class CampaignRow:
    """Normalised campaign + report metrics ready for upsert into EmailCampaign."""

    mailchimp_id: str
    name: str
    subject: str | None
    campaign_type: str | None  # "regular" | "automation" | "rss" | ...
    status: str  # "sent" | "save" | "schedule" | ...
    sent_at_iso: str | None
    recipients_count: int
    open_count: int
    click_count: int
    unsubscribe_count: int
    bounce_count: int
    open_rate: float | None  # percentage (e.g. 36.0 for 36 %)
    click_rate: float | None


def is_configured() -> bool:
    """True when an API key is set. Callers should gate real-API paths on this."""
    return bool(settings.mailchimp_api_key)


def _server_prefix() -> str:
    """Derive the dc subdomain from settings, falling back to the key suffix.

    Raises if neither is available — caller should check ``is_configured()``
    first.
    """
    if settings.mailchimp_server_prefix:
        return settings.mailchimp_server_prefix
    key = settings.mailchimp_api_key
    if "-" in key:
        return key.rsplit("-", 1)[-1]
    raise ValueError(
        "Cannot derive Mailchimp server prefix — set MAILCHIMP_SERVER_PREFIX "
        "or use an API key with the standard 'xxxxx-us21' format."
    )


def _base_url() -> str:
    return f"https://{_server_prefix()}.api.mailchimp.com/3.0"


def _auth() -> tuple[str, str]:
    # Mailchimp accepts any non-empty username; the key goes in the password slot.
    return ("anystring", settings.mailchimp_api_key)


def _client() -> httpx.Client:
    return httpx.Client(timeout=_DEFAULT_TIMEOUT, auth=_auth())


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def list_recent_sent_campaigns(limit: int = _DEFAULT_PAGE_SIZE) -> list[dict[str, Any]]:
    """Return the most recent sent campaigns.

    Sorted by send time descending. Mailchimp caps a single page at 1000;
    we default to 50 which matches the dashboard's appetite.
    """
    url = f"{_base_url()}/campaigns"
    params = {
        "status": "sent",
        "sort_field": "send_time",
        "sort_dir": "DESC",
        "count": str(limit),
        # Trim the heavy `content` payload — we only need metadata.
        "fields": (
            "campaigns.id,campaigns.web_id,campaigns.status,campaigns.send_time,"
            "campaigns.emails_sent,campaigns.type,campaigns.settings.subject_line,"
            "campaigns.settings.title,campaigns.report_summary"
        ),
    }
    with _client() as c:
        resp = c.get(url, params=params)
        resp.raise_for_status()
        payload = resp.json()
    campaigns = payload.get("campaigns") or []
    if not isinstance(campaigns, list):
        return []
    return campaigns


def fetch_report(campaign_id: str) -> dict[str, Any] | None:
    """Pull the per-campaign report (open/click/bounce/unsubscribe).

    Returns None on 404 (campaign may have been deleted between the list
    call and this one). All other HTTP errors propagate.
    """
    url = f"{_base_url()}/reports/{campaign_id}"
    with _client() as c:
        resp = c.get(url)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()


# ---------------------------------------------------------------------------
# Normalisation helpers
# ---------------------------------------------------------------------------


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _safe_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        # Mailchimp returns rates as decimals (0.36); we store percentages (36.0).
        return float(value) * 100.0
    except (TypeError, ValueError):
        return None


def to_campaign_row(campaign: dict[str, Any], report: dict[str, Any] | None) -> CampaignRow:
    """Fold a campaigns-list entry + its report into a flat upsert row."""
    settings_obj = campaign.get("settings") or {}
    name = settings_obj.get("title") or settings_obj.get("subject_line") or "Untitled campaign"
    subject = settings_obj.get("subject_line")

    if report is not None:
        opens = _safe_int(report.get("opens", {}).get("unique_opens"))
        clicks = _safe_int(report.get("clicks", {}).get("unique_clicks"))
        unsubs = _safe_int(report.get("unsubscribed"))
        bounces_block = report.get("bounces") or {}
        bounces = (
            _safe_int(bounces_block.get("hard_bounces"))
            + _safe_int(bounces_block.get("soft_bounces"))
            + _safe_int(bounces_block.get("syntax_errors"))
        )
        open_rate = _safe_float(report.get("opens", {}).get("open_rate"))
        click_rate = _safe_float(report.get("clicks", {}).get("click_rate"))
    else:
        # Fallback to the report_summary nested on the campaigns list. Less
        # accurate (no unsubscribe / bounce breakdown) but better than nothing.
        rs = campaign.get("report_summary") or {}
        opens = _safe_int(rs.get("unique_opens"))
        clicks = _safe_int(rs.get("subscriber_clicks"))
        unsubs = 0
        bounces = 0
        open_rate = _safe_float(rs.get("open_rate"))
        click_rate = _safe_float(rs.get("click_rate"))

    return CampaignRow(
        mailchimp_id=str(campaign.get("id") or ""),
        name=str(name),
        subject=subject,
        campaign_type=campaign.get("type"),
        status=str(campaign.get("status") or "sent"),
        sent_at_iso=campaign.get("send_time"),
        recipients_count=_safe_int(campaign.get("emails_sent")),
        open_count=opens,
        click_count=clicks,
        unsubscribe_count=unsubs,
        bounce_count=bounces,
        open_rate=open_rate,
        click_rate=click_rate,
    )


def fetch_normalised_campaigns(limit: int = _DEFAULT_PAGE_SIZE) -> list[CampaignRow]:
    """One-shot helper used by the Celery task. Returns ready-to-upsert rows."""
    campaigns = list_recent_sent_campaigns(limit=limit)
    rows: list[CampaignRow] = []
    for campaign in campaigns:
        campaign_id = campaign.get("id")
        report: dict[str, Any] | None = None
        if campaign_id:
            try:
                report = fetch_report(str(campaign_id))
            except httpx.HTTPError as exc:
                logger.warning(
                    "Mailchimp report fetch failed — campaign_id=%s error=%s",
                    campaign_id, exc,
                )
        rows.append(to_campaign_row(campaign, report))
    return rows
