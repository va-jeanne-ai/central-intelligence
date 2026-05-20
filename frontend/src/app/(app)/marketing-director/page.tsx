import type { Metadata } from "next";
import { Header } from "@/components/layout/header";
import { MarketingDirectorChatView } from "@/components/chat/marketing-director-chat-view";

// ─── Metadata ─────────────────────────────────────────────────────────────────

export const metadata: Metadata = {
  title: "Marketing Director",
};

// ─── MarketingDirectorPage ────────────────────────────────────────────────────

export default function MarketingDirectorPage() {
  return (
    <>
      <Header title="Marketing Director" />
      <main className="flex flex-1 overflow-hidden">
        <MarketingDirectorChatView />
      </main>
    </>
  );
}
