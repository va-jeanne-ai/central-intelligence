"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { Header } from "@/components/layout/header";
import { apiClient } from "@/lib/api-client";
import { useAuth } from "@/hooks/use-auth";
import { Skeleton } from "@/components/ui/skeleton";
import { KpiCard, KpiRow } from "@/components/ui/kpi-card";
import { Card, CardHeader } from "@/components/ui/card";
import { formatCurrency } from "@/lib/format";
import type { AdsOverviewResponse, AdsOverviewCampaign, AdsOverviewTopAd } from "@/types";

// ─── Status chip ────────────────────────────────────────────────────────────
// Meta campaign/ad statuses ("Active" / "Paused" / "Draft") don't map cleanly
// onto the shared StatusBadge's fixed variant set, so this page uses a small
// local chip keyed off the raw DB value (case-insensitive).

const STATUS_CHIP_CLASSES: Record<string, string> = {
  active: "bg-emerald-50 text-emerald-700 border-emerald-200",
  paused: "bg-amber-50 text-amber-700 border-amber-200",
  draft: "bg-gray-100 text-gray-500 border-gray-200",
};

function StatusChip({ status }: { status: string | null }) {
  if (!status) {
    return <span className="text-xs text-gray-400">—</span>;
  }
  const key = status.trim().toLowerCase();
  const classes = STATUS_CHIP_CLASSES[key] ?? "bg-gray-100 text-gray-500 border-gray-200";
  return (
    <span
      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-[11px] font-semibold border capitalize ${classes}`}
    >
      {status}
    </span>
  );
}

// ─── KPI status chip (Watch / Scale / Kill) ─────────────────────────────────

const KPI_CHIP_CLASSES: Record<string, string> = {
  scale: "bg-emerald-50 text-emerald-700 border-emerald-200",
  watch: "bg-amber-50 text-amber-700 border-amber-200",
  kill: "bg-red-50 text-red-700 border-red-200",
};

function KpiStatusChip({ status }: { status: string | null }) {
  if (!status) {
    return <span className="text-xs text-gray-400">—</span>;
  }
  const key = status.trim().toLowerCase();
  const classes = KPI_CHIP_CLASSES[key] ?? "bg-gray-100 text-gray-500 border-gray-200";
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold border capitalize ${classes}`}
    >
      {status}
    </span>
  );
}

// ─── Ad copy generator CTA card ────────────────────────────────────────────────

function AdCopyCtaCard() {
  return (
    <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-5 flex flex-col items-start gap-4">
      <div className="flex items-center gap-3">
        <div
          className="flex items-center justify-center w-12 h-12 rounded-full flex-shrink-0 shadow-sm"
          style={{ background: "linear-gradient(135deg, #10B981 0%, #059669 100%)" }}
          aria-hidden="true"
        >
          <span className="text-xl leading-none">📢</span>
        </div>
        <div>
          <h2 className="text-sm font-bold text-gray-900">Generate Ad Copy</h2>
          <p className="text-xs text-emerald-700 font-medium mt-0.5">
            AI-powered ad variants for every platform
          </p>
        </div>
      </div>
      <p className="text-sm text-gray-600 leading-relaxed">
        Use the AI Ad Copy Generator to create compelling ad variants tailored
        to your platform and campaign goals.
      </p>
      <Link
        href="/marketing/ads/generator"
        className="inline-flex items-center gap-1.5 px-4 py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white text-sm font-semibold rounded-lg transition-colors duration-150 active:scale-95 shadow-sm"
      >
        Generate Copy
        <span aria-hidden="true">→</span>
      </Link>
    </div>
  );
}

// ─── Campaigns table ────────────────────────────────────────────────────────

