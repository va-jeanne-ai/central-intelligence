import { describe, expect, it } from "vitest";
import {
  channelLabel,
  channelBadgeClasses,
  isUnmappedChannel,
  resolveSource,
  resolveStatus,
  humanise,
  NO_ATTRIBUTION_LABEL,
} from "../lead-display";

describe("channelLabel", () => {
  it("renders null as No attribution", () => {
    expect(channelLabel(null)).toBe(NO_ATTRIBUTION_LABEL);
    expect(channelLabel(undefined)).toBe(NO_ATTRIBUTION_LABEL);
  });

  it("shows canonical channel labels verbatim (open string set, not humanised)", () => {
    expect(channelLabel("Non-marketing")).toBe("Non-marketing");
    expect(channelLabel("other unmapped")).toBe("other unmapped");
  });

  it("shows unmapped:<src>/<med> dialects verbatim", () => {
    expect(channelLabel("unmapped:facebook/cpc")).toBe("unmapped:facebook/cpc");
  });
});

describe("isUnmappedChannel", () => {
  it("flags unmapped:* dialects", () => {
    expect(isUnmappedChannel("unmapped:facebook/cpc")).toBe(true);
  });

  it("flags the other unmapped rollup", () => {
    expect(isUnmappedChannel("other unmapped")).toBe(true);
  });

  it("does not flag canonical channels or No attribution", () => {
    expect(isUnmappedChannel("Organic Search")).toBe(false);
    expect(isUnmappedChannel(null)).toBe(false);
    expect(isUnmappedChannel(undefined)).toBe(false);
  });
});

describe("channelBadgeClasses", () => {
  it("gives unmapped channels an amber warning tint", () => {
    expect(channelBadgeClasses("unmapped:tiktok/organic")).toMatch(/amber/);
    expect(channelBadgeClasses("other unmapped")).toMatch(/amber/);
  });

  it("gives everything else a neutral tint", () => {
    expect(channelBadgeClasses("Paid Social")).not.toMatch(/amber/);
    expect(channelBadgeClasses(null)).not.toMatch(/amber/);
  });
});

describe("resolveSource / resolveStatus (closed-enum resolvers, unaffected by channel)", () => {
  it("resolves known enum sources", () => {
    expect(resolveSource("webinar").label).toBe("Webinar");
  });

  it("falls back to a humanised label for unknown sources", () => {
    // "ads" is <= 3 chars so humanise() treats it as an acronym (ADS).
    expect(resolveSource("facebook_ads").label).toBe("Facebook ADS");
  });

  it("falls back to Unknown for null/undefined", () => {
    expect(resolveSource(null).label).toBe("Unknown");
    expect(resolveStatus(undefined).label).toBe("Unknown");
  });
});

describe("humanise", () => {
  it("title-cases underscore/dash separated words", () => {
    // "ads" is <= 3 chars so it's treated as an acronym (ADS), not title-cased.
    expect(humanise("facebook_ads")).toBe("Facebook ADS");
    expect(humanise("podcast-referral")).toBe("Podcast Referral");
  });

  it("uppercases short acronym-like words", () => {
    expect(humanise("vsl")).toBe("VSL");
  });
});
