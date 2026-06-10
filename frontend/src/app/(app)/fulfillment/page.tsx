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

interface FulfillmentKpis {
  total_members: number;
  members_this_week: number;
  active_members: number;
  goals_completed: number;
}

interface FulfillmentSummary {
  kpis: FulfillmentKpis;
}

const EMPTY_KPIS: FulfillmentKpis = {
  total_members: 0,
  members_this_week: 0,
  active_members: 0,
  goals_completed: 0,
};

// ─── Fulfillment colour ─────────────────────────────────────────────────────

const FULFILLMENT_BORDER = "#F97316";

// ─── Fulfillment tool quick links ─────────────────────────────────────────────

interface ToolLink {
  label: string;
  href: string;
  icon: string;
}

const TOOL_LINKS: ToolLink[] = [
  { label: "Members", href: "/members", icon: "👥" },
  { label: "Coaching Calls", href: "/coaching-calls", icon: "🎯" },
];

// ─── KPI tiles ────────────────────────────────────────────────────────────────

function FulfillmentKpiGrid({ kpis }: { kpis: FulfillmentKpis }) {
  const tiles = [
    { label: "Total Members", value: String(kpis.total_members) },
    { label: "Enrolled This Week", value: String(kpis.members_this_week) },
    { label: "Active Members", value: String(kpis.active_members) },
    { label: "Goals Completed", value: String(kpis.goals_completed) },
  ];

  return (
    <section aria-label="Fulfillment KPIs">
      <div className="grid grid-cols-4 gap-4">
        {tiles.map((tile) => (
          <KpiCard
            key={tile.label}
            label={tile.label}
            value={tile.value}
            borderColor={FULFILLMENT_BORDER}
          />
        ))}
      </div>
    </section>
  );
}

// ─── Fulfillment tools card ───────────────────────────────────────────────────

function FulfillmentToolsCard() {
  return (
    <Card>
      <CardHeader title="Fulfillment Tools" noBorder />
      <CardBody className="pt-0">
        <div className="grid grid-cols-2 gap-1">
          {TOOL_LINKS.map((tool) => (
            <Link
              key={tool.href}
              href={tool.href}
              className="flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-sm font-medium text-gray-700 hover:bg-orange-50 hover:text-orange-700 transition-colors duration-150"
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

// ─── Fulfillment Director CTA card ────────────────────────────────────────────

function FulfillmentDirectorCtaCard() {
  return (
    <div className="bg-orange-50 border border-orange-200 rounded-xl p-5 flex flex-col items-start gap-4">
      {/* Icon + heading */}
      <div className="flex items-center gap-3">
        <div
          className="flex items-center justify-center w-12 h-12 rounded-full flex-shrink-0 shadow-sm"
          style={{
            background: "linear-gradient(135deg, #F97316 0%, #EA580C 100%)",
          }}
          aria-hidden="true"
        >
          <span className="text-xl leading-none">🏆</span>
        </div>
        <div>
          <h2 className="text-sm font-bold text-gray-900">Fulfillment Director</h2>
          <p className="text-xs text-orange-700 font-medium mt-0.5">
            AI-powered client-success intelligence
          </p>
        </div>
      </div>

      {/* Description */}
      <p className="text-sm text-gray-600 leading-relaxed">
        Get AI-powered member-progress insights, coaching wins, and retention
        signals from your dedicated Fulfillment Director agent.
      </p>

      {/* CTA */}
      <Button variant="primary" href="/fulfillment-director">
        Start Conversation <span aria-hidden="true">→</span>
      </Button>
    </div>
  );
}

// ─── Loading skeleton ─────────────────────────────────────────────────────────

function FulfillmentPageSkeleton() {
  return (
    <main className="flex-1 overflow-y-auto p-7 space-y-6">
      <div>
        <div className="h-6 w-48 bg-gray-200 rounded animate-pulse" />
        <div className="h-4 w-72 bg-gray-200 rounded animate-pulse mt-2" />
      </div>

      <section aria-label="Loading fulfillment KPIs">
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

export default function FulfillmentPage() {
  const { isLoading: authLoading } = useAuth();
  const [isLoading, setIsLoading] = useState(true);
  const [kpis, setKpis] = useState<FulfillmentKpis>(EMPTY_KPIS);
  const [lastUpdatedAt, setLastUpdatedAt] = useState<string | null>(null);

  useEffect(() => {
    // Wait until auth has hydrated and set the token before calling the API.
    if (authLoading) return;

    let cancelled = false;

    async function fetchSummary(): Promise<void> {
      try {
        const data = await apiClient.get<FulfillmentSummary>("/fulfillment/summary", {
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
      <Header title="Fulfillment" />

      {isLoading ? (
        <FulfillmentPageSkeleton />
      ) : (
        <main className="flex-1 overflow-y-auto p-7 space-y-6">
          {/* Page heading */}
          <div className="flex items-start justify-between gap-4">
            <div>
              <h1 className="text-xl font-bold text-gray-900">Fulfillment Overview</h1>
              <p className="text-sm text-gray-500 mt-0.5">
                Member-success snapshot across the roster and coaching.
              </p>
            </div>
            <StaleIndicator lastUpdatedAt={lastUpdatedAt} />
          </div>

          {/* Row 1: KPI tiles */}
          <FulfillmentKpiGrid kpis={kpis} />

          {/* Row 2: Tools + Director CTA */}
          <div className="grid grid-cols-2 gap-4">
            <FulfillmentToolsCard />
            <FulfillmentDirectorCtaCard />
          </div>
        </main>
      )}
    </>
  );
}
