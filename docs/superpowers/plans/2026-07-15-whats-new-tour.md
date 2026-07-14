# "What's new" In-App Tour Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A "What's new" dialog that lists four recent features and launches a short driver.js spotlight tour on each feature's page.

**Architecture:** Data-only tour definitions (`lib/tours.ts`) + pure helpers (`lib/tour-logic.ts`) feed a `useFeatureTour` hook that lazy-imports driver.js. A `TourProvider` in the `(app)` layout auto-opens the dialog once per release (localStorage) and starts a pending tour after navigation (sessionStorage handoff). Anchors are `data-tour` attributes on existing elements.

**Tech Stack:** Next 14.2 / React 18, driver.js (^1.3, runtime dep), vitest (devDep — first frontend test runner in this repo, pure logic only).

**Spec:** `docs/superpowers/specs/2026-07-15-whats-new-tour-design.md`

## Global Constraints

- Branch: `feat/whats-new-tour` (already created; spec committed on it).
- Never call `window.alert/confirm/prompt` — use `@/lib/toast` (`showInfo`) and custom modals (project rule).
- Use UI atoms: `Button` from `@/components/ui/button`, `SparkleIcon` from `@/components/ui/sparkle-icon`.
- The Analyze tour must NEVER auto-click the Analyze button (each click is a paid LLM call).
- `npm run build` must pass clean before every commit that touches `frontend/` — ESLint errors block Vercel production deploys (2026-07-15 incident).
- All new UI is light-mode, matching the webapp mockup conventions (white cards, gray-800 text, accent gold for AI).
- No Claude co-author trailer on commits.
- All paths below are relative to `projects/central-intelligence/`.

---

### Task 1: Tour data + pure logic + vitest

**Files:**
- Create: `frontend/src/lib/tours.ts`
- Create: `frontend/src/lib/tour-logic.ts`
- Create: `frontend/src/lib/__tests__/tour-logic.test.ts`
- Modify: `frontend/package.json` (add vitest devDep + `test` script)

**Interfaces:**
- Consumes: nothing.
- Produces: `TOURS_VERSION: string`; `interface TourStep { anchor: string; title: string; body: string }`; `interface TourDef { id: string; title: string; blurb: string; route: string; steps: TourStep[] }`; `TOURS: TourDef[]`; `seenStorageKey(version: string): string`; `filterSteps(steps: TourStep[], present: (anchor: string) => boolean): TourStep[]`; `PENDING_TOUR_KEY = "ci.pendingTour"`.

- [ ] **Step 1: Install vitest and add the test script**

```bash
cd frontend && npm install -D vitest
```

In `frontend/package.json` scripts, add: `"test": "vitest run"`.

- [ ] **Step 2: Write the failing test**

Create `frontend/src/lib/__tests__/tour-logic.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { filterSteps, seenStorageKey, PENDING_TOUR_KEY } from "../tour-logic";
import { TOURS, TOURS_VERSION } from "../tours";

describe("filterSteps", () => {
  const steps = [
    { anchor: "a", title: "A", body: "a" },
    { anchor: "b", title: "B", body: "b" },
  ];

  it("drops steps whose anchor is absent", () => {
    expect(filterSteps(steps, (a) => a === "b")).toEqual([steps[1]]);
  });

  it("keeps all steps when every anchor is present", () => {
    expect(filterSteps(steps, () => true)).toEqual(steps);
  });

  it("returns empty when nothing is present", () => {
    expect(filterSteps(steps, () => false)).toEqual([]);
  });
});

describe("seenStorageKey", () => {
  it("namespaces by version", () => {
    expect(seenStorageKey("2026-07")).toBe("ci.whatsnew.seen.2026-07");
  });
});

describe("tour definitions", () => {
  it("ids are unique", () => {
    const ids = TOURS.map((t) => t.id);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it("every tour has a route and at least one step", () => {
    for (const t of TOURS) {
      expect(t.route.startsWith("/")).toBe(true);
      expect(t.steps.length).toBeGreaterThan(0);
    }
  });

  it("version and pending key are stable strings", () => {
    expect(TOURS_VERSION).toMatch(/^\d{4}-\d{2}$/);
    expect(PENDING_TOUR_KEY).toBe("ci.pendingTour");
  });
});
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd frontend && npm test`
Expected: FAIL — cannot resolve `../tour-logic` / `../tours`.

