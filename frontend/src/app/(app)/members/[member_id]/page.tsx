"use client";

import { useCallback, useEffect, useState } from "react";
import { Header } from "@/components/layout/header";
import { Button } from "@/components/ui/button";
import { Breadcrumbs, ORIGINS } from "@/components/ui/breadcrumbs";
import { apiClient } from "@/lib/api-client";
import { useAuth } from "@/hooks/use-auth";
import { showSuccess, showError } from "@/lib/toast";
import {
  Avatar,
  Card,
  CardHeader,
  CardBody,
  CallHistorySection,
  PerformanceSection,
  SubmissionsSection,
  formatDate,
  humanizeRole,
  statusStyle,
  type TeamMemberDetail,
} from "@/components/members/team-member";

const STATUS_OPTIONS = ["active", "probation", "terminated"];

// The route param is `member_id` but the Members page is the team roster, so the
// id is a rep_id (e.g. REP_NELSON_FIGUERIA) served by /members/team/{rep_id}.
export default function MemberDetailPage({ params }: { params: { member_id: string } }) {
  const repId = params.member_id;
  const { isLoading: authLoading } = useAuth();
  const [detail, setDetail] = useState<TeamMemberDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(false);

  // Edit mode + the draft being edited. Edits write to CI overrides (rep_overrides),
  // so they survive the WGR sync; synced fields are the fallback when not overridden.
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [draft, setDraft] = useState({ full_name: "", email: "", role: "", status: "", notes: "" });

  const load = useCallback(async () => {
    try {
      const d = await apiClient.get<TeamMemberDetail>(`/members/team/${repId}`, { silent: true });
      setDetail(d);
    } catch {
      setError(true);
    } finally {
      setIsLoading(false);
    }
  }, [repId]);

  useEffect(() => {
    if (authLoading) return;
    void load();
  }, [authLoading, load]);

  function startEdit() {
    if (!detail) return;
    setDraft({
      full_name: detail.name ?? "",
      email: detail.email ?? "",
      role: detail.role ?? "",
      status: detail.status ?? "",
      notes: detail.notes ?? "",
    });
    setEditing(true);
  }

  const save = useCallback(async () => {
    setSaving(true);
    try {
      const updated = await apiClient.patch<TeamMemberDetail>(
        `/members/team/${repId}`,
        draft,
        { silent: true },
      );
      setDetail(updated);
      setEditing(false);
      showSuccess("Member updated.");
    } catch (err) {
      showError(err instanceof Error ? err.message : "Couldn't save.");
    } finally {
      setSaving(false);
    }
  }, [repId, draft]);

  return (
    <>
      <Header title="Member" />
      <main className="flex-1 overflow-y-auto p-7 space-y-6">
        <Breadcrumbs origin={ORIGINS.members} current={detail?.name ?? "Member"} />

        {isLoading ? (
          <p className="text-sm text-gray-400">Loading member…</p>
        ) : error || !detail ? (
          <p className="text-[15px] text-red-700">Member not found.</p>
        ) : (
          <>
            {/* Header card */}
            <Card>
              <CardBody>
                <div className="flex items-start gap-4">
                  <Avatar name={detail.name} size="xl" />
                  <div className="min-w-0 flex-1">
                    {editing ? (
                      <div className="space-y-2.5 max-w-md">
                        <Field label="Name">
                          <input
                            value={draft.full_name}
                            onChange={(e) => setDraft({ ...draft, full_name: e.target.value })}
                            className={inputCls}
                          />
                        </Field>
                        <Field label="Email">
                          <input
                            value={draft.email}
                            onChange={(e) => setDraft({ ...draft, email: e.target.value })}
                            className={inputCls}
                          />
                        </Field>
                        <div className="grid grid-cols-2 gap-2.5">
                          <Field label="Role">
                            <input
                              value={draft.role}
                              onChange={(e) => setDraft({ ...draft, role: e.target.value })}
                              className={inputCls}
                            />
                          </Field>
                          <Field label="Status">
                            <select
                              value={draft.status}
                              onChange={(e) => setDraft({ ...draft, status: e.target.value })}
                              className={inputCls}
                            >
                              {STATUS_OPTIONS.map((s) => (
                                <option key={s} value={s}>
                                  {humanizeRole(s)}
                                </option>
                              ))}
                            </select>
                          </Field>
                        </div>
                      </div>
                    ) : (
                      <>
                        <h1 className="text-[22px] font-bold text-gray-900">{detail.name}</h1>
                        <p className="text-sm text-gray-500 mt-0.5">
                          {humanizeRole(detail.role)}
                          {detail.hired_at && ` · since ${formatDate(detail.hired_at)}`}
                          {detail.days_active != null && ` · ${detail.days_active} days active`}
                        </p>
                        <div className="flex items-center gap-2 mt-2">
                          <span
                            className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-[12px] font-semibold ${statusStyle(detail.status).pill}`}
                          >
                            {humanizeRole(detail.status)}
                          </span>
                          {detail.email && <span className="text-[12px] text-gray-400">{detail.email}</span>}
                        </div>
                        {detail.capabilities.length > 0 && (
                          <div className="flex flex-wrap gap-1.5 mt-3">
                            {detail.capabilities.map((cap) => (
                              <span
                                key={cap}
                                className="inline-flex items-center rounded-full bg-gray-100 px-2 py-0.5 text-[11px] font-medium text-gray-600 capitalize"
                              >
                                {cap}
                              </span>
                            ))}
                          </div>
                        )}
                      </>
                    )}
                  </div>
                  <div className="flex flex-shrink-0 gap-2">
                    {editing ? (
                      <>
                        <Button variant="ghost" onClick={() => setEditing(false)} disabled={saving}>
                          Cancel
                        </Button>
                        <Button variant="primary" onClick={() => void save()} disabled={saving}>
                          {saving ? "Saving…" : "Save"}
                        </Button>
                      </>
                    ) : (
                      <Button variant="ghost" onClick={startEdit}>
                        ✎ Edit
                      </Button>
                    )}
                  </div>
                </div>
              </CardBody>
            </Card>

            {/* Notes (CI-owned, editable) */}
            <Card>
              <CardHeader title="Notes" />
              <CardBody className="pt-0">
                {editing ? (
                  <textarea
                    value={draft.notes}
                    onChange={(e) => setDraft({ ...draft, notes: e.target.value })}
                    rows={3}
                    placeholder="Add a note about this member…"
                    className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm focus:border-accent-400 focus:outline-none focus:ring-1 focus:ring-accent-400"
                  />
                ) : detail.notes ? (
                  <p className="text-[13px] text-gray-700 whitespace-pre-wrap leading-relaxed">{detail.notes}</p>
                ) : (
                  <p className="text-[13px] text-gray-400 italic">No notes. Click Edit to add one.</p>
                )}
              </CardBody>
            </Card>

            {/* Performance */}
            <Card>
              <CardHeader title="Performance" />
              <CardBody className="pt-0">
                <PerformanceSection performance={detail.performance} />
              </CardBody>
            </Card>

            {/* Recent submissions + call history */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <Card>
                <CardHeader title="Recent Submissions" />
                <CardBody className="pt-0">
                  <SubmissionsSection submissions={detail.recent_submissions} />
                </CardBody>
              </Card>
              <Card>
                <CardHeader title="Call History" />
                <CardBody className="pt-0">
                  <CallHistorySection calls={detail.call_history} />
                </CardBody>
              </Card>
            </div>
          </>
        )}
      </main>
    </>
  );
}

const inputCls =
  "w-full rounded-md border border-gray-200 px-2.5 py-1.5 text-sm focus:border-accent-400 focus:outline-none focus:ring-1 focus:ring-accent-400";

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="text-[11px] font-semibold uppercase tracking-wide text-gray-400">{label}</span>
      <div className="mt-0.5">{children}</div>
    </label>
  );
}
