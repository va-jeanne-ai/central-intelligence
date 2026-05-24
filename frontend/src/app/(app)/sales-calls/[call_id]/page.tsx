"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { Header } from "@/components/layout/header";
import { apiClient } from "@/lib/api-client";
import { useAuth } from "@/hooks/use-auth";
import { showError, showWarning } from "@/lib/toast";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";

// ─── Types ────────────────────────────────────────────────────────────────────

interface CallDetail {
  call_id: string;
  date: string | null;
  call_type: string | null;
  call_result: string | null;
  call_owner: string | null;
  transcript_quality: string | null;
  processed_date: string | null;
  transcript: string | null;
  summary: string | null;
  created_at: string | null;
}

interface InsightBrief {
  insight_id: string;
  insight_type: string | null;
  signal_family: string | null;
  signal: string | null;
  raw_quote: string | null;
}

interface ContentIdeaBrief {
  content_id: string;
  content_format: string | null;
  status: string | null;
  priority_level: string | null;
  idea_score: number | null;
}

interface CallDetailResponse {
  call: CallDetail;
  insights: InsightBrief[];
  content_ideas: ContentIdeaBrief[];
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "numeric",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

async function downloadTranscript(callId: string): Promise<void> {
  const token = apiClient.getToken();
  const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";
  const headers: HeadersInit = {};
  if (token !== null) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${apiBase}/ci/calls/${callId}/transcript.txt`, {
    method: "GET",
    headers,
  });
  if (!res.ok) {
    if (res.status === 404) {
      showWarning("No transcript on file for this call.");
    } else {
      showError(`Download failed (${res.status})`);
    }
    return;
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${callId}.txt`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

// ─── Inline-edit primitives ───────────────────────────────────────────────────
//
// Two flavors live on this page:
//  - InlineTextEdit: single-line input for short metadata (owner, type, result)
//  - InlineTextareaEdit: multi-line textarea for summary + insight fields
//
// Both use the same pattern: render `displayValue` until clicked, then swap to
// an input with Save / Cancel. Saving calls `onSave(newValue)` and the parent
// decides what to do with it (PATCH the API, update state, etc.).

interface InlineTextEditProps {
  value: string | null;
  placeholder?: string;
  emptyLabel?: string;
  className?: string;
  inputClassName?: string;
  onSave: (next: string | null) => Promise<void> | void;
}

function InlineTextEdit({
  value,
  placeholder = "",
  emptyLabel = "—",
  className = "",
  inputClassName = "",
  onSave,
}: InlineTextEditProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [draft, setDraft] = useState(value ?? "");
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    if (!isEditing) setDraft(value ?? "");
  }, [value, isEditing]);

  if (!isEditing) {
    const display = value && value.trim() !== "" ? value : emptyLabel;
    const isEmpty = !value || value.trim() === "";
    return (
      <button
        type="button"
        onClick={() => setIsEditing(true)}
        className={`text-left hover:bg-amber-50/60 rounded px-1 -mx-1 transition-colors ${
          isEmpty ? "text-gray-400 italic" : ""
        } ${className}`}
        title="Click to edit"
      >
        {display}
      </button>
    );
  }

  async function commit() {
    setIsSaving(true);
    try {
      const next = draft.trim() === "" ? null : draft;
      await onSave(next);
      setIsEditing(false);
    } catch (err) {
      showError(err instanceof Error ? err.message : "Save failed.");
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <span className="inline-flex items-center gap-1.5">
      <input
        type="text"
        value={draft}
        placeholder={placeholder}
        autoFocus
        disabled={isSaving}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") void commit();
          if (e.key === "Escape") setIsEditing(false);
        }}
        className={`border border-indigo-300 rounded px-1.5 py-0.5 focus:outline-none focus:ring-2 focus:ring-indigo-300/50 ${inputClassName}`}
      />
      <button
        type="button"
        onClick={() => void commit()}
        disabled={isSaving}
        className="text-[12px] font-medium text-indigo-600 hover:text-indigo-700"
      >
        {isSaving ? "…" : "Save"}
      </button>
      <button
        type="button"
        onClick={() => setIsEditing(false)}
        disabled={isSaving}
        className="text-[12px] text-gray-400 hover:text-gray-600"
      >
        Cancel
      </button>
    </span>
  );
}

