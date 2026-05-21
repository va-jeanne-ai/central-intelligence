#!/usr/bin/env python3
"""
Push a single fresh lead through the GHL webhook URL.

Sibling of `simulate_ghl_webhook.py`. That script verifies behaviour
(idempotency, partial updates, bad-token handling) and cleans up after
itself. This one is the "I want to watch leads stream into /leads"
script — one new contact per invocation, no cleanup.

Each run mints a fresh contact_id + email, so re-running creates a NEW
row every time instead of updating the same one.

Usage::

    cd backend
    PYTHONPATH=. .venv/bin/python scripts/push_ghl_lead.py

    # Push 5 in a row
    PYTHONPATH=. .venv/bin/python scripts/push_ghl_lead.py --count 5

    # Custom contact details
    PYTHONPATH=. .venv/bin/python scripts/push_ghl_lead.py \\
        --first-name Sarah --last-name Hopkins --source instagram_ads

Looks up the stored webhook token from the integrations table — works
out of the box as long as the GHL integration has been connected via
the UI (or via `simulate_ghl_webhook.py --reset`).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import secrets as _stdlib_secrets
import string
import sys
import time
from pathlib import Path
from typing import Any

import httpx

# Allow `python scripts/push_ghl_lead.py` from backend/.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from app.config import settings  # noqa: E402
from app.database import AsyncSessionLocal  # noqa: E402
from app.models.integration import Integration  # noqa: E402
from app.services import secrets as app_secrets  # noqa: E402


# ─── A small library of demo personas ────────────────────────────────────────
# Used when the user doesn't pass --first-name etc. Keeps the test data
# looking like real humans without anyone having to think about it.

FIRST_NAMES = [
    "Sarah", "Marcus", "Priya", "Jordan", "Aisha", "Diego", "Yuki",
    "Eleanor", "Mateo", "Linnea", "Kenji", "Amara", "Felix", "Naomi",
    "Theo", "Camille", "Rafael", "Iris", "Beck", "Jolene",
]
LAST_NAMES = [
    "Chen", "Hopkins", "Patel", "Reyes", "Okonkwo", "Larsen", "Suzuki",
    "Ferrara", "Akhtar", "Brennan", "Volkov", "Mwangi", "Tanaka",
    "Goldberg", "Solis", "Pham", "Schultz", "Cabrera", "Park", "O'Brien",
]
SOURCES = [
    "facebook_ads", "instagram_ads", "linkedin_organic", "webinar_signup",
    "podcast_referral", "free_consult_form", "newsletter_referral",
    "twitter_thread",
]
TAG_POOLS = [
    ["webinar-attended"],
    ["webinar-attended", "high-intent"],
    ["lead-magnet-downloaded"],
    ["demo-booked"],
    ["newsletter-subscriber", "high-intent"],
    ["consult-requested"],
    ["referral"],
]


# ─── Helpers ─────────────────────────────────────────────────────────────────


async def _get_token() -> str:
    """Decrypt the webhook token from the integrations table. Raises if
    GHL isn't connected yet."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Integration).where(
                Integration.provider == "ghl",
                Integration.status == "connected",
            )
        )
        row = result.scalar_one_or_none()
        if row is None or not row.credentials_encrypted:
            raise RuntimeError(
                "GHL integration is not connected. Connect it via the "
                "UI first, or run scripts/simulate_ghl_webhook.py --reset "
                "to mint a token."
            )
        blob = json.loads(app_secrets.decrypt(row.credentials_encrypted))
        return str(blob.get("webhook_token") or "")


def _email_from_name(first: str, last: str) -> str:
    """Build a plausible-looking email with a short random suffix so
    re-runs don't collide on the unique email index."""
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=4))
    return f"{first.lower()}.{last.lower().replace(chr(39), '')}.{suffix}@example.com"


def _fresh_contact_id() -> str:
    """A short URL-safe id that mirrors GHL's contact_id shape (alphanumeric)."""
    return "ghl-" + _stdlib_secrets.token_urlsafe(9).replace("_", "").replace("-", "")[:12]


def _build_payload(args: argparse.Namespace) -> dict[str, Any]:
    """Mint one synthetic-but-realistic GHL Form-Submitted payload."""
    first = args.first_name or random.choice(FIRST_NAMES)
    last = args.last_name or random.choice(LAST_NAMES)
    email = args.email or _email_from_name(first, last)
    source = args.source or random.choice(SOURCES)
    tags = list(args.tag) if args.tag else random.choice(TAG_POOLS)
    return {
        "contact_id": _fresh_contact_id(),
        "email": email,
        "first_name": first,
        "last_name": last,
        "phone": f"+1555{random.randint(1000000, 9999999)}",
        "status": "new",
        "source": source,
        "tags": tags,
        "custom_fields": {
            "captured_at": int(time.time()),
            "campaign": f"sim-{random.randint(100, 999)}",
        },
    }


# ─── Main ────────────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url",
        default=settings.public_api_base_url,
        help="API base URL (default: from settings.public_api_base_url)",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=1,
        help="How many fresh leads to push (default: 1).",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.3,
        help="Seconds between leads when --count > 1 (default: 0.3).",
    )
    parser.add_argument("--first-name", help="Override the random first name.")
    parser.add_argument("--last-name", help="Override the random last name.")
    parser.add_argument("--email", help="Override the generated email.")
    parser.add_argument("--source", help="Override the random source.")
    parser.add_argument(
        "--tag",
        action="append",
        help="Add a tag (repeatable). Overrides the random tag pool.",
    )
    args = parser.parse_args()

    try:
        token = asyncio.run(_get_token())
    except Exception as exc:
        print(f"\033[31m✗\033[0m {exc}")
        return 1

    webhook_url = f"{args.base_url.rstrip('/')}/api/v1/webhooks/ghl/{token}/leads"

    print(f"\033[1mPushing {args.count} fresh lead(s) to:\033[0m")
    print(f"  {args.base_url}/api/v1/webhooks/ghl/…{token[-6:]}/leads")
    print()

    with httpx.Client(timeout=15.0) as client:
        for i in range(args.count):
            payload = _build_payload(args)
            r = client.post(webhook_url, json=payload)
            ok = r.status_code == 200 and r.json().get("ok") is True
            tag_str = ", ".join(payload["tags"]) or "(no tags)"
            mark = "\033[32m✓\033[0m" if ok else "\033[31m✗\033[0m"
            print(
                f"  {mark} {payload['first_name']} {payload['last_name']} "
                f"<{payload['email']}> · {payload['source']} · [{tag_str}] "
                f"→ {r.status_code}"
            )
            if not ok:
                print(f"      response: {r.text[:200]}")
            if i < args.count - 1 and args.delay > 0:
                time.sleep(args.delay)

    print()
    print("\033[36mi\033[0m Check /leads — new rows should be visible with source='ghl'.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
