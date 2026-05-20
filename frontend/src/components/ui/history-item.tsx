/**
 * Molecule: HistoryItem
 *
 * Timeline row with colored dot, text content, and optional right element.
 * Used in Recent Conversations, Call History, Activity feeds.
 * Matches mockup's .history-item, .history-dot pattern.
 */

interface HistoryItemProps {
  /** CSS color for the left dot */
  dotColor: string;
  children: React.ReactNode;
  /** Right-side element (date, platform tag, etc.) */
  trailing?: React.ReactNode;
  className?: string;
}

export function HistoryItem({ dotColor, children, trailing, className = "" }: HistoryItemProps) {
  return (
    <div className={`flex items-center gap-3 px-5 py-2.5 ${className}`}>
      <div
        className="w-2 h-2 rounded-full flex-shrink-0"
        style={{ backgroundColor: dotColor }}
      />
      <div className="flex-1 min-w-0">{children}</div>
      {trailing && <div className="flex-shrink-0">{trailing}</div>}
    </div>
  );
}

/**
 * Molecule: HistoryList
 *
 * Stacked list of HistoryItem rows with dividers.
 */
export function HistoryList({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={`divide-y divide-gray-100 ${className}`}>
      {children}
    </div>
  );
}
