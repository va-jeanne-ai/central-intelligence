"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { CalendarToolbar } from "@/components/calendar/calendar-toolbar";
import type {
  CalendarViewType,
  RangePreset,
  SourceFilter,
} from "@/components/calendar/calendar-toolbar";
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
  endOfQuarter,
  endOfWeek,
  endOfYear,
  startOfDay,
  startOfMonth,
  startOfQuarter,
  startOfWeek,
  startOfYear,
} from "@/lib/calendar-helpers";
import { calendarClient } from "@/lib/calendar-client";
import { appointmentsClient } from "@/lib/appointments-client";
import { appointmentsToCalendarEvents } from "@/lib/appointment-calendar-mapping";
import { showError, showSuccess } from "@/lib/toast";
import type { AppointmentRow, CalendarEventRow, CalendarSummary } from "@/types";

/**
 * The full calendar surface. Owns:
 *   - `view`          which of the four views is rendered
 *   - `anchorDate`    date the view is centered on (advanced by ← / →)
 *   - `sourceFilter`  "all" / "lead_events" / a specific calendar name
 *   - `rangePreset`   "follow view" or a fixed-window preset, or custom
 *   - `customFrom/To` the explicit window when rangePreset === "custom"
 *   - `searchTerm`    attendee email substring (debounced)
 *
 * The active query window is derived from `rangePreset + view + anchor
 * + custom` so the data fetch is always a deterministic function of
 * the current state. The view components themselves are pure — they
 * receive `events` and render.
 */
