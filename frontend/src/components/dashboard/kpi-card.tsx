// ─── Types ─────────────────────────────────────────────────────────────────────

interface KpiCardProps {
  label: string;
  value: string;
  change: number;
  changeDirection: "up" | "down";
  subtitle?: string;
}

// ─── Component ─────────────────────────────────────────────────────────────────

export function KpiCard({
  label,
  value,
  change,
  changeDirection,
  subtitle,
}: KpiCardProps) {
  const isPositive = changeDirection === "up";

  const badgeClasses = isPositive
    ? "bg-emerald-50 text-emerald-700"
    : "bg-red-50 text-red-600";

  const arrow = isPositive ? "↑" : "↓";
  const sign = isPositive ? "+" : "";

  return (
    <div
      className="bg-white rounded-lg border border-gray-200 px-4 py-3 flex flex-col gap-1 shadow-sm"
      role="group"
      aria-label={label}
    >
      {/* Label */}
      <span className="text-[10px] font-bold uppercase tracking-widest text-gray-400">
        {label}
      </span>

      {/* Value + badge row */}
      <div className="flex items-end gap-2">
        <span className="text-2xl font-bold text-gray-900 leading-none tabular-nums">
          {value}
        </span>
        <span
          className={`mb-0.5 text-[11px] font-semibold px-1.5 py-0.5 rounded-full ${badgeClasses}`}
          aria-label={`${isPositive ? "Up" : "Down"} ${Math.abs(change)}%`}
        >
          {arrow} {sign}{Math.abs(change)}%
        </span>
      </div>

      {/* Subtitle */}
      {subtitle !== undefined && (
        <span className="text-xs text-gray-400">{subtitle}</span>
      )}
    </div>
  );
}
