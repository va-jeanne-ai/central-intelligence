"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { Header } from "@/components/layout/header";
import { Skeleton } from "@/components/ui/skeleton";
import { KpiCard } from "@/components/ui/kpi-card";
import { Button } from "@/components/ui/button";
import { apiClient } from "@/lib/api-client";
import { useAuth } from "@/hooks/use-auth";
import { showSuccess, showApiError } from "@/lib/toast";

// ─── Types ───────────────────────────────────────────────────────────────────

type MemberStatus = "active" | "paused" | "graduated" | "churned";

interface MemberRow {
  id: string;
  name: string | null;
  email: string | null;
  status: string;
  coach_id: string | null;
  enrollmentDate: string | null;
}

interface MembersListResponse {
  members: MemberRow[];
  total: number;
  page: number;
  per_page: number;
}

interface MembersKpis {
  total_members: number;
  members_this_week: number;
  active_members: number;
  goals_completed: number;
}

interface MembersStatsResponse {
  kpis: MembersKpis;
  enrollment_volume: { label: string; value: number }[];
  status_breakdown: { status: string; count: number; percentage: number }[];
  goal_funnel: { stage: string; count: number; percentage: number }[];
}

// ─── Constants ────────────────────────────────────────────────────────────────

const ORANGE = "#F97316";

const EMPTY_KPIS: MembersKpis = {
  total_members: 0,
  members_this_week: 0,
  active_members: 0,
  goals_completed: 0,
};

const EMPTY_LIST: MembersListResponse = {
  members: [],
  total: 0,
  page: 1,
  per_page: 50,
};

type FilterStatus = "all" | MemberStatus;

// ─── Status display config ────────────────────────────────────────────────────

const STATUS_CONFIG: Record<
  MemberStatus,
  { label: string; dotColor: string; badgeClasses: string }
> = {
  active: {
    label: "Active",
    dotColor: "#10B981",
    badgeClasses: "bg-green-50 text-green-700",
  },
  paused: {
    label: "Paused",
    dotColor: "#F59E0B",
    badgeClasses: "bg-amber-50 text-amber-700",
  },
  graduated: {
    label: "Graduated",
    dotColor: "#6366F1",
    badgeClasses: "bg-indigo-50 text-indigo-700",
  },
  churned: {
    label: "Churned",
    dotColor: "#9CA3AF",
    badgeClasses: "bg-gray-100 text-gray-500",
  },
};

function _humanise(value: string): string {
  return value
    .split(/[_\-\s]+/)
    .filter(Boolean)
    .map((w) =>
      w.length <= 3
        ? w.toUpperCase()
        : w[0].toUpperCase() + w.slice(1).toLowerCase()
    )
    .join(" ");
}

function resolveStatus(raw: string) {
  return (
    STATUS_CONFIG[raw as MemberStatus] ?? {
      label: _humanise(raw),
      dotColor: "#9CA3AF",
      badgeClasses: "bg-gray-100 text-gray-600",
    }
  );
}

function formatEnrollmentDate(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  } catch {
    return iso;
  }
}

// ─── Skeleton layouts ─────────────────────────────────────────────────────────

function KpiRowSkeleton() {
  return (
    <div className="grid grid-cols-4 gap-4">
      {[1, 2, 3, 4].map((i) => (
        <div
          key={i}
          className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm space-y-2"
        >
          <Skeleton className="h-2.5 w-20" />
          <Skeleton className="h-8 w-16" />
          <Skeleton className="h-2.5 w-24" />
        </div>
      ))}
    </div>
  );
}

function TableSkeleton() {
  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
      <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
        <Skeleton className="h-4 w-32" />
        <Skeleton className="h-3 w-28" />
      </div>
      <div className="px-5 py-3 border-b border-gray-100 flex gap-2.5">
        <Skeleton className="h-8 flex-1 max-w-xs rounded-lg" />
        <Skeleton className="h-8 w-32 rounded-lg" />
      </div>
      {Array.from({ length: 6 }).map((_, i) => (
        <div
          key={i}
          className="grid grid-cols-4 gap-4 px-5 py-3.5 border-b border-gray-50 items-center"
        >
          <div className="space-y-1.5">
            <Skeleton className="h-3.5 w-28" />
            <Skeleton className="h-2.5 w-36" />
          </div>
          <Skeleton className="h-5 w-20 rounded-full" />
          <Skeleton className="h-3 w-20" />
          <Skeleton className="h-3 w-20" />
        </div>
      ))}
    </div>
  );
}

