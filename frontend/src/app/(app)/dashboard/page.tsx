"use client";

import { useState, useEffect } from "react";
import { Header } from "@/components/layout/header";
import { DepartmentCard } from "@/components/dashboard/department-card";
import { KpiCard } from "@/components/dashboard/kpi-card";
import { CIWidget } from "@/components/dashboard/ci-widget";
import { WeeklyFocus } from "@/components/dashboard/weekly-focus";
import {
  DepartmentCardSkeleton,
  KpiGridSkeleton,
  CIWidgetSkeleton,
} from "@/components/ui/skeleton";
import { StaleIndicator } from "@/components/ui/stale-indicator";
import { apiClient } from "@/lib/api-client";
import { useAuth } from "@/hooks/use-auth";
import type { DashboardStats, DepartmentStats } from "@/types";

// ─── Helpers ─────────────────────────────────────────────────────────────────

/** Format a raw number with comma-separated thousands (e.g. 1247 → "1,247"). */
function formatNumber(n: number): string {
  return n.toLocaleString("en-US");
}

// ─── Fallback data ────────────────────────────────────────────────────────────

/** Shown while loading or when the fetch fails. */
const EMPTY_STATS: DashboardStats = {
  departments: {
    sales: { stats: [] },
    fulfillment: { stats: [] },
    marketing: { stats: [] },
  },
  kpis: {
    total_leads: 0,
    leads_this_week: 0,
    calls_this_week: 0,
    active_members: 0,
  },
  lead_volume: [],
};

// ─── Sparkline ───────────────────────────────────────────────────────────────

interface SparklineProps {
  data: { label: string; value: number }[];
}

function Sparkline({ data }: SparklineProps) {
  if (data.length === 0) {
    return (
      <div className="flex items-end gap-1 h-10" role="img" aria-label="No sparkline data available">
        <span className="text-xs text-gray-400">—</span>
      </div>
    );
  }

  const values = data.map((d) => d.value);
  const max = Math.max(...values, 1); // guard against all-zero data

  return (
    <div
      className="flex items-end gap-1 h-10"
      role="img"
      aria-label="Weekly leads trend bar chart"
    >
      {data.map((d, i) => {
        const isLast = i === data.length - 1;
        const heightPercent = Math.round((d.value / max) * 100);

        return (
          <div
            key={i}
            className={`flex-1 rounded-sm transition-all ${
              isLast ? "bg-indigo-400" : "bg-gray-200"
            }`}
            style={{ height: `${heightPercent}%` }}
            aria-hidden="true"
          />
        );
      })}
    </div>
  );
}

// ─── Weekly Performance Snapshot ────────────────────────────────────────────

interface WeeklySnapshotProps {
  kpis: DashboardStats["kpis"];
  leadVolume: DashboardStats["lead_volume"];
}

function WeeklySnapshot({ kpis, leadVolume }: WeeklySnapshotProps) {
  return (
    <section
      className="bg-white rounded-xl border border-gray-200 p-5 flex flex-col gap-4 shadow-sm"
      aria-label="Weekly Performance Snapshot"
    >
      {/* Section header */}
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-bold text-gray-900">Weekly Performance Snapshot</h2>
        <span className="text-xs text-gray-400 font-medium">Mar 24 – Mar 30</span>
      </div>

      {/* KPI mini-cards */}
      <div className="grid grid-cols-2 gap-3">
        <KpiCard
          label="Total Leads"
          value={formatNumber(kpis.total_leads)}
          change={0}
          changeDirection="up"
          subtitle="All time"
        />
        <KpiCard
          label="This Week"
          value={formatNumber(kpis.leads_this_week)}
          change={0}
          changeDirection="up"
          subtitle="New leads"
        />
        <KpiCard
          label="Calls This Week"
          value={formatNumber(kpis.calls_this_week)}
          change={0}
          changeDirection="up"
          subtitle="Completed"
        />
        <KpiCard
          label="Active Members"
          value={formatNumber(kpis.active_members)}
          change={0}
          changeDirection="up"
          subtitle="Enrolled"
        />
      </div>

      {/* Divider */}
      <div className="border-t border-gray-100 pt-3 flex flex-col gap-2">
        <span className="text-[10px] font-bold uppercase tracking-widest text-gray-400">
          Leads — last 8 weeks
        </span>
        <Sparkline data={leadVolume} />
      </div>
    </section>
  );
}

