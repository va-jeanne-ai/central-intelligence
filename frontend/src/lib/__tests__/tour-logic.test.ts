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
