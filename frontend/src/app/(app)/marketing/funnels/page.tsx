"use client";

import { useEffect, useState } from "react";
import { Header } from "@/components/layout/header";
import { apiClient } from "@/lib/api-client";
import { useAuth } from "@/hooks/use-auth";
import { Skeleton } from "@/components/ui/skeleton";
import { Card, CardHeader, CardBody } from "@/components/ui/card";
import { channelLabel, channelBadgeClasses } from "@/lib/lead-display";

// ─── API response types (GET /funnels/overview — deliverable 3) ────────────

interface FunnelOverviewStage {
  stage: string;
  label: string;
  count: number;
  pct_of_leads: number;
  conversion_from_previous: number | null;
}

interface FunnelChannelRow {
  channel: string;
  platform: string | null;
  reportable: boolean;
  leads: number;
  registered: number;
  watched: number;
  booked_appt: number;
  discovery_held: number;
  closed: number;
  lead_to_close_pct: number;
}

interface FunnelOverviewResponse {
  overall: FunnelOverviewStage[];
  by_channel: FunnelChannelRow[];
  generated_at: string;
}

// ─── Stage bar color ramp — same emerald language as the prior page ─────────

const STAGE_COLORS = [
  { bgClass: "bg-emerald-100", textClass: "text-emerald-800" },
  { bgClass: "bg-emerald-200", textClass: "text-emerald-800" },
  { bgClass: "bg-emerald-300", textClass: "text-emerald-900" },
  { bgClass: "bg-emerald-400", textClass: "text-emerald-900" },
  { bgClass: "bg-emerald-600", textClass: "text-white" },
  { bgClass: "bg-emerald-700", textClass: "text-white" },
];

// ─── Overall funnel visual — horizontal stage bars ──────────────────────────

function FunnelOverviewCard({ stages }: { stages: FunnelOverviewStage[] }) {
  const maxCount = stages.length > 0 ? Math.max(...stages.map((s) => s.count), 1) : 1;

  return (
    <Card>
      <CardHeader
        title="Funnel Stages"
        action={
          <span className="text-xs text-gray-400">
            {stages.length > 0
              ? `${stages[0].label} → ${stages[stages.length - 1].label}`
              : "No data"}
          </span>
        }
      />
      <CardBody>
        {stages.length === 0 ? (
          <p className="text-sm text-gray-400 text-center py-8">
            No lead journey data available for this range.
          </p>
        ) : (
          <div className="flex flex-col items-center gap-1.5">
            {stages.map((stage, index) => {
              const widthPct = maxCount > 0 ? Math.max((stage.count / maxCount) * 100, 20) : 100;
              const colors = STAGE_COLORS[index % STAGE_COLORS.length];

              return (
                <div
                  key={stage.stage}
                  className="flex flex-col items-center w-full"
                  style={{ maxWidth: `${widthPct}%` }}
                >
                  <div className="w-full flex items-center gap-3">
                    <div
                      className={`flex-1 rounded-lg flex items-center justify-center px-4 py-2.5 min-w-0 cursor-default ${colors.bgClass}`}
                    >
                      <span className={`text-xs font-bold tracking-wide truncate ${colors.textClass}`}>
                        {stage.label}
                      </span>
                    </div>
                    <span className="text-xs font-semibold tabular-nums text-gray-700 flex-shrink-0 w-20 text-right">
                      {stage.count.toLocaleString()}
                    </span>
                    <span className="text-[10px] font-medium tabular-nums text-gray-400 flex-shrink-0 w-14 text-right">
                      {stage.pct_of_leads.toFixed(1)}%
                    </span>
                    <span className="text-[10px] font-medium tabular-nums text-gray-400 flex-shrink-0 w-16 text-right">
                      {stage.conversion_from_previous !== null
                        ? `${stage.conversion_from_previous.toFixed(1)}% conv.`
                        : "—"}
                    </span>
                  </div>
                  {index < stages.length - 1 && (
                    <div className="w-px h-1.5 bg-emerald-200" aria-hidden="true" />
                  )}
                </div>
              );
            })}
          </div>
        )}
        <div className="mt-4 flex items-center gap-4 text-[10px] text-gray-400 font-medium uppercase tracking-wide">
          <span>Stage</span>
          <span className="ml-auto w-20 text-right">Count</span>
          <span className="w-14 text-right">% of Leads</span>
          <span className="w-16 text-right">Step Conv.</span>
        </div>
      </CardBody>
    </Card>
  );
}

// ─── Channel breakdown table ─────────────────────────────────────────────────

