"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { DirectorWebSocket } from "@/lib/director-websocket";
import type { ChatMessage, WebSocketMessage } from "@/types";

// ─── useDirectorChat ──────────────────────────────────────────────────────────

export function useDirectorChat(directorSlug: string) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const [connectionFailed, setConnectionFailed] = useState(false);
  const [sessionId] = useState<string>(() => crypto.randomUUID());

  // Keep a stable ref to the current ws instance so callbacks always see it.
  const wsRef = useRef<DirectorWebSocket | null>(null);

  // ─── WebSocket lifecycle ────────────────────────────────────────────────────

  useEffect(() => {
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
  }, [directorSlug, sessionId]);

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

  return {
    messages,
    sendMessage,
    clearChat,
    isStreaming,
    isConnected,
    connectionFailed,
    sessionId,
  };
}
