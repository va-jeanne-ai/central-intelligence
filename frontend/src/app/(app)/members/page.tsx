"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Header } from "@/components/layout/header";
import { KpiCard } from "@/components/ui/kpi-card";
import { Card, CardHeader, CardBody } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { apiClient } from "@/lib/api-client";
import { useAuth } from "@/hooks/use-auth";
import {
  Avatar,
  CallHistorySection,
  PerformanceSection,
  SubmissionsSection,
  formatDate,
  humanizeRole,
  statusStyle,
  type TeamMemberRow,
  type TeamMemberDetail,
} from "@/components/members/team-member";

// ─── Page-only type ─────────────────────────────────────────────────────────────

interface TeamStats {
  total_members: number;
  active_members: number;
  at_risk_members: number;
  calls_this_month: number;
  active_delta: number;
}

// ─── Directory card ─────────────────────────────────────────────────────────────

function MemberCard({
  member,
  selected,
  onSelect,
}: {
  member: TeamMemberRow;
  selected: boolean;
  onSelect: () => void;
}) {
  const st = statusStyle(member.status);
  return (
    <button
      type="button"
      onClick={onSelect}
      className={`flex flex-col items-center gap-2 rounded-xl border bg-white p-4 text-center transition-all hover:shadow-md ${
        selected ? "border-accent-400 ring-1 ring-accent-300" : `border-gray-200 ${st.ring}`
      }`}
    >
      <Avatar name={member.name} />
      <div className="min-w-0">
        <div className="text-sm font-bold text-gray-900 truncate">{member.name}</div>
        <div className="text-[11px] text-gray-400">Joined {formatDate(member.hired_at)}</div>
      </div>
      <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-semibold ${st.pill}`}>
        {st.atRisk && member.status.toLowerCase() === "probation" ? "At Risk" : humanizeRole(member.status)}
      </span>
    </button>
  );
}

// ─── Selected-member detail panel ────────────────────────────────────────────────

function DetailPanel({ repId }: { repId: string }) {
  const [detail, setDetail] = useState<TeamMemberDetail | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    void (async () => {
      try {
        const d = await apiClient.get<TeamMemberDetail>(`/members/team/${repId}`, { silent: true });
        if (!cancelled) setDetail(d);
      } catch {
        if (!cancelled) setDetail(null);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [repId]);

  if (loading) return <Card><CardBody><p className="text-sm text-gray-400">Loading…</p></CardBody></Card>;
  if (!detail) return null;

  const st = statusStyle(detail.status);

  return (
    <div className="space-y-4">
      {/* Header card */}
      <Card>
        <CardBody>
          <div className="flex items-start gap-3">
            <Avatar name={detail.name} size="lg" />
            <div className="min-w-0">
              <h2 className="text-base font-bold text-gray-900">{detail.name}</h2>
              <p className="text-[12px] text-gray-500">
                {humanizeRole(detail.role)}
                {detail.hired_at && ` · since ${formatDate(detail.hired_at)}`}
                {detail.days_active != null && ` · ${detail.days_active} days active`}
              </p>
              <span className={`mt-1.5 inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-semibold ${st.pill}`}>
                {humanizeRole(detail.status)}
              </span>
            </div>
          </div>

          {/* View full detail → dedicated page */}
          <Link
            href={`/members/${detail.rep_id}`}
            className="mt-3 inline-block text-[12px] font-semibold text-accent-600 hover:text-accent-700"
          >
            View full detail →
          </Link>

          {/* Performance bars (was "Goals Progress") */}
          <div className="mt-4 pt-4 border-t border-gray-100">
            <div className="text-[11px] font-bold uppercase tracking-wider text-gray-400 mb-3">Performance</div>
            <PerformanceSection performance={detail.performance} />
          </div>
        </CardBody>
      </Card>

      {/* Recent submissions (EOD reports) */}
      <Card>
        <CardHeader title="Recent Submissions" />
        <CardBody className="pt-0">
          <SubmissionsSection submissions={detail.recent_submissions} />
        </CardBody>
      </Card>

      {/* Call history */}
      <Card>
        <CardHeader title="Call History" />
        <CardBody className="pt-0">
          <CallHistorySection calls={detail.call_history} />
        </CardBody>
      </Card>
    </div>
  );
}

// ─── Page ───────────────────────────────────────────────────────────────────────

const STATUS_OPTIONS = ["all", "active", "probation", "terminated"];

export default function MembersPage() {
  const { isLoading: authLoading } = useAuth();
  const [stats, setStats] = useState<TeamStats | null>(null);
  const [members, setMembers] = useState<TeamMemberRow[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const [search, setSearch] = useState("");
  const [debounced, setDebounced] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");

  useEffect(() => {
    const t = setTimeout(() => setDebounced(search.trim()), 300);
    return () => clearTimeout(t);
  }, [search]);

  const loadStats = useCallback(async () => {
    try {
      const s = await apiClient.get<TeamStats>("/members/team-stats", { silent: true });
      setStats(s);
    } catch {
      /* zeros */
    }
  }, []);

  const loadMembers = useCallback(async () => {
    try {
      const params = new URLSearchParams();
      if (debounced) params.set("search", debounced);
      if (statusFilter !== "all") params.set("status", statusFilter);
      const data = await apiClient.get<{ members: TeamMemberRow[]; total: number }>(
        `/members/team?${params.toString()}`,
        { silent: true },
      );
      setMembers(data.members);
      // Keep selection valid; default to the first member.
      setSelected((prev) =>
        prev && data.members.some((m) => m.rep_id === prev)
          ? prev
          : data.members[0]?.rep_id ?? null,
      );
    } catch {
      setMembers([]);
    } finally {
      setIsLoading(false);
    }
  }, [debounced, statusFilter]);

  useEffect(() => {
    if (authLoading) return;
    void loadStats();
  }, [authLoading, loadStats]);

  useEffect(() => {
    if (authLoading) return;
    void loadMembers();
  }, [authLoading, loadMembers]);

  const activeCount = useMemo(() => members.length, [members]);

  return (
    <>
      <Header title="Members" />

      <main className="flex-1 overflow-y-auto p-7 space-y-6">
        {/* Heading + search + status + add */}
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h1 className="text-xl font-bold text-gray-900">Members</h1>
          <div className="flex items-center gap-3">
            <div className="relative">
              <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 text-sm">🔍</span>
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search members…"
                className="w-56 rounded-lg border border-gray-200 bg-white pl-9 pr-3 py-2 text-sm focus:border-accent-400 focus:outline-none focus:ring-1 focus:ring-accent-400"
              />
            </div>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-600 focus:border-accent-400 focus:outline-none focus:ring-1 focus:ring-accent-400"
            >
              {STATUS_OPTIONS.map((s) => (
                <option key={s} value={s}>
                  {s === "all" ? "All Status" : humanizeRole(s)}
                </option>
              ))}
            </select>
            <Button variant="primary" href="/fulfillment-director">
              + Ask Director
            </Button>
          </div>
        </div>

        {/* KPI cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <KpiCard
            label="Active Members"
            value={isLoading ? "—" : String(stats?.active_members ?? 0)}
            borderColor="#F97316"
            badge={stats && stats.active_delta !== 0 ? `↑ ${Math.abs(stats.active_delta)} this month` : undefined}
            badgeVariant={stats && stats.active_delta >= 0 ? "up" : "down"}
          />
          <KpiCard
            label="Total Members"
            value={isLoading ? "—" : String(stats?.total_members ?? 0)}
            borderColor="#10B981"
            sub="On the team"
          />
          <KpiCard
            label="Calls This Month"
            value={isLoading ? "—" : String(stats?.calls_this_month ?? 0)}
            borderColor="#3B82F6"
            sub="Across the team"
          />
          <KpiCard
            label="At-Risk Members"
            value={isLoading ? "—" : String(stats?.at_risk_members ?? 0)}
            borderColor="#EF4444"
            sub="Needs attention"
          />
        </div>

        {/* Directory + detail */}
        <div className="grid grid-cols-1 lg:grid-cols-[1fr_360px] gap-6">
          <Card>
            <CardHeader
              title="Member Directory"
              action={<span className="text-xs text-gray-400">{activeCount} shown</span>}
            />
            <CardBody>
              {isLoading ? (
                <p className="text-sm text-gray-400">Loading members…</p>
              ) : members.length === 0 ? (
                <p className="text-sm text-gray-400 italic">No members match.</p>
              ) : (
                <div className="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-4 gap-3">
                  {members.map((m) => (
                    <MemberCard
                      key={m.rep_id}
                      member={m}
                      selected={selected === m.rep_id}
                      onSelect={() => setSelected(m.rep_id)}
                    />
                  ))}
                </div>
              )}
            </CardBody>
          </Card>

          {selected ? (
            <DetailPanel repId={selected} />
          ) : (
            <Card><CardBody><p className="text-sm text-gray-400">Select a member to see details.</p></CardBody></Card>
          )}
        </div>
      </main>
    </>
  );
}
