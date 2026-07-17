"use client";

import { useEffect, useState } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { apiClient } from "@/lib/api-client";
import { formatCurrency } from "@/lib/format";

// ─── Shared shapes (mirror the page's analytics types) ────────────────────────

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

interface HistoryPoint {
  value: number;
  sample_size: number;
  date: string;
}

interface MetricHistory {
  metric_key: string;
  window: string;
  points: HistoryPoint[];
}

// ─── Window → history spec ────────────────────────────────────────────────────
// The /insights duration toggle controls BOTH the span shown (days, the X-axis
// range) and the rolling-window width per point (roll). Very short spans use a
// tight roll so the line isn't over-smoothed; longer spans average more.
//   7d  → 7 days, 1-day roll (raw daily points)
//   30d → 30 days, 7-day roll (weekly smoothing)
//   90d → 90 days, 30-day roll
//   all → full available history (capped), 30-day roll
const WINDOW_SPEC: Record<string, { days: number; roll: number }> = {
  "7d": { days: 7, roll: 1 },
  "30d": { days: 30, roll: 7 },
  "90d": { days: 90, roll: 30 },
  all: { days: 730, roll: 30 },
};

function historyQuery(window: string): string {
  const spec = WINDOW_SPEC[window] ?? WINDOW_SPEC["90d"];
  return `days=${spec.days}&roll=${spec.roll}`;
}

// ─── Value formatting (kept in sync with the page) ────────────────────────────

function formatValue(v: number | null, unit: string): string {
  if (v === null) return "—";
  if (unit === "ratio") return `${(v * 100).toFixed(1)}%`;
  if (unit === "currency") return formatCurrency(v);
  if (unit === "score") return v.toFixed(2);
  return Math.round(v).toLocaleString();
}

// ─── 1. Per-metric history sparkline ──────────────────────────────────────────

/** A compact area sparkline of a metric's snapshot history over `window`.
 * Self-fetches the derived rolling history (/metrics/{key}/history-asof). Renders nothing visible until it
 * has at least two points — a single point isn't a trend. */
