"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { apiClient } from "@/lib/api-client";
import { showSuccess, showApiError } from "@/lib/toast";

// ─── Types ───────────────────────────────────────────────────────────────────

export type GoalStatus = "active" | "completed" | "abandoned";

export interface GoalModalGoal {
  id: string;
  goal_text: string | null;
  status: string | null;
  /** ISO date for target_date (may be full datetime or date). */
  targetDate?: string | null;
  target_date?: string | null;
}

interface GoalModalProps {
  open: boolean;
  onClose: () => void;
  onSaved: () => void;
  /** When set, the goal is edited (PATCH); otherwise created (POST). */
  goal?: GoalModalGoal | null;
  /** When set, member is locked (member-detail context). Otherwise the user
   *  must supply a member id (accountability context). */
  memberId?: string;
}

const STATUS_OPTIONS: GoalStatus[] = ["active", "completed", "abandoned"];

interface MemberOption {
  id: string;
  name: string | null;
  email: string | null;
}

/** Normalize an ISO timestamp to a yyyy-mm-dd value for <input type="date">. */
function toDateInput(iso: string | null | undefined): string {
  if (!iso) return "";
  return iso.slice(0, 10);
}

export function GoalModal({ open, onClose, onSaved, goal, memberId }: GoalModalProps) {
  const isEdit = Boolean(goal);
  // The member <select> is only needed when creating a goal without a locked
  // member (the accountability context).
  const needsMemberPicker = !isEdit && !memberId;

  const [goalText, setGoalText] = useState("");
  const [status, setStatus] = useState<GoalStatus>("active");
  const [targetDate, setTargetDate] = useState("");
  const [selectedMember, setSelectedMember] = useState("");
  const [members, setMembers] = useState<MemberOption[]>([]);
  const [membersLoading, setMembersLoading] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open) return;
    setGoalText(goal?.goal_text ?? "");
    setStatus(((goal?.status as GoalStatus) ?? "active") || "active");
    setTargetDate(toDateInput(goal?.targetDate ?? goal?.target_date ?? null));
    setSelectedMember("");
    setSaving(false);
  }, [open, goal]);

  // Load the member roster for the picker when the modal opens in create mode.
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
    if (goalText.trim() === "") {
      showApiError("Goal text is required");
      return;
    }
    setSaving(true);
    try {
      if (isEdit && goal) {
        await apiClient.patch(`/goals/${goal.id}`, {
          goal_text: goalText.trim(),
          status,
          target_date: targetDate || null,
        });
        showSuccess("Goal updated");
      } else {
        const member = memberId ?? selectedMember;
        if (!member) {
          showApiError("Please choose a member");
          setSaving(false);
          return;
        }
        await apiClient.post("/goals", {
          member_id: member,
          goal_text: goalText.trim(),
          status,
          target_date: targetDate || null,
        });
        showSuccess("Goal added");
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
      aria-label={isEdit ? "Edit goal" : "Add goal"}
      onClick={onClose}
    >
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md p-6" onClick={(e) => e.stopPropagation()}>
        <h2 className="text-base font-bold text-gray-900">{isEdit ? "Edit Goal" : "Add Goal"}</h2>
        <p className="text-xs text-gray-500 mt-0.5">
          {isEdit ? "Update this member goal." : "Set a new accountability goal for a member."}
        </p>

        <div className="mt-4 space-y-3">
          {needsMemberPicker && (
            <label className="block">
              <span className="text-[11px] font-bold uppercase tracking-widest text-gray-400">Member *</span>
              <select
                value={selectedMember}
                onChange={(e) => setSelectedMember(e.target.value)}
                disabled={membersLoading}
                className="mt-1 w-full text-sm border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-orange-300 disabled:bg-gray-50 disabled:text-gray-400"
              >
                <option value="">
                  {membersLoading ? "Loading members…" : "Select a member…"}
                </option>
                {members.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.name || m.email || m.id}
                    {m.name && m.email ? ` (${m.email})` : ""}
                  </option>
                ))}
              </select>
              {!membersLoading && members.length === 0 && (
                <span className="mt-1 block text-[11px] text-gray-400">
                  No members yet — add one in Members first.
                </span>
              )}
            </label>
          )}
          <label className="block">
            <span className="text-[11px] font-bold uppercase tracking-widest text-gray-400">Goal *</span>
            <textarea
              value={goalText}
              onChange={(e) => setGoalText(e.target.value)}
              rows={2}
              autoFocus
              className="mt-1 w-full text-sm border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-orange-300 resize-none"
            />
          </label>
          <div className="grid grid-cols-2 gap-3">
            <label className="block">
              <span className="text-[11px] font-bold uppercase tracking-widest text-gray-400">Status</span>
              <select
                value={status}
                onChange={(e) => setStatus(e.target.value as GoalStatus)}
                className="mt-1 w-full text-sm border border-gray-300 rounded-md px-2 py-2 focus:outline-none focus:ring-2 focus:ring-orange-300"
              >
                {STATUS_OPTIONS.map((s) => (
                  <option key={s} value={s}>
                    {s[0].toUpperCase() + s.slice(1)}
                  </option>
                ))}
              </select>
            </label>
            <label className="block">
              <span className="text-[11px] font-bold uppercase tracking-widest text-gray-400">Target Date</span>
              <input
                type="date"
                value={targetDate}
                onChange={(e) => setTargetDate(e.target.value)}
                className="mt-1 w-full text-sm border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-orange-300"
              />
            </label>
          </div>
        </div>

        <div className="mt-6 flex justify-end gap-2">
          <Button variant="ghost" size="sm" onClick={onClose} disabled={saving}>
            Cancel
          </Button>
          <Button
            variant="primary"
            size="sm"
            onClick={() => void submit()}
            disabled={saving || goalText.trim() === "" || (needsMemberPicker && selectedMember === "")}
          >
            {saving ? "Saving…" : isEdit ? "Save Goal" : "Add Goal"}
          </Button>
        </div>
      </div>
    </div>
  );
}
