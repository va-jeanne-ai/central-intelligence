"use client";

import { formatTimeRange } from "@/lib/calendar-helpers";
import { resolveAppointmentStatus } from "@/lib/appointment-status";
import type { CalendarEventRow } from "@/types";

interface EventChipProps {
  event: CalendarEventRow;
  /** Compact = title only (used in month grid cells where space is tight). */
  compact?: boolean;
  /**
   * Called instead of following event_link when the event is an
   * appointment (source === "appointment"). Google events keep the
   * default "open in Google Calendar" link behavior untouched.
   */
  onAppointmentClick?: (event: CalendarEventRow) => void;
}

/**
 * One event rendered as a colored pill.
 *
 * Google Calendar events (source omitted/"google"): click opens the event
 * in Google Calendar in a new tab (read-only model — Google is the editor
 * of record). Tentative events get a dimmer amber fill.
 *
 * Appointment events (source === "appointment"): styled with the same
 * status palette as the /appointments list pills, carry a small "Appt"
 * marker so they're visually distinguishable from Google events at a
 * glance, and clicking opens the shared detail popover instead of
 * navigating away.
 */
export function EventChip({ event, compact = false, onAppointmentClick }: EventChipProps) {
  const time = formatTimeRange(event.start_time, event.end_time, event.is_all_day);
  const isAppointment = event.source === "appointment";
  const isTentative = !isAppointment && event.status === "tentative";

  const baseClasses =
    "block w-full rounded-md px-1.5 py-0.5 text-left text-[11px] leading-tight truncate transition-colors";

  let colorClasses: string;
  if (isAppointment) {
    colorClasses = `${resolveAppointmentStatus(event.status).chipClasses} border-l-[3px]`;
  } else if (isTentative) {
    colorClasses = "bg-amber-50 text-amber-900 border border-amber-200 hover:bg-amber-100";
  } else {
    colorClasses = "bg-accent-50 text-accent-900 border border-accent-100 hover:bg-accent-100";
  }

  const content = compact ? (
    <span className="truncate">
      {isAppointment && (
        <span className="text-[9px] font-bold uppercase tracking-wide mr-1 opacity-70">Appt</span>
      )}
      {!event.is_all_day && event.start_time ? (
        <span className={`font-mono text-[10px] mr-1 ${isAppointment ? "" : "text-accent-700"}`}>
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
      <div className="flex items-center gap-1">
        {isAppointment && (
          <span className="text-[9px] font-bold uppercase tracking-wide opacity-70">Appt</span>
        )}
        <div className={`font-mono text-[10px] ${isAppointment ? "" : "text-accent-700"}`}>{time}</div>
      </div>
      <div className="font-medium truncate">{event.title || "(untitled event)"}</div>
    </>
  );

  if (isAppointment) {
    return (
      <button
        type="button"
        onClick={() => onAppointmentClick?.(event)}
        className={`${baseClasses} ${colorClasses}`}
        title={event.title || "(untitled event)"}
      >
        {content}
      </button>
    );
  }

  return (
    <a
      href={event.event_link || "#"}
      target="_blank"
      rel="noopener noreferrer"
      className={`${baseClasses} ${colorClasses}`}
      title={event.title || "(untitled event)"}
    >
      {content}
    </a>
  );
}
