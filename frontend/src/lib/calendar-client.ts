// Thin wrapper around the calendar surface endpoints.
//
// Powers both the dedicated /calendar page and the lead-detail Events
// card. The lead variant ultimately calls /leads/{id}/events (not
// exposed here — that's done inline on the lead page since it's
// scoped by path param). This client covers the first-class calendar
// page only.

import { apiClient } from "@/lib/api-client";
import type {
  CalendarEventsResponse,
  CalendarListResponse,
} from "@/types";

interface ListEventsParams {
  start?: string;
  end?: string;
  attendee_email_contains?: string;
  /** Filter to one specific source calendar by its display name. */
  calendar_name?: string;
  /** When true, restrict to events with at least one attendee matching a lead. */
  only_lead_events?: boolean;
  limit?: number;
  offset?: number;
}

export const calendarClient = {
  /**
   * GET /api/v1/calendar/events — list the current user's events
   * within a time window. Default window (backend-side) is
   * now → +14 days, ordered by start_time ASC.
   */
  list(params: ListEventsParams = {}): Promise<CalendarEventsResponse> {
    const search = new URLSearchParams();
    if (params.start) search.set("start", params.start);
    if (params.end) search.set("end", params.end);
    if (params.attendee_email_contains) {
      search.set("attendee_email_contains", params.attendee_email_contains);
    }
    if (params.calendar_name) {
      search.set("calendar_name", params.calendar_name);
    }
    if (params.only_lead_events) {
      search.set("only_lead_events", "true");
    }
    if (params.limit !== undefined) search.set("limit", String(params.limit));
    if (params.offset !== undefined) search.set("offset", String(params.offset));
    const qs = search.toString();
    const path = qs ? `/calendar/events?${qs}` : "/calendar/events";
    return apiClient.get<CalendarEventsResponse>(path, { silent: true });
  },

  /**
   * GET /api/v1/calendar/calendars — distinct calendars the user has
   * events from. Used to populate the source-filter dropdown.
   */
  listCalendars(): Promise<CalendarListResponse> {
    return apiClient.get<CalendarListResponse>("/calendar/calendars", {
      silent: true,
    });
  },

  /** POST /api/v1/calendar/sync — enqueue a sync for the current user. */
  sync(): Promise<{ task_id: string; user_id: string }> {
    return apiClient.post<{ task_id: string; user_id: string }>(
      "/calendar/sync",
      {},
    );
  },
};
