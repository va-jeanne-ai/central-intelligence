"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { DirectorWebSocket } from "@/lib/director-websocket";
import { chatSessionsClient } from "@/lib/chat-sessions-client";
import { showError } from "@/lib/toast";
import { useAuth } from "@/hooks/use-auth";
import type { ChatMessage, WebSocketMessage } from "@/types";

// ─── useDirectorChat ──────────────────────────────────────────────────────────
//
// History parity with useChat, scoped per director:
//   - sessionId is mirrored to localStorage under a director-specific key so a
//     reload resumes that director's last conversation (and the transcript is
//     re-fetched on mount).
//   - loadSession(id) swaps to a stored session + reloads its transcript; the
//     WS effect reconnects so the backend re-hydrates the director's memory.
//   - startNewChat() mints a fresh UUID + clears the visible messages.

function _storageKey(directorSlug: string): string {
  return `director-chat-session-id:${directorSlug}`;
}

function _readStoredSessionId(directorSlug: string): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(_storageKey(directorSlug));
  } catch {
    return null;
  }
}

function _writeStoredSessionId(directorSlug: string, id: string): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(_storageKey(directorSlug), id);
  } catch {
    // localStorage unavailable — non-fatal; session still works this load.
  }
}

export function useDirectorChat(directorSlug: string) {
  // Gate all auth-dependent work (WS connect, history fetches) on the auth
  // context: isLoading stays true until apiClient has a valid token, so firing
  // before it means an unauthenticated WS + a sidebar list that returns nothing
  // (the new session row exists but never shows). Mirrors useChat.
  const { isLoading: authLoading, user } = useAuth();

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const [connectionFailed, setConnectionFailed] = useState(false);

  // Restore the prior session id (per director) so a reload resumes it; fall
  // back to a fresh UUID for a true first visit. Transcript is loaded on mount.
  const restoredOnMountRef = useRef<boolean>(false);
  const [sessionId, setSessionId] = useState<string>(() => {
    const stored = _readStoredSessionId(directorSlug);
    restoredOnMountRef.current = stored !== null;
    return stored ?? crypto.randomUUID();
  });

  // Keep a stable ref to the current ws instance so callbacks always see it.
  const wsRef = useRef<DirectorWebSocket | null>(null);

  // Mirror sessionId → localStorage on every change so the latest active
  // session for this director is what we resume to.
  useEffect(() => {
    _writeStoredSessionId(directorSlug, sessionId);
  }, [directorSlug, sessionId]);

  // ─── WebSocket lifecycle ────────────────────────────────────────────────────
  // Gated on auth: the WS reads the token from apiClient at construction time,
  // so connecting before auth hydrates yields an unauthenticated socket whose
  // turns never persist.

  useEffect(() => {
    if (authLoading || !user) return;

    const ws = new DirectorWebSocket(directorSlug, sessionId);
    wsRef.current = ws;

    const unsub = ws.onMessage((msg: WebSocketMessage) => {
      const { data } = msg;

      if (data.isComplete) {
        // Stream is done — finalise the assistant bubble.
        setIsStreaming(false);
        const isIncomplete = data.status === "incomplete";
        setMessages((prev) => {
          const last = prev[prev.length - 1];
          if (last?.role === "assistant" && last.isStreaming === true) {
            const finalContent =
              data.fullResponse !== undefined && data.fullResponse !== ""
                ? data.fullResponse
                : last.content;
            // When the model stopped early, keep the partial text but flag it
            // incomplete so the UI shows a reload prompt instead of treating the
            // cut-off answer as final/trustworthy.
            return [
              ...prev.slice(0, -1),
              {
                ...last,
                isStreaming: false,
                content: finalContent,
                incomplete: isIncomplete,
                finishReason: isIncomplete ? data.finishReason : undefined,
                notice: isIncomplete ? data.notice : undefined,
              },
            ];
          }
          return prev;
        });
      } else {
        // Append incoming token to the in-progress bubble.
        setMessages((prev) => {
          const last = prev[prev.length - 1];
          if (last?.role === "assistant" && last.isStreaming === true) {
            return [
              ...prev.slice(0, -1),
              { ...last, content: last.content + data.chunk },
            ];
          }
          // First token — open a new assistant bubble.
          return [
            ...prev,
            {
              id: crypto.randomUUID(),
              role: "assistant" as const,
              content: data.chunk,
              timestamp: new Date(),
              isStreaming: true,
            },
          ];
        });
      }
    });

    const unsubState = ws.onStateChange((state) => {
      setIsConnected(state === "connected");
      setConnectionFailed(state === "failed");
      if (state === "failed") {
        setIsStreaming(false);
      }
    });

    ws.connect();

    return () => {
      unsub();
      unsubState();
      ws.disconnect();
      wsRef.current = null;
      setIsConnected(false);
    };
  // directorSlug is stable per page mount — re-connecting on slug change is
  // correct behaviour (navigating to a different director).
  }, [directorSlug, sessionId, authLoading, user]);

  // ─── Restore transcript for the resumed session (once, on mount) ────────────
  // The WS effect reconnects to the restored sessionId (so the backend
  // re-hydrates the director's memory); fetch the persisted transcript once so
  // the on-screen bubbles reappear. Skipped for a brand-new session; degrades
  // silently if the stored session was deleted server-side. Gated on auth so
  // the transcript fetch carries a token.
  const didRestoreRef = useRef(false);
  useEffect(() => {
    if (authLoading || !user) return;
    if (didRestoreRef.current) return;
    didRestoreRef.current = true;
    if (!restoredOnMountRef.current) return;

    let cancelled = false;
    void (async () => {
      try {
        const detail = await chatSessionsClient.get(sessionId);
        if (cancelled) return;
        setMessages(
          detail.messages.map((m) => ({
            id: m.id,
            role: m.role,
            content: m.content,
            timestamp: new Date(m.created_at),
          })),
        );
      } catch {
        // Session deleted / fetch failed — leave the blank canvas.
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [sessionId, authLoading, user]);

  // ─── Public actions ─────────────────────────────────────────────────────────

  const sendMessage = useCallback(
    (content: string) => {
      const trimmed = content.trim();
      if (trimmed === "" || isStreaming) return;

      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: "user" as const,
          content: trimmed,
          timestamp: new Date(),
        },
      ]);

      setIsStreaming(true);
      wsRef.current?.send(trimmed);
    },
    [isStreaming],
  );

  const clearChat = useCallback(() => {
    setMessages([]);
  }, []);

  /** Switch to an existing persisted session and load its transcript. */
  const loadSession = useCallback(
    async (nextSessionId: string) => {
      if (nextSessionId === sessionId) return;
      try {
        const detail = await chatSessionsClient.get(nextSessionId);
        setMessages(
          detail.messages.map((m) => ({
            id: m.id,
            role: m.role,
            content: m.content,
            timestamp: new Date(m.created_at),
          })),
        );
        // Swap sessionId — the WS effect tears down the old socket and
        // reconnects on the new session_id path (backend re-hydrates memory).
        setSessionId(nextSessionId);
      } catch (err) {
        showError(
          err instanceof Error ? err.message : "Failed to load chat session.",
        );
      }
    },
    [sessionId],
  );

  /** Start a fresh session — new UUID, empty transcript. */
  const startNewChat = useCallback(() => {
    setMessages([]);
    setSessionId(crypto.randomUUID());
  }, []);

  return {
    messages,
    sendMessage,
    clearChat,
    isStreaming,
    isConnected,
    connectionFailed,
    sessionId,
    loadSession,
    startNewChat,
  };
}