export function MetricSparkline({
  metricKey,
  unit,
  window,
}: {
  metricKey: string;
  unit: string;
  window: string;
}) {
  const [points, setPoints] = useState<HistoryPoint[] | null>(null);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const data = await apiClient.get<MetricHistory>(
          `/analytics/metrics/${encodeURIComponent(metricKey)}/history-asof?${historyQuery(window)}`,
          { silent: true }
        );
        if (!cancelled) setPoints(data.points);
      } catch {
        if (!cancelled) setPoints([]);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [metricKey, window]);

  // Not enough history to draw a line — stay silent rather than show a flat dash.
  if (!points || points.length < 2) return null;

  return (
    <div className="mt-2 h-10 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={points} margin={{ top: 2, bottom: 2, left: 0, right: 0 }}>
          <defs>
            <linearGradient id={`spark-${metricKey}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--accent-500)" stopOpacity={0.3} />
              <stop offset="100%" stopColor="var(--accent-500)" stopOpacity={0} />
            </linearGradient>
          </defs>
          <Tooltip
            cursor={false}
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null;
              const p = payload[0].payload as HistoryPoint;
              return (
                <div className="rounded-md border border-gray-200 bg-white px-2 py-1 shadow-sm">
                  <p className="text-[11px] font-semibold text-gray-900">
                    {formatValue(p.value, unit)}
                  </p>
                  <p className="text-[10px] text-gray-400">{p.date}</p>
                </div>
              );
            }}
          />
          <Area
            type="monotone"
            dataKey="value"
            stroke="var(--accent-500)"
            strokeWidth={1.5}
            fill={`url(#spark-${metricKey})`}
            isAnimationActive={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

// ─── 1b. Historical line chart with metric selector ──────────────────────────

/** Short calendar-date label (e.g. "Jun 3") for the X axis, parsed from an
 * ISO date string without constructing a locale-dependent full Date render. */
function shortDate(iso: string): string {
  // iso is YYYY-MM-DD (or full ISO) — take the date part and format month/day.
  const [, m, d] = iso.slice(0, 10).split("-");
  const months = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
  ];
  const mi = Number(m) - 1;
  if (Number.isNaN(mi) || mi < 0 || mi > 11 || !d) return iso.slice(0, 10);
  return `${months[mi]} ${Number(d)}`;
}

/** A full-size line chart of one metric's snapshot history over `window`, with
 * a dropdown to switch which metric is plotted. Y-axis ticks and the tooltip
 * use the metric's real unit formatting. Self-fetches on metric/window change. */
export function MetricHistoryChart({
  metrics,
  window,
}: {
  metrics: MetricValue[];
  window: string;
}) {
  // Default to the first metric; keep the selection stable across re-renders.
  const [selectedKey, setSelectedKey] = useState<string>("");
  const [points, setPoints] = useState<HistoryPoint[] | null>(null);
  const [loading, setLoading] = useState(false);

  // Pick a sensible default once metrics arrive, and re-home if the selected
  // metric disappears (e.g. an area filter changed upstream).
  useEffect(() => {
    if (metrics.length === 0) {
      setSelectedKey("");
      return;
    }
    if (!metrics.some((m) => m.metric_key === selectedKey)) {
      setSelectedKey(metrics[0].metric_key);
    }
  }, [metrics, selectedKey]);

  const selected = metrics.find((m) => m.metric_key === selectedKey);

  useEffect(() => {
    if (!selectedKey) {
      setPoints(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    void (async () => {
      try {
        const data = await apiClient.get<MetricHistory>(
          `/analytics/metrics/${encodeURIComponent(selectedKey)}/history-asof?${historyQuery(window)}`,
          { silent: true }
        );
        if (!cancelled) setPoints(data.points);
      } catch {
        if (!cancelled) setPoints([]);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [selectedKey, window]);

  const unit = selected?.unit ?? "count";

  // Chart rows carry a short label for the axis; the tooltip reads the raw point.
  const rows = (points ?? []).map((p) => ({ ...p, dateLabel: shortDate(p.date) }));

  return (
    <div>
      {/* Selector row */}
      <div className="mb-3 flex items-center gap-2">
        <label htmlFor="history-metric" className="text-xs font-medium text-gray-500">
          Metric
        </label>
        <select
          id="history-metric"
          value={selectedKey}
          onChange={(e) => setSelectedKey(e.target.value)}
          disabled={metrics.length === 0}
          className="text-sm border border-gray-200 rounded-lg px-3 py-1.5 bg-white text-gray-700 focus:outline-none focus:ring-2 focus:ring-accent-500 focus:border-transparent disabled:opacity-50"
        >
          {metrics.map((m) => (
            <option key={m.metric_key} value={m.metric_key}>
              {m.label}
            </option>
          ))}
        </select>
      </div>

      {loading ? (
        <div className="h-[260px] animate-pulse rounded-lg bg-gray-100" />
      ) : rows.length < 2 ? (
        <div className="flex h-[260px] items-center justify-center">
          <p className="text-xs text-gray-400">
            {rows.length === 0
              ? "No history for this metric yet."
              : "Only one snapshot so far — a line needs at least two points."}
          </p>
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={260}>
          <LineChart data={rows} margin={{ top: 8, right: 16, left: 4, bottom: 4 }}>
            <CartesianGrid stroke="#f3f4f6" vertical={false} />
            <XAxis
              dataKey="dateLabel"
              tick={{ fontSize: 11, fill: "#9ca3af" }}
              axisLine={false}
              tickLine={false}
              minTickGap={24}
            />
            <YAxis
              tick={{ fontSize: 11, fill: "#9ca3af" }}
              axisLine={false}
              tickLine={false}
              width={56}
              tickFormatter={(v: number) => formatValue(v, unit)}
            />
            <Tooltip
              cursor={{ stroke: "#e5e7eb" }}
              content={({ active, payload }) => {
                if (!active || !payload?.length) return null;
                const p = payload[0].payload as HistoryPoint;
                return (
                  <div className="rounded-lg border border-gray-200 bg-white px-3 py-2 shadow-md">
                    <p className="text-xs font-semibold text-gray-900">
                      {formatValue(p.value, unit)}
                    </p>
                    <p className="text-[11px] text-gray-400">{p.date.slice(0, 10)}</p>
                    <p className="text-[11px] text-gray-400">n={p.sample_size}</p>
                  </div>
                );
              }}
            />
            <Line
              type="monotone"
              dataKey="value"
              stroke="var(--accent-500)"
              strokeWidth={2}
              dot={{ r: 2, fill: "var(--accent-500)" }}
              activeDot={{ r: 4 }}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}

// ─── 1c. Multi-metric trend comparison (indexed line chart) ───────────────────

// Distinct categorical line colours — readable on white, well-separated.
const LINE_COLORS = [
  "#2563eb", // blue-600
  "#10b981", // emerald-500
  "#f59e0b", // amber-500
  "#ef4444", // red-500
  "#8b5cf6", // violet-500
  "#0891b2", // cyan-600
];
const MAX_LINES = 6;

/** Overlay several metrics' trajectories on one chart. Because metrics carry
 * mixed units (currency / ratio / score), every series is *indexed to 100* at
 * its first point in the window — so the chart compares relative movement, not
 * absolute magnitude. The tooltip shows both the indexed value and the real
 * formatted value. Each selected metric self-fetches its own history. */
export function MultiMetricTrend({
  metrics,
  window,
}: {
  metrics: MetricValue[];
  window: string;
}) {
  // Which metrics are plotted. Default to the first few; capped at MAX_LINES.
  const [selected, setSelected] = useState<string[]>([]);
  // metric_key -> its fetched history points.
  const [histories, setHistories] = useState<Record<string, HistoryPoint[]>>({});
  const [loading, setLoading] = useState(false);

  // Seed the default selection once metrics arrive; re-home if they change.
  useEffect(() => {
    setSelected((prev) => {
      const stillValid = prev.filter((k) =>
        metrics.some((m) => m.metric_key === k)
      );
      if (stillValid.length > 0) return stillValid;
      return metrics.slice(0, 3).map((m) => m.metric_key);
    });
  }, [metrics]);

  // Fetch history for any selected metric we don't already have, for this window.
  // Re-fetch everything when the window changes (histories keyed only by metric).
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    void (async () => {
      const entries = await Promise.all(
        selected.map(async (key) => {
          try {
            const data = await apiClient.get<MetricHistory>(
              `/analytics/metrics/${encodeURIComponent(key)}/history-asof?${historyQuery(window)}`,
              { silent: true }
            );
            return [key, data.points] as const;
          } catch {
            return [key, [] as HistoryPoint[]] as const;
          }
        })
      );
      if (!cancelled) {
        setHistories(Object.fromEntries(entries));
        setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [selected, window]);

  function toggle(key: string) {
    setSelected((prev) => {
      if (prev.includes(key)) return prev.filter((k) => k !== key);
      if (prev.length >= MAX_LINES) return prev; // hold at the cap
      return [...prev, key];
    });
  }

  // Build a unified, date-aligned row set: one row per distinct date, each
  // selected metric contributing its indexed value (value / first * 100).
  const dateSet = new Set<string>();
  for (const key of selected) {
    for (const p of histories[key] ?? []) dateSet.add(p.date.slice(0, 10));
  }
  const dates = Array.from(dateSet).sort();

  const firstByKey: Record<string, number> = {};
  for (const key of selected) {
    const pts = histories[key] ?? [];
    const firstNonZero = pts.find((p) => p.value !== 0)?.value ?? pts[0]?.value;
    if (firstNonZero) firstByKey[key] = firstNonZero;
  }

  const rows = dates.map((d) => {
    const row: Record<string, number | string> = { date: d };
    for (const key of selected) {
      const pt = (histories[key] ?? []).find((p) => p.date.slice(0, 10) === d);
      const base = firstByKey[key];
      if (pt && base) row[key] = (pt.value / base) * 100;
    }
    return row;
  });

  const metaByKey = Object.fromEntries(metrics.map((m) => [m.metric_key, m]));
  const colorByKey: Record<string, string> = {};
  selected.forEach((key, i) => {
    colorByKey[key] = LINE_COLORS[i % LINE_COLORS.length];
  });

  const enoughData = rows.length >= 2 && selected.length > 0;

  return (
    <div>
      {/* Metric multi-select pills */}
      <div className="mb-3 flex flex-wrap gap-1.5">
        {metrics.map((m) => {
          const on = selected.includes(m.metric_key);
          const atCap = !on && selected.length >= MAX_LINES;
          return (
            <button
              key={m.metric_key}
              type="button"
              onClick={() => toggle(m.metric_key)}
              disabled={atCap}
              className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-medium transition-colors ${
                on
                  ? "border-transparent text-white"
                  : atCap
                    ? "border-gray-200 text-gray-300 cursor-not-allowed"
                    : "border-gray-200 text-gray-600 hover:bg-gray-50"
              }`}
              style={on ? { backgroundColor: colorByKey[m.metric_key] } : undefined}
              title={atCap ? `Up to ${MAX_LINES} metrics at once` : undefined}
            >
              {on && (
                <span className="inline-block h-1.5 w-1.5 rounded-full bg-white/90" />
              )}
              {m.label}
            </button>
          );
        })}
      </div>

      {loading ? (
        <div className="h-[280px] animate-pulse rounded-lg bg-gray-100" />
      ) : !enoughData ? (
        <div className="flex h-[280px] items-center justify-center">
          <p className="text-xs text-gray-400">
            {selected.length === 0
              ? "Select one or more metrics to compare."
              : "Not enough overlapping history yet to draw a comparison."}
          </p>
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={280}>
          <LineChart data={rows} margin={{ top: 8, right: 16, left: 4, bottom: 4 }}>
            <CartesianGrid stroke="#f3f4f6" vertical={false} />
            <XAxis
              dataKey="date"
              tickFormatter={(d: string) => {
                const [, mm, dd] = d.split("-");
                const months = [
                  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
                  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
                ];
                const mi = Number(mm) - 1;
                return mi >= 0 && mi < 12 ? `${months[mi]} ${Number(dd)}` : d;
              }}
              tick={{ fontSize: 11, fill: "#9ca3af" }}
              axisLine={false}
              tickLine={false}
              minTickGap={24}
            />
            <YAxis
              tick={{ fontSize: 11, fill: "#9ca3af" }}
              axisLine={false}
              tickLine={false}
              width={44}
              tickFormatter={(v: number) => `${Math.round(v)}`}
            />
            <Tooltip
              cursor={{ stroke: "#e5e7eb" }}
              content={({ active, payload, label }) => {
                if (!active || !payload?.length) return null;
                return (
                  <div className="rounded-lg border border-gray-200 bg-white px-3 py-2 shadow-md">
                    <p className="mb-1 text-[11px] text-gray-400">{String(label)}</p>
                    {payload.map((entry) => {
                      const key = String(entry.dataKey);
                      const m = metaByKey[key];
                      const indexed = Number(entry.value);
                      // Recover the real value: indexed/100 * baseline.
                      const real =
                        firstByKey[key] != null
                          ? (indexed / 100) * firstByKey[key]
                          : null;
                      return (
                        <p key={key} className="text-xs">
                          <span style={{ color: entry.color as string }}>●</span>{" "}
                          <span className="font-medium text-gray-700">
                            {m?.label ?? key}
                          </span>{" "}
                          <span className="text-gray-900">{Math.round(indexed)}</span>
                          {real != null && m && (
                            <span className="text-gray-400">
                              {" "}
                              ({formatValue(real, m.unit)})
                            </span>
                          )}
                        </p>
                      );
                    })}
                  </div>
                );
              }}
            />
            {selected.map((key) => (
              <Line
                key={key}
                type="monotone"
                dataKey={key}
                stroke={colorByKey[key]}
                strokeWidth={2}
                dot={false}
                connectNulls
                isAnimationActive={false}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      )}

      {enoughData && (
        <p className="mt-2 text-[11px] text-gray-400">
          Each line is indexed to 100 at the window start, so the chart compares
          relative movement across metrics with different units.
        </p>
      )}
    </div>
  );
}

