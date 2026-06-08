import type { Metadata } from "next";
import { Header } from "@/components/layout/header";
import { FulfillmentDirectorChatView } from "@/components/chat/fulfillment-director-chat-view";

// ─── Metadata ─────────────────────────────────────────────────────────────────

export const metadata: Metadata = {
  title: "Fulfillment Director",
};

// ─── FulfillmentDirectorPage ───────────────────────────────────────────────────

export default function FulfillmentDirectorPage() {
  return (
    <>
      <Header title="Fulfillment Director" />
      <main className="flex flex-1 overflow-hidden">
        <FulfillmentDirectorChatView />
      </main>
    </>
  );
}
