"use client";

import { EventChip } from "@/components/calendar/event-chip";
import {
  buildMonthGrid,
  dayKey,
  groupEventsByDay,
  isSameDay,
} from "@/lib/calendar-helpers";
import type { CalendarEventRow } from "@/types";

const DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const MAX_VISIBLE_PER_CELL = 3;

interface MonthViewProps {
  anchorDate: Date;
  events: CalendarEventRow[];
  /** Optional handler — clicking a cell switches the parent to Day view. */
  onDayClick?: (date: Date) => void;
}

/**
 * 6-row × 7-column month grid. Today's cell has an indigo ring;
 * cells outside the active month are dimmed. Each cell shows up to
 * MAX_VISIBLE_PER_CELL chips with a "+N more" link when overflow.
 */
export function MonthView({ anchorDate, events, onDayClick }: MonthViewProps) {
  const today = new Date();
  const grouped = groupEventsByDay(events);
  const grid = buildMonthGrid(anchorDate);
  const activeMonth = anchorDate.getMonth();

  return (
    <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
      {/* Day-of-week header row */}
      <div className="grid grid-cols-7 border-b border-gray-200 bg-gray-50">
        {DAY_NAMES.map((name) => (
          <div
            key={name}
            className="px-2 py-2 text-[11px] font-semibold uppercase tracking-wider text-gray-500 text-center"
          >
            {name}
          </div>
        ))}
      </div>

      {/* 6×7 grid of day cells */}
      <div className="grid grid-cols-7 grid-rows-6">
        {grid.map((cellDate, idx) => {
          const inMonth = cellDate.getMonth() === activeMonth;
          const isToday = isSameDay(cellDate, today);
          const eventsForDay = grouped.get(dayKey(cellDate)) || [];
          const visible = eventsForDay.slice(0, MAX_VISIBLE_PER_CELL);
          const overflow = eventsForDay.length - visible.length;

          return (
            <div
              key={idx}
              className={
                "min-h-[110px] border-r border-b border-gray-100 last-of-row:border-r-0 p-1.5 flex flex-col gap-1 " +
                (inMonth ? "bg-white" : "bg-gray-50/60") +
                (isToday ? " ring-2 ring-indigo-400 ring-inset" : "")
              }
            >
              <button
                type="button"
                onClick={onDayClick ? () => onDayClick(cellDate) : undefined}
                className={
                  "self-start text-[11px] font-semibold leading-none px-1 py-0.5 rounded transition-colors " +
                  (isToday
                    ? "bg-indigo-500 text-white"
                    : inMonth
                      ? "text-gray-700 hover:bg-gray-100"
                      : "text-gray-400 hover:bg-gray-100") +
                  (onDayClick ? " cursor-pointer" : " cursor-default")
                }
                disabled={!onDayClick}
              >
                {cellDate.getDate()}
              </button>

              <div className="flex flex-col gap-0.5 overflow-hidden">
                {visible.map((e) => (
                  <EventChip key={e.id} event={e} compact />
                ))}
                {overflow > 0 && (
                  <button
                    type="button"
                    onClick={onDayClick ? () => onDayClick(cellDate) : undefined}
                    className="text-[10px] text-gray-500 hover:text-indigo-600 text-left px-1.5"
                  >
                    +{overflow} more
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
