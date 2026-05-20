"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { CentralIntelligenceWebSocket } from "@/lib/websocket";
import type { ChatMessage, WebSocketMessage } from "@/types";

// ─── useChat ──────────────────────────────────────────────────────────────────

export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const [connectionFailed, setConnectionFailed] = useState(false);
  const [sessionId] = useState<string>(() => crypto.randomUUID());

  // Keep a stable ref to the current ws instance so callbacks always see it.
  const wsRef = useRef<CentralIntelligenceWebSocket | null>(null);

  // ─── WebSocket lifecycle ────────────────────────────────────────────────────

  useEffect(() => {
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
  }, [sessionId]);

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
