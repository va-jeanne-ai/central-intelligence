import type { Metadata } from "next";
import { Header } from "@/components/layout/header";
import { SalesDirectorChatView } from "@/components/chat/sales-director-chat-view";

// ─── Metadata ─────────────────────────────────────────────────────────────────

export const metadata: Metadata = {
  title: "Sales Director",
};

// ─── SalesDirectorPage ─────────────────────────────────────────────────────────

export default function SalesDirectorPage() {
  return (
    <>
      <Header title="Sales Director" />
      <main className="flex flex-1 overflow-hidden">
        <SalesDirectorChatView />
      </main>
    </>
  );
}
