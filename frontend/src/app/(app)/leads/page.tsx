"use client";

import { useState, useEffect, useMemo, useRef } from "react";
import { useRouter } from "next/navigation";
import { Header } from "@/components/layout/header";
import { Skeleton } from "@/components/ui/skeleton";
import { AnalyzeViewButton } from "@/components/analyze/AnalyzeViewButton";
import { AnalyzeViewDrawer } from "@/components/analyze/AnalyzeViewDrawer";
import type { Lead, LeadStatus, LeadSource } from "@/types";
import { apiClient } from "@/lib/api-client";
import { useAuth } from "@/hooks/use-auth";
import { usePagination } from "@/hooks/use-pagination";
import { Pagination } from "@/components/ui";
import {
  STATUS_CONFIG,
  SOURCE_CONFIG,
  resolveSource,
  resolveStatus,
  channelLabel,
  channelBadgeClasses,
} from "@/lib/lead-display";

// ─── API response types ───────────────────────────────────────────────────────

interface LeadsListResponse {
  leads: Lead[];
  total: number;
  page: number;
  per_page: number;
}

interface LeadsStatsResponse {
  kpis: {
    total_leads: number; // scoped to the selected entry-date range
    all_time_total: number; // unscoped total, headline of the Total Leads card
    leads_this_week: number;
    conversion_rate: number;
    active_applications: number;
    avg_deal_value: number; // avg amount_collected per closed sale (in range)
  };
  lead_volume: { label: string; value: number }[];
  // `source` is transitional (source === channel today, per Task 3/4 notes);
  // the donut now reads `channel`, the canonical attribution bucket label.
  // `platform`/`reportable` aren't rendered yet but are part of the contract.
  source_breakdown: {
    source: string;
    channel: string;
    platform: string | null;
    reportable: boolean;
    count: number;
    percentage: number;
  }[];
  funnel: { stage: string; count: number; percentage: number }[];
  // Distinct provenance `source` values present in the DB (lowercased,
  // count-desc) — drives the Source filter dropdown so its options always
  // reflect real data (e.g. 'wgr') instead of the hardcoded legacy enum.
  available_sources: string[];
}

// ─── Color maps ───────────────────────────────────────────────────────────────

const SOURCE_COLORS: Record<string, string> = {
  webinar: "#F59E0B",
  vsl: "#3B82F6",
  "opt-in": "#10B981",
  ads: "#9CA3AF",
  referral: "#8B5CF6",
  other: "#6B7280",
};

const FUNNEL_COLORS: Record<string, string> = {
  Leads: "#3B82F6",
  Appointments: "#8B5CF6",
  Applications: "#F59E0B",
  Sales: "#10B981",
};

// ─── Helpers ──────────────────────────────────────────────────────────────────

function formatNumber(n: number): string {
  return n.toLocaleString("en-US");
}