function CampaignsTable({ campaigns }: { campaigns: AdsOverviewCampaign[] }) {
  if (campaigns.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 gap-2">
        <span className="text-3xl" aria-hidden="true">📁</span>
        <p className="text-sm font-medium text-gray-500">No campaigns yet.</p>
        <p className="text-xs text-gray-400 text-center">
          Campaigns will appear here once Meta Ads data syncs.
        </p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-100">
            <th className="text-left font-semibold text-gray-500 text-[11px] uppercase tracking-wider px-5 py-2">Campaign</th>
            <th className="text-left font-semibold text-gray-500 text-[11px] uppercase tracking-wider px-3 py-2">Status</th>
            <th className="text-left font-semibold text-gray-500 text-[11px] uppercase tracking-wider px-3 py-2">Objective</th>
            <th className="text-right font-semibold text-gray-500 text-[11px] uppercase tracking-wider px-3 py-2">Budget</th>
            <th className="text-right font-semibold text-gray-500 text-[11px] uppercase tracking-wider px-3 py-2">Spend</th>
            <th className="text-right font-semibold text-gray-500 text-[11px] uppercase tracking-wider px-3 py-2">Leads</th>
            <th className="text-right font-semibold text-gray-500 text-[11px] uppercase tracking-wider px-3 py-2">CPL</th>
            <th className="text-right font-semibold text-gray-500 text-[11px] uppercase tracking-wider px-5 py-2">Ads</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {campaigns.map((c) => {
            const budget =
              c.daily_budget != null
                ? `${formatCurrency(c.daily_budget)}/day`
                : c.lifetime_budget != null
                ? `${formatCurrency(c.lifetime_budget)} lifetime`
                : "—";
            return (
              <tr key={c.campaign_id} className="hover:bg-gray-50">
                <td className="px-5 py-3 font-medium text-gray-800 max-w-xs truncate" title={c.name ?? undefined}>
                  {c.name ?? "Untitled campaign"}
                </td>
                <td className="px-3 py-3"><StatusChip status={c.status} /></td>
                <td className="px-3 py-3 text-gray-500 text-xs">{c.objective ?? "—"}</td>
                <td className="px-3 py-3 text-right tabular-nums text-gray-700">{budget}</td>
                <td className="px-3 py-3 text-right tabular-nums font-semibold text-gray-900">
                  {formatCurrency(c.spend)}
                </td>
                <td className="px-3 py-3 text-right tabular-nums text-gray-700">{c.leads.toLocaleString()}</td>
                <td className="px-3 py-3 text-right tabular-nums text-gray-700">
                  {c.leads > 0 ? formatCurrency(c.cost_per_lead) : "—"}
                </td>
                <td className="px-5 py-3 text-right tabular-nums text-gray-500">{c.ads_count}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// ─── Top ads table ──────────────────────────────────────────────────────────

function TopAdsTable({ ads }: { ads: AdsOverviewTopAd[] }) {
  if (ads.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 gap-2">
        <span className="text-3xl" aria-hidden="true">📊</span>
        <p className="text-sm font-medium text-gray-500">No ad performance data yet.</p>
        <p className="text-xs text-gray-400 text-center">
          Top ads will appear here once spend/performance data syncs.
        </p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-100">
            <th className="text-left font-semibold text-gray-500 text-[11px] uppercase tracking-wider px-5 py-2">Ad</th>
            <th className="text-left font-semibold text-gray-500 text-[11px] uppercase tracking-wider px-3 py-2">Campaign</th>
            <th className="text-left font-semibold text-gray-500 text-[11px] uppercase tracking-wider px-3 py-2">Format</th>
            <th className="text-left font-semibold text-gray-500 text-[11px] uppercase tracking-wider px-3 py-2">Hook</th>
            <th className="text-left font-semibold text-gray-500 text-[11px] uppercase tracking-wider px-3 py-2">Status</th>
            <th className="text-left font-semibold text-gray-500 text-[11px] uppercase tracking-wider px-3 py-2">KPI</th>
            <th className="text-right font-semibold text-gray-500 text-[11px] uppercase tracking-wider px-3 py-2">Spend</th>
            <th className="text-right font-semibold text-gray-500 text-[11px] uppercase tracking-wider px-3 py-2">Leads</th>
            <th className="text-right font-semibold text-gray-500 text-[11px] uppercase tracking-wider px-5 py-2">CPL</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {ads.map((a) => {
            const isKilled = a.status?.trim().toLowerCase() === "killed" || !!a.kill_date;
            const rowTitle = isKilled && a.kill_reason ? a.kill_reason : undefined;
            return (
              <tr key={a.ad_id} className="hover:bg-gray-50" title={rowTitle}>
                <td className="px-5 py-3 font-medium text-gray-800 max-w-[220px] truncate" title={a.name ?? undefined}>
                  {a.name ?? "Untitled ad"}
                </td>
                <td className="px-3 py-3 text-gray-500 text-xs max-w-[160px] truncate" title={a.campaign_name ?? undefined}>
                  {a.campaign_name ?? "—"}
                </td>
                <td className="px-3 py-3 text-gray-500 text-xs">{a.ad_format ?? "—"}</td>
                <td
                  className="px-3 py-3 text-gray-600 text-xs max-w-[220px] truncate"
                  title={a.hook_text ?? undefined}
                >
                  {a.hook_text ?? "—"}
                </td>
                <td className="px-3 py-3">
                  <span title={a.kill_reason ?? undefined}>
                    <StatusChip status={a.status} />
                  </span>
                </td>
                <td className="px-3 py-3"><KpiStatusChip status={a.kpi_status} /></td>
                <td className="px-3 py-3 text-right tabular-nums font-semibold text-gray-900">
                  {formatCurrency(a.spend)}
                </td>
                <td className="px-3 py-3 text-right tabular-nums text-gray-700">{a.leads.toLocaleString()}</td>
                <td className="px-5 py-3 text-right tabular-nums text-gray-700">
                  {a.leads > 0 ? formatCurrency(a.cost_per_lead) : "—"}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// ─── Loading skeleton ─────────────────────────────────────────────────────────

function AdsPageSkeleton() {
  return (
    <main className="flex-1 overflow-y-auto p-7 space-y-6">
      {/* Heading skeleton */}
      <div>
        <Skeleton className="h-6 w-32" />
        <Skeleton className="h-4 w-80 mt-2" />
      </div>

      {/* KPI tiles skeleton */}
      <div className="grid grid-cols-4 gap-4">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="bg-white rounded-xl border border-gray-200 shadow-sm p-5 flex flex-col gap-2">
            <Skeleton className="h-3 w-24" />
            <Skeleton className="h-7 w-16" />
          </div>
        ))}
      </div>

      {/* Campaigns table + CTA skeleton */}
      <div className="grid grid-cols-2 gap-4">
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
          <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
            <Skeleton className="h-4 w-36" />
          </div>
          <div className="divide-y divide-gray-100">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="flex items-center gap-4 px-5 py-3">
                <Skeleton className="h-4 w-24" />
                <div className="flex flex-1 gap-6">
                  <Skeleton className="h-4 w-16" />
                  <Skeleton className="h-4 w-12" />
                  <Skeleton className="h-4 w-12" />
                </div>
              </div>
            ))}
          </div>
        </div>
        <Skeleton className="h-48 rounded-xl" />
      </div>

      {/* Top ads skeleton */}
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
        <div className="px-5 py-4 border-b border-gray-100">
          <Skeleton className="h-4 w-32" />
        </div>
        <div className="p-5 flex flex-col gap-3">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-8 w-full" />
          ))}
        </div>
      </div>
    </main>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function AdsPage() {
  const { isLoading: authLoading } = useAuth();
  const [data, setData] = useState<AdsOverviewResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (authLoading) return;

    let cancelled = false;

    async function fetchData(): Promise<void> {
      try {
        const result = await apiClient.get<AdsOverviewResponse>("/ads/overview", { silent: true });
        if (!cancelled) setData(result);
      } catch {
        // On error, data stays null — page renders with quiet empty states.
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    }

    void fetchData();
    return () => { cancelled = true; };
  }, [authLoading]);

  if (isLoading) {
    return (
      <>
        <Header title="Ads" />
        <AdsPageSkeleton />
      </>
    );
  }

  const kpis = data?.kpis;

  return (
    <>
      <Header title="Ads" />

      <main className="flex-1 overflow-y-auto p-7 space-y-6">
        {/* Page heading */}
        <div>
          <h1 className="text-xl font-bold text-gray-900">Ads</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Campaign performance and spend overview, pulled directly from the Meta Ads sync.
          </p>
        </div>

        {/* Row 1: KPI tiles */}
        <section aria-label="Ads KPIs">
          <KpiRow>
            <KpiCard
              label="Active Campaigns"
              value={kpis ? kpis.active_campaigns.toLocaleString() : "—"}
              sub={kpis ? `${kpis.total_campaigns} total` : undefined}
              borderColor="#10B981"
            />
            <KpiCard
              label="Total Spend"
              value={kpis ? formatCurrency(kpis.total_spend) : "—"}
              borderColor="#10B981"
            />
            <KpiCard
              label="Cost / Lead"
              value={kpis && kpis.total_leads > 0 ? formatCurrency(kpis.avg_cost_per_lead) : "—"}
              sub={kpis ? `${kpis.total_leads.toLocaleString()} leads` : undefined}
              borderColor="#10B981"
            />
            <KpiCard
              label="CTR"
              value={kpis ? `${kpis.avg_ctr.toFixed(2)}%` : "—"}
              sub={kpis ? `${kpis.total_impressions.toLocaleString()} impressions` : undefined}
              borderColor="#10B981"
            />
          </KpiRow>
        </section>

        {/* Row 2: Campaigns table + Ad copy CTA */}
        <div className="grid grid-cols-2 gap-4 items-start">
          <Card>
            <CardHeader
              title="Campaigns"
              action={
                <span className="text-xs text-gray-400">
                  {kpis ? `${kpis.total_campaigns} campaigns` : "—"}
                </span>
              }
            />
            <CampaignsTable campaigns={data?.campaigns ?? []} />
          </Card>
          <AdCopyCtaCard />
        </div>

        {/* Row 3: Top ads */}
        <Card>
          <CardHeader
            title="Top Ads by Spend"
            action={
              <span className="text-xs text-gray-400">
                {kpis ? `${kpis.total_ads} ads total` : "—"}
              </span>
            }
          />
          <TopAdsTable ads={data?.top_ads ?? []} />
        </Card>
      </main>
    </>
  );
}
