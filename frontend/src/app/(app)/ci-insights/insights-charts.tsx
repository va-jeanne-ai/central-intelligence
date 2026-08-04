"use client";

import {
  Bar,
  BarChart,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import type { CIInsightDistribution } from "@/types";

// ─── Colour tokens ────────────────────────────────────────────────────────────
// Insight-type hues mirror the pill colours on the list (rose/blue/orange/
// green/purple/yellow) so a "Pain" slice reads as the same colour as a "Pain"
// pill. Unknown types fall back to slate.

const INSIGHT_TYPE_COLORS: Record<string, string> = {
  Pain: "#e11d48", // rose-600
  Goal: "#2563eb", // blue-600
  Objection: "#ea580c", // orange-600
  Win: "#16a34a", // green-600
  Breakthrough: "#9333ea", // purple-600
  "False Belief": "#ca8a04", // yellow-600
};
const FALLBACK_COLOR = "#64748b"; // slate-500

function typeColor(label: string): string {
  return INSIGHT_TYPE_COLORS[label] ?? FALLBACK_COLOR;
}

// Signal-strength keeps the page's traffic-light semantics.
const STRENGTH_COLORS: Record<string, string> = {
  Strong: "#22c55e", // green-500
  Moderate: "#facc15", // yellow-400
  Weak: "#9ca3af", // gray-400
};

// A calm emerald-leaning sequence for the signal-family bars, which have no
// fixed semantic colour. Cycled by index.
const FAMILY_SEQUENCE = [
  "#059669",
  "#0d9488",
  "#0891b2",
  "#2563eb",
  "#7c3aed",
  "#c026d3",
  "#db2777",
  "#ea580c",
];

// Source bars — blue-leaning sequence, visually distinct from the emerald
// family bars and purple pain layers. Cycled by index (labels are an open
// set: "Call · Discovery", "Call · Sales", …, "Other").
const SOURCE_SEQUENCE = [
  "#2563eb",
  "#0891b2",
  "#0d9488",
  "#7c3aed",
  "#db2777",
  "#64748b",
];

// ─── Shared tooltip ───────────────────────────────────────────────────────────

interface TooltipDatum {
  payload: { label?: string; signal?: string; mentions: number; count?: number };
}

function ChartTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: TooltipDatum[];
}) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  const name = d.label ?? d.signal ?? "";
  return (
    <div className="rounded-lg border border-gray-200 bg-white px-3 py-2 shadow-md">
      <p className="text-xs font-semibold text-gray-900">{name}</p>
      <p className="text-xs text-gray-500">
        <span className="font-medium text-gray-700">{d.mentions}</span> mentions
        {typeof d.count === "number" && (
          <>
            {" · "}
            <span className="font-medium text-gray-700">{d.count}</span> insights
          </>
        )}
      </p>
    </div>
  );
}

// ─── Empty placeholder ────────────────────────────────────────────────────────

function ChartEmpty() {
  return (
    <div className="flex h-[220px] items-center justify-center">
      <p className="text-xs text-gray-400">No data for the current filters.</p>
    </div>
  );
}

// ─── Loading skeleton ─────────────────────────────────────────────────────────

function ChartSkeleton() {
  return <div className="h-[220px] animate-pulse rounded-lg bg-gray-100" />;
}

// ─── Individual charts ────────────────────────────────────────────────────────

/** Donut of insight-type share, coloured to match the list pills. */
function InsightTypeDonut({ data }: { data: CIInsightDistribution["by_insight_type"] }) {
  if (data.length === 0) return <ChartEmpty />;
  return (
    <ResponsiveContainer width="100%" height={220}>
      <PieChart>
        <Pie
          data={data}
          dataKey="mentions"
          nameKey="label"
          innerRadius={55}
          outerRadius={85}
          paddingAngle={2}
          stroke="none"
        >
          {data.map((d) => (
            <Cell key={d.label} fill={typeColor(d.label)} />
          ))}
        </Pie>
        <Tooltip content={<ChartTooltip />} />
      </PieChart>
    </ResponsiveContainer>
  );
}

