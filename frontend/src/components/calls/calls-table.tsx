"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { apiClient, ApiError } from "@/lib/api-client";
import { useAuth } from "@/hooks/use-auth";
import { usePagination } from "@/hooks/use-pagination";
import { showError, showWarning } from "@/lib/toast";
import { Pagination } from "@/components/ui";
import type { CICallFacets } from "@/types";

// ─── Types ────────────────────────────────────────────────────────────────────

export interface CallSummary {
  call_id: string;
  date: string | null;
  call_type: string | null;
  call_result: string | null;
  call_owner: string | null; // the rep/CSR who ran the call
  lead_id: string | null; // the lead/prospect on the call
  lead_name: string | null;
  transcript_quality: string | null;
  processed_date: string | null;
  insights_count: number;
  source: string | null;
  created_at: string | null;
}

interface CallsResponse {
  data: CallSummary[];
  pagination: { total: number; page: number; limit: number };
}

// Backend-whitelisted sort columns (must match _CALL_SORTABLE in routes/ci.py).
type SortColumn =
  | "date"
  | "created_at"
  | "call_type"
  | "call_result"
  | "call_owner"
  | "source";
type SortDir = "asc" | "desc";

interface CallsTableProps {
  /** When set (e.g. "Sales,Discovery"), the call_type filter is locked to this
   *  set and the type dropdown is hidden — used by the Sales Calls page. */
  lockedCallType?: string;
  /** Hide the call-type filter dropdown (Sales Calls already constrains it). */
  hideTypeFilter?: boolean;
  /** Where each row links — the detail page. */
  detailHref?: (callId: string) => string;
  /** Bump this to force a refetch (e.g. after a new transcript upload). */
  refreshKey?: number;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  } catch {
    return iso;
  }
}

