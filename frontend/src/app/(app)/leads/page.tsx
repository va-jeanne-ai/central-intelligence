"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { Header } from "@/components/layout/header";
import { Skeleton } from "@/components/ui/skeleton";
import type { Lead, LeadStatus, LeadSource } from "@/types";
import { apiClient } from "@/lib/api-client";
import { useAuth } from "@/hooks/use-auth";

// ─── API response types ───────────────────────────────────────────────────────

interface LeadsListResponse {
  leads: Lead[];
  total: number;
  page: number;
  per_page: number;
}

interface LeadsStatsResponse {
  kpis: {
    total_leads: number;
    leads_this_week: number;
    conversion_rate: number;
    active_applications: number;
  };
  lead_volume: { label: string; value: number }[];
  source_breakdown: { source: string; count: number; percentage: number }[];
  funnel: { stage: string; count: number; percentage: number }[];
}

// ─── Color maps ───────────────────────────────────────────────────────────────

const SOURCE_COLORS: Record<string, string> = {
  webinar: "#6366F1",
  vsl: "#3B82F6",
  "opt-in": "#10B981",
  ads: "#9CA3AF",
  referral: "#8B5CF6",
  other: "#6B7280",
};

const FUNNEL_COLORS: Record<string, string> = {
  Leads: "#3B82F6",
  Appointments: "#8B5CF6",
  Applications: "#6366F1",
  Sales: "#10B981",
};

// ─── Helpers ──────────────────────────────────────────────────────────────────

function formatNumber(n: number): string {
  return n.toLocaleString("en-US");
}

// ─── Empty fallback state ─────────────────────────────────────────────────────

const EMPTY_STATS: LeadsStatsResponse = {
  kpis: {
    total_leads: 0,
    leads_this_week: 0,
    conversion_rate: 0,
    active_applications: 0,
  },
  lead_volume: [],
  source_breakdown: [],
  funnel: [],
};

const EMPTY_LEADS: LeadsListResponse = {
  leads: [],
  total: 0,
  page: 1,
  per_page: 50,
};

// ─── Status / Source display config ──────────────────────────────────────────

const STATUS_CONFIG: Record<
  LeadStatus,
  { label: string; dotColor: string; badgeClasses: string }
> = {
  new: {
    label: "New",
    dotColor: "#3B82F6",
    badgeClasses: "bg-blue-50 text-blue-700",
  },
  contacted: {
    label: "Active",
    dotColor: "#F97316",
    badgeClasses: "bg-orange-50 text-orange-700",
  },
  qualified: {
    label: "Applied",
    dotColor: "#8B5CF6",
    badgeClasses: "bg-violet-50 text-violet-700",
  },
  appointment_set: {
    label: "Booked",
    dotColor: "#0D9488",
    badgeClasses: "bg-teal-50 text-teal-700",
  },
  closed_won: {
    label: "Closed Won",
    dotColor: "#10B981",
    badgeClasses: "bg-green-50 text-green-700",
  },
  closed_lost: {
    label: "Lost",
    dotColor: "#9CA3AF",
    badgeClasses: "bg-gray-100 text-gray-500",
  },
  stale: {
    label: "Stale",
    dotColor: "#6366F1",
    badgeClasses: "bg-indigo-50 text-indigo-700",
  },
};

const SOURCE_CONFIG: Record<
  LeadSource,
  { label: string; badgeClasses: string }
> = {
  webinar: { label: "Webinar", badgeClasses: "bg-indigo-50 text-indigo-700" },
  vsl: { label: "VSL", badgeClasses: "bg-blue-50 text-blue-700" },
  "opt-in": { label: "Opt-in", badgeClasses: "bg-green-50 text-green-700" },
  ads: { label: "Ads", badgeClasses: "bg-gray-100 text-gray-600" },
  referral: { label: "Referral", badgeClasses: "bg-violet-50 text-violet-700" },
  other: { label: "Other", badgeClasses: "bg-gray-100 text-gray-500" },
};

// Fallback resolvers — leads now arrive from real integrations (GHL pushes
// e.g. source='facebook_ads', 'instagram_ads', 'podcast_referral'; status
// can be anything the upstream system uses). Looking those up in the
// enum-keyed records above returns undefined and the row render crashes
// on `.badgeClasses`. These helpers always return a sane shape so the
// page renders any string the backend hands us.

function _humanise(value: string | null | undefined): string {
  // 'facebook_ads' → 'Facebook Ads'. Best-effort prettifier for unknown
  // values; falls back to the raw string for anything weird. Real WGR leads
  // can arrive with a null/empty source or status, so guard before .split().
  if (!value) return "Unknown";
  return value
    .split(/[_\-\s]+/)
    .filter(Boolean)
    .map((w) => (w.length <= 3 ? w.toUpperCase() : w[0].toUpperCase() + w.slice(1).toLowerCase()))
    .join(" ");
}

function resolveSource(raw: string | null | undefined) {
  return (
    (raw ? SOURCE_CONFIG[raw as LeadSource] : undefined) ?? {
      label: _humanise(raw),
      badgeClasses: "bg-gray-100 text-gray-600",
    }
  );
}