// ─── Dashboard skeleton ─────────────────────────────────────────────────────

function DashboardSkeleton() {
  return (
    <main className="flex-1 overflow-y-auto p-7 space-y-6">
      {/* Heading skeleton */}
      <div>
        <div className="h-6 w-48 bg-gray-200 rounded animate-pulse" />
        <div className="h-4 w-72 bg-gray-200 rounded animate-pulse mt-2" />
      </div>

      {/* Department cards skeleton */}
      <section aria-label="Loading department summaries">
        <div className="grid grid-cols-3 gap-4">
          <DepartmentCardSkeleton />
          <DepartmentCardSkeleton />
          <DepartmentCardSkeleton />
        </div>
      </section>

      {/* Weekly-focus skeleton (full width) */}
      <div className="bg-indigo-50 border border-indigo-200 rounded-xl p-5 h-28 animate-pulse" />

      {/* Bottom 2-column skeleton */}
      <div className="grid grid-cols-2 gap-4">
        <KpiGridSkeleton />
        <CIWidgetSkeleton />
      </div>
    </main>
  );
}

// ─── Page ────────────────────────────────────────────────────────────────────

export default function DashboardPage() {
  const { isLoading: authLoading } = useAuth();
  const [isLoading, setIsLoading] = useState(true);
  const [stats, setStats] = useState<DashboardStats>(EMPTY_STATS);
  const [lastUpdatedAt, setLastUpdatedAt] = useState<string | null>(null);

  useEffect(() => {
    // Wait until auth has hydrated and set the token before calling the API.
    if (authLoading) return;

    let cancelled = false;

    async function fetchStats(): Promise<void> {
      try {
        const data = await apiClient.get<DashboardStats>("/dashboard/stats", { silent: true });
        if (!cancelled) {
          setStats(data);
          setLastUpdatedAt(new Date().toISOString());
        }
      } catch {
        // On error, stats stays as EMPTY_STATS so the page renders with "0" values.
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    }

    void fetchStats();

    return () => {
      cancelled = true;
    };
  }, [authLoading]);

  // ─── Map API departments to DepartmentStats component shape ────────────────

  const departments: DepartmentStats[] = [
    {
      name: "Sales",
      icon: "💼",
      color: "sales",
      stats: stats.departments.sales.stats,
    },
    {
      name: "Marketing",
      icon: "📣",
      color: "marketing",
      stats: stats.departments.marketing.stats,
    },
    {
      name: "Fulfillment",
      icon: "🏆",
      color: "fulfillment",
      stats: stats.departments.fulfillment.stats,
    },
  ];

  return (
    <>
      <Header title="Dashboard" />

      {isLoading ? (
        <DashboardSkeleton />
      ) : (
        <main className="flex-1 overflow-y-auto p-7 space-y-6">
          {/* Page heading */}
          <div className="flex items-start justify-between gap-4">
            <div>
              <h1 className="text-xl font-bold text-gray-900">Good morning</h1>
              <p className="text-sm text-gray-500 mt-0.5">
                Here&apos;s what&apos;s happening across your business today.
              </p>
            </div>
            <StaleIndicator lastUpdatedAt={lastUpdatedAt} />
          </div>

          {/* Department cards — 3-column grid */}
          <section aria-label="Department summaries">
            <div className="grid grid-cols-3 gap-4">
              {departments.map((dept) => (
                <DepartmentCard key={dept.name} {...dept} />
              ))}
            </div>
          </section>

          {/* This week's focus — full-width cross-department synthesis */}
          <WeeklyFocus />

          {/* Bottom 2-column layout */}
          <div className="grid grid-cols-2 gap-4">
            <WeeklySnapshot kpis={stats.kpis} leadVolume={stats.lead_volume} />
            <CIWidget />
          </div>
        </main>
      )}
    </>
  );
}
