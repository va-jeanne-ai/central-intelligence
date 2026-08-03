"use client";

/**
 * Social Media page — rebuilt 1:1 from Greg's own tracking page
 * (central-intelligence-greg/index.html, view-mkt-social — deliverable 1).
 *
 * Section order mirrors his page exactly:
 *   1. Filter bar (date range + type)
 *   2. Summary stat cards (Posts in Range, Reels, Carousels, Watch Time,
 *      Total Views, Total Reach, Total Likes, Total Saves, per-keyword lead
 *      cards, Total Leads)
 *   3. Leads by Day table (comment-arrival frame — any post, any platform)
 *   4. Posts table (sortable columns, type badges, per-keyword lead columns)
 *
 * What's NOT mirrored (documented gaps — see FEATURE-VERIFICATION.md):
 * his page's "Connect & Load" / "Refresh" controls talk directly to a live
 * Instagram Graph API connection — there is no live scrape state in either
 * database to mirror, so those controls are omitted rather than faked.
 * Skip Rate / Follows (reel-only Graph API insights) and true total watch
 * time aren't in the instagram_posts mirror either — surfaced via the
 * backend's `gaps` array, rendered in the page's gap notice.
 *
 * Design language: CI's light-mode atoms (Card/KpiCard/FilterBar/Pagination)
 * per the project's "mirror the WHAT, not the dark-theme HOW" convention —
 * same sections, same metrics, same structure/ordering as his page.
 */

import { useEffect, useMemo, useState } from "react";
import { Header } from "@/components/layout/header";
import { apiClient } from "@/lib/api-client";
import { useAuth } from "@/hooks/use-auth";
import { Skeleton } from "@/components/ui/skeleton";
import { KpiCard, KpiRow } from "@/components/ui/kpi-card";
import { Card, CardHeader, CardBody } from "@/components/ui/card";
import { FilterBar } from "@/components/ui/filter-bar";
import { EmptyState } from "@/components/ui/empty-state";
import { Pagination, DEFAULT_PAGE_SIZE } from "@/components/ui/pagination";
import type { SocialOverviewResponse, SocialOverviewPost } from "@/types";

// ─── Formatting helpers ───────────────────────────────────────────────────

function fmtNum(value: number | null | undefined): string {
  return value != null ? value.toLocaleString("en-US") : "—";
}

function fmtMs(seconds: number | null | undefined): string {
  if (seconds == null) return "—";
  const total = Math.round(seconds);
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
}

