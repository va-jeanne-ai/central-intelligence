# Test Doc — WGR sync: duplicate-email lead merge (2026-07-15)

> **Feature (bugfix):** The WGR → CI sync no longer aborts with
> `UniqueViolationError` on `ix_leads_email` when the client's WGR database
> holds two lead rows with the same email but different `lead_id`s (seen live:
> morrisshort@mac.com). Duplicates now merge into the one existing CI lead —
> latest data wins (freshest `entry_date`), and the CI lead's
> `source`/`external_id`/`email` stay stable so the row doesn't flip-flop
> between the two upstream ids on every run.
>
> **Status legend:** ⬜ pending · ✅ pass · ⚠️ partial: <note> · ❌ fail: <note>
>
> **Prereqs:** backend on :8000, frontend on :3000, logged in.
> `client_sync_enabled` on; worker + beat running (or use the manual button).
> No paid API calls in the sync itself.

## T1 — Manual sync completes without the error
- **Status:** ✅ pass (2026-07-15, ran against live data during the fix — re-verify after deploy)
- **How to locate:** Integrations page → "Sync WGR now" button.
- **Steps to test:**
  - [ ] Click "Sync WGR now" and wait for the running indicator to clear.
  - [ ] The indicator ends in a success message ("Done — N row(s) synced"),
        NOT "Sync failed: … UniqueViolationError … ix_leads_email".
  - [ ] Click "Check data freshness" — WGR sources read fresh, not stale.

## T2 — The duplicated lead is merged, not doubled
- **Status:** ✅ pass (2026-07-15, verified in DB during the fix)
- **How to locate:** `/leads`, search `morrisshort@mac.com`.
- **Steps to test:**
  - [ ] Exactly ONE lead appears for that email (no duplicate row).
  - [ ] Its date reflects the newest upstream entry (2026-07-14), i.e. the
        merge carried the latest data.

## T3 — Sync log records the clean run
- **Status:** ✅ pass (2026-07-15)
- **How to locate:** `sync_log` table (operation = `wgr_sync`), or the
  Integrations page last-sync status.
- **Steps to test:**
  - [ ] Latest `wgr_sync` row has `status = ok` and an advanced watermark.
  - [ ] Subsequent hourly runs stay `ok` (the two other known upstream
        duplicate pairs — mwolfenow@aol.com, gwheeler10@gmail.com — must not
        trip it when their rows next change upstream).

## Unit tests
`cd backend && .venv/bin/python -m tests.test_wgr_lead_email_merge` — 8 cases
covering: merge-by-email routing, identity-key stability, case-insensitive
match, in-batch duplicate collapse (entry_date wins, batch order tie-break),
preserved external_id behavior, null-email rows never collapsing.