// ─── Table Row ────────────────────────────────────────────────────────────────

function MemberTableRow({ member }: { member: MemberRow }) {
  const router = useRouter();
  const status = resolveStatus(member.status);

  function openDetail() {
    router.push(`/members/${member.id}`);
  }

  return (
    <tr
      onClick={openDetail}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          openDetail();
        }
      }}
      role="link"
      tabIndex={0}
      aria-label={`Open member ${member.name ?? "unnamed"}`}
      className="border-b border-gray-50 hover:bg-orange-50/40 focus:bg-orange-50/40 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-orange-300 cursor-pointer transition-colors"
    >
      {/* Name + Email */}
      <td className="px-5 py-3.5">
        <div className="flex flex-col">
          <span className="text-sm font-semibold text-gray-900">
            {member.name ?? "—"}
          </span>
          <span className="text-xs text-gray-400">{member.email ?? "—"}</span>
        </div>
      </td>

      {/* Status */}
      <td className="px-5 py-3.5">
        <span
          className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[11px] font-semibold ${status.badgeClasses}`}
        >
          <span
            className="w-1.5 h-1.5 rounded-full flex-shrink-0"
            style={{ backgroundColor: status.dotColor }}
          />
          {status.label}
        </span>
      </td>

      {/* Coach */}
      <td className="px-5 py-3.5">
        <span className="text-xs text-gray-500">
          {member.coach_id ?? "—"}
        </span>
      </td>

      {/* Enrolled */}
      <td className="px-5 py-3.5">
        <span className="text-xs text-gray-500">
          {formatEnrollmentDate(member.enrollmentDate)}
        </span>
      </td>
    </tr>
  );
}

// ─── Filter Bar ───────────────────────────────────────────────────────────────

function MembersFilterBar({
  search,
  onSearchChange,
  statusFilter,
  onStatusChange,
  onClear,
}: {
  search: string;
  onSearchChange: (v: string) => void;
  statusFilter: FilterStatus;
  onStatusChange: (v: FilterStatus) => void;
  onClear: () => void;
}) {
  const hasFilters = search !== "" || statusFilter !== "all";

  return (
    <div className="flex items-center gap-2.5 flex-wrap">
      {/* Search */}
      <div className="relative flex-1 min-w-[180px] max-w-xs">
        <svg
          className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-400"
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 20 20"
          fill="currentColor"
          aria-hidden="true"
        >
          <path
            fillRule="evenodd"
            d="M9 3.5a5.5 5.5 0 100 11 5.5 5.5 0 000-11zM2 9a7 7 0 1112.452 4.391l3.328 3.329a.75.75 0 11-1.06 1.06l-3.329-3.328A7 7 0 012 9z"
            clipRule="evenodd"
          />
        </svg>
        <input
          type="text"
          placeholder="Search members..."
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
          className="w-full pl-8 pr-3 py-1.5 text-sm border border-gray-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-orange-500/20 focus:border-orange-400 transition-all"
        />
      </div>

      {/* Status */}
      <select
        value={statusFilter}
        onChange={(e) => onStatusChange(e.target.value as FilterStatus)}
        className="px-2.5 py-1.5 text-sm border border-gray-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-orange-500/20 focus:border-orange-400 text-gray-600"
      >
        <option value="all">All Statuses</option>
        {(Object.keys(STATUS_CONFIG) as MemberStatus[]).map((key) => (
          <option key={key} value={key}>
            {STATUS_CONFIG[key].label}
          </option>
        ))}
      </select>

      {/* Clear */}
      {hasFilters && (
        <button
          type="button"
          onClick={onClear}
          className="px-2.5 py-1.5 text-sm text-gray-500 hover:text-gray-700 border border-gray-200 rounded-lg bg-white hover:bg-gray-50 transition-colors"
        >
          Clear filters
        </button>
      )}
    </div>
  );
}

// ─── Add Member modal ───────────────────────────────────────────────────────

function AddMemberModal({
  open,
  onClose,
  onCreated,
}: {
  open: boolean;
  onClose: () => void;
  onCreated: () => void;
}) {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [status, setStatus] = useState<MemberStatus>("active");
  const [coachId, setCoachId] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (open) {
      setName("");
      setEmail("");
      setStatus("active");
      setCoachId("");
      setSaving(false);
    }
  }, [open]);

  if (!open) return null;

  async function submit() {
    if (name.trim() === "") {
      showApiError("Name is required");
      return;
    }
    setSaving(true);
    try {
      await apiClient.post("/members", {
        name: name.trim(),
        email: email.trim() || null,
        status,
        coach_id: coachId.trim() || null,
      });
      showSuccess("Member added");
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
      aria-label="Add member"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-xl shadow-xl w-full max-w-md p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="text-base font-bold text-gray-900">Add Member</h2>
        <p className="text-xs text-gray-500 mt-0.5">
          Enroll a new member into the Fulfillment department.
        </p>

        <div className="mt-4 space-y-3">
          <label className="block">
            <span className="text-[11px] font-bold uppercase tracking-widest text-gray-400">Name *</span>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              autoFocus
              className="mt-1 w-full text-sm border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-orange-300"
            />
          </label>
          <label className="block">
            <span className="text-[11px] font-bold uppercase tracking-widest text-gray-400">Email</span>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="mt-1 w-full text-sm border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-orange-300"
            />
          </label>
          <div className="grid grid-cols-2 gap-3">
            <label className="block">
              <span className="text-[11px] font-bold uppercase tracking-widest text-gray-400">Status</span>
              <select
                value={status}
                onChange={(e) => setStatus(e.target.value as MemberStatus)}
                className="mt-1 w-full text-sm border border-gray-300 rounded-md px-2 py-2 focus:outline-none focus:ring-2 focus:ring-orange-300"
              >
                {(Object.keys(STATUS_CONFIG) as MemberStatus[]).map((k) => (
                  <option key={k} value={k}>
                    {STATUS_CONFIG[k].label}
                  </option>
                ))}
              </select>
            </label>
            <label className="block">
              <span className="text-[11px] font-bold uppercase tracking-widest text-gray-400">Coach ID</span>
              <input
                type="text"
                value={coachId}
                onChange={(e) => setCoachId(e.target.value)}
                placeholder="optional"
                className="mt-1 w-full text-sm border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-orange-300"
              />
            </label>
          </div>
        </div>

        <div className="mt-6 flex justify-end gap-2">
          <Button variant="ghost" size="sm" onClick={onClose} disabled={saving}>
            Cancel
          </Button>
          <Button variant="primary" size="sm" onClick={() => void submit()} disabled={saving || name.trim() === ""}>
            {saving ? "Adding…" : "Add Member"}
          </Button>
        </div>
      </div>
    </div>
  );
}

// ─── Page ────────────────────────────────────────────────────────────────────

export default function MembersPage() {
  const { isLoading: authLoading } = useAuth();
  const [isLoading, setIsLoading] = useState(true);
  const [kpis, setKpis] = useState<MembersKpis>(EMPTY_KPIS);
  const [listData, setListData] = useState<MembersListResponse>(EMPTY_LIST);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<FilterStatus>("all");
  const [showAddModal, setShowAddModal] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);

  // Fetch stats once on mount (after auth hydrates)
  useEffect(() => {
    if (authLoading) return;

    let cancelled = false;

    async function fetchStats(): Promise<void> {
      try {
        const data = await apiClient.get<MembersStatsResponse>(
          "/members/stats",
          { silent: true }
        );
        if (!cancelled) {
          setKpis(data.kpis ?? EMPTY_KPIS);
        }
      } catch {
        // On error, kpis stays as EMPTY_KPIS so the page renders with zeros.
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    }

    void fetchStats();

    return () => {
      cancelled = true;
    };
  }, [authLoading, refreshKey]);

  // Fetch list whenever filters change, with debounce on search
  const searchDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (authLoading) return;

    if (searchDebounceRef.current !== null) {
      clearTimeout(searchDebounceRef.current);
    }

    const doFetch = () => {
      let cancelled = false;

      async function fetchMembers(): Promise<void> {
        const params = new URLSearchParams();
        if (statusFilter !== "all") params.set("status", statusFilter);
        if (search) params.set("search", search);
        params.set("page", "1");
        params.set("per_page", "50");
        params.set("sort_by", "enrollment_date");
        params.set("sort_dir", "desc");

        try {
          const data = await apiClient.get<MembersListResponse>(
            `/members?${params.toString()}`,
            { silent: true }
          );
          if (!cancelled) {
            setListData(data);
          }
        } catch {
          // On error, listData stays as previous value.
        }
      }

      void fetchMembers();

      return () => {
        cancelled = true;
      };
    };

    // Debounce search input; fire immediately for dropdown changes
    if (search !== "") {
      searchDebounceRef.current = setTimeout(doFetch, 300);
      return () => {
        if (searchDebounceRef.current !== null) {
          clearTimeout(searchDebounceRef.current);
        }
      };
    }

    return doFetch();
  }, [authLoading, statusFilter, search, refreshKey]);

  function handleClearFilters() {
    setSearch("");
    setStatusFilter("all");
  }

  const kpiCards = [
    {
      label: "Total Members",
      value: String(kpis.total_members),
      sub: "All time",
    },
    {
      label: "Enrolled This Week",
      value: String(kpis.members_this_week),
      sub: "Last 7 days",
    },
    {
      label: "Active Members",
      value: String(kpis.active_members),
      sub: "Currently active",
    },
    {
      label: "Goals Completed",
      value: String(kpis.goals_completed),
      sub: "Total completed",
    },
  ];

  return (
    <>
      <Header title="Members" />

      <main className="flex-1 overflow-y-auto p-7 space-y-6">
        {/* Page heading */}
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-xl font-bold text-gray-900">Members</h1>
            <p className="text-sm text-gray-500 mt-0.5">
              View and manage all enrolled members in the Fulfillment department.
            </p>
          </div>
          <Button variant="primary" size="sm" onClick={() => setShowAddModal(true)}>
            + Add Member
          </Button>
        </div>

        {/* KPI Row */}
        {isLoading ? (
          <KpiRowSkeleton />
        ) : (
          <div className="grid grid-cols-4 gap-4">
            {kpiCards.map((kpi) => (
              <KpiCard
                key={kpi.label}
                label={kpi.label}
                value={kpi.value}
                borderColor={ORANGE}
                sub={kpi.sub}
              />
            ))}
          </div>
        )}

        {/* Members Table */}
        {isLoading ? (
          <TableSkeleton />
        ) : (
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
            {/* Table header */}
            <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
              <h2 className="text-sm font-bold text-gray-900">Member Records</h2>
              <span className="text-xs text-gray-400">
                Showing {listData.members.length} of{" "}
                {listData.total.toLocaleString()}
              </span>
            </div>

            {/* Filter bar */}
            <div className="px-5 py-3 border-b border-gray-100 bg-gray-50/50">
              <MembersFilterBar
                search={search}
                onSearchChange={setSearch}
                statusFilter={statusFilter}
                onStatusChange={setStatusFilter}
                onClear={handleClearFilters}
              />
            </div>

            {/* Table */}
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-100 bg-gray-50">
                  <th className="px-5 py-2.5 text-left text-[10px] font-bold uppercase tracking-widest text-gray-400">
                    Name
                  </th>
                  <th className="px-5 py-2.5 text-left text-[10px] font-bold uppercase tracking-widest text-gray-400">
                    Status
                  </th>
                  <th className="px-5 py-2.5 text-left text-[10px] font-bold uppercase tracking-widest text-gray-400">
                    Coach
                  </th>
                  <th className="px-5 py-2.5 text-left text-[10px] font-bold uppercase tracking-widest text-gray-400">
                    Enrolled
                  </th>
                </tr>
              </thead>
              <tbody>
                {listData.members.length === 0 ? (
                  <tr>
                    <td
                      colSpan={4}
                      className="px-5 py-12 text-center text-sm text-gray-400"
                    >
                      No members match your filters.
                    </td>
                  </tr>
                ) : (
                  listData.members.map((member) => (
                    <MemberTableRow key={member.id} member={member} />
                  ))
                )}
              </tbody>
            </table>

            {/* Table footer */}
            <div className="flex items-center justify-between px-5 py-3 border-t border-gray-100 bg-gray-50/50">
              <span className="text-xs text-gray-400">
                Showing {listData.members.length} of{" "}
                {listData.total.toLocaleString()} members
              </span>
            </div>
          </div>
        )}
      </main>

      <AddMemberModal
        open={showAddModal}
        onClose={() => setShowAddModal(false)}
        onCreated={() => setRefreshKey((k) => k + 1)}
      />
    </>
  );
}
