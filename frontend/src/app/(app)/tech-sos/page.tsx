"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";
import { Header } from "@/components/layout/header";
import { Skeleton } from "@/components/ui/skeleton";
import { KpiCard } from "@/components/ui/kpi-card";
import { Card, CardHeader, CardBody } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { TicketModal } from "@/components/tech-sos/ticket-modal";
import type { TicketModalTicket } from "@/components/tech-sos/ticket-modal";
import { apiClient } from "@/lib/api-client";
import { useAuth } from "@/hooks/use-auth";
import { usePagination } from "@/hooks/use-pagination";
import { Pagination } from "@/components/ui";
import { showSuccess, showApiError } from "@/lib/toast";

// ─── Types ───────────────────────────────────────────────────────────────────

interface TicketRow {
  id: string;
  member_id: string | null;
  member_name: string | null;
  contact_name: string | null;
  contact_email: string | null;
  subject: string | null;
  category: string | null;
  status: string | null;
  priority: string | null;
  source: string | null;
  createdAt: string | null;
  resolvedAt: string | null;
}

interface TicketsListResponse {
  tickets: TicketRow[];
  total: number;
  page: number;
  per_page: number;
}

interface TicketsKpis {
  total: number;
  open: number;
  in_progress: number;
  resolved: number;
  avg_resolution_hours: number;
}

interface TicketsStatsResponse {
  kpis: TicketsKpis;
  category_breakdown: { category: string; count: number; percentage: number }[];
  status_breakdown: { status: string; count: number; percentage: number }[];
  ticket_volume: { label: string; value: number }[];
}

const ORANGE = "#F97316";
const EMPTY_KPIS: TicketsKpis = { total: 0, open: 0, in_progress: 0, resolved: 0, avg_resolution_hours: 0 };
const EMPTY_STATS: TicketsStatsResponse = {
  kpis: EMPTY_KPIS,
  category_breakdown: [],
  status_breakdown: [],
  ticket_volume: [],
};
const EMPTY_LIST: TicketsListResponse = { tickets: [], total: 0, page: 1, per_page: 50 };

type FilterStatus = "all" | "open" | "in_progress" | "resolved" | "closed";

const STATUS_BADGE: Record<string, string> = {
  open: "bg-blue-50 text-blue-700",
  in_progress: "bg-amber-50 text-amber-700",
  resolved: "bg-green-50 text-green-700",
  closed: "bg-gray-100 text-gray-500",
};

const PRIORITY_BADGE: Record<string, string> = {
  high: "bg-red-50 text-red-600",
  normal: "bg-gray-100 text-gray-600",
  low: "bg-gray-50 text-gray-400",
};

