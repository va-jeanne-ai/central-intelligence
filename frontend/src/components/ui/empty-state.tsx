// ─── EmptyState ───────────────────────────────────────────────────────────────
// Generic empty-state placeholder for zero-data views.

interface EmptyStateAction {
  label: string;
  onClick: () => void;
}

interface EmptyStateProps {
  icon?: string;
  title: string;
  description?: string;
  action?: EmptyStateAction;
  secondaryAction?: EmptyStateAction;
  className?: string;
}

export function EmptyState({
  icon = "📭",
  title,
  description,
  action,
  secondaryAction,
  className = "",
}: EmptyStateProps) {
  return (
    <div
      className={`
        flex flex-col items-center justify-center
        bg-gray-50 rounded-xl border border-dashed border-gray-200
        p-12 text-center
        ${className}
      `}
      role="status"
      aria-label={title}
    >
      {/* Icon */}
      <span
        className="leading-none select-none mb-4"
        style={{ fontSize: "2.5rem" }}
        role="img"
        aria-hidden="true"
      >
        {icon}
      </span>

      {/* Title */}
      <p className="text-sm font-semibold text-gray-700">{title}</p>

      {/* Description */}
      {description && (
        <p className="text-xs text-gray-400 mt-1 max-w-xs">{description}</p>
      )}

      {/* Actions */}
      {(action || secondaryAction) && (
        <div className="flex flex-col items-center gap-2 mt-5">
          {action && (
            <button
              type="button"
              onClick={action.onClick}
              className="
                inline-flex items-center justify-center
                px-4 py-2 rounded-lg
                bg-accent-500 hover:bg-accent-600 active:bg-accent-700
                text-white text-xs font-semibold
                transition-colors duration-150
                focus:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 focus-visible:ring-offset-2
              "
            >
              {action.label}
            </button>
          )}
          {secondaryAction && (
            <button
              type="button"
              onClick={secondaryAction.onClick}
              className="
                text-xs text-gray-400 hover:text-gray-600
                underline underline-offset-2
                transition-colors duration-150
                focus:outline-none focus-visible:ring-2 focus-visible:ring-gray-400 focus-visible:ring-offset-2 rounded
              "
            >
              {secondaryAction.label}
            </button>
          )}
        </div>
      )}
    </div>
  );
}
