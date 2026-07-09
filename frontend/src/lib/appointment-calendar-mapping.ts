// Pure mapping: AppointmentRow → CalendarEventRow.
//
// Lets appointments render through the existing calendar view components
// (MonthView / WeekView / DayView / ListView / EventChip) without forking
// them — those components only know about CalendarEventRow, so an
// appointment just needs to be shaped like one.
//
// Kept dependency-free and side-effect-free so it's trivially testable if a
// test runner is ever added to this project.

import type { AppointmentRow, CalendarEventRow } from "@/types";

/**
 * Map a single appointment into the shape CalendarView's sub-views expect.
 *
 * - title: contact_name, falling back to appointment_type, then a generic
 *   label — mirrors the table's `appt.contact_name ?? "—"` fallback but
 *   never renders a bare em dash as an event title.
 * - start/end: scheduledAt / end_at as-is (both already ISO strings from
 *   the backend; no timezone conversion — matches how calendar-helpers.ts
 *   treats every other event, i.e. `new Date(iso)` in the browser's local
 *   zone).
 * - status: passed through unchanged so EventChip can resolve the same
 *   color palette used on the /appointments list pills.
 * - source/appointment: marks this row as an appointment (not a Google
 *   event) and carries the original record for the detail popover.
 */
export function appointmentToCalendarEvent(appt: AppointmentRow): CalendarEventRow {
  const title = appt.contact_name?.trim() || appt.appointment_type?.trim() || "Appointment";

  return {
    id: `appointment:${appt.id}`,
    title,
    description: appt.appointment_type,
    calendar_name: "Appointments",
    start_time: appt.scheduledAt,
    end_time: appt.end_at,
    is_all_day: false,
    organizer_email: null,
    attendees: [],
    event_link: null,
    location: null,
    status: appt.status,
    source: "appointment",
    appointment: appt,
  };
}

/** Map a full list — order preserved, no filtering/sorting performed here. */
export function appointmentsToCalendarEvents(appointments: AppointmentRow[]): CalendarEventRow[] {
  return appointments.map(appointmentToCalendarEvent);
}
