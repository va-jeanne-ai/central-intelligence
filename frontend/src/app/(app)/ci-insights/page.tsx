"use client";

import { useState, useEffect, useCallback } from "react";
import { Header } from "@/components/layout/header";
import { apiClient } from "@/lib/api-client";
import { useAuth } from "@/hooks/use-auth";
import type { CIInsight, CIInsightsResponse } from "@/types";

// ─── Constants ────────────────────────────────────────────────────────────────

const INSIGHT_TYPES = [
  "All",
  "Pain",
  "Goal",
  "Objection",
  "False Belief",
  "Win",
  "Breakthrough",
  "Product Issue",
  "Feature Request",
] as const;

const SIGNAL_STRENGTHS = ["All", "Strong", "Moderate", "Weak"] as const;

const PAGE_LIMIT = 20;

// ─── Insight type pill color map ──────────────────────────────────────────────

function insightTypePillClasses(type: string): string {
  switch (type) {
    case "Pain":
      return "bg-rose-50 text-rose-700";
    case "Goal":
      return "bg-blue-50 text-blue-700";
    case "Objection":
      return "bg-orange-50 text-orange-700";
    case "Win":
      return "bg-green-50 text-green-700";
    case "Breakthrough":
      return "bg-purple-50 text-purple-700";
    case "False Belief":
      return "bg-yellow-50 text-yellow-700";
    default:
      return "bg-gray-100 text-gray-600";
  }
}

// ─── Signal strength indicator ────────────────────────────────────────────────

function StrengthDot({ strength }: { strength: CIInsight["signal_strength"] }) {
  const colorClass =
    strength === "Strong"
      ? "bg-green-500"
      : strength === "Moderate"
        ? "bg-yellow-400"
        : "bg-gray-400";

  return (
    <span className="inline-flex items-center gap-1.5">
      <span
        className={`inline-block w-2 h-2 rounded-full flex-shrink-0 ${colorClass}`}
        aria-hidden="true"
      />
      <span className="text-xs text-gray-600">{strength}</span>
    </span>
  );
}

// ─── Filter bar ───────────────────────────────────────────────────────────────

interface FilterBarProps {
  insightType: string;
  signalFamily: string;
  signalStrength: string;
  onInsightTypeChange: (v: string) => void;
  onSignalFamilyChange: (v: string) => void;
  onSignalStrengthChange: (v: string) => void;
}

