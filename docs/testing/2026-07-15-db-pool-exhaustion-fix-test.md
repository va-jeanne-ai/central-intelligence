# Test doc — DB pool exhaustion fix (EMAXCONNSESSION / "CORS" errors on Insights)

**Date:** 2026-07-15
**Branch:** `fix/db-pool-exhaustion`

## Feature / fix under test

The Insights page (and any page firing many API calls at once) intermittently
failed with browser-console CORS errors and `500 Internal Server Error` on
`/api/v1/analytics/metrics/*/history-asof`. Root cause: the backend used
SQLAlchemy `NullPool`, opening one fresh Supabase session-pooler connection per
request. Supabase caps session-pooler clients at 15 (`EMAXCONNSESSION`), so a
page-load burst exhausted the slots and the excess requests crashed. The crash
response came from outside the CORS middleware, so browsers reported it as a
CORS violation.

Two changes:

1. `backend/app/database.py` — bounded client-side pool (`pool_size=5`,
   `max_overflow=2`, `pool_timeout=30`, `pool_pre_ping`, `pool_recycle=1800`)
   so bursts queue on our side instead of dying at the pooler.
2. `backend/app/middleware/error_envelope.py` — any future unhandled 500 now
   returns the standard JSON error envelope *with* CORS headers, so real
   errors show up as real errors in the browser, never as CORS noise.

## How to locate

1. Open the deployed app: https://central-intelligence-one.vercel.app
2. Log in and go to the **Insights** page (the one with the metric trend charts).
3. Open the browser dev console (F12 → Console + Network tabs) before the page loads.

## Test steps

1. Hard-refresh the Insights page (Cmd+Shift+R) so all metric charts fetch at once.
2. Watch the Network tab, filtered to `history-asof`.
3. Repeat the hard refresh 3–5 times in quick succession (this is what used to
   trigger the failure — it was intermittent, so one clean load is not proof).
4. Optionally open the app in a second tab and refresh both together.

## Pass criteria

- All `history-asof` requests return **200**; charts render on every refresh.
- **Zero** CORS errors in the console.
- No `500 (Internal Server Error)` entries in the Network tab.

## Fail criteria

- Any console line like `blocked by CORS policy: No 'Access-Control-Allow-Origin'`.
- Any `history-asof` request with status 500. (If a 500 ever does occur, it
  should now show a JSON body with `error.code = "INTERNAL_ERROR"` and a
  `requestId` — that requestId is greppable in the droplet's backend logs.)

## Automated coverage

- `backend/tests/test_error_envelope.py` — unhandled exception returns the JSON
  envelope and carries CORS headers (2 tests).
- Manual load reproduction (2026-07-15, pre-fix): 24 concurrent authed requests
  against production → 2–9 × 500. Post-fix, 24 concurrent against a local
  backend on the same Supabase pooler → 24 × 200.

## Note for deploy

The fix needs the droplet backend redeployed (sync the `va-jeanne-ai` mirror
first, per the usual flow). Until then production still has the bug.
