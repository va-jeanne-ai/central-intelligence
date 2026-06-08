"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { Header } from "@/components/layout/header";
import { Card, CardHeader, CardBody } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { apiClient } from "@/lib/api-client";
import { useAuth } from "@/hooks/use-auth";
import { showSuccess, showApiError } from "@/lib/toast";

// ─── Types ───────────────────────────────────────────────────────────────────

type MemberStatus = "active" | "paused" | "graduated" | "churned";

const STATUS_OPTIONS: MemberStatus[] = ["active", "paused", "graduated", "churned"];

interface CallSummary {
  id: string;
  date: string | null;
  call_type: string | null;
  insights_count: number;
  processed_date: string | null;
}
interface GoalSummary {
  id: string;
  goal_text: string | null;
  status: string | null;
  target_date: string | null;
}
interface WinSummary {
  id: string;
  win_text: string | null;
  impact_area: string | null;
  win_date: string | null;
}
interface PainPointSummary {
  id: string;
  text: string | null;
  category: string | null;
}
interface NoteRow {
  id: string;
  body: string;
  author_id: string | null;
  author_email: string | null;
  created_at: string;
}
interface MemberDetail {
  id: string;
  name: string | null;
  email: string | null;
  status: string | null;
  coach_id: string | null;
  enrollment_date: string | null;
  created_at: string | null;
  calls: CallSummary[];
  goals: GoalSummary[];
  wins: WinSummary[];
  pain_points: PainPointSummary[];
  staff_notes: NoteRow[];
}
interface HistoryEvent {
  id: string;
  action: string;
  before: Record<string, unknown> | null;
  after: Record<string, unknown> | null;
  author_id: string | null;
  author_email: string | null;
  created_at: string;
}

const ORANGE = "#F97316";

// ─── Helpers ──────────────────────────────────────────────────────────────────

function fmtDate(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" });
}

function humanise(value: string): string {
  return value
    .split(/[_\-.\s]+/)
    .filter(Boolean)
    .map((w) => (w.length <= 3 ? w.toUpperCase() : w[0].toUpperCase() + w.slice(1).toLowerCase()))
    .join(" ");
}

const STATUS_BADGE: Record<string, string> = {
  active: "bg-green-50 text-green-700",
  paused: "bg-amber-50 text-amber-700",
  graduated: "bg-indigo-50 text-indigo-700",
  churned: "bg-gray-100 text-gray-500",
};

function statusBadgeClasses(status: string | null): string {
  return STATUS_BADGE[(status ?? "").toLowerCase()] ?? "bg-gray-100 text-gray-600";
}

// ─── Inline-edit field ─────────────────────────────────────────────────────────

interface InlineFieldProps {
  label: string;
  value: string | null;
  onSave: (next: string) => Promise<void>;
  type?: "text" | "email" | "select";
  options?: string[];
  placeholder?: string;
}

