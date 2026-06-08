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

// ─── Types ──────────────────────────────────────────────────────────────────

interface SalesKpis {
  total_leads: number;
  leads_this_week: number;
  conversion_rate: number;
  active_applications: number;
}

interface SalesSummary {
  kpis: SalesKpis;
}

const EMPTY_KPIS: SalesKpis = {
  total_leads: 0,
  leads_this_week: 0,
  conversion_rate: 0,
  active_applications: 0,
};

// ─── Sales colour ─────────────────────────────────────────────────────────────

const SALES_BORDER = "#3B82F6";

// ─── Sales tool quick links ───────────────────────────────────────────────────

interface ToolLink {
  label: string;
  href: string;
  icon: string;
}

const TOOL_LINKS: ToolLink[] = [
  { label: "Leads", href: "/leads", icon: "🧲" },
  { label: "Sales Calls", href: "/sales-calls", icon: "📞" },
];

// ─── KPI tiles ────────────────────────────────────────────────────────────────

function SalesKpiGrid({ kpis }: { kpis: SalesKpis }) {
  const tiles = [
    { label: "Total Leads", value: String(kpis.total_leads) },
    { label: "Leads This Week", value: String(kpis.leads_this_week) },
    { label: "Conversion Rate", value: `${kpis.conversion_rate}%` },
    { label: "Active Applications", value: String(kpis.active_applications) },
  ];

  return (
    <section aria-label="Sales KPIs">
      <div className="grid grid-cols-4 gap-4">
        {tiles.map((tile) => (
          <KpiCard
            key={tile.label}
            label={tile.label}
            value={tile.value}
            borderColor={SALES_BORDER}
          />
        ))}
      </div>
    </section>
  );
}

// ─── Sales tools card ─────────────────────────────────────────────────────────

function SalesToolsCard() {
  return (
    <Card>
      <CardHeader title="Sales Tools" noBorder />
      <CardBody className="pt-0">
        <div className="grid grid-cols-2 gap-1">
          {TOOL_LINKS.map((tool) => (
            <Link
              key={tool.href}
              href={tool.href}
              className="flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-sm font-medium text-gray-700 hover:bg-blue-50 hover:text-blue-700 transition-colors duration-150"
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

// ─── Sales Director CTA card ──────────────────────────────────────────────────

function SalesDirectorCtaCard() {
  return (
    <div className="bg-blue-50 border border-blue-200 rounded-xl p-5 flex flex-col items-start gap-4">
      {/* Icon + heading */}
      <div className="flex items-center gap-3">
        <div
          className="flex items-center justify-center w-12 h-12 rounded-full flex-shrink-0 shadow-sm"
          style={{
            background: "linear-gradient(135deg, #3B82F6 0%, #2563EB 100%)",
          }}
          aria-hidden="true"
        >
          <span className="text-xl leading-none">💼</span>
        </div>
        <div>
          <h2 className="text-sm font-bold text-gray-900">Sales Director</h2>
          <p className="text-xs text-blue-700 font-medium mt-0.5">
            AI-powered pipeline intelligence
          </p>
        </div>
      </div>

      {/* Description */}
      <p className="text-sm text-gray-600 leading-relaxed">
        Get AI-powered pipeline insights, conversion analysis, and call
        intelligence from your dedicated Sales Director agent.
      </p>

      {/* CTA */}
      <Button variant="primary" href="/sales-director">
        Start Conversation <span aria-hidden="true">→</span>
      </Button>
    </div>
  );
}

// ─── Loading skeleton ─────────────────────────────────────────────────────────

function SalesPageSkeleton() {
  return (
    <main className="flex-1 overflow-y-auto p-7 space-y-6">
      <div>
        <div className="h-6 w-48 bg-gray-200 rounded animate-pulse" />
        <div className="h-4 w-72 bg-gray-200 rounded animate-pulse mt-2" />
      </div>

      <section aria-label="Loading sales KPIs">
        <div className="grid grid-cols-4 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <DepartmentCardSkeleton key={i} />
          ))}
        </div>
      </section>

      <div className="grid grid-cols-2 gap-4">
        <DepartmentCardSkeleton />
        <DepartmentCardSkeleton />
      </div>
    </main>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function SalesPage() {
  const { isLoading: authLoading } = useAuth();
  const [isLoading, setIsLoading] = useState(true);
  const [kpis, setKpis] = useState<SalesKpis>(EMPTY_KPIS);
  const [lastUpdatedAt, setLastUpdatedAt] = useState<string | null>(null);

  useEffect(() => {
    // Wait until auth has hydrated and set the token before calling the API.
    if (authLoading) return;

    let cancelled = false;

    async function fetchSummary(): Promise<void> {
      try {
        const data = await apiClient.get<SalesSummary>("/sales/summary", {
          silent: true,
        });
        if (!cancelled) {
          setKpis(data.kpis ?? EMPTY_KPIS);
          setLastUpdatedAt(new Date().toISOString());
        }
      } catch {
        // On error, kpis stays as EMPTY_KPIS so the page renders with zeros.
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    }

    void fetchSummary();

    return () => {
      cancelled = true;
    };
  }, [authLoading]);

  return (
    <>
      <Header title="Sales" />

      {isLoading ? (
        <SalesPageSkeleton />
      ) : (
        <main className="flex-1 overflow-y-auto p-7 space-y-6">
          {/* Page heading */}
          <div className="flex items-start justify-between gap-4">
            <div>
              <h1 className="text-xl font-bold text-gray-900">Sales Overview</h1>
              <p className="text-sm text-gray-500 mt-0.5">
                Pipeline snapshot across leads and sales calls.
              </p>
            </div>
            <StaleIndicator lastUpdatedAt={lastUpdatedAt} />
          </div>

          {/* Row 1: KPI tiles */}
          <SalesKpiGrid kpis={kpis} />

          {/* Row 2: Tools + Director CTA */}
          <div className="grid grid-cols-2 gap-4">
            <SalesToolsCard />
            <SalesDirectorCtaCard />
          </div>
        </main>
      )}
    </>
  );
}
