"use client";

import {
  formatDayHeader,
  formatMonthHeader,
  formatWeekHeader,
  fromDateInputValue,
  toDateInputValue,
} from "@/lib/calendar-helpers";
import type { CalendarSummary } from "@/types";

export type CalendarViewType = "month" | "week" | "day" | "list";

export type RangePreset =
  | "view"
  | "week"
  | "month"
  | "quarter"
  | "year"
  | "custom";

/**
 * Source filter shape. `"all"` = no filter; `"lead_events"` = restrict
 * to events whose attendees match a known lead; any other string =
 * exact-match a specific calendar's `calendar_name`.
 */
export type SourceFilter = "all" | "lead_events" | string;

interface CalendarToolbarProps {
  // View + nav
  view: CalendarViewType;
  setView: (v: CalendarViewType) => void;
  anchorDate: Date;
  /** Called when user clicks ← / →. The parent advances by view-period. */
  onNavPrev: () => void;
  onNavNext: () => void;
  onToday: () => void;
  /** True when nav arrows should be disabled (custom range active). */
  navDisabled: boolean;

  // Source filter
  sourceFilter: SourceFilter;
  setSourceFilter: (s: SourceFilter) => void;
  availableCalendars: CalendarSummary[];

  // Range filter
  rangePreset: RangePreset;
  setRangePreset: (p: RangePreset) => void;
  customFrom: Date | null;
  setCustomFrom: (d: Date | null) => void;
  customTo: Date | null;
  setCustomTo: (d: Date | null) => void;

  // Attendee search
  searchTerm: string;
  setSearchTerm: (s: string) => void;

  // Sync button
  isSyncing: boolean;
  onSync: () => void;

  // Source visibility legend — which event sources render on the grid.
  // Optional: the /appointments Calendar tab doesn't render Google events
  // at all, so it omits these props and the legend is hidden entirely.
  showGoogleEvents?: boolean;
  setShowGoogleEvents?: (v: boolean) => void;
  showAppointments?: boolean;
  setShowAppointments?: (v: boolean) => void;
}

function viewTitle(view: CalendarViewType, anchor: Date): string {
  if (view === "month") return formatMonthHeader(anchor);
  if (view === "week") return formatWeekHeader(anchor);
  if (view === "day") return formatDayHeader(anchor);
  return "Upcoming";
}

const VIEW_TABS: { id: CalendarViewType; label: string }[] = [
  { id: "month", label: "Month" },
  { id: "week", label: "Week" },
  { id: "day", label: "Day" },
  { id: "list", label: "List" },
];

