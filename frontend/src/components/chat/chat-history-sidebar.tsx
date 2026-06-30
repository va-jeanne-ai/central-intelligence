"use client";

import { useCallback, useEffect, useState } from "react";

import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { chatSessionsClient } from "@/lib/chat-sessions-client";
import { showError, showSuccess } from "@/lib/toast";
import type { ChatSessionRow } from "@/types";

// ─── Helpers ──────────────────────────────────────────────────────────────────

function relativeTime(iso: string | null): string {
  if (!iso) return "";
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "";
  const diffSec = Math.max(0, (Date.now() - then) / 1000);
  if (diffSec < 60) return "just now";
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ago`;
  if (diffSec < 86_400) return `${Math.floor(diffSec / 3600)}h ago`;
  if (diffSec < 7 * 86_400) return `${Math.floor(diffSec / 86_400)}d ago`;
  return new Date(iso).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  });
}

// ─── Props ────────────────────────────────────────────────────────────────────

interface ChatHistorySidebarProps {
  /** The session currently rendered in the chat surface (highlighted in the list). */
  activeSessionId: string;
  /** Bump this number when a fresh chat sends its first message so the
   * sidebar refetches and surfaces the new row. */
  refreshKey?: number;
  /** Scope the list to one chat surface. Omit for Central Intelligence;
   * pass a director slug (e.g. "marketing-director") for that director. */
  agentSlug?: string;
  onSelectSession: (sessionId: string) => void;
  onNewChat: () => void;
  /** Called after a session is deleted, so the parent can switch away
   * from it if it was the active one. */
  onDeleted?: (sessionId: string) => void;
}

// ─── Component ────────────────────────────────────────────────────────────────

export function ChatHistorySidebar({
  activeSessionId,
  refreshKey,
  agentSlug,
  onSelectSession,
  onNewChat,
  onDeleted,
}: ChatHistorySidebarProps) {
  const [sessions, setSessions] = useState<ChatSessionRow[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [pendingDelete, setPendingDelete] = useState<ChatSessionRow | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  const load = useCallback(async () => {
    try {
      const data = await chatSessionsClient.list(agentSlug);
      setSessions(data.sessions);
    } catch {
      // Silent — the sidebar is a nice-to-have; don't poison the page
      // with a red toast if the user just hasn't sent anything yet.
    } finally {
      setIsLoading(false);
    }
  }, [agentSlug]);

  // Initial load + refetch whenever refreshKey bumps (parent signals
  // "a new session was just born, please refresh the list").
  useEffect(() => {
    void load();
  }, [load, refreshKey]);

  async function confirmDelete() {
    if (!pendingDelete) return;
    setIsDeleting(true);
    try {
      await chatSessionsClient.remove(pendingDelete.id);
      setSessions((prev) => prev.filter((s) => s.id !== pendingDelete.id));
      onDeleted?.(pendingDelete.id);
      showSuccess("Chat deleted");
      setPendingDelete(null);
    } catch (err) {
      showError(err instanceof Error ? err.message : "Failed to delete chat.");
    } finally {
      setIsDeleting(false);
    }
  }

  return (
    <>
      <aside
        className="flex flex-col w-64 shrink-0 bg-gray-50 border-r border-gray-200 overflow-hidden"
        aria-label="Chat history"
      >
        <div className="px-3 py-3 border-b border-gray-200">
          <button
            type="button"
            onClick={onNewChat}
            className="w-full text-[13px] font-semibold px-3 py-2 rounded-lg bg-accent-500 hover:bg-accent-600 text-white transition-colors"
          >
            + New chat
          </button>
        </div>

        <div className="flex-1 overflow-y-auto py-2">
          {isLoading ? (
            <p className="px-3 py-2 text-[12px] text-gray-400 italic">
              Loading…
            </p>
          ) : sessions.length === 0 ? (
            <p className="px-3 py-2 text-[12px] text-gray-400 italic">
              No past chats yet. Send a message to start.
            </p>
          ) : (
            <ul className="space-y-0.5">
              {sessions.map((s) => {
                const isActive = s.id === activeSessionId;
                return (
                  <li key={s.id} className="px-1.5">
                    <div
                      className={
                        "group flex items-start gap-2 px-2 py-2 rounded-lg cursor-pointer transition-colors " +
                        (isActive
                          ? "bg-accent-100 hover:bg-accent-100"
                          : "hover:bg-gray-100")
                      }
                      onClick={() => onSelectSession(s.id)}
                    >
                      <div className="flex-1 min-w-0">
                        <div
                          className={
                            "text-[13px] font-medium truncate " +
                            (isActive ? "text-accent-900" : "text-gray-700")
                          }
                          title={s.title}
                        >
                          {s.title}
                        </div>
                        <div className="text-[11px] text-gray-400 mt-0.5">
                          {relativeTime(s.last_message_at) || "—"}
                          {s.message_count > 0 && (
                            <span className="ml-1.5">
                              · {s.message_count} msg
                              {s.message_count === 1 ? "" : "s"}
                            </span>
                          )}
                        </div>
                      </div>
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          setPendingDelete(s);
                        }}
                        className="opacity-0 group-hover:opacity-100 transition-opacity text-gray-400 hover:text-red-600 px-1"
                        aria-label={`Delete chat "${s.title}"`}
                        title="Delete chat"
                      >
                        ✕
                      </button>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      </aside>

      <ConfirmDialog
        open={pendingDelete !== null}
        onClose={() => !isDeleting && setPendingDelete(null)}
        onConfirm={() => void confirmDelete()}
        title="Delete this chat?"
        description={
          pendingDelete
            ? `"${pendingDelete.title}" and all of its messages will be deleted permanently.`
            : undefined
        }
        confirmLabel="Delete"
        variant="danger"
        loading={isDeleting}
      />
    </>
  );
}
