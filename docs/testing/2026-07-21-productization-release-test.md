# Test doc — Productization release (phases 1–2 + pooler hardening)

**Date:** 2026-07-21
**Release:** PR #52 (`staging` → `main`, merge `df3e60a`)

## Feature / fix under test

This release makes CI multi-company-ready without changing anything for the
current instance. That means most of this doc verifies **parity** — the app
behaving exactly as it did before — plus one genuinely new surface
(Settings → Business) and the pooler fixes behind the recent outage.

What shipped:

1. **Phase 1 (backend)** — `instance_profile` table + all 19 prompt modules
   templated (vertical/app-name/expertise slots). Defaults render
   byte-identical to the old hardcoded prompts.
2. **Phase 1 (frontend)** — white-label branding: `useBranding()` hook,
   sidebar/login render from the branding API, `formatCurrency()`, new
   **Settings → Business** page.
3. **Phase 2** — instance provisioning + fresh-instance safety (cost guard on
   `overall_insight`). Provisioning itself is NOT testable on this instance —
   it's for new droplets; skip it here.
4. **Pooler hardening** — Celery `worker_concurrency=2` default; settings
   tolerate unknown `.env` keys; `CLIENT_DATABASE_URL` rename (backward
   compatible with `WGR_DATABASE_URL`).

## How to locate

1. Open the deployed app: https://central-intelligence-one.vercel.app
2. Log in with your admin account.
3. Confirm the Vercel deployment for merge `df3e60a` shows **Ready** in the
   Vercel dashboard first — a lint failure deploys nothing and everything
   below would silently test the old build.
4. Droplet API must be on the release too: `curl https://137-184-240-114.sslip.io/api/v1/health`
   should show `uptime` under the time since the redeploy (a multi-hour uptime
   means the old container is still running).

## Test steps

### 1. Branding parity — the app should look EXACTLY as before

1. Load the login page in a fresh incognito window (pre-auth — this exercises
   the public `GET /api/v1/config/branding` endpoint).
2. Log in; look at the sidebar header.

**Pass:** login page and sidebar show the same name/tagline/🧠 logo as before
the release. No flash of missing branding on first paint.
**Fail:** placeholder text (`{{app_name}}` or blank), a broken logo image, or
any visual difference from the pre-release app.

### 2. AI output parity — prompts unchanged on this instance

1. Open CI chat, ask a normal cross-department question you'd ask on any day.
2. Open a lead → run **Analyze with AI**.
3. If a daily overall insight exists for today (Insights page), read it.

**Pass:** responses are the usual quality/format and reference this business's
real data — vertical-specific language intact (nothing generic like
"your industry"), no literal `{{tokens}}` anywhere in output.
**Fail:** any `{{vertical}}`/`{{app_name}}` token visible, generic-sounding
prompts, or an analysis that reads differently in structure from last week's.

### 3. Settings → Business (new page)

1. Sidebar → Settings → **Business** (new entry beside Integrations).
2. Confirm the form is pre-filled with this instance's real profile values.
3. Change **tagline** to a test value, save, hard-refresh: sidebar shows the
   new tagline.
4. Change it back, save, hard-refresh: original restored.
5. (If you have a non-admin test account) log in with it and try to save on
   this page.

**Pass:** loads pre-filled, saves stick across hard refresh, revert works,
non-admin save is rejected with a toast (not a crash or silent success).
**Fail:** empty form on load, save doesn't persist, or non-admin can write.

### 4. Currency formatting parity (Insights)

1. Open Insights; find the money metrics (deal value, revenue figures).

**Pass:** amounts render with `$` exactly as before (same separators/decimals).
**Fail:** bare numbers, wrong symbol, or `undefined`.

### 5. Cost guard must NOT fire on this instance (it has data)

1. Insights page → confirm today's/yesterday's overall insight exists or can
   be refreshed.
2. Trigger a manual insight refresh.

**Pass:** refresh works normally — this instance has evidence, so the new
`has_evidence()` gate must not block it. A generated assessment appears.
**Fail:** a 409 "no evidence" response here — that means the gate misfires on
real data (it must only fire on empty instances).

### 6. Pooler regression check (EMAXCONNSESSION)

1. Open Insights and hard-refresh (Cmd+Shift+R) 3–5 times in quick
   succession, dev console open (Console + Network filtered to `history-asof`).
2. Integrations page → **Check data freshness**, then **Sync WGR now**; wait
   for the spinner to clear.

**Pass:** all requests 200, zero CORS errors, sync completes with a row count
("Done — N row(s) synced").
**Fail:** any CORS-policy console error, any 500/502, or
`Sync failed: (EMAXCONNSESSION)...` — if seen, check droplet `.env`
`DATABASE_URL` port (must be 6543) before anything else.

### 7. WGR sync backward compatibility (env rename)

The droplet `.env` may still use the legacy `WGR_DATABASE_URL` name — that
must keep working.

1. After the sync in step 6 completes, check the freshness panel shows
   `wgr_sync` with a timestamp from just now.

**Pass:** sync ran and freshness updated regardless of which env name the
droplet uses.
**Fail:** "CLIENT_DATABASE_URL is not set" in a sync error — the alias broke.

## Automated coverage

- `backend/tests/parity/test_prompt_snapshots.py` — all 32 prompt constants
  byte-identical to the frozen fixture (the release's core parity proof).
- `backend/tests/test_prompt_context.py` — no leftover `{{tokens}}`; profile
  swap changes rendering; NULL profile fields keep defaults.
- `backend/scripts/capture_parity_baseline.py --check` — table counts +
  registry metrics vs the `v1.0-greg-baseline` tag (run against a staging
  clone, not production).

## Note for deploy

Steps 6–7 are only meaningful on the redeployed droplet (fresh `docker compose
up -d --build` after merge `df3e60a`, with `DATABASE_URL` moved to the
transaction pooler `:6543`). Verify the droplet uptime is fresh before
starting, or you're testing yesterday's build.
