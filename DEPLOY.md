# Deploying Central Intelligence to Render (Staging)

This is the runbook for standing up a **staging** environment on Render. It
provisions the whole stack from one blueprint:

| Service       | Type       | What it runs                              |
|---------------|------------|-------------------------------------------|
| `ci-backend`  | web        | FastAPI + WebSockets (uvicorn)            |
| `ci-worker`   | worker     | Celery worker (background tasks)          |
| `ci-beat`     | worker     | Celery beat (scheduler)                   |
| `ci-redis`    | redis      | Celery broker + result backend            |
| `ci-frontend` | web (node) | Next.js                                   |

**Not provisioned here** (external, already hosted on Supabase):
Postgres/pgvector app DB and Supabase auth.

Everything is defined in [`render.yaml`](render.yaml).

---

## Prerequisites

1. A Render account with access to Blueprints.
2. The repo pushed to a Git remote Render can read (GitHub/GitLab). Render deploys
   from a branch — it does not read your local working tree.
3. A **staging Supabase project** for the app DB + auth. You can reuse the existing
   project for a first pass, but a separate staging project is safer (staging
   migrations/writes won't touch prod). Have ready:
   - `DATABASE_URL` (asyncpg scheme, pooler host, URL-encoded password)
   - `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_JWT_SECRET`

---

## Step 1 — Push the deploy files

The following were added and must be committed/pushed:

- `render.yaml`
- `backend/.env.example`, `backend/.python-version`
- `frontend/.env.example`
- `DEPLOY.md` (this file)

`.env` files themselves are gitignored and never pushed — set real secrets in the
Render dashboard (Step 3).

## Step 2 — Create the Blueprint

1. Render Dashboard → **New** → **Blueprint**.
2. Select this repo + the branch you pushed to.
3. Render reads `render.yaml` and shows the five services. Approve.

`autoDeploy: false` is set on every service, so nothing goes live until you finish
wiring env vars and trigger the first deploy manually. That's intentional for a
controlled first launch.

## Step 3 — Set the secrets (`sync: false` vars)

Render will prompt for every var marked `sync: false`. `REDIS_URL` is wired
automatically from `ci-redis`; you do **not** set it by hand.

> **This environment runs with `MOCK_MODE=false`** — it serves the client's real
> data and makes **paid** Claude/OpenAI/Voyage calls. Reuse the production keys /
> DB from `backend/.env`. All of the following are required.

On **`ci-backend`, `ci-worker`, `ci-beat`**:
- `DATABASE_URL`
- `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_JWT_SECRET`
- `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `VOYAGE_API_KEY`
- `INTEGRATIONS_ENCRYPTION_KEY` — the SAME Fernet key already in use (reuse the
  one from prod `.env`; a new key won't decrypt existing stored credentials).

On **`ci-backend`** additionally:
- `CORS_ORIGINS` — the frontend URL as a JSON array once known, e.g.
  `["https://ci-frontend.onrender.com"]` (see Step 5).
- `PUBLIC_API_BASE_URL` — the backend's own URL, e.g. `https://ci-backend.onrender.com`.

On **`ci-backend` + `ci-worker`** (for the client's WGR data sync, `CLIENT_SYNC_ENABLED=true`):
- `CLIENT_SUPABASE_URL`, `CLIENT_SUPABASE_ANON_KEY`
- `WGR_DATABASE_URL` — **READ-ONLY use only** (client's writable `postgres` role).

On **`ci-frontend`**:
- `NEXT_PUBLIC_API_URL` — `https://ci-backend.onrender.com/api/v1`
- `NEXT_PUBLIC_WS_URL` — `wss://ci-backend.onrender.com/ws/v1`
- `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY` — match the backend's.

Optional (blank → seed fallback): `MAILCHIMP_API_KEY`, `GOOGLE_OAUTH_*`.

> **Chicken-and-egg on URLs:** you won't know the exact `.onrender.com` hostnames
> until services exist. Do a first deploy with best-guess values, note the real
> URLs Render assigns, then update `CORS_ORIGINS` / `NEXT_PUBLIC_API_URL` /
> `NEXT_PUBLIC_WS_URL` / `PUBLIC_API_BASE_URL` and redeploy. The frontend must be
> **rebuilt** after changing `NEXT_PUBLIC_*` (they're baked in at build time).

## Step 4 — First deploy

Trigger a manual deploy on each service (or "Deploy" the whole blueprint). Order
doesn't strictly matter, but `ci-redis` should be healthy before the workers.

- `ci-backend` build runs `pip install -r requirements.txt`; its
  **preDeployCommand** runs `alembic upgrade head` once (migrations run only here,
  not on the workers, to avoid a race).
- Watch each service's logs for a clean start.

## Step 5 — Verify

1. **Backend health:** `curl https://ci-backend.onrender.com/api/v1/health` →
   HTTP 200 with `database` healthy.
2. **API docs:** open `https://ci-backend.onrender.com/docs`.
3. **Frontend:** open `https://ci-frontend.onrender.com` — the dashboard should
   load with seed data.
4. **Worker/beat:** check `ci-beat` logs show it enqueuing tasks and `ci-worker`
   logs show it consuming them (e.g. the `embed-queue-drain` every 2 min).
5. **CORS/WS:** in the browser devtools, confirm API calls to `ci-backend` succeed
   (no CORS error) and the WebSocket connects. If CORS fails, fix `CORS_ORIGINS`
   on `ci-backend` and redeploy.

---

## Cost & data awareness (this env is live)

- `MOCK_MODE=false` means the app issues **paid** Claude/OpenAI/Voyage calls —
  including the daily `overall-insight` task and RAG embedding of every synced
  document. Watch spend after the first full sync cycle.
- It reuses the **production** Supabase DB and API keys, so this "staging" env is
  effectively production-grade. Migrations run against the live app DB.
- `INTEGRATIONS_ENCRYPTION_KEY` must match the value already encrypting stored
  credentials — do not rotate casually.
- `WGR_DATABASE_URL` is the client's **writable** `postgres` role; the app opens
  it READ ONLY. Never point a migration or write at it.
- Google OAuth: if you set `GOOGLE_OAUTH_*`, update the redirect URI in Google
  Cloud Console to
  `https://ci-backend.onrender.com/api/v1/integrations/google_workspace/oauth/callback`.

---

## Notes & gotchas

- **Python 3.12** is pinned (`PYTHON_VERSION=3.12.7`). The stack targets >=3.11;
  the `audioop-lts` backport in `requirements.txt` only installs on 3.13+, so on
  3.12 the stdlib `audioop` is used. Don't bump Render to 3.13 without testing.
- **Beat scheduler state** is stored at `/tmp/celerybeat-schedule` and resets on
  redeploy. That's fine — every scheduled task is idempotent (upsert semantics).
  For durable scheduling later, switch beat to RedBeat (backed by `ci-redis`).
- **NullPool + Supabase pooler:** the DB engine uses `NullPool` and connects
  through Supabase's pgbouncer pooler — correct, no extra tuning needed.
- **Free/starter plans sleep:** on low tiers, the backend may cold-start. If the
  frontend's first request times out, retry after the backend wakes.
- **Secrets hygiene:** never commit `.env`. If a key is ever exposed, rotate it in
  the provider console and update the Render var.