function FilterBar({
  insightType,
  signalFamily,
  signalStrength,
  onInsightTypeChange,
  onSignalFamilyChange,
  onSignalStrengthChange,
}: FilterBarProps) {
  return (
    <div className="flex flex-wrap items-center gap-3 px-5 py-4 border-b border-gray-100">
      {/* Insight type dropdown */}
      <div className="flex flex-col gap-1">
        <label
          htmlFor="filter-insight-type"
          className="text-[10px] font-bold uppercase tracking-wider text-emerald-600"
        >
          Insight Type
        </label>
        <select
          id="filter-insight-type"
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

      {/* Signal family text search */}
      <div className="flex flex-col gap-1">
        <label
          htmlFor="filter-signal-family"
          className="text-[10px] font-bold uppercase tracking-wider text-emerald-600"
        >
          Signal Family
        </label>
        <input
          id="filter-signal-family"
          type="text"
          value={signalFamily}
          onChange={(e) => onSignalFamilyChange(e.target.value)}
          placeholder="Search signal family…"
          className="text-sm border border-gray-200 rounded-lg px-3 py-1.5 bg-white text-gray-700 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent w-48"
        />
      </div>

      {/* Signal strength dropdown */}
      <div className="flex flex-col gap-1">
        <label
          htmlFor="filter-signal-strength"
          className="text-[10px] font-bold uppercase tracking-wider text-emerald-600"
        >
          Signal Strength
        </label>
        <select
          id="filter-signal-strength"
          value={signalStrength}
          onChange={(e) => onSignalStrengthChange(e.target.value)}
          className="text-sm border border-gray-200 rounded-lg px-3 py-1.5 bg-white text-gray-700 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent"
        >
          {SIGNAL_STRENGTHS.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}

// ─── Skeleton row ─────────────────────────────────────────────────────────────

function SkeletonRow() {
  return (
    <div className="flex items-start gap-4 px-5 py-4 border-b border-gray-100 animate-pulse">
      <div className="flex-1 space-y-2">
        <div className="h-4 bg-gray-200 rounded w-2/5" />
        <div className="h-3 bg-gray-200 rounded w-3/4" />
      </div>
      <div className="h-5 bg-gray-200 rounded-full w-20" />
      <div className="h-5 bg-gray-200 rounded-full w-16" />
      <div className="h-4 bg-gray-200 rounded w-12" />
    </div>
  );
}

// ─── Insight row ──────────────────────────────────────────────────────────────

function InsightRow({ insight }: { insight: CIInsight }) {
  return (
    <div className="flex items-start gap-4 px-5 py-4 border-b border-gray-100 hover:bg-gray-50 transition-colors duration-100">
      {/* Left: signal + quote */}
      <div className="flex-1 min-w-0 space-y-1">
        <p className="text-sm font-semibold text-gray-900 truncate">
          {insight.signal}
        </p>
        <p className="text-xs italic text-gray-400 truncate">
          &ldquo;{insight.raw_quote}&rdquo;
        </p>
        <p className="text-[11px] text-gray-500">
          {insight.speaker_name}
          {" · "}
          <span className="font-medium text-gray-600">
            {insight.frequency_score}x
          </span>{" "}
          mentions
        </p>
      </div>

      {/* Insight type pill */}
      <span
        className={`flex-shrink-0 text-[11px] font-medium px-1.5 py-0.5 rounded-full ${insightTypePillClasses(insight.insight_type)}`}
      >
        {insight.insight_type}
      </span>

      {/* Signal family pill */}
      <span className="flex-shrink-0 text-[11px] font-medium px-1.5 py-0.5 rounded-full bg-gray-100 text-gray-600">
        {insight.signal_family}
      </span>

      {/* Signal strength */}
      <div className="flex-shrink-0">
        <StrengthDot strength={insight.signal_strength} />
      </div>
    </div>
  );
}

// ─── Empty state ──────────────────────────────────────────────────────────────

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-16 gap-3">
      <span className="text-4xl" aria-hidden="true">
        🔍
      </span>
      <p className="text-sm font-medium text-gray-500">No insights found.</p>
      <p className="text-xs text-gray-400">
        Try adjusting the filters above.
      </p>
    </div>
  );
}

// ─── Loading skeleton (5 rows) ────────────────────────────────────────────────

function LoadingSkeleton() {
  return (
    <div aria-label="Loading insights">
      {[1, 2, 3, 4, 5].map((i) => (
        <SkeletonRow key={i} />
      ))}
    </div>
  );
}

// ─── Pagination bar ───────────────────────────────────────────────────────────

interface PaginationBarProps {
  page: number;
  totalPages: number;
  hasPrevious: boolean;
  hasNext: boolean;
  onPrev: () => void;
  onNext: () => void;
}