interface InlineTextareaEditProps {
  value: string | null;
  rows?: number;
  emptyMessage: React.ReactNode;
  className?: string;
  onSave: (next: string | null) => Promise<void> | void;
}

function InlineTextareaEdit({
  value,
  rows = 5,
  emptyMessage,
  className = "",
  onSave,
}: InlineTextareaEditProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [draft, setDraft] = useState(value ?? "");
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    if (!isEditing) setDraft(value ?? "");
  }, [value, isEditing]);

  if (!isEditing) {
    return (
      <button
        type="button"
        onClick={() => setIsEditing(true)}
        className="block w-full text-left hover:bg-amber-50/60 rounded p-1 -m-1 transition-colors"
        title="Click to edit"
      >
        {value && value.trim() !== "" ? (
          <p className={`whitespace-pre-wrap leading-relaxed ${className}`}>{value}</p>
        ) : (
          emptyMessage
        )}
      </button>
    );
  }

  async function commit() {
    setIsSaving(true);
    try {
      const next = draft.trim() === "" ? null : draft;
      await onSave(next);
      setIsEditing(false);
    } catch (err) {
      showError(err instanceof Error ? err.message : "Save failed.");
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <div className="space-y-2">
      <textarea
        value={draft}
        rows={rows}
        autoFocus
        disabled={isSaving}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Escape") setIsEditing(false);
          // Cmd+Enter / Ctrl+Enter to save (Enter alone is a newline in a textarea)
          if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) void commit();
        }}
        className={`w-full border border-indigo-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-300/50 ${className}`}
      />
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={() => void commit()}
          disabled={isSaving}
          className="text-[13px] font-medium px-3 py-1 rounded-lg bg-indigo-500 hover:bg-indigo-600 disabled:bg-indigo-200 disabled:cursor-not-allowed text-white"
        >
          {isSaving ? "Saving…" : "Save"}
        </button>
        <button
          type="button"
          onClick={() => setIsEditing(false)}
          disabled={isSaving}
          className="text-[13px] text-gray-500 hover:text-gray-700"
        >
          Cancel
        </button>
        <span className="text-[11px] text-gray-400 ml-auto">⌘+Enter saves · Esc cancels</span>
      </div>
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function CallDetailPage({ params }: { params: { call_id: string } }) {
  const { isLoading: authLoading } = useAuth();
  const callId = params.call_id;

  const [detail, setDetail] = useState<CallDetailResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Pending-delete state for the confirm dialog. When non-null, the dialog
  // is open and confirming deletes this insight id.
  const [pendingDeleteInsightId, setPendingDeleteInsightId] = useState<
    string | null
  >(null);
  const [isDeletingInsight, setIsDeletingInsight] = useState(false);
  const [isReanalyzing, setIsReanalyzing] = useState(false);

  // Track the processed_date at the moment Re-analyze starts so polls can
  // detect when fresh data has actually landed (vs serving stale rows).
  const reanalyzeBaselineRef = useRef<string | null>(null);

  const load = useCallback(
    async (opts: { showSpinner?: boolean; commit?: boolean } = {}) => {
      const showSpinner = opts.showSpinner ?? false;
      const commit = opts.commit ?? true;
      if (showSpinner) setIsLoading(true);
      setError(null);
      try {
        const data = await apiClient.get<CallDetailResponse>(`/ci/calls/${callId}`, {
          silent: true,
        });
        if (commit) setDetail(data);
        return data;
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load call.");
        return null;
      } finally {
        if (showSpinner) setIsLoading(false);
      }
    },
    [callId],
  );

  useEffect(() => {
    if (authLoading) return;
    void load({ showSpinner: true });
  }, [authLoading, load]);

  async function handleReanalyze() {
    reanalyzeBaselineRef.current = detail?.call.processed_date ?? null;
    setIsReanalyzing(true);
    try {
      await apiClient.post(`/ci/calls/${callId}/analyze`, {}, { silent: true });
      const maxAttempts = 30; // ~3 minutes at 6s
      const baseline = reanalyzeBaselineRef.current;
      for (let i = 0; i < maxAttempts; i += 1) {
        await new Promise((r) => setTimeout(r, 6000));
        const fresh = await load({ showSpinner: false, commit: false });
        if (fresh && fresh.call.processed_date && fresh.call.processed_date !== baseline) {
          setDetail(fresh);
          return;
        }
      }
      await load({ showSpinner: false, commit: true });
    } catch (err) {
      showError(err instanceof Error ? err.message : "Re-analyze failed.");
    } finally {
      setIsReanalyzing(false);
    }
  }

  // ─── PATCH helpers ──────────────────────────────────────────────────────────

  async function saveCallField(field: keyof CallDetail, value: string | null) {
    const updated = await apiClient.patch<CallDetail>(
      `/ci/calls/${callId}`,
      { [field]: value },
      { silent: true },
    );
    setDetail((d) => (d ? { ...d, call: updated } : d));
  }

  async function saveInsightField(
    insightId: string,
    field: keyof InsightBrief,
    value: string | null,
  ) {
    const updated = await apiClient.patch<InsightBrief>(
      `/ci/insights/${insightId}`,
      { [field]: value },
      { silent: true },
    );
    setDetail((d) =>
      d ? { ...d, insights: d.insights.map((i) => (i.insight_id === insightId ? updated : i)) } : d,
    );
  }

  function deleteInsight(insightId: string) {
    // Don't delete inline — open the ConfirmDialog and defer the actual
    // call to confirmDeleteInsight below. Using window.confirm here would
    // bypass the project's toast/dialog UX (CLAUDE.md rule).
    setPendingDeleteInsightId(insightId);
  }

  async function confirmDeleteInsight() {
    const insightId = pendingDeleteInsightId;
    if (!insightId) return;
    setIsDeletingInsight(true);
    try {
      await apiClient.delete(`/ci/insights/${insightId}`, { silent: true });
      setDetail((d) =>
        d ? { ...d, insights: d.insights.filter((i) => i.insight_id !== insightId) } : d,
      );
    } catch (err) {
      showError(err instanceof Error ? err.message : "Delete failed.");
    } finally {
      setIsDeletingInsight(false);
      setPendingDeleteInsightId(null);
    }
  }

  // ─── Render ─────────────────────────────────────────────────────────────────

  if (isLoading) {
    return (
      <>
        <Header title="Call detail" />
        <main className="flex-1 overflow-y-auto p-7">
          <p className="text-[15px] text-gray-400">Loading…</p>
        </main>
      </>
    );
  }

  if (error || detail === null) {
    return (
      <>
        <Header title="Call detail" />
        <main className="flex-1 overflow-y-auto p-7 space-y-4">
          <Link href="/sales-calls" className="text-[15px] text-indigo-600 hover:text-indigo-700 underline underline-offset-2">
            ← Back to calls
          </Link>
          <p className="text-[15px] text-red-700">{error ?? "Call not found."}</p>
        </main>
      </>
    );
  }

  const { call, insights, content_ideas } = detail;

  // First-pass analyzer hasn't completed yet — no processed_date stamped.
  // Drives the "Analyzing…" placeholders below. Distinct from isReanalyzing
  // (manual re-run on an already-processed call).
  const isProcessing = !call.processed_date;

  return (
    <>
      <Header title="Call detail" />

      <main className="flex-1 overflow-y-auto p-7 space-y-6">
        {/* Back link */}
        <Link
          href="/sales-calls"
          className="inline-block text-[13px] font-medium text-indigo-600 hover:text-indigo-700 underline underline-offset-2"
        >
          ← Back to calls
        </Link>

        {/* Header — editable metadata */}
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <h1 className="text-[22px] font-bold text-gray-900 truncate">
              <InlineTextEdit
                value={call.call_type}
                placeholder="Call type"
                emptyLabel="Call"
                inputClassName="text-[22px] font-bold"
                onSave={(v) => saveCallField("call_type", v)}
              />
              {" — "}
              {formatDate(call.created_at)}
            </h1>
            <p className="text-[13px] text-gray-500 mt-0.5 font-mono">{call.call_id}</p>
            <p className="text-[13px] text-gray-500 mt-1 flex items-center gap-2 flex-wrap">
              <span>
                Owner:{" "}
                <InlineTextEdit
                  value={call.call_owner}
                  placeholder="Call owner"
                  emptyLabel="Unknown owner"
                  inputClassName="text-[13px]"
                  onSave={(v) => saveCallField("call_owner", v)}
                />
              </span>
              <span className="text-gray-300">·</span>
              <span>
                Result:{" "}
                <InlineTextEdit
                  value={call.call_result}
                  placeholder="Call result"
                  emptyLabel="No result"
                  inputClassName="text-[13px]"
                  onSave={(v) => saveCallField("call_result", v)}
                />
              </span>
              {call.processed_date && (
                <span className="text-[11px] font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded bg-emerald-50 text-emerald-700 border border-emerald-200">
                  Processed
                </span>
              )}
            </p>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <button
              type="button"
              onClick={() => void downloadTranscript(call.call_id)}
              className="text-[13px] font-medium text-indigo-600 hover:text-indigo-700 underline underline-offset-2"
            >
              Download transcript
            </button>
            <button
              type="button"
              onClick={() => void handleReanalyze()}
              disabled={isReanalyzing}
              className="text-[13px] font-medium px-3 py-1.5 rounded-lg bg-indigo-500 hover:bg-indigo-600 disabled:bg-indigo-200 disabled:cursor-not-allowed text-white transition-colors"
            >
              {isReanalyzing ? "Re-analyzing…" : "Re-analyze"}
            </button>
          </div>
        </div>

        {/* Re-analyzing banner */}
        {isReanalyzing && (
          <div className="flex items-center gap-3 bg-amber-50 border border-amber-200 rounded-lg px-4 py-3">
            <svg
              className="animate-spin w-4 h-4 text-amber-600 shrink-0"
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
              aria-hidden="true"
            >
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            <p className="text-[13px] text-amber-800">
              Re-analyzing this call… the existing summary and insights below will update once the new run finishes.
            </p>
          </div>
        )}

        {/* Analysis sections — dimmed while re-analyzing.
            isProcessing = first-pass analyzer hasn't written processed_date
            yet. Distinct from isReanalyzing (manual re-run on an already-
            processed call). Drives the "Analyzing…" placeholder below. */}
        <div className={`space-y-6 transition-opacity ${isReanalyzing ? "opacity-60 pointer-events-none" : ""}`}>
          {/* Summary — editable */}
          <section className="bg-white rounded-xl border border-gray-200 shadow-sm p-5">
            <h2 className="text-[15px] font-bold text-gray-900 mb-2">Summary</h2>
            <InlineTextareaEdit
              value={call.summary}
              rows={6}
              className="text-[15px] text-gray-700"
              emptyMessage={
                isProcessing ? (
                  <div className="flex items-center gap-2 text-[13px] text-amber-700">
                    <svg
                      className="animate-spin w-3.5 h-3.5 text-amber-600 shrink-0"
                      xmlns="http://www.w3.org/2000/svg"
                      fill="none"
                      viewBox="0 0 24 24"
                      aria-hidden="true"
                    >
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                    <span>Analyzing the transcript… summary will appear here once the run finishes.</span>
                  </div>
                ) : (
                  <p className="text-[13px] text-gray-400 italic">
                    No summary yet. Click to write one, or run Re-analyze if the analyzer hasn&apos;t run.
                  </p>
                )
              }
              onSave={(v) => saveCallField("summary", v)}
            />
          </section>

          {/* Insights — editable + deletable */}
          <section className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
            <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
              <h2 className="text-[15px] font-bold text-gray-900">Insights</h2>
              <span className="text-[13px] text-gray-400">{insights.length}</span>
            </div>
            {insights.length === 0 ? (
              isProcessing ? (
                <div className="px-5 py-6 flex items-center gap-2 text-[13px] text-amber-700">
                  <svg
                    className="animate-spin w-3.5 h-3.5 text-amber-600 shrink-0"
                    xmlns="http://www.w3.org/2000/svg"
                    fill="none"
                    viewBox="0 0 24 24"
                    aria-hidden="true"
                  >
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  <span>Analyzing the transcript… insights will appear here once the run finishes.</span>
                </div>
              ) : (
                <div className="px-5 py-6 text-[13px] text-gray-400 italic">No insights extracted yet.</div>
              )
            ) : (
              <div className="divide-y divide-gray-100">
                {insights.map((ins) => (
                  <div key={ins.insight_id} className="px-5 py-3 group">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-[11px] font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded bg-indigo-50 text-indigo-700 border border-indigo-200">
                        <InlineTextEdit
                          value={ins.insight_type}
                          placeholder="type"
                          emptyLabel="type"
                          inputClassName="text-[11px] uppercase"
                          onSave={(v) => saveInsightField(ins.insight_id, "insight_type", v)}
                        />
                      </span>
                      <span className="text-[11px] text-gray-500">
                        <InlineTextEdit
                          value={ins.signal_family}
                          placeholder="signal_family"
                          emptyLabel="family"
                          inputClassName="text-[11px]"
                          onSave={(v) => saveInsightField(ins.insight_id, "signal_family", v)}
                        />
                      </span>
                      <button
                        type="button"
                        onClick={() => void deleteInsight(ins.insight_id)}
                        className="ml-auto text-[11px] text-red-500 hover:text-red-700 opacity-0 group-hover:opacity-100 transition-opacity"
                        title="Delete this insight"
                      >
                        Delete
                      </button>
                    </div>
                    <div className="text-[15px] font-medium text-gray-900 mt-1">
                      <InlineTextEdit
                        value={ins.signal}
                        placeholder="Signal label"
                        emptyLabel="(no signal)"
                        inputClassName="text-[15px] font-medium w-full min-w-[400px]"
                        className="block"
                        onSave={(v) => saveInsightField(ins.insight_id, "signal", v)}
                      />
                    </div>
                    <div className="text-[13px] text-gray-600 italic mt-1">
                      <InlineTextareaEdit
                        value={ins.raw_quote}
                        rows={2}
                        className="text-[13px] not-italic"
                        emptyMessage={<span className="text-gray-400">(no quote)</span>}
                        onSave={(v) => saveInsightField(ins.insight_id, "raw_quote", v)}
                      />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>

          {/* Content ideas — read-only on this page */}
          {content_ideas.length > 0 && (
            <section className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
              <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
                <h2 className="text-[15px] font-bold text-gray-900">Content ideas</h2>
                <span className="text-[13px] text-gray-400">{content_ideas.length}</span>
              </div>
              <div className="divide-y divide-gray-100">
                {content_ideas.map((idea) => (
                  <div key={idea.content_id} className="px-5 py-3 text-[15px] text-gray-700 flex items-center justify-between">
                    <span>
                      {idea.content_format ?? "Idea"}
                      {idea.priority_level ? ` · ${idea.priority_level}` : ""}
                    </span>
                    {idea.status && <span className="text-[13px] text-gray-400">{idea.status}</span>}
                  </div>
                ))}
              </div>
            </section>
          )}
        </div>

        {/* Transcript — read-only */}
        <section className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
          <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
            <h2 className="text-[15px] font-bold text-gray-900">Transcript</h2>
            <span className="text-[13px] text-gray-400">
              {call.transcript ? `${call.transcript.length.toLocaleString()} chars` : "—"}
            </span>
          </div>
          {call.transcript ? (
            <pre className="px-5 py-4 text-[13px] text-gray-700 whitespace-pre-wrap font-sans leading-relaxed max-h-96 overflow-y-auto">
              {call.transcript}
            </pre>
          ) : (
            <div className="px-5 py-6 text-[13px] text-gray-400 italic">No transcript on file.</div>
          )}
        </section>
      </main>

      <ConfirmDialog
        open={pendingDeleteInsightId !== null}
        onClose={() => setPendingDeleteInsightId(null)}
        onConfirm={() => void confirmDeleteInsight()}
        title="Delete this insight?"
        description="This cannot be undone."
        confirmLabel="Delete"
        variant="danger"
        loading={isDeletingInsight}
      />
    </>
  );
}
