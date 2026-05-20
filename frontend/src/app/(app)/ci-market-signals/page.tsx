"use client";

import { useState, useEffect } from "react";
import { Header } from "@/components/layout/header";
import { apiClient } from "@/lib/api-client";
import { useAuth } from "@/hooks/use-auth";
import type { CIMarketSignal, CIMarketSignalsResponse } from "@/types";

// ─── Constants ────────────────────────────────────────────────────────────────

const INSIGHT_TYPES = ["All", "Pain", "Objection", "Goal"] as const;

type SortBy = "total_mentions" | "last_30_days" | "last_7_days";

const SORT_OPTIONS: { label: string; value: SortBy }[] = [
  { label: "Total Mentions", value: "total_mentions" },
  { label: "Last 30 Days", value: "last_30_days" },
  { label: "Last 7 Days", value: "last_7_days" },
];

// ─── Insight type pill color map ──────────────────────────────────────────────

function insightTypePillClasses(type: string): string {
  switch (type) {
    case "Pain":
      return "bg-rose-50 text-rose-700";
    case "Objection":
      return "bg-orange-50 text-orange-700";
    case "Goal":
      return "bg-blue-50 text-blue-700";
    default:
      return "bg-gray-100 text-gray-600";
  }
}

// ─── Trend mini-bar ───────────────────────────────────────────────────────────

interface TrendBarProps {
  signal: CIMarketSignal;
}

function TrendBar({ signal }: TrendBarProps) {
  const max = signal.total_mentions || 1;
  const bars: { label: string; value: number; colorClass: string }[] = [
    {
      label: "7d",
      value: signal.last_7_days,
      colorClass: "bg-emerald-500",
    },
    {
      label: "30d",
      value: signal.last_30_days,
      colorClass: "bg-emerald-300",
    },
    {
      label: "Total",
      value: signal.total_mentions,
      colorClass: "bg-emerald-100",
    },
  ];

  return (
    <div className="space-y-1.5" aria-label="Mention trend">
      {bars.map((bar) => {
        const pct = Math.round((bar.value / max) * 100);
        return (
          <div key={bar.label} className="flex items-center gap-2">
            <span className="text-[10px] font-medium text-gray-400 w-8 flex-shrink-0">
              {bar.label}
            </span>
            <div className="flex-1 bg-gray-100 rounded-full h-1.5 overflow-hidden">
              <div
                className={`${bar.colorClass} h-full rounded-full transition-all duration-300`}
                style={{ width: `${pct}%` }}
                role="presentation"
              />
            </div>
            <span className="text-[10px] tabular-nums text-gray-500 w-6 text-right flex-shrink-0">
              {bar.value}
            </span>
          </div>
        );
      })}
    </div>
  );
}

// ─── Signal card ──────────────────────────────────────────────────────────────

function SignalCard({ signal }: { signal: CIMarketSignal }) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5 flex flex-col gap-4">
      {/* Card header */}
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <span className="text-base leading-none flex-shrink-0" aria-hidden="true">
            📶
          </span>
          <span className="text-[10px] font-bold uppercase tracking-wider text-emerald-600 truncate">
            {signal.signal_family}
          </span>
        </div>
        <span
          className={`flex-shrink-0 text-[11px] font-medium px-1.5 py-0.5 rounded-full ${insightTypePillClasses(signal.insight_type)}`}
        >
          {signal.insight_type}
        </span>
      </div>

      {/* Signal text */}
      <p className="text-sm font-semibold text-gray-900 leading-snug">
        {signal.signal}
      </p>

      {/* Trend bars */}
      <TrendBar signal={signal} />

      {/* Example quote */}
      {signal.example_quote && (
        <p className="text-xs italic text-gray-400 leading-relaxed border-t border-gray-100 pt-3">
          &ldquo;{signal.example_quote}&rdquo;
        </p>
      )}

      {/* Best marketing angle */}
      {signal.best_marketing_angle && (
        <p className="text-xs font-medium text-emerald-700 bg-emerald-50 rounded-lg px-3 py-2 leading-relaxed">
          {signal.best_marketing_angle}
        </p>
      )}
    </div>
  );
}

// ─── Skeleton card ────────────────────────────────────────────────────────────

function SkeletonCard() {
  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5 flex flex-col gap-4 animate-pulse">
      <div className="flex items-center justify-between">
        <div className="h-3 bg-gray-200 rounded w-1/3" />
        <div className="h-5 bg-gray-200 rounded-full w-16" />
      </div>
      <div className="space-y-2">
        <div className="h-4 bg-gray-200 rounded w-full" />
        <div className="h-4 bg-gray-200 rounded w-4/5" />
      </div>
      <div className="space-y-2">
        <div className="h-2 bg-gray-200 rounded w-full" />
        <div className="h-2 bg-gray-200 rounded w-full" />
        <div className="h-2 bg-gray-200 rounded w-full" />
      </div>
      <div className="h-10 bg-gray-200 rounded-lg w-full" />
    </div>
  );
}

