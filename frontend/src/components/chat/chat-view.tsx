"use client";

import { useEffect, useRef, useCallback, useState } from "react";
import { useChat } from "@/hooks/use-chat";
import { MessageBubble } from "@/components/chat/message-bubble";
import { ChatInput } from "@/components/chat/chat-input";
import { TypingIndicator } from "@/components/chat/typing-indicator";
import { ChatHistorySidebar } from "@/components/chat/chat-history-sidebar";
import { ChatConnecting } from "@/components/ui/skeleton";

// ─── Static welcome message ───────────────────────────────────────────────────

const WELCOME_MESSAGE = `Hello! I'm **Central Intelligence** — your AI-powered command center for the Central Intelligence platform.

I have full visibility across all your data sources: **Sales** (leads, calls, appointments), **Fulfillment** (members, coaching, accountability), and **Marketing** (social, email, funnels, ads).

Ask me anything — here are a few ideas to get you started:

- "How many new leads came in this week?"
- "Which members are at risk of churning?"
- "Give me content ideas for next month's campaign"
- "What's our current conversion rate from lead to close?"`;

// ─── Chat topbar ──────────────────────────────────────────────────────────────

interface ChatTopbarProps {
  isConnected: boolean;
  onClear: () => void;
}

function ChatTopbar({ isConnected, onClear }: ChatTopbarProps) {
  return (
    <div className="flex items-center justify-between px-6 py-3 bg-white border-b border-gray-200 flex-shrink-0">
      {/* Left — identity */}
      <div className="flex items-center gap-3">
        {/* Avatar */}
        <div
          className="flex items-center justify-center w-[34px] h-[34px] rounded-full flex-shrink-0 shadow-sm"
          style={{
            background: "linear-gradient(135deg, #F59E0B 0%, #D97706 100%)",
          }}
          aria-hidden="true"
        >
          <span className="text-sm leading-none">👑</span>
        </div>

        {/* Name + status */}
        <div className="flex flex-col">
          <span className="text-sm font-semibold text-gray-900">Central Intelligence</span>
          <div className="flex items-center gap-1.5">
            <span
              className={[
                "w-2 h-2 rounded-full flex-shrink-0",
                isConnected ? "bg-green-500" : "bg-gray-300",
              ].join(" ")}
              aria-hidden="true"
            />
            <span className="text-[11px] text-gray-400 leading-none">
              {isConnected
                ? "Online — connected to all data sources"
                : "Connecting…"}
            </span>
          </div>
        </div>
      </div>

      {/* Right — actions */}
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={onClear}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-gray-600 bg-gray-100 rounded-lg hover:bg-gray-200 transition-all duration-150 active:scale-95"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 20 20"
            fill="currentColor"
            className="w-3.5 h-3.5"
            aria-hidden="true"
          >
            <path
              fillRule="evenodd"
              d="M8.75 1A2.75 2.75 0 006 3.75v.443c-.795.077-1.584.176-2.365.298a.75.75 0 10.23 1.482l.149-.022.841 10.518A2.75 2.75 0 007.596 19h4.807a2.75 2.75 0 002.742-2.53l.841-10.52.149.023a.75.75 0 00.23-1.482A41.03 41.03 0 0014 4.193V3.75A2.75 2.75 0 0011.25 1h-2.5zM10 4c.84 0 1.673.025 2.5.075V3.75c0-.69-.56-1.25-1.25-1.25h-2.5c-.69 0-1.25.56-1.25 1.25v.325C8.327 4.025 9.16 4 10 4zM8.58 7.72a.75.75 0 00-1.5.06l.3 7.5a.75.75 0 101.5-.06l-.3-7.5zm4.34.06a.75.75 0 10-1.5-.06l-.3 7.5a.75.75 0 101.5.06l.3-7.5z"
              clipRule="evenodd"
            />
          </svg>
          Clear chat
        </button>

        <button
          type="button"
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-gray-600 bg-gray-100 rounded-lg hover:bg-gray-200 transition-all duration-150 active:scale-95"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 20 20"
            fill="currentColor"
            className="w-3.5 h-3.5"
            aria-hidden="true"
          >
            <path d="M10.75 2.75a.75.75 0 00-1.5 0v8.614L6.295 8.235a.75.75 0 10-1.09 1.03l4.25 4.5a.75.75 0 001.09 0l4.25-4.5a.75.75 0 00-1.09-1.03l-2.955 3.129V2.75z" />
            <path d="M3.5 12.75a.75.75 0 00-1.5 0v2.5A2.75 2.75 0 004.75 18h10.5A2.75 2.75 0 0018 15.25v-2.5a.75.75 0 00-1.5 0v2.5c0 .69-.56 1.25-1.25 1.25H4.75c-.69 0-1.25-.56-1.25-1.25v-2.5z" />
          </svg>
          Export
        </button>
      </div>
    </div>
  );
}

