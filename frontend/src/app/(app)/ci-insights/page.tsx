"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { Header } from "@/components/layout/header";
import { apiClient } from "@/lib/api-client";
import { useAuth } from "@/hooks/use-auth";
import { usePagination } from "@/hooks/use-pagination";
import { Pagination } from "@/components/ui";
import { InsightsCharts } from "./insights-charts";
import type {
  CIInsight,
  CIInsightsResponse,
  CIInsightFacets,
  CIInsightDistribution,
} from "@/types";

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
      : strength === "Moderate" || strength === "Medium"
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

// ─── Source attribution ───────────────────────────────────────────────────────

/** Which call-detail surface a call_type resolves to. Coaching calls get
 * their own detail page; everything else (Outbound/Discovery/Sales) is a
 * sales call. Falls back to sales-calls when call_type is unknown/missing. */
function callDetailHref(callId: string, callType: string | null): string {
  const base = callType === "Coaching" ? "/coaching-calls" : "/sales-calls";
  return `${base}/${callId}`;
}

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

/** "Call — Discovery · Vivian Malta · Jun 15, 2026" — links to the call
 * detail page (and implicitly the lead, via that page) when a call_id is
 * present. Every insight has one today; the dash-fallback covers the
 * hypothetical future where a source has no call. */
function SourceAttribution({ insight }: { insight: CIInsight }) {
  if (!insight.call_id) {
    return <span className="text-[11px] text-gray-400">Unknown source</span>;
  }
  const parts = [
    insight.call_type ?? "Call",
    insight.lead_name,
    formatDate(insight.call_date),
  ].filter(Boolean);
  return (
    <Link
      href={callDetailHref(insight.call_id, insight.call_type)}
      className="text-[11px] text-gray-500 hover:text-emerald-700 hover:underline truncate block"
      title={`Open ${insight.call_id}`}
    >
      📞 {parts.join(" · ")}
    </Link>
  );
}

// ─── Filter bar ───────────────────────────────────────────────────────────────

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

interface FilterBarProps {
  search: string;
  onSearchChange: (v: string) => void;
  insightType: string;
  signalFamily: string;
  signalStrength: string;
  painLayer: string;
  tag: string;
  onTagChange: (v: string) => void;
  createdFrom: string;
  createdTo: string;
  insightTypeOptions: string[];
  signalFamilyOptions: string[];
  signalStrengthOptions: string[];
  painLayerOptions: string[];
  onInsightTypeChange: (v: string) => void;
  onSignalFamilyChange: (v: string) => void;
  onSignalStrengthChange: (v: string) => void;
  onPainLayerChange: (v: string) => void;
  onCreatedFromChange: (v: string) => void;
  onCreatedToChange: (v: string) => void;
  onClear: () => void;
}

