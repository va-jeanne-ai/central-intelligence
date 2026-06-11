"""Provider registry for third-party integrations.

Single source of truth for "what integrations does CI know about, what
form fields does each one need, and which fields are secret?". The
``/api/v1/integrations`` endpoints render this dict as JSON so the
frontend can build credential forms dynamically — adding a new provider
is a backend-only change.

To wire a new provider:
  1. Add an entry below.
  2. Build ``app/services/<provider>_client.py`` with a ``_resolve_creds``
     that reads from the ``integrations`` table first, then falls back to
     ``settings``.
  3. Map the slug to its trigger task in
     ``app/routes/integrations.py::_trigger_sync``.
"""

from __future__ import annotations

from typing import Any, Literal


ProviderStatus = Literal["available", "coming_soon"]


def _field(
    key: str,
    label: str,
    *,
    type: str = "text",
    secret: bool = False,
    required: bool = False,
    placeholder: str = "",
    help: str = "",
) -> dict[str, Any]:
    """Shorthand builder for one form field dict."""
    return {
        "key": key,
        "label": label,
        "type": type,
        "secret": secret,
        "required": required,
        "placeholder": placeholder,
        "help": help,
    }


PROVIDERS: dict[str, dict[str, Any]] = {
    "mailchimp": {
        "slug": "mailchimp",
        "name": "Mailchimp",
        "icon": "✉",
        "category": "email",
        "status": "available",
        "description": "Sync email campaign metrics (opens, clicks, bounces) into your dashboard.",
        "trigger_task": "mailchimp",  # mapped in routes/_trigger_sync
        "fields": [
            _field(
                "api_key",
                "API Key",
                type="password",
                secret=True,
                required=True,
                placeholder="abc123def456...-us21",
                help="Mailchimp → Profile → Extras → API keys. Format: hexkey-dc.",
            ),
            _field(
                "server_prefix",
                "Server Prefix",
                type="text",
                secret=False,
                required=False,
                placeholder="us21",
                help="Auto-derived from the dc suffix of your API key when blank.",
            ),
        ],
    },
    "ghl": {
        "slug": "ghl",
        "name": "Go High Level",
        "icon": "🎯",
        "category": "crm",
        "status": "available",
        "description": "Two-way GHL link: receive contacts pushed via Custom Webhook action, plus a nightly pull that backfills + catches out-of-band edits.",
        "trigger_task": "app.tasks.ghl_sync.sync_ghl_contacts",
        # Hybrid: both a server-generated webhook token (for inbound) AND
        # user-supplied API credentials (for the pull sync). The upsert
        # route mints the webhook_token on first save if missing, then
        # keeps it on subsequent saves so users can edit API creds without
        # rotating the webhook URL.
        "fields": [
            {
                "key": "api_access_token",
                "label": "API access token",
                "type": "password",
                "secret": True,
                "required": True,
                "help": "Private Integration Token from GHL settings. Used for the nightly contact pull.",
            },
            {
                "key": "location_id",
                "label": "Location ID",
                "type": "text",
                "secret": True,
                "required": True,
                "help": "The GHL sub-account (location) the API token belongs to.",
            },
        ],
    },
    "google_calendar": {
        "slug": "google_calendar",
        "name": "Google Calendar",
        "icon": "📅",
        "category": "calendar",
        "status": "available",
        "description": "Pull events from your Google Calendar into the workflow planner.",
        "trigger_task": None,  # OAuth flow not wired yet
        "oauth_pending": True,
        "fields": [],  # OAuth — no form fields, just a Connect-with-Google button (TBD)
    },
    "google_workspace": {
        "slug": "google_workspace",
        "name": "Google Workspace (Gmail)",
        "icon": "📧",
        "category": "communication",
        "status": "available",
        "description": "Pull email threads where a lead's address appears (To/From/Cc/Bcc) into the lead detail page. Each staff member connects their own Google account via OAuth.",
        "trigger_task": "app.tasks.gmail_sync.sync_gmail_threads",
        # Per-user OAuth provider: the frontend reads this flag and
        # renders a "Connect Gmail" button instead of the credentials
        # form. The actual flow lives in routes/oauth.py.
        "oauth_per_user": True,
        "fields": [],
    },
    "meta_ads": {
        "slug": "meta_ads",
        "name": "Meta Ads",
        "icon": "📢",
        "category": "ads",
        "status": "coming_soon",
        "description": "Facebook + Instagram ad spend, impressions, conversions.",
        "fields": [],
    },
    "google_ads": {
        "slug": "google_ads",
        "name": "Google Ads",
        "icon": "🔍",
        "category": "ads",
        "status": "coming_soon",
        "description": "Search and display ad performance metrics.",
        "fields": [],
    },
    "instagram": {
        "slug": "instagram",
        "name": "Instagram",
        "icon": "📷",
        "category": "social",
        "status": "available",
        "description": "Organic post metrics, follower growth, reach & impressions via the Meta Graph API.",
        "trigger_task": "instagram",  # mapped in routes/_trigger_sync
        # Connect via Meta OAuth (single shared business account). The
        # frontend reads this flag and renders a "Connect with Meta" button.
        # The manual-token `fields` below stay as a fallback for admins who
        # prefer to paste a long-lived token directly.
        "meta_oauth": True,
        "fields": [
            _field(
                "access_token",
                "Access Token",
                type="password",
                secret=True,
                required=True,
                placeholder="EAAG... (long-lived token)",
                help=(
                    "Long-lived Meta access token with instagram_basic + "
                    "instagram_manage_insights + pages_read_engagement scopes. "
                    "Generate in the Meta Graph API Explorer, then exchange for a "
                    "long-lived (~60-day) token. Re-paste when it expires."
                ),
            ),
            _field(
                "ig_user_id",
                "Instagram Account ID",
                type="text",
                secret=False,
                required=True,
                placeholder="17841400000000000",
                help=(
                    "Numeric Instagram Business account ID. Find it via "
                    "GET /me/accounts -> your Page -> "
                    "GET /{page-id}?fields=instagram_business_account."
                ),
            ),
        ],
    },
    "linkedin": {
        "slug": "linkedin",
        "name": "LinkedIn",
        "icon": "💼",
        "category": "social",
        "status": "coming_soon",
        "description": "Company-page post engagement and follower metrics.",
        "fields": [],
    },
    "tiktok": {
        "slug": "tiktok",
        "name": "TikTok",
        "icon": "🎵",
        "category": "social",
        "status": "coming_soon",
        "description": "TikTok video metrics, follower growth, engagement.",
        "fields": [],
    },
}


def list_providers() -> list[dict[str, Any]]:
    """Return providers in display order (available first, then coming soon)."""
    available = [p for p in PROVIDERS.values() if p["status"] == "available"]
    coming = [p for p in PROVIDERS.values() if p["status"] == "coming_soon"]
    return available + coming


def get_provider(slug: str) -> dict[str, Any] | None:
    return PROVIDERS.get(slug)


def secret_keys(slug: str) -> set[str]:
    """Set of field keys flagged secret for a provider. Empty if unknown slug."""
    provider = PROVIDERS.get(slug)
    if not provider:
        return set()
    return {f["key"] for f in provider.get("fields", []) if f.get("secret")}


def required_keys(slug: str) -> set[str]:
    provider = PROVIDERS.get(slug)
    if not provider:
        return set()
    return {f["key"] for f in provider.get("fields", []) if f.get("required")}
