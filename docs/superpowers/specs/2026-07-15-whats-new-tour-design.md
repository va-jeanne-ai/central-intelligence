# Design — "What's new" hub + per-page feature tours

**Date:** 2026-07-15
**Audience:** Greg and his team (client end-users). Plain language, no internals.
**Status:** approved by Jeanne (brainstorming session 2026-07-15)

## Purpose

Recent releases shipped four user-facing features (Analyze with AI, marketing
copy actions, calendar date picker, data freshness / Sync now) that users can
easily miss. This adds an in-app interactive walkthrough: a "What's new"
dialog that lists the features and launches a short spotlight tour on each
feature's own page.

## Decisions (from brainstorming)

| Question | Decision |
|---|---|
| Tutorial form | In-app interactive tour (not a doc or video) |
| Tour shape | "What's new" hub dialog + per-page mini-tours — no cross-page choreography |
| Tour engine | driver.js (~5kB, zero deps), lazy-imported, popover skinned to match the design system |
| Persistence | localStorage, matching the existing page-size-prefs pattern |
| Re-entry | Sidebar footer "What's new" item (sparkle icon), always available |

## Architecture

Three new units under `frontend/src/`, plus anchor attributes on existing
elements:

- **`lib/tours.ts`** — data-only module. Exports `TOURS_VERSION` (e.g.
  `"2026-07"`) and the four tour definitions: `{ id, title, blurb, route,
  steps: [{ anchor, title, body }] }`. `anchor` is a `data-tour` attribute
  value, never a CSS class.
- **`components/tour/WhatsNewDialog.tsx`** — custom modal (Card/Button atoms;
  native dialogs are banned by project rules) listing the tours with blurbs
  and a "Show me" button each. "Show me" writes
  `sessionStorage.pendingTour = <id>` and `router.push(route)`, then closes.
- **`components/tour/TourProvider.tsx`** — mounted once in the `(app)`
  layout. Responsibilities:
  1. On first visit per release (`localStorage["ci.whatsnew.seen." +
     TOURS_VERSION]` unset), open `WhatsNewDialog` and set the key.
  2. On route change, check `sessionStorage.pendingTour`; if set and it
     matches the current route, clear it, wait for the tour's first anchor to
     exist (poll with ~5s timeout), lazy-import driver.js, and run the tour.
- **`components/tour/useFeatureTour.ts`** — thin hook wrapping driver.js:
  maps our step shape to driver steps, applies the skinned popover class,
  filters out steps whose anchor is absent from the DOM.

Sidebar footer gains a "What's new" entry (sparkle icon, matching
`sparkle-icon.tsx` introduced in #43) that opens the dialog on demand.

## The four tours

1. **Analyze with AI** — runs on `/leads`. Steps: (a) spotlight the sparkle
   "Analyze with AI" button — explain it analyzes *the currently filtered
   list*; (b) explain the drawer contents (narrative, highlights, "show the
   data"); (c) note the same button exists on Appointments, Sales Calls, and
   Members. The tour NEVER auto-clicks the button — every click is a paid
   LLM call.
2. **Marketing copy actions** — runs on `/marketing/social/scripts` (the
   generators share `generated-output.tsx`, so one page demonstrates all).
   Steps: (a) the
   generated-output panel renders formatted text now; (b) Copy text / Copy
   Markdown buttons. The copy buttons only exist after a generation, so their
   step skips gracefully when absent.
3. **Calendar date picker** — runs on `/appointments`. One or two steps on
   the jump-to-date toolbar control.
4. **Data freshness + Sync now** — runs on `/integrations`. Steps: (a) the
   "Check data freshness" button and what fresh/stale means; (b) "Sync WGR
   now" for when data looks behind.

## Anchors

Add `data-tour="…"` attributes to roughly six existing elements (analyze
button, generator output panel, copy buttons, date-picker control, freshness
button, sync button). Stable, grep-able, and invisible to styling.

## Edge handling

- Anchor never appears (feature hidden, empty state) → step is filtered out;
  if a tour's every step is missing, show a small toast ("This feature isn't
  visible on this page right now") instead of a broken tour.
- Element off-screen → driver.js scrolls it into view; repositions on resize.
- Mobile → dialog works as normal; tours run but are desktop-first.
- `pendingTour` for a route the user never reaches → sessionStorage clears on
  tab close; harmless.

## Explicitly out of scope

- Backend persistence of seen-state (localStorage only; per-device is fine).
- Auto-clicking or demoing the Analyze drawer with a real LLM call.
- Cross-page continuous tours.
- Analytics on tour completion.

## Verification

- `npm run build` must pass clean (this is the Vercel deploy gate — see
  2026-07-15 incident: lint errors silently blocked production deploys).
- Unit test for the pure parts: step-filtering logic in `useFeatureTour`
  (absent anchors dropped), seen-key versioning.
- Test doc `docs/testing/2026-07-15-whats-new-tour-test.md` in the
  FEATURE-VERIFICATION style: T1 first-visit auto-open, T2 each of the four
  tours end-to-end, T3 relaunch from sidebar, T4 skip-when-hidden behavior.
