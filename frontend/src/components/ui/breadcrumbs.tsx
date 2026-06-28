"use client";

import Link from "next/link";

/**
 * Breadcrumbs for detail pages — "Origin › Current".
 *
 * The origin is passed via a `?from=<key>` query param on the link that brought
 * the user here, then resolved against ORIGINS (a closed allow-list, so we never
 * navigate to an arbitrary URL). Unknown/absent keys fall back to a default the
 * caller supplies. See `resolveOrigin`.
 */

export interface Origin {
  label: string;
  href: string;
}

// Known origins a call detail page can be reached from. Keep keys short/stable —
// they're what link sources put in `?from=`.
export const ORIGINS: Record<string, Origin> = {
  "sales-calls": { label: "Sales Calls", href: "/sales-calls" },
  calls: { label: "All Calls", href: "/calls" },
  "coaching-calls": { label: "Coaching Calls", href: "/coaching-calls" },
  members: { label: "Members", href: "/members" },
  leads: { label: "Leads", href: "/leads" },
};

/** Resolve a `?from=` key to a known Origin, or fall back to `fallbackKey`. */
export function resolveOrigin(fromKey: string | null, fallbackKey: string): Origin {
  if (fromKey && ORIGINS[fromKey]) return ORIGINS[fromKey];
  return ORIGINS[fallbackKey] ?? { label: "Back", href: "/" };
}

export function Breadcrumbs({ origin, current }: { origin: Origin; current: string }) {
  return (
    <nav aria-label="Breadcrumb" className="flex items-center gap-1.5 text-[13px]">
      <Link
        href={origin.href}
        className="font-medium text-accent-600 hover:text-accent-700 hover:underline underline-offset-2"
      >
        {origin.label}
      </Link>
      <span className="text-gray-300" aria-hidden>
        ›
      </span>
      <span className="text-gray-500">{current}</span>
    </nav>
  );
}
