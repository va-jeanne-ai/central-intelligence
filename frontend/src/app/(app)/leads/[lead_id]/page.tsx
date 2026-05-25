"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { Header } from "@/components/layout/header";
import { Card, CardHeader, CardBody } from "@/components/ui/card";
import { ScoreBar } from "@/components/ui/score-bar";
import { FormField, FormSelect, FormTextarea } from "@/components/ui/form-field";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { HistoryItem, HistoryList } from "@/components/ui/history-item";
import { TranscriptUploadWidget } from "@/components/upload/transcript-upload-widget";
import { apiClient } from "@/lib/api-client";
import { useAuth } from "@/hooks/use-auth";
import { showError, showSuccess, showWarning } from "@/lib/toast";
import type { LeadStatus, LeadSource } from "@/types";

// ─── API response shapes ─────────────────────────────────────────────────────

interface LeadCallSummary {
  id: string;
  date: string | null;
  call_type: string | null;
  insights_count: number;
  // NULL while the background analyzer is still running. Drives the
  // in-progress row variant + the 10s poller on the lead detail page.
  processed_date: string | null;
}

interface LeadGoalSummary {
  id: string;
  goal_text: string | null;
  status: string | null;
  target_date: string | null;
}

interface LeadPainPointSummary {
  id: string;
  text: string | null;
  category: string | null;
}

interface LeadObjectionSummary {
  id: string;
  objection_text: string | null;
  resolution_offered: string | null;
}

interface NoteRow {
  id: string;
  body: string;
  author_id: string | null;
  author_email: string | null;
  created_at: string;
}

interface LeadDetailResponse {
  id: string;
  name: string | null;
  email: string | null;
  phone: string | null;
  status: string | null;
  source: string | null;
  score: number;
  external_id: string | null;
  created_at: string | null;
  notes_raw: string | null;
  calls: LeadCallSummary[];
  goals: LeadGoalSummary[];
  pain_points: LeadPainPointSummary[];
  objections: LeadObjectionSummary[];
  staff_notes: NoteRow[];
}

interface LeadHistoryEvent {
  id: string;
  action: string;
  before: Record<string, unknown> | null;
  after: Record<string, unknown> | null;
  author_id: string | null;
  author_email: string | null;
  created_at: string;
}

interface LeadHistoryResponse {
  events: LeadHistoryEvent[];
}

interface EmailAttachmentMeta {
  filename: string;
  size: number;
  mime_type: string | null;
}

interface EmailMessageRow {
  id: string;
  from_address: string | null;
  to_addresses: string[];
  cc_addresses: string[];
  subject: string | null;
  body_text: string | null;
  sent_at: string | null;
  has_attachments: boolean;
  attachments_meta: EmailAttachmentMeta[];
}

interface EmailThreadRow {
  id: string;
  subject: string | null;
  last_message_at: string | null;
  message_count: number;
  messages: EmailMessageRow[];
}

interface EmailThreadsResponse {
  threads: EmailThreadRow[];
}

interface DocumentRow {
  id: string;
  name: string | null;
  mime_type: string | null;
  owner_email: string | null;
  modified_time: string | null;
  web_view_link: string | null;
  parent_folder_name: string | null;
  size_bytes: number | null;
}

interface DocumentsResponse {
  files: DocumentRow[];
}

function mimeIcon(mime: string | null): string {
  if (!mime) return "📄";
  if (mime.includes("spreadsheet") || mime === "text/csv") return "📊";
  if (mime.includes("presentation")) return "🎨";
  if (mime === "application/pdf") return "📕";
  if (mime.includes("document") || mime.startsWith("text/")) return "📄";
  if (mime.startsWith("image/")) return "🖼️";
  return "📄";
}

// ─── Status / Source display config ──────────────────────────────────────────
// TODO(v2): hoist to @/lib/lead-display.ts — duplicated from
// /leads/page.tsx for now since the detail page is the second consumer.

const STATUS_CONFIG: Record<
  LeadStatus,
  { label: string; dotColor: string; badgeClasses: string }
> = {
  new: { label: "New", dotColor: "#3B82F6", badgeClasses: "bg-blue-50 text-blue-700" },
  contacted: { label: "Active", dotColor: "#F97316", badgeClasses: "bg-orange-50 text-orange-700" },
  qualified: { label: "Applied", dotColor: "#8B5CF6", badgeClasses: "bg-violet-50 text-violet-700" },
  appointment_set: { label: "Booked", dotColor: "#0D9488", badgeClasses: "bg-teal-50 text-teal-700" },
  closed_won: { label: "Closed Won", dotColor: "#10B981", badgeClasses: "bg-green-50 text-green-700" },
  closed_lost: { label: "Lost", dotColor: "#9CA3AF", badgeClasses: "bg-gray-100 text-gray-500" },
  stale: { label: "Stale", dotColor: "#6366F1", badgeClasses: "bg-indigo-50 text-indigo-700" },
};

const SOURCE_CONFIG: Record<LeadSource, { label: string; badgeClasses: string }> = {
  webinar: { label: "Webinar", badgeClasses: "bg-indigo-50 text-indigo-700" },
  vsl: { label: "VSL", badgeClasses: "bg-blue-50 text-blue-700" },
  "opt-in": { label: "Opt-in", badgeClasses: "bg-green-50 text-green-700" },
  ads: { label: "Ads", badgeClasses: "bg-gray-100 text-gray-600" },
  referral: { label: "Referral", badgeClasses: "bg-violet-50 text-violet-700" },
  other: { label: "Other", badgeClasses: "bg-gray-100 text-gray-500" },
};

const STATUS_OPTIONS: LeadStatus[] = [
  "new",
  "contacted",
  "qualified",
  "appointment_set",
  "closed_won",
  "closed_lost",
  "stale",
];

function _humanise(value: string): string {
  return value
    .split(/[_\-\s]+/)
    .filter(Boolean)
    .map((w) => (w.length <= 3 ? w.toUpperCase() : w[0].toUpperCase() + w.slice(1).toLowerCase()))
    .join(" ");
}

