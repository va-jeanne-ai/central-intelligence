"use client";

// Calendar mode for /appointments — reuses the same MonthView / WeekView /
// DayView / ListView sub-views as the main /calendar page (via the
// appointment→event mapping), so appointments render through one set of
// grid components rather than a fork. Owns only view/anchor-date nav; the
// rep/status/date filters live on the parent page and are passed in so
// List mode and Calendar mode always agree on what's currently filtered.

import { useCallback, useEffect, useMemo, useState } from "react";

import { AppointmentDetailPopover } from "@/components/calendar/appointment-detail-popover";
import { DayView } from "@/components/calendar/day-view";
import { ListView } from "@/components/calendar/list-view";
import { MonthView } from "@/components/calendar/month-view";
import { WeekView } from "@/components/calendar/week-view";
import {
  addDays,
  addMonths,
  addWeeks,
  endOfDay,
  endOfMonth,
  endOfWeek,
  formatDayHeader,
  formatMonthHeader,
  formatWeekHeader,
  startOfDay,
  startOfMonth,
  startOfWeek,
  toDateInputValue,
} from "@/lib/calendar-helpers";
import { appointmentsClient } from "@/lib/appointments-client";
import { appointmentsToCalendarEvents } from "@/lib/appointment-calendar-mapping";
import { showError } from "@/lib/toast";
import type { AppointmentRow, CalendarEventRow } from "@/types";

type CalendarSubView = "month" | "week" | "day" | "list";

const VIEW_TABS: { id: CalendarSubView; label: string }[] = [
  { id: "month", label: "Month" },
  { id: "week", label: "Week" },
  { id: "day", label: "Day" },
  { id: "list", label: "List" },
];

function viewTitle(view: CalendarSubView, anchor: Date): string {
  if (view === "month") return formatMonthHeader(anchor);
  if (view === "week") return formatWeekHeader(anchor);
  if (view === "day") return formatDayHeader(anchor);
  return "Upcoming";
}

interface AppointmentsCalendarViewProps {
  /** Applied server-side via appointmentsClient.listRange — mirrors the List tab's filters. */
  statusFilter: string; // "all" | AppointmentStatus
  repFilter: string; // "all" | rep_id
  search: string;
}

/**
 * The active fetch window is derived from (view, anchorDate) — list mode
 * defaults to today → +14 days to match the main calendar page's List
 * behavior, since there's no natural "period" for an open-ended list.
 */
