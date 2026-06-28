"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Header } from "@/components/layout/header";
import { KpiCard } from "@/components/ui/kpi-card";
import { Card, CardHeader, CardBody } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { apiClient } from "@/lib/api-client";
import { useAuth } from "@/hooks/use-auth";

// ─── Types (bound to /members/team*, sourced from the sales team) ───────────────

interface TeamStats {
  total_members: number;
  active_members: number;
  at_risk_members: number;
  calls_this_month: number;
  active_delta: number;
}

interface TeamMemberRow {
  rep_id: string;
  name: string;
  email: string | null;
  role: string | null;
  status: string;
  hired_at: string | null;
  capabilities: string[];
  calls_count: number;
}

interface PerformanceBar {
  label: string;
  percent: number;
  detail: string | null;
}
interface SubmissionRow {
  label: string;
  date: string | null;
  delivered: boolean;
}
interface CallHistoryRow {
  call_id: string;
  call_type: string | null;
  call_result: string | null;
  date: string | null;
}
interface TeamMemberDetail {
  rep_id: string;
  name: string;
  email: string | null;
  role: string | null;
  status: string;
  hired_at: string | null;
  days_active: number | null;
  capabilities: string[];
  performance: PerformanceBar[];
  recent_submissions: SubmissionRow[];
  call_history: CallHistoryRow[];
}

// ─── Helpers ────────────────────────────────────────────────────────────────────

function initials(name: string): string {
  const p = name.trim().split(/\s+/);
  return ((p[0]?.[0] ?? "") + (p.length > 1 ? p[p.length - 1][0] : "")).toUpperCase() || "—";
}

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

function humanizeRole(role: string | null): string {
  if (!role) return "Team member";
  return role.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

// Status → pill + accent. "active" green, "probation" amber/at-risk, else gray/red.
function statusStyle(status: string): { pill: string; ring: string; atRisk: boolean } {
  const s = status.toLowerCase();
  if (s === "active") return { pill: "bg-emerald-50 text-emerald-700", ring: "", atRisk: false };
  if (s === "probation") return { pill: "bg-amber-50 text-amber-700", ring: "ring-1 ring-amber-300", atRisk: true };
  return { pill: "bg-red-50 text-red-700", ring: "ring-1 ring-red-300", atRisk: true }; // terminated, etc.
}

// Deterministic avatar color from the name (stable per person).
const AVATAR_COLORS = ["#F97316", "#3B82F6", "#10B981", "#8B5CF6", "#EC4899", "#14B8A6", "#EF4444", "#6366F1"];
function avatarColor(name: string): string {
  let h = 0;
  for (let i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) | 0;
  return AVATAR_COLORS[Math.abs(h) % AVATAR_COLORS.length];
}

function Avatar({ name, size = "md" }: { name: string; size?: "md" | "lg" }) {
  const dim = size === "lg" ? "h-14 w-14 text-lg" : "h-12 w-12 text-sm";
  return (
    <span
      className={`flex flex-shrink-0 items-center justify-center rounded-full font-bold text-white ${dim}`}
      style={{ backgroundColor: avatarColor(name) }}
    >
      {initials(name)}
    </span>
  );
}

// Performance bar color by label.
function barColor(label: string): string {
  const l = label.toLowerCase();
  if (l.includes("score")) return "#10B981";
  if (l.includes("calls")) return "#F59E0B";
  return "#3B82F6";
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

          {/* Performance bars (was "Goals Progress") */}
          <div className="mt-4 pt-4 border-t border-gray-100">
            <div className="text-[11px] font-bold uppercase tracking-wider text-gray-400 mb-3">Performance</div>
            {detail.performance.length === 0 ? (
              <p className="text-[13px] text-gray-400 italic">No performance data.</p>
            ) : (
              <div className="space-y-3">
                {detail.performance.map((bar) => (
                  <div key={bar.label}>
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-[13px] font-medium text-gray-700">{bar.label}</span>
                      <span className="text-[13px] font-bold text-gray-900">{Math.round(bar.percent)}%</span>
                    </div>
                    <div className="h-2 rounded-full bg-gray-100 overflow-hidden">
                      <div
                        className="h-full rounded-full transition-all duration-500"
                        style={{ width: `${bar.percent}%`, backgroundColor: barColor(bar.label) }}
                      />
                    </div>
                    {bar.detail && <div className="text-[11px] text-gray-400 mt-0.5">{bar.detail}</div>}
                  </div>
                ))}
              </div>
            )}
          </div>
        </CardBody>
      </Card>

      {/* Recent submissions (EOD reports) */}
      <Card>
        <CardHeader title="Recent Submissions" />
        <CardBody className="pt-0">
          {detail.recent_submissions.length === 0 ? (
            <p className="text-[13px] text-gray-400 italic">No reports yet.</p>
          ) : (
            <div className="space-y-1.5">
              {detail.recent_submissions.map((sub, i) => (
                <div key={i} className="flex items-center justify-between rounded-lg bg-gray-50 px-3 py-2 text-[13px]">
                  <span className="flex items-center gap-2 text-gray-700">
                    <span className={`h-2 w-2 rounded-full ${sub.delivered ? "bg-emerald-500" : "bg-gray-300"}`} />
                    {sub.label}
                  </span>
                  <span className="text-[12px] text-gray-400">{formatDate(sub.date)}</span>
                </div>
              ))}
            </div>
          )}
        </CardBody>
      </Card>

      {/* Call history */}
      <Card>
        <CardHeader title="Call History" />
        <CardBody className="pt-0">
          {detail.call_history.length === 0 ? (
            <p className="text-[13px] text-gray-400 italic">No calls yet.</p>
          ) : (
            <div className="space-y-1.5">
              {detail.call_history.map((call) => (
                <Link
                  key={call.call_id}
                  href={`/sales-calls/${call.call_id}`}
                  className="flex items-center justify-between rounded-lg bg-gray-50 px-3 py-2 text-[13px] hover:bg-gray-100 transition-colors"
                >
                  <span className="flex items-center gap-2 text-gray-700">
                    <span className="h-2 w-2 rounded-full bg-orange-500" />
                    {call.call_type || "Call"}
                    {call.call_result && <span className="text-gray-400">· {call.call_result}</span>}
                  </span>
                  <span className="text-[12px] text-gray-400">{formatDate(call.date)}</span>
                </Link>
              ))}
            </div>
          )}
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
