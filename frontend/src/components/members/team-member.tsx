"use client";

import Link from "next/link";
import { Card, CardHeader, CardBody } from "@/components/ui/card";

// ─── Types (bound to /members/team*) ────────────────────────────────────────────

export interface TeamMemberRow {
  rep_id: string;
  name: string;
  email: string | null;
  role: string | null;
  status: string;
  hired_at: string | null;
  capabilities: string[];
  calls_count: number;
}

export interface PerformanceBar {
  label: string;
  percent: number;
  detail: string | null;
}
export interface SubmissionRow {
  label: string;
  date: string | null;
  delivered: boolean;
}
export interface CallHistoryRow {
  call_id: string;
  call_type: string | null;
  call_result: string | null;
  date: string | null;
}
export interface TeamMemberDetail {
  rep_id: string;
  name: string;
  email: string | null;
  role: string | null;
  status: string;
  hired_at: string | null;
  days_active: number | null;
  capabilities: string[];
  performance: PerformanceBar[];
  recent_submissions: SubmissionRow[];
  call_history: CallHistoryRow[];
}

// ─── Display helpers (shared by the directory, panel, and detail page) ───────────

export function initials(name: string): string {
  const p = name.trim().split(/\s+/);
  return ((p[0]?.[0] ?? "") + (p.length > 1 ? p[p.length - 1][0] : "")).toUpperCase() || "—";
}

export function formatDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

export function humanizeRole(role: string | null): string {
  if (!role) return "Team member";
  return role.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

// Status → pill + accent. "active" green, "probation" amber/at-risk, else gray/red.
export function statusStyle(status: string): { pill: string; ring: string; atRisk: boolean } {
  const s = status.toLowerCase();
  if (s === "active") return { pill: "bg-emerald-50 text-emerald-700", ring: "", atRisk: false };
  if (s === "probation") return { pill: "bg-amber-50 text-amber-700", ring: "ring-1 ring-amber-300", atRisk: true };
  return { pill: "bg-red-50 text-red-700", ring: "ring-1 ring-red-300", atRisk: true };
}

// Deterministic avatar color from the name (stable per person).
const AVATAR_COLORS = ["#F97316", "#3B82F6", "#10B981", "#8B5CF6", "#EC4899", "#14B8A6", "#EF4444", "#6366F1"];
export function avatarColor(name: string): string {
  let h = 0;
  for (let i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) | 0;
  return AVATAR_COLORS[Math.abs(h) % AVATAR_COLORS.length];
}

export function Avatar({ name, size = "md" }: { name: string; size?: "md" | "lg" | "xl" }) {
  const dim = size === "xl" ? "h-20 w-20 text-2xl" : size === "lg" ? "h-14 w-14 text-lg" : "h-12 w-12 text-sm";
  return (
    <span
      className={`flex flex-shrink-0 items-center justify-center rounded-full font-bold text-white ${dim}`}
      style={{ backgroundColor: avatarColor(name) }}
    >
      {initials(name)}
    </span>
  );
}

export function barColor(label: string): string {
  const l = label.toLowerCase();
  if (l.includes("score")) return "#10B981";
  if (l.includes("calls")) return "#F59E0B";
  return "#3B82F6";
}

// ─── Reusable detail sections (panel + full page share these) ────────────────────

export function PerformanceSection({ performance }: { performance: PerformanceBar[] }) {
  if (performance.length === 0) {
    return <p className="text-[13px] text-gray-400 italic">No performance data.</p>;
  }
  return (
    <div className="space-y-3">
      {performance.map((bar) => (
        <div key={bar.label}>
          <div className="flex items-center justify-between mb-1">
            <span className="text-[13px] font-medium text-gray-700">{bar.label}</span>
            <span className="text-[13px] font-bold text-gray-900">{Math.round(bar.percent)}%</span>
          </div>
          <div className="h-2 rounded-full bg-gray-100 overflow-hidden">
            <div
              className="h-full rounded-full transition-all duration-500"
              style={{ width: `${bar.percent}%`, backgroundColor: barColor(bar.label) }}
            />
          </div>
          {bar.detail && <div className="text-[11px] text-gray-400 mt-0.5">{bar.detail}</div>}
        </div>
      ))}
    </div>
  );
}

export function SubmissionsSection({ submissions }: { submissions: SubmissionRow[] }) {
  if (submissions.length === 0) {
    return <p className="text-[13px] text-gray-400 italic">No reports yet.</p>;
  }
  return (
    <div className="space-y-1.5">
      {submissions.map((sub, i) => (
        <div key={i} className="flex items-center justify-between rounded-lg bg-gray-50 px-3 py-2 text-[13px]">
          <span className="flex items-center gap-2 text-gray-700">
            <span className={`h-2 w-2 rounded-full ${sub.delivered ? "bg-emerald-500" : "bg-gray-300"}`} />
            {sub.label}
          </span>
          <span className="text-[12px] text-gray-400">{formatDate(sub.date)}</span>
        </div>
      ))}
    </div>
  );
}

export function CallHistorySection({ calls }: { calls: CallHistoryRow[] }) {
  if (calls.length === 0) {
    return <p className="text-[13px] text-gray-400 italic">No calls yet.</p>;
  }
  return (
    <div className="space-y-1.5">
      {calls.map((call) => (
        <Link
          key={call.call_id}
          href={`/sales-calls/${call.call_id}?from=members`}
          className="flex items-center justify-between rounded-lg bg-gray-50 px-3 py-2 text-[13px] hover:bg-gray-100 transition-colors"
        >
          <span className="flex items-center gap-2 text-gray-700">
            <span className="h-2 w-2 rounded-full bg-orange-500" />
            {call.call_type || "Call"}
            {call.call_result && <span className="text-gray-400">· {call.call_result}</span>}
          </span>
          <span className="text-[12px] text-gray-400">{formatDate(call.date)}</span>
        </Link>
      ))}
    </div>
  );
}

// Re-export Card primitives for convenience when composing the sections.
export { Card, CardHeader, CardBody };