export function AppointmentsCalendarView({ statusFilter, repFilter, search }: AppointmentsCalendarViewProps) {
  const [view, setView] = useState<CalendarSubView>("month");
  const [anchorDate, setAnchorDate] = useState<Date>(() => new Date());
  const [appointments, setAppointments] = useState<AppointmentRow[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedAppointment, setSelectedAppointment] = useState<AppointmentRow | null>(null);

  const { windowStart, windowEnd } = useMemo(() => {
    if (view === "month") return { windowStart: startOfMonth(anchorDate), windowEnd: endOfMonth(anchorDate) };
    if (view === "week") return { windowStart: startOfWeek(anchorDate), windowEnd: endOfWeek(anchorDate) };
    if (view === "day") return { windowStart: startOfDay(anchorDate), windowEnd: endOfDay(anchorDate) };
    return { windowStart: startOfDay(anchorDate), windowEnd: addDays(anchorDate, 14) };
  }, [view, anchorDate]);

  const loadAppointments = useCallback(async () => {
    setIsLoading(true);
    try {
      const data = await appointmentsClient.listRange({
        start: windowStart.toISOString(),
        end: windowEnd.toISOString(),
        status: statusFilter !== "all" ? statusFilter : undefined,
        rep: repFilter !== "all" ? repFilter : undefined,
        search: search || undefined,
      });
      setAppointments(data.appointments);
    } catch (err) {
      showError(
        err instanceof Error ? err.message : "Failed to load appointments for the calendar view.",
      );
    } finally {
      setIsLoading(false);
    }
  }, [windowStart, windowEnd, statusFilter, repFilter, search]);

  useEffect(() => {
    void loadAppointments();
  }, [loadAppointments]);

  const events: CalendarEventRow[] = useMemo(
    () => appointmentsToCalendarEvents(appointments),
    [appointments],
  );

  const onAppointmentClick = useCallback((event: CalendarEventRow) => {
    if (event.appointment) setSelectedAppointment(event.appointment);
  }, []);

  const onNavPrev = useCallback(() => {
    if (view === "month") setAnchorDate((d) => addMonths(d, -1));
    else if (view === "week") setAnchorDate((d) => addWeeks(d, -1));
    else if (view === "day") setAnchorDate((d) => addDays(d, -1));
    else setAnchorDate((d) => addDays(d, -14));
  }, [view]);

  const onNavNext = useCallback(() => {
    if (view === "month") setAnchorDate((d) => addMonths(d, 1));
    else if (view === "week") setAnchorDate((d) => addWeeks(d, 1));
    else if (view === "day") setAnchorDate((d) => addDays(d, 1));
    else setAnchorDate((d) => addDays(d, 14));
  }, [view]);

  const onToday = useCallback(() => setAnchorDate(new Date()), []);

  // Jump straight to a picked date (any view; most useful in Day). Parse the
  // YYYY-MM-DD locally — new Date("YYYY-MM-DD") would interpret it as UTC and
  // shift the day for negative-offset timezones.
  const onPickDate = useCallback((value: string) => {
    const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
    if (!m) return; // cleared/partial input — keep the current anchor
    setAnchorDate(new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3])));
  }, []);

  return (
    <div className="rounded-xl border border-gray-200 overflow-hidden">
      {/* Nav + view tabs toolbar */}
      <div className="px-5 py-3 border-b border-gray-100 bg-gray-50/50 flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onToday}
            className="text-[12px] font-medium px-3 py-1.5 rounded-lg bg-gray-100 hover:bg-gray-200 text-gray-700 transition-colors"
          >
            Today
          </button>
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={onNavPrev}
              aria-label="Previous"
              className="text-[14px] px-2 py-1 rounded-lg bg-gray-100 hover:bg-gray-200 text-gray-700 transition-colors"
            >
              ←
            </button>
            <button
              type="button"
              onClick={onNavNext}
              aria-label="Next"
              className="text-[14px] px-2 py-1 rounded-lg bg-gray-100 hover:bg-gray-200 text-gray-700 transition-colors"
            >
              →
            </button>
          </div>
          <input
            type="date"
            value={toDateInputValue(anchorDate)}
            onChange={(e) => onPickDate(e.target.value)}
            aria-label="Jump to date"
            title="Jump to date"
            className="px-2 py-1 text-[12px] border border-gray-200 rounded-lg bg-white text-gray-600 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
          />
          <div className="text-[15px] font-semibold text-gray-800 ml-2">
            {viewTitle(view, anchorDate)}
          </div>
        </div>

        <div className="inline-flex rounded-lg bg-gray-100 p-0.5">
          {VIEW_TABS.map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => setView(tab.id)}
              className={
                "text-[12px] font-medium px-3 py-1 rounded-md transition-colors " +
                (view === tab.id
                  ? "bg-white text-blue-600 shadow-sm"
                  : "text-gray-600 hover:text-gray-900")
              }
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      <div className="p-4">
        {isLoading ? (
          <p className="text-[13px] text-gray-400 italic px-1 py-8 text-center">Loading appointments…</p>
        ) : view === "month" ? (
          <MonthView
            anchorDate={anchorDate}
            events={events}
            onDayClick={(d) => {
              setAnchorDate(d);
              setView("day");
            }}
            onAppointmentClick={onAppointmentClick}
          />
        ) : view === "week" ? (
          <WeekView anchorDate={anchorDate} events={events} onAppointmentClick={onAppointmentClick} />
        ) : view === "day" ? (
          <DayView anchorDate={anchorDate} events={events} onAppointmentClick={onAppointmentClick} />
        ) : (
          <ListView events={events} onAppointmentClick={onAppointmentClick} />
        )}
      </div>

      <AppointmentDetailPopover
        appointment={selectedAppointment}
        onClose={() => setSelectedAppointment(null)}
      />
    </div>
  );
}
