"use client";

import { useState, useEffect } from "react";
import { apiClient } from "@/lib/api-client";
import { useAuth } from "@/hooks/use-auth";

// ─── Types ─────────────────────────────────────────────────────────────────────

interface WeeklyFocusItem {
  title: string;
  detail: string;
}

interface WeeklyFocusResponse {
  focus: WeeklyFocusItem[];
  summary: string;
  generated_at: string;
  cached: boolean;
}

// ─── Shell ─────────────────────────────────────────────────────────────────────
// Shared chrome so the loading, empty, and populated states stay visually
// identical (same indigo CI accent as the recommendations widget).

function FocusShell({ children }: { children: React.ReactNode }) {
  return (
    <aside
      className="bg-indigo-50 border border-indigo-200 rounded-xl p-5 flex flex-col gap-4 shadow-sm"
      aria-label="This Week's Focus"
    >
      <div className="flex flex-col gap-0.5">
        <div className="flex items-center gap-2">
          <span className="text-lg leading-none" role="img" aria-label="Crown">
            👑
          </span>
          <h2 className="text-sm font-bold text-indigo-900">This Week&apos;s Focus</h2>
        </div>
        <p className="text-xs text-indigo-700 ml-7">
          Cross-department priorities, synthesized for you
        </p>
      </div>
      <hr className="border-indigo-200" />
      {children}
    </aside>
  );
}

// ─── Skeleton ──────────────────────────────────────────────────────────────────

function FocusSkeleton() {
  return (
    <FocusShell>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="flex items-start gap-3">
            <div className="w-5 h-5 rounded-full bg-indigo-200/60 animate-pulse flex-shrink-0" />
            <div className="flex-1 space-y-1.5 pt-0.5">
              <div className="h-3 w-2/3 bg-indigo-200/60 rounded animate-pulse" />
              <div className="h-3 w-full bg-indigo-200/40 rounded animate-pulse" />
            </div>
          </div>
        ))}
      </div>
    </FocusShell>
  );
}

// ─── Component ─────────────────────────────────────────────────────────────────

export function WeeklyFocus() {
  const { isLoading: authLoading } = useAuth();
  const [focus, setFocus] = useState<WeeklyFocusItem[]>([]);
  const [summary, setSummary] = useState("");
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (authLoading) return;

    let cancelled = false;

    async function fetchFocus(): Promise<void> {
      try {
        const data = await apiClient.get<WeeklyFocusResponse>(
          "/dashboard/weekly-focus",
          { silent: true },
        );
        if (!cancelled) {
          setFocus(data.focus);
          setSummary(data.summary);
        }
      } catch {
        // On error the panel falls through to its empty state — not critical.
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    }

    void fetchFocus();

    return () => {
      cancelled = true;
    };
  }, [authLoading]);

  if (isLoading) return <FocusSkeleton />;

  if (focus.length === 0) {
    return (
      <FocusShell>
        <p className="text-xs text-indigo-700">
          No focus priorities available right now.
        </p>
      </FocusShell>
    );
  }

  return (
    <FocusShell>
      {summary && (
        <p className="text-sm font-semibold text-indigo-900 leading-snug -mt-1">
          {summary}
        </p>
      )}
      <ol className="grid grid-cols-1 md:grid-cols-2 gap-3" role="list">
        {focus.map((item, index) => (
          <li key={`${item.title}-${index}`} className="flex items-start gap-3">
            <span
              className="flex-shrink-0 flex items-center justify-center w-5 h-5 rounded-full bg-indigo-200 text-indigo-800 text-[10px] font-bold mt-0.5"
              aria-hidden="true"
            >
              {index + 1}
            </span>
            <div className="min-w-0">
              <p className="text-sm font-semibold text-indigo-900 leading-snug">
                {item.title}
              </p>
              {item.detail && (
                <p className="text-xs text-indigo-700 leading-snug mt-0.5">
                  {item.detail}
                </p>
              )}
            </div>
          </li>
        ))}
      </ol>
    </FocusShell>
  );
}
