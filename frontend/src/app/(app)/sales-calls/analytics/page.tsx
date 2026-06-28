"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Header } from "@/components/layout/header";
import { apiClient } from "@/lib/api-client";
import { useAuth } from "@/hooks/use-auth";

// ─── Types (bound to /ci/calls/analytics) ───────────────────────────────────────

interface TimeBucket {
  label: string;
  value: number;
}
interface LabeledCount {
  label: string;
  count: number;
}
interface CallAnalytics {
  calls_by_month: TimeBucket[];
  result_breakdown: LabeledCount[];
  top_pain_points: LabeledCount[];
  top_call_owners: LabeledCount[];
}

const EMPTY: CallAnalytics = {
  calls_by_month: [],
  result_breakdown: [],
  top_pain_points: [],
  top_call_owners: [],
};

// Result → bar color, matching the status pills on the calls page.
function resultColor(label: string): string {
  const l = label.toLowerCase();
  if (/booked|won|sale|sold/.test(l)) return "#10B981";
  if (/follow.?up|scheduled/.test(l)) return "#8B5CF6";
  if (/no.?show/.test(l)) return "#9CA3AF";
  if (/not.?qualified|no.?sale|lost/.test(l)) return "#EF4444";
  if (/pending|processing/.test(l)) return "#F59E0B";
  return "#6B7280";
}

// ─── Calls-per-month bar chart (with hover values) ──────────────────────────────

function MonthlyBars({ data }: { data: TimeBucket[] }) {
  const [hovered, setHovered] = useState<number | null>(null);
  const max = Math.max(...data.map((d) => d.value), 1);

  if (data.length === 0) {
    return <p className="text-sm text-gray-400">No data.</p>;
  }

  return (
    <div className="flex items-end gap-3 h-44 pt-6">
      {data.map((d, i) => {
        const heightPercent = Math.round((d.value / max) * 100);
        const isHovered = hovered === i;
        return (
          <div
            key={i}
            className="relative flex-1 h-full flex flex-col items-center justify-end"
            onMouseEnter={() => setHovered(i)}
            onMouseLeave={() => setHovered(null)}
          >
            {isHovered && (
              <div className="pointer-events-none absolute -top-1 z-10 rounded-md bg-gray-800 px-2 py-1 text-[11px] font-semibold text-white shadow-md">
                {d.value.toLocaleString()}
              </div>
            )}
            <div
              className={`w-full rounded-t-md cursor-pointer transition-all duration-150 origin-bottom ${
                isHovered ? "bg-accent-500 scale-y-105" : "bg-accent-400"
              }`}
              style={{ height: `${heightPercent}%`, minHeight: d.value > 0 ? 4 : 0 }}
              aria-hidden
            />
            <span className="mt-2 text-[11px] text-gray-400">{d.label}</span>
          </div>
        );
      })}
    </div>
  );
}

// ─── Horizontal bar list (result breakdown / top owners) ────────────────────────

function BarList({
  items,
  colorFor,
}: {
  items: LabeledCount[];
  colorFor?: (label: string) => string;
}) {
  const max = Math.max(...items.map((i) => i.count), 1);
  if (items.length === 0) return <p className="text-sm text-gray-400">No data.</p>;
  return (
    <div className="space-y-2.5">
      {items.map((item) => (
        <div key={item.label} className="flex items-center gap-3">
          <span className="w-36 flex-shrink-0 truncate text-[13px] text-gray-600" title={item.label}>
            {item.label}
          </span>
          <div className="flex-1 h-5 rounded bg-gray-100 overflow-hidden">
            <div
              className="h-full rounded transition-all duration-500"
              style={{
                width: `${Math.max((item.count / max) * 100, 4)}%`,
                backgroundColor: colorFor ? colorFor(item.label) : "#3B82F6",
              }}
            />
          </div>
          <span className="w-10 flex-shrink-0 text-right text-[13px] font-semibold text-gray-700 tabular-nums">
            {item.count}
          </span>
        </div>
      ))}
    </div>
  );
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5">
      <h2 className="text-sm font-bold text-gray-900 mb-4">{title}</h2>
      {children}
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function SalesCallsAnalyticsPage() {
  const router = useRouter();
  const { isLoading: authLoading } = useAuth();
  const [data, setData] = useState<CallAnalytics>(EMPTY);
  const [isLoading, setIsLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const d = await apiClient.get<CallAnalytics>("/ci/calls/analytics", { silent: true });
      setData(d);
    } catch {
      /* leave empties */
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (authLoading) return;
    void load();
  }, [authLoading, load]);

  return (
    <>
      <Header title="Sales Calls Analytics" />

      <main className="flex-1 overflow-y-auto p-7 space-y-6">
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => router.push("/sales-calls")}
            className="inline-flex items-center gap-1.5 rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm font-semibold text-gray-700 hover:bg-gray-50 transition-colors"
          >
            ← Sales Calls
          </button>
          <h1 className="text-xl font-bold text-gray-900">Analytics</h1>
        </div>

        {isLoading ? (
          <p className="text-sm text-gray-400">Loading analytics…</p>
        ) : (
          <>
            <Card title="Calls per Month — Last 6 Months">
              <MonthlyBars data={data.calls_by_month} />
            </Card>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <Card title="Call Result Breakdown">
                <BarList items={data.result_breakdown} colorFor={resultColor} />
              </Card>
              <Card title="Most Active Call Owners">
                <BarList items={data.top_call_owners} />
              </Card>
            </div>

            <Card title="Top Pain-Point Signals">
              <BarList items={data.top_pain_points} colorFor={() => "#F97316"} />
            </Card>
          </>
        )}
      </main>
    </>
  );
}
