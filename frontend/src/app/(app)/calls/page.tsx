"use client";

import { Header } from "@/components/layout/header";
import { CallsTable } from "@/components/calls/calls-table";

export default function AllCallsPage() {
  return (
    <>
      <Header title="All Calls" />

      <main className="flex-1 overflow-y-auto p-7 space-y-6">
        {/* Page heading */}
        <div>
          <h1 className="text-xl font-bold text-gray-900">All Calls</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Every analyzed call across all types — discovery, sales, outbound, and more.
            Sort any column, or filter by type, result, source, and date.
          </p>
        </div>

        {/* All call types — the Type column + filter are shown. */}
        <CallsTable />
      </main>
    </>
  );
}
