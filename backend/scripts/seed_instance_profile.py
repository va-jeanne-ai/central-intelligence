"""Seed (or update) this instance's instance_profile row.

Idempotent upsert of the singleton row. Two modes:

  --defaults    Seed the pre-Phase-1 literals (this deployment's original
                client). Running this on the original instance changes nothing
                behaviorally — it just makes the implicit profile explicit.
  --json FILE   Seed from a JSON object whose keys match the instance_profile
                columns (unknown keys are rejected). Used when provisioning a
                new company's instance.

Usage (from backend/):
    PYTHONPATH=. .venv/bin/python -m scripts.seed_instance_profile --defaults
    PYTHONPATH=. .venv/bin/python -m scripts.seed_instance_profile --json profile.json
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.instance import InstanceProfile
from app.prompts.context import DEFAULT_PROFILE

_COLUMNS = {
    "business_name", "vertical", "business_description", "target_audience",
    "brand_voice", "vertical_context", "terminology", "benchmarks",
    "app_name", "tagline", "logo_url", "colors",
    "currency_code", "currency_symbol", "timezone", "locale",
}


def _defaults_payload() -> dict:
    """The pre-Phase-1 literals as an explicit profile."""
    return {
        "vertical": DEFAULT_PROFILE.vertical,
        "app_name": DEFAULT_PROFILE.app_name,
        "tagline": "AI Command Center",
        "vertical_context": DEFAULT_PROFILE.vertical_context,
        "currency_code": "USD",
        "currency_symbol": "$",
        "timezone": "UTC",
        "locale": "en-US",
    }


async def seed(payload: dict) -> None:
    unknown = set(payload) - _COLUMNS
    if unknown:
        raise SystemExit(f"Unknown profile keys: {sorted(unknown)}")

    async with AsyncSessionLocal() as session:
        row = (await session.execute(select(InstanceProfile).limit(1))).scalar_one_or_none()
        created = row is None
        if created:
            row = InstanceProfile(id=1)
            session.add(row)
        for key, value in payload.items():
            setattr(row, key, value)
        await session.commit()
    action = "created" if created else "updated"
    print(f"instance_profile {action}: {sorted(payload)}")


if __name__ == "__main__":
    if "--defaults" in sys.argv:
        payload = _defaults_payload()
    elif "--json" in sys.argv:
        path = Path(sys.argv[sys.argv.index("--json") + 1])
        payload = json.loads(path.read_text())
    else:
        raise SystemExit(__doc__)
    asyncio.run(seed(payload))
