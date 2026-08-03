"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Header } from "@/components/layout/header";
import { apiClient } from "@/lib/api-client";
import { useAuth } from "@/hooks/use-auth";
import { Skeleton } from "@/components/ui/skeleton";
import { KpiCard, KpiRow } from "@/components/ui/kpi-card";
import { Card, CardHeader, CardBody } from "@/components/ui/card";
import { ScoreBar } from "@/components/ui/score-bar";
import { FilterBar } from "@/components/ui/filter-bar";
import { FormSelect } from "@/components/ui/form-field";

// ─── API response types ───────────────────────────────────────────────────────

interface CampaignRow {
  id: string;
  name: string;
  subject: string | null;
  campaign_type: string | null;
  status: string;
  sent_at: string | null;
  audience_name: string | null;
  recipients_count: number;
  open_count: number;
  click_count: number;
  unsubscribe_count: number;
  bounce_count: number;
  open_rate: number | null;
  click_rate: number | null;
  archive_url: string | null;
}

interface CampaignsSummary {
  count: number;
  total_recipients: number;
  total_opens: number;
  total_clicks: number;
  avg_open_rate: number;
  avg_click_rate: number;
}

interface FilterOptions {
  campaign_types: string[];
  statuses: string[];
}

interface CampaignsResponse {
  campaigns: CampaignRow[];
  summary: CampaignsSummary;
  filter_options: FilterOptions;
}

const EMPTY_DATA: CampaignsResponse = {
  campaigns: [],
  summary: {
    count: 0,
    total_recipients: 0,
    total_opens: 0,
    total_clicks: 0,
    avg_open_rate: 0,
    avg_click_rate: 0,
  },
  filter_options: { campaign_types: [], statuses: [] },
};

// ─── Sort metric options — the "campaign metric filters" ask ─────────────────

type SortMetric =
  | "sent_at"
  | "recipients_count"
  | "open_count"
  | "click_count"
  | "open_rate"
  | "click_rate"
  | "unsubscribe_count"
  | "bounce_count";
type SortDir = "asc" | "desc";

const SORT_METRIC_LABELS: Record<SortMetric, string> = {
  sent_at: "Date sent",
  recipients_count: "Sent (recipients)",
  open_count: "Opens",
  click_count: "Clicks",
  open_rate: "Open rate",
  click_rate: "Click rate",
  unsubscribe_count: "Unsubscribes",
  bounce_count: "Bounces",
};

// ─── Helpers ──────────────────────────────────────────────────────────────────

function formatPercent(value: number | null): string {
  if (value === null || value === undefined) return "—";
  return `${value.toFixed(1)}%`;
}

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

function formatNumber(n: number): string {
  return n.toLocaleString("en-US");
}

/** Tercile tier (Top / Mid / Low) of `value` among `all` values, higher = better. */
function tierOf(value: number | null, all: number[]): "Top" | "Mid" | "Low" | null {
  if (value === null || all.length === 0) return null;
  const sorted = [...all].sort((a, b) => a - b);
  const rank = sorted.filter((v) => v <= value).length / sorted.length;
  if (rank > 2 / 3) return "Top";
  if (rank > 1 / 3) return "Mid";
  return "Low";
}

const TIER_STYLES: Record<"Top" | "Mid" | "Low", string> = {
  Top: "bg-emerald-50 text-emerald-700 border-emerald-200",
  Mid: "bg-amber-50 text-amber-700 border-amber-200",
  Low: "bg-gray-100 text-gray-500 border-gray-200",
};

function TierChip({ tier }: { tier: "Top" | "Mid" | "Low" | null }) {
  if (!tier) {
    return (
      <span className="text-[10px] font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded bg-gray-100 text-gray-400 border border-gray-200">
        —
      </span>
    );
  }
  return (
    <span
      className={`text-[10px] font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded border ${TIER_STYLES[tier]}`}
    >
      {tier}
    </span>
  );
}

// ─── Sortable column header ───────────────────────────────────────────────────