function resolveStatus(raw: string | null) {
  if (!raw) return { label: "—", dotColor: "#9CA3AF", badgeClasses: "bg-gray-100 text-gray-500" };
  return (
    STATUS_CONFIG[raw as LeadStatus] ?? {
      label: _humanise(raw),
      dotColor: "#9CA3AF",
      badgeClasses: "bg-gray-100 text-gray-600",
    }
  );
}

function resolveSource(raw: string | null) {
  if (!raw) return { label: "—", badgeClasses: "bg-gray-100 text-gray-500" };
  return (
    SOURCE_CONFIG[raw as LeadSource] ?? {
      label: _humanise(raw),
      badgeClasses: "bg-gray-100 text-gray-600",
    }
  );
}

// ─── Date helpers ────────────────────────────────────────────────────────────

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

function relativeTime(iso: string): string {
  // Minimal "X min ago" / "Just now" formatter — full date on hover via title attr.
  const diff = Date.now() - new Date(iso).getTime();
  if (Number.isNaN(diff)) return iso;
  const sec = Math.floor(diff / 1000);
  if (sec < 60) return "Just now";
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min} min ago`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr} hr ago`;
  const day = Math.floor(hr / 24);
  if (day < 7) return `${day} day${day === 1 ? "" : "s"} ago`;
  return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

// ─── Inline-edit primitives ──────────────────────────────────────────────────
// TODO(v2): extract InlineTextEdit + InlineTextareaEdit to
// @/components/ui/inline-edit.tsx — this is the second consumer (call detail
// is the first); third consumer makes the right time to extract.

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

// ─── Initial Submission parsing ──────────────────────────────────────────────
//
// GHL pushes the original webhook body into `lead.notes` as a JSON string.
// We parse it best-effort and surface the human-readable fields as a card;
// the raw JSON is still available below in the collapsible "Source payload"
// section in case something is hiding that the parsed view doesn't show.

interface ParsedSubmission {
  fields: { label: string; value: string }[];
  raw: unknown;
  isJson: boolean;
}

function parseSubmission(rawText: string | null): ParsedSubmission | null {
  if (!rawText || rawText.trim() === "") return null;
  try {
    const parsed = JSON.parse(rawText) as unknown;
    if (!parsed || typeof parsed !== "object") {
      return { fields: [], raw: parsed, isJson: true };
    }
    const obj = parsed as Record<string, unknown>;
    const skipKeys = new Set(["webhook_token", "token"]);
    const fields: { label: string; value: string }[] = [];
    for (const [key, val] of Object.entries(obj)) {
      if (skipKeys.has(key)) continue;
      if (val === null || val === undefined) continue;
      if (typeof val === "string" && val.trim() === "") continue;
      // Render primitives directly; stringify nested objects/arrays.
      const valueStr =
        typeof val === "string" || typeof val === "number" || typeof val === "boolean"
          ? String(val)
          : JSON.stringify(val);
      fields.push({ label: _humanise(key), value: valueStr });
    }
    return { fields, raw: parsed, isJson: true };
  } catch {
    return { fields: [], raw: rawText, isJson: false };
  }
}

// ─── History event rendering ─────────────────────────────────────────────────
//
// Each audit action gets a dot color + a short headline + an optional
// trailing detail (the diff snippet). Unknown actions still render with
// a neutral grey dot — the GET endpoint is intentionally permissive about
// what `action` strings it serves so we can add new emitters without
// breaking the client.

const HISTORY_DOT_COLORS: Record<string, string> = {
  "lead.created": "#10B981", // green — birth event
  "lead.status_changed": "#0D9488", // teal — same family as status badge
  "lead.name_changed": "#F59E0B", // amber — field edit
  "lead.phone_changed": "#F59E0B",
  "lead.note_added": "#6366F1", // indigo — same as staff notes
  "lead.note_deleted": "#9CA3AF", // grey — soft removal
  "lead.call_logged": "#3B82F6", // blue — for future action
};

function pickString(obj: Record<string, unknown> | null, key: string): string | null {
  if (!obj) return null;
  const v = obj[key];
  return typeof v === "string" && v.trim() !== "" ? v : null;
}

