"use client";

import { useCallback, useEffect, useState } from "react";
import { Header } from "@/components/layout/header";
import { Card, CardHeader, CardBody } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { apiClient } from "@/lib/api-client";
import { useAuth } from "@/hooks/use-auth";
import { showSuccess, showError } from "@/lib/toast";

// ─── Types (mirror /analytics responses) ────────────────────────────────────────

interface MetricValue {
  metric_key: string;
  area: string;
  label: string;
  unit: string;
  higher_is_better: boolean;
  window: string;
  value: number | null;
  sample_size: number | null;
  captured_date: string | null;
}

interface TrendItem {
  metric_key: string;
  verdict: string; // improving | declining | flat | insufficient_data
  rel_change: number | null;
  reason: string;
}

interface Recommendation {
  id: number;
  metric_key: string;
  area: string;
  window: string;
  verdict: string;
  severity: string; // info | warn | critical
  title: string;
  body: string;
  evidence: Record<string, unknown>;
  status: string;
  updated_at: string | null;
}

const WINDOWS = ["7d", "30d", "90d", "all"];

// ─── Formatting ─────────────────────────────────────────────────────────────────

function formatValue(v: number | null, unit: string): string {
  if (v === null) return "—";
  if (unit === "ratio") return `${(v * 100).toFixed(1)}%`;
  if (unit === "currency") return `$${Math.round(v).toLocaleString()}`;
  if (unit === "score") return v.toFixed(2);
  return Math.round(v).toLocaleString();
}

const VERDICT_STYLE: Record<string, { pill: string; label: string }> = {
  improving: { pill: "bg-emerald-50 text-emerald-700", label: "Improving" },
  declining: { pill: "bg-red-50 text-red-700", label: "Declining" },
  flat: { pill: "bg-gray-100 text-gray-500", label: "Flat" },
  insufficient_data: { pill: "bg-amber-50 text-amber-600", label: "Need more data" },
};

const SEVERITY_STYLE: Record<string, string> = {
  critical: "border-red-300 bg-red-50",
  warn: "border-amber-300 bg-amber-50",
  info: "border-emerald-300 bg-emerald-50",
};

const AREA_LABEL: Record<string, string> = {
  sales: "Sales",
  marketing: "Marketing",
  fulfillment: "Fulfillment",
};

// ─── Page ───────────────────────────────────────────────────────────────────────

