"use client";

import { useState, useEffect } from "react";
import { apiClient } from "@/lib/api-client";
import { useAuth } from "@/hooks/use-auth";

// ─── Types ─────────────────────────────────────────────────────────────────────

interface RecommendationItem {
  id: string;
  icon: string;
  text: string;
}

interface RecommendationsResponse {
  recommendations: RecommendationItem[];
  generated_at: string;
  cached: boolean;
}

// ─── Skeleton ──────────────────────────────────────────────────────────────────

function WidgetSkeleton() {
  return (
    <aside
      className="bg-indigo-50 border border-indigo-200 rounded-xl p-5 flex flex-col gap-4 shadow-sm"
      aria-label="Loading Central Intelligence Recommendations"
    >
      <div className="flex flex-col gap-0.5">
        <div className="flex items-center gap-2">
          <span className="text-lg leading-none">👑</span>
          <div className="h-4 w-52 bg-indigo-200/60 rounded animate-pulse" />
        </div>
        <div className="h-3 w-44 bg-indigo-200/40 rounded animate-pulse ml-7 mt-1" />
      </div>
      <hr className="border-indigo-200" />
      <div className="flex flex-col gap-3">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="flex items-start gap-3">
            <div className="w-5 h-5 rounded-full bg-indigo-200/60 animate-pulse flex-shrink-0" />
            <div className="flex-1 space-y-1.5 pt-0.5">
              <div className="h-3 w-full bg-indigo-200/40 rounded animate-pulse" />
              <div className="h-3 w-3/4 bg-indigo-200/40 rounded animate-pulse" />
            </div>
          </div>
        ))}
      </div>
    </aside>
  );
}

// ─── Component ─────────────────────────────────────────────────────────────────

export function CIWidget() {
  const { isLoading: authLoading } = useAuth();
  const [recommendations, setRecommendations] = useState<RecommendationItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (authLoading) return;

    let cancelled = false;

    async function fetchRecommendations(): Promise<void> {
      try {
        const data = await apiClient.get<RecommendationsResponse>(
          "/dashboard/recommendations",
          { silent: true },
        );
        if (!cancelled) {
          setRecommendations(data.recommendations);
        }
      } catch {
        // On error, widget stays empty — not critical
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    }

    void fetchRecommendations();

    return () => {
      cancelled = true;
    };
  }, [authLoading]);

  if (isLoading) return <WidgetSkeleton />;

  if (recommendations.length === 0) {
    return (
      <aside
        className="bg-indigo-50 border border-indigo-200 rounded-xl p-5 flex flex-col gap-4 shadow-sm"
        aria-label="Central Intelligence Recommendations"
      >
        <div className="flex flex-col gap-0.5">
          <div className="flex items-center gap-2">
            <span className="text-lg leading-none" role="img" aria-label="Crown">
              👑
            </span>
            <h2 className="text-sm font-bold text-indigo-900">
              Central Intelligence Recommendations
            </h2>
          </div>
          <p className="text-xs text-indigo-700 ml-7">
            No recommendations available right now.
          </p>
        </div>
      </aside>
    );
  }

  return (
    <aside
      className="bg-indigo-50 border border-indigo-200 rounded-xl p-5 flex flex-col gap-4 shadow-sm"
      aria-label="Central Intelligence Recommendations"
    >
      {/* Header */}
      <div className="flex flex-col gap-0.5">
        <div className="flex items-center gap-2">
          <span className="text-lg leading-none" role="img" aria-label="Crown">
            👑
          </span>
          <h2 className="text-sm font-bold text-indigo-900">
            Central Intelligence Recommendations
          </h2>
        </div>
        <p className="text-xs text-indigo-700 ml-7">
          Focus areas for this week &mdash; AI-generated
        </p>
      </div>

      {/* Divider */}
      <hr className="border-indigo-200" />

      {/* Recommendation list */}
      <ul className="flex flex-col gap-3" role="list">
        {recommendations.map((rec, index) => (
          <li
            key={rec.id}
            className="flex items-start gap-3"
          >
            {/* Index badge */}
            <span
              className="flex-shrink-0 flex items-center justify-center w-5 h-5 rounded-full bg-indigo-200 text-indigo-800 text-[10px] font-bold mt-0.5"
              aria-hidden="true"
            >
              {index + 1}
            </span>

            {/* Icon + text */}
            <div className="flex items-start gap-2 min-w-0">
              <span className="text-base leading-none flex-shrink-0 mt-0.5" role="img" aria-hidden="true">
                {rec.icon}
              </span>
              <p
                className="text-sm text-indigo-900 leading-snug"
                dangerouslySetInnerHTML={{ __html: rec.text }}
              />
            </div>
          </li>
        ))}
      </ul>
    </aside>
  );
}
