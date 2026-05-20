"use client";

import { useCallback, useEffect, useState } from "react";
import { Header } from "@/components/layout/header";
import { TranscriptUploadWidget } from "@/components/upload/transcript-upload-widget";
import type { TranscriptUploadResult } from "@/components/upload/transcript-upload-widget";
import { apiClient } from "@/lib/api-client";
import { useAuth } from "@/hooks/use-auth";

// ─── Types ────────────────────────────────────────────────────────────────────

interface CallSummary {
  call_id: string;
  date: string | null;
  call_type: string | null;
  call_result: string | null;
  call_owner: string | null;
  transcript_quality: string | null;
  processed_date: string | null;
  insights_count: number;
}

interface CallsResponse {
  data: CallSummary[];
  pagination: { total: number; page: number; limit: number };
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  } catch {
    return iso;
  }
}

async function downloadTranscript(callId: string): Promise<void> {
  const token = apiClient.getToken();
  const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";
  const headers: HeadersInit = {};
  if (token !== null) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${apiBase}/ci/calls/${callId}/transcript.txt`, {
    method: "GET",
    headers,
  });
  if (!res.ok) {
    alert(res.status === 404 ? "No transcript on file for this call." : `Download failed (${res.status})`);
    return;
  }

  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${callId}.txt`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

// ─── Empty state ──────────────────────────────────────────────────────────────

function EmptyCallsList() {
  return (
    <div className="flex flex-col items-center justify-center py-16 gap-3">
      <span className="text-4xl" aria-hidden="true">
        📞
      </span>
      <p className="text-sm font-medium text-gray-500">No calls analyzed yet.</p>
      <p className="text-xs text-gray-400">
        Submit your first recording above.
      </p>
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function SalesCallsPage() {
  const { isLoading: authLoading } = useAuth();
  const [calls, setCalls] = useState<CallSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(true);

  const loadCalls = useCallback(async () => {
    try {
      const result = await apiClient.get<CallsResponse>(
        "/ci/calls?call_type=Sales&limit=50",
        { silent: true },
      );
      setCalls(result.data);
      setTotal(result.pagination.total);
    } catch {
      // Leave list empty on error — empty state will render.
      setCalls([]);
      setTotal(0);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (authLoading) return;
    void loadCalls();
  }, [authLoading, loadCalls]);

  function handleUploadSuccess(result: TranscriptUploadResult) {
    // Refresh the list so the newly uploaded call appears.
    void result;
    void loadCalls();
  }

  return (
    <>
      <Header title="Sales Calls" />

      <main className="flex-1 overflow-y-auto p-7 space-y-6">
        {/* Page heading */}
        <div>
          <h1 className="text-xl font-bold text-gray-900">Sales Calls</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Transcribe and analyze your sales recordings to surface insights and coaching opportunities.
          </p>
        </div>

        {/* Upload widget */}
        <TranscriptUploadWidget
          callType="Sales"
          onSuccess={handleUploadSuccess}
        />

        {/* Calls list section */}
        <section aria-label="Analyzed calls">
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
            {/* Section header */}
            <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
              <h2 className="text-sm font-bold text-gray-900">Analyzed Calls</h2>
              <span className="text-xs text-gray-400">
                {isLoading ? "Loading…" : `${total} call${total === 1 ? "" : "s"}`}
              </span>
            </div>

            {/* Empty state / list */}
            {isLoading ? (
              <div className="px-5 py-8 text-xs text-gray-400">Loading calls…</div>
            ) : calls.length === 0 ? (
              <EmptyCallsList />
            ) : (
              <div className="divide-y divide-gray-100">
                {calls.map((call) => (
                  <div
                    key={call.call_id}
                    className="px-5 py-3 flex items-center justify-between gap-4 hover:bg-gray-50 transition-colors"
                  >
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <p className="text-sm font-medium text-gray-900 truncate">
                          {call.call_type ?? "Call"} — {formatDate(call.date)}
                        </p>
                        {call.processed_date && (
                          <span className="text-[10px] font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded bg-emerald-50 text-emerald-700 border border-emerald-200">
                            Processed
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-gray-500 mt-0.5">
                        {call.call_result ?? "No result"}
                        {call.call_owner ? ` · ${call.call_owner}` : ""}
                        {` · ${call.insights_count} insight${call.insights_count === 1 ? "" : "s"}`}
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={() => void downloadTranscript(call.call_id)}
                      className="shrink-0 text-xs font-medium text-indigo-600 hover:text-indigo-700 underline underline-offset-2"
                    >
                      Download transcript
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </section>
      </main>
    </>
  );
}