export default function InsightsPage() {
  const { isLoading: authLoading } = useAuth();
  const [window, setWindow] = useState("30d");
  const [metrics, setMetrics] = useState<MetricValue[]>([]);
  const [trends, setTrends] = useState<Record<string, TrendItem>>({});
  const [recs, setRecs] = useState<Recommendation[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [m, t, r] = await Promise.all([
        apiClient.get<MetricValue[]>(`/analytics/metrics?window=${window}`, { silent: true }),
        apiClient.get<TrendItem[]>(`/analytics/trends?window=${window}`, { silent: true }),
        apiClient.get<Recommendation[]>(`/analytics/recommendations`, { silent: true }),
      ]);
      setMetrics(m);
      setTrends(Object.fromEntries(t.map((x) => [x.metric_key, x])));
      setRecs(r);
    } catch {
      setMetrics([]);
      setTrends({});
      setRecs([]);
    } finally {
      setLoading(false);
    }
  }, [window]);

  useEffect(() => {
    if (authLoading) return;
    void load();
  }, [authLoading, load]);

  async function handleRefresh() {
    setRefreshing(true);
    try {
      await apiClient.post(`/analytics/refresh`, {}, { silent: true });
      await load();
      showSuccess("Recomputed from the latest data.");
    } catch {
      showError("Couldn't refresh.");
    } finally {
      setRefreshing(false);
    }
  }

  async function setStatus(id: number, status: string) {
    try {
      await apiClient.patch<Recommendation>(`/analytics/recommendations/${id}?status=${status}`, {}, { silent: true });
      setRecs((prev) =>
        status === "resolved" ? prev.filter((r) => r.id !== id) : prev.map((r) => (r.id === id ? { ...r, status } : r)),
      );
    } catch {
      showError("Couldn't update.");
    }
  }

  // Group metrics by area for display.
  const byArea = metrics.reduce<Record<string, MetricValue[]>>((acc, m) => {
    (acc[m.area] ??= []).push(m);
    return acc;
  }, {});

  return (
    <>
      <Header title="Insights" />
      <main className="flex-1 overflow-y-auto p-7 space-y-6">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-xl font-bold text-gray-900">Insights</h1>
            <p className="text-sm text-gray-500 mt-0.5">
              What&apos;s working and what needs to change — computed purely from your data.
              Recommendations appear only when the numbers cross a threshold, and each cites its evidence.
            </p>
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            <div className="flex rounded-lg border border-gray-200 overflow-hidden">
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
            <Button variant="ghost" onClick={() => void handleRefresh()} disabled={refreshing}>
              {refreshing ? "Refreshing…" : "↻ Refresh"}
            </Button>
          </div>
        </div>

        {/* Recommendations — the headline findings */}
        <Card>
          <CardHeader title={`Recommendations${recs.length ? ` (${recs.length})` : ""}`} />
          <CardBody className="pt-0">
            {loading ? (
              <p className="text-sm text-gray-400">Loading…</p>
            ) : recs.length === 0 ? (
              <p className="text-[13px] text-gray-500">
                No recommendations yet. The engine only emits a finding when a metric moves materially
                with enough data behind it — none currently cross the threshold. As more daily snapshots
                accrue, trends and recommendations will appear here.
              </p>
            ) : (
              <div className="space-y-3">
                {recs.map((r) => (
                  <div key={r.id} className={`rounded-lg border p-3 ${SEVERITY_STYLE[r.severity] ?? "border-gray-200"}`}>
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-[10px] font-bold uppercase tracking-wider text-gray-500">
                            {AREA_LABEL[r.area] ?? r.area} · {r.severity}
                          </span>
                        </div>
                        <p className="text-sm font-bold text-gray-900 mt-0.5">{r.title}</p>
                        <p className="text-[13px] text-gray-600 mt-1 leading-relaxed">{r.body}</p>
                      </div>
                      <div className="flex flex-col gap-1.5 flex-shrink-0">
                        <button
                          type="button"
                          onClick={() => void setStatus(r.id, "acted")}
                          className="text-[12px] font-medium text-accent-600 hover:text-accent-700 whitespace-nowrap"
                        >
                          Mark acted
                        </button>
                        <button
                          type="button"
                          onClick={() => void setStatus(r.id, "resolved")}
                          className="text-[12px] text-gray-400 hover:text-gray-600 whitespace-nowrap"
                        >
                          Dismiss
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardBody>
        </Card>

        {/* Metrics by area, each with its trend verdict */}
        {loading ? null : Object.keys(byArea).length === 0 ? (
          <Card>
            <CardBody>
              <p className="text-sm text-gray-400">No metrics yet.</p>
            </CardBody>
          </Card>
        ) : (
          Object.entries(byArea).map(([area, items]) => (
            <Card key={area}>
              <CardHeader title={`${AREA_LABEL[area] ?? area} Metrics`} />
              <CardBody className="pt-0">
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                  {items.map((m) => {
                    const t = trends[m.metric_key];
                    const vs = VERDICT_STYLE[t?.verdict ?? "insufficient_data"];
                    return (
                      <div key={m.metric_key} className="rounded-lg border border-gray-200 p-3">
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-[12px] font-medium text-gray-500">{m.label}</span>
                          <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold ${vs.pill}`}>
                            {vs.label}
                          </span>
                        </div>
                        <div className="text-[22px] font-bold text-gray-900 mt-1">
                          {formatValue(m.value, m.unit)}
                        </div>
                        <div className="text-[11px] text-gray-400 mt-0.5">
                          {m.sample_size != null ? `n=${m.sample_size.toLocaleString()}` : "—"}
                          {t?.rel_change != null && Number.isFinite(t.rel_change)
                            ? ` · ${t.rel_change >= 0 ? "+" : ""}${(t.rel_change * 100).toFixed(0)}%`
                            : ""}
                        </div>
                        {t?.reason && (
                          <p className="text-[11px] text-gray-400 mt-1.5 leading-snug">{t.reason}</p>
                        )}
                      </div>
                    );
                  })}
                </div>
              </CardBody>
            </Card>
          ))
        )}
      </main>
    </>
  );
}
