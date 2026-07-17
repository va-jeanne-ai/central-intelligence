"""Capture (or check) the DB parity baseline for the productization refactor.

Read-only. Records two things from the app database:
  1. Row counts for every ORM-mapped table.
  2. Every registry metric's (value, sample_size) over fixed absolute windows —
     all-time, and since 2026-06-01 — so results are reproducible against a
     cloned copy of the same data.

``capture`` freezes the fixture; ``--check`` recomputes and diffs against it.
A check is only meaningful against the SAME data snapshot the fixture was
captured from (a staging clone / dump restore) — live data drifts by design.
See docs/staging-parity-runbook.html.

Connection: DATABASE_URL points at the Supabase *session* pooler (15-client
cap, mostly held by the production droplet), so this script connects through
the *transaction* pooler on port 6543 with a single read-only sync connection.
Override with PARITY_DATABASE_URL if the derived URL is wrong.

Usage (from backend/):
    PYTHONPATH=. .venv/bin/python -m scripts.capture_parity_baseline            # capture
    PYTHONPATH=. .venv/bin/python -m scripts.capture_parity_baseline --check    # verify
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

from app.analytics.registry import all_metrics
from app.config import settings
from app.models.base import Base

FIXTURE = Path(__file__).resolve().parent.parent / "tests" / "parity" / "fixtures" / "db_baseline.json"

# Fixed absolute windows so a re-run against the same data snapshot reproduces
# the numbers exactly. "all_time" uses the registry's `:since IS NULL` branch.
WINDOWS: dict[str, str | None] = {
    "all_time": None,
    "since_2026-06-01": "2026-06-01T00:00:00+00:00",
}


def _parity_url() -> str:
    override = os.environ.get("PARITY_DATABASE_URL")
    if override:
        return override
    return settings.database_url.replace("+asyncpg", "").replace(":5432/", ":6543/")


def compute_baseline() -> dict:
    engine = create_engine(_parity_url(), poolclass=NullPool)
    row_counts: dict[str, int] = {}
    metrics: dict[str, dict[str, dict[str, float | int | None]]] = {}
    try:
        with engine.connect().execution_options(postgresql_readonly=True) as conn:
            for table in sorted(Base.metadata.sorted_tables, key=lambda t: t.name):
                n = conn.execute(text(f'SELECT COUNT(*) FROM "{table.name}"')).scalar()
                row_counts[table.name] = int(n or 0)

            for m in all_metrics():
                per_window: dict[str, dict[str, float | int | None]] = {}
                for wname, since in WINDOWS.items():
                    since_dt = datetime.fromisoformat(since) if since else None
                    row = conn.execute(m.sql, {"since": since_dt}).one()
                    value = float(row.value) if row.value is not None else None
                    per_window[wname] = {"value": value, "sample_size": int(row.sample_size or 0)}
                metrics[m.key] = per_window
    finally:
        engine.dispose()

    return {"row_counts": row_counts, "metrics": metrics}


def _git_rev() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
    except Exception:
        return "unknown"


def capture() -> int:
    baseline = compute_baseline()
    baseline["_meta"] = {
        "captured_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "git_rev": _git_rev(),
        "windows": WINDOWS,
    }
    FIXTURE.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE.write_text(json.dumps(baseline, indent=2, sort_keys=True) + "\n")
    n_tables = len(baseline["row_counts"])
    n_metrics = len(baseline["metrics"])
    print(f"Wrote {FIXTURE.name}: {n_tables} tables, {n_metrics} metrics x {len(WINDOWS)} windows")
    return 0


def check() -> int:
    if not FIXTURE.exists():
        print(f"FAILED: fixture missing at {FIXTURE} — run capture first")
        return 1
    expected = json.loads(FIXTURE.read_text())
    actual = compute_baseline()
    failures: list[str] = []

    exp_counts, act_counts = expected["row_counts"], actual["row_counts"]
    for name in sorted(set(exp_counts) | set(act_counts)):
        e, a = exp_counts.get(name), act_counts.get(name)
        if name not in exp_counts:
            # Table added by a migration since the baseline — additive schema
            # changes are expected between phases; only data drift is a failure.
            print(f"  note: new table since baseline: {name} ({a} rows)")
            continue
        if e != a:
            failures.append(f"row_counts.{name}: expected {e}, got {a}")

    exp_metrics, act_metrics = expected["metrics"], actual["metrics"]
    for key in sorted(set(exp_metrics) | set(act_metrics)):
        e, a = exp_metrics.get(key), act_metrics.get(key)
        if e != a:
            failures.append(f"metrics.{key}: expected {e}, got {a}")

    if failures:
        print(f"FAILED: {len(failures)} drift(s) vs baseline ({expected['_meta']['captured_at']}):")
        for f in failures:
            print(f"  {f}")
        return 1
    print(f"PARITY OK: {len(act_counts)} tables and {len(act_metrics)} metrics match baseline {expected['_meta']['git_rev']}")
    return 0


if __name__ == "__main__":
    sys.exit(check() if "--check" in sys.argv else capture())