function describeHistoryEvent(e: LeadHistoryEvent): {
  headline: React.ReactNode;
  detail: React.ReactNode | null;
  dotColor?: string;
} {
  const author = e.author_email ?? "system";
  switch (e.action) {
    case "lead.created":
      return {
        headline: (
          <>
            <span className="font-semibold text-gray-700">Lead created</span>
            <span className="text-gray-500"> · {author}</span>
          </>
        ),
        detail: pickString(e.after, "source")
          ? <span className="text-gray-500">via {pickString(e.after, "source")}</span>
          : null,
      };
    case "lead.status_changed": {
      const from = pickString(e.before, "status") ?? "—";
      const to = pickString(e.after, "status") ?? "—";
      return {
        headline: (
          <>
            <span className="font-semibold text-gray-700">Status changed</span>
            <span className="text-gray-500"> · {author}</span>
          </>
        ),
        detail: (
          <span className="text-gray-500 font-mono text-[11px]">
            {from} → {to}
          </span>
        ),
      };
    }
    case "lead.name_changed": {
      const from = pickString(e.before, "name") ?? "—";
      const to = pickString(e.after, "name") ?? "—";
      return {
        headline: (
          <>
            <span className="font-semibold text-gray-700">Name updated</span>
            <span className="text-gray-500"> · {author}</span>
          </>
        ),
        detail: <span className="text-gray-500">{from} → {to}</span>,
      };
    }
    case "lead.phone_changed": {
      const from = pickString(e.before, "phone") ?? "—";
      const to = pickString(e.after, "phone") ?? "—";
      return {
        headline: (
          <>
            <span className="font-semibold text-gray-700">Phone updated</span>
            <span className="text-gray-500"> · {author}</span>
          </>
        ),
        detail: <span className="text-gray-500 font-mono text-[11px]">{from} → {to}</span>,
      };
    }
    case "lead.note_added": {
      const preview = pickString(e.after, "preview");
      return {
        headline: (
          <>
            <span className="font-semibold text-gray-700">Note added</span>
            <span className="text-gray-500"> · {author}</span>
          </>
        ),
        detail: preview ? <span className="text-gray-500 italic">“{preview}”</span> : null,
      };
    }
    case "lead.note_deleted": {
      const preview = pickString(e.before, "preview");
      return {
        headline: (
          <>
            <span className="font-semibold text-gray-700">Note deleted</span>
            <span className="text-gray-500"> · {author}</span>
          </>
        ),
        detail: preview ? <span className="text-gray-400 italic line-through">“{preview}”</span> : null,
      };
    }
    case "lead.call_logged": {
      const callType = pickString(e.after, "call_type");
      return {
        headline: (
          <>
            <span className="font-semibold text-gray-700">Call logged</span>
            <span className="text-gray-500"> · {author}</span>
          </>
        ),
        detail: callType
          ? <span className="text-gray-500">{callType} call</span>
          : null,
      };
    }
    case "lead.pushed_to_ghl": {
      // Outcome lives in after.status — color + headline depend on it.
      // status="ok" → green; "conflict_refused" → amber; "error" → red;
      // any "skipped_*" → grey (silent informational row).
      const pushStatus = pickString(e.after, "status") ?? "unknown";
      if (pushStatus === "ok") {
        const fieldsRaw = e.after?.fields;
        const fields = Array.isArray(fieldsRaw) ? fieldsRaw : [];
        return {
          headline: (
            <>
              <span className="font-semibold text-gray-700">Pushed to GHL</span>
              <span className="text-gray-500"> · {author}</span>
            </>
          ),
          detail: fields.length > 0
            ? <span className="text-gray-500">{fields.length} field{fields.length === 1 ? "" : "s"}</span>
            : null,
          dotColor: "#10B981", // green
        };
      }
      if (pushStatus === "conflict_refused") {
        return {
          headline: (
            <>
              <span className="font-semibold text-gray-700">GHL update refused</span>
              <span className="text-gray-500"> · {author}</span>
            </>
          ),
          detail: <span className="text-amber-700">GHL has newer data — sync first</span>,
          dotColor: "#F59E0B", // amber
        };
      }
      if (pushStatus === "error") {
        const reason = pickString(e.after, "reason");
        return {
          headline: (
            <>
              <span className="font-semibold text-gray-700">GHL push failed</span>
              <span className="text-gray-500"> · {author}</span>
            </>
          ),
          detail: reason ? <span className="text-red-700">{reason}</span> : null,
          dotColor: "#EF4444", // red
        };
      }
      // skipped_* statuses — render quietly so the user can see "no push because…"
      const skipReason = pushStatus.replace(/^skipped_/, "").replace(/_/g, " ");
      return {
        headline: (
          <>
            <span className="font-semibold text-gray-700">GHL push skipped</span>
            <span className="text-gray-500"> · {author}</span>
          </>
        ),
        detail: <span className="text-gray-400 italic">{skipReason}</span>,
        dotColor: "#9CA3AF", // grey
      };
    }
    default:
      return {
        headline: (
          <>
            <span className="font-semibold text-gray-700">{e.action}</span>
            <span className="text-gray-500"> · {author}</span>
          </>
        ),
        detail: null,
      };
  }
}

// ─── Page ────────────────────────────────────────────────────────────────────

