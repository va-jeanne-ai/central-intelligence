/**
 * Atom: ScoreBar
 *
 * Horizontal progress bar used for ICP alignment, lead scores, etc.
 * Matches mockup's .icp-score-wrap / .score-bar-wrap patterns.
 * Default color is brand indigo gradient.
 */

interface ScoreBarProps {
  /** Percentage 0–100 */
  value: number;
  label?: string;
  /** Color of the filled portion. Defaults to brand gradient. */
  color?: "brand" | "emerald" | "gray";
  showValue?: boolean;
  className?: string;
}

const COLOR_CLASSES: Record<string, string> = {
  brand: "bg-gradient-to-r from-indigo-600 to-indigo-400",
  emerald: "bg-emerald-500",
  gray: "bg-gray-300",
};

export function ScoreBar({
  value,
  label,
  color = "brand",
  showValue = true,
  className = "",
}: ScoreBarProps) {
  const clamped = Math.max(0, Math.min(100, value));

  return (
    <div className={`flex items-center gap-2.5 ${className}`}>
      {label && (
        <span className="text-[11px] font-semibold text-gray-500 flex-shrink-0">
          {label}
        </span>
      )}
      <div className="flex-1 h-1.5 bg-gray-200 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full ${COLOR_CLASSES[color]}`}
          style={{ width: `${clamped}%` }}
        />
      </div>
      {showValue && (
        <span className="text-sm font-extrabold text-indigo-700 tabular-nums flex-shrink-0">
          {clamped}%
        </span>
      )}
    </div>
  );
}
