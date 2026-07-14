"use client";

// Thin wrapper around driver.js: maps our TourStep shape to driver steps,
// filters out steps whose data-tour anchor isn't in the DOM, and falls back
// to a toast when nothing is visible. driver.js is lazy-imported so it adds
// nothing to the main bundle until a tour actually runs.

import { useCallback } from "react";
import { showInfo, showError } from "@/lib/toast";
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
    try {
      const { driver } = await import("driver.js");
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
    } catch {
      showError(
        "Couldn't start the tour — please refresh the page and try again.",
      );
    }
  }, []);

  return { runTour };
}
