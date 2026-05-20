import type { DepartmentStats } from "@/types";

// ─── Style maps ────────────────────────────────────────────────────────────────

const BORDER_COLOR: Record<DepartmentStats["color"], string> = {
  marketing: "border-l-emerald-500",
  sales: "border-l-blue-500",
  fulfillment: "border-l-orange-500",
};

const LABEL_COLOR: Record<DepartmentStats["color"], string> = {
  marketing: "text-emerald-600",
  sales: "text-blue-600",
  fulfillment: "text-orange-600",
};

const BADGE_COLOR: Record<DepartmentStats["color"], string> = {
  marketing: "bg-emerald-50 text-emerald-700",
  sales: "bg-blue-50 text-blue-700",
  fulfillment: "bg-orange-50 text-orange-700",
};

// ─── Component ─────────────────────────────────────────────────────────────────

export function DepartmentCard({ name, icon, color, stats }: DepartmentStats) {
  return (
    <article
      className={`
        bg-white rounded-xl border border-gray-200 border-l-4
        ${BORDER_COLOR[color]}
        p-5 flex flex-col gap-4 shadow-sm
      `}
      aria-label={`${name} department summary`}
    >
      {/* Header */}
      <div className="flex items-center gap-2">
        <span className="text-lg leading-none" role="img" aria-label={name}>
          {icon}
        </span>
        <span className={`text-sm font-bold tracking-wide uppercase ${LABEL_COLOR[color]}`}>
          {name}
        </span>
      </div>

      {/* Stats row */}
      <div className="flex gap-4">
        {stats.map((stat) => (
          <div key={stat.label} className="flex flex-col gap-0.5 min-w-0 flex-1">
            <span className="text-[10px] font-semibold uppercase tracking-wider text-gray-400 truncate">
              {stat.label}
            </span>
            <span className="text-xl font-bold text-gray-900 leading-tight tabular-nums">
              {stat.value}
            </span>
            {stat.sub !== undefined && (
              <span className={`text-[11px] font-medium px-1.5 py-0.5 rounded-full self-start mt-0.5 ${BADGE_COLOR[color]}`}>
                {stat.sub}
              </span>
            )}
          </div>
        ))}
      </div>
    </article>
  );
}
