"use client";

import { useState, useEffect } from "react";
import { Header } from "@/components/layout/header";
import { DepartmentCard } from "@/components/dashboard/department-card";
import { KpiCard } from "@/components/dashboard/kpi-card";
import { CIWidget } from "@/components/dashboard/ci-widget";
import { WeeklyFocus } from "@/components/dashboard/weekly-focus";
import { ScheduleBrief } from "@/components/dashboard/schedule-brief";
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
  const [hovered, setHovered] = useState<number | null>(null);

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
        const isHovered = hovered === i;
        const heightPercent = Math.round((d.value / max) * 100);

        return (
          <div
            key={i}
            className="relative flex-1 h-full flex items-end"
            onMouseEnter={() => setHovered(i)}
            onMouseLeave={() => setHovered(null)}
          >
            {/* Tooltip — value + label above the hovered bar */}
            {isHovered && (
              <div className="pointer-events-none absolute -top-9 left-1/2 -translate-x-1/2 z-10 whitespace-nowrap rounded-md bg-gray-800 px-2 py-1 text-[11px] font-semibold text-white shadow-md">
                {d.value.toLocaleString()} · {d.label}
                <span className="absolute left-1/2 top-full -translate-x-1/2 border-4 border-transparent border-t-gray-800" />
              </div>
            )}
            <div
              className={`w-full rounded-sm cursor-pointer transition-all duration-150 origin-bottom ${
                isHovered
                  ? isLast
                    ? "bg-amber-500 scale-y-105"
                    : "bg-gray-400 scale-y-105"
                  : isLast
                    ? "bg-amber-600"
                    : "bg-gray-200"
              }`}
              style={{ height: `${heightPercent}%` }}
              aria-hidden="true"
            />
          </div>
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
        <span className="text-xs text-gray-400 font-medium">vs last week</span>
      </div>

      {/* KPI mini-cards — 4-col per mockup screen 1 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
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
          Lead Volume — Last 8 Weeks
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

      {/* Schedule brief + weekly-focus skeleton (2-column) */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-sky-50 border border-sky-200 rounded-xl p-5 h-28 animate-pulse" />
        <div className="bg-accent-50 border border-accent-200 rounded-xl p-5 h-28 animate-pulse" />
      </div>

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

          {/* Today's schedule + this week's focus */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <ScheduleBrief />
            <WeeklyFocus />
          </div>

          {/* Bottom layout — snapshot flexes, CI widget fixed 380px (mockup) */}
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1fr_380px]">
            <WeeklySnapshot kpis={stats.kpis} leadVolume={stats.lead_volume} />
            <CIWidget />
          </div>
        </main>
      )}
    </>
  );
}