export function CalendarView() {
  const [view, setView] = useState<CalendarViewType>("month");
  const [anchorDate, setAnchorDate] = useState<Date>(() => new Date());

  const [sourceFilter, setSourceFilter] = useState<SourceFilter>("all");
  const [availableCalendars, setAvailableCalendars] = useState<CalendarSummary[]>([]);

  const [rangePreset, setRangePreset] = useState<RangePreset>("view");
  const [customFrom, setCustomFrom] = useState<Date | null>(null);
  const [customTo, setCustomTo] = useState<Date | null>(null);

  const [searchTerm, setSearchTerm] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");

  const [events, setEvents] = useState<CalendarEventRow[]>([]);
  const [appointments, setAppointments] = useState<AppointmentRow[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSyncing, setIsSyncing] = useState(false);

  // Source visibility — both on by default. Purely a display filter; the
  // underlying fetches still run so toggling is instant.
  const [showGoogleEvents, setShowGoogleEvents] = useState(true);
  const [showAppointments, setShowAppointments] = useState(true);

  // Detail popover — set when an appointment chip is clicked.
  const [selectedAppointment, setSelectedAppointment] = useState<AppointmentRow | null>(null);

  // ─── Active window derivation ───────────────────────────────────────────
  // The window the backend gets is a function of (rangePreset, view,
  // anchorDate, customFrom, customTo). Anytime any of those change we
  // refetch.
  const { windowStart, windowEnd } = useMemo(() => {
    if (rangePreset === "custom") {
      const s = customFrom ? startOfDay(customFrom) : addDays(new Date(), -14);
      const e = customTo ? endOfDay(customTo) : addDays(new Date(), 14);
      return { windowStart: s, windowEnd: e };
    }

    const now = new Date();
    if (rangePreset === "week") {
      return { windowStart: startOfWeek(now), windowEnd: endOfWeek(now) };
    }
    if (rangePreset === "month") {
      return { windowStart: startOfMonth(now), windowEnd: endOfMonth(now) };
    }
    if (rangePreset === "quarter") {
      return { windowStart: startOfQuarter(now), windowEnd: endOfQuarter(now) };
    }
    if (rangePreset === "year") {
      return { windowStart: startOfYear(now), windowEnd: endOfYear(now) };
    }

    // "Follow view" — window matches the active view's natural span.
    if (view === "month") {
      return { windowStart: startOfMonth(anchorDate), windowEnd: endOfMonth(anchorDate) };
    }
    if (view === "week") {
      return { windowStart: startOfWeek(anchorDate), windowEnd: endOfWeek(anchorDate) };
    }
    if (view === "day") {
      return { windowStart: startOfDay(anchorDate), windowEnd: endOfDay(anchorDate) };
    }
    // List view: today → +14 days, same default as the original page.
    return { windowStart: startOfDay(anchorDate), windowEnd: addDays(anchorDate, 14) };
  }, [rangePreset, view, anchorDate, customFrom, customTo]);

  // ─── Search debounce ───────────────────────────────────────────────────
  useEffect(() => {
    const id = setTimeout(() => setDebouncedSearch(searchTerm.trim()), 300);
    return () => clearTimeout(id);
  }, [searchTerm]);

  // ─── Load available calendars once on mount ────────────────────────────
  useEffect(() => {
    void (async () => {
      try {
        const data = await calendarClient.listCalendars();
        setAvailableCalendars(data.calendars);
      } catch {
        // Source dropdown still works with the "All" + "Lead events"
        // options even if this fetch fails; degrade silently.
      }
    })();
  }, []);

  // ─── Load events whenever the effective filter set changes ─────────────
  const loadEvents = useCallback(async () => {
    setIsLoading(true);
    try {
      // Translate the source filter into the right backend param.
      const params: Parameters<typeof calendarClient.list>[0] = {
        start: windowStart.toISOString(),
        end: windowEnd.toISOString(),
        limit: 300,
      };
      if (debouncedSearch) params.attendee_email_contains = debouncedSearch;
      if (sourceFilter === "lead_events") {
        params.only_lead_events = true;
      } else if (sourceFilter !== "all") {
        params.calendar_name = sourceFilter;
      }

      const data = await calendarClient.list(params);
      setEvents(data.events);
    } catch (err) {
      showError(
        err instanceof Error
          ? err.message
          : "Failed to load calendar events. Try again in a minute.",
      );
    } finally {
      setIsLoading(false);
    }
  }, [windowStart, windowEnd, debouncedSearch, sourceFilter]);

  useEffect(() => {
    void loadEvents();
  }, [loadEvents]);

  // ─── Load appointments in the same visible window ───────────────────────
  // Independent of the Google-events fetch (separate loading flag) so a
  // slow appointments call never blocks the Google grid from painting, and
  // vice versa. Errors degrade silently to an empty appointments list —
  // the Google calendar overlay still works standalone if this fails.
  const loadAppointments = useCallback(async () => {
    try {
      const data = await appointmentsClient.listRange({
        start: windowStart.toISOString(),
        end: windowEnd.toISOString(),
      });
      setAppointments(data.appointments);
    } catch {
      setAppointments([]);
    }
  }, [windowStart, windowEnd]);

  useEffect(() => {
    void loadAppointments();
  }, [loadAppointments]);

  // ─── Merge sources for rendering ────────────────────────────────────────
  // Google events keep rendering byte-identical to before when the
  // appointments toggle is off (`events` array itself is untouched). When
  // both sources are visible, the merged list is sorted by start_time so
  // a day/list cell interleaves Google events and appointments
  // chronologically rather than always showing Google events first.
  const visibleEvents = useMemo(() => {
    const google = showGoogleEvents ? events : [];
    const appts = showAppointments ? appointmentsToCalendarEvents(appointments) : [];
    if (google.length === 0 || appts.length === 0) return [...google, ...appts];
    return [...google, ...appts].sort((a, b) => {
      const at = a.start_time ? new Date(a.start_time).getTime() : 0;
      const bt = b.start_time ? new Date(b.start_time).getTime() : 0;
      return at - bt;
    });
  }, [events, appointments, showGoogleEvents, showAppointments]);

  const onAppointmentClick = useCallback((event: CalendarEventRow) => {
    if (event.appointment) setSelectedAppointment(event.appointment);
  }, []);

  // ─── Nav handlers ──────────────────────────────────────────────────────
  // Arrows are view-aware: month/week/day step by their respective
  // periods; list view steps by 14d (matching its natural window).
  // Disabled when a custom range is active (the explicit window owns
  // the data, not the anchor).
  const navDisabled = rangePreset === "custom";

  const onNavPrev = useCallback(() => {
    if (navDisabled) return;
    if (view === "month") setAnchorDate(addMonths(anchorDate, -1));
    else if (view === "week") setAnchorDate(addWeeks(anchorDate, -1));
    else if (view === "day") setAnchorDate(addDays(anchorDate, -1));
    else setAnchorDate(addDays(anchorDate, -14));
  }, [anchorDate, view, navDisabled]);

  const onNavNext = useCallback(() => {
    if (navDisabled) return;
    if (view === "month") setAnchorDate(addMonths(anchorDate, 1));
    else if (view === "week") setAnchorDate(addWeeks(anchorDate, 1));
    else if (view === "day") setAnchorDate(addDays(anchorDate, 1));
    else setAnchorDate(addDays(anchorDate, 14));
  }, [anchorDate, view, navDisabled]);

  const onToday = useCallback(() => {
    setAnchorDate(new Date());
    // If they're on custom range, snapping to "today" should drop
    // the explicit window so the view can actually move.
    if (rangePreset === "custom") setRangePreset("view");
  }, [rangePreset]);

  // ─── Sync button ───────────────────────────────────────────────────────
  async function onSync() {
    if (isSyncing) return;
    setIsSyncing(true);
    try {
      await calendarClient.sync();
      showSuccess("Calendar sync queued. Refreshing in a few seconds…");
      setTimeout(() => {
        void loadEvents();
        setIsSyncing(false);
      }, 6000);
    } catch (err) {
      showError(
        err instanceof Error ? err.message : "Failed to start calendar sync.",
      );
      setIsSyncing(false);
    }
  }

  // ─── Render ────────────────────────────────────────────────────────────
  return (
    <div className="flex flex-col flex-1 overflow-hidden">
      <CalendarToolbar
        view={view}
        setView={setView}
        anchorDate={anchorDate}
        onNavPrev={onNavPrev}
        onNavNext={onNavNext}
        onToday={onToday}
        navDisabled={navDisabled}
        sourceFilter={sourceFilter}
        setSourceFilter={setSourceFilter}
        availableCalendars={availableCalendars}
        rangePreset={rangePreset}
        setRangePreset={setRangePreset}
        customFrom={customFrom}
        setCustomFrom={setCustomFrom}
        customTo={customTo}
        setCustomTo={setCustomTo}
        searchTerm={searchTerm}
        setSearchTerm={setSearchTerm}
        isSyncing={isSyncing}
        onSync={onSync}
        showGoogleEvents={showGoogleEvents}
        setShowGoogleEvents={setShowGoogleEvents}
        showAppointments={showAppointments}
        setShowAppointments={setShowAppointments}
      />

      <div className="flex-1 overflow-y-auto px-6 py-5">
        {isLoading ? (
          <p className="text-[13px] text-gray-400 italic">Loading events…</p>
        ) : view === "month" ? (
          <MonthView
            anchorDate={anchorDate}
            events={visibleEvents}
            onDayClick={(d) => {
              setAnchorDate(d);
              setView("day");
            }}
            onAppointmentClick={onAppointmentClick}
          />
        ) : view === "week" ? (
          <WeekView anchorDate={anchorDate} events={visibleEvents} onAppointmentClick={onAppointmentClick} />
        ) : view === "day" ? (
          <DayView anchorDate={anchorDate} events={visibleEvents} onAppointmentClick={onAppointmentClick} />
        ) : (
          <ListView events={visibleEvents} onAppointmentClick={onAppointmentClick} />
        )}
      </div>

      <AppointmentDetailPopover
        appointment={selectedAppointment}
        onClose={() => setSelectedAppointment(null)}
      />
    </div>
  );
}
