"use client";

import { useState, useEffect } from "react";
import { apiClient } from "@/lib/api-client";
import { useAuth } from "@/hooks/use-auth";

// ─── Types ─────────────────────────────────────────────────────────────────────

interface ScheduleBriefItem {
  title: string;
  start: string; // ISO 8601 (UTC)
  end: string | null;
  is_all_day: boolean;
  location: string | null;
  attendees_count: number;
  status: string | null;
}

interface ScheduleBriefResponse {
  items: ScheduleBriefItem[];
  summary: string;
  event_count: number;
  calendar_connected: boolean;
  generated_at: string;
}

// ─── Helpers ───────────────────────────────────────────────────────────────────

/** Local-day bounds [00:00, 23:59:59.999] as ISO strings, so "today" matches
 *  the user's wall clock regardless of the UTC-stored event times. */
function todayBounds(): { start: string; end: string } {
  const now = new Date();
  const startOfDay = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 0, 0, 0, 0);
  const endOfDay = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 23, 59, 59, 999);
  return { start: startOfDay.toISOString(), end: endOfDay.toISOString() };
}

/** Render an event's time in the browser's locale/timezone. */
function formatEventTime(item: ScheduleBriefItem): string {
  if (item.is_all_day) return "All day";
  const start = new Date(item.start);
  const startStr = start.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
  if (item.end) {
    const end = new Date(item.end);
    const endStr = end.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
    return `${startStr} – ${endStr}`;
  }
  return startStr;
}

// ─── Shell ─────────────────────────────────────────────────────────────────────

function BriefShell({ children }: { children: React.ReactNode }) {
  return (
    <aside
      className="bg-sky-50 border border-sky-200 rounded-xl p-5 flex flex-col gap-4 shadow-sm"
      aria-label="Today's Schedule"
    >
      <div className="flex flex-col gap-0.5">
        <div className="flex items-center gap-2">
          <span className="text-lg leading-none" role="img" aria-label="Calendar">
            📅
          </span>
          <h2 className="text-sm font-bold text-sky-900">Today&apos;s Schedule</h2>
        </div>
        <p className="text-xs text-sky-700 ml-7">
          Your calendar for today, in your timezone
        </p>
      </div>
      <hr className="border-sky-200" />
      {children}
    </aside>
  );
}

// ─── Skeleton ──────────────────────────────────────────────────────────────────

function BriefSkeleton() {
  return (
    <BriefShell>
      <div className="flex flex-col gap-3">
        {[1, 2, 3].map((i) => (
          <div key={i} className="flex items-start gap-3">
            <div className="w-14 h-3 bg-sky-200/60 rounded animate-pulse flex-shrink-0 mt-0.5" />
            <div className="flex-1 space-y-1.5">
              <div className="h-3 w-2/3 bg-sky-200/60 rounded animate-pulse" />
              <div className="h-3 w-1/3 bg-sky-200/40 rounded animate-pulse" />
            </div>
          </div>
        ))}
      </div>
    </BriefShell>
  );
}

// ─── Component ─────────────────────────────────────────────────────────────────

export function ScheduleBrief() {
  const { isLoading: authLoading } = useAuth();
  const [items, setItems] = useState<ScheduleBriefItem[]>([]);
  const [summary, setSummary] = useState("");
  const [calendarConnected, setCalendarConnected] = useState(true);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (authLoading) return;

    let cancelled = false;

    async function fetchBrief(): Promise<void> {
      try {
        const { start, end } = todayBounds();
        const params = new URLSearchParams({ start, end });
        const data = await apiClient.get<ScheduleBriefResponse>(
          `/dashboard/schedule-brief?${params.toString()}`,
          { silent: true },
        );
        if (!cancelled) {
          setItems(data.items);
          setSummary(data.summary);
          setCalendarConnected(data.calendar_connected);
        }
      } catch {
        // On error the panel falls through to its empty state — not critical.
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    }

    void fetchBrief();

    return () => {
      cancelled = true;
    };
  }, [authLoading]);

  if (isLoading) return <BriefSkeleton />;

  if (items.length === 0) {
    return (
      <BriefShell>
        <p className="text-xs text-sky-700">
          {calendarConnected
            ? "Nothing on your calendar today. Enjoy the open day."
            : "Connect your Google Calendar to see your schedule here."}
        </p>
      </BriefShell>
    );
  }

  return (
    <BriefShell>
      {summary && (
        <p className="text-sm font-semibold text-sky-900 leading-snug -mt-1">
          {summary}
        </p>
      )}
      <ul className="flex flex-col gap-3" role="list">
        {items.map((item, index) => (
          <li key={`${item.title}-${item.start}-${index}`} className="flex items-start gap-3">
            <span className="flex-shrink-0 w-16 text-[11px] font-semibold tabular-nums text-sky-700 mt-0.5">
              {formatEventTime(item)}
            </span>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium text-sky-900 leading-snug truncate">
                {item.title}
              </p>
              <div className="flex items-center gap-2 text-[11px] text-sky-600 mt-0.5">
                {item.location && <span className="truncate">📍 {item.location}</span>}
                {item.attendees_count > 0 && (
                  <span className="flex-shrink-0">
                    👥 {item.attendees_count}
                  </span>
                )}
                {item.status === "tentative" && (
                  <span className="flex-shrink-0 italic">tentative</span>
                )}
              </div>
            </div>
          </li>
        ))}
      </ul>
    </BriefShell>
  );
}
