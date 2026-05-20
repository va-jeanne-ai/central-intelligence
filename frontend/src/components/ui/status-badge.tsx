/**
 * Atom: StatusBadge
 *
 * Status pill for entities like offers, leads, campaigns.
 * Matches mockup's .status-badge with .badge-active, .badge-new, etc.
 */

type Status = "active" | "draft" | "paused" | "archived" | "new" | "booked" | "closed" | "lost" | "sent";

interface StatusBadgeProps {
  status: Status;
  className?: string;
}

const STATUS_CLASSES: Record<Status, string> = {
  active: "bg-emerald-50 text-emerald-700 border-emerald-200",
  sent: "bg-emerald-50 text-emerald-700 border-emerald-200",
  new: "bg-blue-50 text-blue-700 border-blue-200",
  booked: "bg-violet-50 text-violet-700 border-violet-200",
  draft: "bg-amber-50 text-amber-700 border-amber-200",
  paused: "bg-amber-50 text-amber-700 border-amber-200",
  closed: "bg-emerald-50 text-emerald-700 border-emerald-200",
  lost: "bg-red-50 text-red-700 border-red-200",
  archived: "bg-gray-100 text-gray-500 border-gray-200",
};

export function StatusBadge({ status, className = "" }: StatusBadgeProps) {
  return (
    <span
      className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold border capitalize ${STATUS_CLASSES[status] ?? STATUS_CLASSES.active} ${className}`}
    >
      {status}
    </span>
  );
}