- [ ] **Step 4: Write the implementation**

Create `frontend/src/lib/tour-logic.ts`:

```ts
// Pure helpers for the What's-new tour system. No DOM, no React — unit-tested.

import type { TourStep } from "./tours";

/** sessionStorage key that carries "start this tour after navigation". */
export const PENDING_TOUR_KEY = "ci.pendingTour";

/** localStorage key marking the What's-new dialog as seen for a release. */
export function seenStorageKey(version: string): string {
  return `ci.whatsnew.seen.${version}`;
}

/**
 * Keep only steps whose anchor exists (per the injected `present` check).
 * Feature UI can legitimately be absent — e.g. copy buttons before any
 * content is generated — and a tour must skip those steps, not break.
 */
export function filterSteps(
  steps: TourStep[],
  present: (anchor: string) => boolean,
): TourStep[] {
  return steps.filter((s) => present(s.anchor));
}
```

Create `frontend/src/lib/tours.ts`:

```ts
// What's-new tour definitions. Data only — rendering lives in
// components/tour/. Bump TOURS_VERSION when shipping a new batch of
// features; the dialog auto-opens once per version.

export const TOURS_VERSION = "2026-07";

export interface TourStep {
  /** Matches a data-tour attribute on the target element. */
  anchor: string;
  title: string;
  body: string;
}

export interface TourDef {
  id: string;
  title: string;
  blurb: string;
  route: string;
  steps: TourStep[];
}

export const TOURS: TourDef[] = [
  {
    id: "analyze-view",
    title: "Analyze any list with AI",
    blurb:
      "One click turns the list you're looking at — filters and all — into a plain-English analysis.",
    route: "/leads",
    steps: [
      {
        anchor: "analyze-button",
        title: "Analyze any list with AI",
        body:
          "This button reads the list exactly as you've filtered it — same rows, same date range — and writes a short analysis.",
      },
      {
        anchor: "analyze-button",
        title: "What you get",
        body:
          "A plain-English summary with key counts, standout patterns, and a \"show the data\" section backing every number. Nothing is saved — it's a fresh read each time.",
      },
      {
        anchor: "analyze-button",
        title: "It's on four pages",
        body:
          "Leads, Appointments, Sales Calls, and Members each have this same button at the end of their filter bar.",
      },
    ],
  },
  {
    id: "copy-actions",
    title: "Formatted content you can copy anywhere",
    blurb:
      "Generated marketing content now renders with real formatting, plus one-click copy buttons. Generate something first to see it live.",
    route: "/marketing/social/scripts",
    steps: [
      {
        anchor: "generated-output",
        title: "Cleaner generated content",
        body:
          "Generated marketing content now shows real formatting — headings, bullets, bold — instead of raw text.",
      },
      {
        anchor: "copy-actions",
        title: "Copy it your way",
        body:
          "\"Copy text\" grabs clean text for emails or DMs. \"Copy Markdown\" keeps the formatting for docs and Notion.",
      },
    ],
  },
  {
    id: "calendar-jump",
    title: "Jump to any date on the calendar",
    blurb:
      "Skip the arrow-clicking — the appointments calendar now has a jump-to-date picker. Switch to calendar view to see it.",
    route: "/appointments",
    steps: [
      {
        anchor: "calendar-jump-date",
        title: "Jump straight to a date",
        body:
          "Pick any date here and the calendar moves right to it — no more paging through weeks with the arrows.",
      },
    ],
  },
  {
    id: "data-freshness",
    title: "Check data freshness & sync on demand",
    blurb:
      "See at a glance whether every data source is up to date, and pull the latest WGR data yourself.",
    route: "/integrations",
    steps: [
      {
        anchor: "freshness-check",
        title: "Is the data current?",
        body:
          "This checks every connected source and tells you which are fresh and which look stale, with how old each one is.",
      },
      {
        anchor: "wgr-sync-now",
        title: "Pull the latest now",
        body:
          "If WGR data looks behind, this pulls the newest rows on demand — it usually takes about a minute.",
      },
    ],
  },
];

export function getTour(id: string): TourDef | undefined {
  return TOURS.find((t) => t.id === id);
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd frontend && npm test`
Expected: PASS (7 tests).

