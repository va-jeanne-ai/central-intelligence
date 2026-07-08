"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { Header } from "@/components/layout/header";
import { DepartmentCardSkeleton } from "@/components/ui/skeleton";
import { StaleIndicator } from "@/components/ui/stale-indicator";
import { KpiCard } from "@/components/ui/kpi-card";
import { Card, CardHeader, CardBody } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { apiClient } from "@/lib/api-client";
import { useAuth } from "@/hooks/use-auth";
import type { DashboardStats, DepartmentStat } from "@/types";

// ─── Fallback data ────────────────────────────────────────────────────────────

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

// ─── Marketing tool quick links ───────────────────────────────────────────────

interface ToolLink {
  label: string;
  href: string;
  icon: string;
}

const TOOL_LINKS: ToolLink[] = [
  { label: "Social Media", href: "/marketing/social", icon: "📱" },
  { label: "Email", href: "/marketing/email", icon: "✉" },
  { label: "Funnels", href: "/marketing/funnels", icon: "📈" },
  { label: "Ads", href: "/marketing/ads", icon: "📢" },
  { label: "DM", href: "/marketing/dm", icon: "💬" },
  { label: "Offers", href: "/marketing/offers", icon: "🎁" },
  { label: "Promo Calendar", href: "/marketing/promo-calendar", icon: "📅" },
];

// ─── KPI stat tile (uses atomic KpiCard) ─────────────────────────────────────

function StatTile({ stat }: { stat: DepartmentStat }) {
  return (
    <KpiCard
      label={stat.label}
      value={stat.value}
      borderColor="#10B981"
      sub={stat.sub}
    />
  );
}

// ─── KPI grid skeleton ────────────────────────────────────────────────────────

function MarketingKpiSkeleton() {
  return (
    <section aria-label="Loading marketing KPIs">
      <div className="grid grid-cols-4 gap-4">
        {[1, 2, 3, 4, 5, 6, 7].map((i) => (
          <DepartmentCardSkeleton key={i} />
        ))}
      </div>
    </section>
  );
}

// ─── Marketing tools card ─────────────────────────────────────────────────────

function MarketingToolsCard() {
  return (
    <Card>
      <CardHeader title="Marketing Tools" noBorder />
      <CardBody className="pt-0">
        <div className="grid grid-cols-2 gap-1">
          {TOOL_LINKS.map((tool) => (
            <Link
              key={tool.href}
              href={tool.href}
              className="flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-sm font-medium text-gray-700 hover:bg-emerald-50 hover:text-emerald-700 transition-colors duration-150"
            >
              <span className="text-base leading-none" aria-hidden="true">
                {tool.icon}
              </span>
              <span>{tool.label}</span>
            </Link>
          ))}
        </div>
      </CardBody>
    </Card>
  );
}

// ─── Marketing Director CTA card ──────────────────────────────────────────────

function MarketingDirectorCtaCard() {
  return (
    <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-5 flex flex-col items-start gap-4">
      {/* Icon + heading */}
      <div className="flex items-center gap-3">
        <div
          className="flex items-center justify-center w-12 h-12 rounded-full flex-shrink-0 shadow-sm"
          style={{
            background: "linear-gradient(135deg, #10B981 0%, #059669 100%)",
          }}
          aria-hidden="true"
        >
          <span className="text-xl leading-none">📣</span>
        </div>
        <div>
          <h2 className="text-sm font-bold text-gray-900">Marketing Director</h2>
          <p className="text-xs text-emerald-700 font-medium mt-0.5">
            AI-powered marketing intelligence
          </p>
        </div>
      </div>

      {/* Description */}
      <p className="text-sm text-gray-600 leading-relaxed">
        Get AI-powered marketing insights, content ideas, and campaign strategy
        from your dedicated Marketing Director agent.
      </p>

      {/* CTA */}
      <Button variant="primary" href="/marketing-director">
        Start Conversation <span aria-hidden="true">→</span>
      </Button>
    </div>
  );
}

// ─── Loading skeleton ─────────────────────────────────────────────────────────

function MarketingPageSkeleton() {
  return (
    <main className="flex-1 overflow-y-auto p-7 space-y-6">
      {/* Heading skeleton */}
      <div>
        <div className="h-6 w-48 bg-gray-200 rounded animate-pulse" />
        <div className="h-4 w-72 bg-gray-200 rounded animate-pulse mt-2" />
      </div>

      {/* KPI grid skeleton */}
      <MarketingKpiSkeleton />

      {/* Bottom 2-column skeleton */}
      <div className="grid grid-cols-2 gap-4">
        <DepartmentCardSkeleton />
        <DepartmentCardSkeleton />
      </div>
    </main>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function MarketingPage() {
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
        const data = await apiClient.get<DashboardStats>("/dashboard/stats", {
          silent: true,
        });
        if (!cancelled) {
          setStats(data);
          setLastUpdatedAt(new Date().toISOString());
        }
      } catch {
        // On error, stats stays as EMPTY_STATS so the page renders with "—" values.
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

  const allStats: DepartmentStat[] = stats.departments.marketing.stats;

  return (
    <>
      <Header title="Marketing" />

      {isLoading ? (
        <MarketingPageSkeleton />
      ) : (
        <main className="flex-1 overflow-y-auto p-7 space-y-6">
          {/* Page heading */}
          <div className="flex items-start justify-between gap-4">
            <div>
              <h1 className="text-xl font-bold text-gray-900">
                Marketing Overview
              </h1>
              <p className="text-sm text-gray-500 mt-0.5">
                Performance snapshot across all marketing channels.
              </p>
            </div>
            <StaleIndicator lastUpdatedAt={lastUpdatedAt} />
          </div>

          {/* Row 1: KPI tiles — full width 4-column grid */}
          <section aria-label="Marketing KPIs">
            <div className="grid grid-cols-4 gap-4">
              {allStats.map((stat, index) => (
                <StatTile key={`${stat.label}-${index}`} stat={stat} />
              ))}
            </div>
          </section>

          {/* Row 2: Tools + Director CTA */}
          <div className="grid grid-cols-2 gap-4">
            <MarketingToolsCard />
            <MarketingDirectorCtaCard />
          </div>
        </main>
      )}
    </>
  );
}
