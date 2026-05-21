#!/usr/bin/env python3
"""
Simulate Go High Level webhook calls against a local CI backend.

Run alongside `uvicorn app.main:app --reload`. This script:

  1. Looks up the existing GHL integration row in the DB (or auto-connects
     if there isn't one).
  2. Reads the stored webhook token, builds the same URL the integration
     page hands to the user.
  3. POSTs four payloads through httpx — the same path GHL's servers
     would hit — and reports what came back + what landed in the DB.

Scenarios covered:

  Scenario 1  — INSERT a new contact (form-style payload).
  Scenario 2  — UPDATE the same contact with a richer Contact-Created style.
  Scenario 3  — Tag-added trigger: only contact_id + tags, confirms
                partial updates don't blank existing fields.
  Scenario 4  — Bad token: 404 (never 401).

Usage:
    cd backend
    PYTHONPATH=. .venv/bin/python scripts/simulate_ghl_webhook.py

Flags:
    --base-url URL         Override the API base (default: http://localhost:8000).
    --keep                 Don't clean up the test lead afterwards.
    --reset                Wipe any existing GHL integration row first
                           (forces a fresh token / fresh URL).

No external services needed. The script writes only to your local DB
and reads back from it for the assertions.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import secrets as _stdlib_secrets
import sys
from pathlib import Path
from typing import Any

import httpx

# Allow `python scripts/simulate_ghl_webhook.py` from the backend/ dir.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import delete, select  # noqa: E402

from app.config import settings  # noqa: E402
from app.database import AsyncSessionLocal  # noqa: E402
from app.models.integration import Integration  # noqa: E402
from app.models.operational import Lead  # noqa: E402
from app.services import secrets as app_secrets  # noqa: E402


# ─── Console helpers ─────────────────────────────────────────────────────────


def _ok(msg: str) -> None:
    print(f"  \033[32m✓\033[0m {msg}")


def _fail(msg: str) -> None:
    print(f"  \033[31m✗\033[0m {msg}")


def _info(msg: str) -> None:
    print(f"  \033[36mi\033[0m {msg}")


def _header(msg: str) -> None:
    print(f"\n\033[1m{msg}\033[0m")


# ─── Payload library — realistic GHL workflow shapes ─────────────────────────

CONTACT_ID = "ghl-sim-001"

# Form-Submitted trigger — GHL uses Title Case keys for form fields by default.
PAYLOAD_INSERT: dict[str, Any] = {
    "contact_id": CONTACT_ID,
    "email": "Greg.Test@Example.com",
    "first_name": "Greg",
    "last_name": "Test",
    "phone": "+15551234567",
    "source": "facebook_ads",
    "status": "new",
    "tags": ["webinar-attended"],
    "custom_fields": {"signup_source": "fb-lookalike-may"},
}

# Contact-Created trigger — GHL emits camelCase here.
PAYLOAD_UPDATE: dict[str, Any] = {
    "contactId": CONTACT_ID,
    "email": "greg.test@example.com",
    "firstName": "Greg",
    "lastName": "Test-Updated",
    "phone": "+15551234567",
    "status": "qualified",
    "tags": ["webinar-attended", "high-intent"],
}

# Tag-Added trigger — minimal payload, only the contact id + new tags.
# Critical test: this MUST NOT blank the name / phone / email we already have.
PAYLOAD_TAG_ADDED: dict[str, Any] = {
    "contact_id": CONTACT_ID,
    "tags": ["webinar-attended", "high-intent", "demo-booked"],
}


# ─── Setup / teardown ────────────────────────────────────────────────────────


async def _get_or_create_token(reset: bool) -> str:
    """Find an existing GHL integration row, or insert one. Returns the
    decrypted webhook token."""
    async with AsyncSessionLocal() as session:
        if reset:
            await session.execute(
                delete(Integration).where(Integration.provider == "ghl")
            )
            await session.commit()
            _info("Existing GHL integration wiped (--reset).")

        result = await session.execute(
            select(Integration).where(Integration.provider == "ghl")
        )
        row = result.scalar_one_or_none()

        if row is None:
            # Auto-connect: mint a token the same way the integrations route
            # would. This lets the simulator work even on a fresh dev env.
            token = _stdlib_secrets.token_urlsafe(32)
            blob = app_secrets.encrypt(json.dumps({"webhook_token": token}))
            row = Integration(
                provider="ghl", status="connected", credentials_encrypted=blob
            )
            session.add(row)
            await session.commit()
            _ok(f"Created fresh GHL integration row (token …{token[-8:]})")
            return token

        # Existing row — decrypt and return its token.
        if not row.credentials_encrypted:
            raise RuntimeError(
                "GHL integration row exists but has no credentials_encrypted. "
                "Re-run with --reset to mint a new token."
            )
        blob = json.loads(app_secrets.decrypt(row.credentials_encrypted))
        token = str(blob.get("webhook_token") or "")
        if not token:
            raise RuntimeError(
                "GHL credentials blob has no webhook_token. Use --reset."
            )
        _ok(f"Using existing GHL token (…{token[-8:]})")
        return token


async def _fetch_lead() -> Lead | None:
    """Return the simulator's lead row from the DB, or None."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Lead).where(
                Lead.source == "ghl",
                Lead.external_id == CONTACT_ID,
                Lead.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()


async def _cleanup_lead() -> None:
    """Hard-delete the simulator's lead row (idempotent)."""
    async with AsyncSessionLocal() as session:
        await session.execute(
            delete(Lead).where(
                Lead.source == "ghl",
                Lead.external_id == CONTACT_ID,
            )
        )
        await session.commit()


