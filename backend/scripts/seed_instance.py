"""Seed a freshly provisioned instance: profile + first admin user.

Run inside the api container (or locally from backend/) after the migrate
service has applied migrations and the admin's account exists in Supabase
Auth (create it in the dashboard first — this script grants the role, it
does not create the auth user).

Usage:
    python -m scripts.seed_instance --profile-json profile.json --admin-email owner@client.com
    python -m scripts.seed_instance --defaults                    # original-client literals
    python -m scripts.seed_instance --admin-email owner@client.com  # role grant only

profile.json keys = instance_profile columns (see scripts/seed_instance_profile.py).
Idempotent: safe to re-run.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from sqlalchemy import text

from app.database import AsyncSessionLocal
from scripts.seed_instance_profile import _defaults_payload, seed as seed_profile


async def grant_admin(email: str) -> None:
    """Set role=admin in Supabase auth metadata + the local users mirror.

    The auth schema lives in the same Postgres as the app DB (one Supabase
    project per instance), so a direct UPDATE is authoritative. The user must
    already exist in Supabase Auth; we fail loudly if not.
    """
    async with AsyncSessionLocal() as session:
        updated = (
            await session.execute(
                text("""
                    UPDATE auth.users
                    SET raw_user_meta_data =
                        jsonb_set(COALESCE(raw_user_meta_data, '{}'::jsonb), '{role}', '"admin"')
                    WHERE email = :email
                """),
                {"email": email},
            )
        ).rowcount
        if not updated:
            raise SystemExit(
                f"No Supabase auth user with email {email!r} — create the account in "
                "the Supabase dashboard (Authentication → Users) first, then re-run."
            )
        # Mirror row may not exist until their first API request; update if present.
        await session.execute(
            text("UPDATE public.users SET role = 'admin' WHERE email = :email"),
            {"email": email},
        )
        await session.commit()
    print(f"admin role granted: {email}")


async def main(argv: list[str]) -> None:
    did_something = False

    if "--json" in argv or "--profile-json" in argv:
        flag = "--profile-json" if "--profile-json" in argv else "--json"
        path = Path(argv[argv.index(flag) + 1])
        await seed_profile(json.loads(path.read_text()))
        did_something = True
    elif "--defaults" in argv:
        await seed_profile(_defaults_payload())
        did_something = True

    if "--admin-email" in argv:
        await grant_admin(argv[argv.index("--admin-email") + 1])
        did_something = True

    if not did_something:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:]))
