/**
 * Molecule: KpiCard
 *
 * KPI metric card with colored top border, large value, optional trend badge and subtitle.
 * Matches mockup's .kpi-card with border-top: 3px solid <departmentColor>.
 *
 * Usage:
 *   <KpiCard label="Active Offers" value="4" borderColor="#10B981" sub="2 drafts" />
 *   <KpiCard label="Response Rate" value="68%" borderColor="#3B82F6" badge="↑ 5%" badgeVariant="up" />
 */

import { Badge } from "@/components/ui/badge";

interface KpiCardProps {
  label: string;
  value: string;
  /** CSS color for the top border accent */
  borderColor?: string;
  /** Trend badge text, e.g. "↑ 22% this week" */
  badge?: string;
  badgeVariant?: "up" | "down" | "neutral";
  /** Small subtitle below the value */
  sub?: string;
  className?: string;
}

export function KpiCard({
  label,
  value,
  borderColor,
  badge,
  badgeVariant = "up",
  sub,
  className = "",
}: KpiCardProps) {
  return (
    <div
      className={`bg-white rounded-xl p-5 border border-gray-200 shadow-sm hover:shadow-md hover:-translate-y-0.5 transition-all duration-200 ${className}`}
      style={borderColor ? { borderTop: `3px solid ${borderColor}` } : undefined}
    >
      <div className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">
        {label}
      </div>
      <div className="text-[28px] font-extrabold text-gray-900 tracking-tight leading-none tabular-nums">
        {value}
      </div>
      {badge && (
        <div className="mt-2">
          <Badge variant={badgeVariant}>{badge}</Badge>
        </div>
      )}
      {sub && (
        <div className="text-xs text-gray-500 mt-1.5">{sub}</div>
      )}
    </div>
  );
}

/**
 * Molecule: KpiRow
 *
 * Grid of 4 KPI cards. Matches mockup's .grid-4 layout.
 */
export function KpiRow({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={`grid grid-cols-4 gap-3.5 ${className}`}>
      {children}
    </div>
  );
}