# ─── Test scenarios ──────────────────────────────────────────────────────────


def _post(client: httpx.Client, url: str, body: dict) -> httpx.Response:
    return client.post(url, json=body)


def run_scenarios(base_url: str, token: str) -> tuple[int, int]:
    """Returns (passed, failed)."""
    webhook_url = f"{base_url.rstrip('/')}/api/v1/webhooks/ghl/{token}/leads"
    bad_token_url = webhook_url.replace(token, token[:-5] + "XXXXX")

    passed = 0
    failed = 0

    with httpx.Client(timeout=15.0) as client:
        # ── Scenario 1 ──────────────────────────────────────────────────────
        _header("Scenario 1 — INSERT (Form-Submitted trigger)")
        r = _post(client, webhook_url, PAYLOAD_INSERT)
        if r.status_code == 200 and r.json() == {"ok": True}:
            _ok(f"POST returned 200 {r.json()}")
        else:
            _fail(f"expected 200 {{'ok':True}}, got {r.status_code} {r.text}")
            failed += 1
            return passed, failed

        lead = asyncio.run(_fetch_lead())
        if lead is None:
            _fail("lead not in DB after insert")
            failed += 1
            return passed, failed
        _ok(
            f"lead persisted — name={lead.name!r} email={lead.email!r} "
            f"phone={lead.phone!r} status={lead.status!r}"
        )
        if lead.email == "greg.test@example.com":
            _ok("email lowercased + stripped ✓")
            passed += 1
        else:
            _fail(f"email not normalised, got {lead.email!r}")
            failed += 1

        # ── Scenario 2 ──────────────────────────────────────────────────────
        _header("Scenario 2 — UPDATE (Contact-Created style, camelCase)")
        r = _post(client, webhook_url, PAYLOAD_UPDATE)
        if r.status_code == 200:
            _ok(f"POST returned 200 {r.json()}")
        else:
            _fail(f"expected 200, got {r.status_code} {r.text}")
            failed += 1

        lead = asyncio.run(_fetch_lead())
        if lead is None:
            _fail("lead vanished after update?")
            failed += 1
            return passed, failed
        if lead.name == "Greg Test-Updated" and lead.status == "qualified":
            _ok("name + status updated in place ✓")
            passed += 1
        else:
            _fail(
                f"update didn't take — name={lead.name!r} status={lead.status!r}"
            )
            failed += 1

        # ── Scenario 3 ──────────────────────────────────────────────────────
        _header("Scenario 3 — Tag-Added (minimal payload, partial update)")
        before_name = lead.name
        before_phone = lead.phone
        r = _post(client, webhook_url, PAYLOAD_TAG_ADDED)
        if r.status_code == 200:
            _ok(f"POST returned 200 {r.json()}")
        else:
            _fail(f"expected 200, got {r.status_code} {r.text}")
            failed += 1

        lead = asyncio.run(_fetch_lead())
        if lead is None:
            _fail("lead vanished after tag-added?")
            failed += 1
            return passed, failed
        if lead.name == before_name and lead.phone == before_phone:
            _ok(
                f"partial payload didn't blank name/phone ✓ "
                f"(name={lead.name!r}, phone={lead.phone!r})"
            )
            passed += 1
        else:
            _fail(
                f"partial payload corrupted existing fields — "
                f"name was {before_name!r}, now {lead.name!r}; "
                f"phone was {before_phone!r}, now {lead.phone!r}"
            )
            failed += 1

        # Confirm the new tags landed in notes JSON
        try:
            notes = json.loads(lead.notes or "{}")
        except (TypeError, json.JSONDecodeError):
            notes = {}
        if "demo-booked" in (notes.get("tags") or []):
            _ok("new tag (demo-booked) visible in lead.notes ✓")
            passed += 1
        else:
            _fail(f"new tag not in notes — got tags={notes.get('tags')!r}")
            failed += 1

        # ── Scenario 4 ──────────────────────────────────────────────────────
        _header("Scenario 4 — Bad token → 404 (not 401)")
        r = _post(client, bad_token_url, {"contact_id": "x"})
        if r.status_code == 404:
            _ok("bad token rejected with 404 ✓")
            passed += 1
        elif r.status_code == 401:
            _fail("got 401 — should be 404 (URL existence not confirmed)")
            failed += 1
        else:
            _fail(f"expected 404, got {r.status_code} {r.text}")
            failed += 1

    return passed, failed


# ─── Main ────────────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url",
        default=settings.public_api_base_url,
        help="API base URL (default: from settings.public_api_base_url)",
    )
    parser.add_argument(
        "--keep",
        action="store_true",
        help="Don't delete the simulator's lead row at the end.",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Wipe the GHL integration row first (mints a fresh token).",
    )
    args = parser.parse_args()

    print("\033[1mGHL webhook simulator\033[0m")
    print(f"  base URL: {args.base_url}")

    try:
        token = asyncio.run(_get_or_create_token(reset=args.reset))
    except Exception as exc:
        _fail(f"setup failed: {exc}")
        return 1

    # Always start from a clean slate so the insert/update assertions are real.
    asyncio.run(_cleanup_lead())

    try:
        passed, failed = run_scenarios(args.base_url, token)
    finally:
        if not args.keep:
            asyncio.run(_cleanup_lead())
            print()
            _info("Test lead cleaned up. (--keep to inspect manually.)")

    print()
    print(f"\033[1mTotal: {passed} passed, {failed} failed\033[0m")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
