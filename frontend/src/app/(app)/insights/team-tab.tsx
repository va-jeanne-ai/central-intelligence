"use client";

import { Fragment, useCallback, useEffect, useState } from "react";
import { Card, CardHeader, CardBody } from "@/components/ui/card";
import { KpiCard, KpiRow } from "@/components/ui/kpi-card";
import { EmptyState } from "@/components/ui/empty-state";
import { TableSkeleton } from "@/components/ui/skeleton";
import { SuggestionPanel } from "@/components/ui/suggestion-panel";
import { apiClient } from "@/lib/api-client";
import { showError } from "@/lib/toast";
import { RepStatusPill, TrendPill } from "./team-pills";
import {
  CALL_SCORE_KEY,
  CLOSES_KEY,
  OUTBOUND_KEY,
  REVENUE_KEY,
  STRIKES_KEY,
  formatCount,
  formatRelChange,
  formatValue,
  sortRepsByOutboundDesc,
  statusPillVariant,
  weightedTeamCallScore,
  type TeamAnalyticsResponse,
  type TeamRep,
} from "./team-formatting";

const WINDOWS = ["7d", "30d", "90d", "all"];

const AREA_LABEL: Record<string, string> = {
  sales: "Sales",
  marketing: "Marketing",
  fulfillment: "Fulfillment",
};

// ─── Rep detail panel (expandable row content) ─────────────────────────────────

