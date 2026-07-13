# Test Doc — "Analyze this view" (2026-07-13)

> **Feature:** On Appointments, Sales Calls, Leads, and Members, an
> "Analyze this view" button opens a drawer with an LLM narrative grounded in
> server-computed aggregates of the currently filtered dataset. Ephemeral —
> nothing is saved; one real LLM call per click.
>
> **Status legend:** ⬜ pending · ✅ pass · ⚠️ partial: <note> · ❌ fail: <note>
>
> **Prereqs:** backend on :8000, frontend on :3000, logged in.
> `ANTHROPIC_API_KEY` must be set in backend/.env — there is NO mock fallback.
> **Cost note:** every Analyze click is one real Claude call.

## T1 — Appointments
- **Status:** ⬜ pending
- **How to locate:** `/appointments` → "Analyze this view" button at the right end of the filter bar.
- **Steps to test:**
  - [ ] Set a date range + a rep filter. Note the list's total count.
  - [ ] Click Analyze. Drawer header shows "Analyzing N appointments" — N equals the list total.
  - [ ] The filter echo names the same status/window/date range/rep you set.
  - [ ] Open "Show the data this is based on": every number in the narrative and
        highlights appears in these tables (counts and percentages).
  - [ ] Hypotheses (if any) are in the amber box and phrased speculatively.
  - [ ] Set a filter combination with zero results → "No data in this view" appears
        instantly (no LLM wait).
  - [ ] Close and reopen the drawer → previous analysis is gone (ephemeral).
- **Rating:** ⬜

## T2 — Sales Calls
- **Status:** ⬜ pending
- **How to locate:** `/sales-calls` → "Analyze this view" in the filter bar.
- **Steps to test:**
  - [ ] Pick a call-result subset + date range. List total = drawer N.
  - [ ] Narrative numbers all verifiable in the data section (incl. avg duration in Extras).
  - [ ] Rep filter: pick a rep, re-run — breakdown "rep" table shows only that rep's aliases.
- **Rating:** ⬜

## T3 — Leads
- **Status:** ⬜ pending
- **How to locate:** `/leads` → "Analyze this view" in the filter bar.
- **Steps to test:**
  - [ ] Filter status = Applications + this week's entry dates. List total = drawer N.
  - [ ] Status breakdown uses DB vocabulary (qualified / appointment-set) — expected, noted in describe.
  - [ ] Weekly series matches the entry-date window you set.
- **Rating:** ⬜

## T4 — Members (team)
- **Status:** ⬜ pending
- **How to locate:** `/members` → "Analyze this view" in the filter bar.
- **Steps to test:**
  - [ ] Filter status = active. Drawer N = number of rows in the directory.
  - [ ] Extras shows total_calls and top 5 reps by calls — spot-check one rep's
        calls count against their directory row.
- **Rating:** ⬜

## T5 — Cross-cutting
- **Status:** ⬜ pending
- **Steps to test:**
  - [ ] Analysis is ephemeral: nothing appears in the DB (`overall_insights` etc. unchanged).
  - [ ] While the drawer loads, the page behind stays usable after closing.
  - [ ] Kill the backend mid-analysis → drawer shows the error state with a Retry button.
  - [ ] Re-run button produces a fresh analysis (may word things differently; numbers identical).
- **Rating:** ⬜

## Regression checks (filter extraction refactor)
- **Status:** ⬜ pending
- **Why:** Tasks 1–3 moved the list endpoints' WHERE-building into
  `app/repositories/list_filters.py`. The lists must behave identically.
- **Steps to test:**
  - [ ] `/appointments`: each filter (status, window, date range, rep, search) still
        constrains the list and the calendar view.
  - [ ] `/sales-calls`: result multi-select, rep, dates, search still work.
  - [ ] `/leads`: status (incl. Applications composite), source, entry dates, search still work.
  - [ ] `/members`: status + search still constrain the directory.
- **Rating:** ⬜