- [ ] **Step 6: Build gate + commit**

```bash
cd frontend && npm run build   # must pass clean
cd .. && git add frontend/src/lib/tours.ts frontend/src/lib/tour-logic.ts "frontend/src/lib/__tests__/tour-logic.test.ts" frontend/package.json frontend/package-lock.json
git commit -m "feat: tour definitions + pure tour logic with vitest coverage"
```

---

### Task 2: `useFeatureTour` hook (driver.js) + popover skin

**Files:**
- Create: `frontend/src/components/tour/use-feature-tour.ts`
- Modify: `frontend/src/app/globals.css` (append popover skin)
- Modify: `frontend/package.json` (add driver.js)

**Interfaces:**
- Consumes: `TourDef`, `filterSteps` from Task 1.
- Produces: `useFeatureTour(): { runTour: (tour: TourDef) => Promise<void> }`. `runTour` resolves after the tour is started (or after the fallback toast).

- [ ] **Step 1: Install driver.js**

```bash
cd frontend && npm install driver.js
```

- [ ] **Step 2: Write the hook**

Create `frontend/src/components/tour/use-feature-tour.ts`:

```ts
"use client";

// Thin wrapper around driver.js: maps our TourStep shape to driver steps,
// filters out steps whose data-tour anchor isn't in the DOM, and falls back
// to a toast when nothing is visible. driver.js is lazy-imported so it adds
// nothing to the main bundle until a tour actually runs.

import { useCallback } from "react";
import { showInfo } from "@/lib/toast";
import { filterSteps } from "@/lib/tour-logic";
import type { TourDef } from "@/lib/tours";

function anchorPresent(anchor: string): boolean {
  return document.querySelector(`[data-tour="${anchor}"]`) !== null;
}

export function useFeatureTour() {
  const runTour = useCallback(async (tour: TourDef) => {
    const steps = filterSteps(tour.steps, anchorPresent);
    if (steps.length === 0) {
      showInfo(
        "This feature isn't visible on this page right now — try again once it's on screen.",
      );
      return;
    }
    const { driver } = await import("driver.js");
    await import("driver.js/dist/driver.css");
    driver({
      showProgress: steps.length > 1,
      popoverClass: "ci-tour-popover",
      nextBtnText: "Next",
      prevBtnText: "Back",
      doneBtnText: "Done",
      steps: steps.map((s) => ({
        element: `[data-tour="${s.anchor}"]`,
        popover: { title: s.title, description: s.body },
      })),
    }).drive();
  }, []);

  return { runTour };
}
```

- [ ] **Step 3: Append the popover skin to `frontend/src/app/globals.css`**

```css
/* ── What's-new tour popover (driver.js skin) ────────────────────────── */
.ci-tour-popover.driver-popover {
  border-radius: 12px;
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.12);
  padding: 16px 18px;
}
.ci-tour-popover .driver-popover-title {
  font-size: 14px;
  font-weight: 600;
  color: #1f2937; /* gray-800 */
}
.ci-tour-popover .driver-popover-description {
  font-size: 13px;
  color: #4b5563; /* gray-600 */
}
.ci-tour-popover .driver-popover-next-btn,
.ci-tour-popover .driver-popover-prev-btn {
  border-radius: 8px;
  font-size: 12px;
  font-weight: 600;
  text-shadow: none;
}
.ci-tour-popover .driver-popover-next-btn {
  background: #f59e0b; /* accent gold — AI/new-feature mark */
  color: #ffffff;
  border: none;
}
.ci-tour-popover .driver-popover-next-btn:hover {
  background: #d97706;
}
```

- [ ] **Step 4: Build gate + commit**

```bash
cd frontend && npm run build   # must pass clean
cd .. && git add frontend/src/components/tour/use-feature-tour.ts frontend/src/app/globals.css frontend/package.json frontend/package-lock.json
git commit -m "feat: useFeatureTour hook wrapping driver.js with skip-absent-anchors and skinned popover"
```

> **Fallback:** if `npm run build` rejects the dynamic `import("driver.js/dist/driver.css")`, delete that line and add `@import "driver.js/dist/driver.css";` at the top of `globals.css` instead (driver.css is ~2kB; acceptable in the global bundle).

