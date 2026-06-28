import type { DepartmentStats } from "@/types";

// ─── Style maps ────────────────────────────────────────────────────────────────
// Gradient fills per webapp-mockup.html screen 1 (.dept-card.{marketing,sales,
// fulfillment}). Bold colored cards with white text, not white-with-border.

const GRADIENT: Record<DepartmentStats["color"], string> = {
  marketing: "bg-gradient-to-br from-emerald-600 to-emerald-500",
  sales: "bg-gradient-to-br from-blue-700 to-blue-500",
  fulfillment: "bg-gradient-to-br from-orange-600 to-orange-500",
};

// ─── Component ─────────────────────────────────────────────────────────────────

export function DepartmentCard({ name, icon, color, stats }: DepartmentStats) {
  return (
    <article
      className={`
        relative overflow-hidden rounded-xl p-5 text-white shadow-sm
        transition duration-200 hover:-translate-y-0.5 hover:shadow-md
        ${GRADIENT[color]}
      `}
      aria-label={`${name} department summary`}
    >
      {/* Decorative corner circle (mockup .dept-card::after) */}
      <span
        className="pointer-events-none absolute -right-5 -bottom-5 h-24 w-24 rounded-full bg-white/[0.08]"
        aria-hidden="true"
      />

      {/* Label + title */}
      <div className="relative">
        <div className="text-[11px] font-bold uppercase tracking-[0.1em] opacity-80">
          Department
        </div>
        <div className="mt-1 mb-3 flex items-center gap-1.5 text-[17px] font-bold">
          <span role="img" aria-label={name}>
            {icon}
          </span>
          {name}
        </div>
      </div>

      {/* Stats row */}
      <div className="relative flex gap-5">
        {stats.map((stat) => (
          <div key={stat.label} className="min-w-0">
            <span className="block text-[22px] font-extrabold leading-none tracking-[-0.03em] tabular-nums">
              {stat.value}
            </span>
            <span className="text-[11px] opacity-75">{stat.label}</span>
          </div>
        ))}
      </div>
    </article>
  );
}