export default function LeadDetailPage({ params }: { params: { lead_id: string } }) {
  const { isLoading: authLoading } = useAuth();
  const leadId = params.lead_id;

  const [detail, setDetail] = useState<LeadDetailResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [noteDraft, setNoteDraft] = useState("");
  const [isPostingNote, setIsPostingNote] = useState(false);
  const [pendingDeleteNoteId, setPendingDeleteNoteId] = useState<string | null>(null);
  const [isDeletingNote, setIsDeletingNote] = useState(false);
  const [showRawPayload, setShowRawPayload] = useState(false);
  const [isLoggingCall, setIsLoggingCall] = useState(false);

  // Filenames the user dropped in this session, keyed by call_id. We map
  // a freshly uploaded file to its returned call_id and render the name
  // on the in-progress row for as long as it's still processing. Other
  // tabs / reloads don't have this state — they fall back to
  // "{call_type} · {date}" on the row, which is fine.
  const [pendingFilenames, setPendingFilenames] = useState<Record<string, string>>({});
  // Filename the user just picked, before onSuccess returns a call_id.
  const lastDroppedFilenameRef = useRef<string | null>(null);

  const [history, setHistory] = useState<LeadHistoryEvent[]>([]);

  // Gmail thread sync state — Emails card.
  const [emailThreads, setEmailThreads] = useState<EmailThreadRow[]>([]);
  const [expandedThreadIds, setExpandedThreadIds] = useState<Set<string>>(new Set());
  const [isSyncingEmails, setIsSyncingEmails] = useState(false);

  // Drive documents — files where this lead's email is in shared_with.
  const [documents, setDocuments] = useState<DocumentRow[]>([]);
  const [isSyncingDocuments, setIsSyncingDocuments] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    try {
      const data = await apiClient.get<LeadDetailResponse>(`/leads/${leadId}`, {
        silent: true,
      });
      setDetail(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load lead.");
    } finally {
      setIsLoading(false);
    }
  }, [leadId]);

  const loadHistory = useCallback(async () => {
    // Fetched separately so the detail GET stays small and history can
    // refresh independently after edits/notes.
    try {
      const data = await apiClient.get<LeadHistoryResponse>(
        `/leads/${leadId}/history`,
        { silent: true },
      );
      setHistory(data.events);
    } catch {
      // History is a nice-to-have on this page; silently skip on error
      // rather than poisoning the whole detail render with an alert.
    }
  }, [leadId]);

  const loadEmails = useCallback(async () => {
    // Same pattern as loadHistory — best-effort, silent on error.
    try {
      const data = await apiClient.get<EmailThreadsResponse>(
        `/leads/${leadId}/emails`,
        { silent: true },
      );
      setEmailThreads(data.threads);
    } catch {
      // Gmail sync may not even be connected yet; degrade silently.
    }
  }, [leadId]);

  const loadDocuments = useCallback(async () => {
    try {
      const data = await apiClient.get<DocumentsResponse>(
        `/leads/${leadId}/documents`,
        { silent: true },
      );
      setDocuments(data.files);
    } catch {
      // Drive may not be connected yet; degrade silently.
    }
  }, [leadId]);

  useEffect(() => {
    if (authLoading) return;
    void load();
    void loadHistory();
    void loadEmails();
    void loadDocuments();
  }, [authLoading, load, loadHistory, loadEmails, loadDocuments]);

  // Poll the lead detail every 10s while at least one call is still being
  // analyzed. Once every call has processed_date set, the interval is
  // cleared and the page settles back to zero background work. Re-runs
  // when `detail` changes — including after our own poll lands fresh data.
  useEffect(() => {
    const hasPending = detail?.calls.some((c) => c.processed_date === null) ?? false;
    if (!hasPending) return;
    const id = setInterval(() => {
      void load();
    }, 10000);
    return () => clearInterval(id);
  }, [detail, load]);

  async function saveField(field: "name" | "phone" | "status", value: string | null) {
    const updated = await apiClient.patch<{
      id: string;
      name: string | null;
      email: string | null;
      phone: string | null;
      status: string | null;
      source: string | null;
      score: number;
      createdAt: string;
    }>(`/leads/${leadId}`, { [field]: value }, { silent: true });
    setDetail((d) =>
      d
        ? {
            ...d,
            name: updated.name,
            phone: updated.phone,
            status: updated.status,
            source: updated.source,
            score: updated.score,
          }
        : d,
    );
    void loadHistory();
  }

  async function postNote() {
    const body = noteDraft.trim();
    if (body === "") return;
    setIsPostingNote(true);
    try {
      const note = await apiClient.post<NoteRow>(
        `/leads/${leadId}/notes`,
        { body },
        { silent: true },
      );
      setDetail((d) => (d ? { ...d, staff_notes: [note, ...d.staff_notes] } : d));
      setNoteDraft("");
      showSuccess("Note added.");
      void loadHistory();
    } catch (err) {
      showError(err instanceof Error ? err.message : "Failed to post note.");
    } finally {
      setIsPostingNote(false);
    }
  }

  async function confirmDeleteNote() {
    const noteId = pendingDeleteNoteId;
    if (!noteId) return;
    setIsDeletingNote(true);
    try {
      await apiClient.delete(`/leads/${leadId}/notes/${noteId}`, { silent: true });
      setDetail((d) =>
        d ? { ...d, staff_notes: d.staff_notes.filter((n) => n.id !== noteId) } : d,
      );
      void loadHistory();
    } catch (err) {
      showError(err instanceof Error ? err.message : "Delete failed.");
    } finally {
      setIsDeletingNote(false);
      setPendingDeleteNoteId(null);
    }
  }

  // ─── Render ─────────────────────────────────────────────────────────────────

  if (isLoading) {
    return (
      <>
        <Header title="Lead detail" />
        <main className="flex-1 overflow-y-auto p-7">
          <p className="text-[15px] text-gray-400">Loading…</p>
        </main>
      </>
    );
  }

  if (error || detail === null) {
    return (
      <>
        <Header title="Lead detail" />
        <main className="flex-1 overflow-y-auto p-7 space-y-4">
          <Link
            href="/leads"
            className="text-[13px] font-medium text-indigo-600 hover:text-indigo-700 underline underline-offset-2"
          >
            ← Back to leads
          </Link>
          <p className="text-[15px] text-red-700">{error ?? "Lead not found."}</p>
        </main>
      </>
    );
  }

  const status = resolveStatus(detail.status);
  const source = resolveSource(detail.source);
  const submission = parseSubmission(detail.notes_raw);

  const hasActivity =
    detail.calls.length > 0 ||
    detail.goals.length > 0 ||
    detail.pain_points.length > 0 ||
    detail.objections.length > 0;

  // Any call still being transcribed/analyzed disables the Log-call button —
  // avoids confusion about which in-progress row belongs to the next upload.
  const hasPendingCall = detail.calls.some((c) => c.processed_date === null);

  function handleCallLogged(result: { callId?: string; status?: string }) {
    // Backend returns "duplicate" when the file's SHA-256 matches an
    // existing call — no new row, no audit emit, no link to this lead.
    // Warn the user instead of pretending a call was logged. Keep the
    // upload widget mounted so they can pick a different file.
    if (result.status === "duplicate") {
      const callRef = result.callId ? ` (${result.callId})` : "";
      showWarning(
        `This recording was already uploaded${callRef}. It may be linked to a different lead — open the Sales calls list to find it.`,
      );
      lastDroppedFilenameRef.current = null;
      return;
    }

    setIsLoggingCall(false);
    showSuccess("Call logged. Analyzing transcript in the background…");
    // Pin the dropped filename to the call_id so the in-progress row
    // shows the file the user just picked. Other tabs / fresh sessions
    // don't have this and fall back to "{call_type} · {date}".
    const filename = lastDroppedFilenameRef.current;
    if (result.callId && filename) {
      setPendingFilenames((m) => ({ ...m, [result.callId as string]: filename }));
    }
    lastDroppedFilenameRef.current = null;
    void load();
    void loadHistory();
  }

  async function syncEmails() {
    if (isSyncingEmails) return;
    setIsSyncingEmails(true);
    try {
      await apiClient.post(`/leads/${leadId}/sync-emails`, {}, { silent: true });
      showSuccess("Email sync queued. Refreshing in a few seconds…");
      // Give Celery a chance to drain a quick mailbox, then refetch.
      // For larger mailboxes the user can refresh manually.
      setTimeout(() => {
        void loadEmails();
        setIsSyncingEmails(false);
      }, 5000);
    } catch (err) {
      showError(err instanceof Error ? err.message : "Failed to start email sync.");
      setIsSyncingEmails(false);
    }
  }

  async function syncDocuments() {
    if (isSyncingDocuments) return;
    setIsSyncingDocuments(true);
    try {
      await apiClient.post(`/leads/${leadId}/sync-documents`, {}, { silent: true });
      showSuccess("Document sync queued. Refreshing in a few seconds…");
      // Drive sweeps can be slow; just give the worker a head start.
      setTimeout(() => {
        void loadDocuments();
        setIsSyncingDocuments(false);
      }, 5000);
    } catch (err) {
      showError(err instanceof Error ? err.message : "Failed to start document sync.");
      setIsSyncingDocuments(false);
    }
  }

  function toggleThread(threadId: string) {
    setExpandedThreadIds((prev) => {
      const next = new Set(prev);
      if (next.has(threadId)) next.delete(threadId);
      else next.add(threadId);
      return next;
    });
  }

  return (
    <>
      <Header title="Lead detail" />

      <main className="flex-1 overflow-y-auto p-7 space-y-6">
        {/* Back link */}
        <Link
          href="/leads"
          className="inline-block text-[13px] font-medium text-indigo-600 hover:text-indigo-700 underline underline-offset-2"
        >
          ← Back to leads
        </Link>

        {/* Heading */}
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div className="min-w-0">
            <h1 className="text-[22px] font-bold text-gray-900">
              <InlineTextEdit
                value={detail.name}
                placeholder="Lead name"
                emptyLabel="Unnamed lead"
                inputClassName="text-[22px] font-bold min-w-[280px]"
                onSave={(v) => saveField("name", v)}
              />
            </h1>
            <p className="text-[13px] text-gray-500 mt-0.5 font-mono">{detail.id}</p>
          </div>
          <span
            className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[12px] font-semibold ${status.badgeClasses}`}
          >
            <span
              className="w-1.5 h-1.5 rounded-full"
              style={{ backgroundColor: status.dotColor }}
            />
            {status.label}
          </span>
        </div>

        {/* Two-column: Contact + Status/Score */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          {/* Contact card */}
          <Card>
            <CardHeader title="Contact" />
            <CardBody>
              <dl className="space-y-3 text-[13px]">
                <div className="flex items-baseline gap-2">
                  <dt className="w-20 text-[11px] font-bold uppercase tracking-wider text-gray-500 shrink-0">
                    Email
                  </dt>
                  <dd className="text-gray-700">
                    {detail.email && detail.email.trim() !== "" ? (
                      <a
                        href={`mailto:${detail.email}`}
                        className="text-indigo-600 hover:text-indigo-700 underline underline-offset-2"
                      >
                        {detail.email}
                      </a>
                    ) : (
                      <span className="text-gray-400 italic">—</span>
                    )}
                  </dd>
                </div>
                <div className="flex items-baseline gap-2">
                  <dt className="w-20 text-[11px] font-bold uppercase tracking-wider text-gray-500 shrink-0">
                    Phone
                  </dt>
                  <dd className="text-gray-700">
                    <InlineTextEdit
                      value={detail.phone}
                      placeholder="+1 555 555 5555"
                      emptyLabel="Add phone"
                      inputClassName="text-[13px]"
                      onSave={(v) => saveField("phone", v)}
                    />
                  </dd>
                </div>
                <div className="flex items-baseline gap-2">
                  <dt className="w-20 text-[11px] font-bold uppercase tracking-wider text-gray-500 shrink-0">
                    Source
                  </dt>
                  <dd>
                    <span
                      className={`inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold ${source.badgeClasses}`}
                    >
                      {source.label}
                    </span>
                  </dd>
                </div>
                <div className="flex items-baseline gap-2">
                  <dt className="w-20 text-[11px] font-bold uppercase tracking-wider text-gray-500 shrink-0">
                    Created
                  </dt>
                  <dd className="text-gray-700">{formatDate(detail.created_at)}</dd>
                </div>
                {detail.external_id && (
                  <div className="flex items-baseline gap-2">
                    <dt className="w-20 text-[11px] font-bold uppercase tracking-wider text-gray-500 shrink-0">
                      Ext ID
                    </dt>
                    <dd className="text-gray-500 font-mono text-[12px]">{detail.external_id}</dd>
                  </div>
                )}
              </dl>
            </CardBody>
          </Card>

          {/* Status + Score card */}
          <Card>
            <CardHeader title="Status & Score" />
            <CardBody className="space-y-4">
              <FormField label="Lead status">
                <FormSelect
                  value={detail.status ?? ""}
                  onChange={(e) => void saveField("status", e.target.value)}
                >
                  {STATUS_OPTIONS.map((s) => (
                    <option key={s} value={s}>
                      {STATUS_CONFIG[s].label}
                    </option>
                  ))}
                  {/* Preserve any unknown DB status the backend returned */}
                  {detail.status && !STATUS_OPTIONS.includes(detail.status as LeadStatus) && (
                    <option value={detail.status}>{_humanise(detail.status)}</option>
                  )}
                </FormSelect>
              </FormField>
              <div>
                <label className="text-[11px] font-bold uppercase tracking-wider text-gray-500 block mb-1.5">
                  Score
                </label>
                <ScoreBar value={detail.score} />
                <p className="text-[11px] text-gray-400 mt-1.5">
                  Auto-derived from status.
                </p>
              </div>
            </CardBody>
          </Card>
        </div>

        {/* Initial Submission */}
        {submission && (
          <Card>
            <CardHeader
              title="Initial Submission"
              action={
                <span className="text-[11px] text-gray-400">
                  Original payload from {resolveSource(detail.source).label}
                </span>
              }
            />
            <CardBody>
              {submission.fields.length > 0 ? (
                <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-3 text-[13px]">
                  {submission.fields.map((f) => (
                    <div key={f.label} className="flex flex-col gap-0.5 min-w-0">
                      <dt className="text-[11px] font-bold uppercase tracking-wider text-gray-500">
                        {f.label}
                      </dt>
                      <dd className="text-gray-700 break-words">{f.value}</dd>
                    </div>
                  ))}
                </dl>
              ) : (
                <p className="text-[13px] text-gray-400 italic">
                  Couldn&apos;t parse the original submission. See &ldquo;Source payload&rdquo; below.
                </p>
              )}
            </CardBody>
          </Card>
        )}

        {/* Staff notes timeline */}
        <Card>
          <CardHeader
            title="Staff notes"
            action={
              <span className="text-[11px] text-gray-400">
                {detail.staff_notes.length}
              </span>
            }
          />
          <CardBody className="space-y-4">
            <div className="space-y-2">
              <FormTextarea
                rows={3}
                value={noteDraft}
                onChange={(e) => setNoteDraft(e.target.value)}
                placeholder="Add a note — a call-back reminder, an observation, a follow-up plan…"
                disabled={isPostingNote}
                className="w-full"
                onKeyDown={(e) => {
                  if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
                    e.preventDefault();
                    void postNote();
                  }
                }}
              />
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => void postNote()}
                  disabled={isPostingNote || noteDraft.trim() === ""}
                  className="text-[13px] font-medium px-3 py-1.5 rounded-lg bg-indigo-500 hover:bg-indigo-600 disabled:bg-indigo-200 disabled:cursor-not-allowed text-white transition-colors"
                >
                  {isPostingNote ? "Posting…" : "Post note"}
                </button>
                <span className="text-[11px] text-gray-400">⌘+Enter posts</span>
              </div>
            </div>

            {detail.staff_notes.length > 0 ? (
              <ul className="divide-y divide-gray-100 -mx-5">
                {detail.staff_notes.map((n) => (
                  <li key={n.id} className="px-5 py-3 group">
                    <div className="flex items-baseline gap-2 text-[11px] text-gray-500 mb-1">
                      <span className="font-semibold text-gray-700">
                        {n.author_email ?? "—"}
                      </span>
                      <span title={formatDate(n.created_at)}>
                        · {relativeTime(n.created_at)}
                      </span>
                      <button
                        type="button"
                        onClick={() => setPendingDeleteNoteId(n.id)}
                        className="ml-auto text-[11px] text-red-500 hover:text-red-700 opacity-0 group-hover:opacity-100 focus:opacity-100 transition-opacity"
                        title="Delete this note"
                      >
                        Delete
                      </button>
                    </div>
                    <p className="text-[14px] text-gray-700 whitespace-pre-wrap leading-relaxed">
                      {n.body}
                    </p>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-[13px] text-gray-400 italic">
                No notes yet. Add one above.
              </p>
            )}
          </CardBody>
        </Card>

        {/* Emails — Gmail threads where this lead's email appears.
            Threads collapsed by default; click to expand the message list.
            Plain-text bodies only; attachments rendered as metadata chips.
            Only rendered when the lead has an email AND we've synced
            something — empty state is shown when the lead has an email
            but no threads have been found yet. */}
        {detail.email && (
          <Card>
            <CardHeader
              title="Emails"
              action={
                <div className="flex items-center gap-3">
                  <span className="text-[11px] text-gray-400">
                    {emailThreads.length} thread{emailThreads.length === 1 ? "" : "s"}
                  </span>
                  <button
                    type="button"
                    onClick={() => void syncEmails()}
                    disabled={isSyncingEmails}
                    className="text-[12px] font-semibold px-3 py-1.5 rounded-lg bg-indigo-500 hover:bg-indigo-600 disabled:bg-gray-300 disabled:cursor-not-allowed text-white transition-colors"
                  >
                    {isSyncingEmails ? "Syncing…" : "Sync emails now"}
                  </button>
                </div>
              }
            />
            <CardBody noPadding>
              {emailThreads.length === 0 ? (
                <p className="px-5 py-4 text-[13px] text-gray-400 italic">
                  No email threads on file. Click <b>Sync emails now</b> if Google Workspace is connected and this lead has been in correspondence.
                </p>
              ) : (
                <HistoryList className="py-1">
                  {emailThreads.map((thread) => {
                    const isExpanded = expandedThreadIds.has(thread.id);
                    const firstMsg = thread.messages[0];
                    const latestParticipants = firstMsg
                      ? [firstMsg.from_address, ...firstMsg.to_addresses]
                          .filter((s): s is string => Boolean(s))
                          .slice(0, 2)
                          .join(", ")
                      : "";
                    return (
                      <div key={thread.id}>
                        <HistoryItem
                          dotColor={isExpanded ? "#6366F1" : "#9CA3AF"}
                          trailing={
                            <span
                              className="text-[11px] text-gray-400"
                              title={thread.last_message_at ? formatDate(thread.last_message_at) : undefined}
                            >
                              {thread.last_message_at ? relativeTime(thread.last_message_at) : "—"}
                            </span>
                          }
                        >
                          <button
                            type="button"
                            onClick={() => toggleThread(thread.id)}
                            className="block w-full text-left"
                            aria-expanded={isExpanded}
                          >
                            <div className="flex items-center gap-2 text-[13px]">
                              <span className="text-gray-500 inline-block w-3">{isExpanded ? "▾" : "▸"}</span>
                              <span className="font-semibold text-gray-700 truncate">
                                {thread.subject || "(no subject)"}
                              </span>
                              <span className="text-[11px] text-gray-400 ml-auto">
                                {thread.message_count} msg{thread.message_count === 1 ? "" : "s"}
                              </span>
                            </div>
                            {latestParticipants && (
                              <div className="text-[11px] text-gray-500 mt-0.5 ml-5 truncate">
                                {latestParticipants}
                              </div>
                            )}
                          </button>
                        </HistoryItem>
                        {isExpanded && (
                          <div className="bg-gray-50 border-t border-gray-100 px-5 py-3 space-y-3">
                            {thread.messages.length === 0 ? (
                              <p className="text-[12px] text-gray-400 italic">No messages on this thread yet.</p>
                            ) : (
                              thread.messages.map((m) => (
                                <div
                                  key={m.id}
                                  className="bg-white rounded-lg border border-gray-200 px-3 py-2.5 text-[13px]"
                                >
                                  <div className="flex items-baseline gap-2 text-[11px] text-gray-500">
                                    <span className="font-semibold text-gray-700">
                                      {m.from_address || "—"}
                                    </span>
                                    {m.to_addresses.length > 0 && (
                                      <span>→ {m.to_addresses.join(", ")}</span>
                                    )}
                                    <span
                                      className="ml-auto"
                                      title={m.sent_at ? formatDate(m.sent_at) : undefined}
                                    >
                                      {m.sent_at ? relativeTime(m.sent_at) : "—"}
                                    </span>
                                  </div>
                                  {m.body_text ? (
                                    <pre className="mt-1.5 text-[12px] text-gray-700 whitespace-pre-wrap font-sans leading-relaxed max-h-64 overflow-y-auto">
                                      {m.body_text}
                                    </pre>
                                  ) : (
                                    <p className="mt-1.5 text-[11px] text-gray-400 italic">
                                      (no plain-text body — HTML emails aren&apos;t rendered)
                                    </p>
                                  )}
                                  {m.attachments_meta.length > 0 && (
                                    <div className="mt-2 flex flex-wrap gap-1.5">
                                      {m.attachments_meta.map((a, i) => (
                                        <span
                                          key={i}
                                          className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] bg-gray-100 text-gray-600 border border-gray-200"
                                          title={a.mime_type || undefined}
                                        >
                                          📎 {a.filename}
                                          {a.size > 0 && (
                                            <span className="text-gray-400">
                                              · {Math.round(a.size / 1024)} KB
                                            </span>
                                          )}
                                        </span>
                                      ))}
                                    </div>
                                  )}
                                </div>
                              ))
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </HistoryList>
              )}
            </CardBody>
          </Card>
        )}

        {/* Documents — Drive files where this lead's email is in the file's
            sharing permissions. Populated by the Drive sync task; sweeps
            every connected user's Drive and dedupes by provider_file_id.
            Only rendered when the lead has an email — without one we have
            no key to match against shared_with. */}
        {detail.email && (
          <Card>
            <CardHeader
              title="Documents"
              action={
                <div className="flex items-center gap-3">
                  <span className="text-[11px] text-gray-400">
                    {documents.length} file{documents.length === 1 ? "" : "s"}
                  </span>
                  <button
                    type="button"
                    onClick={() => void syncDocuments()}
                    disabled={isSyncingDocuments}
                    className="text-[12px] font-semibold px-3 py-1.5 rounded-lg bg-indigo-500 hover:bg-indigo-600 disabled:bg-gray-300 disabled:cursor-not-allowed text-white transition-colors"
                  >
                    {isSyncingDocuments ? "Syncing…" : "Sync documents now"}
                  </button>
                </div>
              }
            />
            <CardBody noPadding>
              {documents.length === 0 ? (
                <p className="px-5 py-4 text-[13px] text-gray-400 italic">
                  No documents shared with this lead. Click <b>Sync documents now</b> if Google Workspace is connected.
                </p>
              ) : (
                <HistoryList className="py-1">
                  {documents.map((doc) => (
                    <HistoryItem
                      key={doc.id}
                      dotColor="#0EA5E9"
                      trailing={
                        <span
                          className="text-[11px] text-gray-400"
                          title={doc.modified_time ? formatDate(doc.modified_time) : undefined}
                        >
                          {doc.modified_time ? relativeTime(doc.modified_time) : "—"}
                        </span>
                      }
                    >
                      <a
                        href={doc.web_view_link || "#"}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="block text-left hover:underline"
                      >
                        <div className="flex items-center gap-2 text-[13px]">
                          <span aria-hidden>{mimeIcon(doc.mime_type)}</span>
                          <span className="font-semibold text-gray-700 truncate">
                            {doc.name || "(untitled)"}
                          </span>
                        </div>
                        <div className="text-[11px] text-gray-500 mt-0.5 ml-5 truncate">
                          {doc.parent_folder_name ? `${doc.parent_folder_name} · ` : ""}
                          {doc.owner_email || "—"}
                          {doc.size_bytes ? ` · ${Math.round(doc.size_bytes / 1024)} KB` : ""}
                        </div>
                      </a>
                    </HistoryItem>
                  ))}
                </HistoryList>
              )}
            </CardBody>
          </Card>
        )}

        {/* Activity timeline — always rendered so the Log call button has a
            home, even on brand-new leads with no FK rows yet. When
            isLoggingCall, the card body swaps to the upload widget so a
            long-running upload (whisper is CPU-bound; 50MB ≈ 30 min) lives
            in the page and can't disappear behind a stray click. */}
        <Card>
          <CardHeader
            title={isLoggingCall ? "Log a call" : "Activity"}
            action={
              isLoggingCall ? (
                <button
                  type="button"
                  onClick={() => setIsLoggingCall(false)}
                  className="text-[12px] font-semibold px-3 py-1.5 rounded-lg border border-gray-300 text-gray-600 hover:bg-gray-50 transition-colors"
                >
                  Cancel
                </button>
              ) : (
                <button
                  type="button"
                  onClick={() => setIsLoggingCall(true)}
                  disabled={hasPendingCall}
                  title={hasPendingCall ? "A call is currently being processed" : undefined}
                  className="text-[12px] font-semibold px-3 py-1.5 rounded-lg bg-indigo-500 hover:bg-indigo-600 disabled:bg-gray-300 disabled:cursor-not-allowed text-white transition-colors"
                >
                  Log call
                </button>
              )
            }
          />
          {isLoggingCall ? (
            <CardBody>
              <p className="text-[12px] text-gray-500 mb-3">
                Upload the recording. We&apos;ll transcribe it and run the
                analyzer automatically. Stay on this page until the upload
                completes — transcription takes roughly as long as the
                recording itself.
              </p>
              <TranscriptUploadWidget
                leadId={detail.id}
                callType="Sales"
                onSuccess={handleCallLogged}
                onFileSelected={(name) => {
                  lastDroppedFilenameRef.current = name;
                }}
              />
            </CardBody>
          ) : (
          <CardBody className="space-y-5">
            {!hasActivity && (
              <p className="text-[13px] text-gray-400 italic">
                No activity yet. Log a call to get started.
              </p>
            )}
            {detail.calls.length > 0 && (
                <section>
                  <h3 className="text-[11px] font-bold uppercase tracking-wider text-gray-500 mb-2">
                    Calls
                  </h3>
                  <ul className="divide-y divide-gray-100 border border-gray-100 rounded-lg overflow-hidden">
                    {detail.calls.map((c) => {
                      // processed_date === null while the analyzer is still
                      // running. Show a pending row with an indeterminate
                      // bar — no link yet (the call detail page is mostly
                      // empty until insights/summary land).
                      if (c.processed_date === null) {
                        const label =
                          pendingFilenames[c.id]
                          ?? `${c.call_type ?? "Call"} · ${formatDate(c.date)}`;
                        return (
                          <li key={c.id} className="px-4 py-2.5 text-[13px]">
                            <div className="flex items-center justify-between gap-3">
                              <span className="text-gray-700 truncate">{label}</span>
                              <span className="text-[11px] font-semibold text-amber-700 shrink-0">
                                Processing…
                              </span>
                            </div>
                            <div className="mt-2 h-1 rounded-full bg-gray-100 overflow-hidden">
                              <div className="h-full w-1/3 bg-gradient-to-r from-indigo-300 via-indigo-500 to-indigo-300 animate-pulse rounded-full" />
                            </div>
                          </li>
                        );
                      }
                      return (
                        <li
                          key={c.id}
                          className="px-4 py-2.5 flex items-center justify-between text-[13px]"
                        >
                          <Link
                            href={`/sales-calls/${c.id}`}
                            className="text-indigo-600 hover:text-indigo-700"
                          >
                            {c.call_type ?? "Call"} — {formatDate(c.date)}
                          </Link>
                          <span className="text-[11px] text-gray-400">
                            {c.insights_count} insight{c.insights_count === 1 ? "" : "s"}
                          </span>
                        </li>
                      );
                    })}
                  </ul>
                </section>
              )}
              {detail.goals.length > 0 && (
                <section>
                  <h3 className="text-[11px] font-bold uppercase tracking-wider text-gray-500 mb-2">
                    Goals
                  </h3>
                  <ul className="divide-y divide-gray-100 border border-gray-100 rounded-lg overflow-hidden">
                    {detail.goals.map((g) => (
                      <li key={g.id} className="px-4 py-2.5 text-[13px]">
                        <div className="text-gray-700">{g.goal_text ?? "—"}</div>
                        <div className="text-[11px] text-gray-400 mt-0.5">
                          {g.status ?? "no status"}
                          {g.target_date ? ` · target ${g.target_date}` : ""}
                        </div>
                      </li>
                    ))}
                  </ul>
                </section>
              )}
              {detail.pain_points.length > 0 && (
                <section>
                  <h3 className="text-[11px] font-bold uppercase tracking-wider text-gray-500 mb-2">
                    Pain points
                  </h3>
                  <ul className="divide-y divide-gray-100 border border-gray-100 rounded-lg overflow-hidden">
                    {detail.pain_points.map((p) => (
                      <li key={p.id} className="px-4 py-2.5 text-[13px]">
                        <div className="text-gray-700">{p.text ?? "—"}</div>
                        {p.category && (
                          <div className="text-[11px] text-gray-400 mt-0.5">{p.category}</div>
                        )}
                      </li>
                    ))}
                  </ul>
                </section>
              )}
              {detail.objections.length > 0 && (
                <section>
                  <h3 className="text-[11px] font-bold uppercase tracking-wider text-gray-500 mb-2">
                    Objections
                  </h3>
                  <ul className="divide-y divide-gray-100 border border-gray-100 rounded-lg overflow-hidden">
                    {detail.objections.map((o) => (
                      <li key={o.id} className="px-4 py-2.5 text-[13px]">
                        <div className="text-gray-700">{o.objection_text ?? "—"}</div>
                        {o.resolution_offered && (
                          <div className="text-[11px] text-gray-500 mt-0.5">
                            Resolution: {o.resolution_offered}
                          </div>
                        )}
                      </li>
                    ))}
                  </ul>
                </section>
              )}
          </CardBody>
          )}
        </Card>

        {/* History — audit-log timeline */}
        {history.length > 0 && (
          <Card>
            <CardHeader
              title="History"
              action={<span className="text-[11px] text-gray-400">{history.length}</span>}
            />
            <CardBody noPadding>
              <HistoryList className="py-1">
                {history.map((e) => {
                  const { headline, detail: detailNode, dotColor: dotOverride } = describeHistoryEvent(e);
                  return (
                    <HistoryItem
                      key={e.id}
                      dotColor={dotOverride ?? HISTORY_DOT_COLORS[e.action] ?? "#9CA3AF"}
                      trailing={
                        <span
                          className="text-[11px] text-gray-400"
                          title={formatDate(e.created_at)}
                        >
                          {relativeTime(e.created_at)}
                        </span>
                      }
                    >
                      <div className="text-[13px]">{headline}</div>
                      {detailNode && <div className="text-[12px] mt-0.5">{detailNode}</div>}
                    </HistoryItem>
                  );
                })}
              </HistoryList>
            </CardBody>
          </Card>
        )}

        {/* Source payload — collapsible raw JSON */}
        {detail.notes_raw && (
          <Card>
            <CardHeader
              title="Source payload"
              action={
                <button
                  type="button"
                  onClick={() => setShowRawPayload((v) => !v)}
                  className="text-[12px] font-medium text-indigo-600 hover:text-indigo-700"
                >
                  {showRawPayload ? "Hide" : "Show"}
                </button>
              }
            />
            {showRawPayload && (
              <CardBody noPadding>
                <pre className="px-5 py-4 text-[12px] text-gray-600 bg-gray-50 whitespace-pre-wrap font-mono leading-relaxed max-h-96 overflow-y-auto">
                  {(() => {
                    try {
                      return JSON.stringify(JSON.parse(detail.notes_raw), null, 2);
                    } catch {
                      return detail.notes_raw;
                    }
                  })()}
                </pre>
              </CardBody>
            )}
          </Card>
        )}
      </main>

      <ConfirmDialog
        open={pendingDeleteNoteId !== null}
        onClose={() => setPendingDeleteNoteId(null)}
        onConfirm={() => void confirmDeleteNote()}
        title="Delete this note?"
        description="This cannot be undone."
        confirmLabel="Delete"
        variant="danger"
        loading={isDeletingNote}
      />
    </>
  );
}