function SortableHeader({
  label,
  column,
  sortBy,
  sortDir,
  onSort,
  align = "left",
}: {
  label: string;
  column: SortMetric;
  sortBy: SortMetric;
  sortDir: SortDir;
  onSort: (col: SortMetric) => void;
  align?: "left" | "right";
}) {
  const active = sortBy === column;
  return (
    <th
      className={`px-4 py-2.5 text-[10px] font-bold uppercase tracking-widest text-gray-400 ${
        align === "right" ? "text-right" : "text-left"
      }`}
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

// ─── Top campaigns ranking card ───────────────────────────────────────────────

function TopCampaignsCard({
  campaigns,
  metric,
  maxMetricValue,
}: {
  campaigns: CampaignRow[];
  metric: SortMetric;
  maxMetricValue: number;
}) {
  const metricValue = (c: CampaignRow): number => {
    switch (metric) {
      case "sent_at":
        return c.sent_at ? new Date(c.sent_at).getTime() : 0;
      case "recipients_count":
        return c.recipients_count;
      case "open_count":
        return c.open_count;
      case "click_count":
        return c.click_count;
      case "open_rate":
        return c.open_rate ?? 0;
      case "click_rate":
        return c.click_rate ?? 0;
      case "unsubscribe_count":
        return c.unsubscribe_count;
      case "bounce_count":
        return c.bounce_count;
      default:
        return 0;
    }
  };

  const formatMetric = (c: CampaignRow): string => {
    switch (metric) {
      case "sent_at":
        return formatDate(c.sent_at);
      case "open_rate":
        return formatPercent(c.open_rate);
      case "click_rate":
        return formatPercent(c.click_rate);
      default:
        return formatNumber(metricValue(c));
    }
  };

  const top5 = [...campaigns]
    .sort((a, b) => metricValue(b) - metricValue(a))
    .slice(0, 5);

  return (
    <Card>
      <CardHeader
        title="Top campaigns"
        action={
          <span className="text-xs text-gray-400">
            by {SORT_METRIC_LABELS[metric].toLowerCase()}
          </span>
        }
      />
      <CardBody noPadding>
        {top5.length === 0 ? (
          <div className="px-5 py-8 text-center text-xs text-gray-400">
            No campaigns in this range.
          </div>
        ) : (
          <div className="divide-y divide-gray-100">
            {top5.map((c, i) => {
              const v = metricValue(c);
              const pct = maxMetricValue > 0 ? Math.round((v / maxMetricValue) * 100) : 0;
              return (
                <div key={c.id} className="px-5 py-3 flex items-center gap-3">
                  <span className="text-sm font-bold text-gray-300 w-5 shrink-0 tabular-nums">
                    {i + 1}
                  </span>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-900 truncate" title={c.name}>
                      {c.name}
                    </p>
                    <div className="mt-1">
                      <ScoreBar value={pct} showValue={false} color="brand" />
                    </div>
                  </div>
                  <span className="text-sm font-semibold text-gray-900 tabular-nums shrink-0">
                    {formatMetric(c)}
                  </span>
                </div>
              );
            })}
          </div>
        )}
      </CardBody>
    </Card>
  );
}

// ─── Campaign row ─────────────────────────────────────────────────────────────

function CampaignTableRow({
  c,
  maxOpenRate,
  tier,
}: {
  c: CampaignRow;
  maxOpenRate: number;
  tier: "Top" | "Mid" | "Low" | null;
}) {
  const barValue =
    c.open_rate !== null && maxOpenRate > 0
      ? Math.round((c.open_rate / maxOpenRate) * 100)
      : 0;

  return (
    <tr className="border-b border-gray-100 last:border-0 hover:bg-gray-50/60 transition-colors">
      <td className="px-4 py-3">
        <p className="text-sm font-medium text-gray-900 truncate max-w-[280px]" title={c.name}>
          {c.name}
        </p>
        <p className="text-xs text-gray-500 truncate max-w-[280px]" title={c.subject ?? undefined}>
          {c.subject ?? "(no subject)"}
        </p>
      </td>
      <td className="px-4 py-3 text-xs text-gray-600">{c.campaign_type ?? "—"}</td>
      <td className="px-4 py-3 text-xs text-gray-600 whitespace-nowrap">{formatDate(c.sent_at)}</td>
      <td className="px-4 py-3 text-right text-sm text-gray-900 tabular-nums">
        {formatNumber(c.recipients_count)}
      </td>
      <td className="px-4 py-3 text-right text-sm text-gray-900 tabular-nums">
        {formatNumber(c.open_count)}
        <span className="block text-[11px] text-gray-400">{formatPercent(c.open_rate)}</span>
      </td>
      <td className="px-4 py-3 text-right text-sm text-gray-900 tabular-nums">
        {formatNumber(c.click_count)}
        <span className="block text-[11px] text-gray-400">{formatPercent(c.click_rate)}</span>
      </td>
      <td className="px-4 py-3 text-right text-sm text-gray-600 tabular-nums">
        {formatNumber(c.unsubscribe_count)}
      </td>
      <td className="px-4 py-3 text-right text-sm text-gray-600 tabular-nums">
        {formatNumber(c.bounce_count)}
      </td>
      <td className="px-4 py-3 min-w-[140px]">
        <div className="flex items-center gap-2">
          <div className="flex-1">
            <ScoreBar value={barValue} showValue={false} color="brand" />
          </div>
          <TierChip tier={tier} />
        </div>
      </td>
    </tr>
  );
}

// ─── Empty state ──────────────────────────────────────────────────────────────

function CampaignsEmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-16 gap-3">
      <span className="text-4xl" aria-hidden="true">
        📬
      </span>
      <p className="text-sm font-medium text-gray-500">No campaigns match these filters.</p>
      <p className="text-xs text-gray-400">Try widening the date range or clearing a filter.</p>
    </div>
  );
}

