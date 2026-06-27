"use client";

import { useState } from "react";
import { Header } from "@/components/layout/header";
import { TranscriptUploadWidget } from "@/components/upload/transcript-upload-widget";
import type { TranscriptUploadResult } from "@/components/upload/transcript-upload-widget";
import { CallsTable } from "@/components/calls/calls-table";

export default function SalesCallsPage() {
  // Bumped after a successful upload to force the table to refetch.
  const [refreshKey, setRefreshKey] = useState(0);

  function handleUploadSuccess(result: TranscriptUploadResult) {
    void result;
    setRefreshKey((k) => k + 1);
  }

  return (
    <>
      <Header title="Sales Calls" />

      <main className="flex-1 overflow-y-auto p-7 space-y-6">
        {/* Page heading */}
        <div>
          <h1 className="text-xl font-bold text-gray-900">Sales Calls</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Transcribe and analyze your sales recordings to surface insights and coaching
            opportunities. Sort any column, or filter by result, source, and date.
          </p>
        </div>

        {/* Upload widget */}
        <TranscriptUploadWidget callType="Sales" onSuccess={handleUploadSuccess} />

        {/* Sales-side calls: Sales, Discovery, and Outbound (the WGR mirror's
            outbound-dial calls). Type column/filter hidden since locked. */}
        <CallsTable
          lockedCallType="Sales,Discovery,Outbound"
          hideTypeFilter
          refreshKey={refreshKey}
        />
      </main>
    </>
  );
}
