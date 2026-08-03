// Shared lead status/source/channel display helpers — used by both the
// leads list (/leads) and lead detail (/leads/[lead_id]) pages. Hoisted per
// the TODO(v2) left in leads/[lead_id]/page.tsx once a second consumer
// (the leads-list Channel column + donut) needed the same logic.

import type { LeadStatus, LeadSource } from "@/types";

// ─── Status / Source display config ──────────────────────────────────────────

export const STATUS_CONFIG: Record<
  LeadStatus,
  { label: string; dotColor: string; badgeClasses: string }
> = {
  new: { label: "New", dotColor: "#3B82F6", badgeClasses: "bg-blue-50 text-blue-700" },
  contacted: { label: "Active", dotColor: "#F97316", badgeClasses: "bg-orange-50 text-orange-700" },
  qualified: { label: "Applied", dotColor: "#8B5CF6", badgeClasses: "bg-violet-50 text-violet-700" },
  appointment_set: { label: "Booked", dotColor: "#0D9488", badgeClasses: "bg-teal-50 text-teal-700" },
  closed_won: { label: "Closed Won", dotColor: "#10B981", badgeClasses: "bg-green-50 text-green-700" },
  closed_lost: { label: "Lost", dotColor: "#9CA3AF", badgeClasses: "bg-gray-100 text-gray-500" },
  stale: { label: "Stale", dotColor: "#F59E0B", badgeClasses: "bg-accent-50 text-accent-700" },
};

export const SOURCE_CONFIG: Record<LeadSource, { label: string; badgeClasses: string }> = {
  webinar: { label: "Webinar", badgeClasses: "bg-accent-50 text-accent-700" },
  vsl: { label: "VSL", badgeClasses: "bg-blue-50 text-blue-700" },
  "opt-in": { label: "Opt-in", badgeClasses: "bg-green-50 text-green-700" },
  ads: { label: "Ads", badgeClasses: "bg-gray-100 text-gray-600" },
  referral: { label: "Referral", badgeClasses: "bg-violet-50 text-violet-700" },
  other: { label: "Other", badgeClasses: "bg-gray-100 text-gray-500" },
};

// Fallback resolvers — leads now arrive from real integrations (GHL pushes
// e.g. source='facebook_ads', 'instagram_ads', 'podcast_referral'; status
// can be anything the upstream system uses). Looking those up in the
// enum-keyed records above returns undefined and the row render crashes
// on `.badgeClasses`. These helpers always return a sane shape so the
// page renders any string the backend hands us.

export function humanise(value: string | null | undefined): string {
  // 'facebook_ads' → 'Facebook Ads'. Best-effort prettifier for unknown
  // values; falls back to the raw string for anything weird. Real WGR leads
  // can arrive with a null/empty source or status, so guard before .split().
  if (!value) return "Unknown";
  return value
    .split(/[_\-\s]+/)
    .filter(Boolean)
    .map((w) => (w.length <= 3 ? w.toUpperCase() : w[0].toUpperCase() + w.slice(1).toLowerCase()))
    .join(" ");
}

export function resolveSource(raw: string | null | undefined) {
  return (
    (raw ? SOURCE_CONFIG[raw as LeadSource] : undefined) ?? {
      label: humanise(raw),
      badgeClasses: "bg-gray-100 text-gray-600",
    }
  );
}

export function resolveStatus(raw: string | null | undefined) {
  return (
    (raw ? STATUS_CONFIG[raw as LeadStatus] : undefined) ?? {
      label: humanise(raw),
      dotColor: "#9CA3AF",
      badgeClasses: "bg-gray-100 text-gray-600",
    }
  );
}

// ─── Channel display (attribution taxonomy) ──────────────────────────────────
//
// `channel` is an OPEN string set — canonical channels plus "No attribution",
// "Non-marketing", "other unmapped", and "unmapped:<src>/<med>" dialects for
// UTM combos the taxonomy hasn't mapped yet. It must NOT be routed through
// the closed-enum SOURCE_CONFIG above. Colors come from the hash-based
// colorForSource palette (defined in leads/page.tsx) keyed on the resolved
// label below.

export const NO_ATTRIBUTION_LABEL = "No attribution";

/** True for the open "unmapped:<src>/<med>" and "other unmapped" dialects —
 * these must surface loudly (amber warning tint) per the taxonomy contract,
 * since they flag UTM combos the backend hasn't mapped to a real channel. */
export function isUnmappedChannel(channel: string | null | undefined): boolean {
  if (!channel) return false;
  return channel.startsWith("unmapped:") || channel === "other unmapped";
}

/** Resolve a raw `channel` value (or null) to its display label. Channel is
 * an open string set, so this never falls back to `humanise()` — the
 * backend-provided label (e.g. "unmapped:facebook/cpc") is shown verbatim. */
export function channelLabel(channel: string | null | undefined): string {
  return channel ?? NO_ATTRIBUTION_LABEL;
}

/** Tailwind classes for the channel chip. `unmapped:*` / "other unmapped"
 * get an amber warning tint so new UTM dialects surface loudly; everything
 * else gets a neutral chip (color-coding for channel comes from the donut's
 * hash palette, not from per-chip background color). */
export function channelBadgeClasses(channel: string | null | undefined): string {
  return isUnmappedChannel(channel)
    ? "bg-amber-50 text-amber-700 ring-1 ring-inset ring-amber-200"
    : "bg-gray-100 text-gray-600";
}
