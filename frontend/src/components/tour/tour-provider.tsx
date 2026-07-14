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
const ANCHOR_TIMEOUT_MS = 10_000;
const SETTLE_MS = 400;

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

    const firstAnchor = tour.steps[0]?.anchor;
    const startedAt = Date.now();
    let settleTimer: number | undefined;
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
      settleTimer = window.setTimeout(() => void runTour(tour), SETTLE_MS);
    }, ANCHOR_POLL_MS);
    return () => {
      window.clearInterval(timer);
      if (settleTimer) window.clearTimeout(settleTimer);
    };
  }, [pathname, runTour]);

  const openWhatsNew = useCallback(() => setDialogOpen(true), []);

  return (
    <WhatsNewContext.Provider value={{ openWhatsNew }}>
      {children}
      <WhatsNewDialog open={dialogOpen} onClose={() => setDialogOpen(false)} />
    </WhatsNewContext.Provider>
  );
}
