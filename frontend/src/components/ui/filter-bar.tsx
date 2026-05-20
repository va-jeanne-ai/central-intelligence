/**
 * Molecule: FilterBar
 *
 * Horizontal row of search input + filter selects.
 * Matches mockup's .filter-bar layout.
 */

interface FilterBarProps {
  children: React.ReactNode;
  className?: string;
}

export function FilterBar({ children, className = "" }: FilterBarProps) {
  return (
    <div className={`flex items-center gap-2.5 flex-wrap ${className}`}>
      {children}
    </div>
  );
}