/** Horizontal bars for signal-family mentions. */
function SignalFamilyBars({ data }: { data: CIInsightDistribution["by_signal_family"] }) {
  if (data.length === 0) return <ChartEmpty />;
  // Cap to the densest 8 so the axis stays legible.
  const rows = data.slice(0, 8);
  return (
    <ResponsiveContainer width="100%" height={Math.max(220, rows.length * 34)}>
      <BarChart data={rows} layout="vertical" margin={{ left: 12, right: 16 }}>
        <XAxis type="number" hide />
        <YAxis
          type="category"
          dataKey="label"
          width={120}
          tick={{ fontSize: 11, fill: "#6b7280" }}
          axisLine={false}
          tickLine={false}
        />
        <Tooltip cursor={{ fill: "#f9fafb" }} content={<ChartTooltip />} />
        <Bar dataKey="mentions" radius={[0, 4, 4, 0]} maxBarSize={22}>
          {rows.map((d, i) => (
            <Cell key={d.label} fill={FAMILY_SEQUENCE[i % FAMILY_SEQUENCE.length]} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

/** Signal-strength distribution as traffic-light bars. */
function SignalStrengthBars({
  data,
}: {
  data: CIInsightDistribution["by_signal_strength"];
}) {
  if (data.length === 0) return <ChartEmpty />;
  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={data} margin={{ top: 8, left: -16, right: 8 }}>
        <XAxis
          dataKey="label"
          tick={{ fontSize: 11, fill: "#6b7280" }}
          axisLine={false}
          tickLine={false}
        />
        <YAxis
          tick={{ fontSize: 11, fill: "#9ca3af" }}
          axisLine={false}
          tickLine={false}
          allowDecimals={false}
        />
        <Tooltip cursor={{ fill: "#f9fafb" }} content={<ChartTooltip />} />
        <Bar dataKey="mentions" radius={[4, 4, 0, 0]} maxBarSize={64}>
          {data.map((d) => (
            <Cell key={d.label} fill={STRENGTH_COLORS[d.label] ?? FALLBACK_COLOR} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

/** Top signals by total mentions — coloured by their insight type. */
function TopSignalsBars({ data }: { data: CIInsightDistribution["top_signals"] }) {
  if (data.length === 0) return <ChartEmpty />;
  return (
    <ResponsiveContainer width="100%" height={Math.max(260, data.length * 30)}>
      <BarChart data={data} layout="vertical" margin={{ left: 12, right: 16 }}>
        <XAxis type="number" hide />
        <YAxis
          type="category"
          dataKey="signal"
          width={200}
          tick={{ fontSize: 11, fill: "#6b7280" }}
          axisLine={false}
          tickLine={false}
        />
        <Tooltip cursor={{ fill: "#f9fafb" }} content={<ChartTooltip />} />
        <Bar dataKey="mentions" radius={[0, 4, 4, 0]} maxBarSize={20}>
          {data.map((d) => (
            <Cell key={d.signal} fill={typeColor(d.insight_type ?? "")} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

// A cool violet-leaning sequence for pain-layer bars — distinct from the
// signal-family greens so the two horizontal-bar charts read as different
// dimensions even side by side.
const PAIN_LAYER_SEQUENCE = [
  "#7c3aed",
  "#9333ea",
  "#c026d3",
  "#db2777",
  "#e11d48",
  "#f97316",
  "#ca8a04",
];

/** Horizontal bars for pain-layer mentions — which "layer" of the pain
 * (structural, emotional, identity, belief, etc.) shows up most often. */
function PainLayerBars({ data }: { data: CIInsightDistribution["by_pain_layer"] }) {
  if (data.length === 0) return <ChartEmpty />;
  return (
    <ResponsiveContainer width="100%" height={Math.max(220, data.length * 34)}>
      <BarChart data={data} layout="vertical" margin={{ left: 12, right: 16 }}>
        <XAxis type="number" hide />
        <YAxis
          type="category"
          dataKey="label"
          width={120}
          tick={{ fontSize: 11, fill: "#6b7280" }}
          axisLine={false}
          tickLine={false}
        />
        <Tooltip cursor={{ fill: "#f9fafb" }} content={<ChartTooltip />} />
        <Bar dataKey="mentions" radius={[0, 4, 4, 0]} maxBarSize={22}>
          {data.map((d, i) => (
            <Cell key={d.label} fill={PAIN_LAYER_SEQUENCE[i % PAIN_LAYER_SEQUENCE.length]} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

/** Horizontal bars for insight sources — which calls (by call type) the
 * filtered insights were extracted from. Same visual pattern as the
 * pain-layer bars; reacts to the page's filter bar like every other chart. */
function SourceBars({ data }: { data: NonNullable<CIInsightDistribution["by_source"]> }) {
  if (data.length === 0) return <ChartEmpty />;
  return (
    <ResponsiveContainer width="100%" height={Math.max(220, data.length * 34)}>
      <BarChart data={data} layout="vertical" margin={{ left: 12, right: 16 }}>
        <XAxis type="number" hide />
        <YAxis
          type="category"
          dataKey="label"
          width={120}
          tick={{ fontSize: 11, fill: "#6b7280" }}
          axisLine={false}
          tickLine={false}
        />
        <Tooltip cursor={{ fill: "#f9fafb" }} content={<ChartTooltip />} />
        <Bar dataKey="count" radius={[0, 4, 4, 0]} maxBarSize={22}>
          {data.map((d, i) => (
            <Cell key={d.label} fill={SOURCE_SEQUENCE[i % SOURCE_SEQUENCE.length]} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

// ─── Legend (shared for the donut) ────────────────────────────────────────────

function TypeLegend({ data }: { data: CIInsightDistribution["by_insight_type"] }) {
  if (data.length === 0) return null;
  return (
    <ul className="mt-3 flex flex-wrap gap-x-4 gap-y-1">
      {data.map((d) => (
        <li key={d.label} className="flex items-center gap-1.5 text-xs text-gray-600">
          <span
            className="inline-block h-2.5 w-2.5 rounded-sm"
            style={{ backgroundColor: typeColor(d.label) }}
            aria-hidden="true"
          />
          {d.label}
          <span className="text-gray-400">({d.mentions})</span>
        </li>
      ))}
    </ul>
  );
}

// ─── Public grid ──────────────────────────────────────────────────────────────

/** The full charts grid for the CI Insights page. Renders skeletons while
 * loading and an empty placeholder per chart when a distribution is empty. */
export function InsightsCharts({
  data,
  isLoading,
}: {
  data: CIInsightDistribution | null;
  isLoading: boolean;
}) {
  return (
    <section aria-label="CI Insights charts" className="grid grid-cols-1 gap-5 lg:grid-cols-2">
      {/* Insight-type donut */}
      <Card>
        <CardHeader title="Insight type mix" />
        <CardBody>
          {isLoading || !data ? (
            <ChartSkeleton />
          ) : (
            <>
              <InsightTypeDonut data={data.by_insight_type} />
              <TypeLegend data={data.by_insight_type} />
            </>
          )}
        </CardBody>
      </Card>

      {/* Signal-strength bars */}
      <Card>
        <CardHeader title="Signal strength" />
        <CardBody>
          {isLoading || !data ? (
            <ChartSkeleton />
          ) : (
            <SignalStrengthBars data={data.by_signal_strength} />
          )}
        </CardBody>
      </Card>

      {/* Signal-family bars */}
      <Card>
        <CardHeader title="Top signal families" />
        <CardBody>
          {isLoading || !data ? (
            <ChartSkeleton />
          ) : (
            <SignalFamilyBars data={data.by_signal_family} />
          )}
        </CardBody>
      </Card>

      {/* Pain-layer bars */}
      <Card>
        <CardHeader title="Pain layer breakdown" />
        <CardBody>
          {isLoading || !data ? (
            <ChartSkeleton />
          ) : (
            <PainLayerBars data={data.by_pain_layer} />
          )}
        </CardBody>
      </Card>

      {/* Source bars — where the insights come from (call types today) */}
      <Card>
        <CardHeader
          title="Insight sources"
          action={<span className="text-xs text-gray-400">by insight count</span>}
        />
        <CardBody>
          {isLoading || !data ? (
            <ChartSkeleton />
          ) : (
            <SourceBars data={data.by_source ?? []} />
          )}
        </CardBody>
      </Card>

      {/* Top signals bars */}
      <Card>
        <CardHeader title="Most-mentioned signals" />
        <CardBody>
          {isLoading || !data ? (
            <ChartSkeleton />
          ) : (
            <TopSignalsBars data={data.top_signals} />
          )}
        </CardBody>
      </Card>
    </section>
  );
}