/** Current week as YYYY-MM-DD bounds, Monday→Sunday (local time). */
function currentWeekRange(): { from: string; to: string } {
  const iso = (d: Date) =>
    `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  const now = new Date();
  const dow = (now.getDay() + 6) % 7; // 0 = Monday
  const monday = new Date(now);
  monday.setDate(now.getDate() - dow);
  const sunday = new Date(monday);
  sunday.setDate(monday.getDate() + 6);
  return { from: iso(monday), to: iso(sunday) };
}

/** "Jun 22 – Jun 28, 2026" style label for a YYYY-MM-DD range (or "All time"). */
function rangeLabel(from: string, to: string): string {
  if (!from && !to) return "All time";
  const fmt = (s: string) =>
    s
      ? new Date(`${s}T00:00:00`).toLocaleDateString("en-US", {
          month: "short",
          day: "numeric",
          year: "numeric",
        })
      : "…";
  if (from && to) return `${fmt(from)} – ${fmt(to)}`;
  return from ? `From ${fmt(from)}` : `Until ${fmt(to)}`;
}

// ─── Empty fallback state ─────────────────────────────────────────────────────

const EMPTY_STATS: LeadsStatsResponse = {
  kpis: {
    total_leads: 0,
    all_time_total: 0,
    leads_this_week: 0,
    conversion_rate: 0,
    active_applications: 0,
    avg_deal_value: 0,
  },
  lead_volume: [],
  source_breakdown: [],
  funnel: [],
  available_sources: [],
};

const EMPTY_LEADS: LeadsListResponse = {
  leads: [],
  total: 0,
  page: 1,
  per_page: 50,
};

// Status / Source display config, and the resolveSource/resolveStatus
// fallback resolvers, live in @/lib/lead-display.ts (shared with the lead
// detail page — see the former TODO(v2) there).

// ─── KPI Card ─────────────────────────────────────────────────────────────────

function LeadsKpiCard({
  label,
  value,
  badgeLabel,
  badgeDirection,
  subtitle,
  borderColor,
}: {
  label: string;
  value: string;
  badgeLabel: string;
  badgeDirection: "up" | "down";
  subtitle: string;
  borderColor: string;
}) {
  const isUp = badgeDirection === "up";
  return (
    <div
      className="bg-white rounded-xl border border-gray-200 shadow-sm p-4 flex flex-col gap-1"
      style={{ borderTop: `3px solid ${borderColor}` }}
      role="group"
      aria-label={label}
    >
      <span className="text-[10px] font-bold uppercase tracking-widest text-gray-400">
        {label}
      </span>
      <div className="flex items-end gap-2 mt-0.5">
        <span className="text-2xl font-bold text-gray-900 leading-none tabular-nums">
          {value}
        </span>
        <span
          className={`mb-0.5 text-[11px] font-semibold px-1.5 py-0.5 rounded-full ${
            isUp ? "bg-emerald-50 text-emerald-700" : "bg-red-50 text-red-600"
          }`}
        >
          {isUp ? "↑" : "↓"} {badgeLabel}
        </span>
      </div>
      <span className="text-xs text-gray-400">{subtitle}</span>
    </div>
  );
}

// ─── Lead Volume Line Chart ───────────────────────────────────────────────────

function LeadVolumeChart({ data }: { data: { label: string; value: number }[] }) {
  const [hovered, setHovered] = useState<number | null>(null);

  const values = data.map((d) => d.value);
  const min = data.length > 0 ? Math.min(...values) : 0;
  const max = data.length > 0 ? Math.max(...values) : 1;
  const range = max - min || 1;

  const chartW = 460;
  const chartH = 140;
  const paddingX = 8;
  const paddingY = 16;
  const innerW = chartW - paddingX * 2;
  const innerH = chartH - paddingY * 2;

  const toX = (i: number) => paddingX + (i / Math.max(data.length - 1, 1)) * innerW;
  const toY = (v: number) =>
    paddingY + innerH - ((v - min) / range) * innerH;

  const linePath = data
    .map((d, i) => `${i === 0 ? "M" : "L"} ${toX(i)} ${toY(d.value)}`)
    .join(" ");

  const areaPath =
    data.length > 0
      ? linePath +
        ` L ${toX(data.length - 1)} ${chartH - paddingY + 4}` +
        ` L ${toX(0)} ${chartH - paddingY + 4} Z`
      : "";

  const gradientId = "leadVolumeGrad";

  return (
    <div
      className="bg-white rounded-xl border border-gray-200 shadow-sm p-5"
      aria-label="Lead volume chart — last 8 weeks"
    >
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-sm font-bold text-gray-900">
          Lead Volume — Last 8 Weeks
        </h2>
        <span className="text-xs text-gray-400">by entry date</span>
      </div>
      <svg
        viewBox={`0 0 ${chartW} ${chartH}`}
        className="w-full"
        style={{ height: 160 }}
        role="img"
        aria-label="Lead volume over the last 8 weeks by entry date"
      >
        <defs>
          <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#3B82F6" stopOpacity="0.2" />
            <stop offset="100%" stopColor="#3B82F6" stopOpacity="0" />
          </linearGradient>
        </defs>

        {/* Horizontal grid lines */}
        {[0, 0.25, 0.5, 0.75, 1].map((frac, i) => {
          const y = paddingY + (1 - frac) * innerH;
          return (
            <line
              key={i}
              x1={paddingX}
              y1={y}
              x2={chartW - paddingX}
              y2={y}
              stroke="#F3F4F6"
              strokeWidth="1"
            />
          );
        })}

        {/* Area fill */}
        {areaPath && <path d={areaPath} fill={`url(#${gradientId})`} />}

        {/* Line */}
        {linePath && (
          <path
            d={linePath}
            fill="none"
            stroke="#3B82F6"
            strokeWidth="2"
            strokeLinejoin="round"
            strokeLinecap="round"
          />
        )}

        {/* Data points */}
        {data.map((d, i) => {
          const isLast = i === data.length - 1;
          const isHovered = hovered === i;
          const cx = toX(i);
          const cy = toY(d.value);
          return (
            <g key={i}>
              {(isLast || isHovered) && (
                <circle
                  cx={cx}
                  cy={cy}
                  r={isHovered ? 8 : 7}
                  fill="#BFDBFE"
                  opacity="0.6"
                />
              )}
              <circle
                cx={cx}
                cy={cy}
                r={isHovered ? 5 : isLast ? 4 : 3}
                fill={isLast || isHovered ? "#1D4ED8" : "#3B82F6"}
                stroke="white"
                strokeWidth="1.5"
              />
            </g>
          );
        })}

        {/* X-axis labels */}
        {data.map((d, i) => {
          const isLast = i === data.length - 1;
          const x = toX(i);
          return (
            <text
              key={i}
              x={x}
              y={chartH}
              textAnchor="middle"
              fontSize="10"
              fill={isLast ? "#3B82F6" : "#9CA3AF"}
              fontWeight={isLast ? "700" : "400"}
            >
              {d.label}
            </text>
          );
        })}

        {/* Hover tooltip — value + label above the hovered point */}
        {hovered !== null && data[hovered] && (() => {
          const d = data[hovered];
          const cx = toX(hovered);
          const cy = toY(d.value);
          const text = `${d.value} · ${d.label}`;
          const boxW = Math.max(46, text.length * 6.2);
          const boxH = 22;
          // Keep the tooltip inside the chart horizontally.
          const bx = Math.min(Math.max(cx - boxW / 2, 2), chartW - boxW - 2);
          const by = Math.max(cy - boxH - 10, 2);
          return (
            <g pointerEvents="none">
              <rect x={bx} y={by} width={boxW} height={boxH} rx="5" fill="#1F2937" />
              <text
                x={bx + boxW / 2}
                y={by + boxH / 2 + 4}
                textAnchor="middle"
                fontSize="11"
                fontWeight="600"
                fill="#FFFFFF"
              >
                {text}
              </text>
            </g>
          );
        })()}

        {/* Invisible, forgiving hit-areas — drive the hover state per point */}
        {data.map((d, i) => (
          <circle
            key={`hit-${i}`}
            cx={toX(i)}
            cy={toY(d.value)}
            r="14"
            fill="transparent"
            onMouseEnter={() => setHovered(i)}
            onMouseLeave={() => setHovered(null)}
            style={{ cursor: "pointer" }}
          >
            <title>{`${d.value} leads — ${d.label}`}</title>
          </circle>
        ))}
      </svg>
    </div>
  );
}

// ─── Source Breakdown Donut Chart ─────────────────────────────────────────────

// Stable palette for source colors not in SOURCE_COLORS (real integrations send
// sources like 'wgr', 'facebook_ads', … that the enum map doesn't cover). Hashed
// by source string so a given source always gets the same color across renders.
const SOURCE_FALLBACK_PALETTE = [
  "#F59E0B", "#3B82F6", "#10B981", "#8B5CF6", "#EC4899", "#14B8A6", "#F97316", "#6366F1",
];

function colorForSource(source: string): string {
  if (SOURCE_COLORS[source]) return SOURCE_COLORS[source];
  let hash = 0;
  for (let i = 0; i < source.length; i++) hash = (hash * 31 + source.charCodeAt(i)) | 0;
  return SOURCE_FALLBACK_PALETTE[Math.abs(hash) % SOURCE_FALLBACK_PALETTE.length];
}

