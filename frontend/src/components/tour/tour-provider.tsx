"use client";

// Orchestrates the What's-new system from the (app) layout:
//  1. Auto-opens the dialog once per TOURS_VERSION (localStorage seen-key).
//  2. After a "Show me" request, either starts the tour directly (already on
//     its page) or navigates and reads the pending tour id from
//     sessionStorage on the next pathname change, waits for the tour's first
//     anchor to render (poll, ~10s timeout — pages fetch data before their
//     toolbars appear), then runs the driver.js tour.
//  3. Exposes openWhatsNew() so the sidebar can relaunch the dialog, and
//     requestTour() for the dialog's "Show me" action.

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { usePathname, useRouter } from "next/navigation";
import { seenStorageKey, PENDING_TOUR_KEY } from "@/lib/tour-logic";
import { getTour, TOURS_VERSION, type TourDef } from "@/lib/tours";
import { useFeatureTour } from "./use-feature-tour";
import { WhatsNewDialog } from "./whats-new-dialog";

const ANCHOR_POLL_MS = 250;
const ANCHOR_TIMEOUT_MS = 10_000;
const SETTLE_MS = 400;

const WhatsNewContext = createContext<{
  openWhatsNew: () => void;
  requestTour: (id: string) => void;
}>({
  openWhatsNew: () => {},
  requestTour: () => {},
});

export function useWhatsNew() {
  return useContext(WhatsNewContext);
}

export function TourProvider({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { runTour } = useFeatureTour();
  const [dialogOpen, setDialogOpen] = useState(false);
  const timersRef = useRef<number[]>([]);

  const clearTimers = useCallback(() => {
    for (const id of timersRef.current) {
      window.clearInterval(id);
      window.clearTimeout(id);
    }
    timersRef.current = [];
  }, []);

  // Waits for the tour's first anchor to render (poll, ~10s timeout — pages
  // fetch data before their toolbars appear), then runs the driver.js tour.
  // Cancels any in-flight wait from a previous request first.
  const startTourWhenReady = useCallback(
    (tour: TourDef) => {
      clearTimers();

      const firstAnchor = tour.steps[0]?.anchor;
      const startedAt = Date.now();
      const timer = window.setInterval(() => {
        const anchorReady = firstAnchor
          ? document.querySelector(`[data-tour="${firstAnchor}"]`) !== null
          : true;
        // Don't start the spotlight while the page still shows loading
        // skeletons — the layout shifts under the popover as data lands.
        const stillLoading = document.querySelector(".animate-pulse") !== null;
        const timedOut = Date.now() - startedAt > ANCHOR_TIMEOUT_MS;
        if ((!anchorReady || stillLoading) && !timedOut) return;
        window.clearInterval(timer);
        // Short settle so the final data render paints before the overlay
        // measures element positions. On timeout runTour still fires — it
        // filters absent anchors and falls back to a toast.
        const settleTimer = window.setTimeout(
          () => {
            sessionStorage.removeItem(PENDING_TOUR_KEY);
            void runTour(tour);
          },
          SETTLE_MS
        );
        timersRef.current.push(settleTimer);
      }, ANCHOR_POLL_MS);
      timersRef.current.push(timer);
    },
    [clearTimers, runTour]
  );

  // 1. First visit per release → auto-open the dialog.
  useEffect(() => {
    const key = seenStorageKey(TOURS_VERSION);
    if (localStorage.getItem(key)) return;
    localStorage.setItem(key, new Date().toISOString());
    setDialogOpen(true);
  }, []);

  // 2. Pending tour handoff after navigation.
  // StrictMode double-mount: the effect runs twice (with cleanup in-between).
  // First run: reads the key and arms timers. Cleanup: clears those timers.
  // Second run must still see the key to re-arm, so we defer key removal until
  // the tour actually fires (in the settle callback below).
  useEffect(() => {
    const id = sessionStorage.getItem(PENDING_TOUR_KEY);
    if (!id) return;
    const tour = getTour(id);
    if (!tour || tour.route !== pathname) return;

    startTourWhenReady(tour);
    return clearTimers;
  }, [pathname, startTourWhenReady, clearTimers]);

  // Unmount-only cleanup — belt-and-suspenders on top of the effect above.
  useEffect(() => clearTimers, [clearTimers]);

  const openWhatsNew = useCallback(() => setDialogOpen(true), []);

  // Called from the What's-new dialog's "Show me". If we're already on the
  // tour's page, pathname never changes so the handoff effect above would
  // never re-fire — start the tour directly instead of round-tripping
  // through sessionStorage + a no-op navigation.
  const requestTour = useCallback(
    (id: string) => {
      const tour = getTour(id);
      if (!tour) return;
      setDialogOpen(false);
      if (tour.route === pathname) {
        startTourWhenReady(tour);
      } else {
        sessionStorage.setItem(PENDING_TOUR_KEY, id);
        router.push(tour.route);
      }
    },
    [pathname, router, startTourWhenReady]
  );

  return (
    <WhatsNewContext.Provider value={{ openWhatsNew, requestTour }}>
      {children}
      <WhatsNewDialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        onShowMe={requestTour}
      />
    </WhatsNewContext.Provider>
  );
}
