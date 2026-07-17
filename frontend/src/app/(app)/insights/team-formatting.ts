// ─── Team tab — pure formatting/derivation helpers ─────────────────────────────
// Extracted so they can be unit-tested without mounting the component tree.
// No client-side derivation of business values beyond formatting and the
// weighted team average — every other number comes verbatim from the API.

import { formatCurrency } from "@/lib/format";

export interface RepMetricBlock {
  metric_key: string;
  label: string;
  area: string;
  unit: string;
  higher_is_better: boolean;
  value: number | null;
  sample_size: number | null;
  verdict: string; // improving | declining | flat | insufficient_data
  rel_change: number | null;
  baseline_value: number | null;
  reason: string;
}

export interface TeamRecommendation {
  id: number;
  metric_key: string;
  area: string;
  window: string;
  verdict: string;
  severity: string;
  title: string;
  body: string;
  evidence: Record<string, unknown>;
  status: string;
  updated_at: string | null;
}

export interface TeamRep {
  rep_id: string;
  full_name: string;
  role: string | null;
  status: string; // active | probation (terminated reps never appear)
  metrics: Record<string, RepMetricBlock>;
  recommendations: TeamRecommendation[];
}

export interface TeamRollup {
  total_outbound: number;
  open_strikes: number;
  active_reps: number;
  total_reps: number;
}

export interface TeamAnalyticsResponse {
  window: string;
  reps: TeamRep[];
  rollup: TeamRollup;
}

export const CALL_SCORE_KEY = "sales.avg_call_score";
export const OUTBOUND_KEY = "sales.outbound_volume";
export const CLOSES_KEY = "sales.closed_sales_count";
export const REVENUE_KEY = "sales.revenue_collected";
export const STRIKES_KEY = "fulfillment.open_coaching_strikes";

// ─── Value formatting (mirrors the page's existing formatValue) ───────────────

export function formatValue(v: number | null, unit: string): string {
  if (v === null) return "—";
  if (unit === "ratio") return `${(v * 100).toFixed(1)}%`;
  if (unit === "currency") return formatCurrency(v);
  if (unit === "score") return v.toFixed(2);
  return Math.round(v).toLocaleString();
}

export function formatCount(v: number | null | undefined): string {
  if (v === null || v === undefined) return "—";
  return Math.round(v).toLocaleString();
}

export function formatRelChange(relChange: number | null): string | null {
  if (relChange === null || !Number.isFinite(relChange)) return null;
  return `${relChange >= 0 ? "+" : ""}${(relChange * 100).toFixed(0)}%`;
}

/** Sample-size-weighted average call score across reps, derived purely from
 * the per-rep metric blocks the API already returned (no invented numbers).
 * Reps with a null value or null/zero sample_size are excluded. Returns null
 * when no rep has a usable score yet — the launch-day common case. */
export function weightedTeamCallScore(reps: TeamRep[]): { value: number | null; totalSamples: number } {
  let weightedSum = 0;
  let totalSamples = 0;

  for (const rep of reps) {
    const block = rep.metrics[CALL_SCORE_KEY];
    if (!block || block.value === null || !block.sample_size) continue;
    weightedSum += block.value * block.sample_size;
    totalSamples += block.sample_size;
  }

  if (totalSamples === 0) return { value: null, totalSamples: 0 };
  return { value: weightedSum / totalSamples, totalSamples };
}

/** Sort reps by outbound volume descending (nulls/missing sink to the bottom). */
export function sortRepsByOutboundDesc(reps: TeamRep[]): TeamRep[] {
  return [...reps].sort((a, b) => {
    const av = a.metrics[OUTBOUND_KEY]?.value ?? -1;
    const bv = b.metrics[OUTBOUND_KEY]?.value ?? -1;
    return bv - av;
  });
}

export type StatusPillVariant = "active" | "probation" | "terminated";

export function statusPillVariant(status: string): StatusPillVariant {
  if (status === "active") return "active";
  if (status === "probation") return "probation";
  return "terminated";
}

export type TrendPillVariant = "up" | "down" | "flat" | "thin";

export function trendPillVariant(verdict: string): TrendPillVariant {
  if (verdict === "improving") return "up";
  if (verdict === "declining") return "down";
  if (verdict === "flat") return "flat";
  return "thin"; // insufficient_data (and any unrecognized verdict)
}

export function trendPillLabel(verdict: string): string {
  if (verdict === "improving") return "▲ improving";
  if (verdict === "declining") return "▼ declining";
  if (verdict === "flat") return "flat";
  return "insufficient data";
}
