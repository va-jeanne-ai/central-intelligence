"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Header } from "@/components/layout/header";
import { TranscriptUploadWidget } from "@/components/upload/transcript-upload-widget";
import type { TranscriptUploadResult } from "@/components/upload/transcript-upload-widget";
import { KpiCard } from "@/components/ui/kpi-card";
import { Pagination } from "@/components/ui";
import { Button } from "@/components/ui/button";
import { AnalyzeViewButton } from "@/components/analyze/AnalyzeViewButton";
import { AnalyzeViewDrawer } from "@/components/analyze/AnalyzeViewDrawer";
import { apiClient } from "@/lib/api-client";
import { useAuth } from "@/hooks/use-auth";
import { usePagination } from "@/hooks/use-pagination";
import { showSuccess, showError } from "@/lib/toast";

// ─── Types (bound to /ci/calls, /ci/calls/stats, /ci/calls/{id}) ────────────────

interface CallStats {
  total_calls: number;
  calls_this_month: number;
  pain_points_found: number;
  content_ideas: number;
  this_month_delta: number;
}

interface CallSummary {
  call_id: string;
  date: string | null;
  call_type: string | null;
  call_result: string | null;
  call_owner: string | null; // the rep/CSR who ran the call (raw WGR string)
  rep_id: string | null; // call_owner resolved against the sales_reps roster
  rep_name: string | null;
  lead_id: string | null; // the prospect on the call
  lead_name: string | null;
  processed_date: string | null;
  insights_count: number;
  pain_points_count: number;
  content_ideas_count: number;
  duration_minutes: number | null;
  transcript_excerpt: string | null;
  source: string | null;
}

interface RepOption {
  rep_id: string;
  full_name: string;
  status: string;
}

interface CallsResponse {
  data: CallSummary[];
  pagination: { total: number; page: number; limit: number };
}

interface InsightBrief {
  insight_id: string;
  insight_type: string | null;
  signal_family: string | null;
  signal: string | null;
  raw_quote: string | null;
}

interface ContentIdeaBrief {
  content_id: string;
  content_premise?: string | null;
  content_format?: string | null;
  hook_opening_line?: string | null;
}

interface CallDetailResponse {
  call: { transcript?: string | null; summary?: string | null };
  insights: InsightBrief[];
  content_ideas: ContentIdeaBrief[];
}

// ─── Helpers ────────────────────────────────────────────────────────────────────

const PAIN_TYPES = new Set(["Pain", "Objection", "Belief"]);

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

function initials(name: string | null): string {
  if (!name) return "—";
  const parts = name.trim().split(/\s+/);
  return ((parts[0]?.[0] ?? "") + (parts.length > 1 ? parts[parts.length - 1][0] : "")).toUpperCase() || "—";
}

// Map the real call_result values (verified live: No Show, Follow-up
// Scheduled, Deposit Paid, Not Qualified, Booked, Enrolled, No Sale, Pending)
// to colored status pills. Palette matches the Appointments page convention:
// green = won/completed, blue = scheduled/booked, gray = no-show/neutral,
// red = lost/disqualified, amber = pending/in-progress. Unknown values fall
// back to a neutral gray pill rather than breaking.
const RESULT_STYLE: { match: (r: string) => boolean; classes: string; dot: string }[] = [
  { match: (r) => /won|sale|sold|enrolled|deposit|paid/.test(r), classes: "bg-green-50 text-green-700", dot: "bg-green-500" },
  { match: (r) => /booked|follow.?up|scheduled/.test(r), classes: "bg-blue-50 text-blue-700", dot: "bg-blue-500" },
  { match: (r) => /no.?show/.test(r), classes: "bg-gray-100 text-gray-600", dot: "bg-gray-400" },
  { match: (r) => /not.?qualified|no.?sale|lost/.test(r), classes: "bg-red-50 text-red-700", dot: "bg-red-500" },
  { match: (r) => /pending|processing/.test(r), classes: "bg-amber-50 text-amber-700", dot: "bg-amber-500" },
];