// ─── ChatView ─────────────────────────────────────────────────────────────────

export function ChatView() {
  const {
    messages,
    sendMessage,
    clearChat,
    isStreaming,
    isConnected,
    sessionId,
    loadSession,
    startNewChat,
  } = useChat();

  // Scroll anchor — sits at the bottom of the messages list.
  const bottomRef = useRef<HTMLDivElement>(null);
  const messagesAreaRef = useRef<HTMLDivElement>(null);

  // Bump this to tell the sidebar "refetch the session list" — used
  // after a new chat sends its first message (sidebar row didn't
  // exist yet) and after a delete-followed-by-redirect.
  const [sidebarRefreshKey, setSidebarRefreshKey] = useState(0);

  // Auto-scroll whenever the messages list grows.
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // First user message of a fresh chat creates a new DB row backend-
  // side. Once the assistant's response lands (streaming completes,
  // isStreaming flips false with ≥1 user+assistant pair persisted)
  // we refresh the sidebar so the new session appears.
  const lastStreaming = useRef(false);
  useEffect(() => {
    if (lastStreaming.current && !isStreaming && messages.length > 0) {
      setSidebarRefreshKey((k) => k + 1);
    }
    lastStreaming.current = isStreaming;
  }, [isStreaming, messages.length]);

  const handleClear = useCallback(() => {
    clearChat();
  }, [clearChat]);

  const handleSelectSession = useCallback(
    (id: string) => {
      void loadSession(id);
    },
    [loadSession],
  );

  const handleDeletedSession = useCallback(
    (id: string) => {
      // If the user deleted the chat they were viewing, drop them
      // into a fresh "New chat" state so we're not silently broken.
      if (id === sessionId) {
        startNewChat();
      }
    },
    [sessionId, startNewChat],
  );

  // Derive the effective message list: prepend the static welcome bubble.
  const welcomeBubble = {
    id: "welcome",
    role: "assistant" as const,
    content: WELCOME_MESSAGE,
    timestamp: new Date(0), // epoch — always first
    isStreaming: false,
  };

  const allMessages =
    messages.length === 0 && !isStreaming
      ? [welcomeBubble]
      : [welcomeBubble, ...messages];

  // Show connecting screen until WebSocket is ready
  if (!isConnected) {
    return (
      <div className="flex flex-1 overflow-hidden bg-white">
        <ChatHistorySidebar
          activeSessionId={sessionId}
          refreshKey={sidebarRefreshKey}
          onSelectSession={handleSelectSession}
          onNewChat={startNewChat}
          onDeleted={handleDeletedSession}
        />
        <div className="flex flex-col flex-1 overflow-hidden bg-white">
          <ChatTopbar isConnected={false} onClear={handleClear} />
          <ChatConnecting />
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-1 overflow-hidden bg-white">
      {/* History sidebar */}
      <ChatHistorySidebar
        activeSessionId={sessionId}
        refreshKey={sidebarRefreshKey}
        onSelectSession={handleSelectSession}
        onNewChat={startNewChat}
        onDeleted={handleDeletedSession}
      />

      {/* Main chat column */}
      <div className="flex flex-col flex-1 overflow-hidden bg-white">
      {/* Chat topbar */}
      <ChatTopbar isConnected={isConnected} onClear={handleClear} />

      {/* Messages area */}
      <div
        ref={messagesAreaRef}
        className="flex-1 overflow-y-auto px-6 py-5"
        style={{ backgroundColor: "#FAFAFA" }}
        aria-label="Chat messages"
        role="log"
        aria-live="polite"
        aria-atomic="false"
      >
        <div className="flex flex-col gap-4">
          {allMessages.map((message) => (
            <MessageBubble key={message.id} message={message} />
          ))}

          {/* Typing indicator — shown while streaming (before first token arrives) */}
          {isStreaming &&
            (messages[messages.length - 1]?.isStreaming !== true) && (
              <div className="flex items-start gap-3">
                <div
                  className="flex items-center justify-center w-9 h-9 rounded-full flex-shrink-0 shadow-sm"
                  style={{
                    background:
                      "linear-gradient(135deg, #F59E0B 0%, #D97706 100%)",
                  }}
                  aria-hidden="true"
                >
                  <span className="text-base leading-none">👑</span>
                </div>
                <div className="bg-white border border-gray-200 rounded-2xl rounded-tl-[4px] shadow-sm">
                  <TypingIndicator />
                </div>
              </div>
            )}

          {/* Scroll anchor */}
          <div ref={bottomRef} aria-hidden="true" />
        </div>
      </div>

      {/* Input bar */}
      <ChatInput onSend={sendMessage} isDisabled={isStreaming} />
      </div>
    </div>
  );
}
