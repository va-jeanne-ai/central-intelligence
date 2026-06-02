"use client";

import {
  dayKey,
  formatDayHeader,
  formatTimeRange,
  groupEventsByDay,
  isSameDay,
} from "@/lib/calendar-helpers";
import type { CalendarEventRow } from "@/types";

interface DayViewProps {
  anchorDate: Date;
  events: CalendarEventRow[];
}

/**
 * Single-column list for one day with hour markers down the left.
 *
 * Not an absolute-positioned canvas layout (no Y-position-from-time
 * blocks) — v1 stays chronological-list. Easy upgrade later if Greg
 * wants the "block" calendar-canvas feel.
 */
export function DayView({ anchorDate, events }: DayViewProps) {
  const today = new Date();
  const isToday = isSameDay(anchorDate, today);
  const grouped = groupEventsByDay(events);
  const dayEvents = grouped.get(dayKey(anchorDate)) || [];

  return (
    <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
      <div
        className={
          "px-5 py-3 border-b border-gray-200 " +
          (isToday ? "bg-indigo-50" : "bg-gray-50")
        }
      >
        <div
          className={
            "text-[20px] font-semibold leading-none " +
            (isToday ? "text-indigo-700" : "text-gray-800")
          }
        >
          {formatDayHeader(anchorDate)}
          {isToday && (
            <span className="ml-2 text-[10px] font-bold uppercase tracking-wider text-indigo-500">
              Today
            </span>
          )}
        </div>
      </div>

      <div className="divide-y divide-gray-100">
        {dayEvents.length === 0 ? (
          <p className="px-5 py-8 text-[13px] text-gray-400 italic text-center">
            No events on this day.
          </p>
        ) : (
          dayEvents.map((e) => {
            const attendeeCount = e.attendees.length;
            return (
              <a
                key={e.id}
                href={e.event_link || "#"}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-baseline gap-4 px-5 py-3 hover:bg-gray-50 transition-colors"
              >
                <span className="text-[12px] font-mono text-gray-500 w-32 flex-shrink-0">
                  {formatTimeRange(e.start_time, e.end_time, e.is_all_day)}
                </span>
                <div className="flex-1 min-w-0">
                  <div className="text-[14px] font-medium text-gray-800 truncate">
                    {e.title || "(untitled event)"}
                  </div>
                  <div className="text-[11px] text-gray-500 mt-0.5 truncate">
                    {e.calendar_name && (
                      <span className="mr-2">📆 {e.calendar_name}</span>
                    )}
                    {e.organizer_email && (
                      <span className="mr-2">👤 {e.organizer_email}</span>
                    )}
                    {attendeeCount > 0 && (
                      <span className="mr-2">
                        👥 {attendeeCount} attendee
                        {attendeeCount === 1 ? "" : "s"}
                      </span>
                    )}
                    {e.location && (
                      <span className="mr-2">📍 {e.location}</span>
                    )}
                  </div>
                </div>
                {e.status === "tentative" && (
                  <span className="text-[10px] text-amber-600 font-semibold uppercase">
                    Tentative
                  </span>
                )}
              </a>
            );
          })
        )}
      </div>
    </div>
  );
}