function ResultBadge({ result }: { result: string | null }) {
  if (!result) return null;
  const lower = result.toLowerCase();
  const style = RESULT_STYLE.find((s) => s.match(lower)) ?? {
    classes: "bg-gray-100 text-gray-600",
    dot: "bg-gray-400",
  };
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[12px] font-semibold ${style.classes}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${"dot" in style ? style.dot : "bg-gray-400"}`} aria-hidden />
      {result}
    </span>
  );
}

// ─── Expandable call card ───────────────────────────────────────────────────────

// ─── Lead link / picker ─────────────────────────────────────────────────────────

interface LeadSearchRow {
  id: string;
  name: string | null;
  email: string | null;
}

function LeadLinkRow({ call, onChanged }: { call: CallSummary; onChanged: () => void }) {
  const router = useRouter();
  const [picking, setPicking] = useState(false);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<LeadSearchRow[]>([]);
  const [searching, setSearching] = useState(false);
  const [saving, setSaving] = useState(false);

  // Debounced lead search (reuses /leads?search=).
  useEffect(() => {
    if (!picking || query.trim().length < 2) {
      setResults([]);
      return;
    }
    const t = setTimeout(async () => {
      setSearching(true);
      try {
        const data = await apiClient.get<{ leads: LeadSearchRow[] }>(
          `/leads?search=${encodeURIComponent(query.trim())}&per_page=8`,
          { silent: true },
        );
        setResults(data.leads);
      } catch {
        setResults([]);
      } finally {
        setSearching(false);
      }
    }, 300);
    return () => clearTimeout(t);
  }, [picking, query]);

  const linkLead = useCallback(
    async (leadId: string) => {
      setSaving(true);
      try {
        await apiClient.patch(`/ci/calls/${call.call_id}`, { lead_id: leadId }, { silent: true });
        showSuccess("Call linked to lead.");
        setPicking(false);
        setQuery("");
        onChanged();
      } catch (err) {
        showError(err instanceof Error ? err.message : "Couldn't link the lead.");
      } finally {
        setSaving(false);
      }
    },
    [call.call_id, onChanged],
  );

  // Linked → show the lead + a "view" link.
  if (call.lead_id && call.lead_name) {
    return (
      <div className="flex items-center gap-2 text-[13px]">
        <span className="text-gray-400">Lead:</span>
        <button
          type="button"
          onClick={() => router.push(`/leads/${call.lead_id}`)}
          className="font-semibold text-accent-700 hover:text-accent-800 hover:underline"
        >
          {call.lead_name} →
        </button>
      </div>
    );
  }

  // Unlinked → search + pick.
  return (
    <div className="rounded-lg border border-dashed border-gray-200 bg-gray-50/60 px-3.5 py-3">
      {!picking ? (
        <div className="flex items-center justify-between gap-2">
          <span className="text-[13px] text-gray-500">Not linked to a lead.</span>
          <button
            type="button"
            onClick={() => setPicking(true)}
            className="text-[12px] font-semibold text-accent-600 hover:text-accent-700"
          >
            🔗 Link to lead
          </button>
        </div>
      ) : (
        <div className="space-y-2">
          <input
            type="text"
            autoFocus
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search a lead by name or email…"
            className="w-full rounded-md border border-gray-200 bg-white px-3 py-1.5 text-sm focus:border-accent-400 focus:outline-none focus:ring-1 focus:ring-accent-400"
          />
          {searching && <p className="text-[12px] text-gray-400">Searching…</p>}
          {!searching && query.trim().length >= 2 && results.length === 0 && (
            <p className="text-[12px] text-gray-400">No leads found.</p>
          )}
          {results.length > 0 && (
            <div className="max-h-48 overflow-y-auto divide-y divide-gray-100 rounded-md border border-gray-100 bg-white">
              {results.map((lead) => (
                <button
                  key={lead.id}
                  type="button"
                  disabled={saving}
                  onClick={() => void linkLead(lead.id)}
                  className="w-full px-3 py-2 text-left hover:bg-accent-50 disabled:opacity-50 transition-colors"
                >
                  <div className="text-[13px] font-medium text-gray-800">{lead.name || "—"}</div>
                  {lead.email && <div className="text-[11px] text-gray-400">{lead.email}</div>}
                </button>
              ))}
            </div>
          )}
          <button
            type="button"
            onClick={() => {
              setPicking(false);
              setQuery("");
            }}
            className="text-[12px] text-gray-400 hover:text-gray-600"
          >
            Cancel
          </button>
        </div>
      )}
    </div>
  );
}

function CallCard({ call, onChanged }: { call: CallSummary; onChanged: () => void }) {
  const [open, setOpen] = useState(false);
  const [detail, setDetail] = useState<CallDetailResponse | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);

  const toggle = useCallback(async () => {
    const next = !open;
    setOpen(next);
    if (next && detail === null && !loadingDetail) {
      setLoadingDetail(true);
      try {
        const d = await apiClient.get<CallDetailResponse>(`/ci/calls/${call.call_id}`, { silent: true });
        setDetail(d);
      } catch {
        /* leave detail null — the card shows a gentle fallback */
      } finally {
        setLoadingDetail(false);
      }
    }
  }, [open, detail, loadingDetail, call.call_id]);

  const painPoints = (detail?.insights ?? []).filter(
    (i) => i.insight_type && PAIN_TYPES.has(i.insight_type),
  );
  const ideas = detail?.content_ideas ?? [];

  // Primary identity = the LEAD (prospect). call_owner is the rep, shown as
  // "with <rep>". Unlinked calls fall back to a neutral label + a link action.
  // Prefer the roster-resolved rep_name (clean) over the raw call_owner string
  // (can carry whitespace/typo variants) when available.
  const leadDisplay = call.lead_name || (call.lead_id ? "Lead" : null);
  const title = `${leadDisplay ?? "Unlinked call"}${call.call_type ? ` — ${call.call_type} Call` : ""}`;
  const repDisplay = call.rep_name || call.call_owner;
  const metaParts = [
    repDisplay ? `with ${repDisplay}` : null,
    formatDate(call.date),
    call.duration_minutes ? `${Math.round(call.duration_minutes)} min` : null,
    call.source === "wgr" ? "WGR" : "CI",
  ].filter(Boolean);

  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
      {/* Header — clickable to expand */}
      <button
        type="button"
        onClick={() => void toggle()}
        aria-expanded={open}
        className="w-full flex items-center gap-3 px-5 py-4 text-left hover:bg-gray-50 transition-colors"
      >
        <span
          className={`flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full text-sm font-bold ${
            leadDisplay ? "bg-accent-100 text-accent-700" : "bg-gray-100 text-gray-400"
          }`}
        >
          {leadDisplay ? initials(call.lead_name) : "?"}
        </span>
        <div className="min-w-0 flex-1">
          <div className="text-sm font-bold text-gray-900 truncate">{title}</div>
          <div className="text-[12px] text-gray-500">{metaParts.join(" · ")}</div>
        </div>
        <ResultBadge result={call.call_result} />
        {call.pain_points_count > 0 && (
          <span className="inline-flex items-center rounded-full bg-amber-50 px-2.5 py-0.5 text-[12px] font-semibold text-amber-700">
            {call.pain_points_count} pain point{call.pain_points_count === 1 ? "" : "s"}
          </span>
        )}
        <span className={`text-gray-400 transition-transform duration-200 ${open ? "rotate-180" : ""}`} aria-hidden>
          ▾
        </span>
      </button>

      {/* Expanded detail */}
      {open && (
        <div className="border-t border-gray-100 px-5 py-4 space-y-4">
          {loadingDetail && <p className="text-[13px] text-gray-400">Loading analysis…</p>}

          {!loadingDetail && (
            <>
              {/* Lead link — view the connected lead, or attach one if unlinked */}
              <LeadLinkRow call={call} onChanged={onChanged} />

              {/* Transcript excerpt */}
              {call.transcript_excerpt && (
                <div>
                  <div className="text-[11px] font-bold uppercase tracking-wider text-gray-400 mb-1.5">
                    Transcript Excerpt
                  </div>
                  <p className="rounded-lg bg-gray-50 border border-gray-100 px-3.5 py-3 text-[13px] leading-relaxed text-gray-700">
                    {call.transcript_excerpt}
                  </p>
                </div>
              )}

              {/* Two columns: pain points + content ideas */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <div>
                  <div className="flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wider text-gray-500 mb-2">
                    <span className="h-2.5 w-2.5 rounded-full bg-red-500" aria-hidden /> Extracted Pain Points
                  </div>
                  {painPoints.length === 0 ? (
                    <p className="text-[13px] text-gray-400 italic">No pain points extracted.</p>
                  ) : (
                    <div className="space-y-1.5">
                      {painPoints.map((p) => (
                        <div
                          key={p.insight_id}
                          className="flex items-start gap-2 rounded-lg bg-orange-50/60 border border-orange-100 px-3 py-2 text-[13px] text-gray-700"
                        >
                          <span className="text-orange-500 mt-0.5" aria-hidden>•</span>
                          <span>{p.signal || p.signal_family || p.raw_quote || "Pain point"}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                <div>
                  <div className="flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wider text-gray-500 mb-2">
                    <span className="h-2.5 w-2.5 rounded-full bg-emerald-500" aria-hidden /> Content Ideas Generated
                  </div>
                  {ideas.length === 0 ? (
                    <p className="text-[13px] text-gray-400 italic">No content ideas generated.</p>
                  ) : (
                    <div className="space-y-1.5">
                      {ideas.map((idea) => (
                        <div
                          key={idea.content_id}
                          className="flex items-start gap-2 rounded-lg bg-emerald-50/60 border border-emerald-100 px-3 py-2 text-[13px] text-gray-700"
                        >
                          <span aria-hidden>💡</span>
                          <span>{idea.content_premise || idea.hook_opening_line || idea.content_format || "Content idea"}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

// Result excluded by default ("show all except No Show").
const DEFAULT_EXCLUDED_RESULT = "No Show";

export default function SalesCallsPage() {
  const router = useRouter();
  const { isLoading: authLoading } = useAuth();
  const [refreshKey, setRefreshKey] = useState(0);
  const [stats, setStats] = useState<CallStats | null>(null);
  const [calls, setCalls] = useState<CallSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [analyzeOpen, setAnalyzeOpen] = useState(false);
  const [analyzeParams, setAnalyzeParams] = useState<URLSearchParams | null>(null);

  const { page, pageSize, setPage, setPageSize, resetToFirstPage } =
    usePagination("sales-calls");

  // Search box: `search` is the live input, `debouncedSearch` is what's actually
  // queried (matches call id, rep, or the linked lead's name/email).
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(search.trim()), 300);
    return () => clearTimeout(t);
  }, [search]);

  // Date range + rep filters (server-side, mirrors the Appointments page).
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [repFilter, setRepFilter] = useState("all");
  const [reps, setReps] = useState<RepOption[]>([]);

  useEffect(() => {
    if (authLoading) return;
    void (async () => {
      try {
        const data = await apiClient.get<{ reps: RepOption[] }>("/reps", { silent: true });
        setReps(data.reps ?? []);
      } catch {
        setReps([]);
      }
    })();
  }, [authLoading]);

  // Multi-select result filter. `null` = not yet initialized (defaults seed from
  // the facets the first time they load: every result ON except "No Show").
  const [resultOptions, setResultOptions] = useState<string[]>([]);
  const [selectedResults, setSelectedResults] = useState<Set<string> | null>(null);

  // Load the available result values once and seed the default selection.
  useEffect(() => {
    if (authLoading || selectedResults !== null) return;
    void (async () => {
      try {
        const facets = await apiClient.get<{ call_result: string[] }>("/ci/calls/facets", {
          silent: true,
        });
        setResultOptions(facets.call_result);
        setSelectedResults(
          new Set(facets.call_result.filter((r) => r !== DEFAULT_EXCLUDED_RESULT)),
        );
      } catch {
        setSelectedResults(new Set()); // facets failed — treat as "no filter"
      }
    })();
  }, [authLoading, selectedResults]);

  const load = useCallback(async () => {
    try {
      const params = new URLSearchParams({
        call_type: "Sales,Discovery,Outbound",
        sort_by: "date",
        sort_dir: "desc",
        page: String(page),
        limit: String(pageSize),
      });
      // Only send call_result when a strict subset is selected — sending all
      // (or none) just means "no result filter".
      if (
        selectedResults &&
        selectedResults.size > 0 &&
        selectedResults.size < resultOptions.length
      ) {
        params.set("call_result", Array.from(selectedResults).join(","));
      }
      if (debouncedSearch) params.set("search", debouncedSearch);
      if (startDate) params.set("start", startDate);
      if (endDate) params.set("end", endDate);
      if (repFilter !== "all") params.set("rep", repFilter);
      const [statsData, callsData] = await Promise.all([
        apiClient.get<CallStats>("/ci/calls/stats", { silent: true }),
        apiClient.get<CallsResponse>(`/ci/calls?${params.toString()}`, { silent: true }),
      ]);
      setStats(statsData);
      setCalls(callsData.data);
      setTotal(callsData.pagination.total);
    } catch {
      /* leave empties — page renders with zeros */
    } finally {
      setIsLoading(false);
    }
  }, [selectedResults, resultOptions.length, page, pageSize, debouncedSearch, startDate, endDate, repFilter]);

  // Mirrors the list-fetch params in `load` above, minus pagination/sort —
  // snapshot for "Analyze this view". `call_type` is always pinned, matching load().
  const openAnalyze = useCallback(() => {
    const params = new URLSearchParams();
    params.set("call_type", "Sales,Discovery,Outbound");
    if (
      selectedResults &&
      selectedResults.size > 0 &&
      selectedResults.size < resultOptions.length
    ) {
      params.set("call_result", Array.from(selectedResults).join(","));
    }
    if (debouncedSearch) params.set("search", debouncedSearch);
    if (startDate) params.set("start", startDate);
    if (endDate) params.set("end", endDate);
    if (repFilter !== "all") params.set("rep", repFilter);
    setAnalyzeParams(params);
    setAnalyzeOpen(true);
  }, [selectedResults, resultOptions.length, debouncedSearch, startDate, endDate, repFilter]);

  useEffect(() => {
    if (authLoading || selectedResults === null) return;
    void load();
  }, [authLoading, load, refreshKey, selectedResults]);

  // Changing the result filter, search, date range, or rep narrows the set —
  // jump back to page 1.
  useEffect(() => {
    resetToFirstPage();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedResults, debouncedSearch, startDate, endDate, repFilter]);

  const toggleResult = useCallback((result: string) => {
    setSelectedResults((prev) => {
      const next = new Set(prev ?? []);
      if (next.has(result)) next.delete(result);
      else next.add(result);
      return next;
    });
  }, []);

  function handleUploadSuccess(result: TranscriptUploadResult) {
    void result;
    setRefreshKey((k) => k + 1);
  }

  return (
    <>
      <Header title="Sales Calls" />

      <main className="flex-1 overflow-y-auto p-7 space-y-6">
        {/* Heading + Analytics button */}
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-xl font-bold text-gray-900">Sales Calls</h1>
            <p className="text-sm text-gray-500 mt-0.5">
              Submit a recording — AI transcribes and extracts pain points + content ideas automatically.
            </p>
          </div>
          <button
            type="button"
            onClick={() => router.push("/sales-calls/analytics")}
            className="flex-shrink-0 inline-flex items-center gap-1.5 rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm font-semibold text-gray-700 hover:bg-gray-50 transition-colors"
          >
            📊 Analytics
          </button>
        </div>

        {/* Upload widget */}
        <TranscriptUploadWidget callType="Sales" onSuccess={handleUploadSuccess} />

        {/* KPI cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <KpiCard
            label="Total Calls"
            value={isLoading ? "—" : String(stats?.total_calls ?? 0)}
            borderColor="#3B82F6"
            sub="Analyzed all time"
          />
          <KpiCard
            label="This Month"
            value={isLoading ? "—" : String(stats?.calls_this_month ?? 0)}
            borderColor="#F59E0B"
            badge={stats && stats.this_month_delta !== 0 ? `↑ ${Math.abs(stats.this_month_delta)}` : undefined}
            badgeVariant={stats && stats.this_month_delta >= 0 ? "up" : "down"}
          />
          <KpiCard
            label="Pain Points Found"
            value={isLoading ? "—" : String(stats?.pain_points_found ?? 0)}
            borderColor="#F97316"
            sub="Across all calls"
          />
          <KpiCard
            label="Content Ideas"
            value={isLoading ? "—" : String(stats?.content_ideas ?? 0)}
            borderColor="#10B981"
            sub="Auto-generated"
          />
        </div>

        {/* Analyzed calls */}
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm">
          <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between gap-3">
            <h2 className="text-sm font-bold text-gray-900">Analyzed Calls</h2>
            <span className="text-xs text-gray-400">Most recent first</span>
          </div>
          {/* Filter strip — search + rep + date range in one wrapping row, matching
              the Appointments page's filter band. */}
          <div className="px-5 py-3 border-b border-gray-100 bg-gray-50/50 space-y-2.5">
            <div className="flex items-center gap-2.5 flex-wrap">
              <div className="relative flex-1 min-w-[220px] max-w-sm">
                <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 text-sm">🔍</span>
                <input
                  type="text"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Search by lead, rep, or call id…"
                  className="w-full rounded-lg border border-gray-200 bg-white pl-9 pr-8 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-400"
                />
                {search && (
                  <button
                    type="button"
                    onClick={() => setSearch("")}
                    aria-label="Clear search"
                    className="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 text-sm"
                  >
                    ✕
                  </button>
                )}
              </div>
              <select
                value={repFilter}
                onChange={(e) => setRepFilter(e.target.value)}
                className="px-2.5 py-1.5 text-sm border border-gray-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20 text-gray-600"
              >
                <option value="all">All Reps</option>
                {reps.map((r) => (
                  <option key={r.rep_id} value={r.rep_id}>
                    {r.full_name}
                  </option>
                ))}
              </select>
              <div className="flex items-center gap-1.5">
                <input
                  type="date"
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                  aria-label="Start date"
                  className="px-2.5 py-1.5 text-sm border border-gray-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20 text-gray-600"
                />
                <span className="text-xs text-gray-400">to</span>
                <input
                  type="date"
                  value={endDate}
                  onChange={(e) => setEndDate(e.target.value)}
                  aria-label="End date"
                  className="px-2.5 py-1.5 text-sm border border-gray-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20 text-gray-600"
                />
              </div>
              <AnalyzeViewButton onClick={openAnalyze} />
            </div>
            {/* Multi-select result filter — all on except "No Show" by default. */}
            {resultOptions.length > 0 && selectedResults && (
              <div className="flex flex-wrap items-center gap-1.5">
                <span className="text-[11px] font-semibold uppercase tracking-wide text-gray-400 mr-1">
                  Result
                </span>
                {resultOptions.map((result) => {
                  const active = selectedResults.has(result);
                  return (
                    <button
                      key={result}
                      type="button"
                      onClick={() => toggleResult(result)}
                      aria-pressed={active}
                      className={`rounded-full px-2.5 py-1 text-[12px] font-medium border transition-colors ${
                        active
                          ? "bg-accent-50 border-accent-300 text-accent-700"
                          : "bg-white border-gray-200 text-gray-400 hover:border-gray-300"
                      }`}
                    >
                      {result}
                    </button>
                  );
                })}
              </div>
            )}
          </div>
          <div className="p-4 space-y-3">
            {isLoading ? (
              <p className="text-sm text-gray-400">Loading calls…</p>
            ) : calls.length === 0 ? (
              <p className="text-sm text-gray-400 italic">
                {selectedResults && selectedResults.size === 0
                  ? "No results selected — pick a result chip above to show calls."
                  : debouncedSearch
                    ? `No calls match "${debouncedSearch}".`
                    : "No calls match the selected results."}
              </p>
            ) : (
              calls.map((call) => (
                <CallCard key={call.call_id} call={call} onChanged={() => void load()} />
              ))
            )}
          </div>
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
      </main>

      <AnalyzeViewDrawer
        surface="sales_calls"
        params={analyzeParams}
        open={analyzeOpen}
        onClose={() => setAnalyzeOpen(false)}
      />
    </>
  );
}