---

### Task 3: `WhatsNewDialog`

**Files:**
- Create: `frontend/src/components/tour/whats-new-dialog.tsx`

**Interfaces:**
- Consumes: `TOURS`, `PENDING_TOUR_KEY` (Task 1); `Button`, `SparkleIcon` atoms.
- Produces: `WhatsNewDialog({ open, onClose }: { open: boolean; onClose: () => void })`. "Show me" writes `sessionStorage[PENDING_TOUR_KEY] = tour.id`, calls `router.push(tour.route)`, then `onClose()`.

- [ ] **Step 1: Write the component**

Create `frontend/src/components/tour/whats-new-dialog.tsx`:

```tsx
"use client";

// "What's new" hub: lists the current release's features; "Show me"
// navigates to the feature's page and hands the tour id to TourProvider via
// sessionStorage (no cross-page tour choreography). Custom modal per the
// project's no-native-dialogs rule; ESC and backdrop-click close it.

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { SparkleIcon } from "@/components/ui/sparkle-icon";
import { PENDING_TOUR_KEY } from "@/lib/tour-logic";
import { TOURS, type TourDef } from "@/lib/tours";

interface WhatsNewDialogProps {
  open: boolean;
  onClose: () => void;
}

export function WhatsNewDialog({ open, onClose }: WhatsNewDialogProps) {
  const router = useRouter();

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  const startTour = (tour: TourDef) => {
    sessionStorage.setItem(PENDING_TOUR_KEY, tour.id);
    onClose();
    router.push(tour.route);
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label="What's new"
    >
      <div
        className="w-full max-w-lg rounded-xl bg-white shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-2 border-b border-gray-100 px-6 py-4">
          <span className="text-accent-500">
            <SparkleIcon />
          </span>
          <h2 className="text-[15px] font-semibold text-gray-800">
            What&apos;s new in Central Intelligence
          </h2>
        </div>
        <ul className="divide-y divide-gray-100">
          {TOURS.map((tour) => (
            <li key={tour.id} className="flex items-start gap-4 px-6 py-4">
              <div className="min-w-0 flex-1">
                <div className="text-[13px] font-semibold text-gray-800">
                  {tour.title}
                </div>
                <div className="mt-0.5 text-[12px] leading-relaxed text-gray-500">
                  {tour.blurb}
                </div>
              </div>
              <Button variant="ghost" size="sm" onClick={() => startTour(tour)}>
                Show me
              </Button>
            </li>
          ))}
        </ul>
        <div className="flex justify-end border-t border-gray-100 px-6 py-3">
          <Button variant="ghost" size="sm" onClick={onClose}>
            Close
          </Button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Build gate + commit**

```bash
cd frontend && npm run build   # must pass clean; unused-import errors block Vercel
cd .. && git add frontend/src/components/tour/whats-new-dialog.tsx
git commit -m "feat: What's-new hub dialog listing feature tours"
```

---

### Task 4: `TourProvider` + layout mount

**Files:**
- Create: `frontend/src/components/tour/tour-provider.tsx`
- Modify: `frontend/src/app/(app)/layout.tsx`

**Interfaces:**
- Consumes: `WhatsNewDialog` (Task 3), `useFeatureTour` (Task 2), `TOURS_VERSION`, `getTour`, `seenStorageKey`, `PENDING_TOUR_KEY` (Task 1).
- Produces: `TourProvider({ children })` and `useWhatsNew(): { openWhatsNew: () => void }` (context hook; Task 5's sidebar entry calls it).

- [ ] **Step 1: Write the provider**

Create `frontend/src/components/tour/tour-provider.tsx`:

```tsx
"use client";

// Orchestrates the What's-new system from the (app) layout:
//  1. Auto-opens the dialog once per TOURS_VERSION (localStorage seen-key).
//  2. After a "Show me" navigation, reads the pending tour id from
//     sessionStorage, waits for the tour's first anchor to render (poll,
//     ~5s timeout — pages fetch data before their toolbars appear), then
//     runs the driver.js tour.
//  3. Exposes openWhatsNew() so the sidebar can relaunch the dialog.

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { usePathname } from "next/navigation";
import { seenStorageKey, PENDING_TOUR_KEY } from "@/lib/tour-logic";
import { getTour, TOURS_VERSION } from "@/lib/tours";
import { useFeatureTour } from "./use-feature-tour";
import { WhatsNewDialog } from "./whats-new-dialog";