function FilterBar({
  search,
  onSearchChange,
  insightType,
  signalFamily,
  signalStrength,
  painLayer,
  tag,
  onTagChange,
  createdFrom,
  createdTo,
  insightTypeOptions,
  signalFamilyOptions,
  signalStrengthOptions,
  painLayerOptions,
  onInsightTypeChange,
  onSignalFamilyChange,
  onSignalStrengthChange,
  onPainLayerChange,
  onCreatedFromChange,
  onCreatedToChange,
  onClear,
}: FilterBarProps) {
  const hasFilters =
    search !== "" ||
    insightType !== "All" ||
    signalFamily !== "All" ||
    signalStrength !== "All" ||
    painLayer !== "All" ||
    tag !== "" ||
    createdFrom !== "" ||
    createdTo !== "";

  return (
    <div className="flex flex-wrap items-end gap-3 px-5 py-4 border-b border-gray-100">
      {/* Search */}
      <div className="flex flex-col gap-1">
        <label
          htmlFor="filter-search"
          className="text-[10px] font-bold uppercase tracking-wider text-emerald-600"
        >
          Search
        </label>
        <input
          id="filter-search"
          type="text"
          placeholder="Signal or quote..."
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
          className="text-sm border border-gray-200 rounded-lg px-3 py-1.5 bg-white text-gray-700 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent w-44"
        />
      </div>

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
      <FacetSelect
        id="filter-pain-layer"
        label="Pain Layer"
        value={painLayer}
        options={painLayerOptions}
        onChange={onPainLayerChange}
      />

      {/* Tag — free text, not a dropdown (2,774 distinct tags is free-text
          cardinality, not a picker) */}
      <div className="flex flex-col gap-1">
        <label
          htmlFor="filter-tag"
          className="text-[10px] font-bold uppercase tracking-wider text-emerald-600"
        >
          Tag
        </label>
        <input
          id="filter-tag"
          type="text"
          placeholder="e.g. burnout"
          value={tag}
          onChange={(e) => onTagChange(e.target.value)}
          className="text-sm border border-gray-200 rounded-lg px-3 py-1.5 bg-white text-gray-700 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent w-32"
        />
      </div>

      {/* Created-date range */}
      <div className="flex flex-col gap-1">
        <label className="text-[10px] font-bold uppercase tracking-wider text-emerald-600">
          Generated
        </label>
        <div className="flex items-center gap-1.5 text-gray-500">
          <input
            type="date"
            aria-label="Generated on or after"
            value={createdFrom}
            max={createdTo || undefined}
            onChange={(e) => onCreatedFromChange(e.target.value)}
            className="px-2 py-1.5 text-sm border border-gray-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent text-gray-600"
          />
          <span className="text-gray-300">–</span>
          <input
            type="date"
            aria-label="Generated on or before"
            value={createdTo}
            min={createdFrom || undefined}
            onChange={(e) => onCreatedToChange(e.target.value)}
            className="px-2 py-1.5 text-sm border border-gray-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent text-gray-600"
          />
        </div>
      </div>

      {hasFilters && (
        <button
          type="button"
          onClick={onClear}
          className="text-[12px] font-medium text-gray-400 hover:text-gray-600 pb-1.5"
        >
          Clear filters
        </button>
      )}
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
        <div className="h-3 bg-gray-200 rounded w-1/3" />
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
      {/* Left: signal + quote + source attribution */}
      <div className="flex-1 min-w-0 space-y-1">
        <p className="text-sm font-semibold text-gray-900 truncate">
          {insight.signal}
        </p>
        <p className="text-xs italic text-gray-400 truncate">
          &ldquo;{insight.raw_quote}&rdquo;
        </p>
        <div className="flex items-center gap-2 text-[11px] text-gray-500">
          <span>
            {insight.speaker_name}
            {" · "}
            <span className="font-medium text-gray-600">
              {insight.frequency_score}x
            </span>{" "}
            mentions
          </span>
        </div>
        <SourceAttribution insight={insight} />
        {insight.tags.length > 0 && (
          <div className="flex flex-wrap gap-1 pt-0.5">
            {insight.tags.slice(0, 4).map((t) => (
              <span
                key={t}
                className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-50 text-emerald-700"
              >
                {t}
              </span>
            ))}
          </div>
        )}
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

const DEFAULT_FACETS: CIInsightFacets = {
  insight_type: [],
  signal_family: [],
  signal_strength: [],
  pain_layer: [],
};

export default function CIInsightsPage() {
  const { isLoading: authLoading } = useAuth();

  const [isLoading, setIsLoading] = useState(true);
  const [insights, setInsights] = useState<CIInsight[]>([]);
  const [total, setTotal] = useState(0);

  // Aggregated distributions for the charts. Filter-aware but page-independent.
  const [summary, setSummary] = useState<CIInsightDistribution | null>(null);
  const [summaryLoading, setSummaryLoading] = useState(true);

  // Pagination — page/pageSize persisted per surface via the shared hook.
  const { page, pageSize, setPage, setPageSize } = usePagination("insights");

  // Filter state — "All" is the cleared sentinel for facets; "" for text/date.
  const [search, setSearch] = useState("");
  const [insightType, setInsightType] = useState("All");
  const [signalFamily, setSignalFamily] = useState("All");
  const [signalStrength, setSignalStrength] = useState("All");
  const [painLayer, setPainLayer] = useState("All");
  const [tag, setTag] = useState("");
  const [createdFrom, setCreatedFrom] = useState("");
  const [createdTo, setCreatedTo] = useState("");

  // Facet options, derived from the data so they can't drift from it.
  const [facets, setFacets] = useState<CIInsightFacets>(DEFAULT_FACETS);

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

  // Build the shared query params once per filter change; reused for the
  // list fetch and (minus pagination) the summary fetch.
  function buildFilterParams(): URLSearchParams {
    const params = new URLSearchParams();
    if (search.trim()) params.set("search", search.trim());
    if (insightType !== "All") params.set("insight_type", insightType);
    if (signalFamily !== "All") params.set("signal_family", signalFamily);
    if (signalStrength !== "All") params.set("signal_strength", signalStrength);
    if (painLayer !== "All") params.set("pain_layer", painLayer);
    if (tag.trim()) params.set("tag", tag.trim());
    if (createdFrom) params.set("created_from", createdFrom);
    if (createdTo) params.set("created_to", createdTo);
    return params;
  }

  // Debounce free-text inputs (search, tag) so we don't fire a request per
  // keystroke; dropdown/date changes fire immediately.
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (authLoading) return;
    let cancelled = false;

    function doFetch() {
      void (async () => {
        setIsLoading(true);
        try {
          const params = buildFilterParams();
          params.set("page", String(page));
          params.set("limit", String(pageSize));

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
    }

    if (debounceRef.current !== null) clearTimeout(debounceRef.current);
    if (search !== "" || tag !== "") {
      debounceRef.current = setTimeout(doFetch, 300);
    } else {
      doFetch();
    }

    return () => {
      cancelled = true;
      if (debounceRef.current !== null) clearTimeout(debounceRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    authLoading,
    page,
    pageSize,
    search,
    insightType,
    signalFamily,
    signalStrength,
    painLayer,
    tag,
    createdFrom,
    createdTo,
  ]);

  // Fetch the chart distributions. Keyed on filters only (not pagination) so
  // paging through the list doesn't refetch the aggregates. Charts reflect the
  // full filtered dataset, computed server-side. Debounced the same as the
  // list fetch so search/tag typing doesn't double the request volume.
  const summaryDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (authLoading) return;
    let cancelled = false;

    function doFetch() {
      void (async () => {
        setSummaryLoading(true);
        try {
          const params = buildFilterParams();
          const qs = params.toString();
          const data = await apiClient.get<CIInsightDistribution>(
            `/ci/insights/summary${qs ? `?${qs}` : ""}`,
            { silent: true }
          );
          if (!cancelled) setSummary(data);
        } catch {
          if (!cancelled) setSummary(null);
        } finally {
          if (!cancelled) setSummaryLoading(false);
        }
      })();
    }

    if (summaryDebounceRef.current !== null) clearTimeout(summaryDebounceRef.current);
    if (search !== "" || tag !== "") {
      summaryDebounceRef.current = setTimeout(doFetch, 300);
    } else {
      doFetch();
    }

    return () => {
      cancelled = true;
      if (summaryDebounceRef.current !== null) clearTimeout(summaryDebounceRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    authLoading,
    search,
    insightType,
    signalFamily,
    signalStrength,
    painLayer,
    tag,
    createdFrom,
    createdTo,
  ]);

  // Reset to page 1 whenever a filter changes.
  useEffect(() => {
    setPage(1);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search, insightType, signalFamily, signalStrength, painLayer, tag, createdFrom, createdTo]);

  function handleClear() {
    setSearch("");
    setInsightType("All");
    setSignalFamily("All");
    setSignalStrength("All");
    setPainLayer("All");
    setTag("");
    setCreatedFrom("");
    setCreatedTo("");
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

        {/* Charts — aggregated distributions over the full filtered dataset */}
        <InsightsCharts data={summary} isLoading={summaryLoading} />

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
              search={search}
              onSearchChange={setSearch}
              insightType={insightType}
              signalFamily={signalFamily}
              signalStrength={signalStrength}
              painLayer={painLayer}
              tag={tag}
              onTagChange={setTag}
              createdFrom={createdFrom}
              createdTo={createdTo}
              insightTypeOptions={facets.insight_type}
              signalFamilyOptions={facets.signal_family}
              signalStrengthOptions={facets.signal_strength}
              painLayerOptions={facets.pain_layer}
              onInsightTypeChange={setInsightType}
              onSignalFamilyChange={setSignalFamily}
              onSignalStrengthChange={setSignalStrength}
              onPainLayerChange={setPainLayer}
              onCreatedFromChange={setCreatedFrom}
              onCreatedToChange={setCreatedTo}
              onClear={handleClear}
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
