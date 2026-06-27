"use client";

import { useState, useEffect } from "react";
import { Header } from "@/components/layout/header";
import { apiClient } from "@/lib/api-client";
import { useAuth } from "@/hooks/use-auth";
import { usePagination } from "@/hooks/use-pagination";
import { Pagination } from "@/components/ui";
import type { CIInsight, CIInsightsResponse, CIInsightFacets } from "@/types";

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
  insightTypeOptions: string[];
  signalFamilyOptions: string[];
  signalStrengthOptions: string[];
  onInsightTypeChange: (v: string) => void;
  onSignalFamilyChange: (v: string) => void;
  onSignalStrengthChange: (v: string) => void;
}

/** A labelled facet dropdown whose options are derived from the data.
 * The "All" sentinel clears the filter. */
function FacetSelect({
  id,
  label,
  value,
  options,
  onChange,
}: {
  id: string;
  label: string;
  value: string;
  options: string[];
  onChange: (v: string) => void;
}) {
  return (
    <div className="flex flex-col gap-1">
      <label
        htmlFor={id}
        className="text-[10px] font-bold uppercase tracking-wider text-emerald-600"
      >
        {label}
      </label>
      <select
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="text-sm border border-gray-200 rounded-lg px-3 py-1.5 bg-white text-gray-700 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent"
      >
        <option value="All">All</option>
        {options.map((o) => (
          <option key={o} value={o}>
            {o}
          </option>
        ))}
      </select>
    </div>
  );
}

function FilterBar({
  insightType,
  signalFamily,
  signalStrength,
  insightTypeOptions,
  signalFamilyOptions,
  signalStrengthOptions,
  onInsightTypeChange,
  onSignalFamilyChange,
  onSignalStrengthChange,
}: FilterBarProps) {
  return (
    <div className="flex flex-wrap items-center gap-3 px-5 py-4 border-b border-gray-100">
      <FacetSelect
        id="filter-insight-type"
        label="Insight Type"
        value={insightType}
        options={insightTypeOptions}
        onChange={onInsightTypeChange}
      />
      <FacetSelect
        id="filter-signal-family"
        label="Signal Family"
        value={signalFamily}
        options={signalFamilyOptions}
        onChange={onSignalFamilyChange}
      />
      <FacetSelect
        id="filter-signal-strength"
        label="Signal Strength"
        value={signalStrength}
        options={signalStrengthOptions}
        onChange={onSignalStrengthChange}
      />
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

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function CIInsightsPage() {
  const { isLoading: authLoading } = useAuth();

  const [isLoading, setIsLoading] = useState(true);
  const [insights, setInsights] = useState<CIInsight[]>([]);
  const [total, setTotal] = useState(0);

  // Pagination — page/pageSize persisted per surface via the shared hook.
  const { page, pageSize, setPage, setPageSize } = usePagination("insights");

  // Filter state — "All" is the cleared sentinel for every facet.
  const [insightType, setInsightType] = useState("All");
  const [signalFamily, setSignalFamily] = useState("All");
  const [signalStrength, setSignalStrength] = useState("All");

  // Facet options, derived from the data so they can't drift from it.
  const [facets, setFacets] = useState<CIInsightFacets>({
    insight_type: [],
    signal_family: [],
    signal_strength: [],
  });

  // Fetch the available filter values once auth is ready. Silent — an
  // empty facet set just leaves the dropdowns with only "All".
  useEffect(() => {
    if (authLoading) return;
    let cancelled = false;

    void (async () => {
      try {
        const data = await apiClient.get<CIInsightFacets>(
          "/ci/insights/facets",
          { silent: true }
        );
        if (!cancelled) setFacets(data);
      } catch {
        /* leave facets empty — dropdowns still show "All" */
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [authLoading]);

  useEffect(() => {
    if (authLoading) return;
    let cancelled = false;

    void (async () => {
      setIsLoading(true);
      try {
        const params = new URLSearchParams();
        params.set("page", String(page));
        params.set("limit", String(pageSize));
        if (insightType !== "All") params.set("insight_type", insightType);
        if (signalFamily !== "All") params.set("signal_family", signalFamily);
        if (signalStrength !== "All") params.set("signal_strength", signalStrength);

        const data = await apiClient.get<CIInsightsResponse>(
          `/ci/insights?${params.toString()}`,
          { silent: true }
        );
        if (!cancelled) {
          setInsights(data.data);
          setTotal(data.pagination.total);
        }
      } catch {
        if (!cancelled) {
          setInsights([]);
          setTotal(0);
        }
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [authLoading, page, pageSize, insightType, signalFamily, signalStrength]);

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
                <span className="text-xs text-gray-400">{total} total</span>
              )}
            </div>

            {/* Filter bar */}
            <FilterBar
              insightType={insightType}
              signalFamily={signalFamily}
              signalStrength={signalStrength}
              insightTypeOptions={facets.insight_type}
              signalFamilyOptions={facets.signal_family}
              signalStrengthOptions={facets.signal_strength}
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
                <Pagination
                  page={page}
                  total={total}
                  pageSize={pageSize}
                  onPageChange={setPage}
                  onPageSizeChange={setPageSize}
                />
              </>
            )}
          </div>
        </section>
      </main>
    </>
  );
}
