"use client";

import { Card, CardBody } from "@/components/ui/card";
import {
  dayKey,
  formatDayHeader,
  formatTimeRange,
  groupEventsByDay,
} from "@/lib/calendar-helpers";
import type { CalendarEventRow } from "@/types";

interface ListViewProps {
  events: CalendarEventRow[];
}

function EventRow({ event }: { event: CalendarEventRow }) {
  const time = formatTimeRange(event.start_time, event.end_time, event.is_all_day);
  const attendeeCount = event.attendees.length;
  return (
    <a
      href={event.event_link || "#"}
      target="_blank"
      rel="noopener noreferrer"
      className="block px-4 py-3 hover:bg-gray-50 transition-colors border-b border-gray-100 last:border-b-0"
    >
      <div className="flex items-baseline gap-3">
        <span className="text-[11px] font-mono text-gray-500 w-32 flex-shrink-0">
          {time}
        </span>
        <div className="flex-1 min-w-0">
          <div className="text-[14px] font-medium text-gray-800 truncate">
            {event.title || "(untitled event)"}
          </div>
          <div className="text-[11px] text-gray-500 mt-0.5 truncate">
            {event.calendar_name && (
              <span className="mr-2">📆 {event.calendar_name}</span>
            )}
            {event.organizer_email && (
              <span className="mr-2">👤 {event.organizer_email}</span>
            )}
            {attendeeCount > 0 && (
              <span className="mr-2">
                👥 {attendeeCount} attendee{attendeeCount === 1 ? "" : "s"}
              </span>
            )}
            {event.location && (
              <span className="mr-2">📍 {event.location}</span>
            )}
          </div>
        </div>
        {event.status === "tentative" && (
          <span className="text-[10px] text-amber-600 font-semibold uppercase">
            Tentative
          </span>
        )}
      </div>
    </a>
  );
}

/**
 * Flat day-grouped list, ordered by date ASC. The original /calendar
 * page was exclusively this view; here it becomes one of four.
 */
export function ListView({ events }: ListViewProps) {
  if (events.length === 0) {
    return (
      <Card>
        <CardBody>
          <p className="text-[13px] text-gray-400 italic">
            No events in this window. Adjust filters or click <b>Sync now</b>.
          </p>
        </CardBody>
      </Card>
    );
  }

  const grouped = groupEventsByDay(events);
  const orderedKeys = Array.from(grouped.keys()).sort();

  return (
    <div>
      {orderedKeys.map((key) => {
        const [y, m, d] = key.split("-").map((s) => parseInt(s, 10));
        const dayDate = new Date(y, m - 1, d);
        const dayEvents = grouped.get(key) || [];
        return (
          <div key={key} className="mb-4">
            <div className="text-[11px] font-bold uppercase tracking-wider text-gray-500 px-1 py-2">
              {formatDayHeader(dayDate)}
            </div>
            <Card>
              <CardBody noPadding>
                {dayEvents.map((e) => (
                  <EventRow key={e.id} event={e} />
                ))}
              </CardBody>
            </Card>
          </div>
        );
      })}
    </div>
  );
}
