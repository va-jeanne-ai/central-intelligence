"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { apiClient } from "@/lib/api-client";
import { showSuccess, showApiError } from "@/lib/toast";

// ─── Shared option lists ──────────────────────────────────────────────────────

export const TICKET_CATEGORIES = ["login", "billing", "video", "portal", "access", "other"] as const;
export const TICKET_STATUSES = ["open", "in_progress", "resolved", "closed"] as const;
export const TICKET_PRIORITIES = ["low", "normal", "high"] as const;

export interface TicketModalTicket {
  id: string;
  subject: string | null;
  description?: string | null;
  category: string | null;
  status: string | null;
  priority: string | null;
  resolution?: string | null;
}

interface MemberOption {
  id: string;
  name: string | null;
  email: string | null;
}

interface TicketModalProps {
  open: boolean;
  onClose: () => void;
  onSaved: () => void;
  /** When set, the ticket is edited (PATCH); otherwise created (POST). */
  ticket?: TicketModalTicket | null;
  /** When set, member is locked (member-detail context). */
  memberId?: string;
}

function humanise(v: string): string {
  return v.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function TicketModal({ open, onClose, onSaved, ticket, memberId }: TicketModalProps) {
  const isEdit = Boolean(ticket);
  const needsMemberPicker = !isEdit && !memberId;

  const [subject, setSubject] = useState("");
  const [description, setDescription] = useState("");
  const [category, setCategory] = useState<string>("other");
  const [priority, setPriority] = useState<string>("normal");
  const [status, setStatus] = useState<string>("open");
  const [resolution, setResolution] = useState("");
  const [selectedMember, setSelectedMember] = useState("");
  const [members, setMembers] = useState<MemberOption[]>([]);
  const [membersLoading, setMembersLoading] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open) return;
    setSubject(ticket?.subject ?? "");
    setDescription(ticket?.description ?? "");
    setCategory(ticket?.category ?? "other");
    setPriority(ticket?.priority ?? "normal");
    setStatus(ticket?.status ?? "open");
    setResolution(ticket?.resolution ?? "");
    setSelectedMember("");
    setSaving(false);

    // The list row doesn't carry description/resolution — fetch the full
    // ticket so editing doesn't blank them on save.
    if (ticket && (ticket.description === undefined || ticket.resolution === undefined)) {
      void (async () => {
        try {
          const full = await apiClient.get<{ description: string | null; resolution: string | null }>(
            `/tech-sos/${ticket.id}`,
            { silent: true },
          );
          setDescription(full.description ?? "");
          setResolution(full.resolution ?? "");
        } catch {
          // leave as-is; PATCH still updates the fields the user touched
        }
      })();
    }
  }, [open, ticket]);

  useEffect(() => {
    if (!open || !needsMemberPicker) return;
    let cancelled = false;
    setMembersLoading(true);
    void (async () => {
      try {
        const data = await apiClient.get<{ members: MemberOption[] }>(
          "/members?per_page=200&sort_by=name&sort_dir=asc",
          { silent: true },
        );
        if (!cancelled) setMembers(data.members ?? []);
      } catch {
        if (!cancelled) setMembers([]);
      } finally {
        if (!cancelled) setMembersLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [open, needsMemberPicker]);

  if (!open) return null;

  async function submit() {
    if (subject.trim() === "") {
      showApiError("Subject is required");
      return;
    }
    setSaving(true);
    try {
      if (isEdit && ticket) {
        await apiClient.patch(`/tech-sos/${ticket.id}`, {
          subject: subject.trim(),
          description: description.trim() || null,
          category,
          priority,
          status,
          resolution: resolution.trim() || null,
        });
        showSuccess("Ticket updated");
      } else {
        await apiClient.post("/tech-sos", {
          subject: subject.trim(),
          description: description.trim() || null,
          member_id: (memberId ?? selectedMember) || null,
          category,
          priority,
        });
        showSuccess("Ticket created");
      }
      onSaved();
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
      aria-label={isEdit ? "Edit ticket" : "New ticket"}
      onClick={onClose}
    >
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md p-6" onClick={(e) => e.stopPropagation()}>
        <h2 className="text-base font-bold text-gray-900">{isEdit ? "Edit Ticket" : "New Ticket"}</h2>
        <p className="text-xs text-gray-500 mt-0.5">
          {isEdit ? "Update status, category, and resolution." : "Log a tech-support issue for a member."}
        </p>

        <div className="mt-4 space-y-3">
          {needsMemberPicker && (
            <label className="block">
              <span className="text-[11px] font-bold uppercase tracking-widest text-gray-400">Member</span>
              <select
                value={selectedMember}
                onChange={(e) => setSelectedMember(e.target.value)}
                disabled={membersLoading}
                className="mt-1 w-full text-sm border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-orange-300 disabled:bg-gray-50"
              >
                <option value="">{membersLoading ? "Loading members…" : "Unassigned / select a member…"}</option>
                {members.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.name || m.email || m.id}
                    {m.name && m.email ? ` (${m.email})` : ""}
                  </option>
                ))}
              </select>
            </label>
          )}
          <label className="block">
            <span className="text-[11px] font-bold uppercase tracking-widest text-gray-400">Subject *</span>
            <input
              type="text"
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              autoFocus
              className="mt-1 w-full text-sm border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-orange-300"
            />
          </label>
          <label className="block">
            <span className="text-[11px] font-bold uppercase tracking-widest text-gray-400">Description</span>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={2}
              className="mt-1 w-full text-sm border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-orange-300 resize-none"
            />
          </label>
          <div className="grid grid-cols-2 gap-3">
            <label className="block">
              <span className="text-[11px] font-bold uppercase tracking-widest text-gray-400">Category</span>
              <select
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                className="mt-1 w-full text-sm border border-gray-300 rounded-md px-2 py-2 focus:outline-none focus:ring-2 focus:ring-orange-300"
              >
                {TICKET_CATEGORIES.map((c) => (
                  <option key={c} value={c}>{humanise(c)}</option>
                ))}
              </select>
            </label>
            <label className="block">
              <span className="text-[11px] font-bold uppercase tracking-widest text-gray-400">Priority</span>
              <select
                value={priority}
                onChange={(e) => setPriority(e.target.value)}
                className="mt-1 w-full text-sm border border-gray-300 rounded-md px-2 py-2 focus:outline-none focus:ring-2 focus:ring-orange-300"
              >
                {TICKET_PRIORITIES.map((p) => (
                  <option key={p} value={p}>{humanise(p)}</option>
                ))}
              </select>
            </label>
          </div>
          {isEdit && (
            <>
              <label className="block">
                <span className="text-[11px] font-bold uppercase tracking-widest text-gray-400">Status</span>
                <select
                  value={status}
                  onChange={(e) => setStatus(e.target.value)}
                  className="mt-1 w-full text-sm border border-gray-300 rounded-md px-2 py-2 focus:outline-none focus:ring-2 focus:ring-orange-300"
                >
                  {TICKET_STATUSES.map((s) => (
                    <option key={s} value={s}>{humanise(s)}</option>
                  ))}
                </select>
              </label>
              <label className="block">
                <span className="text-[11px] font-bold uppercase tracking-widest text-gray-400">Resolution</span>
                <textarea
                  value={resolution}
                  onChange={(e) => setResolution(e.target.value)}
                  rows={2}
                  placeholder="How it was resolved…"
                  className="mt-1 w-full text-sm border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-orange-300 resize-none"
                />
              </label>
            </>
          )}
        </div>

        <div className="mt-6 flex justify-end gap-2">
          <Button variant="ghost" size="sm" onClick={onClose} disabled={saving}>
            Cancel
          </Button>
          <Button variant="primary" size="sm" onClick={() => void submit()} disabled={saving || subject.trim() === ""}>
            {saving ? "Saving…" : isEdit ? "Save Ticket" : "Create Ticket"}
          </Button>
        </div>
      </div>
    </div>
  );
}