export function CalendarToolbar({
  view,
  setView,
  anchorDate,
  onNavPrev,
  onNavNext,
  onToday,
  navDisabled,
  sourceFilter,
  setSourceFilter,
  availableCalendars,
  rangePreset,
  setRangePreset,
  customFrom,
  setCustomFrom,
  customTo,
  setCustomTo,
  searchTerm,
  setSearchTerm,
  isSyncing,
  onSync,
  showGoogleEvents,
  setShowGoogleEvents,
  showAppointments,
  setShowAppointments,
}: CalendarToolbarProps) {
  const showLegend = setShowGoogleEvents !== undefined && setShowAppointments !== undefined;
  return (
    <div className="bg-white border-b border-gray-200 px-6 py-3 flex-shrink-0">
      {/* Top row — nav + title + sync */}
      <div className="flex items-center justify-between gap-3 mb-2">
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
              disabled={navDisabled}
              aria-label="Previous"
              className="text-[14px] px-2 py-1 rounded-lg bg-gray-100 hover:bg-gray-200 disabled:opacity-40 disabled:cursor-not-allowed text-gray-700 transition-colors"
            >
              ←
            </button>
            <button
              type="button"
              onClick={onNavNext}
              disabled={navDisabled}
              aria-label="Next"
              className="text-[14px] px-2 py-1 rounded-lg bg-gray-100 hover:bg-gray-200 disabled:opacity-40 disabled:cursor-not-allowed text-gray-700 transition-colors"
            >
              →
            </button>
          </div>
          <div className="text-[15px] font-semibold text-gray-800 ml-2">
            {viewTitle(view, anchorDate)}
          </div>
        </div>

        <button
          type="button"
          onClick={onSync}
          disabled={isSyncing}
          className="text-[12px] font-semibold px-3 py-1.5 rounded-lg bg-accent-500 hover:bg-accent-600 disabled:bg-gray-300 disabled:cursor-not-allowed text-white transition-colors"
        >
          {isSyncing ? "Syncing…" : "Sync now"}
        </button>
      </div>

      {/* Bottom row — view tabs + filters */}
      <div className="flex items-center justify-between gap-3 flex-wrap">
        {/* View toggle */}
        <div className="inline-flex rounded-lg bg-gray-100 p-0.5">
          {VIEW_TABS.map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => setView(tab.id)}
              className={
                "text-[12px] font-medium px-3 py-1 rounded-md transition-colors " +
                (view === tab.id
                  ? "bg-white text-accent-600 shadow-sm"
                  : "text-gray-600 hover:text-gray-900")
              }
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Filters row */}
        <div className="flex items-center gap-2 flex-wrap">
          {/* Source visibility legend */}
          {showLegend && (
            <div className="flex items-center gap-3 pr-2 mr-1 border-r border-gray-200">
              <label className="flex items-center gap-1.5 text-[12px] text-gray-700 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={showGoogleEvents}
                  onChange={(e) => setShowGoogleEvents?.(e.target.checked)}
                  className="rounded border-gray-300 text-accent-500 focus:ring-accent-300"
                />
                <span className="w-2 h-2 rounded-full bg-accent-400 flex-shrink-0" />
                Google Calendar
              </label>
              <label className="flex items-center gap-1.5 text-[12px] text-gray-700 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={showAppointments}
                  onChange={(e) => setShowAppointments?.(e.target.checked)}
                  className="rounded border-gray-300 text-blue-500 focus:ring-blue-300"
                />
                <span className="w-2 h-2 rounded-full bg-blue-400 flex-shrink-0" />
                Appointments
              </label>
            </div>
          )}

          {/* Source filter */}
          <select
            value={sourceFilter}
            onChange={(e) => setSourceFilter(e.target.value as SourceFilter)}
            className="text-[12px] px-3 py-1.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-accent-300 bg-white"
            aria-label="Calendar source"
          >
            <option value="all">All calendars</option>
            <option value="lead_events">Lead events</option>
            {availableCalendars.length > 0 && (
              <optgroup label="Specific calendars">
                {availableCalendars.map((c) => (
                  <option key={c.calendar_id} value={c.calendar_name || c.calendar_id}>
                    {c.calendar_name || c.calendar_id}
                  </option>
                ))}
              </optgroup>
            )}
          </select>

          {/* Range preset */}
          <select
            value={rangePreset}
            onChange={(e) => setRangePreset(e.target.value as RangePreset)}
            className="text-[12px] px-3 py-1.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-accent-300 bg-white"
            aria-label="Date range"
          >
            <option value="view">Follow view</option>
            <option value="week">This week</option>
            <option value="month">This month</option>
            <option value="quarter">This quarter</option>
            <option value="year">This year</option>
            <option value="custom">Custom…</option>
          </select>

          {/* Custom range inputs */}
          {rangePreset === "custom" && (
            <>
              <input
                type="date"
                value={toDateInputValue(customFrom)}
                onChange={(e) =>
                  setCustomFrom(fromDateInputValue(e.target.value))
                }
                className="text-[12px] px-2 py-1.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-accent-300 bg-white"
                aria-label="From date"
              />
              <span className="text-[11px] text-gray-400">→</span>
              <input
                type="date"
                value={toDateInputValue(customTo)}
                onChange={(e) =>
                  setCustomTo(fromDateInputValue(e.target.value))
                }
                className="text-[12px] px-2 py-1.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-accent-300 bg-white"
                aria-label="To date"
              />
            </>
          )}

          {/* Attendee search */}
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Filter by attendee email"
            className="text-[12px] px-3 py-1.5 border border-gray-300 rounded-lg w-56 focus:outline-none focus:ring-2 focus:ring-accent-300"
          />
        </div>
      </div>
    </div>
  );
}
