"use client";

import { Header } from "@/components/layout/header";
import { TranscriptUploadWidget } from "@/components/upload/transcript-upload-widget";
import type { TranscriptUploadResult } from "@/components/upload/transcript-upload-widget";

// ─── Empty state ──────────────────────────────────────────────────────────────

function EmptyUploadsList() {
  return (
    <div className="flex flex-col items-center justify-center py-16 gap-3">
      <span className="text-4xl" aria-hidden="true">
        📋
      </span>
      <p className="text-sm font-medium text-gray-500">No uploads yet.</p>
      <p className="text-xs text-gray-400">
        Submit your first transcript above to get started.
      </p>
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function CiTranscriptUploadPage() {
  function handleUploadSuccess(result: TranscriptUploadResult) {
    // Future: refresh uploads list or show toast
    void result;
  }

  return (
    <>
      <Header title="CI Transcript Upload" />

      <main className="flex-1 overflow-y-auto p-7 space-y-6">
        {/* Page heading */}
        <div>
          <h1 className="text-xl font-bold text-gray-900">CI Transcript Upload</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Upload coaching and client call transcripts to extract competitive intelligence.
          </p>
        </div>

        {/* Upload widget */}
        <TranscriptUploadWidget
          callType="Coaching"
          onSuccess={handleUploadSuccess}
        />

        {/* Recent uploads section */}
        <section aria-label="Recent uploads">
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
            {/* Section header */}
            <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
              <h2 className="text-sm font-bold text-gray-900">Recent Uploads</h2>
              <span className="text-xs text-gray-400">0 uploads</span>
            </div>

            {/* Empty state */}
            <EmptyUploadsList />
          </div>
        </section>
      </main>
    </>
  );
}
