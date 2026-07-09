// Thin wrapper around GET /appointments for range-based (calendar) fetches.
//
// The table on /appointments builds its own querystring inline (it owns
// page/pageSize + several filters already wired to usePagination). This
// client is for the two calendar surfaces — the /appointments Calendar tab
// and the /calendar page's appointments overlay — which both need "give me
// every appointment in this visible date range" rather than a paginated
// table page.

import { apiClient } from "@/lib/api-client";
import type { AppointmentsListResponse } from "@/types";

// Backend hard-caps per_page at 1000 (see routes/appointments.py). A single
// month is typically <400 appointments (1,922 total across all time as of
// 2026-07), so one request at this size covers month/week/day/list views
// without pagination. If usage ever approaches the cap, revisit — the
// options are date-window narrowing (already available via start/end) or a
// dedicated range endpoint.
const CALENDAR_RANGE_PAGE_SIZE = 1000;

export interface ListAppointmentsRangeParams {
  /** ISO date/datetime — inclusive lower bound on scheduled_at. */
  start?: string;
  /** ISO date/datetime — inclusive upper bound on scheduled_at. */
  end?: string;
  status?: string;
  rep?: string;
  search?: string;
}

export const appointmentsClient = {
  /**
   * Fetch all appointments in a date range in one page, sized generously
   * for calendar rendering (month/week/day/list views all fit comfortably
   * under the 1000-row cap). Callers that need the full table's pagination
   * UX should keep using apiClient directly, as /appointments/page.tsx does.
   */
  listRange(params: ListAppointmentsRangeParams): Promise<AppointmentsListResponse> {
    const search = new URLSearchParams();
    if (params.start) search.set("start", params.start);
    if (params.end) search.set("end", params.end);
    if (params.status) search.set("status", params.status);
    if (params.rep) search.set("rep", params.rep);
    if (params.search) search.set("search", params.search);
    search.set("page", "1");
    search.set("per_page", String(CALENDAR_RANGE_PAGE_SIZE));
    return apiClient.get<AppointmentsListResponse>(
      `/appointments?${search.toString()}`,
      { silent: true },
    );
  },
};
