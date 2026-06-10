"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";
import { Header } from "@/components/layout/header";
import { Skeleton } from "@/components/ui/skeleton";
import { KpiCard } from "@/components/ui/kpi-card";
import { Card, CardHeader, CardBody } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { GoalModal } from "@/components/goals/goal-modal";
import type { GoalModalGoal } from "@/components/goals/goal-modal";
import { apiClient } from "@/lib/api-client";
import { useAuth } from "@/hooks/use-auth";
import { showSuccess, showApiError } from "@/lib/toast";

// ─── Types ───────────────────────────────────────────────────────────────────

interface GoalRow {
  id: string;
  member_id: string | null;
  member_name: string | null;
  goal_text: string | null;
  status: string | null;
  targetDate: string | null;
  created_at: string | null;
  overdue: boolean;
}

interface GoalsListResponse {
  goals: GoalRow[];
  total: number;
  page: number;
  per_page: number;
}

interface GoalsKpis {
  total: number;
  in_progress: number;
  completed: number;
  overdue: number;
}

interface GoalsStatsResponse {
  kpis: GoalsKpis;
  goal_funnel: { stage: string; count: number; percentage: number }[];
  status_breakdown: { status: string; count: number; percentage: number }[];
}

// ─── Constants ────────────────────────────────────────────────────────────────

const ORANGE = "#F97316";

const EMPTY_KPIS: GoalsKpis = { total: 0, in_progress: 0, completed: 0, overdue: 0 };
const EMPTY_STATS: GoalsStatsResponse = { kpis: EMPTY_KPIS, goal_funnel: [], status_breakdown: [] };
const EMPTY_LIST: GoalsListResponse = { goals: [], total: 0, page: 1, per_page: 50 };

type FilterStatus = "all" | "active" | "completed" | "abandoned";

const STATUS_BADGE: Record<string, string> = {
  active: "bg-blue-50 text-blue-700",
  completed: "bg-green-50 text-green-700",
  abandoned: "bg-gray-100 text-gray-500",
};

function statusBadge(status: string | null): string {
  return STATUS_BADGE[(status ?? "").toLowerCase()] ?? "bg-gray-100 text-gray-600";
}

function fmtDate(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
  } catch {
    return iso;
  }
}

// ─── Goal funnel mini-chart (horizontal bars) ────────────────────────────────

function GoalFunnel({ stages }: { stages: { stage: string; count: number; percentage: number }[] }) {
  if (stages.length === 0) return null;
  return (
    <Card>
      <CardHeader title="Goal Funnel" noBorder />
      <CardBody className="pt-0 space-y-2.5">
        {stages.map((s) => (
          <div key={s.stage}>
            <div className="flex items-center justify-between text-[11px] text-gray-500 mb-1">
              <span>{s.stage}</span>
              <span>
                {s.count} · {s.percentage}%
              </span>
            </div>
            <div className="h-2 rounded-full bg-gray-100 overflow-hidden">
              <div
                className="h-full rounded-full"
                style={{ width: `${Math.max(s.percentage, 2)}%`, backgroundColor: ORANGE }}
              />
            </div>
          </div>
        ))}
      </CardBody>
    </Card>
  );
}

// ─── Page ────────────────────────────────────────────────────────────────────

