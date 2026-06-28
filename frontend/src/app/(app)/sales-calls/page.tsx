"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Header } from "@/components/layout/header";
import { TranscriptUploadWidget } from "@/components/upload/transcript-upload-widget";
import type { TranscriptUploadResult } from "@/components/upload/transcript-upload-widget";
import { KpiCard } from "@/components/ui/kpi-card";
import { Pagination } from "@/components/ui";
import { apiClient } from "@/lib/api-client";
import { useAuth } from "@/hooks/use-auth";
import { usePagination } from "@/hooks/use-pagination";

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
  call_owner: string | null;
  processed_date: string | null;
  insights_count: number;
  pain_points_count: number;
  content_ideas_count: number;
  duration_minutes: number | null;
  transcript_excerpt: string | null;
  source: string | null;
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

// Map the real call_result values to colored status pills. Unknown values fall
// back to a neutral gray pill rather than breaking.
const RESULT_STYLE: { match: (r: string) => boolean; classes: string; dot: string }[] = [
  { match: (r) => /booked|won|sale|sold/.test(r), classes: "bg-emerald-50 text-emerald-700", dot: "bg-emerald-500" },
  { match: (r) => /follow.?up|scheduled/.test(r), classes: "bg-violet-50 text-violet-700", dot: "bg-violet-500" },
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

function CallCard({ call }: { call: CallSummary }) {
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
  const title = `${call.call_owner ?? "Unknown"}${call.call_type ? ` — ${call.call_type} Call` : ""}`;
  const meta = [formatDate(call.date), call.duration_minutes ? `${Math.round(call.duration_minutes)} min` : null, call.source === "wgr" ? "WGR" : "CI"]
    .filter(Boolean)
    .join(" · ");

  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
      {/* Header — clickable to expand */}
      <button
        type="button"
        onClick={() => void toggle()}
        aria-expanded={open}
        className="w-full flex items-center gap-3 px-5 py-4 text-left hover:bg-gray-50 transition-colors"
      >
        <span className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full bg-accent-100 text-accent-700 text-sm font-bold">
          {initials(call.call_owner)}
        </span>
        <div className="min-w-0 flex-1">
          <div className="text-sm font-bold text-gray-900 truncate">{title}</div>
          <div className="text-[12px] text-gray-500">{meta}</div>
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

  const { page, pageSize, setPage, setPageSize, resetToFirstPage } =
    usePagination("sales-calls");

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
  }, [selectedResults, resultOptions.length, page, pageSize]);

  useEffect(() => {
    if (authLoading || selectedResults === null) return;
    void load();
  }, [authLoading, load, refreshKey, selectedResults]);

  // Changing the result filter narrows the set — jump back to page 1.
  useEffect(() => {
    resetToFirstPage();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedResults]);

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
          <div className="px-5 py-4 border-b border-gray-100 space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-bold text-gray-900">Analyzed Calls</h2>
              <span className="text-xs text-gray-400">Most recent first</span>
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
                  : "No calls match the selected results."}
              </p>
            ) : (
              calls.map((call) => <CallCard key={call.call_id} call={call} />)
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
    </>
  );
}