function RepDetailPanel({ rep }: { rep: TeamRep }) {
  const blocks = Object.values(rep.metrics);
  const openRecs = rep.recommendations.filter((r) => r.status !== "resolved");

  return (
    <div className="space-y-4 bg-gray-50 px-4 py-4 sm:px-6">
      {/* Per-metric blocks */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {blocks.map((m) => (
          <div key={m.metric_key} className="rounded-lg border border-gray-200 bg-white p-3">
            <div className="flex items-center justify-between gap-2">
              <span className="text-[11px] font-medium text-gray-500">{m.label}</span>
              <TrendPill verdict={m.verdict} />
            </div>
            <div className="mt-1 text-lg font-bold text-gray-900">{formatValue(m.value, m.unit)}</div>
            <div className="mt-0.5 text-[11px] text-gray-400">
              {m.sample_size != null ? `n=${m.sample_size.toLocaleString()}` : "—"}
              {formatRelChange(m.rel_change) ? ` · ${formatRelChange(m.rel_change)}` : ""}
            </div>
            {m.reason && <p className="mt-1.5 text-[11px] leading-snug text-gray-400">{m.reason}</p>}
          </div>
        ))}
      </div>

      {/* Recommendations, amber SuggestionPanel style */}
      {openRecs.length > 0 && (
        <SuggestionPanel
          title={`Recommendations for ${rep.full_name}`}
          icon="⚠️"
          items={openRecs.map((r) => ({
            title: `${AREA_LABEL[r.area] ?? r.area} · ${r.severity} — ${r.title}`,
            body: r.body,
          }))}
        />
      )}
    </div>
  );
}

// ─── Rep leaderboard table ──────────────────────────────────────────────────────

function RepLeaderboard({ reps, window }: { reps: TeamRep[]; window: string }) {
  const [expandedRepId, setExpandedRepId] = useState<string | null>(null);
  const sorted = sortRepsByOutboundDesc(reps);

  return (
    <Card>
      <CardHeader title="Rep leaderboard" action={<span className="text-[11.5px] text-gray-400">window: {window} · click a row for detail</span>} />
      <CardBody noPadding>
        {sorted.length === 0 ? (
          <div className="p-6">
            <EmptyState
              icon="🧑‍💼"
              title="No reps to show"
              description="No active or probation reps found for this window."
            />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-[12.5px]">
              <thead>
                <tr className="border-b border-gray-100 bg-gray-50">
                  <th className="px-4 py-2.5 text-left text-[10.5px] font-semibold uppercase tracking-wide text-gray-500">Rep</th>
                  <th className="px-4 py-2.5 text-left text-[10.5px] font-semibold uppercase tracking-wide text-gray-500">Status</th>
                  <th className="px-4 py-2.5 text-right text-[10.5px] font-semibold uppercase tracking-wide text-gray-500">Outbound</th>
                  <th className="px-4 py-2.5 text-right text-[10.5px] font-semibold uppercase tracking-wide text-gray-500">Avg score</th>
                  <th className="px-4 py-2.5 text-right text-[10.5px] font-semibold uppercase tracking-wide text-gray-500">Closes</th>
                  <th className="px-4 py-2.5 text-right text-[10.5px] font-semibold uppercase tracking-wide text-gray-500">Revenue</th>
                  <th className="px-4 py-2.5 text-right text-[10.5px] font-semibold uppercase tracking-wide text-gray-500">Strikes</th>
                  <th className="px-4 py-2.5 text-left text-[10.5px] font-semibold uppercase tracking-wide text-gray-500">Trend</th>
                </tr>
              </thead>
              <tbody>
                {sorted.map((rep) => {
                  const outbound = rep.metrics[OUTBOUND_KEY];
                  const score = rep.metrics[CALL_SCORE_KEY];
                  const closes = rep.metrics[CLOSES_KEY];
                  const revenue = rep.metrics[REVENUE_KEY];
                  const strikes = rep.metrics[STRIKES_KEY];
                  const expanded = expandedRepId === rep.rep_id;

                  return (
                    <Fragment key={rep.rep_id}>
                      <tr
                        onClick={() => setExpandedRepId(expanded ? null : rep.rep_id)}
                        className={`cursor-pointer border-b border-gray-100 transition-colors hover:bg-gray-50 ${expanded ? "bg-gray-50" : ""}`}
                      >
                        <td className="px-4 py-2.5">
                          <div className="font-semibold text-gray-900">{rep.full_name}</div>
                          {rep.role && <div className="text-[11px] text-gray-500">{rep.role.replace(/_/g, " ")}</div>}
                        </td>
                        <td className="px-4 py-2.5">
                          <RepStatusPill status={statusPillVariant(rep.status)} />
                        </td>
                        <td className="px-4 py-2.5 text-right tabular-nums text-gray-700">
                          {formatCount(outbound?.value)}
                        </td>
                        <td className="px-4 py-2.5 text-right tabular-nums text-gray-700">
                          {score ? formatValue(score.value, score.unit) : "—"}
                          {score?.sample_size != null && (
                            <span className="ml-1 text-[11px] text-gray-400">(n={score.sample_size.toLocaleString()})</span>
                          )}
                        </td>
                        <td className="px-4 py-2.5 text-right tabular-nums text-gray-700">
                          {formatCount(closes?.value)}
                        </td>
                        <td className="px-4 py-2.5 text-right tabular-nums text-gray-700">
                          {revenue ? formatValue(revenue.value, revenue.unit) : "—"}
                        </td>
                        <td className="px-4 py-2.5 text-right tabular-nums text-gray-700">
                          {formatCount(strikes?.value)}
                        </td>
                        <td className="px-4 py-2.5">
                          <TrendPill verdict={score?.verdict ?? "insufficient_data"} />
                        </td>
                      </tr>
                      {expanded && (
                        <tr className="border-b border-gray-100">
                          <td colSpan={8} className="p-0">
                            <RepDetailPanel rep={rep} />
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </CardBody>
    </Card>
  );
}

// ─── Team tab (top-level) ───────────────────────────────────────────────────────

export function TeamTab() {
  const [window, setWindow] = useState("30d");
  const [data, setData] = useState<TeamAnalyticsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(false);
    try {
      const result = await apiClient.get<TeamAnalyticsResponse>(`/analytics/team?window=${window}`, {
        silent: true,
      });
      setData(result);
    } catch {
      setData(null);
      setError(true);
      showError("Couldn't load the team view.");
    } finally {
      setLoading(false);
    }
  }, [window]);

  useEffect(() => {
    void load();
  }, [load]);

  const reps = data?.reps ?? [];
  const rollup = data?.rollup;
  const teamScore = weightedTeamCallScore(reps);

  return (
    <div className="space-y-6">
      {/* Window select */}
      <div className="flex items-center justify-between gap-4">
        <p className="text-sm text-gray-500">
          Per-rep outbound, call scores, closes, revenue and coaching strikes — computed from the same
          statistical engine as Overview, scoped to each rep.
        </p>
        <div className="flex flex-shrink-0 rounded-lg border border-gray-200 overflow-hidden">
          {WINDOWS.map((w) => (
            <button
              key={w}
              type="button"
              onClick={() => setWindow(w)}
              className={`px-3 py-1.5 text-[13px] font-medium transition-colors ${
                window === w ? "bg-accent-500 text-white" : "bg-white text-gray-600 hover:bg-gray-50"
              }`}
            >
              {w}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <TableSkeleton rows={6} cols={8} />
      ) : error ? (
        <Card>
          <CardBody>
            <EmptyState
              icon="⚠️"
              title="Couldn't load the team view"
              description="Something went wrong reaching the analytics service."
              action={{ label: "Retry", onClick: () => void load() }}
            />
          </CardBody>
        </Card>
      ) : (
        <>
          {/* KPI row */}
          <KpiRow>
            <KpiCard
              label="Team outbound"
              value={formatCount(rollup?.total_outbound ?? null)}
              borderColor="#3B82F6"
              sub={rollup ? `across ${rollup.active_reps} active reps` : undefined}
            />
            <KpiCard
              label="Team avg call score"
              value={teamScore.value !== null ? teamScore.value.toFixed(2) : "—"}
              borderColor="#3B82F6"
              sub={teamScore.totalSamples > 0 ? `${teamScore.totalSamples.toLocaleString()} scored calls` : "No scored calls yet"}
            />
            <KpiCard
              label="Open strikes"
              value={formatCount(rollup?.open_strikes ?? null)}
              borderColor="#3B82F6"
            />
            <KpiCard
              label="Active reps"
              value={rollup ? `${rollup.active_reps}` : "—"}
              borderColor="#3B82F6"
              sub={rollup ? `of ${rollup.total_reps} total` : undefined}
            />
          </KpiRow>

          {/* Rep leaderboard */}
          {reps.length === 0 ? (
            <Card>
              <CardBody>
                <EmptyState
                  icon="🧑‍💼"
                  title="No reps yet"
                  description="Once reps are on the roster and generating activity, they'll show up here."
                  secondaryAction={{ label: "Refresh", onClick: () => void load() }}
                />
              </CardBody>
            </Card>
          ) : (
            <RepLeaderboard reps={reps} window={window} />
          )}
        </>
      )}
    </div>
  );
}
