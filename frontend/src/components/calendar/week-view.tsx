"use client";

import { EventChip } from "@/components/calendar/event-chip";
import {
  addDays,
  dayKey,
  groupEventsByDay,
  isSameDay,
  startOfWeek,
} from "@/lib/calendar-helpers";
import type { CalendarEventRow } from "@/types";

interface WeekViewProps {
  anchorDate: Date;
  events: CalendarEventRow[];
}

/**
 * Seven-column day grid for the week containing anchorDate.
 * Each column is a vertical scroll of EventChips (non-compact —
 * title + time fit comfortably at this column width).
 */
export function WeekView({ anchorDate, events }: WeekViewProps) {
  const weekStart = startOfWeek(anchorDate);
  const days: Date[] = [];
  for (let i = 0; i < 7; i++) days.push(addDays(weekStart, i));

  const today = new Date();
  const grouped = groupEventsByDay(events);

  return (
    <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
      {/* Column headers — weekday + day number */}
      <div className="grid grid-cols-7 border-b border-gray-200 bg-gray-50">
        {days.map((d) => {
          const isToday = isSameDay(d, today);
          return (
            <div
              key={d.toISOString()}
              className={
                "px-3 py-2 text-center border-r border-gray-200 last:border-r-0 " +
                (isToday ? "bg-accent-50" : "")
              }
            >
              <div className="text-[11px] font-semibold uppercase tracking-wider text-gray-500">
                {d.toLocaleDateString(undefined, { weekday: "short" })}
              </div>
              <div
                className={
                  "text-[18px] font-semibold leading-none mt-1 " +
                  (isToday ? "text-accent-600" : "text-gray-800")
                }
              >
                {d.getDate()}
              </div>
            </div>
          );
        })}
      </div>

      {/* 7 vertical columns of events for the week */}
      <div className="grid grid-cols-7 min-h-[500px]">
        {days.map((d) => {
          const isToday = isSameDay(d, today);
          const eventsForDay = grouped.get(dayKey(d)) || [];
          return (
            <div
              key={d.toISOString()}
              className={
                "border-r border-gray-100 last:border-r-0 p-2 flex flex-col gap-1.5 " +
                (isToday ? "bg-accent-50/40" : "bg-white")
              }
            >
              {eventsForDay.length === 0 ? (
                <p className="text-[11px] text-gray-300 italic">No events</p>
              ) : (
                eventsForDay.map((e) => <EventChip key={e.id} event={e} />)
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
