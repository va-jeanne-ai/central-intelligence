import type { Metadata } from "next";
import { Header } from "@/components/layout/header";
import { ChatView } from "@/components/chat/chat-view";

// ─── Metadata ─────────────────────────────────────────────────────────────────

export const metadata: Metadata = {
  title: "Central Intelligence Chat",
};

// ─── ChatPage ─────────────────────────────────────────────────────────────────

export default function ChatPage() {
  return (
    <>
      {/* Standard site header */}
      <Header title="Central Intelligence Chat" />

      {/*
        Main content area.
        flex-1 + overflow-hidden lets ChatView own its own scroll.
        The outer layout (layout.tsx) already wraps this in a flex column,
        so flex-1 here expands to fill all remaining vertical space.
      */}
      <main className="flex flex-1 overflow-hidden">
        <ChatView />
      </main>
    </>
  );
}
