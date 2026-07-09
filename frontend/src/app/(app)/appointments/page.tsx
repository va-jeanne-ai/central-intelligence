"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { Header } from "@/components/layout/header";
import { Skeleton } from "@/components/ui/skeleton";
import { KpiCard } from "@/components/ui/kpi-card";
import { Button } from "@/components/ui/button";
import { apiClient } from "@/lib/api-client";
import { useAuth } from "@/hooks/use-auth";
import { usePagination } from "@/hooks/use-pagination";
import { Pagination } from "@/components/ui";
import { showSuccess, showApiError } from "@/lib/toast";

// ─── Types ───────────────────────────────────────────────────────────────────

// Real appointment statuses (app DB, verified live): completed, cancelled,
// scheduled, no_show, plus null/unknown. The older booked/confirmed/showed/
// no-show/rescheduled vocabulary below is kept in STATUS_CONFIG for any
// legacy/manual rows that still carry it — resolveStatus falls back to a
// neutral pill for anything unrecognized either way.
type AppointmentStatus =
  | "completed"
  | "cancelled"
  | "scheduled"
  | "no_show"
  | "booked"
  | "confirmed"
  | "showed"
  | "no-show"
  | "rescheduled";

interface AppointmentRow {
  id: string;
  contact_name: string | null;
  contact_email: string | null;
  lead_id: string | null;
  member_id: string | null;
  status: string | null;
  appointment_type: string | null;
  scheduledAt: string | null;
  source: string | null;
  rep_id: string | null;
  rep_name: string | null;
}

interface RepOption {
  rep_id: string;
  full_name: string;
  status: string;
}

interface AppointmentsListResponse {
  appointments: AppointmentRow[];
  total: number;
  page: number;
  per_page: number;
}

interface AppointmentsKpis {
  total: number;
  upcoming_this_week: number;
  showed: number;
  no_show: number;
  show_rate: number;
  no_show_rate: number;
}

interface AppointmentsStatsResponse {
  kpis: AppointmentsKpis;
  appointment_volume: { label: string; value: number }[];
  status_breakdown: { status: string; count: number; percentage: number }[];
}

// ─── Constants ────────────────────────────────────────────────────────────────

const BLUE = "#3B82F6";

const EMPTY_KPIS: AppointmentsKpis = {
  total: 0,
  upcoming_this_week: 0,
  showed: 0,
  no_show: 0,
  show_rate: 0,
  no_show_rate: 0,
};

const EMPTY_LIST: AppointmentsListResponse = {
  appointments: [],
  total: 0,
  page: 1,
  per_page: 50,
};

type FilterStatus = "all" | AppointmentStatus;
type FilterWindow = "all" | "upcoming" | "this_week";

// Color convention (shared with the Sales Calls page): green = completed/
// showed, blue = scheduled/booked, gray = cancelled, red = no-show, amber =
// in-between states like rescheduled/confirmed.
const STATUS_CONFIG: Record<AppointmentStatus, { label: string; dotColor: string; badgeClasses: string }> = {
  completed: { label: "Completed", dotColor: "#10B981", badgeClasses: "bg-green-50 text-green-700" },
  scheduled: { label: "Scheduled", dotColor: "#3B82F6", badgeClasses: "bg-blue-50 text-blue-700" },
  cancelled: { label: "Cancelled", dotColor: "#9CA3AF", badgeClasses: "bg-gray-100 text-gray-500" },
  no_show: { label: "No-Show", dotColor: "#EF4444", badgeClasses: "bg-red-50 text-red-700" },
  booked: { label: "Booked", dotColor: "#3B82F6", badgeClasses: "bg-blue-50 text-blue-700" },
  confirmed: { label: "Confirmed", dotColor: "#F59E0B", badgeClasses: "bg-accent-50 text-accent-700" },
  showed: { label: "Showed", dotColor: "#10B981", badgeClasses: "bg-green-50 text-green-700" },
  "no-show": { label: "No-Show", dotColor: "#EF4444", badgeClasses: "bg-red-50 text-red-700" },
  rescheduled: { label: "Rescheduled", dotColor: "#F59E0B", badgeClasses: "bg-amber-50 text-amber-700" },
};

function resolveStatus(raw: string | null) {
  return (
    STATUS_CONFIG[(raw ?? "") as AppointmentStatus] ?? {
      label: raw ?? "—",
      dotColor: "#9CA3AF",
      badgeClasses: "bg-gray-100 text-gray-600",
    }
  );
}