function PaginationBar({
  page,
  totalPages,
  hasPrevious,
  hasNext,
  onPrev,
  onNext,
}: PaginationBarProps) {
  return (
    <div className="flex items-center justify-between px-5 py-4 border-t border-gray-100">
      <button
        type="button"
        onClick={onPrev}
        disabled={!hasPrevious}
        className="text-sm font-medium text-gray-600 hover:text-emerald-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
      >
        ← Previous
      </button>
      <span className="text-sm text-gray-500">
        Page {page} of {totalPages}
      </span>
      <button
        type="button"
        onClick={onNext}
        disabled={!hasNext}
        className="text-sm font-medium text-gray-600 hover:text-emerald-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
      >
        Next →
      </button>
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function CIInsightsPage() {
  const { isLoading: authLoading } = useAuth();

  const [isLoading, setIsLoading] = useState(true);
  const [insights, setInsights] = useState<CIInsight[]>([]);
  const [pagination, setPagination] = useState({
    page: 1,
    totalPages: 1,
    hasNextPage: false,
    hasPreviousPage: false,
    total: 0,
  });

  // Filter state
  const [insightType, setInsightType] = useState("All");
  const [signalFamily, setSignalFamily] = useState("");
  const [signalStrength, setSignalStrength] = useState("All");
  const [page, setPage] = useState(1);

  const fetchInsights = useCallback(async () => {
    setIsLoading(true);
    try {
      const params = new URLSearchParams();
      params.set("page", String(page));
      params.set("limit", String(PAGE_LIMIT));
      if (insightType !== "All") params.set("insight_type", insightType);
      if (signalFamily.trim()) params.set("signal_family", signalFamily.trim());
      if (signalStrength !== "All") params.set("signal_strength", signalStrength);

      const data = await apiClient.get<CIInsightsResponse>(
        `/ci/insights?${params.toString()}`,
        { silent: true }
      );
      setInsights(data.data);
      setPagination({
        page: data.pagination.page,
        totalPages: data.pagination.totalPages,
        hasNextPage: data.pagination.hasNextPage,
        hasPreviousPage: data.pagination.hasPreviousPage,
        total: data.pagination.total,
      });
    } catch {
      setInsights([]);
    } finally {
      setIsLoading(false);
    }
  }, [page, insightType, signalFamily, signalStrength]);

  useEffect(() => {
    if (authLoading) return;
    let cancelled = false;

    void (async () => {
      setIsLoading(true);
      try {
        const params = new URLSearchParams();
        params.set("page", String(page));
        params.set("limit", String(PAGE_LIMIT));
        if (insightType !== "All") params.set("insight_type", insightType);
        if (signalFamily.trim()) params.set("signal_family", signalFamily.trim());
        if (signalStrength !== "All") params.set("signal_strength", signalStrength);

        const data = await apiClient.get<CIInsightsResponse>(
          `/ci/insights?${params.toString()}`,
          { silent: true }
        );
        if (!cancelled) {
          setInsights(data.data);
          setPagination({
            page: data.pagination.page,
            totalPages: data.pagination.totalPages,
            hasNextPage: data.pagination.hasNextPage,
            hasPreviousPage: data.pagination.hasPreviousPage,
            total: data.pagination.total,
          });
        }
      } catch {
        if (!cancelled) setInsights([]);
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [authLoading, page, insightType, signalFamily, signalStrength]);

  // Reset to page 1 whenever filters change
  function handleInsightTypeChange(v: string) {
    setInsightType(v);
    setPage(1);
  }
  function handleSignalFamilyChange(v: string) {
    setSignalFamily(v);
    setPage(1);
  }
  function handleSignalStrengthChange(v: string) {
    setSignalStrength(v);
    setPage(1);
  }

  // Suppress unused warning — fetchInsights used as fallback ref
  void fetchInsights;

  return (
    <>
      <Header title="CI Insights" />

      <main className="flex-1 overflow-y-auto p-7 space-y-6">
        {/* Page heading */}
        <div>
          <h1 className="text-xl font-bold text-gray-900">CI Insights</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Competitive intelligence signals extracted from your sales and coaching calls.
          </p>
        </div>

        {/* Insights list card */}
        <section aria-label="CI Insights list">
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
            {/* Card header */}
            <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
              <h2 className="text-sm font-bold text-gray-900">Insights</h2>
              {!isLoading && (
                <span className="text-xs text-gray-400">
                  {pagination.total} total
                </span>
              )}
            </div>

            {/* Filter bar */}
            <FilterBar
              insightType={insightType}
              signalFamily={signalFamily}
              signalStrength={signalStrength}
              onInsightTypeChange={handleInsightTypeChange}
              onSignalFamilyChange={handleSignalFamilyChange}
              onSignalStrengthChange={handleSignalStrengthChange}
            />

            {/* Content */}
            {isLoading ? (
              <LoadingSkeleton />
            ) : insights.length === 0 ? (
              <EmptyState />
            ) : (
              <>
                <div>
                  {insights.map((insight) => (
                    <InsightRow key={insight.insight_id} insight={insight} />
                  ))}
                </div>
                <PaginationBar
                  page={pagination.page}
                  totalPages={pagination.totalPages}
                  hasPrevious={pagination.hasPreviousPage}
                  hasNext={pagination.hasNextPage}
                  onPrev={() => setPage((p) => Math.max(1, p - 1))}
                  onNext={() => setPage((p) => p + 1)}
                />
              </>
            )}
          </div>
        </section>
      </main>
    </>
  );
}
