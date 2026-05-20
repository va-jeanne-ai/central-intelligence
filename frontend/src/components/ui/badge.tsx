/**
 * Atom: Badge
 *
 * Trend badges (↑ 22%, ↓ 3%) and generic pills used throughout the app.
 * Matches the mockup's .kpi-badge, .badge-up, .badge-down classes.
 */

interface BadgeProps {
  children: React.ReactNode;
  variant?: "up" | "down" | "neutral";
  className?: string;
}

const VARIANT_CLASSES: Record<string, string> = {
  up: "bg-emerald-100 text-emerald-800",
  down: "bg-red-100 text-red-800",
  neutral: "bg-gray-100 text-gray-600",
};

export function Badge({ children, variant = "neutral", className = "" }: BadgeProps) {
  return (
    <span
      className={`inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-0.5 rounded-full ${VARIANT_CLASSES[variant]} ${className}`}
    >
      {children}
    </span>
  );
}