function formatScheduled(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("en-US", {
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

// ─── Add Appointment modal ──────────────────────────────────────────────────

function AddAppointmentModal({
  open,
  onClose,
  onCreated,
}: {
  open: boolean;
  onClose: () => void;
  onCreated: () => void;
}) {
  const [scheduledAt, setScheduledAt] = useState("");
  const [contactName, setContactName] = useState("");
  const [contactEmail, setContactEmail] = useState("");
  const [appointmentType, setAppointmentType] = useState("");
  const [leadId, setLeadId] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (open) {
      setScheduledAt("");
      setContactName("");
      setContactEmail("");
      setAppointmentType("");
      setLeadId("");
      setSaving(false);
    }
  }, [open]);

  if (!open) return null;

  async function submit() {
    if (scheduledAt.trim() === "") {
      showApiError("Scheduled time is required");
      return;
    }
    setSaving(true);
    try {
      // datetime-local has no timezone; send as-is (ISO-ish) — backend parses it.
      await apiClient.post("/appointments", {
        scheduled_at: scheduledAt,
        contact_name: contactName.trim() || null,
        contact_email: contactEmail.trim() || null,
        appointment_type: appointmentType.trim() || null,
        lead_id: leadId.trim() || null,
      });
      showSuccess("Appointment booked");
      onCreated();
      onClose();
    } catch (err) {
      showApiError(err as Error);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      role="dialog"
      aria-modal="true"
      aria-label="Add appointment"
      onClick={onClose}
    >
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md p-6" onClick={(e) => e.stopPropagation()}>
        <h2 className="text-base font-bold text-gray-900">Book Appointment</h2>
        <p className="text-xs text-gray-500 mt-0.5">Manually log a booked call or meeting.</p>

        <div className="mt-4 space-y-3">
          <label className="block">
            <span className="text-[11px] font-bold uppercase tracking-widest text-gray-400">Scheduled *</span>
            <input
              type="datetime-local"
              value={scheduledAt}
              onChange={(e) => setScheduledAt(e.target.value)}
              autoFocus
              className="mt-1 w-full text-sm border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-300"
            />
          </label>
          <label className="block">
            <span className="text-[11px] font-bold uppercase tracking-widest text-gray-400">Contact Name</span>
            <input
              type="text"
              value={contactName}
              onChange={(e) => setContactName(e.target.value)}
              className="mt-1 w-full text-sm border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-300"
            />
          </label>
          <label className="block">
            <span className="text-[11px] font-bold uppercase tracking-widest text-gray-400">Contact Email</span>
            <input
              type="email"
              value={contactEmail}
              onChange={(e) => setContactEmail(e.target.value)}
              className="mt-1 w-full text-sm border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-300"
            />
          </label>
          <div className="grid grid-cols-2 gap-3">
            <label className="block">
              <span className="text-[11px] font-bold uppercase tracking-widest text-gray-400">Type</span>
              <input
                type="text"
                value={appointmentType}
                onChange={(e) => setAppointmentType(e.target.value)}
                placeholder="Sales Call"
                className="mt-1 w-full text-sm border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-300"
              />
            </label>
            <label className="block">
              <span className="text-[11px] font-bold uppercase tracking-widest text-gray-400">Lead ID</span>
              <input
                type="text"
                value={leadId}
                onChange={(e) => setLeadId(e.target.value)}
                placeholder="optional"
                className="mt-1 w-full text-sm border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-300"
              />
            </label>
          </div>
        </div>

        <div className="mt-6 flex justify-end gap-2">
          <Button variant="ghost" size="sm" onClick={onClose} disabled={saving}>
            Cancel
          </Button>
          <Button
            variant="primary"
            size="sm"
            onClick={() => void submit()}
            disabled={saving || scheduledAt.trim() === ""}
          >
            {saving ? "Booking…" : "Book Appointment"}
          </Button>
        </div>
      </div>
    </div>
  );
}

// ─── Table Row ────────────────────────────────────────────────────────────────

function AppointmentTableRow({ appt }: { appt: AppointmentRow }) {
  const router = useRouter();
  const status = resolveStatus(appt.status);
  const clickable = Boolean(appt.lead_id);

  return (
    <tr
      onClick={clickable ? () => router.push(`/leads/${appt.lead_id}`) : undefined}
      role={clickable ? "link" : undefined}
      tabIndex={clickable ? 0 : undefined}
      onKeyDown={
        clickable
          ? (e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                router.push(`/leads/${appt.lead_id}`);
              }
            }
          : undefined
      }
      className={`border-b border-gray-50 ${
        clickable ? "hover:bg-blue-50/40 focus:bg-blue-50/40 cursor-pointer focus:outline-none focus:ring-2 focus:ring-inset focus:ring-blue-300" : ""
      } transition-colors`}
    >
      <td className="px-5 py-3.5">
        <div className="flex flex-col">
          <span className="text-sm font-semibold text-gray-900">{appt.contact_name ?? "—"}</span>
          <span className="text-xs text-gray-400">{appt.contact_email ?? "—"}</span>
        </div>
      </td>
      <td className="px-5 py-3.5 text-sm text-gray-700">{appt.rep_name ?? "—"}</td>
      <td className="px-5 py-3.5 text-sm text-gray-700">{formatScheduled(appt.scheduledAt)}</td>
      <td className="px-5 py-3.5">
        <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[11px] font-semibold ${status.badgeClasses}`}>
          <span className="w-1.5 h-1.5 rounded-full flex-shrink-0" style={{ backgroundColor: status.dotColor }} />
          {status.label}
        </span>
      </td>
      <td className="px-5 py-3.5 text-xs text-gray-500">{appt.appointment_type ?? "—"}</td>
    </tr>
  );
}

// ─── Page ────────────────────────────────────────────────────────────────────

export default function AppointmentsPage() {
  const { isLoading: authLoading } = useAuth();
  const [isLoading, setIsLoading] = useState(true);
  const [kpis, setKpis] = useState<AppointmentsKpis>(EMPTY_KPIS);
  const [listData, setListData] = useState<AppointmentsListResponse>(EMPTY_LIST);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<FilterStatus>("all");
  const [windowFilter, setWindowFilter] = useState<FilterWindow>("all");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [repFilter, setRepFilter] = useState("all");
  const [reps, setReps] = useState<RepOption[]>([]);
  const [showAddModal, setShowAddModal] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);

  // Pagination — page size persisted per surface in localStorage.
  const { page, pageSize, setPage, setPageSize, resetToFirstPage } =
    usePagination("appointments");

  // Rep dropdown options — active + probation reps, loaded once.
  useEffect(() => {
    if (authLoading) return;
    void (async () => {
      try {
        const data = await apiClient.get<{ reps: RepOption[] }>("/reps", { silent: true });
        setReps(data.reps ?? []);
      } catch {
        setReps([]);
      }
    })();
  }, [authLoading]);

  // Stats
  useEffect(() => {
    if (authLoading) return;
    let cancelled = false;
    async function fetchStats(): Promise<void> {
      try {
        const data = await apiClient.get<AppointmentsStatsResponse>("/appointments/stats", { silent: true });
        if (!cancelled) setKpis(data.kpis ?? EMPTY_KPIS);
      } catch {
        // keep zeros
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    }
    void fetchStats();
    return () => {
      cancelled = true;
    };
  }, [authLoading, refreshKey]);

  // List
  const searchDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => {
    if (authLoading) return;
    if (searchDebounceRef.current !== null) clearTimeout(searchDebounceRef.current);

    const doFetch = () => {
      let cancelled = false;
      async function fetchList(): Promise<void> {
        const params = new URLSearchParams();
        if (statusFilter !== "all") params.set("status", statusFilter);
        if (windowFilter !== "all") params.set("window", windowFilter);
        if (search) params.set("search", search);
        if (startDate) params.set("start", startDate);
        if (endDate) params.set("end", endDate);
        if (repFilter !== "all") params.set("rep", repFilter);
        params.set("page", String(page));
        params.set("per_page", String(pageSize));
        try {
          const data = await apiClient.get<AppointmentsListResponse>(`/appointments?${params.toString()}`, { silent: true });
          if (!cancelled) setListData(data);
        } catch {
          // keep previous
        }
      }
      void fetchList();
      return () => {
        cancelled = true;
      };
    };

    if (search !== "") {
      searchDebounceRef.current = setTimeout(doFetch, 300);
      return () => {
        if (searchDebounceRef.current !== null) clearTimeout(searchDebounceRef.current);
      };
    }
    return doFetch();
  }, [authLoading, statusFilter, windowFilter, search, startDate, endDate, repFilter, refreshKey, page, pageSize]);

  // When a filter/search narrows the set, jump back to page 1 so the user
  // isn't stranded on a page that no longer exists.
  useEffect(() => {
    resetToFirstPage();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statusFilter, windowFilter, search, startDate, endDate, repFilter]);

  const kpiCards = [
    { label: "Total Appointments", value: String(kpis.total), sub: "All time" },
    { label: "Upcoming This Week", value: String(kpis.upcoming_this_week), sub: "Next 7 days" },
    { label: "Show Rate", value: `${kpis.show_rate}%`, sub: `${kpis.showed} showed` },
    { label: "No-Show Rate", value: `${kpis.no_show_rate}%`, sub: `${kpis.no_show} no-shows` },
  ];

  return (
    <>
      <Header title="Appointments" />

      <main className="flex-1 overflow-y-auto p-7 space-y-6">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-xl font-bold text-gray-900">Appointments</h1>
            <p className="text-sm text-gray-500 mt-0.5">Booked calls and meetings across the pipeline.</p>
          </div>
          <Button variant="primary" size="sm" onClick={() => setShowAddModal(true)}>
            + Book Appointment
          </Button>
        </div>

        {/* KPI Row */}
        {isLoading ? (
          <div className="grid grid-cols-4 gap-4">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm space-y-2">
                <Skeleton className="h-2.5 w-20" />
                <Skeleton className="h-8 w-16" />
                <Skeleton className="h-2.5 w-24" />
              </div>
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-4 gap-4">
            {kpiCards.map((kpi) => (
              <KpiCard key={kpi.label} label={kpi.label} value={kpi.value} borderColor={BLUE} sub={kpi.sub} />
            ))}
          </div>
        )}

        {/* Table */}
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
          <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
            <h2 className="text-sm font-bold text-gray-900">Appointment Records</h2>
            <span className="text-xs text-gray-400">
              Showing {listData.appointments.length} of {listData.total.toLocaleString()}
            </span>
          </div>

          {/* Filter bar */}
          <div className="px-5 py-3 border-b border-gray-100 bg-gray-50/50 flex items-center gap-2.5 flex-wrap">
            <input
              type="text"
              placeholder="Search contact..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="flex-1 min-w-[180px] max-w-xs px-3 py-1.5 text-sm border border-gray-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-400"
            />
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value as FilterStatus)}
              className="px-2.5 py-1.5 text-sm border border-gray-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20 text-gray-600"
            >
              <option value="all">All Statuses</option>
              {(Object.keys(STATUS_CONFIG) as AppointmentStatus[]).map((k) => (
                <option key={k} value={k}>
                  {STATUS_CONFIG[k].label}
                </option>
              ))}
            </select>
            <select
              value={windowFilter}
              onChange={(e) => setWindowFilter(e.target.value as FilterWindow)}
              className="px-2.5 py-1.5 text-sm border border-gray-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20 text-gray-600"
            >
              <option value="all">Any Time</option>
              <option value="this_week">This Week</option>
              <option value="upcoming">Upcoming</option>
            </select>
            <select
              value={repFilter}
              onChange={(e) => setRepFilter(e.target.value)}
              className="px-2.5 py-1.5 text-sm border border-gray-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20 text-gray-600"
            >
              <option value="all">All Reps</option>
              {reps.map((r) => (
                <option key={r.rep_id} value={r.rep_id}>
                  {r.full_name}
                </option>
              ))}
            </select>
            <div className="flex items-center gap-1.5">
              <input
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                aria-label="Start date"
                className="px-2.5 py-1.5 text-sm border border-gray-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20 text-gray-600"
              />
              <span className="text-xs text-gray-400">to</span>
              <input
                type="date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                aria-label="End date"
                className="px-2.5 py-1.5 text-sm border border-gray-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20 text-gray-600"
              />
            </div>
          </div>

          <table className="w-full">
            <thead>
              <tr className="border-b border-gray-100 bg-gray-50">
                {["Contact", "Rep", "Scheduled", "Status", "Type"].map((h) => (
                  <th key={h} className="px-5 py-2.5 text-left text-[10px] font-bold uppercase tracking-widest text-gray-400">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {listData.appointments.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-5 py-12 text-center text-sm text-gray-400">
                    No appointments match your filters.
                  </td>
                </tr>
              ) : (
                listData.appointments.map((appt) => <AppointmentTableRow key={appt.id} appt={appt} />)
              )}
            </tbody>
          </table>

          {!isLoading && listData.total > 0 && (
            <Pagination
              page={page}
              total={listData.total}
              pageSize={pageSize}
              onPageChange={setPage}
              onPageSizeChange={setPageSize}
            />
          )}
        </div>
      </main>

      <AddAppointmentModal
        open={showAddModal}
        onClose={() => setShowAddModal(false)}
        onCreated={() => setRefreshKey((k) => k + 1)}
      />
    </>
  );
}
