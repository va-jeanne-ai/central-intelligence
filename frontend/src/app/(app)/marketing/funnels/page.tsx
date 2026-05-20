"use client";

import { useState, useEffect } from "react";
import { Header } from "@/components/layout/header";
import { apiClient } from "@/lib/api-client";
import { useAuth } from "@/hooks/use-auth";
import { Skeleton } from "@/components/ui/skeleton";
import { KpiCard, KpiRow } from "@/components/ui/kpi-card";
import { Card, CardHeader, CardBody } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

// ─── API response types ──────────────────────────────────────────────────────

interface FunnelStageStats {
  funnel_id: string;
  stage: string;
  event_count: number;
  conversion_rate: number | null;
  updated_at: string;
}

interface FunnelData {
  stages: FunnelStageStats[];
  generated_at: string;
}

// ─── KPI data ─────────────────────────────────────────────────────────────────

interface KpiTile {
  label: string;
  value: string;
  sub?: string;
}

function buildKpiTiles(stages: FunnelStageStats[]): KpiTile[] {
  if (stages.length === 0) {
    return [
      { label: "Total Leads", value: "—" },
      { label: "Converted", value: "—" },
      { label: "Conversion Rate", value: "—" },
      { label: "Stages", value: "—" },
    ];
  }
  const topStage = stages.reduce((max, s) => (s.event_count > max.event_count ? s : max), stages[0]);
  const bottomStage = stages.reduce((min, s) => (s.event_count < min.event_count ? s : min), stages[0]);
  const rate = topStage.event_count > 0
    ? ((bottomStage.event_count / topStage.event_count) * 100).toFixed(1)
    : "0";
  return [
    { label: "Top of Funnel", value: topStage.event_count.toLocaleString(), sub: topStage.stage },
    { label: "Converted", value: bottomStage.event_count.toLocaleString(), sub: bottomStage.stage },
    { label: "Overall Conversion", value: `${rate}%` },
    { label: "Stages", value: stages.length.toString() },
  ];
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function groupByFunnel(data: FunnelData | null): Map<string, FunnelStageStats[]> {
  const map = new Map<string, FunnelStageStats[]>();
  if (!data) return map;
  for (const s of data.stages) {
    const arr = map.get(s.funnel_id) ?? [];
    arr.push(s);
    map.set(s.funnel_id, arr);
  }
  return map;
}

function formatFunnelId(id: string): string {
  return id
    .replace(/-/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

// ─── Funnel stage styling ─────────────────────────────────────────────────────

const STAGE_COLORS = [
  { bgClass: "bg-emerald-100", textClass: "text-emerald-800" },
  { bgClass: "bg-emerald-200", textClass: "text-emerald-800" },
  { bgClass: "bg-emerald-300", textClass: "text-emerald-900" },
  { bgClass: "bg-emerald-500", textClass: "text-white" },
  { bgClass: "bg-emerald-700", textClass: "text-white" },
];

// ─── AI suggestion data ───────────────────────────────────────────────────────

interface AiSuggestion {
  dotClass: string;
  title: string;
  description: string;
  estimatedImpact: string;
}

const AI_SUGGESTIONS: AiSuggestion[] = [
  {
    dotClass: "bg-indigo-400",
    title: "Optimize Consideration Stage",
    description:
      "High drop-off detected at the Consideration stage. Review messaging clarity and add social proof to reduce friction.",
    estimatedImpact: "—",
  },
  {
    dotClass: "bg-blue-400",
    title: "Improve Interest Conversion",
    description:
      "Leads stalling at Interest may benefit from targeted nurture sequences and clearer value proposition content.",
    estimatedImpact: "—",
  },
  {
    dotClass: "bg-emerald-500",
    title: "Strengthen Awareness Reach",
    description:
      "Broadening top-of-funnel reach through paid channels could increase total lead volume entering the funnel.",
    estimatedImpact: "—",
  },
];

// ─── Stale data indicator ─────────────────────────────────────────────────────

interface StaleIndicatorProps {
  lastUpdatedAt?: string | null;
}

function StaleIndicator({ lastUpdatedAt }: StaleIndicatorProps) {
  let display = "—";
  if (lastUpdatedAt) {
    try {
      const d = new Date(lastUpdatedAt);
      display = d.toLocaleString(undefined, {
        month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
      });
    } catch {
      display = lastUpdatedAt;
    }
  }

  return (
    <div className="inline-flex items-center gap-1.5 text-xs text-gray-400">
      <svg
        xmlns="http://www.w3.org/2000/svg"
        className="w-3.5 h-3.5 flex-shrink-0"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
      >
        <circle cx="12" cy="12" r="10" />
        <polyline points="12 6 12 12 16 14" />
      </svg>
      <span>
        Last updated:{" "}
        <span className="tabular-nums">{display}</span>
      </span>
    </div>
  );
}

// ─── Funnel visualization card ────────────────────────────────────────────────

function FunnelVisualizationCard({ stages }: { stages: FunnelStageStats[] }) {
  const maxCount = stages.length > 0 ? Math.max(...stages.map((s) => s.event_count)) : 1;

  return (
    <Card>
      <CardHeader
        title="Funnel Stages"
        action={
          <span className="text-xs text-gray-400">
            {stages.length > 0
              ? `${formatFunnelId(stages[0].stage)} to ${formatFunnelId(stages[stages.length - 1].stage)}`
              : "No data"}
          </span>
        }
      />
      <CardBody>
        <div className="flex flex-col items-center gap-1.5">
          {stages.map((stage, index) => {
            const widthPct = maxCount > 0 ? Math.max((stage.event_count / maxCount) * 100, 20) : 100;
            const colors = STAGE_COLORS[index % STAGE_COLORS.length];
            const prevCount = index > 0 ? stages[index - 1].event_count : null;
            const dropOff = prevCount !== null && prevCount > 0
              ? `${((1 - stage.event_count / prevCount) * 100).toFixed(1)}%`
              : null;
            const stageName = stage.stage.replace(/_/g, " ");

            return (
              <div
                key={stage.stage}
                className="flex flex-col items-center w-full group/stage relative"
                style={{ maxWidth: `${widthPct}%` }}
              >
                {/* Hover tooltip */}
                <div className="absolute bottom-full mb-2 left-1/2 -translate-x-1/2 opacity-0 pointer-events-none group-hover/stage:opacity-100 group-hover/stage:pointer-events-auto transition-opacity duration-150 z-10">
                  <div className="bg-gray-900 text-white rounded-lg px-4 py-3 shadow-lg whitespace-nowrap text-xs">
                    <p className="font-bold capitalize text-sm mb-1.5">{stageName}</p>
                    <div className="flex flex-col gap-1 text-gray-300">
                      <span>
                        Count:{" "}
                        <span className="text-white font-semibold tabular-nums">
                          {stage.event_count.toLocaleString()}
                        </span>
                      </span>
                      {stage.conversion_rate !== null && (
                        <span>
                          Conv. Rate:{" "}
                          <span className="text-white font-semibold tabular-nums">
                            {stage.conversion_rate.toFixed(1)}%
                          </span>
                        </span>
                      )}
                      {dropOff !== null && (
                        <span>
                          Drop-off:{" "}
                          <span className="text-red-300 font-semibold tabular-nums">
                            {dropOff}
                          </span>
                        </span>
                      )}
                    </div>
                  </div>
                  {/* Arrow */}
                  <div className="flex justify-center">
                    <div className="w-2 h-2 bg-gray-900 rotate-45 -mt-1" />
                  </div>
                </div>

                {/* Bar + inline stats */}
                <div className="w-full flex items-center gap-3">
                  <div
                    className={`flex-1 rounded-lg flex items-center justify-center px-4 py-2.5 min-w-0 cursor-default ${colors.bgClass}`}
                  >
                    <span className={`text-xs font-bold tracking-wide capitalize truncate ${colors.textClass}`}>
                      {stageName}
                    </span>
                  </div>
                  <span className="text-xs font-semibold tabular-nums text-gray-700 flex-shrink-0">
                    {stage.event_count.toLocaleString()}
                  </span>
                  {stage.conversion_rate !== null && (
                    <span className="text-[10px] font-medium tabular-nums text-gray-400 flex-shrink-0">
                      {stage.conversion_rate.toFixed(1)}%
                    </span>
                  )}
                </div>
                {index < stages.length - 1 && (
                  <div className="w-px h-1.5 bg-emerald-200" aria-hidden="true" />
                )}
              </div>
            );
          })}
        </div>
        <div className="mt-4 flex items-center gap-4 text-[10px] text-gray-400 font-medium uppercase tracking-wide">
          <span>Stage</span>
          <span className="ml-auto">Count</span>
          <span>Conv. Rate</span>
        </div>
      </CardBody>
    </Card>
  );
}

// ─── Funnel performance table card ────────────────────────────────────────────

function FunnelPerformanceCard({ stages }: { stages: FunnelStageStats[] }) {
  return (
    <Card>
      <CardHeader
        title="Funnel Performance"
        action={<span className="text-xs text-gray-400">{stages.length} stages</span>}
      />
      <CardBody noPadding>
        <table className="w-full text-sm" aria-label="Funnel performance by stage">
          <thead>
            <tr className="border-b border-gray-100 bg-gray-50">
              <th className="text-left px-5 py-3 text-[10px] font-bold uppercase tracking-wider text-gray-500">
                Stage
              </th>
              <th className="text-right px-5 py-3 text-[10px] font-bold uppercase tracking-wider text-gray-500">
                Events
              </th>
              <th className="text-right px-5 py-3 text-[10px] font-bold uppercase tracking-wider text-gray-500">
                Conv. Rate
              </th>
              <th className="text-right px-5 py-3 text-[10px] font-bold uppercase tracking-wider text-gray-500">
                Drop-off
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {stages.map((stage, index) => {
              const prevCount = index > 0 ? stages[index - 1].event_count : null;
              const dropOff = prevCount !== null && prevCount > 0
                ? `${((1 - stage.event_count / prevCount) * 100).toFixed(1)}%`
                : "—";
              return (
                <tr key={stage.stage} className="hover:bg-gray-50 transition-colors">
                  <td className="px-5 py-3 text-sm font-medium text-gray-800 capitalize">
                    {stage.stage.replace(/_/g, " ")}
                  </td>
                  <td className="px-5 py-3 text-sm text-right tabular-nums text-gray-600">
                    {stage.event_count.toLocaleString()}
                  </td>
                  <td className="px-5 py-3 text-sm text-right tabular-nums text-gray-600">
                    {stage.conversion_rate !== null ? `${stage.conversion_rate.toFixed(1)}%` : "—"}
                  </td>
                  <td className="px-5 py-3 text-sm text-right tabular-nums text-gray-600">
                    {dropOff}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </CardBody>
    </Card>
  );
}

// ─── AI optimization suggestions card ────────────────────────────────────────

function AiOptimizationCard() {
  return (
    <Card>
      <CardHeader
        title="AI Optimization Suggestions"
        action={<span className="text-xs text-gray-400">3 recommendations</span>}
      />
      <CardBody noPadding>
        <div className="divide-y divide-gray-100">
          {AI_SUGGESTIONS.map((suggestion) => (
            <div key={suggestion.title} className="px-5 py-4 flex items-start gap-3">
              <span
                className={`mt-1.5 w-2 h-2 rounded-full flex-shrink-0 ${suggestion.dotClass}`}
                aria-hidden="true"
              />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-semibold text-gray-900">
                  {suggestion.title}
                </p>
                <p className="text-xs text-gray-500 mt-0.5 leading-relaxed">
                  {suggestion.description}
                </p>
                <p className="text-[10px] font-bold uppercase tracking-wider text-gray-400 mt-1.5">
                  Est. Impact:{" "}
                  <span className="tabular-nums">{suggestion.estimatedImpact}</span>
                </p>
              </div>
            </div>
          ))}
        </div>
        <div className="px-5 py-4 border-t border-gray-100 bg-emerald-50">
          <Button variant="primary" href="#">
            Generate Analysis
          </Button>
        </div>
      </CardBody>
    </Card>
  );
}

// ─── Loading skeleton ─────────────────────────────────────────────────────────

function FunnelsPageSkeleton() {
  return (
    <main className="flex-1 overflow-y-auto p-7 space-y-6">
      {/* Heading skeleton */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <Skeleton className="h-6 w-28" />
          <Skeleton className="h-4 w-96 mt-2" />
        </div>
        <Skeleton className="h-4 w-36" />
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

      {/* Funnel visualization + AI suggestions skeleton */}
      <div className="grid grid-cols-2 gap-4">
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
          <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
            <Skeleton className="h-4 w-28" />
            <Skeleton className="h-3 w-32" />
          </div>
          <div className="px-5 py-6 flex flex-col items-center gap-2">
            {[100, 80, 60, 40, 20].map((w) => (
              <Skeleton key={w} className="h-9 rounded-lg" style={{ width: `${w}%` }} />
            ))}
          </div>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
          <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
            <Skeleton className="h-4 w-44" />
            <Skeleton className="h-3 w-28" />
          </div>
          <div className="divide-y divide-gray-100">
            {[1, 2, 3].map((i) => (
              <div key={i} className="px-5 py-4 flex items-start gap-3">
                <Skeleton className="w-2 h-2 rounded-full mt-1.5" />
                <div className="flex-1 space-y-1.5">
                  <Skeleton className="h-4 w-40" />
                  <Skeleton className="h-3 w-full" />
                  <Skeleton className="h-3 w-24" />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Performance table skeleton */}
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
          <Skeleton className="h-4 w-36" />
          <Skeleton className="h-3 w-20" />
        </div>
        <div className="divide-y divide-gray-100">
          {[1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="flex items-center gap-4 px-5 py-3">
              <Skeleton className="h-4 w-28" />
              <Skeleton className="h-4 w-14 ml-auto" />
              <Skeleton className="h-4 w-14" />
              <Skeleton className="h-4 w-14" />
            </div>
          ))}
        </div>
      </div>
    </main>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function FunnelsPage() {
  const { isLoading: authLoading } = useAuth();
  const [data, setData] = useState<FunnelData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedFunnel, setSelectedFunnel] = useState<string | null>(null);

  useEffect(() => {
    if (authLoading) return;

    let cancelled = false;

    async function fetchData(): Promise<void> {
      try {
        const result = await apiClient.get<FunnelData>("/funnels", {
          silent: true,
        });
        if (!cancelled) {
          setData(result);
          // Auto-select the first funnel
          const funnelIds = Array.from(new Set(result.stages.map((s) => s.funnel_id)));
          if (funnelIds.length > 0 && !selectedFunnel) {
            setSelectedFunnel(funnelIds[0]);
          }
        }
      } catch {
        // On error, data stays null — page renders with "—" fallbacks.
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    }

    void fetchData();
    return () => { cancelled = true; };
  }, [authLoading]);

  const funnelMap = groupByFunnel(data);
  const funnelIds = Array.from(funnelMap.keys());
  const activeStages = selectedFunnel ? (funnelMap.get(selectedFunnel) ?? []) : [];
  const kpiTiles = buildKpiTiles(activeStages);

  if (isLoading) {
    return (
      <>
        <Header title="Funnels" />
        <FunnelsPageSkeleton />
      </>
    );
  }

  return (
    <>
      <Header title="Funnels" />

      <main className="flex-1 overflow-y-auto p-7 space-y-6">
        {/* Page heading + funnel selector + stale indicator */}
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-xl font-bold text-gray-900">Funnels</h1>
            <p className="text-sm text-gray-500 mt-0.5">
              Funnel stage metrics, conversion rates, and AI-driven optimization
              recommendations.
            </p>
          </div>
          <div className="flex items-center gap-4 flex-shrink-0 mt-1">
            {funnelIds.length > 1 && (
              <select
                value={selectedFunnel ?? ""}
                onChange={(e) => setSelectedFunnel(e.target.value)}
                className="text-sm border border-gray-200 rounded-lg px-3 py-1.5 bg-white text-gray-700 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent"
              >
                {funnelIds.map((id) => (
                  <option key={id} value={id}>
                    {formatFunnelId(id)}
                  </option>
                ))}
              </select>
            )}
            <StaleIndicator lastUpdatedAt={data?.generated_at ?? null} />
          </div>
        </div>

        {/* Row 1: KPI tiles */}
        <section aria-label="Funnel KPIs">
          <KpiRow>
            <KpiCard label={kpiTiles[0].label} value={kpiTiles[0].value} sub={kpiTiles[0].sub} borderColor="#10B981" />
            <KpiCard label={kpiTiles[1].label} value={kpiTiles[1].value} sub={kpiTiles[1].sub} borderColor="#6366F1" />
            <KpiCard label={kpiTiles[2].label} value={kpiTiles[2].value} sub={kpiTiles[2].sub} borderColor="#3B82F6" />
            <KpiCard label={kpiTiles[3].label} value={kpiTiles[3].value} sub={kpiTiles[3].sub} borderColor="#F97316" />
          </KpiRow>
        </section>

        {/* Row 2: Funnel visualization + AI suggestions */}
        <div className="grid grid-cols-2 gap-4">
          <FunnelVisualizationCard stages={activeStages} />
          <AiOptimizationCard />
        </div>

        {/* Row 3: Funnel performance table */}
        <FunnelPerformanceCard stages={activeStages} />
      </main>
    </>
  );
}
