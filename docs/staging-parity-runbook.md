# Staging Parity Runbook — protecting Greg's instance during productization

Every productization phase (instance profile, prompt templating, sync engine,
configurable directors, …) must prove it changes **nothing** for the current
client before it reaches production. This runbook is that gate.

## The three parity checks

| Check | What it freezes | How to run (from `backend/`) |
|---|---|---|
| Prompt snapshots | Every module-level prompt constant (32 constants, 24 modules) | `PYTHONPATH=. .venv/bin/python -m tests.parity.test_prompt_snapshots` |
| Row counts | COUNT(*) for all 62 ORM tables | `PYTHONPATH=. .venv/bin/python -m scripts.capture_parity_baseline --check` |
| Metric values | All registry metrics' (value, sample_size) over fixed windows (all-time + since 2026-06-01) | same command as row counts |

Fixtures live in `backend/tests/parity/fixtures/`. The baseline production
state is tagged **`v1.0-greg-baseline`**.

- Prompt snapshots are **data-independent** — they must pass on any checkout,
  any machine, no DB needed. Run them on every branch before merging.
- Row counts / metric values are **data-dependent** — the live DB drifts by
  design (hourly WGR sync). A `--check` is only meaningful against a frozen
  copy of the data, which is what the staging procedure below provides.

## Creating a staging clone

Local restore of a production dump (preferred — cheap, disposable):

1. **Dump the app DB** (read-only; use the transaction pooler, port 6543):
   `pg_dump "$PARITY_DATABASE_URL" -Fc -f .tmp/ci_prod.dump`
2. **Restore locally** into Postgres 15+ with pgvector:
   `createdb ci_staging && pg_restore -d ci_staging --no-owner .tmp/ci_prod.dump`
3. **Point a staging env at it** — copy `backend/.env` to `backend/.env.staging`
   and edit, then run the API/scripts with it. Required overrides:
   - `DATABASE_URL` → the local `ci_staging` DB
   - `CLIENT_SYNC_ENABLED=false` (never sync into staging)
   - `INTEGRATIONS_ENCRYPTION_KEY` → a **freshly generated** Fernet key, so the
     restored third-party credentials are unreadable and no job can
     accidentally call Mailchimp/Meta/Google from staging
   - `MOCK_MODE=true` unless a test explicitly needs live LLM calls (keeps
     Anthropic/Voyage spend at zero)

Alternative when full-stack behavior matters (Caddy, compose, beat): snapshot
the DO droplet and restore the snapshot to a throwaway droplet, then apply the
same env overrides there. Destroy it when done.

## Release gate procedure (per phase)

1. On the staging clone, **refresh the data fixtures against the old code**:
   check out the last released tag (first time: `v1.0-greg-baseline`), then
   `PYTHONPATH=. .venv/bin/python -m scripts.capture_parity_baseline`
   with `PARITY_DATABASE_URL` pointing at the staging DB. This freezes what
   "unchanged" means for this data snapshot.
2. **Check out the release-candidate branch** (same staging DB) and run:
   - `python -m tests.parity.test_prompt_snapshots` — prompts identical
     (or intentionally regenerated in the same PR, with the diff reviewed)
   - `python -m scripts.capture_parity_baseline --check` — counts + metrics
     identical
   - the full test suite (`for f in tests/test_*.py; do ...` — see CI habits)
   - chat smoke test: ask the orchestrator + each director one real business
     question; answers must cite the same numbers as before
3. Only on green: tag the release, merge to org `main`, sync the `va-jeanne-ai`
   mirror, redeploy the droplet, verify Vercel shows **Ready** (frontend
   deploys fail silently on lint — run `npm run build` locally first).

## When a parity change is intentional

A phase that *means* to change something (e.g. Phase 1 moves a benchmark
sentence between prompt files) regenerates the affected fixture **in the same
PR** (`UPDATE_PARITY_FIXTURES=1 ... test_prompt_snapshots`), and the fixture
diff is reviewed like code — the diff IS the proof of exactly what changed.
