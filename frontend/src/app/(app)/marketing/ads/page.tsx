"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { Header } from "@/components/layout/header";
import { apiClient } from "@/lib/api-client";
import { useAuth } from "@/hooks/use-auth";
import { Skeleton } from "@/components/ui/skeleton";
import type { AdsData } from "@/types";

// ─── Platform breakdown data ───────────────────────────────────────────────────

interface PlatformRow {
  name: string;
  icon: string;
  impressions: string;
  clicks: string;
  cpc: string;
  roas: string;
}

const AD_PLATFORMS: PlatformRow[] = [
  { name: "Google Ads", icon: "📊", impressions: "—", clicks: "—", cpc: "—", roas: "—" },
  { name: "Facebook Ads", icon: "📘", impressions: "—", clicks: "—", cpc: "—", roas: "—" },
  { name: "Instagram Ads", icon: "📷", impressions: "—", clicks: "—", cpc: "—", roas: "—" },
  { name: "TikTok Ads", icon: "🎵", impressions: "—", clicks: "—", cpc: "—", roas: "—" },
];

// ─── Platform breakdown card ───────────────────────────────────────────────────

function PlatformBreakdownCard() {
  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
      <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
        <h2 className="text-sm font-bold text-gray-900">Platform Breakdown</h2>
        <span className="text-xs text-gray-400">Last 30 days</span>
      </div>
      {/* Table header */}
      <div className="flex items-center gap-4 px-5 py-2 bg-gray-50 border-b border-gray-100">
        <span className="text-[10px] font-bold uppercase tracking-wider text-gray-400 w-36 flex-shrink-0">
          Platform
        </span>
        <div className="flex flex-1 gap-6">
          <span className="text-[10px] font-bold uppercase tracking-wider text-gray-400 w-20">
            Impressions
          </span>
          <span className="text-[10px] font-bold uppercase tracking-wider text-gray-400 w-16">
            Clicks
          </span>
          <span className="text-[10px] font-bold uppercase tracking-wider text-gray-400 w-16">
            CPC
          </span>
          <span className="text-[10px] font-bold uppercase tracking-wider text-gray-400 w-16">
            ROAS
          </span>
        </div>
      </div>
      <div className="divide-y divide-gray-100">
        {AD_PLATFORMS.map((platform) => (
          <div
            key={platform.name}
            className="flex items-center gap-4 px-5 py-3"
          >
            <div className="flex items-center gap-2.5 w-36 flex-shrink-0">
              <span className="text-xl leading-none flex-shrink-0" aria-hidden="true">
                {platform.icon}
              </span>
              <span className="text-sm font-medium text-gray-800">
                {platform.name}
              </span>
            </div>
            <div className="flex flex-1 gap-6">
              <span className="text-sm font-semibold text-gray-700 tabular-nums w-20">
                {platform.impressions}
              </span>
              <span className="text-sm font-semibold text-gray-700 tabular-nums w-16">
                {platform.clicks}
              </span>
              <span className="text-sm font-semibold text-gray-700 tabular-nums w-16">
                {platform.cpc}
              </span>
              <span className="text-sm font-semibold text-gray-700 tabular-nums w-16">
                {platform.roas}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
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

// ─── Ad performance empty state ───────────────────────────────────────────────

function AdPerformanceEmptyState({ label }: { label: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-12 gap-3">
      <span className="text-3xl" aria-hidden="true">
        📊
      </span>
      <p className="text-sm font-medium text-gray-500">No ad data yet.</p>
      <p className="text-xs text-gray-400 text-center">
        {label} will appear here once campaigns are running.
      </p>
    </div>
  );
}

// ─── Ad performance card ──────────────────────────────────────────────────────

function AdPerformanceCard() {
  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
      <div className="px-5 py-4 border-b border-gray-100">
        <h2 className="text-sm font-bold text-gray-900">Ad Performance</h2>
      </div>
      <div className="grid grid-cols-2 divide-x divide-gray-100">
        <div>
          <div className="px-5 py-3 border-b border-gray-100">
            <h3 className="text-xs font-bold text-gray-700">Top Performers</h3>
          </div>
          <AdPerformanceEmptyState label="Top performing ads" />
        </div>
        <div>
          <div className="px-5 py-3 border-b border-gray-100">
            <h3 className="text-xs font-bold text-gray-700">Underperforming</h3>
          </div>
          <AdPerformanceEmptyState label="Underperforming ads" />
        </div>
      </div>
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

      {/* Platform breakdown + CTA skeleton */}
      <div className="grid grid-cols-2 gap-4">
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
          <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
            <Skeleton className="h-4 w-36" />
            <Skeleton className="h-3 w-20" />
          </div>
          <div className="divide-y divide-gray-100">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="flex items-center gap-4 px-5 py-3">
                <Skeleton className="w-6 h-6 rounded" />
                <Skeleton className="h-4 w-24" />
                <div className="flex flex-1 gap-6">
                  <Skeleton className="h-4 w-16" />
                  <Skeleton className="h-4 w-12" />
                  <Skeleton className="h-4 w-12" />
                  <Skeleton className="h-4 w-12" />
                </div>
              </div>
            ))}
          </div>
        </div>
        <Skeleton className="h-48 rounded-xl" />
      </div>

      {/* Ad performance skeleton */}
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
        <div className="px-5 py-4 border-b border-gray-100">
          <Skeleton className="h-4 w-32" />
        </div>
        <div className="grid grid-cols-2 divide-x divide-gray-100">
          {[1, 2].map((i) => (
            <div key={i} className="flex flex-col items-center justify-center py-12 gap-3">
              <Skeleton className="w-8 h-8 rounded-full" />
              <Skeleton className="h-4 w-28" />
              <Skeleton className="h-3 w-48" />
            </div>
          ))}
        </div>
      </div>
    </main>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function AdsPage() {
  const { isLoading: authLoading } = useAuth();
  const [data, setData] = useState<AdsData | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (authLoading) return;

    let cancelled = false;

    async function fetchData(): Promise<void> {
      try {
        const result = await apiClient.get<AdsData>("/ads", { silent: true });
        if (!cancelled) setData(result);
      } catch {
        // On error, data stays null — page renders with "—" fallbacks.
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

  return (
    <>
      <Header title="Ads" />

      <main className="flex-1 overflow-y-auto p-7 space-y-6">
        {/* Page heading */}
        <div>
          <h1 className="text-xl font-bold text-gray-900">Ads</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Campaign performance and spend overview across all paid ad platforms.
          </p>
        </div>

        {/* Row 1: KPI tiles */}
        <section aria-label="Ads KPIs">
          <div className="grid grid-cols-4 gap-4">
            <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5 flex flex-col gap-1" style={{ borderTopWidth: "3px", borderTopColor: "#10B981" }}>
              <span className="text-[10px] font-bold uppercase tracking-wider text-emerald-600">Active Campaigns</span>
              <span className="text-2xl font-bold text-gray-900 tabular-nums leading-tight">
                {data ? data.campaigns.toLocaleString() : "—"}
              </span>
            </div>
            <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5 flex flex-col gap-1" style={{ borderTopWidth: "3px", borderTopColor: "#10B981" }}>
              <span className="text-[10px] font-bold uppercase tracking-wider text-emerald-600">Total Spend MTD</span>
              <span className="text-2xl font-bold text-gray-900 tabular-nums leading-tight">
                {data ? `$${data.total_spend.toLocaleString()}` : "—"}
              </span>
            </div>
            <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5 flex flex-col gap-1" style={{ borderTopWidth: "3px", borderTopColor: "#10B981" }}>
              <span className="text-[10px] font-bold uppercase tracking-wider text-emerald-600">ROAS</span>
              <span className="text-2xl font-bold text-gray-900 tabular-nums leading-tight">
                {data ? `${data.avg_roas.toFixed(1)}x` : "—"}
              </span>
            </div>
            <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5 flex flex-col gap-1" style={{ borderTopWidth: "3px", borderTopColor: "#10B981" }}>
              <span className="text-[10px] font-bold uppercase tracking-wider text-emerald-600">CTR</span>
              <span className="text-2xl font-bold text-gray-900 tabular-nums leading-tight">—</span>
            </div>
          </div>
        </section>

        {/* Row 2: Platform breakdown + Ad copy CTA */}
        <div className="grid grid-cols-2 gap-4">
          <PlatformBreakdownCard />
          <AdCopyCtaCard />
        </div>

        {/* Row 3: Ad performance */}
        <AdPerformanceCard />
      </main>
    </>
  );
}