function humanise(v: string | null): string {
  if (!v) return "—";
  return v.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

// ─── Pattern bars (category breakdown) ────────────────────────────────────────

function PatternBars({
  title,
  rows,
}: {
  title: string;
  rows: { label: string; count: number; percentage: number }[];
}) {
  return (
    <Card>
      <CardHeader title={title} noBorder />
      <CardBody className="pt-0 space-y-2.5">
        {rows.length === 0 ? (
          <p className="text-[11px] text-gray-400">No data yet.</p>
        ) : (
          rows.map((r) => (
            <div key={r.label}>
              <div className="flex items-center justify-between text-[11px] text-gray-500 mb-1">
                <span>{humanise(r.label)}</span>
                <span>
                  {r.count} · {r.percentage}%
                </span>
              </div>
              <div className="h-2 rounded-full bg-gray-100 overflow-hidden">
                <div
                  className="h-full rounded-full"
                  style={{ width: `${Math.max(r.percentage, 2)}%`, backgroundColor: ORANGE }}
                />
              </div>
            </div>
          ))
        )}
      </CardBody>
    </Card>
  );
}

// ─── Page ────────────────────────────────────────────────────────────────────

export default function TechSosPage() {
  const { isLoading: authLoading } = useAuth();
  const router = useRouter();
  const [isLoading, setIsLoading] = useState(true);
  const [stats, setStats] = useState<TicketsStatsResponse>(EMPTY_STATS);
  const [listData, setListData] = useState<TicketsListResponse>(EMPTY_LIST);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<FilterStatus>("all");
  const [categoryFilter, setCategoryFilter] = useState("all");
  const [refreshKey, setRefreshKey] = useState(0);

  const { page, pageSize, setPage, setPageSize, resetToFirstPage } =
    usePagination("tech-sos");

  const [showAdd, setShowAdd] = useState(false);
  const [editTicket, setEditTicket] = useState<TicketModalTicket | null>(null);
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);

  const refresh = useCallback(() => setRefreshKey((k) => k + 1), []);

  // Stats
  useEffect(() => {
    if (authLoading) return;
    let cancelled = false;
    async function run() {
      try {
        const data = await apiClient.get<TicketsStatsResponse>("/tech-sos/stats", { silent: true });
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
        if (categoryFilter !== "all") params.set("category", categoryFilter);
        if (search) params.set("search", search);
        params.set("page", String(page));
        params.set("per_page", String(pageSize));
        try {
          const data = await apiClient.get<TicketsListResponse>(`/tech-sos?${params.toString()}`, { silent: true });
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
  }, [authLoading, statusFilter, categoryFilter, search, refreshKey, page, pageSize]);

  // When a filter/search narrows the set, jump back to page 1 so the user
  // isn't stranded on a page that no longer exists.
  useEffect(() => {
    resetToFirstPage();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statusFilter, categoryFilter, search]);

  async function confirmDelete() {
    if (!deleteId) return;
    setDeleting(true);
    try {
      await apiClient.delete(`/tech-sos/${deleteId}`);
      showSuccess("Ticket deleted");
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
    { label: "Open", value: String(k.open), sub: "Awaiting action" },
    { label: "In Progress", value: String(k.in_progress), sub: "Being worked" },
    { label: "Resolved", value: String(k.resolved), sub: "Resolved + closed" },
    { label: "Avg Resolution", value: `${k.avg_resolution_hours}h`, sub: "Mean time to resolve" },
  ];

  return (
    <>
      <Header title="Tech SOS" />

      <main className="flex-1 overflow-y-auto p-7 space-y-6">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-xl font-bold text-gray-900">Tech SOS</h1>
            <p className="text-sm text-gray-500 mt-0.5">Member tech-support tickets — track, categorize, and resolve.</p>
          </div>
          <Button variant="primary" size="sm" onClick={() => setShowAdd(true)}>
            + New Ticket
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

        {/* Patterns + table */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="lg:col-span-1 space-y-4">
            <PatternBars
              title="Issue Categories"
              rows={stats.category_breakdown.map((c) => ({ label: c.category, count: c.count, percentage: c.percentage }))}
            />
            <PatternBars
              title="By Status"
              rows={stats.status_breakdown.map((s) => ({ label: s.status, count: s.count, percentage: s.percentage }))}
            />
          </div>

          <div className="lg:col-span-2">
            <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
              <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
                <h2 className="text-sm font-bold text-gray-900">Tickets</h2>
                <span className="text-xs text-gray-400">{listData.total.toLocaleString()} total</span>
              </div>

              {/* Filter bar */}
              <div className="px-5 py-3 border-b border-gray-100 bg-gray-50/50 flex items-center gap-2.5 flex-wrap">
                <input
                  type="text"
                  placeholder="Search tickets..."
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
                  <option value="open">Open</option>
                  <option value="in_progress">In Progress</option>
                  <option value="resolved">Resolved</option>
                  <option value="closed">Closed</option>
                </select>
                <select
                  value={categoryFilter}
                  onChange={(e) => setCategoryFilter(e.target.value)}
                  className="px-2.5 py-1.5 text-sm border border-gray-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-orange-500/20 text-gray-600"
                >
                  <option value="all">All Categories</option>
                  {["login", "billing", "video", "portal", "access", "other"].map((c) => (
                    <option key={c} value={c}>{humanise(c)}</option>
                  ))}
                </select>
              </div>

              <table className="w-full">
                <thead>
                  <tr className="border-b border-gray-100 bg-gray-50">
                    {["Subject", "Member", "Category", "Status", ""].map((h, i) => (
                      <th key={i} className="px-4 py-2.5 text-left text-[10px] font-bold uppercase tracking-widest text-gray-400">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {listData.tickets.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="px-5 py-12 text-center text-sm text-gray-400">
                        No tickets match your filters.
                      </td>
                    </tr>
                  ) : (
                    listData.tickets.map((t) => (
                      <tr key={t.id} className="border-b border-gray-50 hover:bg-gray-50/60">
                        <td className="px-4 py-3">
                          <div className="flex flex-col">
                            <span className="text-sm text-gray-800 truncate max-w-[220px]">{t.subject ?? "—"}</span>
                            {t.priority && (
                              <span className={`mt-0.5 inline-flex w-fit items-center px-1.5 py-0.5 rounded-full text-[10px] font-semibold ${PRIORITY_BADGE[t.priority] ?? "bg-gray-100 text-gray-500"}`}>
                                {humanise(t.priority)}
                              </span>
                            )}
                          </div>
                        </td>
                        <td className="px-4 py-3 text-sm">
                          {t.member_id ? (
                            <button
                              type="button"
                              onClick={() => router.push(`/members/${t.member_id}`)}
                              className="text-gray-800 hover:text-orange-700"
                            >
                              {t.member_name ?? "—"}
                            </button>
                          ) : (
                            <span className="text-gray-400">{t.contact_name ?? t.contact_email ?? "—"}</span>
                          )}
                        </td>
                        <td className="px-4 py-3 text-xs text-gray-500">{humanise(t.category)}</td>
                        <td className="px-4 py-3">
                          <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold ${STATUS_BADGE[(t.status ?? "").toLowerCase()] ?? "bg-gray-100 text-gray-600"}`}>
                            {humanise(t.status)}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-right whitespace-nowrap">
                          <button
                            type="button"
                            onClick={() =>
                              setEditTicket({
                                id: t.id,
                                subject: t.subject,
                                category: t.category,
                                status: t.status,
                                priority: t.priority,
                              })
                            }
                            className="text-[11px] font-medium text-orange-600 hover:text-orange-700 mr-2"
                          >
                            Manage
                          </button>
                          <button
                            type="button"
                            onClick={() => setDeleteId(t.id)}
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
          </div>
        </div>
      </main>

      <TicketModal open={showAdd} onClose={() => setShowAdd(false)} onSaved={refresh} />
      <TicketModal open={editTicket !== null} ticket={editTicket} onClose={() => setEditTicket(null)} onSaved={refresh} />
      <ConfirmDialog
        open={deleteId !== null}
        onClose={() => setDeleteId(null)}
        onConfirm={() => void confirmDelete()}
        title="Delete ticket?"
        description="This removes the support ticket."
        confirmLabel="Delete"
        variant="danger"
        loading={deleting}
      />
    </>
  );
}
