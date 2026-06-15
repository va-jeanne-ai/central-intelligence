"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { CentralIntelligenceWebSocket } from "@/lib/websocket";
import { chatSessionsClient } from "@/lib/chat-sessions-client";
import { showError } from "@/lib/toast";
import { useAuth } from "@/hooks/use-auth";
import type { ChatMessage, WebSocketMessage } from "@/types";

// ─── useChat ──────────────────────────────────────────────────────────────────
//
// Owns the chat state for the page: the active sessionId, the visible
// messages list, and the streaming WebSocket connection.
//
// Persistence:
//   - sessionId is generated client-side and held in this hook, AND mirrored
//     to localStorage so a page reload resumes the same conversation instead
//     of starting a blank one. On mount we restore the stored id and reload
//     its transcript (history itself lives in the DB; this just re-opens it).
//   - When the user picks a session from the sidebar, the parent calls
//     loadSession(id): we fetch the transcript, swap messages, switch
//     the WebSocket connection to the new sessionId so subsequent
//     turns hit the right backend agent.
//   - startNewChat() mints a fresh UUID + clears messages.

const _SESSION_STORAGE_KEY = "ci-chat-session-id";

function _readStoredSessionId(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(_SESSION_STORAGE_KEY);
  } catch {
    return null;
  }
}

function _writeStoredSessionId(id: string): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(_SESSION_STORAGE_KEY, id);
  } catch {
    // localStorage unavailable (private mode / quota) — non-fatal; the
    // session still works for this page load, it just won't survive reload.
  }
}

export function useChat() {
  const { isLoading: authLoading, user } = useAuth();

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const [connectionFailed, setConnectionFailed] = useState(false);
  // Restore the prior session id on mount so a reload resumes that chat;
  // fall back to a fresh UUID for a true first visit. The transcript for a
  // restored id is loaded by the mount effect below.
  const restoredOnMountRef = useRef<boolean>(false);
  const [sessionId, setSessionId] = useState<string>(() => {
    const stored = _readStoredSessionId();
    restoredOnMountRef.current = stored !== null;
    return stored ?? crypto.randomUUID();
  });

  // Keep a stable ref to the current ws instance so callbacks always see it.
  const wsRef = useRef<CentralIntelligenceWebSocket | null>(null);

  // Mirror sessionId → localStorage on every change (initial, loadSession,
  // startNewChat) so the latest active session is always what we resume to.
  useEffect(() => {
    _writeStoredSessionId(sessionId);
  }, [sessionId]);

  // ─── WebSocket lifecycle ────────────────────────────────────────────────────
  // Gated on auth: the WS constructor reads the token from apiClient
  // at construction time, so we must wait until the auth context has
  // hydrated and pushed the token into apiClient. Otherwise the socket
  // connects unauthenticated and chat persistence silently no-ops.

  useEffect(() => {
    if (authLoading || !user) return;

    const ws = new CentralIntelligenceWebSocket(sessionId);
    wsRef.current = ws;

    const unsub = ws.onMessage((msg: WebSocketMessage) => {
      const { data } = msg;

      if (data.isComplete) {
        // Stream is done — finalise the assistant bubble.
        setIsStreaming(false);
        setMessages((prev) => {
          const last = prev[prev.length - 1];
          if (last?.role === "assistant" && last.isStreaming === true) {
            const finalContent =
              data.fullResponse !== undefined && data.fullResponse !== ""
                ? data.fullResponse
                : last.content;
            return [
              ...prev.slice(0, -1),
              { ...last, isStreaming: false, content: finalContent },
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
  }, [sessionId, authLoading, user]);

  // ─── Restore transcript for the resumed session (once, on mount) ────────────
  // The WS effect reconnects the socket to the restored sessionId (so the
  // backend re-hydrates the agent's memory), but the on-screen bubbles start
  // empty. Fetch the persisted transcript once so the conversation reappears.
  // Skipped for a brand-new session (nothing to load) and degrades silently if
  // the stored session was deleted server-side.
  const didRestoreRef = useRef(false);
  useEffect(() => {
    if (authLoading || !user) return;
    if (didRestoreRef.current) return;
    didRestoreRef.current = true;

    // Only attempt restore if the id was resumed from a prior visit. A
    // freshly-minted first-visit id has no persisted transcript to fetch.
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
        // Session not found (deleted) or fetch failed — leave the blank
        // canvas; the user can start typing or pick a session from the sidebar.
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [authLoading, user, sessionId]);

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
  const loadSession = useCallback(async (nextSessionId: string) => {
    if (nextSessionId === sessionId) return;
    try {
      const detail = await chatSessionsClient.get(nextSessionId);
      // Map persisted rows into the in-memory ChatMessage shape.
      setMessages(
        detail.messages.map((m) => ({
          id: m.id,
          role: m.role,
          content: m.content,
          timestamp: new Date(m.created_at),
        })),
      );
      // Swap sessionId — the WS effect will tear down the old socket
      // and reconnect against the new session_id path.
      setSessionId(nextSessionId);
    } catch (err) {
      showError(
        err instanceof Error ? err.message : "Failed to load chat session.",
      );
    }
  }, [sessionId]);

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