const ANCHOR_POLL_MS = 250;
const ANCHOR_TIMEOUT_MS = 5000;

const WhatsNewContext = createContext<{ openWhatsNew: () => void }>({
  openWhatsNew: () => {},
});

export function useWhatsNew() {
  return useContext(WhatsNewContext);
}

export function TourProvider({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const { runTour } = useFeatureTour();
  const [dialogOpen, setDialogOpen] = useState(false);

  // 1. First visit per release → auto-open the dialog.
  useEffect(() => {
    const key = seenStorageKey(TOURS_VERSION);
    if (localStorage.getItem(key)) return;
    localStorage.setItem(key, new Date().toISOString());
    setDialogOpen(true);
  }, []);

  // 2. Pending tour handoff after navigation.
  useEffect(() => {
    const id = sessionStorage.getItem(PENDING_TOUR_KEY);
    if (!id) return;
    const tour = getTour(id);
    if (!tour || tour.route !== pathname) return;
    sessionStorage.removeItem(PENDING_TOUR_KEY);

    const firstAnchor = tour.steps[0].anchor;
    const startedAt = Date.now();
    const timer = window.setInterval(() => {
      const found = document.querySelector(`[data-tour="${firstAnchor}"]`);
      const timedOut = Date.now() - startedAt > ANCHOR_TIMEOUT_MS;
      if (!found && !timedOut) return;
      window.clearInterval(timer);
      // Timed out → runTour still fires; it filters absent anchors and
      // falls back to an informative toast when nothing is visible.
      void runTour(tour);
    }, ANCHOR_POLL_MS);
    return () => window.clearInterval(timer);
  }, [pathname, runTour]);

  const openWhatsNew = useCallback(() => setDialogOpen(true), []);

  return (
    <WhatsNewContext.Provider value={{ openWhatsNew }}>
      {children}
      <WhatsNewDialog open={dialogOpen} onClose={() => setDialogOpen(false)} />
    </WhatsNewContext.Provider>
  );
}
```

- [ ] **Step 2: Mount it in `frontend/src/app/(app)/layout.tsx`**

Wrap the existing grid in `TourProvider` (the provider must contain BOTH the sidebar — which calls `useWhatsNew` — and the page content):

```tsx
import { Sidebar } from "@/components/layout/sidebar";
import { AuthGuard } from "@/components/layout/auth-guard";
import { TourProvider } from "@/components/tour/tour-provider";

export default function AppLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <TourProvider>
      <div className="grid grid-cols-[228px_1fr] h-screen overflow-hidden">
        <AuthGuard />
        <Sidebar />
        <div className="flex flex-col min-w-0 bg-gray-50 overflow-hidden">
          {children}
        </div>
      </div>
    </TourProvider>
  );
}
```

- [ ] **Step 3: Build gate + commit**

```bash
cd frontend && npm run build   # must pass clean
cd .. && git add frontend/src/components/tour/tour-provider.tsx "frontend/src/app/(app)/layout.tsx"
git commit -m "feat: TourProvider — once-per-release auto-open + pending-tour handoff"
```

---

### Task 5: Sidebar entry + `data-tour` anchors

**Files:**
- Modify: `frontend/src/components/layout/sidebar.tsx` (footer, near the Sign out button, ~line 380-405)
- Modify: `frontend/src/components/analyze/AnalyzeViewButton.tsx`
- Modify: `frontend/src/components/marketing/generated-output.tsx`
- Modify: `frontend/src/components/appointments/appointments-calendar-view.tsx` (~line 167-174)
- Modify: `frontend/src/app/(app)/integrations/freshness-panel.tsx` (lines ~129 and ~256)

**Interfaces:**
- Consumes: `useWhatsNew` (Task 4). Anchor names must match `tours.ts` exactly: `analyze-button`, `generated-output`, `copy-actions`, `calendar-jump-date`, `freshness-check`, `wgr-sync-now`.
- Produces: nothing new.

- [ ] **Step 1: Sidebar "What's new" entry**

In the sidebar footer component (the block containing the Sign out button), add a sparkle button beside Sign out. The footer is not currently a client component consumer of tour context — `sidebar.tsx` is already `"use client"`, so import and use the hook directly:

```tsx
import { SparkleIcon } from "@/components/ui/sparkle-icon";
import { useWhatsNew } from "@/components/tour/tour-provider";
```

Inside the footer, before the Sign out button:

```tsx
<button
  type="button"
  onClick={openWhatsNew}
  aria-label="What's new"
  className="flex-shrink-0 text-sidebar-heading hover:text-sidebar-text-hover transition-colors"
  title="What's new"
