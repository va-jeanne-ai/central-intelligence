# Deploying Central Intelligence — DigitalOcean droplet + Vercel

The cheapest way to run the **full pipeline** (API + Celery worker + beat + Redis)
always-on: one small DigitalOcean droplet runs everything via docker-compose,
and the Next.js frontend is hosted free on Vercel.

**Cost:** ~$6/mo (droplet) + $0 (Vercel) + $0 (Redis is a local container).

| Piece | Where | Cost |
|-------|-------|------|
| API + worker + beat + Redis + Caddy (HTTPS) | DO droplet (docker-compose) | ~$6/mo |
| Frontend (Next.js) | Vercel | free |
| Postgres/pgvector + auth | Supabase (external) | existing |

Files: [`docker-compose.yml`](docker-compose.yml), [`Caddyfile`](Caddyfile),
[`backend/Dockerfile`](backend/Dockerfile), [`backend/.env.example`](backend/.env.example).

---

## What you need first

1. A **domain** (or subdomain) you control for the API, e.g. `api.yourdomain.com`.
   Caddy needs it to get an HTTPS cert. (No domain? See "No domain?" at the end.)
2. The values from `backend/.env` (DB URL, Supabase, API keys, WGR, Fernet key).
3. A DigitalOcean account and a Vercel account.

---

## Part A — The backend droplet

### 1. Create the droplet
DigitalOcean → Create → Droplet:
- **Image:** Ubuntu 24.04 LTS
- **Plan:** Basic → Regular → **$6/mo** (1 GB RAM / 1 vCPU / 25 GB). This is enough
  for staging; bump to the $12 (2 GB) tier if the worker + Whisper transcription
  get memory-hungry under real load.
- **Auth:** add your SSH key (easiest) or a password.
- Create, and note the droplet's **public IP**.

### 2. Point DNS at it
At your DNS provider, add an **A record**: `api.yourdomain.com` → `<droplet IP>`.
Wait until `dig +short api.yourdomain.com` returns the IP (usually minutes).
**Do this before step 6** or the TLS cert challenge fails.

### 3. SSH in and install Docker
```bash
ssh root@<droplet IP>
curl -fsSL https://get.docker.com | sh          # installs Docker + compose plugin
```

### 4. Get the code onto the droplet
```bash
apt-get update && apt-get install -y git
git clone https://github.com/VAPhilippines/greg_central-intelligence.git
cd greg_central-intelligence
```
(For a private repo, use a deploy token/SSH key, or `scp` the folder up.)

### 5. Create backend/.env on the droplet
`.env` is gitignored, so it is NOT in the clone. Create it from the template and
fill in real values:
```bash
cp backend/.env.example backend/.env
nano backend/.env
```
Set, at minimum (values from your local `backend/.env`):
- `MOCK_MODE=false`
- `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_JWT_SECRET`
- `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `VOYAGE_API_KEY`
- `INTEGRATIONS_ENCRYPTION_KEY`  (the Fernet key)
- `CLIENT_SYNC_ENABLED=true`, `CLIENT_SUPABASE_URL`, `CLIENT_SUPABASE_ANON_KEY`, `WGR_DATABASE_URL`
- `API_DOMAIN=api.yourdomain.com`   ← the domain from step 2
- `PUBLIC_API_BASE_URL=https://api.yourdomain.com`
- `CORS_ORIGINS=["https://<your-vercel-domain>.vercel.app"]`  ← set after Part B,
  or put a best guess now and edit later.

Do NOT set `REDIS_URL` — compose points it at the local Redis container.

### 6. Launch
```bash
docker compose up -d --build
```
This builds the backend image, runs migrations once (`migrate` service), then
starts redis, api, worker, beat, and Caddy. Caddy fetches the HTTPS cert for
`API_DOMAIN` automatically.

### 7. Verify the backend
```bash
docker compose ps                       # all services "running"/"healthy"
curl https://api.yourdomain.com/api/v1/health     # HTTP 200, database healthy
docker compose logs -f beat             # see it enqueue scheduled tasks
docker compose logs -f worker           # see it consume them
```
Open `https://api.yourdomain.com/docs` in a browser for the API docs.

---

## Part B — The frontend on Vercel

1. Vercel → **Add New → Project** → import `VAPhilippines/greg_central-intelligence`.
2. **Root Directory:** set to `frontend` (this repo is a monorepo; Vercel must
   build from the frontend subfolder). Framework auto-detects as Next.js.
3. **Environment Variables** (Project Settings → Environment Variables):
   - `NEXT_PUBLIC_API_URL` = `https://api.yourdomain.com/api/v1`
   - `NEXT_PUBLIC_WS_URL` = `wss://api.yourdomain.com/ws/v1`
   - `NEXT_PUBLIC_SUPABASE_URL` = *(same as backend SUPABASE_URL)*
   - `NEXT_PUBLIC_SUPABASE_ANON_KEY` = *(same as backend SUPABASE_ANON_KEY)*
4. **Deploy.** Vercel gives you a URL like `https://central-intelligence.vercel.app`.
5. **Close the CORS loop:** put that Vercel URL into `CORS_ORIGINS` in
   `backend/.env` on the droplet, then `docker compose up -d` (recreates api).

> `NEXT_PUBLIC_*` are baked in at build time. If you change them later, redeploy
> the Vercel project (a plain restart won't pick them up).

---

## Updating after a code change
On the droplet:
```bash
cd greg_central-intelligence && git pull
docker compose up -d --build            # rebuilds + reruns migrations, zero-config
```
Vercel redeploys the frontend automatically on every push to the tracked branch.

## Cost & data awareness
- Full pipeline runs live: paid Claude/OpenAI/Voyage calls, real client data,
  WGR sync against the client's DB (opened READ ONLY). Same as before — just a
  cheaper host.
- Migrations run against the **live** Supabase app DB on every `up`.
- `INTEGRATIONS_ENCRYPTION_KEY` must stay constant, or stored integration creds
  won't decrypt.

## No domain? (skip HTTPS)
Caddy needs a domain for a cert. To test without one, you can temporarily expose
the API on the droplet IP over plain HTTP: remove the `caddy` service, publish
`api`'s port (`ports: ["8000:8000"]`), and set the frontend to
`http://<droplet IP>:8000/...`. Note: browsers block `ws://`+`https://` mixing,
and Vercel is HTTPS — so for a real demo you DO want a domain + Caddy. Cheapest
path: a $1/yr-ish domain or a free subdomain from a dynamic-DNS provider.

## Firewall (recommended)
```bash
ufw allow OpenSSH && ufw allow 80 && ufw allow 443 && ufw --force enable
```
Redis is not published to the host, so it stays private to the compose network.
