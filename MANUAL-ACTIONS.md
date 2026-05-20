# Manual Actions Required

Items that need your intervention. Claude will update this file as new action items arise.

---

## Pending

### 1. Credential Rotation
**When**: Before any deployment or sharing
**Why**: `.env` files contain live keys. Even though they're git-ignored, rotation is good hygiene after initial setup.
**What to do**:
1. Rotate your Anthropic API key in the [Anthropic Console](https://console.anthropic.com)
2. Reset your Supabase project's JWT secret and anon key in Supabase Dashboard → Settings → API
3. Change your Supabase Postgres password in Dashboard → Settings → Database
4. Update `backend/.env` and `frontend/.env.local` with the new values
**Status**: Pending.

### 2. Add OpenAI API Key
**When**: Before using the Transcriber (audio-to-text)
**What to do**:
1. Get an API key from [OpenAI Platform](https://platform.openai.com/api-keys)
2. Add to `backend/.env`: `OPENAI_API_KEY=sk-...`
**Impact if skipped**: Transcriber falls back to mock mode with placeholder transcripts.
**Status**: Missing from `.env`.

### 3. Install FFmpeg (System Dependency)
**When**: Before using audio transcription
**What to do**:
- **macOS**: `brew install ffmpeg`
- **Ubuntu/Debian**: `apt-get install ffmpeg`
- **Windows**: `choco install ffmpeg`
- Verify: `ffmpeg -version`
**Why**: `pydub` (used by TranscriberOperator) requires FFmpeg for audio format conversion.
**Status**: Pending.

### 4. Install and Start Redis
**When**: Before running Celery background tasks (transcription, ICP generation)
**What to do**:
- **macOS**: `brew install redis && brew services start redis`
- **Ubuntu**: `apt-get install redis-server && systemctl start redis`
- Default URL `redis://localhost:6379/0` is used if `REDIS_URL` not set in `.env`
**Impact if skipped**: Celery worker and background tasks will fail to start.
**Status**: Pending.

### 5. Run Alembic Migrations
**When**: Before connecting to a real database
**What to do**:
1. Ensure `DATABASE_URL` is set in `backend/.env` pointing to your Supabase Postgres
2. Run: `cd backend && alembic upgrade head`
**Note**: No migration files exist yet in `backend/alembic/versions/` (only `.gitkeep`). You may need to generate the initial migration first: `alembic revision --autogenerate -m "initial schema"`
**Status**: Waiting on database setup.

### 6. Create a Supabase Auth User
**When**: To test real login (not mock mode)
**What to do**:
1. Go to Supabase Dashboard → Authentication → Users
2. Click "Add user" → create a user with email/password
3. Use those credentials to log in at `http://localhost:3000/login`
**Status**: Ready once Supabase credentials are configured.

### 7. Fix Invalid Claude Model References
**When**: Now — these will cause runtime errors
**What to do**:
Two files reference `claude-sonnet-4-6` which is not a valid model ID:
1. `backend/app/agents/directors/marketing.py` (line ~64) — change to `claude-sonnet-4-5-20250514`
2. `backend/app/tasks/icp.py` — change to `claude-sonnet-4-5-20250514`

Additionally, CentralIntelligence uses an outdated model:
3. `backend/app/agents/central_intelligence.py` (line ~187) — currently `claude-3-haiku-20240307`, upgrade to `claude-haiku-4-5-20251001`

**Current model versions across the codebase**:
| File | Current Model | Recommended |
|------|--------------|-------------|
| `agents/base.py` | `claude-sonnet-4-5-20250514` | OK |
| `agents/central_intelligence.py` | `claude-3-haiku-20240307` | `claude-haiku-4-5-20251001` |
| `agents/specialists/base.py` | `claude-haiku-4-5-20251001` | OK |
| `agents/directors/base.py` | `claude-sonnet-4-5-20250514` | OK |
| `agents/directors/marketing.py` | `claude-sonnet-4-6` (INVALID) | `claude-sonnet-4-5-20250514` |
| `agents/operators/transcriber.py` | `claude-sonnet-4-5-20250514` | OK |
| `tasks/icp.py` | `claude-sonnet-4-6` (INVALID) | `claude-sonnet-4-5-20250514` |

**Status**: Two invalid model IDs will cause API errors. One outdated model works but costs efficiency.

### 8. Start Celery Worker + Beat (Development)
**When**: Before testing transcription, ICP generation, or any scheduled marketing-stats refresh
**What to do**:
1. Ensure Redis is running (see item 4)
2. **Worker** — in a separate terminal: `cd backend && ./scripts/start-celery-worker.sh`
   Processes `app.tasks.transcriber`, `app.tasks.icp`, `app.tasks.offer_generator`, and any scheduled marketing-stats task once beat dispatches it.
3. **Beat (scheduler)** — in ANOTHER separate terminal: `cd backend && ./scripts/start-celery-beat.sh`
   Beat enqueues the 5 scheduled tasks per the `beat_schedule` in `app/tasks/celery_app.py`:
   - `update_funnel_stats` — every hour at :05
   - `update_social_stats` / `update_email_stats` / `update_ads_stats` — every 6 hours (staggered :10/:15/:20)
   - `collect_social_comments` — every 4 hours at :25
**Manually trigger a single task** (useful to verify without waiting for cron): `cd backend && ./scripts/trigger-task.sh <funnel|social|email|ads|comments>`
**Note**: Worker and beat MUST be separate processes. Do not pass `-B` to the worker outside dev. Default beat scheduler writes `celerybeat-schedule` to the current directory — gitignored.
**Status**: Manual process each dev session.

### 9. Update Frontend URLs for Production
**When**: Before deploying to production
**What to do**:
Edit `frontend/.env.local`:
```
NEXT_PUBLIC_API_URL=https://api.yourdomain.com/api/v1
NEXT_PUBLIC_WS_URL=wss://api.yourdomain.com/ws/v1
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJ...
```
Also update `CORS_ORIGINS` in `backend/.env` to include the production frontend URL.
**Status**: Currently hardcoded to `localhost`.

### 10. Update Backend CORS for Production
**When**: Before deploying to production
**What to do**:
In `backend/app/config.py` (line ~9), `cors_origins` defaults to `["http://localhost:3000"]`.
Set `CORS_ORIGINS` in `backend/.env` to include your production frontend domain.
**Status**: Localhost only.

### 11. Create Docker Configuration
**When**: Before production deployment
**What to do**:
No Dockerfile or docker-compose.yml exists yet. You'll need:
- `Dockerfile` for backend (FastAPI + Celery)
- `Dockerfile` for frontend (Next.js)
- `docker-compose.yml` for local dev (backend, frontend, PostgreSQL, Redis)
**Status**: Not started.

### 12. Verify Python and Node.js Versions
**When**: On fresh machine setup
**What to do**:
- Python 3.11+ required (`python --version`) — per `backend/pyproject.toml`
- Node.js 18+ required — for Next.js 14
**Status**: One-time check.

---

## Completed

_(Items move here once done)_

### Set up Anthropic API Key
**Completed**: 2026-03-30
**What was done**: Added API key to `backend/.env`, set `MOCK_MODE=false`.