>
  <SparkleIcon />
</button>
```

with `const { openWhatsNew } = useWhatsNew();` at the top of the footer component.

- [ ] **Step 2: Anchor attributes (exact placements)**

1. `AnalyzeViewButton.tsx` — on the `<Button>`:
   `<Button variant="ai" size="sm" onClick={onClick} data-tour="analyze-button" title="AI analysis of the currently filtered list">`
   (`Button` extends `ButtonHTMLAttributes` and spreads `...rest`, so `data-tour` passes through.)
2. `generated-output.tsx` — outer wrapper `<div>` → `<div data-tour="generated-output">`; the copy-buttons flex container → `<div className="flex gap-1.5 flex-shrink-0" data-tour="copy-actions">`.
3. `appointments-calendar-view.tsx` — the jump-to-date `<input type="date" … aria-label="Jump to date">` gets `data-tour="calendar-jump-date"`.
4. `freshness-panel.tsx` — the Sync button (line ~129) gets `data-tour="wgr-sync-now"`; the Check button (line ~256) gets `data-tour="freshness-check"`.

- [ ] **Step 3: Build gate + commit**

```bash
cd frontend && npm run build   # must pass clean
cd .. && git add frontend/src/components/layout/sidebar.tsx frontend/src/components/analyze/AnalyzeViewButton.tsx frontend/src/components/marketing/generated-output.tsx frontend/src/components/appointments/appointments-calendar-view.tsx "frontend/src/app/(app)/integrations/freshness-panel.tsx"
git commit -m "feat: sidebar What's-new entry + data-tour anchors on the four feature surfaces"
```

---

### Task 6: Docs, live verification, PR

**Files:**
- Create: `docs/testing/2026-07-15-whats-new-tour-test.md`
- Modify: `CHANGELOG.md` (new entry under `## [Unreleased]`)

- [ ] **Step 1: Test doc** (FEATURE-VERIFICATION style, per project convention — user tests personally on real data)

Sections: T1 first-visit auto-open (clear `ci.whatsnew.seen.2026-07` from localStorage, reload, dialog appears once, not again after reload); T2 each of the four tours end-to-end via "Show me" (navigation → spotlight steps → Done); T3 relaunch from the sidebar sparkle; T4 skip-when-hidden (open copy-actions tour before generating content → info toast; calendar tour while in list view → toast or skipped step).

- [ ] **Step 2: CHANGELOG entry** under `## [Unreleased]`:

`### Added — In-app "What's new" tour` + 4-6 lines: hub dialog auto-opens once per release; four driver.js mini-tours (Analyze with AI, marketing copy actions, calendar date picker, data freshness/sync); relaunchable from sidebar; anchors via data-tour attributes; localStorage seen-state.

- [ ] **Step 3: Live verification** (drive the app, not just build)

With the dev stack running (backend :8000, frontend :3000): clear the seen key, log in, confirm the dialog auto-opens; run the Analyze tour end-to-end via "Show me" (confirm it never auto-opens the drawer); run the freshness tour. Playwright MCP or manual.

- [ ] **Step 4: Run full test + build, push, PR**

```bash
cd frontend && npm test && npm run build
cd .. && git add docs/testing/2026-07-15-whats-new-tour-test.md CHANGELOG.md
git commit -m "docs: What's-new tour test doc + changelog"
git push -u origin feat/whats-new-tour
gh pr create --repo VAPhilippines/greg_central-intelligence --title "feat: in-app What's-new tour (hub dialog + per-page feature walkthroughs)" --body "<summary of spec, tours, verification>"
```
