"use client";

import { useEffect, useRef, useState } from "react";
import { Header } from "@/components/layout/header";
import { apiClient } from "@/lib/api-client";
import { useAuth } from "@/hooks/use-auth";
import type {
  CIMarketSignal,
  CIMarketSignalsResponse,
  CIMarketSignalFacets,
} from "@/types";

// ─── Constants ────────────────────────────────────────────────────────────────

type SortBy = "total_mentions" | "last_30_days" | "last_7_days" | "momentum";

const SORT_OPTIONS: { label: string; value: SortBy }[] = [
  { label: "Total Mentions", value: "total_mentions" },
  { label: "Momentum", value: "momentum" },
  { label: "Last 30 Days", value: "last_30_days" },
  { label: "Last 7 Days", value: "last_7_days" },
];

const DEFAULT_FACETS: CIMarketSignalFacets = {
  insight_type: [],
  signal_family: [],
};

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

// ─── Momentum chip ────────────────────────────────────────────────────────────

/** Momentum reads as a plain-language chip, not a raw percentage — the
 * underlying volumes are small (most signals sit at 1-3 total mentions), so
 * a "+400%" figure would overstate a jump from 1 mention to 2. The chip
 * communicates direction and rough magnitude, never false precision. */
function MomentumChip({ momentum }: { momentum: number | null }) {
  if (momentum === null) {
    return (
      <span className="inline-flex items-center gap-1 text-[11px] font-medium px-2 py-0.5 rounded-full bg-gray-100 text-gray-500">
        Not enough data
      </span>
    );
  }
  if (momentum > 0.15) {
    return (
      <span className="inline-flex items-center gap-1 text-[11px] font-medium px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800">
        ↑ Picking up
      </span>
    );
  }
  if (momentum < -0.15) {
    return (
      <span className="inline-flex items-center gap-1 text-[11px] font-medium px-2 py-0.5 rounded-full bg-red-100 text-red-800">
        ↓ Cooling off
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 text-[11px] font-medium px-2 py-0.5 rounded-full bg-gray-100 text-gray-600">
      → Steady
    </span>
  );
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

// ─── Expandable quote ─────────────────────────────────────────────────────────

function ExpandableQuote({ quote }: { quote: string }) {
  const [expanded, setExpanded] = useState(false);
  const isLong = quote.length > 120;

  return (
    <button
      type="button"
      onClick={() => isLong && setExpanded((v) => !v)}
      className={`text-left text-xs italic text-gray-400 leading-relaxed border-t border-gray-100 pt-3 ${
        isLong ? "cursor-pointer hover:text-gray-500" : "cursor-default"
      }`}
    >
      &ldquo;{expanded || !isLong ? quote : `${quote.slice(0, 120)}…`}&rdquo;
      {isLong && (
        <span className="block text-[10px] not-italic text-emerald-600 font-medium mt-1">
          {expanded ? "Show less" : "Read more"}
        </span>
      )}
    </button>
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

      {/* Momentum + total mentions — the headline read of the card */}
      <div className="flex items-center justify-between gap-2">
        <MomentumChip momentum={signal.momentum} />
        <span className="text-[11px] text-gray-500">
          <span className="font-semibold text-gray-700">{signal.total_mentions}</span>{" "}
          total mention{signal.total_mentions === 1 ? "" : "s"}
        </span>
      </div>

      {/* Trend bars */}
      <TrendBar signal={signal} />

      {/* Best marketing angle — surfaced prominently, above the quote */}
      {signal.best_marketing_angle && (
        <p className="text-xs font-medium text-emerald-700 bg-emerald-50 rounded-lg px-3 py-2 leading-relaxed">
          💡 {signal.best_marketing_angle}
        </p>
      )}

      {/* Example quote — collapsible rather than a raw dump */}
      {signal.example_quote && <ExpandableQuote quote={signal.example_quote} />}
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
      <div className="h-5 bg-gray-200 rounded-full w-24" />
      <div className="space-y-2">
        <div className="h-2 bg-gray-200 rounded w-full" />
        <div className="h-2 bg-gray-200 rounded w-full" />
        <div className="h-2 bg-gray-200 rounded w-full" />
      </div>
      <div className="h-10 bg-gray-200 rounded-lg w-full" />
    </div>
  );
}

// ─── Stat strip ───────────────────────────────────────────────────────────────

/** A small headline strip above the grid — how many signals are trending up
 * vs. down right now, computed client-side from the current filtered page's
 * momentum classification (matches the same thresholds as MomentumChip). */
function StatStrip({ signals, total }: { signals: CIMarketSignal[]; total: number }) {
  const trending = signals.filter((s) => (s.momentum ?? 0) > 0.15).length;
  const cooling = signals.filter((s) => (s.momentum ?? 0) < -0.15).length;

  return (
    <div className="flex flex-wrap items-center gap-4 px-5 py-3 bg-gray-50/60 border-b border-gray-100 text-xs text-gray-500">
      <span>
        <span className="font-semibold text-gray-700">{total}</span> signal
        {total === 1 ? "" : "s"} tracked
      </span>
      <span className="text-gray-300">·</span>
      <span>
        <span className="font-semibold text-emerald-700">{trending}</span> picking up
        on this page
      </span>
      <span className="text-gray-300">·</span>
      <span>
        <span className="font-semibold text-red-700">{cooling}</span> cooling off
        on this page
      </span>
    </div>
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
  minMentions: string;
  updatedFrom: string;
  updatedTo: string;
  sortBy: SortBy;
  insightTypeOptions: string[];
  signalFamilyOptions: string[];
  onInsightTypeChange: (v: string) => void;
  onSignalFamilyChange: (v: string) => void;
  onMinMentionsChange: (v: string) => void;
  onUpdatedFromChange: (v: string) => void;
  onUpdatedToChange: (v: string) => void;
  onSortByChange: (v: SortBy) => void;
  onClear: () => void;
}

function FilterBar({
  search,
  onSearchChange,
  insightType,
  signalFamily,
  minMentions,
  updatedFrom,
  updatedTo,
  sortBy,
  insightTypeOptions,
  signalFamilyOptions,
  onInsightTypeChange,
  onSignalFamilyChange,
  onMinMentionsChange,
  onUpdatedFromChange,
  onUpdatedToChange,
  onSortByChange,
  onClear,
}: FilterBarProps) {
  const hasFilters =
    search !== "" ||
    insightType !== "All" ||
    signalFamily !== "All" ||
    minMentions !== "" ||
    updatedFrom !== "" ||
    updatedTo !== "";

  return (
    <div className="flex flex-wrap items-end gap-3 px-5 py-4 border-b border-gray-100">
      {/* Search */}
      <div className="flex flex-col gap-1">
        <label
          htmlFor="ms-filter-search"
          className="text-[10px] font-bold uppercase tracking-wider text-emerald-600"
        >
          Search
        </label>
        <input
          id="ms-filter-search"
          type="text"
          placeholder="Signal or quote..."
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
          className="text-sm border border-gray-200 rounded-lg px-3 py-1.5 bg-white text-gray-700 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent w-44"
        />
      </div>

      <FacetSelect
        id="ms-filter-insight-type"
        label="Insight Type"
        value={insightType}
        options={insightTypeOptions}
        onChange={onInsightTypeChange}
      />
      <FacetSelect
        id="ms-filter-signal-family"
        label="Signal Family"
        value={signalFamily}
        options={signalFamilyOptions}
        onChange={onSignalFamilyChange}
      />

      {/* Min mentions */}
      <div className="flex flex-col gap-1">
        <label
          htmlFor="ms-min-mentions"
          className="text-[10px] font-bold uppercase tracking-wider text-emerald-600"
        >
          Min Mentions
        </label>
        <input
          id="ms-min-mentions"
          type="number"
          min={0}
          placeholder="0"
          value={minMentions}
          onChange={(e) => onMinMentionsChange(e.target.value)}
          className="text-sm border border-gray-200 rounded-lg px-3 py-1.5 bg-white text-gray-700 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent w-20"
        />
      </div>

      {/* Updated-date range */}
      <div className="flex flex-col gap-1">
        <label className="text-[10px] font-bold uppercase tracking-wider text-emerald-600">
          Updated
        </label>
        <div className="flex items-center gap-1.5 text-gray-500">
          <input
            type="date"
            aria-label="Updated on or after"
            value={updatedFrom}
            max={updatedTo || undefined}
            onChange={(e) => onUpdatedFromChange(e.target.value)}
            className="px-2 py-1.5 text-sm border border-gray-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent text-gray-600"
          />
          <span className="text-gray-300">–</span>
          <input
            type="date"
            aria-label="Updated on or before"
            value={updatedTo}
            min={updatedFrom || undefined}
            onChange={(e) => onUpdatedToChange(e.target.value)}
            className="px-2 py-1.5 text-sm border border-gray-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent text-gray-600"
          />
        </div>
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
  const [total, setTotal] = useState(0);

  const [search, setSearch] = useState("");
  const [insightType, setInsightType] = useState("All");
  const [signalFamily, setSignalFamily] = useState("All");
  const [minMentions, setMinMentions] = useState("");
  const [updatedFrom, setUpdatedFrom] = useState("");
  const [updatedTo, setUpdatedTo] = useState("");
  const [sortBy, setSortBy] = useState<SortBy>("momentum");

  // Facet options, derived from the data so they can't drift from it.
  const [facets, setFacets] = useState<CIMarketSignalFacets>(DEFAULT_FACETS);

  // Fetch the available filter values once auth is ready. Silent — an
  // empty facet set just leaves the dropdowns with only "All".
  useEffect(() => {
    if (authLoading) return;
    let cancelled = false;

    void (async () => {
      try {
        const data = await apiClient.get<CIMarketSignalFacets>(
          "/ci/market-signals/facets",
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

  // Debounce free-text search so it doesn't fire a request per keystroke;
  // everything else fires immediately.
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (authLoading) return;
    let cancelled = false;

    function doFetch() {
      void (async () => {
        setIsLoading(true);
        try {
          const params = new URLSearchParams();
          if (search.trim()) params.set("search", search.trim());
          if (insightType !== "All") params.set("insight_type", insightType);
          if (signalFamily !== "All") params.set("signal_family", signalFamily);
          if (minMentions.trim()) params.set("min_mentions", minMentions.trim());
          if (updatedFrom) params.set("updated_from", updatedFrom);
          if (updatedTo) params.set("updated_to", updatedTo);
          params.set("sort_by", sortBy);
          params.set("limit", "60");

          const data = await apiClient.get<CIMarketSignalsResponse>(
            `/ci/market-signals?${params.toString()}`,
            { silent: true }
          );
          if (!cancelled) {
            setSignals(data.data);
            setTotal(data.total);
          }
        } catch {
          if (!cancelled) {
            setSignals([]);
            setTotal(0);
          }
        } finally {
          if (!cancelled) setIsLoading(false);
        }
      })();
    }

    if (debounceRef.current !== null) clearTimeout(debounceRef.current);
    if (search !== "") {
      debounceRef.current = setTimeout(doFetch, 300);
    } else {
      doFetch();
    }

    return () => {
      cancelled = true;
      if (debounceRef.current !== null) clearTimeout(debounceRef.current);
    };
  }, [authLoading, search, insightType, signalFamily, minMentions, updatedFrom, updatedTo, sortBy]);

  function handleClear() {
    setSearch("");
    setInsightType("All");
    setSignalFamily("All");
    setMinMentions("");
    setUpdatedFrom("");
    setUpdatedTo("");
  }

  return (
    <>
      <Header title="Market Signals" />

      <main className="flex-1 overflow-y-auto p-7 space-y-6">
        {/* Page heading */}
        <div>
          <h1 className="text-xl font-bold text-gray-900">Market Signals</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            What&apos;s trending across every analyzed call — mentions this week
            against each signal&apos;s own recent baseline, not raw counts alone.
          </p>
        </div>

        {/* Signals card */}
        <section aria-label="Market signals">
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
            {/* Card header */}
            <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
              <h2 className="text-sm font-bold text-gray-900">
                Trending Signals
              </h2>
              {!isLoading && (
                <span className="text-xs text-gray-400">
                  {signals.length} shown
                </span>
              )}
            </div>

            {/* Filter bar */}
            <FilterBar
              search={search}
              onSearchChange={setSearch}
              insightType={insightType}
              signalFamily={signalFamily}
              minMentions={minMentions}
              updatedFrom={updatedFrom}
              updatedTo={updatedTo}
              sortBy={sortBy}
              insightTypeOptions={facets.insight_type}
              signalFamilyOptions={facets.signal_family}
              onInsightTypeChange={setInsightType}
              onSignalFamilyChange={setSignalFamily}
              onMinMentionsChange={setMinMentions}
              onUpdatedFromChange={setUpdatedFrom}
              onUpdatedToChange={setUpdatedTo}
              onSortByChange={setSortBy}
              onClear={handleClear}
            />

            {/* Stat strip */}
            {!isLoading && signals.length > 0 && (
              <StatStrip signals={signals} total={total} />
            )}

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