// ─── Loading skeleton ─────────────────────────────────────────────────────────

function EmailPageSkeleton() {
  return (
    <main className="flex-1 overflow-y-auto p-7 space-y-6">
      <div>
        <Skeleton className="h-6 w-44" />
        <Skeleton className="h-4 w-80 mt-2" />
      </div>
      <div className="grid grid-cols-4 gap-4">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="bg-white rounded-xl border border-gray-200 shadow-sm p-5 flex flex-col gap-2">
            <Skeleton className="h-3 w-24" />
            <Skeleton className="h-7 w-16" />
          </div>
        ))}
      </div>
      <Skeleton className="h-12 rounded-xl" />
      <div className="grid grid-cols-3 gap-4">
        <Skeleton className="h-64 rounded-xl col-span-1" />
        <div className="col-span-2 bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
          <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
            <Skeleton className="h-4 w-36" />
            <Skeleton className="h-3 w-24" />
          </div>
          <div className="flex flex-col items-center justify-center py-16 gap-3">
            <Skeleton className="w-10 h-10 rounded-full" />
            <Skeleton className="h-4 w-32" />
            <Skeleton className="h-3 w-60" />
          </div>
        </div>
      </div>
    </main>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function EmailPage() {
  const { isLoading: authLoading } = useAuth();
  const [data, setData] = useState<CampaignsResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Filters
  const [search, setSearch] = useState("");
  const [sentFrom, setSentFrom] = useState("");
  const [sentTo, setSentTo] = useState("");
  const [campaignType, setCampaignType] = useState("all");
  const [status, setStatus] = useState("all");
  const [sortBy, setSortBy] = useState<SortMetric>("sent_at");
  const [sortDir, setSortDir] = useState<SortDir>("desc");

  const searchDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const handleSort = (col: SortMetric) => {
    if (col === sortBy) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortBy(col);
      setSortDir("desc");
    }
  };

  useEffect(() => {
    if (authLoading) return;

    if (searchDebounceRef.current !== null) {
      clearTimeout(searchDebounceRef.current);
    }

    const doFetch = () => {
      let cancelled = false;

      async function fetchCampaigns(): Promise<void> {
        const params = new URLSearchParams();
        if (search) params.set("search", search);
        if (sentFrom) params.set("sent_from", sentFrom);
        if (sentTo) params.set("sent_to", sentTo);
        if (campaignType !== "all") params.set("campaign_type", campaignType);
        if (status !== "all") params.set("status", status);
        params.set("sort_by", sortBy);
        params.set("sort_dir", sortDir);

        try {
          const result = await apiClient.get<CampaignsResponse>(
            `/email/campaigns?${params.toString()}`,
            { silent: true },
          );
          if (!cancelled) setData(result);
        } catch {
          // On error, data stays as previous snapshot.
        } finally {
          if (!cancelled) setIsLoading(false);
        }
      }

      void fetchCampaigns();

      return () => {
        cancelled = true;
      };
    };

    if (search) {
      searchDebounceRef.current = setTimeout(doFetch, 300);
    } else {
      doFetch();
    }

    return () => {
      if (searchDebounceRef.current !== null) clearTimeout(searchDebounceRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authLoading, search, sentFrom, sentTo, campaignType, status, sortBy, sortDir]);

  const campaigns = useMemo(() => data?.campaigns ?? [], [data]);
  const filterOptions = data?.filter_options ?? EMPTY_DATA.filter_options;
  const summary = data?.summary ?? EMPTY_DATA.summary;

  const maxOpenRate = useMemo(
    () => Math.max(0, ...campaigns.map((c) => c.open_rate ?? 0)),
    [campaigns],
  );
  const openRates = useMemo(
    () => campaigns.map((c) => c.open_rate ?? 0),
    [campaigns],
  );
  const maxSortMetricValue = useMemo(() => {
    const val = (c: CampaignRow): number => {
      switch (sortBy) {
        case "sent_at":
          return c.sent_at ? new Date(c.sent_at).getTime() : 0;
        case "recipients_count":
          return c.recipients_count;
        case "open_count":
          return c.open_count;
        case "click_count":
          return c.click_count;
        case "open_rate":
          return c.open_rate ?? 0;
        case "click_rate":
          return c.click_rate ?? 0;
        case "unsubscribe_count":
          return c.unsubscribe_count;
        case "bounce_count":
          return c.bounce_count;
        default:
          return 0;
      }
    };
    return Math.max(0, ...campaigns.map(val));
  }, [campaigns, sortBy]);

  const hasFilters =
    !!search || !!sentFrom || !!sentTo || campaignType !== "all" || status !== "all";

  function clearFilters() {
    setSearch("");
    setSentFrom("");
    setSentTo("");
    setCampaignType("all");
    setStatus("all");
  }

  if (isLoading && !data) {
    return (
      <>
        <Header title="Email" />
        <EmailPageSkeleton />
      </>
    );
  }

  return (
    <>
      <Header title="Email" />

      <main className="flex-1 overflow-y-auto p-7 space-y-6">
        {/* Page heading */}
        <div>
          <h1 className="text-xl font-bold text-gray-900">Email Campaigns</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Subscriber performance and campaign results across all email sends.
          </p>
        </div>

        {/* Row 1: KPI tiles — scoped to the current filtered set */}
        <section aria-label="Email KPIs">
          <KpiRow>
            <KpiCard label="Campaigns" value={formatNumber(summary.count)} borderColor="#10B981" />
            <KpiCard
              label="Avg Open Rate"
              value={`${summary.avg_open_rate.toFixed(1)}%`}
              borderColor="#10B981"
            />
            <KpiCard
              label="Avg Click Rate"
              value={`${summary.avg_click_rate.toFixed(1)}%`}
              borderColor="#10B981"
            />
            <KpiCard
              label="Total Recipients"
              value={formatNumber(summary.total_recipients)}
              borderColor="#10B981"
            />
          </KpiRow>
        </section>

        {/* Row 2: Filters */}
        <FilterBar>
          <input
            type="text"
            placeholder="Search name or subject…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="px-2.5 py-1.5 text-sm border border-gray-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-400 text-gray-600 min-w-[200px]"
          />

          <FormSelect
            aria-label="Campaign type"
            value={campaignType}
            onChange={(e) => setCampaignType(e.target.value)}
          >
            <option value="all">All types</option>
            {filterOptions.campaign_types.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </FormSelect>

          <FormSelect aria-label="Status" value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="all">All statuses</option>
            {filterOptions.statuses.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </FormSelect>

          <div className="flex items-center gap-1.5 text-gray-500">
            <span className="text-[11px] font-semibold uppercase tracking-wide shrink-0">Sent</span>
            <input
              type="date"
              aria-label="Sent on or after"
              value={sentFrom}
              max={sentTo || undefined}
              onChange={(e) => setSentFrom(e.target.value)}
              className="px-2 py-1.5 text-sm border border-gray-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-400 text-gray-600"
            />
            <span className="text-gray-300">–</span>
            <input
              type="date"
              aria-label="Sent on or before"
              value={sentTo}
              min={sentFrom || undefined}
              onChange={(e) => setSentTo(e.target.value)}
              className="px-2 py-1.5 text-sm border border-gray-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-400 text-gray-600"
            />
          </div>

          <div className="flex items-center gap-1.5 text-gray-500">
            <span className="text-[11px] font-semibold uppercase tracking-wide shrink-0">Sort by</span>
            <FormSelect
              aria-label="Sort by metric"
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as SortMetric)}
            >
              {(Object.keys(SORT_METRIC_LABELS) as SortMetric[]).map((m) => (
                <option key={m} value={m}>
                  {SORT_METRIC_LABELS[m]}
                </option>
              ))}
            </FormSelect>
          </div>

          {hasFilters && (
            <button
              type="button"
              onClick={clearFilters}
              className="px-2.5 py-1.5 text-sm text-gray-500 hover:text-gray-700 border border-gray-200 rounded-lg bg-white hover:bg-gray-50 transition-colors"
            >
              Clear filters
            </button>
          )}
        </FilterBar>

        {/* Row 3: Ranking + table */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="lg:col-span-1">
            <TopCampaignsCard
              campaigns={campaigns}
              metric={sortBy}
              maxMetricValue={maxSortMetricValue}
            />
          </div>

          <div className="lg:col-span-2">
            <Card>
              <CardHeader
                title="Campaigns"
                action={<span className="text-xs text-gray-400">{campaigns.length} shown</span>}
              />
              <CardBody noPadding>
                {campaigns.length === 0 ? (
                  <CampaignsEmptyState />
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full">
                      <thead>
                        <tr className="border-b border-gray-100">
                          <th className="px-4 py-2.5 text-left text-[10px] font-bold uppercase tracking-widest text-gray-400">
                            Campaign
                          </th>
                          <th className="px-4 py-2.5 text-left text-[10px] font-bold uppercase tracking-widest text-gray-400">
                            Type
                          </th>
                          <SortableHeader
                            label="Sent"
                            column="sent_at"
                            sortBy={sortBy}
                            sortDir={sortDir}
                            onSort={handleSort}
                          />
                          <SortableHeader
                            label="Recipients"
                            column="recipients_count"
                            sortBy={sortBy}
                            sortDir={sortDir}
                            onSort={handleSort}
                            align="right"
                          />
                          <SortableHeader
                            label="Opens"
                            column="open_count"
                            sortBy={sortBy}
                            sortDir={sortDir}
                            onSort={handleSort}
                            align="right"
                          />
                          <SortableHeader
                            label="Clicks"
                            column="click_count"
                            sortBy={sortBy}
                            sortDir={sortDir}
                            onSort={handleSort}
                            align="right"
                          />
                          <SortableHeader
                            label="Unsubs"
                            column="unsubscribe_count"
                            sortBy={sortBy}
                            sortDir={sortDir}
                            onSort={handleSort}
                            align="right"
                          />
                          <SortableHeader
                            label="Bounces"
                            column="bounce_count"
                            sortBy={sortBy}
                            sortDir={sortDir}
                            onSort={handleSort}
                            align="right"
                          />
                          <th className="px-4 py-2.5 text-left text-[10px] font-bold uppercase tracking-widest text-gray-400">
                            Performance
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {campaigns.map((c) => (
                          <CampaignTableRow
                            key={c.id}
                            c={c}
                            maxOpenRate={maxOpenRate}
                            tier={tierOf(c.open_rate, openRates)}
                          />
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </CardBody>
            </Card>
          </div>
        </div>
      </main>
    </>
  );
}
