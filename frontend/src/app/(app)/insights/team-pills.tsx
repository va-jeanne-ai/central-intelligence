// ─── Team tab — small local pill atoms ──────────────────────────────────────────
// The shared StatusBadge/Badge atoms don't have variants for rep status
// (active/probation) or trend verdicts (improving/declining/flat/insufficient
// data), so these are hand-rolled locally per the design doc rather than
// widening the shared atoms for one page.

import type { StatusPillVariant, TrendPillVariant } from "./team-formatting";
import { trendPillLabel } from "./team-formatting";

const STATUS_STYLE: Record<StatusPillVariant, string> = {
  active: "bg-emerald-50 text-emerald-700",
  probation: "bg-amber-50 text-amber-700",
  terminated: "bg-gray-100 text-gray-500",
};

export function RepStatusPill({ status }: { status: StatusPillVariant }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10.5px] font-semibold capitalize ${STATUS_STYLE[status]}`}
    >
      {status}
    </span>
  );
}

const TREND_STYLE: Record<TrendPillVariant, string> = {
  up: "bg-emerald-50 text-emerald-700",
  down: "bg-red-50 text-red-700",
  flat: "bg-gray-100 text-gray-500",
  thin: "bg-amber-50 text-amber-600",
};

export function TrendPill({ verdict }: { verdict: string }) {
  const variant: TrendPillVariant =
    verdict === "improving" ? "up" : verdict === "declining" ? "down" : verdict === "flat" ? "flat" : "thin";
  return (
    <span
      className={`inline-flex items-center whitespace-nowrap rounded-full px-2 py-0.5 text-[10.5px] font-semibold ${TREND_STYLE[variant]}`}
    >
      {trendPillLabel(verdict)}
    </span>
  );
}