function SourceDonutChart({
  segments,
  total,
}: {
  segments: { channel: string; count: number; percentage: number }[];
  total: number;
}) {
  const cx = 80;
  const cy = 80;
  const r = 58;
  const innerR = 38;
  const ringWidth = r - innerR;
  const midR = (r + innerR) / 2;
  const circumference = 2 * Math.PI * midR;

  // Resolve color + label once per segment. `channel` is an open string set
  // (canonical channels + "No attribution" + "Non-marketing" + "other
  // unmapped" + "unmapped:<src>/<med>" dialects) — shown verbatim via
  // channelLabel, NOT routed through the closed-enum SOURCE_CONFIG/
  // resolveSource (those are for the legacy per-lead `source` field only).
  const items = segments.map((seg) => ({
    ...seg,
    color: colorForSource(seg.channel),
    label: channelLabel(seg.channel),
  }));

  // A single segment at (near) 100% can't be drawn as one SVG arc — the start
  // and end points coincide and the path collapses to nothing. Render a plain
  // stroked ring in that case so a 100%-one-source donut isn't blank.
  const isFullCircle = items.length === 1 && items[0].percentage >= 99.95;

  // Build wedge paths for the multi-segment case.
  let cumulativePercent = 0;
  const arcs = items.map((seg) => {
    const startAngle = (cumulativePercent / 100) * 2 * Math.PI - Math.PI / 2;
    cumulativePercent += seg.percentage;
    const endAngle = (cumulativePercent / 100) * 2 * Math.PI - Math.PI / 2;

    const x1 = cx + r * Math.cos(startAngle);
    const y1 = cy + r * Math.sin(startAngle);
    const x2 = cx + r * Math.cos(endAngle);
    const y2 = cy + r * Math.sin(endAngle);

    const ix1 = cx + innerR * Math.cos(endAngle);
    const iy1 = cy + innerR * Math.sin(endAngle);
    const ix2 = cx + innerR * Math.cos(startAngle);
    const iy2 = cy + innerR * Math.sin(startAngle);

    const largeArc = seg.percentage > 50 ? 1 : 0;
    const d = [
      `M ${x1} ${y1}`,
      `A ${r} ${r} 0 ${largeArc} 1 ${x2} ${y2}`,
      `L ${ix1} ${iy1}`,
      `A ${innerR} ${innerR} 0 ${largeArc} 0 ${ix2} ${iy2}`,
      "Z",
    ].join(" ");

    return { ...seg, d };
  });

  return (
    <div
      className="bg-white rounded-xl border border-gray-200 shadow-sm p-5"
      aria-label="Lead source breakdown donut chart"
    >
      <h2 className="text-sm font-bold text-gray-900 mb-4">
        Source Breakdown
      </h2>
      <div className="flex items-center gap-6">
        {/* Donut SVG */}
        <div className="flex-shrink-0 relative" style={{ width: 160, height: 160 }}>
          <svg
            viewBox="0 0 160 160"
            width="160"
            height="160"
            aria-hidden="true"
          >
            {isFullCircle ? (
              // Single-source 100%: stroked ring (arc paths can't draw a full circle).
              <circle
                cx={cx}
                cy={cy}
                r={midR}
                fill="none"
                stroke={items[0].color}
                strokeWidth={ringWidth}
                strokeDasharray={circumference}
              />
            ) : (
              arcs.map((arc, i) => (
                <path
                  key={i}
                  d={arc.d}
                  fill={arc.color}
                  stroke="white"
                  strokeWidth="2"
                />
              ))
            )}
            {/* Center text */}
            <text
              x={cx}
              y={cy - 4}
              textAnchor="middle"
              fontSize="16"
              fontWeight="700"
              fill="#111827"
            >
              {total.toLocaleString()}
            </text>
            <text
              x={cx}
              y={cy + 14}
              textAnchor="middle"
              fontSize="10"
              fill="#9CA3AF"
            >
              total leads
            </text>
          </svg>
        </div>

        {/* Legend */}
        <div className="flex flex-col gap-2.5 flex-1">
          {items.length === 0 ? (
            <p className="text-xs text-gray-400">No source data.</p>
          ) : (
            items.map((item, i) => (
              <div key={`${item.channel}-${i}`} className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2 min-w-0">
                  <span
                    className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                    style={{ backgroundColor: item.color }}
                  />
                  <span className="text-xs text-gray-600 truncate">{item.label}</span>
                </div>
                <div className="text-right flex-shrink-0">
                  <span className="text-xs font-bold text-gray-900">
                    {item.percentage.toFixed(1)}%
                  </span>
                  <span className="text-xs text-gray-400 ml-1">
                    ({item.count.toLocaleString()})
                  </span>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}

// ─── Sales Funnel ─────────────────────────────────────────────────────────────

// Each funnel stage → the table status filter that reflects it. "Leads" clears
// the filter (all); the rest map to API status values (Applications is the
// composite qualified+appointment-set filter).
const FUNNEL_STAGE_TO_FILTER: Record<string, FilterStatus> = {
  Leads: "all",
  Appointments: "appointment_set",
  Applications: "applications",
  Sales: "closed_won",
};

function SalesFunnel({
  stages,
  rangeText,
  avgDealValue,
  onStageClick,
}: {
  stages: { stage: string; count: number; percentage: number }[];
  rangeText: string;
  avgDealValue: number;
  onStageClick: (filter: FilterStatus) => void;
}) {
  // Each stage is a centered rectangle bar; the bars step down evenly in width
  // (100% → MIN) so the stack reads as an inverted triangle, with a downward
  // arrow between stages showing the flow. The numbers on each bar carry the
  // actual data. Step conversion = stage / prev.
  const MIN_WIDTH = 34; // % width of the narrowest (bottom) bar
  const n = stages.length;
  const widthFor = (i: number) =>
    n <= 1 ? 100 : 100 - ((100 - MIN_WIDTH) * i) / (n - 1);

  const funnelStages = stages.map((stage, i) => ({
    ...stage,
    color: FUNNEL_COLORS[stage.stage] ?? "#6B7280",
    widthPercent: widthFor(i),
    stepRate:
      i > 0 && stages[i - 1].count > 0
        ? ((stage.count / stages[i - 1].count) * 100).toFixed(1) + "%"
        : undefined,
  }));

  // Overall conversion: last stage / first stage.
  const overallConversion =
    funnelStages.length >= 2 && funnelStages[0].count > 0
      ? ((funnelStages[funnelStages.length - 1].count / funnelStages[0].count) * 100).toFixed(2) + "%"
      : "—";

  const dealValueText =
    avgDealValue > 0
      ? `$${Math.round(avgDealValue).toLocaleString()}`
      : "—";

  return (
    <div
      className="bg-white rounded-xl border border-gray-200 shadow-sm p-5"
      aria-label="Sales funnel overview"
    >
      {/* Card header */}
      <div className="flex items-center justify-between mb-5">
        <h2 className="text-sm font-bold text-gray-900">Sales Funnel Overview</h2>
        <span className="text-xs text-gray-400">{rangeText} • by entry date</span>
      </div>

      <div className="flex gap-5">
        {/* Funnel — centered rectangle bars stepping down into an inverted
            triangle, with a downward arrow between stages showing the flow */}
        <div className="flex-1 flex flex-col items-center">
          {funnelStages.map((stage, i) => (
            <div key={stage.stage} className="w-full flex flex-col items-center">
              {/* Down-arrow connector indicating lead flow to the next stage */}
              {i > 0 && (
                <span
                  className="text-gray-300 leading-none my-1 select-none"
                  style={{ fontSize: "1rem" }}
                  aria-hidden
                >
                  ▼
                </span>
              )}
              <button
                type="button"
                onClick={() => onStageClick(FUNNEL_STAGE_TO_FILTER[stage.stage] ?? "all")}
                title={`Show ${stage.stage} in the table`}
                aria-label={`Filter table to ${stage.count.toLocaleString()} ${stage.stage}`}
                className="rounded-lg h-12 flex items-center justify-center gap-2 px-4 text-white transition-all duration-200 hover:brightness-110 hover:-translate-y-px hover:shadow-md focus:outline-none focus:ring-2 focus:ring-offset-1 focus:ring-gray-400 cursor-pointer"
                style={{ width: `${stage.widthPercent}%`, backgroundColor: stage.color }}
              >
                <span className="text-lg font-extrabold tabular-nums">
                  {stage.count.toLocaleString()}
                </span>
                <span className="text-[13px] font-medium opacity-95">{stage.stage}</span>
                {stage.stepRate && (
                  <span className="text-[11px] font-semibold opacity-80">{stage.stepRate}</span>
                )}
              </button>
            </div>
          ))}
        </div>

        {/* Right rail — overall conversion + avg deal value */}
        <div className="flex-shrink-0 w-36 border-l border-gray-200 pl-5 flex flex-col justify-center gap-5">
          <div>
            <p className="text-[10px] font-bold uppercase tracking-widest text-gray-400 mb-1">
              Overall Conv.
            </p>
            <p className="text-2xl font-extrabold text-gray-900 leading-none">{overallConversion}</p>
            <p className="text-[11px] text-gray-500 mt-1">Lead to sale</p>
          </div>
          <div>
            <p className="text-[10px] font-bold uppercase tracking-widest text-gray-400 mb-1">
              Avg Deal Value
            </p>
            <p className="text-2xl font-extrabold text-emerald-600 leading-none">{dealValueText}</p>
            <p className="text-[11px] text-gray-500 mt-1">Per closed sale</p>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Score Bar ────────────────────────────────────────────────────────────────

function ScoreBar({ score }: { score: number }) {
  const color =
    score >= 80
      ? "#10B981"
      : score >= 60
      ? "#3B82F6"
      : score >= 40
      ? "#F59E0B"
      : "#EF4444";

  return (
    <div className="flex items-center gap-2">
      <div className="w-20 h-1.5 bg-gray-100 rounded-full overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-300"
          style={{ width: `${score}%`, backgroundColor: color }}
        />
      </div>
      <span className="text-xs font-semibold text-gray-600 tabular-nums">
        {score}
      </span>
    </div>
  );
}

// ─── Table Row ────────────────────────────────────────────────────────────────

function LeadTableRow({ lead }: { lead: Lead }) {
  // Use the resolver helpers so unknown values (e.g. GHL pushing
  // source='facebook_ads') get a sensible default instead of crashing.
  const status = resolveStatus(lead.status);
  const source = resolveSource(lead.source);
  // Channel is a distinct, open string set from `source` — never routed
  // through SOURCE_CONFIG. Colored via the same hash palette as the donut
  // (colorForSource) keyed on `channel ?? "No attribution"`; `unmapped:*`
  // dialects get an amber warning tint instead so they surface loudly.
  const channelValue = lead.channel ?? null;
  const channelText = channelLabel(channelValue);
  const channelColor = colorForSource(channelText);
  const date = new Date(lead.createdAt);
  const formattedDate = date.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
  });

  const router = useRouter();

  // Whole-row click navigates to detail. Wrapping <tr> in a Next.js
  // <Link> produces invalid HTML (tr can't be inside a). Instead we
  // attach role="link" + Enter/Space keyboard handlers for a11y.
  function openDetail() {
    router.push(`/leads/${lead.id}`);
  }

  return (
    <tr
      onClick={openDetail}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          openDetail();
        }
      }}
      role="link"
      tabIndex={0}
      aria-label={`Open lead ${lead.name ?? "unnamed"}`}
      className="border-b border-gray-50 hover:bg-gray-50/60 focus:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-accent-300 cursor-pointer transition-colors"
    >
      {/* Name + Email */}
      <td className="px-5 py-3.5">
        <div className="flex flex-col">
          <span className="text-sm font-semibold text-gray-900">{lead.name}</span>
          <span className="text-xs text-gray-400">{lead.email}</span>
        </div>
      </td>

      {/* Source */}
      <td className="px-5 py-3.5">
        <span
          className={`inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold ${source.badgeClasses}`}
        >
          {source.label}
        </span>
      </td>

      {/* Channel */}
      <td className="px-5 py-3.5">
        <span
          className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[11px] font-semibold ${channelBadgeClasses(channelValue)}`}
        >
          <span
            className="w-1.5 h-1.5 rounded-full flex-shrink-0"
            style={{ backgroundColor: channelColor }}
          />
          {channelText}
        </span>
      </td>

      {/* Date Added */}
      <td className="px-5 py-3.5">
        <span className="text-xs text-gray-500">{formattedDate}</span>
      </td>

      {/* Status */}
      <td className="px-5 py-3.5">
        <span
          className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[11px] font-semibold ${status.badgeClasses}`}
        >
          <span
            className="w-1.5 h-1.5 rounded-full flex-shrink-0"
            style={{ backgroundColor: status.dotColor }}
          />
          {status.label}
        </span>
      </td>

      {/* Score */}
      <td className="px-5 py-3.5">
        <ScoreBar score={lead.score ?? 50} />
      </td>
    </tr>
  );
}

// ─── Filter Bar ───────────────────────────────────────────────────────────────

// "applications" is a composite filter (qualified + appointment-set) used by the
// funnel's Applications stage and the matching dropdown option — not a real
// per-lead status, so it's added on top of LeadStatus.
type FilterStatus = "all" | LeadStatus | "applications";
// Source is server-filtered (exact lowercased match on leads.source). The
// option list comes from stats.available_sources — the distinct values
// actually in the DB — so any string can be a valid filter value, not just
// the legacy LeadSource enum.
type FilterSource = "all" | string;
// Channel is an open string set (not an enum) — "all" plus any raw channel
// value seen on the currently-loaded page, or the sentinel below for leads
// with no attribution. Filtering happens client-side only (Task 3 scope
// didn't add a server-side channel filter param).
type FilterChannel = "all" | string;
const NO_ATTRIBUTION_FILTER_VALUE = "__no_attribution__";

// ─── Column sort ──────────────────────────────────────────────────────────────

// Backend-whitelisted sort columns. "Date Added" sorts on entry_date (the lead's
// displayed date); "Score" has no DB column and is derived from status, so the
// Score header sorts by status — same ordering the score reflects.
type SortColumn = "name" | "source" | "entry_date" | "status";
type SortDir = "asc" | "desc";

function SortableHeader({
  label,
  column,
  sortBy,
  sortDir,
  onSort,
}: {
  label: string;
  column: SortColumn;
  sortBy: SortColumn;
  sortDir: SortDir;
  onSort: (col: SortColumn) => void;
}) {
  const active = sortBy === column;
  return (
    <th className="px-5 py-2.5 text-left text-[10px] font-bold uppercase tracking-widest text-gray-400">
      <button
        type="button"
        onClick={() => onSort(column)}
        aria-sort={active ? (sortDir === "asc" ? "ascending" : "descending") : "none"}
        className={`inline-flex items-center gap-1 uppercase tracking-widest transition-colors hover:text-gray-600 ${
          active ? "text-gray-700" : ""
        }`}
      >
        {label}
        <span className="text-[9px] leading-none w-2 inline-block" aria-hidden="true">
          {active ? (sortDir === "asc" ? "▲" : "▼") : "↕"}
        </span>
      </button>
    </th>
  );
}

function FilterBar({
  search,
  onSearchChange,
  statusFilter,
  onStatusChange,
  sourceFilter,
  onSourceChange,
  sourceOptions,
  channelFilter,
  onChannelChange,
  channelOptions,
  entryFrom,
  onEntryFromChange,
  entryTo,
  onEntryToChange,
  onClear,
  onAnalyze,
}: {
  search: string;
  onSearchChange: (v: string) => void;
  statusFilter: FilterStatus;
  onStatusChange: (v: FilterStatus) => void;
  sourceFilter: FilterSource;
  onSourceChange: (v: FilterSource) => void;
  /** Distinct provenance sources present in the DB (from stats.available_sources),
   * each paired with its display label. Raw value is what the server-side
   * `source` filter param expects (exact lowercased match). */
  sourceOptions: { value: string; label: string }[];
  channelFilter: FilterChannel;
  onChannelChange: (v: FilterChannel) => void;
  /** Distinct channel values present on the currently-loaded page, each
   * paired with its display label (raw value for the select's `value`, so
   * filtering can match `lead.channel` directly). */
  channelOptions: { value: string; label: string }[];
  entryFrom: string;
  onEntryFromChange: (v: string) => void;
  entryTo: string;
  onEntryToChange: (v: string) => void;
  onClear: () => void;
  onAnalyze: () => void;
}) {
  const hasFilters =
    search !== "" ||
    statusFilter !== "all" ||
    sourceFilter !== "all" ||
    channelFilter !== "all" ||
    entryFrom !== "" ||
    entryTo !== "";

  return (
    <div className="flex items-center gap-2.5 flex-wrap">
      {/* Search */}
      <div className="relative flex-1 min-w-[180px] max-w-xs">
        <svg
          className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-400"
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 20 20"
          fill="currentColor"
          aria-hidden="true"
        >
          <path
            fillRule="evenodd"
            d="M9 3.5a5.5 5.5 0 100 11 5.5 5.5 0 000-11zM2 9a7 7 0 1112.452 4.391l3.328 3.329a.75.75 0 11-1.06 1.06l-3.329-3.328A7 7 0 012 9z"
            clipRule="evenodd"
          />
        </svg>
        <input
          type="text"
          placeholder="Search leads..."
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
          className="w-full pl-8 pr-3 py-1.5 text-sm border border-gray-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-400 transition-all"
        />
      </div>

      {/* Source */}
      <select
        value={sourceFilter}
        onChange={(e) => onSourceChange(e.target.value as FilterSource)}
        className="px-2.5 py-1.5 text-sm border border-gray-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-400 text-gray-600"
      >
        <option value="all">All Sources</option>
        {sourceOptions.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>

      {/* Channel — client-side only, filters the loaded page on
          lead.channel. Options are derived from the loaded leads since
          channel is an open string set, not an enum. */}
      <select
        value={channelFilter}
        onChange={(e) => onChannelChange(e.target.value as FilterChannel)}
        className="px-2.5 py-1.5 text-sm border border-gray-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-400 text-gray-600"
      >
        <option value="all">All Channels</option>
        {channelOptions.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>

      {/* Status */}
      <select
        value={statusFilter}
        onChange={(e) => onStatusChange(e.target.value as FilterStatus)}
        className="px-2.5 py-1.5 text-sm border border-gray-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-400 text-gray-600"
      >
        <option value="all">All Statuses</option>
        {/* Composite filter matching the funnel's Applications stage. */}
        <option value="applications">Applications (qualified + booked)</option>
        {(Object.keys(STATUS_CONFIG) as LeadStatus[]).map((key) => (
          <option key={key} value={key}>
            {STATUS_CONFIG[key].label}
          </option>
        ))}
      </select>

      {/* Entry-date range — filters on the upstream funnel-entry date */}
      <div className="flex items-center gap-1.5 text-gray-500">
        <span className="text-[11px] font-semibold uppercase tracking-wide shrink-0">
          Entered
        </span>
        <input
          type="date"
          aria-label="Entered on or after"
          value={entryFrom}
          max={entryTo || undefined}
          onChange={(e) => onEntryFromChange(e.target.value)}
          className="px-2 py-1.5 text-sm border border-gray-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-400 text-gray-600"
        />
        <span className="text-gray-300">–</span>
        <input
          type="date"
          aria-label="Entered on or before"
          value={entryTo}
          min={entryFrom || undefined}
          onChange={(e) => onEntryToChange(e.target.value)}
          className="px-2 py-1.5 text-sm border border-gray-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-400 text-gray-600"
        />
      </div>

      {/* Clear */}
      {hasFilters && (
        <button
          type="button"
          onClick={onClear}
          className="px-2.5 py-1.5 text-sm text-gray-500 hover:text-gray-700 border border-gray-200 rounded-lg bg-white hover:bg-gray-50 transition-colors"
        >
          Clear filters
        </button>
      )}

      <AnalyzeViewButton onClick={onAnalyze} />
    </div>
  );
}

// ─── Skeleton layouts ─────────────────────────────────────────────────────────

function KpiRowSkeleton() {
  return (
    <div className="grid grid-cols-4 gap-4">
      {[1, 2, 3, 4].map((i) => (
        <div
          key={i}
          className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm space-y-2"
        >
          <Skeleton className="h-2.5 w-20" />
          <div className="flex items-end gap-2">
            <Skeleton className="h-7 w-16" />
            <Skeleton className="h-4 w-12 rounded-full" />
          </div>
          <Skeleton className="h-2.5 w-24" />
        </div>
      ))}
    </div>
  );
}

function ChartRowSkeleton() {
  return (
    <div className="grid grid-cols-2 gap-4">
      <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
        <Skeleton className="h-4 w-48 mb-4" />
        <Skeleton className="h-36 w-full rounded-lg" />
      </div>
      <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
        <Skeleton className="h-4 w-36 mb-4" />
        <div className="flex items-center gap-6">
          <Skeleton className="h-36 w-36 rounded-full" />
          <div className="flex-1 space-y-3">
            <Skeleton className="h-3 w-full" />
            <Skeleton className="h-3 w-3/4" />
            <Skeleton className="h-3 w-5/6" />
          </div>
        </div>
      </div>
    </div>
  );
}

function FunnelSkeleton() {
  const barWidths = [100, 70, 48, 30];
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
      <Skeleton className="h-4 w-44 mb-5" />
      <div className="flex gap-5">
        <div className="flex-1 space-y-3">
          {barWidths.map((w, i) => (
            <div
              key={i}
              className="h-7 animate-pulse rounded-full bg-gray-200"
              style={{ width: `${w}%` }}
            />
          ))}
        </div>
        <div className="w-36 border-l border-gray-100 pl-5 space-y-4">
          <Skeleton className="h-8 w-20" />
          <Skeleton className="h-8 w-20" />
        </div>
      </div>
    </div>
  );
}

function TableSkeleton() {
  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
      <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
        <Skeleton className="h-4 w-28" />
        <Skeleton className="h-3 w-32" />
      </div>
      <div className="px-5 py-3 border-b border-gray-100 flex gap-2.5">
        <Skeleton className="h-8 flex-1 max-w-xs rounded-lg" />
        <Skeleton className="h-8 w-28 rounded-lg" />
        <Skeleton className="h-8 w-28 rounded-lg" />
        <Skeleton className="h-8 w-24 rounded-lg" />
      </div>
      {Array.from({ length: 6 }).map((_, i) => (
        <div
          key={i}
          className="grid grid-cols-6 gap-4 px-5 py-3.5 border-b border-gray-50 items-center"
        >
          <div className="space-y-1.5">
            <Skeleton className="h-3.5 w-28" />
            <Skeleton className="h-2.5 w-32" />
          </div>
          <Skeleton className="h-5 w-16 rounded-full" />
          <Skeleton className="h-5 w-20 rounded-full" />
          <Skeleton className="h-3 w-16" />
          <Skeleton className="h-5 w-20 rounded-full" />
          <div className="flex items-center gap-2">
            <Skeleton className="h-1.5 w-20 rounded-full" />
            <Skeleton className="h-3 w-6" />
          </div>
        </div>
      ))}
    </div>
  );
}

// ─── Page ────────────────────────────────────────────────────────────────────

export default function LeadsPage() {
  const { isLoading: authLoading } = useAuth();
  const [isLoading, setIsLoading] = useState(true);
  const [stats, setStats] = useState<LeadsStatsResponse>(EMPTY_STATS);
  const [leadsData, setLeadsData] = useState<LeadsListResponse>(EMPTY_LEADS);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<FilterStatus>("all");
  const [sourceFilter, setSourceFilter] = useState<FilterSource>("all");
  // Channel filter is CLIENT-SIDE only — it narrows the already-loaded page
  // by lead.channel and does not touch the /leads request params (no
  // server-side channel filter exists per Task 3 scope).
  const [channelFilter, setChannelFilter] = useState<FilterChannel>("all");
  // Entry-date range filter (YYYY-MM-DD strings from <input type="date">).
  // Defaults to the current week (Mon–Sun) so the funnel/KPIs/table open scoped
  // to "this week" rather than all-time; cleared via Clear filters.
  const [entryFrom, setEntryFrom] = useState(() => currentWeekRange().from);
  const [entryTo, setEntryTo] = useState(() => currentWeekRange().to);
  // Column sort. Defaults match the API default (entry-date, newest first).
  const [sortBy, setSortBy] = useState<SortColumn>("entry_date");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [analyzeOpen, setAnalyzeOpen] = useState(false);
  const [analyzeParams, setAnalyzeParams] = useState<URLSearchParams | null>(null);

  // Pagination — page size persisted per surface in localStorage.
  const { page, pageSize, setPage, setPageSize, resetToFirstPage } =
    usePagination("leads");

  // Toggle sort on a column: same column flips direction, new column starts desc.
  const handleSort = (col: SortColumn) => {
    if (col === sortBy) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortBy(col);
      setSortDir("desc");
    }
  };

  // Fetch stats (after auth hydrates). Re-runs when the entry-date range
  // changes so the funnel / KPIs / charts stay scoped to the same window the
  // table uses — filtered on entry_date, not created/sync date.
  useEffect(() => {
    if (authLoading) return;

    let cancelled = false;

    async function fetchStats(): Promise<void> {
      try {
        const params = new URLSearchParams();
        if (entryFrom) params.set("entry_from", entryFrom);
        if (entryTo) params.set("entry_to", entryTo);
        const qs = params.toString();
        const data = await apiClient.get<LeadsStatsResponse>(
          `/leads/stats${qs ? `?${qs}` : ""}`,
          { silent: true },
        );
        if (!cancelled) {
          setStats(data);
        }
      } catch {
        // On error, stats stays as EMPTY_STATS so the page renders with "0" values.
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
  }, [authLoading, entryFrom, entryTo]);

  // Scroll target for funnel-bar clicks → the records table.
  const leadsTableRef = useRef<HTMLDivElement | null>(null);

  // Fetch leads whenever filters change, with debounce on search
  const searchDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (authLoading) return;

    // Clear any pending search debounce
    if (searchDebounceRef.current !== null) {
      clearTimeout(searchDebounceRef.current);
    }

    const doFetch = () => {
      let cancelled = false;

      async function fetchLeads(): Promise<void> {
        const params = new URLSearchParams();
        if (statusFilter !== "all") params.set("status", statusFilter);
        if (sourceFilter !== "all") params.set("source", sourceFilter);
        if (search) params.set("search", search);
        if (entryFrom) params.set("entry_from", entryFrom);
        if (entryTo) params.set("entry_to", entryTo);
        params.set("sort_by", sortBy);
        params.set("sort_dir", sortDir);
        params.set("page", String(page));
        params.set("per_page", String(pageSize));

        try {
          const data = await apiClient.get<LeadsListResponse>(
            `/leads?${params.toString()}`,
            { silent: true }
          );
          if (!cancelled) {
            setLeadsData(data);
          }
        } catch {
          // On error, leadsData stays as previous value.
        }
      }

      void fetchLeads();

      return () => {
        cancelled = true;
      };
    };

    // Debounce only the search input; fire immediately for dropdown changes
    if (search !== "") {
      searchDebounceRef.current = setTimeout(doFetch, 300);
      return () => {
        if (searchDebounceRef.current !== null) {
          clearTimeout(searchDebounceRef.current);
        }
      };
    }

    return doFetch();
  }, [authLoading, statusFilter, sourceFilter, search, entryFrom, entryTo, sortBy, sortDir, page, pageSize]);

  // Mirrors the list-fetch params in fetchLeads above, minus sort/pagination —
  // snapshot for "Analyze this view".
  const openAnalyze = () => {
    const params = new URLSearchParams();
    if (statusFilter !== "all") params.set("status", statusFilter);
    if (sourceFilter !== "all") params.set("source", sourceFilter);
    if (search) params.set("search", search);
    if (entryFrom) params.set("entry_from", entryFrom);
    if (entryTo) params.set("entry_to", entryTo);
    setAnalyzeParams(params);
    setAnalyzeOpen(true);
  };

  // When a filter/search/sort narrows the set, jump back to page 1 so the user
  // isn't stranded on a page that no longer exists.
  useEffect(() => {
    resetToFirstPage();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statusFilter, sourceFilter, search, entryFrom, entryTo, sortBy, sortDir]);

  // Build KPI cards from live stats
  const kpiCards = [
    {
      label: "Total Leads",
      value: formatNumber(stats.kpis.all_time_total),
      badgeLabel: "—",
      badgeDirection: "up" as const,
      // Headline is the true all-time total; subtitle shows how many fall in the
      // selected entry-date range so both numbers are visible without ambiguity.
      subtitle: `All time · ${formatNumber(stats.kpis.total_leads)} in range`,
      borderColor: "#3B82F6",
    },
    {
      label: "This Week",
      value: formatNumber(stats.kpis.leads_this_week),
      badgeLabel: "—",
      badgeDirection: "up" as const,
      subtitle: "Entered, last 7 days",
      borderColor: "#F59E0B",
    },
    {
      label: "Conversion Rate",
      value: stats.kpis.conversion_rate.toFixed(1) + "%",
      badgeLabel: "—",
      badgeDirection: "up" as const,
      subtitle: "Lead to sale",
      borderColor: "#10B981",
    },
    {
      label: "Active Applications",
      value: formatNumber(stats.kpis.active_applications),
      badgeLabel: "—",
      badgeDirection: "up" as const,
      subtitle: "Awaiting review",
      borderColor: "#F97316",
    },
  ];

  const handleClearFilters = () => {
    setSearch("");
    setStatusFilter("all");
    setSourceFilter("all");
    setChannelFilter("all");
    setEntryFrom("");
    setEntryTo("");
  };

  // Distinct channel values on the currently-loaded page, each with its
  // display label. "No attribution" (null channel) is represented by the
  // sentinel value so it's selectable via a normal <option value>. Memoized
  // on leadsData.leads so it isn't rebuilt (Map + sort) on every render.
  const channelOptions = useMemo(() => {
    const seen = new Map<string, string>();
    for (const lead of leadsData.leads) {
      const raw = lead.channel ?? null;
      const value = raw ?? NO_ATTRIBUTION_FILTER_VALUE;
      if (!seen.has(value)) seen.set(value, channelLabel(raw));
    }
    return Array.from(seen.entries())
      .map(([value, label]) => ({ value, label }))
      .sort((a, b) => a.label.localeCompare(b.label));
  }, [leadsData.leads]);

  // Source filter options from the distinct values actually in the DB
  // (stats.available_sources, count-desc from the backend — keep that order
  // so the most common sources list first). Labels via resolveSource so
  // legacy enum values keep their curated labels ("Opt-in") and anything
  // else is prettified ("wgr" → "WGR"). Falls back to the legacy enum list
  // while stats are still loading (or against an older backend without
  // available_sources) so the dropdown is never empty.
  const sourceOptions = useMemo(() => {
    const sources = stats.available_sources ?? [];
    if (sources.length === 0) {
      return (Object.keys(SOURCE_CONFIG) as LeadSource[]).map((key) => ({
        value: key as string,
        label: SOURCE_CONFIG[key].label,
      }));
    }
    return sources.map((src) => ({ value: src, label: resolveSource(src).label }));
  }, [stats.available_sources]);

  // Client-side channel filter over the loaded page (server-side filtering
  // on channel is out of scope per Task 3).
  const visibleLeads =
    channelFilter === "all"
      ? leadsData.leads
      : leadsData.leads.filter((lead) => {
          const value = lead.channel ?? NO_ATTRIBUTION_FILTER_VALUE;
          return value === channelFilter;
        });

  return (
    <>
      <Header title="Leads" />

      <main className="flex-1 overflow-y-auto p-7 space-y-6">
        {/* Page heading + action buttons */}
        <div className="flex items-start justify-between">
          <div>
            <div className="flex items-center gap-2.5">
              <h1 className="text-xl font-bold text-gray-900">Lead Pipeline</h1>
            </div>
            <p className="text-sm text-gray-500 mt-0.5">
              Track and manage your incoming leads across all sources.
            </p>
          </div>

          {/* Action buttons */}
          <div className="flex items-center gap-2 flex-shrink-0">
            <button
              type="button"
              className="flex items-center gap-1.5 px-3 py-2 text-sm font-medium text-gray-600 bg-white border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
            >
              <svg
                className="w-3.5 h-3.5"
                xmlns="http://www.w3.org/2000/svg"
                viewBox="0 0 20 20"
                fill="currentColor"
                aria-hidden="true"
              >
                <path
                  fillRule="evenodd"
                  d="M3 10a.75.75 0 01.75-.75h10.638L10.23 5.29a.75.75 0 111.04-1.08l5.5 5.25a.75.75 0 010 1.08l-5.5 5.25a.75.75 0 11-1.04-1.08l4.158-3.96H3.75A.75.75 0 013 10z"
                  clipRule="evenodd"
                />
              </svg>
              Export CSV
            </button>
            <button
              type="button"
              className="flex items-center gap-1.5 px-3 py-2 text-sm font-semibold text-white rounded-lg transition-colors hover:opacity-90"
              style={{ backgroundColor: "#3B82F6" }}
            >
              <svg
                className="w-3.5 h-3.5"
                xmlns="http://www.w3.org/2000/svg"
                viewBox="0 0 20 20"
                fill="currentColor"
                aria-hidden="true"
              >
                <path d="M10.75 4.75a.75.75 0 00-1.5 0v4.5h-4.5a.75.75 0 000 1.5h4.5v4.5a.75.75 0 001.5 0v-4.5h4.5a.75.75 0 000-1.5h-4.5v-4.5z" />
              </svg>
              Add Lead
            </button>
          </div>
        </div>

        {/* KPI Row */}
        {isLoading ? (
          <KpiRowSkeleton />
        ) : (
          <div className="grid grid-cols-4 gap-4">
            {kpiCards.map((kpi) => (
              <LeadsKpiCard key={kpi.label} {...kpi} />
            ))}
          </div>
        )}

        {/* Charts Row */}
        {isLoading ? (
          <ChartRowSkeleton />
        ) : (
          <div className="grid grid-cols-2 gap-4">
            <LeadVolumeChart data={stats.lead_volume} />
            <SourceDonutChart
              segments={stats.source_breakdown}
              total={stats.kpis.total_leads}
            />
          </div>
        )}

        {/* Sales Funnel */}
        {isLoading ? (
          <FunnelSkeleton />
        ) : (
          <SalesFunnel
            stages={stats.funnel}
            rangeText={rangeLabel(entryFrom, entryTo)}
            avgDealValue={stats.kpis.avg_deal_value}
            onStageClick={(filter) => {
              setStatusFilter(filter);
              // Bring the records table into view so the result is visible.
              leadsTableRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
            }}
          />
        )}

        {/* Lead Records Table */}
        <div ref={leadsTableRef} className="scroll-mt-4" />
        {isLoading ? (
          <TableSkeleton />
        ) : (
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
            {/* Table header */}
            <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
              <h2 className="text-sm font-bold text-gray-900">Lead Records</h2>
              <span className="text-xs text-gray-400">
                Showing {visibleLeads.length} of {leadsData.total.toLocaleString()}
              </span>
            </div>

            {/* Filter bar */}
            <div className="px-5 py-3 border-b border-gray-100 bg-gray-50/50">
              <FilterBar
                search={search}
                onSearchChange={setSearch}
                statusFilter={statusFilter}
                onStatusChange={setStatusFilter}
                sourceFilter={sourceFilter}
                sourceOptions={sourceOptions}
                onSourceChange={setSourceFilter}
                channelFilter={channelFilter}
                onChannelChange={setChannelFilter}
                channelOptions={channelOptions}
                entryFrom={entryFrom}
                onEntryFromChange={setEntryFrom}
                entryTo={entryTo}
                onEntryToChange={setEntryTo}
                onClear={handleClearFilters}
                onAnalyze={openAnalyze}
              />
            </div>

            {/* Table */}
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-100 bg-gray-50">
                  <SortableHeader
                    label="Name"
                    column="name"
                    sortBy={sortBy}
                    sortDir={sortDir}
                    onSort={handleSort}
                  />
                  <SortableHeader
                    label="Source"
                    column="source"
                    sortBy={sortBy}
                    sortDir={sortDir}
                    onSort={handleSort}
                  />
                  {/* Not backend-sortable — channel filtering/sorting is
                      client-side only per Task 3/4 scope. */}
                  <th className="px-5 py-2.5 text-left text-[10px] font-bold uppercase tracking-widest text-gray-400">
                    Channel
                  </th>
                  <SortableHeader
                    label="Date Added"
                    column="entry_date"
                    sortBy={sortBy}
                    sortDir={sortDir}
                    onSort={handleSort}
                  />
                  <SortableHeader
                    label="Status"
                    column="status"
                    sortBy={sortBy}
                    sortDir={sortDir}
                    onSort={handleSort}
                  />
                  <th className="px-5 py-2.5 text-left text-[10px] font-bold uppercase tracking-widest text-gray-400">
                    Score
                  </th>
                </tr>
              </thead>
              <tbody>
                {visibleLeads.length === 0 ? (
                  <tr>
                    <td
                      colSpan={6}
                      className="px-5 py-12 text-center text-sm text-gray-400"
                    >
                      No leads match your filters.
                    </td>
                  </tr>
                ) : (
                  visibleLeads.map((lead) => (
                    <LeadTableRow key={lead.id} lead={lead} />
                  ))
                )}
              </tbody>
            </table>

            {!isLoading && leadsData.total > 0 && (
              <Pagination
                page={page}
                total={leadsData.total}
                pageSize={pageSize}
                onPageChange={setPage}
                onPageSizeChange={setPageSize}
              />
            )}

            {/* Table footer */}
            <div className="flex items-center justify-between px-5 py-3 border-t border-gray-100 bg-gray-50/50">
              <span className="text-xs text-gray-400">
                Showing {visibleLeads.length} of {leadsData.total.toLocaleString()} leads
              </span>
              <button
                type="button"
                className="text-xs font-medium text-blue-600 hover:text-blue-700"
              >
                View all leads
              </button>
            </div>
          </div>
        )}
      </main>

      <AnalyzeViewDrawer
        surface="leads"
        params={analyzeParams}
        open={analyzeOpen}
        onClose={() => setAnalyzeOpen(false)}
      />
    </>
  );
}
