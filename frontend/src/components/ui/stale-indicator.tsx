"use client";

import { useEffect, useState } from "react";

// ─── StaleIndicator ───────────────────────────────────────────────────────────
// Shows "Last updated: <time>" and optionally a stale warning badge.
// - lastUpdatedAt: ISO string of when data was last fetched; null/undefined → "—"
// - staleSec: seconds after which data is considered stale (default: 300 = 5min)

interface StaleIndicatorProps {
  lastUpdatedAt?: string | null;
  staleSec?: number;
}

export function StaleIndicator({
  lastUpdatedAt,
  staleSec = 300,
}: StaleIndicatorProps) {
  const [, setTick] = useState(0);

  // Re-render every 60s so the "stale" badge can appear without a page refresh.
  useEffect(() => {
    const id = setInterval(() => setTick((n) => n + 1), 60_000);
    return () => clearInterval(id);
  }, []);

  const isStale =
    lastUpdatedAt != null &&
    Date.now() - new Date(lastUpdatedAt).getTime() > staleSec * 1000;

  const label = lastUpdatedAt
    ? formatRelative(new Date(lastUpdatedAt))
    : "—";

  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-gray-400">
      <ClockIcon />
      <span>Last updated: {label}</span>
      {isStale && (
        <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full bg-amber-50 text-amber-600 font-medium text-[10px] border border-amber-200">
          <span aria-hidden="true">⚠</span>
          Stale
        </span>
      )}
    </span>
  );
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function ClockIcon() {
  return (
    <svg
      width="12"
      height="12"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <circle cx="12" cy="12" r="10" />
      <polyline points="12 6 12 12 16 14" />
    </svg>
  );
}

function formatRelative(date: Date): string {
  const diffMs = Date.now() - date.getTime();
  const diffMin = Math.floor(diffMs / 60_000);
  if (diffMin < 1) return "just now";
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  return date.toLocaleDateString();
}