function ChannelBreakdownCard({ rows }: { rows: FunnelChannelRow[] }) {
  return (
    <Card>
      <CardHeader
        title="Funnel by Channel"
        action={<span className="text-xs text-gray-400">{rows.length} channels</span>}
      />
      <CardBody noPadding>
        {rows.length === 0 ? (
          <p className="text-sm text-gray-400 text-center py-8">
            No channel data available for this range.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm" aria-label="Funnel stage counts by channel">
              <thead>
                <tr className="border-b border-gray-100 bg-gray-50">
                  <th className="text-left px-5 py-3 text-[10px] font-bold uppercase tracking-wider text-gray-500">
                    Channel
                  </th>
                  <th className="text-right px-3 py-3 text-[10px] font-bold uppercase tracking-wider text-gray-500">
                    Leads
                  </th>
                  <th className="text-right px-3 py-3 text-[10px] font-bold uppercase tracking-wider text-gray-500">
                    Registered
                  </th>
                  <th className="text-right px-3 py-3 text-[10px] font-bold uppercase tracking-wider text-gray-500">
                    Watched
                  </th>
                  <th className="text-right px-3 py-3 text-[10px] font-bold uppercase tracking-wider text-gray-500">
                    Booked Appt
                  </th>
                  <th className="text-right px-3 py-3 text-[10px] font-bold uppercase tracking-wider text-gray-500">
                    Discovery Held
                  </th>
                  <th className="text-right px-3 py-3 text-[10px] font-bold uppercase tracking-wider text-gray-500">
                    Closed
                  </th>
                  <th className="text-right px-5 py-3 text-[10px] font-bold uppercase tracking-wider text-gray-500">
                    Lead → Close %
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {rows.map((row) => (
                  <tr key={row.channel} className="hover:bg-gray-50 transition-colors">
                    <td className="px-5 py-3">
                      <span
                        className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-[11px] font-semibold ${channelBadgeClasses(row.channel)}`}
                      >
                        {channelLabel(row.channel)}
                      </span>
                    </td>
                    <td className="px-3 py-3 text-right tabular-nums text-gray-700">
                      {row.leads.toLocaleString()}
                    </td>
                    <td className="px-3 py-3 text-right tabular-nums text-gray-600">
                      {row.registered.toLocaleString()}
                    </td>
                    <td className="px-3 py-3 text-right tabular-nums text-gray-600">
                      {row.watched.toLocaleString()}
                    </td>
                    <td className="px-3 py-3 text-right tabular-nums text-gray-600">
                      {row.booked_appt.toLocaleString()}
                    </td>
                    <td className="px-3 py-3 text-right tabular-nums text-gray-600">
                      {row.discovery_held.toLocaleString()}
                    </td>
                    <td className="px-3 py-3 text-right tabular-nums font-semibold text-gray-900">
                      {row.closed.toLocaleString()}
                    </td>
                    <td className="px-5 py-3 text-right tabular-nums text-gray-700">
                      {row.lead_to_close_pct.toFixed(1)}%
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

// ─── Loading skeleton ─────────────────────────────────────────────────────────

function FunnelsPageSkeleton() {
  return (
    <main className="flex-1 overflow-y-auto p-7 space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <Skeleton className="h-6 w-28" />
          <Skeleton className="h-4 w-96 mt-2" />
        </div>
        <Skeleton className="h-8 w-64" />
      </div>

      <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
          <Skeleton className="h-4 w-28" />
          <Skeleton className="h-3 w-32" />
        </div>
        <div className="px-5 py-6 flex flex-col items-center gap-2">
          {[100, 88, 62, 22, 8, 5].map((w, i) => (
            <Skeleton key={i} className="h-9 rounded-lg" style={{ width: `${w}%` }} />
          ))}
        </div>
      </div>

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
  const [data, setData] = useState<FunnelOverviewResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [entryFrom, setEntryFrom] = useState("");
  const [entryTo, setEntryTo] = useState("");

  useEffect(() => {
    if (authLoading) return;

    let cancelled = false;

    async function fetchData(): Promise<void> {
      setIsLoading(true);
      try {
        const params = new URLSearchParams();
        if (entryFrom) params.set("entry_from", entryFrom);
        if (entryTo) params.set("entry_to", entryTo);
        const qs = params.toString();
        const result = await apiClient.get<FunnelOverviewResponse>(
          `/funnels/overview${qs ? `?${qs}` : ""}`,
          { silent: true },
        );
        if (!cancelled) setData(result);
      } catch {
        // On error, data stays null — page renders with quiet empty states.
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    }

    void fetchData();
    return () => { cancelled = true; };
  }, [authLoading, entryFrom, entryTo]);

  if (isLoading && !data) {
    return (
      <>
        <Header title="Funnels" />
        <FunnelsPageSkeleton />
      </>
    );
  }

  const hasFilters = entryFrom !== "" || entryTo !== "";

  return (
    <>
      <Header title="Funnels" />

      <main className="flex-1 overflow-y-auto p-7 space-y-6">
        {/* Page heading + date range filter */}
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-xl font-bold text-gray-900">Funnels</h1>
            <p className="text-sm text-gray-500 mt-0.5">
              Lead journey stages from entry through close, sliceable by channel.
            </p>
          </div>
          <div className="flex items-center gap-1.5 text-gray-500 flex-shrink-0 mt-1">
            <span className="text-[11px] font-semibold uppercase tracking-wide shrink-0">
              Entered
            </span>
            <input
              type="date"
              aria-label="Entered on or after"
              value={entryFrom}
              max={entryTo || undefined}
              onChange={(e) => setEntryFrom(e.target.value)}
              className="px-2 py-1.5 text-sm border border-gray-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-400 text-gray-600"
            />
            <span className="text-gray-300">–</span>
            <input
              type="date"
              aria-label="Entered on or before"
              value={entryTo}
              min={entryFrom || undefined}
              onChange={(e) => setEntryTo(e.target.value)}
              className="px-2 py-1.5 text-sm border border-gray-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-emerald-500/20 focus:border-emerald-400 text-gray-600"
            />
            {hasFilters && (
              <button
                type="button"
                onClick={() => { setEntryFrom(""); setEntryTo(""); }}
                className="px-2.5 py-1.5 text-sm text-gray-500 hover:text-gray-700 border border-gray-200 rounded-lg bg-white hover:bg-gray-50 transition-colors"
              >
                Clear
              </button>
            )}
          </div>
        </div>

        {/* Row 1: Overall funnel visual */}
        <FunnelOverviewCard stages={data?.overall ?? []} />

        {/* Row 2: Channel breakdown table */}
        <ChannelBreakdownCard rows={data?.by_channel ?? []} />
      </main>
    </>
  );
}
