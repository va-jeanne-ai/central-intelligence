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

// Shared shell styling so the loaded / empty / skeleton states match the
// mockup's .ci-widget (dark amber→gray gradient, gold-tinted border).
const SHELL_CLASS =
  "rounded-xl p-5 flex flex-col gap-3.5 text-white border border-amber-500/25 " +
  "bg-gradient-to-br from-[#78350F] via-[#92400E] to-[#1F2937]";

// Header block (crown in a gold ring + gold title) reused across states.
function WidgetHeader() {
  return (
    <div className="flex items-center gap-2.5">
      <span
        className="flex h-9 w-9 items-center justify-center rounded-full text-xl bg-amber-500/20 border-[1.5px] border-amber-500/40"
        role="img"
        aria-label="Crown"
      >
        👑
      </span>
      <div>
        <h2 className="text-sm font-bold text-amber-300">
          Central Intelligence Recommendations
        </h2>
        <p className="text-[11px] text-white/60 mt-px">
          Focus areas for this week &mdash; AI-generated
        </p>
      </div>
    </div>
  );
}

function WidgetSkeleton() {
  return (
    <aside className={SHELL_CLASS} aria-label="Loading Central Intelligence Recommendations">
      <WidgetHeader />
      <div className="flex flex-col gap-2">
        {[1, 2, 3, 4].map((i) => (
          <div
            key={i}
            className="flex items-start gap-2 rounded-lg bg-white/[0.06] border border-white/10 px-3 py-2.5"
          >
            <div className="h-3.5 w-3.5 rounded bg-white/15 animate-pulse flex-shrink-0 mt-0.5" />
            <div className="flex-1 space-y-1.5 pt-0.5">
              <div className="h-3 w-full bg-white/10 rounded animate-pulse" />
              <div className="h-3 w-3/4 bg-white/10 rounded animate-pulse" />
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
      <aside className={SHELL_CLASS} aria-label="Central Intelligence Recommendations">
        <WidgetHeader />
        <p className="text-xs text-white/60">No recommendations available right now.</p>
      </aside>
    );
  }

  return (
    <aside className={SHELL_CLASS} aria-label="Central Intelligence Recommendations">
      <WidgetHeader />

      {/* Recommendation list — glass cards, icon-prefixed, gold <strong> */}
      <ul className="flex flex-col gap-2" role="list">
        {recommendations.map((rec) => (
          <li
            key={rec.id}
            className="flex items-start gap-2 rounded-lg bg-white/[0.06] border border-white/10 px-3 py-2.5"
          >
            <span
              className="text-sm leading-none flex-shrink-0 mt-px"
              role="img"
              aria-hidden="true"
            >
              {rec.icon}
            </span>
            {/* [&_strong]:text-amber-300 styles the <strong> the API emits */}
            <p
              className="text-[12.5px] leading-[1.45] text-white/[0.88] [&_strong]:font-bold [&_strong]:text-amber-300"
              dangerouslySetInnerHTML={{ __html: rec.text }}
            />
          </li>
        ))}
      </ul>
    </aside>
  );
}