// ─── Filter bar ───────────────────────────────────────────────────────────────

interface FilterBarProps {
  insightType: string;
  sortBy: SortBy;
  onInsightTypeChange: (v: string) => void;
  onSortByChange: (v: SortBy) => void;
}

function FilterBar({
  insightType,
  sortBy,
  onInsightTypeChange,
  onSortByChange,
}: FilterBarProps) {
  return (
    <div className="flex flex-wrap items-center gap-3 px-5 py-4 border-b border-gray-100">
      {/* Insight type dropdown */}
      <div className="flex flex-col gap-1">
        <label
          htmlFor="ms-filter-insight-type"
          className="text-[10px] font-bold uppercase tracking-wider text-emerald-600"
        >
          Insight Type
        </label>
        <select
          id="ms-filter-insight-type"
          value={insightType}
          onChange={(e) => onInsightTypeChange(e.target.value)}
          className="text-sm border border-gray-200 rounded-lg px-3 py-1.5 bg-white text-gray-700 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent"
        >
          {INSIGHT_TYPES.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
      </div>

      {/* Sort by dropdown */}
      <div className="flex flex-col gap-1">
        <label
          htmlFor="ms-sort-by"
          className="text-[10px] font-bold uppercase tracking-wider text-emerald-600"
        >
          Sort By
        </label>
        <select
          id="ms-sort-by"
          value={sortBy}
          onChange={(e) => onSortByChange(e.target.value as SortBy)}
          className="text-sm border border-gray-200 rounded-lg px-3 py-1.5 bg-white text-gray-700 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent"
        >
          {SORT_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}

// ─── Empty state ──────────────────────────────────────────────────────────────

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-16 gap-3">
      <span className="text-4xl" aria-hidden="true">
        📶
      </span>
      <p className="text-sm font-medium text-gray-500">
        No market signals found.
      </p>
      <p className="text-xs text-gray-400">
        Try adjusting the filters above or uploading more call transcripts.
      </p>
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function CIMarketSignalsPage() {
  const { isLoading: authLoading } = useAuth();

  const [isLoading, setIsLoading] = useState(true);
  const [signals, setSignals] = useState<CIMarketSignal[]>([]);

  const [insightType, setInsightType] = useState("All");
  const [sortBy, setSortBy] = useState<SortBy>("total_mentions");

  useEffect(() => {
    if (authLoading) return;
    let cancelled = false;

    void (async () => {
      setIsLoading(true);
      try {
        const params = new URLSearchParams();
        if (insightType !== "All") params.set("insight_type", insightType);
        params.set("sort_by", sortBy);

        const data = await apiClient.get<CIMarketSignalsResponse>(
          `/ci/market-signals?${params.toString()}`,
          { silent: true }
        );
        if (!cancelled) {
          setSignals(data.data);
        }
      } catch {
        if (!cancelled) setSignals([]);
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [authLoading, insightType, sortBy]);

  return (
    <>
      <Header title="Market Signals" />

      <main className="flex-1 overflow-y-auto p-7 space-y-6">
        {/* Page heading */}
        <div>
          <h1 className="text-xl font-bold text-gray-900">Market Signals</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Aggregated signal trends surfaced across all analyzed calls.
          </p>
        </div>

        {/* Signals card */}
        <section aria-label="Market signals">
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
            {/* Card header */}
            <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
              <h2 className="text-sm font-bold text-gray-900">
                Top Signals
              </h2>
              {!isLoading && (
                <span className="text-xs text-gray-400">
                  {signals.length} signal{signals.length !== 1 ? "s" : ""}
                </span>
              )}
            </div>

            {/* Filter bar */}
            <FilterBar
              insightType={insightType}
              sortBy={sortBy}
              onInsightTypeChange={setInsightType}
              onSortByChange={setSortBy}
            />

            {/* Content */}
            <div className="p-5">
              {isLoading ? (
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                  {[1, 2, 3, 4, 5, 6].map((i) => (
                    <SkeletonCard key={i} />
                  ))}
                </div>
              ) : signals.length === 0 ? (
                <EmptyState />
              ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                  {signals.map((signal, index) => (
                    <SignalCard
                      key={`${signal.signal_family}-${signal.signal}-${index}`}
                      signal={signal}
                    />
                  ))}
                </div>
              )}
            </div>
          </div>
        </section>
      </main>
    </>
  );
}
