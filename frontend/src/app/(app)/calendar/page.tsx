import type { Metadata } from "next";
import { Header } from "@/components/layout/header";
import { CalendarView } from "@/components/calendar/calendar-view";

// ─── Metadata ─────────────────────────────────────────────────────────────────

export const metadata: Metadata = {
  title: "Calendar — Central Intelligence",
};

// ─── CalendarPage ─────────────────────────────────────────────────────────────

export default function CalendarPage() {
  return (
    <>
      <Header title="Calendar" />

      <main className="flex flex-1 overflow-hidden bg-gray-50">
        <CalendarView />
      </main>
    </>
  );
}
