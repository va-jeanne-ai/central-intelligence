// Shared appointment status palette — single source of truth for the color
// coding used on the Appointments list page, its calendar view, and the
// appointment chips overlaid on the main /calendar page.
//
// Color convention (shared with the Sales Calls page): green = completed/
// showed, blue = scheduled/booked, gray = cancelled, red = no-show, amber =
// in-between states like rescheduled/confirmed.

// Real appointment statuses (app DB, verified live): completed, cancelled,
// scheduled, no_show, plus null/unknown. The older booked/confirmed/showed/
// no-show/rescheduled vocabulary below is kept for any legacy/manual rows
// that still carry it — resolveAppointmentStatus falls back to a neutral
// pill for anything unrecognized either way.
export type AppointmentStatus =
  | "completed"
  | "cancelled"
  | "scheduled"
  | "no_show"
  | "booked"
  | "confirmed"
  | "showed"
  | "no-show"
  | "rescheduled";

export interface AppointmentStatusConfig {
  label: string;
  dotColor: string;
  badgeClasses: string;
  /** Tailwind classes for a chip/pill background + text + border. */
  chipClasses: string;
}

export const APPOINTMENT_STATUS_CONFIG: Record<AppointmentStatus, AppointmentStatusConfig> = {
  completed: {
    label: "Completed",
    dotColor: "#10B981",
    badgeClasses: "bg-green-50 text-green-700",
    chipClasses: "bg-green-50 text-green-800 border-green-200 hover:bg-green-100",
  },
  scheduled: {
    label: "Scheduled",
    dotColor: "#3B82F6",
    badgeClasses: "bg-blue-50 text-blue-700",
    chipClasses: "bg-blue-50 text-blue-800 border-blue-200 hover:bg-blue-100",
  },
  cancelled: {
    label: "Cancelled",
    dotColor: "#9CA3AF",
    badgeClasses: "bg-gray-100 text-gray-500",
    chipClasses: "bg-gray-100 text-gray-500 border-gray-200 hover:bg-gray-200",
  },
  no_show: {
    label: "No-Show",
    dotColor: "#EF4444",
    badgeClasses: "bg-red-50 text-red-700",
    chipClasses: "bg-red-50 text-red-800 border-red-200 hover:bg-red-100",
  },
  booked: {
    label: "Booked",
    dotColor: "#3B82F6",
    badgeClasses: "bg-blue-50 text-blue-700",
    chipClasses: "bg-blue-50 text-blue-800 border-blue-200 hover:bg-blue-100",
  },
  confirmed: {
    label: "Confirmed",
    dotColor: "#F59E0B",
    badgeClasses: "bg-accent-50 text-accent-700",
    chipClasses: "bg-amber-50 text-amber-800 border-amber-200 hover:bg-amber-100",
  },
  showed: {
    label: "Showed",
    dotColor: "#10B981",
    badgeClasses: "bg-green-50 text-green-700",
    chipClasses: "bg-green-50 text-green-800 border-green-200 hover:bg-green-100",
  },
  "no-show": {
    label: "No-Show",
    dotColor: "#EF4444",
    badgeClasses: "bg-red-50 text-red-700",
    chipClasses: "bg-red-50 text-red-800 border-red-200 hover:bg-red-100",
  },
  rescheduled: {
    label: "Rescheduled",
    dotColor: "#F59E0B",
    badgeClasses: "bg-amber-50 text-amber-700",
    chipClasses: "bg-amber-50 text-amber-800 border-amber-200 hover:bg-amber-100",
  },
};

const FALLBACK_CONFIG: AppointmentStatusConfig = {
  label: "—",
  dotColor: "#9CA3AF",
  badgeClasses: "bg-gray-100 text-gray-600",
  chipClasses: "bg-gray-100 text-gray-600 border-gray-200 hover:bg-gray-200",
};

export function resolveAppointmentStatus(raw: string | null): AppointmentStatusConfig {
  const config = APPOINTMENT_STATUS_CONFIG[(raw ?? "") as AppointmentStatus];
  if (config) return config;
  return raw ? { ...FALLBACK_CONFIG, label: raw } : FALLBACK_CONFIG;
}