function resolveStatus(raw: string | null | undefined) {
  return (
    (raw ? STATUS_CONFIG[raw as LeadStatus] : undefined) ?? {
      label: _humanise(raw),
      dotColor: "#9CA3AF",
      badgeClasses: "bg-gray-100 text-gray-600",
    }
  );
}

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
      <h2 className="text-sm font-bold text-gray-900 mb-4">
        Lead Volume — Last 8 Weeks
      </h2>
      <svg
        viewBox={`0 0 ${chartW} ${chartH}`}
        className="w-full"
        style={{ height: 160 }}
        aria-hidden="true"
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
          const cx = toX(i);
          const cy = toY(d.value);
          return (
            <g key={i}>
              {isLast && (
                <circle
                  cx={cx}
                  cy={cy}
                  r="7"
                  fill="#BFDBFE"
                  opacity="0.6"
                />
              )}
              <circle
                cx={cx}
                cy={cy}
                r={isLast ? 4 : 3}
                fill={isLast ? "#1D4ED8" : "#3B82F6"}
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
      </svg>
    </div>
  );
}

// ─── Source Breakdown Donut Chart ─────────────────────────────────────────────

function SourceDonutChart({
  segments,
  total,
}: {
  segments: { source: string; count: number; percentage: number }[];
  total: number;
}) {
  const cx = 80;
  const cy = 80;
  const r = 58;
  const innerR = 38;

  // Build arc segments
  let cumulativePercent = 0;
  const arcs = segments.map((seg) => {
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

    const color = SOURCE_COLORS[seg.source] ?? "#6B7280";
    const label = SOURCE_CONFIG[seg.source as LeadSource]?.label ?? seg.source;

    return { ...seg, d, color, label };
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
            {arcs.map((arc, i) => (
              <path
                key={i}
                d={arc.d}
                fill={arc.color}
                stroke="white"
                strokeWidth="2"
              />
            ))}
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
          {arcs.map((arc) => (
            <div key={arc.source} className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <span
                  className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                  style={{ backgroundColor: arc.color }}
                />
                <span className="text-xs text-gray-600">{arc.label}</span>
              </div>
              <div className="text-right">
                <span className="text-xs font-bold text-gray-900">
                  {arc.percentage.toFixed(1)}%
                </span>
                <span className="text-xs text-gray-400 ml-1">
                  ({arc.count.toLocaleString()})
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ─── Sales Funnel ─────────────────────────────────────────────────────────────

function SalesFunnel({
  stages,
}: {
  stages: { stage: string; count: number; percentage: number }[];
}) {
  // Derive display properties from API data
  const funnelStages = stages.map((stage, i) => {
    const color = FUNNEL_COLORS[stage.stage] ?? "#6B7280";
    const widthPercent = Math.max(stage.percentage * 0.9, 10);
    const conversionRate =
      i > 0 && stages[i - 1].count > 0
        ? ((stage.count / stages[i - 1].count) * 100).toFixed(1) + "%"
        : undefined;

    return { ...stage, color, widthPercent, conversionRate };
  });

  // Overall conversion: last stage / first stage
  const overallConversion =
    funnelStages.length >= 2 && funnelStages[0].count > 0
      ? ((funnelStages[funnelStages.length - 1].count / funnelStages[0].count) * 100).toFixed(2) + "%"
      : "—";

  return (
    <div
      className="bg-white rounded-xl border border-gray-200 shadow-sm p-5"
      aria-label="Sales funnel overview"
    >
      {/* Card header */}
      <div className="flex items-center justify-between mb-5">
        <h2 className="text-sm font-bold text-gray-900">Sales Funnel Overview</h2>
        <span className="text-xs text-gray-400">All time • Updated live</span>
      </div>

      <div className="flex gap-5">
        {/* Funnel bars */}
        <div className="flex-1 flex flex-col gap-1">
          {funnelStages.map((stage, i) => (
            <div key={stage.stage}>
              {/* Arrow between stages */}
              {i > 0 && (
                <div className="flex items-center gap-3 my-0.5 pl-2">
                  <span className="text-gray-300 text-sm font-bold leading-none">▼</span>
                  <span className="text-[11px] font-semibold text-gray-400">
                    {stage.conversionRate} conversion
                  </span>
                </div>
              )}

              {/* Bar row */}
              <div className="flex items-center gap-3">
                <span className="text-xs text-gray-500 w-24 flex-shrink-0">
                  {stage.stage}
                </span>
                <div className="flex-1 bg-gray-100 rounded-full h-7 relative overflow-hidden">
                  <div
                    className="absolute inset-y-0 left-0 rounded-full flex items-center pl-3 transition-all duration-500"
                    style={{
                      width: `${stage.widthPercent}%`,
                      backgroundColor: stage.color,
                    }}
                  >
                    <span className="text-xs font-bold text-white tabular-nums">
                      {stage.count.toLocaleString()}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Side panel */}
        <div className="flex-shrink-0 w-36 border-l border-gray-100 pl-5 flex flex-col justify-center gap-4">
          <div>
            <p className="text-[10px] font-bold uppercase tracking-widest text-gray-400 mb-0.5">
              Overall Conv.
            </p>
            <p className="text-lg font-bold text-gray-900">
              {overallConversion}
            </p>
          </div>
          <div>
            <p className="text-[10px] font-bold uppercase tracking-widest text-gray-400 mb-0.5">
              Avg Deal Value
            </p>
            <p className="text-lg font-bold text-gray-900">
              —
            </p>
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
      ? "#6366F1"
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
      className="border-b border-gray-50 hover:bg-gray-50/60 focus:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-indigo-300 cursor-pointer transition-colors"
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

type FilterStatus = "all" | LeadStatus;
type FilterSource = "all" | LeadSource;

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
  entryFrom,
  onEntryFromChange,
  entryTo,
  onEntryToChange,
  onClear,
}: {
  search: string;
  onSearchChange: (v: string) => void;
  statusFilter: FilterStatus;
  onStatusChange: (v: FilterStatus) => void;
  sourceFilter: FilterSource;
  onSourceChange: (v: FilterSource) => void;
  entryFrom: string;
  onEntryFromChange: (v: string) => void;
  entryTo: string;
  onEntryToChange: (v: string) => void;
  onClear: () => void;
}) {
  const hasFilters =
    search !== "" ||
    statusFilter !== "all" ||
    sourceFilter !== "all" ||
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
        {(Object.keys(SOURCE_CONFIG) as LeadSource[]).map((key) => (
          <option key={key} value={key}>
            {SOURCE_CONFIG[key].label}
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
          <Skeleton className="h-3 w-16" />
          <Skeleton className="h-5 w-20 rounded-full" />
          <div className="flex items-center gap-2">
            <Skeleton className="h-1.5 w-20 rounded-full" />
            <Skeleton className="h-3 w-6" />
          </div>
          <Skeleton className="h-6 w-12 rounded-md" />
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
  // Entry-date range filter (YYYY-MM-DD strings from <input type="date">).
  const [entryFrom, setEntryFrom] = useState("");
  const [entryTo, setEntryTo] = useState("");
  // Column sort. Defaults match the API default (entry-date, newest first).
  const [sortBy, setSortBy] = useState<SortColumn>("entry_date");
  const [sortDir, setSortDir] = useState<SortDir>("desc");

  // Toggle sort on a column: same column flips direction, new column starts desc.
  const handleSort = (col: SortColumn) => {
    if (col === sortBy) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortBy(col);
      setSortDir("desc");
    }
  };

  // Fetch stats once on mount (after auth hydrates)
  useEffect(() => {
    if (authLoading) return;

    let cancelled = false;

    async function fetchStats(): Promise<void> {
      try {
        const data = await apiClient.get<LeadsStatsResponse>("/leads/stats", { silent: true });
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
  }, [authLoading]);

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
        params.set("page", "1");
        params.set("per_page", "50");

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
  }, [authLoading, statusFilter, sourceFilter, search, entryFrom, entryTo, sortBy, sortDir]);

  // Build KPI cards from live stats
  const kpiCards = [
    {
      label: "Total Leads",
      value: formatNumber(stats.kpis.total_leads),
      badgeLabel: "—",
      badgeDirection: "up" as const,
      subtitle: "All time",
      borderColor: "#3B82F6",
    },
    {
      label: "This Week",
      value: formatNumber(stats.kpis.leads_this_week),
      badgeLabel: "—",
      badgeDirection: "up" as const,
      subtitle: "Last 7 days",
      borderColor: "#6366F1",
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
    setEntryFrom("");
    setEntryTo("");
  };

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
          <SalesFunnel stages={stats.funnel} />
        )}

        {/* Lead Records Table */}
        {isLoading ? (
          <TableSkeleton />
        ) : (
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
            {/* Table header */}
            <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
              <h2 className="text-sm font-bold text-gray-900">Lead Records</h2>
              <span className="text-xs text-gray-400">
                Showing {leadsData.leads.length} of {leadsData.total.toLocaleString()}
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
                onSourceChange={setSourceFilter}
                entryFrom={entryFrom}
                onEntryFromChange={setEntryFrom}
                entryTo={entryTo}
                onEntryToChange={setEntryTo}
                onClear={handleClearFilters}
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
                {leadsData.leads.length === 0 ? (
                  <tr>
                    <td
                      colSpan={5}
                      className="px-5 py-12 text-center text-sm text-gray-400"
                    >
                      No leads match your filters.
                    </td>
                  </tr>
                ) : (
                  leadsData.leads.map((lead) => (
                    <LeadTableRow key={lead.id} lead={lead} />
                  ))
                )}
              </tbody>
            </table>

            {/* Table footer */}
            <div className="flex items-center justify-between px-5 py-3 border-t border-gray-100 bg-gray-50/50">
              <span className="text-xs text-gray-400">
                Showing {leadsData.leads.length} of {leadsData.total.toLocaleString()} leads
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
    </>
  );
}
