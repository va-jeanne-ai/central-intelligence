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
