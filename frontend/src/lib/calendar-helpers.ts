// Pure date math + formatting for the calendar page.
//
// No external date library — the project hasn't installed one and the
// existing promo-calendar grid is hand-rolled the same way.
//
// All "start of X" helpers return a fresh Date in the *local* timezone
// at midnight. All formatters use the browser's locale where it makes
// sense for the user-facing label.

import type { CalendarEventRow } from "@/types";

// ─── Period boundaries ───────────────────────────────────────────────────────

export function startOfDay(d: Date): Date {
  const r = new Date(d);
  r.setHours(0, 0, 0, 0);
  return r;
}

export function endOfDay(d: Date): Date {
  const r = new Date(d);
  r.setHours(23, 59, 59, 999);
  return r;
}

/** Monday-anchored start of the week containing d. */
export function startOfWeek(d: Date): Date {
  const r = startOfDay(d);
  // JS: Sunday=0, Monday=1, …, Saturday=6. We shift to Monday-start.
  const day = r.getDay();
  const delta = (day + 6) % 7; // Mon→0, Tue→1, …, Sun→6
  r.setDate(r.getDate() - delta);
  return r;
}

export function endOfWeek(d: Date): Date {
  const start = startOfWeek(d);
  const end = new Date(start);
  end.setDate(start.getDate() + 6);
  return endOfDay(end);
}

export function startOfMonth(d: Date): Date {
  const r = startOfDay(d);
  r.setDate(1);
  return r;
}

export function endOfMonth(d: Date): Date {
  const r = startOfMonth(d);
  r.setMonth(r.getMonth() + 1);
  r.setDate(0); // last day of previous month = last day of d's month
  return endOfDay(r);
}

export function startOfQuarter(d: Date): Date {
  const r = startOfMonth(d);
  // Floor month to quarter start (0,3,6,9).
  r.setMonth(Math.floor(r.getMonth() / 3) * 3);
  return r;
}

export function endOfQuarter(d: Date): Date {
  const r = startOfQuarter(d);
  r.setMonth(r.getMonth() + 3);
  r.setDate(0);
  return endOfDay(r);
}

export function startOfYear(d: Date): Date {
  const r = startOfDay(d);
  r.setMonth(0, 1);
  return r;
}

export function endOfYear(d: Date): Date {
  const r = startOfDay(d);
  r.setMonth(11, 31);
  return endOfDay(r);
}

// ─── Date arithmetic ────────────────────────────────────────────────────────

export function addDays(d: Date, n: number): Date {
  const r = new Date(d);
  r.setDate(r.getDate() + n);
  return r;
}

export function addWeeks(d: Date, n: number): Date {
  return addDays(d, n * 7);
}

export function addMonths(d: Date, n: number): Date {
  const r = new Date(d);
  r.setMonth(r.getMonth() + n);
  return r;
}

export function isSameDay(a: Date, b: Date): boolean {
  return (
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate()
  );
}

// ─── Month grid ─────────────────────────────────────────────────────────────

/**
 * Build a 6-row × 7-column grid spanning the given month plus padding
 * days from the previous + next months. Monday-anchored.
 *
 * Returns 42 Date objects flat (consumers reshape into rows of 7).
 */
export function buildMonthGrid(monthAnchor: Date): Date[] {
  const monthStart = startOfMonth(monthAnchor);
  // Padding days *before* monthStart so the grid begins on a Monday.
  const dayOfWeek = monthStart.getDay();
  const padBefore = (dayOfWeek + 6) % 7; // Mon=0…Sun=6
  const gridStart = addDays(monthStart, -padBefore);
  const cells: Date[] = [];
  for (let i = 0; i < 42; i++) {
    cells.push(addDays(gridStart, i));
  }
  return cells;
}

// ─── Event grouping ─────────────────────────────────────────────────────────

/**
 * Group events by the local day their start_time falls on.
 *
 * Returns a Map keyed by a stable day-string (`YYYY-MM-DD` in the local
 * timezone) so callers can look up "events on this date" by passing
 * dayKey(date).
 */
export function dayKey(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

export function groupEventsByDay(
  events: CalendarEventRow[],
): Map<string, CalendarEventRow[]> {
  const out = new Map<string, CalendarEventRow[]>();
  for (const e of events) {
    if (!e.start_time) continue;
    const d = new Date(e.start_time);
    const key = dayKey(d);
    const list = out.get(key);
    if (list) list.push(e);
    else out.set(key, [e]);
  }
  return out;
}

// ─── Formatters ─────────────────────────────────────────────────────────────

export function formatTimeRange(
  startIso: string | null,
  endIso: string | null,
  isAllDay: boolean,
): string {
  if (isAllDay) return "All day";
  if (!startIso) return "—";
  const start = new Date(startIso);
  const opts: Intl.DateTimeFormatOptions = {
    hour: "numeric",
    minute: "2-digit",
  };
  const startStr = start.toLocaleTimeString(undefined, opts);
  if (!endIso) return startStr;
  const end = new Date(endIso);
  return `${startStr} – ${end.toLocaleTimeString(undefined, opts)}`;
}

export function formatDayHeader(d: Date): string {
  return d.toLocaleDateString(undefined, {
    weekday: "long",
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export function formatWeekHeader(weekStart: Date): string {
  const end = addDays(weekStart, 6);
  // Compact: "May 26 – Jun 1, 2026" or "May 4 – 10, 2026" when same month.
  const sameMonth = weekStart.getMonth() === end.getMonth();
  const sameYear = weekStart.getFullYear() === end.getFullYear();
  const startStr = weekStart.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    ...(sameYear ? {} : { year: "numeric" }),
  });
  if (sameMonth) {
    return `${startStr} – ${end.getDate()}, ${end.getFullYear()}`;
  }
  const endStr = end.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
  return `${startStr} – ${endStr}`;
}

export function formatMonthHeader(d: Date): string {
  return d.toLocaleDateString(undefined, {
    month: "long",
    year: "numeric",
  });
}

/**
 * Format a Date as YYYY-MM-DD for use in `<input type="date">`
 * (which doesn't accept ISO datetime strings).
 */
export function toDateInputValue(d: Date | null): string {
  if (!d) return "";
  return dayKey(d);
}

/** Parse the `<input type="date">` value into a local-midnight Date. */
export function fromDateInputValue(value: string): Date | null {
  if (!value) return null;
  const [y, m, day] = value.split("-").map((s) => parseInt(s, 10));
  if (!y || !m || !day) return null;
  return new Date(y, m - 1, day, 0, 0, 0, 0);
}
