// ─── Skeleton primitives ─────────────────────────────────────────────────────
// Reusable shimmer / pulse placeholders for loading states.

interface SkeletonProps {
  className?: string;
  style?: React.CSSProperties;
}

export function Skeleton({ className = "", style }: SkeletonProps) {
  return (
    <div
      className={`animate-pulse rounded bg-gray-200 ${className}`}
      style={style}
      aria-hidden="true"
    />
  );
}

// ─── Pre-built skeletons ─────────────────────────────────────────────────────

/** Matches DepartmentCard layout */
export function DepartmentCardSkeleton() {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
      <div className="flex items-center gap-3 mb-4">
        <Skeleton className="w-9 h-9 rounded-lg" />
        <Skeleton className="h-4 w-24" />
      </div>
      <div className="space-y-3">
        {[1, 2, 3].map((i) => (
          <div key={i} className="flex justify-between items-center">
            <Skeleton className="h-3 w-16" />
            <Skeleton className="h-5 w-12" />
          </div>
        ))}
      </div>
    </div>
  );
}

/** Matches KPI mini-card grid */
export function KpiGridSkeleton() {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
      <div className="flex items-center justify-between mb-4">
        <Skeleton className="h-4 w-48" />
        <Skeleton className="h-3 w-28" />
      </div>
      <div className="grid grid-cols-2 gap-3">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="bg-gray-50 rounded-lg p-3 space-y-2">
            <Skeleton className="h-3 w-16" />
            <Skeleton className="h-6 w-12" />
            <Skeleton className="h-2 w-20" />
          </div>
        ))}
      </div>
      <div className="border-t border-gray-100 mt-4 pt-3">
        <Skeleton className="h-2 w-28 mb-2" />
        <div className="flex items-end gap-1 h-10">
          {[1, 2, 3, 4, 5, 6, 7, 8].map((i) => (
            <Skeleton
              key={i}
              className="flex-1 rounded-sm"
              style={{ height: `${30 + Math.random() * 60}%` } as React.CSSProperties}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

/** Matches CIWidget layout */
export function CIWidgetSkeleton() {
  return (
    <div className="bg-indigo-50 rounded-xl border border-indigo-200/50 p-5 shadow-sm">
      <div className="flex items-center gap-2 mb-4">
        <Skeleton className="w-8 h-8 rounded-full bg-indigo-200" />
        <Skeleton className="h-4 w-44 bg-indigo-200" />
      </div>
      <div className="space-y-3">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="flex items-start gap-3">
            <Skeleton className="w-5 h-5 rounded bg-indigo-200 flex-shrink-0 mt-0.5" />
            <div className="flex-1 space-y-1">
              <Skeleton className="h-3 w-full bg-indigo-200" />
              <Skeleton className="h-3 w-3/4 bg-indigo-200" />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/** Full-page centered spinner */
export function PageSpinner({ label = "Loading..." }: { label?: string }) {
  return (
    <div className="flex flex-col items-center justify-center flex-1 gap-3" role="status">
      <div className="w-8 h-8 border-3 border-gray-200 border-t-indigo-500 rounded-full animate-spin" />
      <span className="text-sm text-gray-400">{label}</span>
    </div>
  );
}

/** Chat-specific: connecting overlay */
export function ChatConnecting() {
  return (
    <div className="flex flex-col items-center justify-center flex-1 gap-3" role="status">
      <div className="relative">
        <div className="w-12 h-12 rounded-full border-3 border-gray-200 border-t-indigo-500 animate-spin" />
        <span className="absolute inset-0 flex items-center justify-center text-lg">
          👑
        </span>
      </div>
      <span className="text-sm text-gray-500 font-medium">Connecting to Central Intelligence...</span>
      <span className="text-xs text-gray-400">Setting up your secure session</span>
    </div>
  );
}

// ─── Table and chart skeletons ────────────────────────────────────────────────

interface TableSkeletonProps {
  rows?: number;
  cols?: number;
  showFilters?: boolean;
}

/** Generic reusable table skeleton */
export function TableSkeleton({
  rows = 6,
  cols = 5,
  showFilters = true,
}: TableSkeletonProps) {
  const safeCols = Math.min(Math.max(cols, 1), 6);
  const safeRows = Math.max(rows, 1);

  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
        <Skeleton className="h-4 w-36" />
        <Skeleton className="h-5 w-10 rounded-full" />
      </div>

      {/* Optional filter row */}
      {showFilters && (
        <div className="flex items-center gap-2 px-5 py-3 border-b border-gray-100">
          <Skeleton className="h-8 flex-1 max-w-xs rounded-lg" />
          <Skeleton className="h-7 w-20 rounded-full" />
          <Skeleton className="h-7 w-20 rounded-full" />
          <Skeleton className="h-7 w-20 rounded-full" />
        </div>
      )}

      {/* Data rows */}
      <div className="divide-y divide-gray-100">
        {Array.from({ length: safeRows }).map((_, rowIndex) => (
          <div key={rowIndex} className="flex items-center gap-4 px-5 py-3">
            {Array.from({ length: safeCols }).map((_, colIndex) => (
              <Skeleton
                key={colIndex}
                className={`h-3 ${colIndex === 0 ? "w-32" : colIndex === safeCols - 1 ? "w-16" : "flex-1"}`}
              />
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

interface ChartCardSkeletonProps {
  height?: string;
}

/** Generic single chart card skeleton */
export function ChartCardSkeleton({ height = "h-36" }: ChartCardSkeletonProps) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5">
      <Skeleton className="h-4 w-40 mb-4" />
      <Skeleton className={`w-full ${height} rounded-lg`} />
    </div>
  );
}

/** Donut/pie chart card skeleton */
export function DonutChartSkeleton() {
  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5">
      <Skeleton className="h-4 w-40 mb-4" />
      <div className="flex items-center gap-6">
        {/* Donut circle */}
        <Skeleton className="w-36 h-36 rounded-full flex-shrink-0" />
        {/* Legend rows */}
        <div className="flex-1 space-y-3">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="flex items-center gap-2">
              <Skeleton className="w-3 h-3 rounded-sm flex-shrink-0" />
              <Skeleton className="h-3 flex-1" />
              <Skeleton className="h-3 w-8 flex-shrink-0" />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