function InlineField({ label, value, onSave, type = "text", options, placeholder }: InlineFieldProps) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value ?? "");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setDraft(value ?? "");
  }, [value]);

  const commit = async () => {
    if (draft === (value ?? "")) {
      setEditing(false);
      return;
    }
    setSaving(true);
    try {
      await onSave(draft);
      setEditing(false);
    } catch {
      // error toast handled upstream
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="flex flex-col gap-1">
      <span className="text-[10px] font-bold uppercase tracking-widest text-gray-400">{label}</span>
      {editing ? (
        <div className="flex items-center gap-2">
          {type === "select" ? (
            <select
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              className="text-sm border border-gray-300 rounded-md px-2 py-1 focus:outline-none focus:ring-2 focus:ring-orange-300"
              autoFocus
            >
              <option value="">—</option>
              {(options ?? []).map((o) => (
                <option key={o} value={o}>
                  {humanise(o)}
                </option>
              ))}
            </select>
          ) : (
            <input
              type={type}
              value={draft}
              placeholder={placeholder}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") void commit();
                if (e.key === "Escape") setEditing(false);
              }}
              className="text-sm border border-gray-300 rounded-md px-2 py-1 focus:outline-none focus:ring-2 focus:ring-orange-300"
              autoFocus
            />
          )}
          <button
            type="button"
            onClick={() => void commit()}
            disabled={saving}
            className="text-xs font-semibold text-orange-600 hover:text-orange-700 disabled:opacity-50"
          >
            {saving ? "Saving…" : "Save"}
          </button>
          <button
            type="button"
            onClick={() => {
              setDraft(value ?? "");
              setEditing(false);
            }}
            className="text-xs text-gray-400 hover:text-gray-600"
          >
            Cancel
          </button>
        </div>
      ) : (
        <button
          type="button"
          onClick={() => setEditing(true)}
          className="text-left text-sm text-gray-900 hover:text-orange-600 group flex items-center gap-1.5"
        >
          {type === "select" && value ? (
            <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold ${statusBadgeClasses(value)}`}>
              {humanise(value)}
            </span>
          ) : (
            <span>{value || <span className="text-gray-400">—</span>}</span>
          )}
          <span className="opacity-0 group-hover:opacity-100 text-[10px] text-gray-400">edit</span>
        </button>
      )}
    </div>
  );
}

// ─── Section list card ──────────────────────────────────────────────────────────

function SectionCard({ title, count, children }: { title: string; count: number; children: React.ReactNode }) {
  return (
    <Card>
      <CardHeader title={`${title} (${count})`} />
      <CardBody>{children}</CardBody>
    </Card>
  );
}

function EmptyRow({ text }: { text: string }) {
  return <p className="text-sm text-gray-400 py-2">{text}</p>;
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function MemberDetailPage({ params }: { params: { member_id: string } }) {
  const memberId = params.member_id;
  const { isLoading: authLoading } = useAuth();
  const [member, setMember] = useState<MemberDetail | null>(null);
  const [history, setHistory] = useState<HistoryEvent[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);

  // notes
  const [noteDraft, setNoteDraft] = useState("");
  const [postingNote, setPostingNote] = useState(false);
  const [deleteNoteId, setDeleteNoteId] = useState<string | null>(null);
  const [deletingNote, setDeletingNote] = useState(false);
  const noteRef = useRef<HTMLTextAreaElement>(null);

  const loadDetail = useCallback(async () => {
    try {
      const data = await apiClient.get<MemberDetail>(`/members/${memberId}`, { silent: true });
      setMember(data);
    } catch {
      setNotFound(true);
    }
  }, [memberId]);

  const loadHistory = useCallback(async () => {
    try {
      const data = await apiClient.get<{ events: HistoryEvent[] }>(
        `/members/${memberId}/history`,
        { silent: true },
      );
      setHistory(data.events ?? []);
    } catch {
      // history is best-effort
    }
  }, [memberId]);

  useEffect(() => {
    if (authLoading) return;
    let cancelled = false;
    void (async () => {
      await Promise.all([loadDetail(), loadHistory()]);
      if (!cancelled) setIsLoading(false);
    })();
    return () => {
      cancelled = true;
    };
  }, [authLoading, loadDetail, loadHistory]);

  const patchField = useCallback(
    async (field: "name" | "email" | "status" | "coach_id", next: string) => {
      try {
        await apiClient.patch(`/members/${memberId}`, { [field]: next || null });
        setMember((prev) => (prev ? { ...prev, [field]: next || null } : prev));
        showSuccess(`Updated ${humanise(field)}`);
        void loadHistory();
      } catch (err) {
        showApiError(err as Error);
        throw err;
      }
    },
    [memberId, loadHistory],
  );

  const postNote = useCallback(async () => {
    const body = noteDraft.trim();
    if (!body) return;
    setPostingNote(true);
    try {
      await apiClient.post(`/members/${memberId}/notes`, { body });
      setNoteDraft("");
      showSuccess("Note added");
      await Promise.all([loadDetail(), loadHistory()]);
    } catch (err) {
      showApiError(err as Error);
    } finally {
      setPostingNote(false);
    }
  }, [memberId, noteDraft, loadDetail, loadHistory]);

  const confirmDeleteNote = useCallback(async () => {
    if (!deleteNoteId) return;
    setDeletingNote(true);
    try {
      await apiClient.delete(`/members/${memberId}/notes/${deleteNoteId}`);
      showSuccess("Note deleted");
      setDeleteNoteId(null);
      await Promise.all([loadDetail(), loadHistory()]);
    } catch (err) {
      showApiError(err as Error);
    } finally {
      setDeletingNote(false);
    }
  }, [memberId, deleteNoteId, loadDetail, loadHistory]);

  if (notFound) {
    return (
      <>
        <Header title="Member" />
        <main className="flex-1 overflow-y-auto p-7">
          <Card>
            <CardBody>
              <p className="text-sm text-gray-600">Member not found.</p>
              <div className="mt-3">
                <Button variant="ghost" href="/members">
                  ← Back to Members
                </Button>
              </div>
            </CardBody>
          </Card>
        </main>
      </>
    );
  }

  if (isLoading || !member) {
    return (
      <>
        <Header title="Member" />
        <main className="flex-1 overflow-y-auto p-7 space-y-4">
          <div className="h-7 w-56 bg-gray-200 rounded animate-pulse" />
          <div className="h-40 bg-gray-100 rounded-xl animate-pulse" />
          <div className="h-64 bg-gray-100 rounded-xl animate-pulse" />
        </main>
      </>
    );
  }

  return (
    <>
      <Header title={member.name || "Member"} />
      <main className="flex-1 overflow-y-auto p-7 space-y-6">
        {/* Back link */}
        <Button variant="ghost" href="/members" size="sm">
          ← Members
        </Button>

        {/* Identity card with inline-edit fields */}
        <Card>
          <CardBody>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-5">
              <InlineField label="Name" value={member.name} onSave={(v) => patchField("name", v)} />
              <InlineField label="Email" type="email" value={member.email} onSave={(v) => patchField("email", v)} />
              <InlineField
                label="Status"
                type="select"
                options={STATUS_OPTIONS}
                value={member.status}
                onSave={(v) => patchField("status", v)}
              />
              <InlineField
                label="Coach"
                value={member.coach_id}
                placeholder="coach user id"
                onSave={(v) => patchField("coach_id", v)}
              />
            </div>
            <div className="mt-4 pt-4 border-t border-gray-100 flex gap-6 text-xs text-gray-500">
              <span>Enrolled: {fmtDate(member.enrollment_date)}</span>
              <span>Created: {fmtDate(member.created_at)}</span>
            </div>
          </CardBody>
        </Card>

        {/* Two-column: goals/wins/pain + notes/history */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <div className="space-y-4">
            <SectionCard title="Goals" count={member.goals.length}>
              {member.goals.length === 0 ? (
                <EmptyRow text="No goals yet." />
              ) : (
                <ul className="space-y-2">
                  {member.goals.map((g) => (
                    <li key={g.id} className="flex items-start justify-between gap-3 text-sm">
                      <span className="text-gray-800">{g.goal_text || "—"}</span>
                      <span className={`shrink-0 inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold ${statusBadgeClasses(g.status)}`}>
                        {g.status ? humanise(g.status) : "—"}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </SectionCard>

            <SectionCard title="Wins" count={member.wins.length}>
              {member.wins.length === 0 ? (
                <EmptyRow text="No wins recorded yet." />
              ) : (
                <ul className="space-y-2">
                  {member.wins.map((w) => (
                    <li key={w.id} className="text-sm">
                      <div className="flex items-center justify-between gap-3">
                        <span className="text-gray-800">{w.win_text || "—"}</span>
                        <span className="shrink-0 text-[11px] text-gray-400">{fmtDate(w.win_date)}</span>
                      </div>
                      {w.impact_area && (
                        <span className="inline-flex items-center mt-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-orange-50 text-orange-700">
                          {w.impact_area}
                        </span>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </SectionCard>

            <SectionCard title="Pain Points" count={member.pain_points.length}>
              {member.pain_points.length === 0 ? (
                <EmptyRow text="No pain points yet." />
              ) : (
                <ul className="space-y-2">
                  {member.pain_points.map((p) => (
                    <li key={p.id} className="flex items-start justify-between gap-3 text-sm">
                      <span className="text-gray-800">{p.text || "—"}</span>
                      {p.category && <span className="shrink-0 text-[11px] text-gray-400">{p.category}</span>}
                    </li>
                  ))}
                </ul>
              )}
            </SectionCard>

            <SectionCard title="Calls" count={member.calls.length}>
              {member.calls.length === 0 ? (
                <EmptyRow text="No calls logged yet." />
              ) : (
                <ul className="space-y-2">
                  {member.calls.map((c) => (
                    <li key={c.id} className="flex items-center justify-between gap-3 text-sm">
                      <span className="text-gray-800">{c.call_type ? humanise(c.call_type) : "Call"}</span>
                      <span className="shrink-0 text-[11px] text-gray-400">
                        {c.processed_date ? `${c.insights_count} insights · ${fmtDate(c.date)}` : "Analyzing…"}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </SectionCard>
          </div>

          <div className="space-y-4">
            {/* Staff notes */}
            <Card>
              <CardHeader title={`Staff Notes (${member.staff_notes.length})`} />
              <CardBody>
                <div className="flex flex-col gap-2">
                  <textarea
                    ref={noteRef}
                    value={noteDraft}
                    onChange={(e) => setNoteDraft(e.target.value)}
                    onKeyDown={(e) => {
                      if ((e.metaKey || e.ctrlKey) && e.key === "Enter") void postNote();
                    }}
                    placeholder="Add a note… (⌘/Ctrl+Enter to post)"
                    rows={2}
                    className="text-sm border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-orange-300 resize-none"
                  />
                  <div className="flex justify-end">
                    <Button
                      variant="primary"
                      size="sm"
                      onClick={() => void postNote()}
                      disabled={postingNote || noteDraft.trim() === ""}
                    >
                      {postingNote ? "Adding…" : "Add note"}
                    </Button>
                  </div>
                </div>

                <ul className="mt-4 space-y-3">
                  {member.staff_notes.length === 0 ? (
                    <EmptyRow text="No notes yet." />
                  ) : (
                    member.staff_notes.map((n) => (
                      <li key={n.id} className="group border-l-2 border-orange-200 pl-3">
                        <div className="flex items-start justify-between gap-3">
                          <p className="text-sm text-gray-800 whitespace-pre-wrap">{n.body}</p>
                          <button
                            type="button"
                            onClick={() => setDeleteNoteId(n.id)}
                            className="opacity-0 group-hover:opacity-100 text-[11px] text-red-500 hover:text-red-600 shrink-0"
                          >
                            Delete
                          </button>
                        </div>
                        <span className="text-[11px] text-gray-400">
                          {n.author_email || "Staff"} · {fmtDate(n.created_at)}
                        </span>
                      </li>
                    ))
                  )}
                </ul>
              </CardBody>
            </Card>

            {/* Activity timeline */}
            <Card>
              <CardHeader title="Activity" />
              <CardBody>
                {history.length === 0 ? (
                  <EmptyRow text="No activity yet." />
                ) : (
                  <ul className="space-y-3">
                    {history.map((ev) => (
                      <li key={ev.id} className="flex items-start gap-2.5 text-sm">
                        <span
                          className="mt-1.5 w-2 h-2 rounded-full shrink-0"
                          style={{ backgroundColor: ORANGE }}
                          aria-hidden="true"
                        />
                        <div className="flex flex-col">
                          <span className="text-gray-800">{humanise(ev.action.replace(/^member\./, ""))}</span>
                          {ev.after && (
                            <span className="text-[11px] text-gray-400">
                              {Object.entries(ev.after)
                                .map(([k, v]) => `${humanise(k)}: ${String(v ?? "—")}`)
                                .join(", ")}
                            </span>
                          )}
                          <span className="text-[11px] text-gray-400">
                            {ev.author_email ? `${ev.author_email} · ` : ""}
                            {fmtDate(ev.created_at)}
                          </span>
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </CardBody>
            </Card>
          </div>
        </div>
      </main>

      <ConfirmDialog
        open={deleteNoteId !== null}
        onClose={() => setDeleteNoteId(null)}
        onConfirm={() => void confirmDeleteNote()}
        title="Delete note?"
        description="This permanently removes the staff note. This can't be undone."
        confirmLabel="Delete"
        variant="danger"
        loading={deletingNote}
      />
    </>
  );
}
