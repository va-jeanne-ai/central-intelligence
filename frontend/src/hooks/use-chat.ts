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
//   - sessionId is generated client-side and held in this hook.
//   - When the user picks a session from the sidebar, the parent calls
//     loadSession(id): we fetch the transcript, swap messages, switch
//     the WebSocket connection to the new sessionId so subsequent
//     turns hit the right backend agent.
//   - startNewChat() mints a fresh UUID + clears messages.

export function useChat() {
  const { isLoading: authLoading, user } = useAuth();

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const [connectionFailed, setConnectionFailed] = useState(false);
  const [sessionId, setSessionId] = useState<string>(() => crypto.randomUUID());

  // Keep a stable ref to the current ws instance so callbacks always see it.
  const wsRef = useRef<CentralIntelligenceWebSocket | null>(null);

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
