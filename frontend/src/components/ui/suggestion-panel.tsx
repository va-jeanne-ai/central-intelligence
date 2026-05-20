/**
 * Molecule: SuggestionPanel
 *
 * Indigo-tinted panel for AI optimization suggestions.
 * Matches mockup's .suggestion-panel, .suggestion-item pattern.
 */

interface SuggestionItemData {
  title: string;
  body: string;
}

interface SuggestionPanelProps {
  title?: string;
  icon?: string;
  items: SuggestionItemData[];
  className?: string;
}

export function SuggestionPanel({
  title = "AI Optimization Suggestions",
  icon = "💡",
  items,
  className = "",
}: SuggestionPanelProps) {
  return (
    <div
      className={`bg-indigo-50 border border-indigo-200 rounded-xl overflow-hidden ${className}`}
    >
      {/* Header */}
      <div className="flex items-center gap-2 px-5 py-3 border-b border-indigo-200/60">
        <span className="text-base">{icon}</span>
        <span className="text-sm font-bold text-gray-800">{title}</span>
      </div>

      {/* Items */}
      <div className="divide-y divide-indigo-200/40">
        {items.map((item) => (
          <div key={item.title} className="flex items-start gap-3 px-5 py-3.5">
            <span className="text-emerald-600 flex-shrink-0 mt-0.5 font-bold">→</span>
            <div className="text-[13px] text-gray-700 leading-relaxed">
              <strong className="text-gray-900">{item.title}</strong>
              {" — "}
              {item.body}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
