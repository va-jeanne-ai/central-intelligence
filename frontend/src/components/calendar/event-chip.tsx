"use client";

import { formatTimeRange } from "@/lib/calendar-helpers";
import type { CalendarEventRow } from "@/types";

interface EventChipProps {
  event: CalendarEventRow;
  /** Compact = title only (used in month grid cells where space is tight). */
  compact?: boolean;
}

/**
 * One event rendered as a colored pill. Click opens the event in
 * Google Calendar in a new tab (read-only model — Google is the
 * editor of record).
 *
 * Visual states:
 *   - Tentative events get a striped border + dimmer fill.
 *   - All-day events get a slightly different shape (no time label).
 */
export function EventChip({ event, compact = false }: EventChipProps) {
  const time = formatTimeRange(event.start_time, event.end_time, event.is_all_day);
  const isTentative = event.status === "tentative";

  const baseClasses =
    "block rounded-md px-1.5 py-0.5 text-left text-[11px] leading-tight truncate transition-colors";
  const colorClasses = isTentative
    ? "bg-amber-50 text-amber-900 border border-amber-200 hover:bg-amber-100"
    : "bg-indigo-50 text-indigo-900 border border-indigo-100 hover:bg-indigo-100";

  return (
    <a
      href={event.event_link || "#"}
      target="_blank"
      rel="noopener noreferrer"
      className={`${baseClasses} ${colorClasses}`}
      title={event.title || "(untitled event)"}
    >
      {compact ? (
        <span className="truncate">
          {!event.is_all_day && event.start_time ? (
            <span className="font-mono text-[10px] text-indigo-700 mr-1">
              {new Date(event.start_time).toLocaleTimeString(undefined, {
                hour: "numeric",
                minute: "2-digit",
              })}
            </span>
          ) : null}
          <span className="font-medium">{event.title || "(untitled)"}</span>
        </span>
      ) : (
        <>
          <div className="font-mono text-[10px] text-indigo-700">{time}</div>
          <div className="font-medium truncate">
            {event.title || "(untitled event)"}
          </div>
        </>
      )}
    </a>
  );
}