export default function AccountabilityPage() {
  const { isLoading: authLoading } = useAuth();
  const router = useRouter();
  const [isLoading, setIsLoading] = useState(true);
  const [stats, setStats] = useState<GoalsStatsResponse>(EMPTY_STATS);
  const [listData, setListData] = useState<GoalsListResponse>(EMPTY_LIST);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<FilterStatus>("all");
  const [overdueOnly, setOverdueOnly] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);

  const [showAdd, setShowAdd] = useState(false);
  const [editGoal, setEditGoal] = useState<GoalModalGoal | null>(null);
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);

  const refresh = useCallback(() => setRefreshKey((k) => k + 1), []);

  // Stats
  useEffect(() => {
    if (authLoading) return;
    let cancelled = false;
    async function run() {
      try {
        const data = await apiClient.get<GoalsStatsResponse>("/goals/stats", { silent: true });
        if (!cancelled) setStats(data);
      } catch {
        // keep empty
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    }
    void run();
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
      async function run() {
        const params = new URLSearchParams();
        if (statusFilter !== "all") params.set("status", statusFilter);
        if (overdueOnly) params.set("overdue", "true");
        if (search) params.set("search", search);
        params.set("page", "1");
        params.set("per_page", "100");
        try {
          const data = await apiClient.get<GoalsListResponse>(`/goals?${params.toString()}`, { silent: true });
          if (!cancelled) setListData(data);
        } catch {
          // keep previous
        }
      }
      void run();
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
  }, [authLoading, statusFilter, overdueOnly, search, refreshKey]);

  async function completeGoal(id: string) {
    try {
      await apiClient.patch(`/goals/${id}`, { status: "completed" });
      showSuccess("Goal completed");
      refresh();
    } catch (err) {
      showApiError(err as Error);
    }
  }

  async function confirmDelete() {
    if (!deleteId) return;
    setDeleting(true);
    try {
      await apiClient.delete(`/goals/${deleteId}`);
      showSuccess("Goal deleted");
      setDeleteId(null);
      refresh();
    } catch (err) {
      showApiError(err as Error);
    } finally {
      setDeleting(false);
    }
  }

  const k = stats.kpis;
  const kpiCards = [
    { label: "Total Goals", value: String(k.total), sub: "Member goals" },
    { label: "In Progress", value: String(k.in_progress), sub: "Active" },
    { label: "Completed", value: String(k.completed), sub: "Done" },
    { label: "Overdue", value: String(k.overdue), sub: "Past target" },
  ];

  return (
    <>
      <Header title="Accountability" />

      <main className="flex-1 overflow-y-auto p-7 space-y-6">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-xl font-bold text-gray-900">Accountability</h1>
            <p className="text-sm text-gray-500 mt-0.5">Track member goals, progress, and overdue commitments.</p>
          </div>
          <Button variant="primary" size="sm" onClick={() => setShowAdd(true)}>
            + Add Goal
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
              <KpiCard key={kpi.label} label={kpi.label} value={kpi.value} borderColor={ORANGE} sub={kpi.sub} />
            ))}
          </div>
        )}

        {/* Funnel + table */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="lg:col-span-1">
            <GoalFunnel stages={stats.goal_funnel} />
          </div>

          <div className="lg:col-span-2">
            <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
              <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
                <h2 className="text-sm font-bold text-gray-900">Goals</h2>
                <span className="text-xs text-gray-400">{listData.total.toLocaleString()} total</span>
              </div>

              {/* Filter bar */}
              <div className="px-5 py-3 border-b border-gray-100 bg-gray-50/50 flex items-center gap-2.5 flex-wrap">
                <input
                  type="text"
                  placeholder="Search goals..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  className="flex-1 min-w-[160px] max-w-xs px-3 py-1.5 text-sm border border-gray-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-orange-500/20 focus:border-orange-400"
                />
                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value as FilterStatus)}
                  className="px-2.5 py-1.5 text-sm border border-gray-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-orange-500/20 text-gray-600"
                >
                  <option value="all">All Statuses</option>
                  <option value="active">Active</option>
                  <option value="completed">Completed</option>
                  <option value="abandoned">Abandoned</option>
                </select>
                <label className="flex items-center gap-1.5 text-sm text-gray-600 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={overdueOnly}
                    onChange={(e) => setOverdueOnly(e.target.checked)}
                    className="accent-orange-500"
                  />
                  Overdue only
                </label>
              </div>

              <table className="w-full">
                <thead>
                  <tr className="border-b border-gray-100 bg-gray-50">
                    {["Member", "Goal", "Status", "Target", ""].map((h, i) => (
                      <th
                        key={i}
                        className="px-4 py-2.5 text-left text-[10px] font-bold uppercase tracking-widest text-gray-400"
                      >
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {listData.goals.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="px-5 py-12 text-center text-sm text-gray-400">
                        No goals match your filters.
                      </td>
                    </tr>
                  ) : (
                    listData.goals.map((g) => (
                      <tr key={g.id} className="border-b border-gray-50 hover:bg-gray-50/60">
                        <td className="px-4 py-3">
                          {g.member_id ? (
                            <button
                              type="button"
                              onClick={() => router.push(`/members/${g.member_id}`)}
                              className="text-sm text-gray-800 hover:text-orange-700 text-left"
                            >
                              {g.member_name ?? "—"}
                            </button>
                          ) : (
                            <span className="text-sm text-gray-400">—</span>
                          )}
                        </td>
                        <td className="px-4 py-3 text-sm text-gray-700 max-w-xs truncate">{g.goal_text ?? "—"}</td>
                        <td className="px-4 py-3">
                          <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold ${statusBadge(g.status)}`}>
                            {g.status ? g.status[0].toUpperCase() + g.status.slice(1) : "—"}
                          </span>
                          {g.overdue && (
                            <span className="ml-1.5 inline-flex items-center px-1.5 py-0.5 rounded-full text-[10px] font-semibold bg-red-50 text-red-600">
                              Overdue
                            </span>
                          )}
                        </td>
                        <td className="px-4 py-3 text-xs text-gray-500">{fmtDate(g.targetDate)}</td>
                        <td className="px-4 py-3 text-right whitespace-nowrap">
                          {g.status !== "completed" && (
                            <button
                              type="button"
                              onClick={() => void completeGoal(g.id)}
                              className="text-[11px] font-medium text-green-600 hover:text-green-700 mr-2"
                            >
                              Complete
                            </button>
                          )}
                          <button
                            type="button"
                            onClick={() =>
                              setEditGoal({
                                id: g.id,
                                goal_text: g.goal_text,
                                status: g.status,
                                targetDate: g.targetDate,
                              })
                            }
                            className="text-[11px] font-medium text-orange-600 hover:text-orange-700 mr-2"
                          >
                            Edit
                          </button>
                          <button
                            type="button"
                            onClick={() => setDeleteId(g.id)}
                            className="text-[11px] font-medium text-red-500 hover:text-red-600"
                          >
                            Delete
                          </button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </main>

      <GoalModal open={showAdd} onClose={() => setShowAdd(false)} onSaved={refresh} />
      <GoalModal
        open={editGoal !== null}
        goal={editGoal}
        onClose={() => setEditGoal(null)}
        onSaved={refresh}
      />
      <ConfirmDialog
        open={deleteId !== null}
        onClose={() => setDeleteId(null)}
        onConfirm={() => void confirmDelete()}
        title="Delete goal?"
        description="This removes the goal from accountability tracking."
        confirmLabel="Delete"
        variant="danger"
        loading={deleting}
      />
    </>
  );
}