function fmtDate(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

function fmtPct(value: number | null | undefined): string {
  return value != null ? `${value.toFixed(1)}%` : "—";
}

function kwLabel(kw: string): string {
  return kw.charAt(0).toUpperCase() + kw.slice(1);
}

function typeBadge(post: SocialOverviewPost): { label: string; classes: string } {
  if (post.is_reel) return { label: "Reel", classes: "bg-pink-50 text-pink-700 border-pink-200" };
  const mt = (post.media_type || "").toUpperCase();
  if (mt === "CAROUSEL_ALBUM") return { label: "Carousel", classes: "bg-blue-50 text-blue-700 border-blue-200" };
  if (mt === "VIDEO") return { label: "Video", classes: "bg-purple-50 text-purple-700 border-purple-200" };
  return { label: "Photo", classes: "bg-gray-100 text-gray-600 border-gray-200" };
}

// ─── Sortable column config (mirrors igTh()/igSortBy() column set) ────────

type SortCol =
  | "timestamp" | "likes_count" | "comments_count" | "views" | "avg_watch_time_sec"
  | "reach" | "saves_count" | "shares_count" | "engagement_rate";

// ─── Filter bar ────────────────────────────────────────────────────────────

const TYPE_OPTIONS = [
  { value: "", label: "All" },
  { value: "REELS", label: "Reels" },
  { value: "IMAGE", label: "Photos" },
  { value: "VIDEO", label: "Videos" },
  { value: "CAROUSEL_ALBUM", label: "Carousels" },
];

function SocialFilterBar({
  dateFrom, dateTo, mediaType, onChange,
}: {
  dateFrom: string;
  dateTo: string;
  mediaType: string;
  onChange: (next: { dateFrom?: string; dateTo?: string; mediaType?: string }) => void;
}) {
  return (
    <FilterBar>
      <label className="text-xs font-medium text-gray-500">From</label>
      <input
        type="date"
        value={dateFrom}
        onChange={(e) => onChange({ dateFrom: e.target.value })}
        className="rounded-md border border-gray-200 bg-white px-2 py-1.5 text-sm text-gray-700 focus:border-emerald-400 focus:outline-none focus:ring-1 focus:ring-emerald-400"
      />
      <label className="text-xs font-medium text-gray-500">To</label>
      <input
        type="date"
        value={dateTo}
        onChange={(e) => onChange({ dateTo: e.target.value })}
        className="rounded-md border border-gray-200 bg-white px-2 py-1.5 text-sm text-gray-700 focus:border-emerald-400 focus:outline-none focus:ring-1 focus:ring-emerald-400"
      />
      <label className="text-xs font-medium text-gray-500">Type</label>
      <select
        value={mediaType}
        onChange={(e) => onChange({ mediaType: e.target.value })}
        className="rounded-md border border-gray-200 bg-white px-2 py-1.5 text-sm text-gray-700 focus:border-emerald-400 focus:outline-none focus:ring-1 focus:ring-emerald-400"
      >
        {TYPE_OPTIONS.map((opt) => (
          <option key={opt.value} value={opt.value}>{opt.label}</option>
        ))}
      </select>
    </FilterBar>
  );
}

// ─── Gap notice ─────────────────────────────────────────────────────────────

function GapNotice({ gaps }: { gaps: string[] }) {
  if (gaps.length === 0) return null;
  return (
    <details className="bg-amber-50 border border-amber-200 rounded-xl px-4 py-3 text-xs text-amber-800">
      <summary className="font-semibold cursor-pointer select-none">
        {gaps.length} documented gap{gaps.length !== 1 ? "s" : ""} vs. the live Instagram-connected tracker
      </summary>
      <ul className="mt-2 space-y-1.5 list-disc list-inside">
        {gaps.map((g) => (
          <li key={g}>{g}</li>
        ))}
      </ul>
    </details>
  );
}

// ─── Leads by Day table ─────────────────────────────────────────────────────

function LeadsByDayCard({ data }: { data: SocialOverviewResponse | null }) {
  const rows = data?.leads_by_day ?? [];
  const keywords = data?.keywords ?? [];

  return (
    <Card>
      <CardHeader
        title="Leads by Day"
        action={<span className="text-xs text-gray-400">comment-arrival date · any post, any platform</span>}
      />
      <CardBody noPadding>
        {rows.length === 0 ? (
          <EmptyState
            icon="📅"
            title="No lead activity in this range."
            description="Leads by day tracks comments matching a configured keyword."
          />
        ) : (
          <div className="overflow-x-auto max-h-80 overflow-y-auto">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-white">
                <tr className="border-b border-gray-100">
                  <th className="text-left font-semibold text-gray-500 text-[11px] uppercase tracking-wider px-5 py-2">Day</th>
                  {keywords.map((kw) => (
                    <th key={kw} className="text-right font-semibold text-gray-500 text-[11px] uppercase tracking-wider px-3 py-2">
                      {kwLabel(kw)}
                    </th>
                  ))}
                  <th className="text-right font-semibold text-gray-500 text-[11px] uppercase tracking-wider px-5 py-2">Total</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {rows.map((row) => (
                  <tr key={row.day} className="hover:bg-gray-50">
                    <td className="px-5 py-2 text-gray-700">{fmtDate(row.day)}</td>
                    {keywords.map((kw) => (
                      <td key={kw} className="px-3 py-2 text-right tabular-nums text-gray-600">
                        {fmtNum(row.per_keyword[kw] ?? 0)}
                      </td>
                    ))}
                    <td className="px-5 py-2 text-right tabular-nums font-semibold text-gray-900">
                      {fmtNum(row.total)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardBody>
    </Card>
  );
}

// ─── Posts table ─────────────────────────────────────────────────────────────

function PostsTable({
  data, sortCol, sortDir, onSort,
}: {
  data: SocialOverviewResponse | null;
  sortCol: SortCol;
  sortDir: "asc" | "desc";
  onSort: (col: SortCol) => void;
}) {
  const posts = data?.posts ?? [];
  const keywords = data?.keywords ?? [];

  if (posts.length === 0) {
    return (
      <EmptyState
        icon="📱"
        title="No posts match this filter."
        description="Adjust the date range or type filter."
      />
    );
  }

  const th = (col: SortCol, label: string, alignRight = true) => {
    const active = sortCol === col;
    const arrow = active ? (sortDir === "desc" ? " ↓" : " ↑") : "";
    return (
      <th
        onClick={() => onSort(col)}
        className={`font-semibold text-[11px] uppercase tracking-wider px-3 py-2 cursor-pointer select-none whitespace-nowrap ${
          alignRight ? "text-right" : "text-left"
        } ${active ? "text-emerald-700" : "text-gray-500"}`}
      >
        {label}{arrow}
      </th>
    );
  };

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-100">
            <th className="text-left font-semibold text-gray-500 text-[11px] uppercase tracking-wider px-5 py-2">Type</th>
            <th className="text-left font-semibold text-gray-500 text-[11px] uppercase tracking-wider px-3 py-2">Caption</th>
            {th("timestamp", "Date", false)}
            {th("likes_count", "Likes")}
            {th("comments_count", "Comments")}
            {keywords.map((kw) => (
              <th key={kw} className="text-right font-semibold text-gray-500 text-[11px] uppercase tracking-wider px-3 py-2 whitespace-nowrap">
                {kwLabel(kw)}
              </th>
            ))}
            {th("views", "Views")}
            {th("reach", "Reach")}
            {th("saves_count", "Saves")}
            {th("shares_count", "Shares")}
            {th("avg_watch_time_sec", "Avg Watch")}
            {th("engagement_rate", "Eng. Rate")}
            <th className="px-5 py-2" />
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {posts.map((p) => {
            const badge = typeBadge(p);
            const isReel = p.is_reel;
            return (
              <tr key={p.id} className="hover:bg-gray-50">
                <td className="px-5 py-3">
                  <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold border ${badge.classes}`}>
                    {badge.label}
                  </span>
                </td>
                <td className="px-3 py-3 max-w-[220px] truncate text-gray-700" title={p.caption ?? undefined}>
                  {p.caption?.trim() || "—"}
                </td>
                <td className="px-3 py-3 whitespace-nowrap text-gray-500 text-xs">{fmtDate(p.posted_at)}</td>
                <td className="px-3 py-3 text-right tabular-nums text-gray-700">{fmtNum(p.likes_count)}</td>
                <td className="px-3 py-3 text-right tabular-nums text-gray-700">{fmtNum(p.comments_count)}</td>
                {keywords.map((kw) => (
                  <td key={kw} className="px-3 py-3 text-right tabular-nums text-gray-600">
                    {fmtNum(p.lead_counts[kw] ?? 0)}
                  </td>
                ))}
                <td className="px-3 py-3 text-right tabular-nums text-gray-700">
                  {isReel ? fmtNum(p.views) : "—"}
                </td>
                <td className="px-3 py-3 text-right tabular-nums text-gray-700">{fmtNum(p.reach)}</td>
                <td className="px-3 py-3 text-right tabular-nums text-gray-700">{fmtNum(p.saves_count)}</td>
                <td className="px-3 py-3 text-right tabular-nums text-gray-700">
                  {isReel ? fmtNum(p.shares_count) : "—"}
                </td>
                <td className="px-3 py-3 text-right tabular-nums text-gray-700">
                  {isReel ? fmtMs(p.avg_watch_time_sec) : "—"}
                </td>
                <td className="px-3 py-3 text-right tabular-nums font-semibold text-gray-900">
                  {fmtPct(p.engagement_rate)}
                </td>
                <td className="px-5 py-3 text-right">
                  {p.permalink && (
                    <a
                      href={p.permalink}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs font-medium text-emerald-700 hover:text-emerald-800"
                    >
                      View
                    </a>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// ─── Loading skeleton ────────────────────────────────────────────────────────

function SocialPageSkeleton() {
  return (
    <main className="flex-1 overflow-y-auto p-7 space-y-6">
      <div>
        <Skeleton className="h-6 w-40" />
        <Skeleton className="h-4 w-80 mt-2" />
      </div>
      <div className="grid grid-cols-4 gap-4">
        {[1, 2, 3, 4, 5, 6, 7, 8].map((i) => (
          <div key={i} className="bg-white rounded-xl border border-gray-200 shadow-sm p-5 flex flex-col gap-2">
            <Skeleton className="h-3 w-24" />
            <Skeleton className="h-7 w-16" />
          </div>
        ))}
      </div>
      <Skeleton className="h-56 rounded-xl" />
      <Skeleton className="h-96 rounded-xl" />
    </main>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function SocialMediaPage() {
  const { isLoading: authLoading } = useAuth();
  const [data, setData] = useState<SocialOverviewResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [mediaType, setMediaType] = useState("");
  const [sortCol, setSortCol] = useState<SortCol>("timestamp");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE);

  const queryKey = useMemo(
    () => JSON.stringify({ dateFrom, dateTo, mediaType, sortCol, sortDir, page, pageSize }),
    [dateFrom, dateTo, mediaType, sortCol, sortDir, page, pageSize],
  );

  useEffect(() => {
    if (authLoading) return;

    let cancelled = false;

    async function fetchData(): Promise<void> {
      try {
        const params = new URLSearchParams();
        if (dateFrom) params.set("date_from", dateFrom);
        if (dateTo) params.set("date_to", dateTo);
        if (mediaType) params.set("media_type", mediaType);
        params.set("sort_col", sortCol);
        params.set("sort_dir", sortDir);
        params.set("limit", String(pageSize));
        params.set("offset", String((page - 1) * pageSize));

        const result = await apiClient.get<SocialOverviewResponse>(
          `/social/overview?${params.toString()}`,
          { silent: true },
        );
        if (!cancelled) setData(result);
      } catch {
        // On error, data stays null — page renders with "—" fallbacks.
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    }

    void fetchData();
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authLoading, queryKey]);

  function handleFilterChange(next: { dateFrom?: string; dateTo?: string; mediaType?: string }) {
    if (next.dateFrom !== undefined) setDateFrom(next.dateFrom);
    if (next.dateTo !== undefined) setDateTo(next.dateTo);
    if (next.mediaType !== undefined) setMediaType(next.mediaType);
    setPage(1);
  }

  function handleSort(col: SortCol) {
    if (col === sortCol) {
      setSortDir((d) => (d === "desc" ? "asc" : "desc"));
    } else {
      setSortCol(col);
      setSortDir("desc");
    }
    setPage(1);
  }

  if (isLoading) {
    return (
      <>
        <Header title="Social Media" />
        <SocialPageSkeleton />
      </>
    );
  }

  const summary = data?.summary;

  return (
    <>
      <Header title="Social Media" />

      <main className="flex-1 overflow-y-auto p-7 space-y-6">
        {/* Page heading */}
        <div>
          <h1 className="text-xl font-bold text-gray-900">Social Media</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Instagram analytics, post performance, and comment-lead attribution.
          </p>
        </div>

        {data && <GapNotice gaps={data.gaps} />}

        {/* Filter bar */}
        <SocialFilterBar
          dateFrom={dateFrom}
          dateTo={dateTo}
          mediaType={mediaType}
          onChange={handleFilterChange}
        />

        {/* Summary stat cards — mirrors Greg's ig-s-* tiles 1:1 */}
        <section aria-label="Social media summary">
          <KpiRow>
            <KpiCard label="Posts in Range" value={summary ? fmtNum(summary.posts_in_range) : "—"} borderColor="#10B981" />
            <KpiCard label="Reels" value={summary ? fmtNum(summary.reels_count) : "—"} borderColor="#10B981" />
            <KpiCard label="Carousels" value={summary ? fmtNum(summary.carousels_count) : "—"} borderColor="#10B981" />
            <KpiCard
              label="Watch Time"
              value={summary ? fmtMs(summary.total_watch_time_sec) : "—"}
              sub="Reels only (sum of avg watch)"
              borderColor="#10B981"
            />
            <KpiCard label="Total Views" value={summary ? fmtNum(summary.total_views) : "—"} sub="Reels only" borderColor="#10B981" />
            <KpiCard label="Total Reach" value={summary ? fmtNum(summary.total_reach) : "—"} borderColor="#10B981" />
            <KpiCard label="Total Likes" value={summary ? fmtNum(summary.total_likes) : "—"} borderColor="#10B981" />
            <KpiCard label="Total Saves" value={summary ? fmtNum(summary.total_saves) : "—"} borderColor="#10B981" />
          </KpiRow>
        </section>

        {/* Per-keyword lead cards + Total Leads — dynamic, never hardcoded */}
        <section aria-label="Comment-lead totals">
          <KpiRow className="!grid-cols-2 sm:!grid-cols-3 lg:!grid-cols-4">
            {(summary?.keywords ?? []).map((kw) => (
              <KpiCard
                key={kw}
                label={`${kwLabel(kw)} Leads`}
                value={fmtNum(summary?.per_keyword_leads[kw] ?? 0)}
                borderColor="#3B82F6"
              />
            ))}
            <KpiCard label="Total Leads" value={summary ? fmtNum(summary.total_leads) : "—"} borderColor="#3B82F6" />
          </KpiRow>
        </section>

        {/* Leads by Day */}
        <LeadsByDayCard data={data} />

        {/* Posts table */}
        <Card>
          <CardHeader
            title="Posts"
            action={
              <span className="text-xs text-gray-400">
                {data ? `${data.posts_total} post${data.posts_total !== 1 ? "s" : ""}` : "—"}
              </span>
            }
          />
          <PostsTable data={data} sortCol={sortCol} sortDir={sortDir} onSort={handleSort} />
          {data && data.posts_total > 0 && (
            <Pagination
              page={page}
              total={data.posts_total}
              pageSize={pageSize}
              onPageChange={setPage}
              onPageSizeChange={(size) => { setPageSize(size); setPage(1); }}
            />
          )}
        </Card>
      </main>
    </>
  );
}
