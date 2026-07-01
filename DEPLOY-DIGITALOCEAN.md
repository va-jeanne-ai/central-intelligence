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

1. **No domain needed** — this dev deploy uses **sslip.io**: the hostname
   `<droplet-ip-with-dashes>.sslip.io` resolves to your droplet automatically, so
   Caddy can still get a real Let's Encrypt cert and serve HTTPS + wss (required
   because the Vercel frontend is HTTPS and browsers block HTTPS→HTTP calls).
2. The values from `backend/.env` (DB URL, Supabase, API keys, WGR, Fernet key).
3. A DigitalOcean account and a Vercel account.

---

## Part A — The backend droplet

### 1. Create the droplet
DigitalOcean → Create → Droplet:
- **Image:** Ubuntu 24.04 (LTS) x64
- **Plan:** Basic → Regular → **`s-1vcpu-2gb`** (2 GB RAM / 1 vCPU / 50 GB, ~$12/mo).
  2 GB is the safe floor: `faster-whisper` (call transcription) loads an ML model
  into RAM, and the worker/embeddings/API/beat/Redis all share this one box.
- **Region:** Singapore (SGP1) is a good default for a PH-based client. (The WGR
  sync to the client's US Supabase is a background job and tolerates the latency.)
- **Auth:** add your SSH key.
- Create, and note the droplet's **public IP**.

### 2. Your API hostname (sslip.io — no DNS setup)
Take the droplet IP and replace dots with dashes, then append `.sslip.io`:

    203.0.113.5   →   203-0-113-5.sslip.io

That is your `API_DOMAIN`. It resolves to the droplet automatically — nothing to
configure at a registrar. (Verify: `dig +short 203-0-113-5.sslip.io` returns the IP.)

### 3. SSH in, add swap, install Docker
```bash
ssh root@<droplet IP>

# 2 GB swap — cheap insurance against a transient spike OOM-killing the worker
# mid-transcription.
fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab

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
- `API_DOMAIN=203-0-113-5.sslip.io`   ← your sslip.io hostname from step 2
- `PUBLIC_API_BASE_URL=https://203-0-113-5.sslip.io`
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
docker compose ps                                   # all services "running"/"healthy"
curl https://203-0-113-5.sslip.io/api/v1/health     # HTTP 200, database healthy
docker compose logs -f caddy                        # confirm the cert was issued
docker compose logs -f beat                         # see it enqueue scheduled tasks
docker compose logs -f worker                       # see it consume them
```
Open `https://203-0-113-5.sslip.io/docs` in a browser for the API docs.

---

## Part B — The frontend on Vercel

1. Vercel → **Add New → Project** → import `VAPhilippines/greg_central-intelligence`.
2. **Root Directory:** set to `frontend` (this repo is a monorepo; Vercel must
   build from the frontend subfolder). Framework auto-detects as Next.js.
3. **Environment Variables** (Project Settings → Environment Variables):
   - `NEXT_PUBLIC_API_URL` = `https://203-0-113-5.sslip.io/api/v1`
   - `NEXT_PUBLIC_WS_URL` = `wss://203-0-113-5.sslip.io/ws/v1`
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

## About sslip.io (no-domain HTTPS)
`sslip.io` is a free public wildcard-DNS service: `<ip-with-dashes>.sslip.io`
always resolves to that IP, so Caddy can complete a Let's Encrypt HTTP-01
challenge and serve real HTTPS — which is what lets the HTTPS Vercel frontend
talk to the backend (browsers block HTTPS→HTTP and `wss`→`ws`). It's ideal for a
dev/staging box. If the droplet IP ever changes, update `API_DOMAIN`,
`PUBLIC_API_BASE_URL`, and the Vercel `NEXT_PUBLIC_*` vars, then rebuild both.

If the cert doesn't issue: make sure ports 80 and 443 are open (see firewall
below) and `dig +short <your>.sslip.io` returns the droplet IP before you `up`.

## Firewall (recommended)
```bash
ufw allow OpenSSH && ufw allow 80 && ufw allow 443 && ufw --force enable
```
Redis is not published to the host, so it stays private to the compose network.