async function downloadTranscript(callId: string): Promise<void> {
  let blob: Blob;
  try {
    blob = await apiClient.getBlob(`/ci/calls/${callId}/transcript.txt`, { silent: true });
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) {
      showWarning("No transcript on file for this call.");
    } else {
      const status = err instanceof ApiError ? err.status : "unknown";
      showError(`Download failed (${status})`);
    }
    return;
  }
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${callId}.txt`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

// ─── Sortable header cell ───────────────────────────────────────────────────────

function SortableHeader({
  label,
  column,
  sortBy,
  sortDir,
  onSort,
  className = "",
}: {
  label: string;
  column: SortColumn;
  sortBy: SortColumn;
  sortDir: SortDir;
  onSort: (col: SortColumn) => void;
  className?: string;
}) {
  const active = sortBy === column;
  return (
    <th
      className={`px-4 py-2.5 text-left text-[10px] font-bold uppercase tracking-widest text-gray-400 ${className}`}
    >
      <button
        type="button"
        onClick={() => onSort(column)}
        aria-sort={active ? (sortDir === "asc" ? "ascending" : "descending") : "none"}
        className={`inline-flex items-center gap-1 uppercase tracking-widest transition-colors hover:text-gray-600 ${
          active ? "text-gray-700" : ""
        }`}
      >
        {label}
        <span className="text-[9px] leading-none w-2 inline-block" aria-hidden="true">
          {active ? (sortDir === "asc" ? "▲" : "▼") : "↕"}
        </span>
      </button>
    </th>
  );
}

// ─── Multi-select filter dropdown ───────────────────────────────────────────────

function MultiSelect({
  label,
  options,
  selected,
  onToggle,
  onClear,
}: {
  label: string; // e.g. "Types", "Results"
  options: string[];
  selected: Set<string>;
  onToggle: (value: string) => void;
  onClear: () => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement | null>(null);

  // Close on outside click.
  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [open]);

  const count = selected.size;
  const buttonLabel = count === 0 ? `All ${label}` : `${label}: ${count}`;

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className={`flex items-center gap-1.5 px-2.5 py-1.5 text-sm border rounded-lg bg-white transition-colors ${
          count > 0
            ? "border-accent-300 text-accent-700"
            : "border-gray-200 text-gray-600 hover:border-gray-300"
        }`}
      >
        {buttonLabel}
        <span className="text-[9px] text-gray-400" aria-hidden>▼</span>
      </button>
      {open && (
        <div className="absolute z-20 mt-1 w-56 max-h-72 overflow-y-auto rounded-lg border border-gray-200 bg-white shadow-lg py-1">
          <div className="flex items-center justify-between px-3 py-1.5 border-b border-gray-100">
            <span className="text-[11px] font-semibold uppercase tracking-wide text-gray-400">
              {label}
            </span>
            {count > 0 && (
              <button
                type="button"
                onClick={onClear}
                className="text-[11px] text-gray-400 hover:text-gray-600"
              >
                Clear
              </button>
            )}
          </div>
          {options.length === 0 ? (
            <p className="px-3 py-2 text-[12px] text-gray-400">No options.</p>
          ) : (
            options.map((opt) => {
              const checked = selected.has(opt);
              return (
                <label
                  key={opt}
                  className="flex items-center gap-2 px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-50 cursor-pointer"
                >
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => onToggle(opt)}
                    className="h-3.5 w-3.5 rounded border-gray-300 text-accent-600 focus:ring-accent-400"
                  />
                  <span className="truncate">{opt}</span>
                </label>
              );
            })
          )}
        </div>
      )}
    </div>
  );
}

// ─── Badges ─────────────────────────────────────────────────────────────────────

function ProvenanceTag({ source }: { source: string | null }) {
  const isWgr = source === "wgr";
  return (
    <span
      className={`text-[10px] font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded border ${
        isWgr
          ? "bg-violet-50 text-violet-700 border-violet-200"
          : "bg-sky-50 text-sky-700 border-sky-200"
      }`}
      title={
        isWgr
          ? "Synced read-only from the client (WGR) database"
          : "Uploaded and analyzed in Central Intelligence"
      }
    >
      {isWgr ? "WGR" : "CI"}
    </span>
  );
}

// ─── Table ──────────────────────────────────────────────────────────────────────

export function CallsTable({
  lockedCallType,
  hideTypeFilter = false,
  // ?from=calls so the call-detail breadcrumb links back to All Calls.
  detailHref = (id) => `/sales-calls/${id}?from=calls`,
  refreshKey = 0,
}: CallsTableProps) {
  const { isLoading: authLoading } = useAuth();

  const [calls, setCalls] = useState<CallSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(true);

  // Pagination — page size persisted per surface (Sales vs All Calls share the
  // component but get distinct keys via lockedCallType).
  const { page, pageSize, setPage, setPageSize, resetToFirstPage } =
    usePagination(`calls:${lockedCallType ?? "all"}`);

  // Filters. Type + Result are multi-select (empty Set = no filter / "all").
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState<Set<string>>(new Set());
  const [resultFilter, setResultFilter] = useState<Set<string>>(new Set());
  const [sourceFilter, setSourceFilter] = useState<string>("all");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  // Sort
  const [sortBy, setSortBy] = useState<SortColumn>("date");
  const [sortDir, setSortDir] = useState<SortDir>("desc");

  // Filter options, derived from the data so they can't drift from it.
  const [facets, setFacets] = useState<CICallFacets>({
    call_type: [],
    call_result: [],
  });

  const hasFilters =
    search !== "" ||
    typeFilter.size > 0 ||
    resultFilter.size > 0 ||
    sourceFilter !== "all" ||
    dateFrom !== "" ||
    dateTo !== "";

  function toggleSort(col: SortColumn) {
    if (col === sortBy) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortBy(col);
      setSortDir("desc");
    }
  }

  // Toggle one value in a multi-select filter Set (returns a fresh Set so the
  // fetch effect's deps see a new reference).
  function toggleIn(
    setter: React.Dispatch<React.SetStateAction<Set<string>>>,
    value: string,
  ) {
    setter((prev) => {
      const next = new Set(prev);
      if (next.has(value)) next.delete(value);
      else next.add(value);
      return next;
    });
  }

  function clearFilters() {
    setSearch("");
    setTypeFilter(new Set());
    setResultFilter(new Set());
    setSourceFilter("all");
    setDateFrom("");
    setDateTo("");
  }

  const loadCalls = useCallback(async () => {
    setIsLoading(true);
    try {
      const params = new URLSearchParams();
      params.set("page", String(page));
      params.set("limit", String(pageSize));
      params.set("sort_by", sortBy);
      params.set("sort_dir", sortDir);
      // Sales Calls locks the type set; otherwise honor the multi-select.
      if (lockedCallType) params.set("call_type", lockedCallType);
      else if (typeFilter.size > 0) params.set("call_type", Array.from(typeFilter).join(","));
      if (resultFilter.size > 0) params.set("call_result", Array.from(resultFilter).join(","));
      if (sourceFilter !== "all") params.set("source", sourceFilter);
      if (search.trim() !== "") params.set("search", search.trim());
      if (dateFrom) params.set("date_from", dateFrom);
      if (dateTo) params.set("date_to", dateTo);

      const result = await apiClient.get<CallsResponse>(
        `/ci/calls?${params.toString()}`,
        { silent: true },
      );
      setCalls(result.data);
      setTotal(result.pagination.total);
    } catch {
      setCalls([]);
      setTotal(0);
    } finally {
      setIsLoading(false);
    }
  }, [
    lockedCallType,
    typeFilter,
    resultFilter,
    sourceFilter,
    search,
    dateFrom,
    dateTo,
    sortBy,
    sortDir,
    page,
    pageSize,
  ]);

  // When a filter/search/sort narrows the set, jump back to page 1 so the user
  // isn't stranded on a page that no longer exists.
  useEffect(() => {
    resetToFirstPage();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    lockedCallType,
    typeFilter,
    resultFilter,
    sourceFilter,
    search,
    dateFrom,
    dateTo,
    sortBy,
    sortDir,
  ]);

  useEffect(() => {
    if (authLoading) return;
    void loadCalls();
    // refreshKey is an explicit reload trigger (e.g. post-upload).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authLoading, loadCalls, refreshKey]);

  // Fetch the available filter values once auth is ready. Silent — an empty
  // facet set just leaves the dropdowns with only their "All" option.
  useEffect(() => {
    if (authLoading) return;
    let cancelled = false;

    void (async () => {
      try {
        const data = await apiClient.get<CICallFacets>("/ci/calls/facets", {
          silent: true,
        });
        if (!cancelled) setFacets(data);
      } catch {
        /* leave facets empty — dropdowns still show "All" */
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [authLoading]);

  const showTypeColumn = useMemo(() => !hideTypeFilter, [hideTypeFilter]);

  return (
    <section aria-label="Calls">
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
        {/* Filter bar */}
        <div className="px-4 py-3 border-b border-gray-100 flex items-center gap-2.5 flex-wrap">
          <div className="relative flex-1 min-w-[180px] max-w-xs">
            <svg
              className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-400"
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 20 20"
              fill="currentColor"
              aria-hidden="true"
            >
              <path
                fillRule="evenodd"
                d="M9 3.5a5.5 5.5 0 100 11 5.5 5.5 0 000-11zM2 9a7 7 0 1112.452 4.391l3.328 3.329a.75.75 0 11-1.06 1.06l-3.329-3.328A7 7 0 012 9z"
                clipRule="evenodd"
              />
            </svg>
            <input
              type="text"
              placeholder="Search by ID or owner…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-8 pr-3 py-1.5 text-sm border border-gray-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-400 transition-all"
            />
          </div>

          {!hideTypeFilter && (
            <MultiSelect
              label="Types"
              options={facets.call_type}
              selected={typeFilter}
              onToggle={(v) => toggleIn(setTypeFilter, v)}
              onClear={() => setTypeFilter(new Set())}
            />
          )}

          <MultiSelect
            label="Results"
            options={facets.call_result}
            selected={resultFilter}
            onToggle={(v) => toggleIn(setResultFilter, v)}
            onClear={() => setResultFilter(new Set())}
          />

          <select
            value={sourceFilter}
            onChange={(e) => setSourceFilter(e.target.value)}
            className="px-2.5 py-1.5 text-sm border border-gray-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-400 text-gray-600"
          >
            <option value="all">All Sources</option>
            <option value="wgr">WGR-synced</option>
            <option value="ci_upload">CI-analyzed</option>
          </select>

          {/* Call-date range */}
          <div className="flex items-center gap-1.5 text-xs text-gray-500">
            <input
              type="date"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
              title="Call date from"
              className="px-2 py-1.5 text-sm border border-gray-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-400 text-gray-600"
            />
            <span aria-hidden="true">–</span>
            <input
              type="date"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
              title="Call date to"
              className="px-2 py-1.5 text-sm border border-gray-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-400 text-gray-600"
            />
          </div>

          {hasFilters && (
            <button
              type="button"
              onClick={clearFilters}
              className="text-xs font-medium text-gray-500 hover:text-gray-700 underline underline-offset-2"
            >
              Clear
            </button>
          )}

          <span className="ml-auto text-xs text-gray-400">
            {isLoading ? "Loading…" : `${total} call${total === 1 ? "" : "s"}`}
          </span>
        </div>

        {/* Table */}
        {isLoading ? (
          <div className="px-4 py-8 text-xs text-gray-400">Loading calls…</div>
        ) : calls.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 gap-3">
            <span className="text-4xl" aria-hidden="true">
              ☎️
            </span>
            <p className="text-sm font-medium text-gray-500">
              {hasFilters ? "No calls match these filters." : "No calls yet."}
            </p>
            {hasFilters && (
              <button
                type="button"
                onClick={clearFilters}
                className="text-xs font-medium text-accent-600 hover:text-accent-700 underline underline-offset-2"
              >
                Clear filters
              </button>
            )}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50/60">
                <tr className="border-b border-gray-100">
                  {showTypeColumn && (
                    <SortableHeader
                      label="Type"
                      column="call_type"
                      sortBy={sortBy}
                      sortDir={sortDir}
                      onSort={toggleSort}
                    />
                  )}
                  <SortableHeader
                    label="Call Date"
                    column="date"
                    sortBy={sortBy}
                    sortDir={sortDir}
                    onSort={toggleSort}
                  />
                  <SortableHeader
                    label="Date Added"
                    column="created_at"
                    sortBy={sortBy}
                    sortDir={sortDir}
                    onSort={toggleSort}
                  />
                  <SortableHeader
                    label="Result"
                    column="call_result"
                    sortBy={sortBy}
                    sortDir={sortDir}
                    onSort={toggleSort}
                  />
                  {/* Lead (prospect) — not a Call column, so non-sortable. */}
                  <th className="px-4 py-2.5 text-left text-[10px] font-bold uppercase tracking-widest text-gray-400">
                    Lead
                  </th>
                  <SortableHeader
                    label="Owner"
                    column="call_owner"
                    sortBy={sortBy}
                    sortDir={sortDir}
                    onSort={toggleSort}
                  />
                  <th className="px-4 py-2.5 text-left text-[10px] font-bold uppercase tracking-widest text-gray-400">
                    Insights
                  </th>
                  <SortableHeader
                    label="Source"
                    column="source"
                    sortBy={sortBy}
                    sortDir={sortDir}
                    onSort={toggleSort}
                  />
                  <th className="px-4 py-2.5" />
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {calls.map((call) => (
                  <tr key={call.call_id} className="hover:bg-gray-50 transition-colors">
                    {showTypeColumn && (
                      <td className="px-4 py-3">
                        <Link
                          href={detailHref(call.call_id)}
                          className="text-sm font-medium text-gray-900 hover:text-accent-700"
                        >
                          {call.call_type ?? "Call"}
                        </Link>
                      </td>
                    )}
                    <td className="px-4 py-3 text-sm text-gray-600 whitespace-nowrap">
                      {!showTypeColumn ? (
                        <Link
                          href={detailHref(call.call_id)}
                          className="font-medium text-gray-900 hover:text-accent-700"
                        >
                          {formatDate(call.date)}
                        </Link>
                      ) : (
                        formatDate(call.date)
                      )}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600 whitespace-nowrap">
                      {formatDate(call.created_at)}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600">
                      {call.call_result ?? "—"}
                    </td>
                    <td className="px-4 py-3 text-sm whitespace-nowrap">
                      {call.lead_id && call.lead_name ? (
                        <Link
                          href={`/leads/${call.lead_id}`}
                          className="font-medium text-accent-700 hover:text-accent-800 hover:underline"
                        >
                          {call.lead_name}
                        </Link>
                      ) : (
                        <span className="text-gray-400">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600 whitespace-nowrap">
                      {call.call_owner ?? "—"}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600">
                      {call.insights_count}
                    </td>
                    <td className="px-4 py-3">
                      <ProvenanceTag source={call.source} />
                    </td>
                    <td className="px-4 py-3 text-right whitespace-nowrap">
                      <button
                        type="button"
                        onClick={() => void downloadTranscript(call.call_id)}
                        className="text-xs font-medium text-accent-600 hover:text-accent-700 underline underline-offset-2"
                      >
                        Transcript
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {!isLoading && total > 0 && (
          <Pagination
            page={page}
            total={total}
            pageSize={pageSize}
            onPageChange={setPage}
            onPageSizeChange={setPageSize}
          />
        )}
      </div>
    </section>
  );
}
