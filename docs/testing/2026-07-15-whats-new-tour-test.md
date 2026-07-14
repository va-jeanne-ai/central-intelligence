# Test Doc — In-app "What's new" tour (2026-07-15)

> **Feature:** A "What's new in Central Intelligence" hub dialog auto-opens
> once per release (localStorage-gated, version `2026-07`) and lists the
> current batch of features with a "Show me" button each. "Show me" navigates
> to the feature's page and runs a short driver.js spotlight tour anchored on
> `data-tour` attributes. The hub is relaunchable anytime from a sparkle
> button in the sidebar footer. Tour steps skip gracefully (falling back to
> an info toast) when their target UI isn't on screen.
>
> **Status legend:** ⬜ pending · ✅ pass · ⚠️ partial: <note> · ❌ fail: <note>
>
> **Prereqs:** backend on :8000, frontend on :3000, logged in.
> DevTools open to Application → Local Storage → your app origin (to inspect/
> clear `ci.whatsnew.seen.2026-07`).

## T1 — First-visit auto-open
- **Status:** ⬜ pending
- **How to locate:** DevTools → Application → Local Storage → delete the key
  `ci.whatsnew.seen.2026-07` → reload any app page.
- **Steps to test:**
  - [ ] With the key cleared, reload any logged-in page. The "What's new in
        Central Intelligence" dialog auto-opens (sparkle icon in the header,
        four feature rows each with a "Show me" button, "Close" in the footer).
  - [ ] Close the dialog (Close button, Escape key, or backdrop click all work).
  - [ ] Reload the page again. The dialog does **not** reappear (the seen-key
        was written back on the first open).
  - [ ] Re-check Local Storage: `ci.whatsnew.seen.2026-07` now holds an ISO
        timestamp string.
- **Rating:** ⬜

## T2 — The four tours end-to-end via "Show me"
- **Status:** ⬜ pending
- **How to locate:** Open the hub dialog (sparkle icon, sidebar footer, or a
  fresh first-visit auto-open per T1) → click "Show me" on each row in turn.

### T2a — Analyze with AI
- [ ] Click "Show me" on "Analyze any list with AI". Browser navigates to `/leads`.
- [ ] Tour spotlights the gold "Analyze with AI" button — 3 steps total
      (progress indicator shows, e.g., "1/3"): "Analyze any list with AI" →
      "What you get" → "It's on four pages".
- [ ] The tour never auto-clicks the Analyze button or opens the analysis
      drawer — it only highlights it.
- [ ] "Next"/"Back"/"Done" buttons navigate the 3 steps; "Done" closes the tour.

### T2b — Marketing copy actions
- [ ] Click "Show me" on "Formatted content you can copy anywhere". Browser
      navigates to `/marketing/social/scripts`.
- [ ] Generate a script/content first (so `generated-output` and
      `copy-actions` anchors exist in the DOM).
- [ ] Tour spotlights the generated output block ("Cleaner generated
      content") then the copy buttons ("Copy it your way" — mentions "Copy
      text" for clean text and "Copy Markdown" for formatting).
- [ ] "Done" closes the tour after step 2.

### T2c — Calendar date picker
- [ ] Click "Show me" on "Jump to any date on the calendar". Browser
      navigates to `/appointments`.
- [ ] Switch to calendar view (if not already there).
- [ ] Tour spotlights the jump-to-date picker — single step: "Jump straight
      to a date".

### T2d — Data freshness
- [ ] Click "Show me" on "Check data freshness & sync on demand". Browser
      navigates to `/integrations`.
- [ ] Tour runs 2 steps: "Is the data current?" (spotlights the freshness
      check) then "Pull the latest now" (spotlights the WGR sync-now control).
- **Rating:** ⬜

## T3 — Relaunch from the sidebar
- **Status:** ⬜ pending
- **How to locate:** Sidebar footer, sparkle icon button immediately left of
  the "Sign out" icon (both `title`/`aria-label` on the sparkle button read
  "What's new").
- **Steps to test:**
  - [ ] After the hub has already been dismissed once (T1 done), click the
        sparkle button in the sidebar footer.
  - [ ] The "What's new in Central Intelligence" dialog reopens with all four
        rows, regardless of the localStorage seen-key state.
  - [ ] Close it; confirm the sidebar and page behind remain interactive.
- **Rating:** ⬜

## T4 — Skip-when-hidden
- **Status:** ⬜ pending
- **Steps to test:**
  - [ ] On `/marketing/social/scripts`, with **no** content generated yet
        (fresh page load, `generated-output`/`copy-actions` anchors absent),
        open the hub dialog and click "Show me" on the copy-actions tour.
  - [ ] No spotlight tour appears. Instead an info toast shows: "This
        feature isn't visible on this page right now — try again once it's
        on screen."
  - [ ] On `/appointments` in **list view** (not calendar view), open the hub
        dialog and click "Show me" on the calendar tour.
  - [ ] Same graceful behavior: no tour runs (the `calendar-jump-date` anchor
        isn't in the DOM in list view); the info toast appears instead of an
        error or a broken/stuck spotlight.
- **Rating:** ⬜
