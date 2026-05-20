"use client";

import { useEffect, useRef, useCallback } from "react";
import { useDirectorChat } from "@/hooks/use-director-chat";
import { MessageBubble } from "@/components/chat/message-bubble";
import { ChatInput } from "@/components/chat/chat-input";
import { TypingIndicator } from "@/components/chat/typing-indicator";

// ─── Static welcome message ───────────────────────────────────────────────────

const WELCOME_MESSAGE = `Hello! I'm your **Marketing Director** — your AI-powered marketing strategist for the Central Intelligence platform.

I have deep visibility into your marketing operations: **Content Strategy** (ideas, calendar, copy), **Campaign Intelligence** (performance signals, audience insights), **Lead Generation** (funnels, ads, social), and **Engagement** (email, DM, offers).

Ask me anything — here are a few ideas to get you started:

- "Give me content ideas for next week's social posts"
- "How is our top-of-funnel performing this month?"
- "What email subject lines should we test next?"
- "Which ad campaigns should we pause or scale?"`;

// ─── Connecting screen ────────────────────────────────────────────────────────

function DirectorConnecting() {
  return (
    <div className="flex flex-col items-center justify-center flex-1 gap-3" role="status">
      <div className="relative">
        <div className="w-12 h-12 rounded-full border-3 border-gray-200 border-t-emerald-500 animate-spin" />
        <span className="absolute inset-0 flex items-center justify-center text-lg">
          📣
        </span>
      </div>
      <span className="text-sm text-gray-500 font-medium">
        Connecting to Marketing Director...
      </span>
      <span className="text-xs text-gray-400">Setting up your secure session</span>
    </div>
  );
}

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
            background: "linear-gradient(135deg, #10B981 0%, #059669 100%)",
          }}
          aria-hidden="true"
        >
          <span className="text-sm leading-none">📣</span>
        </div>

        {/* Name + status */}
        <div className="flex flex-col">
          <span className="text-sm font-semibold text-gray-900">
            Marketing Director
          </span>
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
                ? "Online — connected to marketing data"
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

// ─── MarketingDirectorChatView ────────────────────────────────────────────────

export function MarketingDirectorChatView() {
  const { messages, sendMessage, clearChat, isStreaming, isConnected } =
    useDirectorChat("marketing-director");

  // Scroll anchor — sits at the bottom of the messages list.
  const bottomRef = useRef<HTMLDivElement>(null);
  const messagesAreaRef = useRef<HTMLDivElement>(null);

  // Auto-scroll whenever the messages list grows.
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleClear = useCallback(() => {
    clearChat();
  }, [clearChat]);

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
      <div className="flex flex-col flex-1 overflow-hidden bg-white">
        <ChatTopbar isConnected={false} onClear={handleClear} />
        <DirectorConnecting />
      </div>
    );
  }

  return (
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
            <MessageBubble
              key={message.id}
              message={message}
              agent={{
                name: "Marketing Director",
                icon: "📣",
                gradient: "linear-gradient(135deg, #10B981 0%, #059669 100%)",
              }}
            />
          ))}

          {/* Typing indicator — shown while streaming (before first token arrives) */}
          {isStreaming &&
            messages[messages.length - 1]?.isStreaming !== true && (
              <div className="flex items-start gap-3">
                <div
                  className="flex items-center justify-center w-9 h-9 rounded-full flex-shrink-0 shadow-sm"
                  style={{
                    background:
                      "linear-gradient(135deg, #10B981 0%, #059669 100%)",
                  }}
                  aria-hidden="true"
                >
                  <span className="text-base leading-none">📣</span>
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
  );
}
