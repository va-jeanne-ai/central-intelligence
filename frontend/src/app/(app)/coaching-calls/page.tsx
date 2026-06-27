"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Header } from "@/components/layout/header";
import { TranscriptUploadWidget } from "@/components/upload/transcript-upload-widget";
import type { TranscriptUploadResult } from "@/components/upload/transcript-upload-widget";
import { apiClient } from "@/lib/api-client";
import { useAuth } from "@/hooks/use-auth";
import { usePagination } from "@/hooks/use-pagination";
import { Pagination } from "@/components/ui";
import { showError, showWarning } from "@/lib/toast";

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
    if (res.status === 404) {
      showWarning("No transcript on file for this call.");
    } else {
      showError(`Download failed (${res.status})`);
    }
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
        🎯
      </span>
      <p className="text-sm font-medium text-gray-500">No coaching calls analyzed yet.</p>
      <p className="text-xs text-gray-400">Submit your first coaching session above.</p>
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function CoachingCallsPage() {
  const { isLoading: authLoading } = useAuth();
  const [calls, setCalls] = useState<CallSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(true);

  // Pagination — page/pageSize persisted per surface via the shared hook.
  const { page, pageSize, setPage, setPageSize } = usePagination("coaching-calls");

  const loadCalls = useCallback(async () => {
    setIsLoading(true);
    try {
      const params = new URLSearchParams();
      params.set("call_type", "Coaching");
      params.set("page", String(page));
      params.set("limit", String(pageSize));

      const result = await apiClient.get<CallsResponse>(
        `/ci/calls?${params.toString()}`,
        { silent: true },
      );
      setCalls(result.data);
      setTotal(result.pagination.total);
    } catch {
      setCalls([]);
      setTotal(0);
    } finally {
      setIsLoading(false);
    }
  }, [page, pageSize]);

  useEffect(() => {
    if (authLoading) return;
    void loadCalls();
  }, [authLoading, loadCalls]);

  function handleUploadSuccess(result: TranscriptUploadResult) {
    void result;
    void loadCalls();
  }

  return (
    <>
      <Header title="Coaching Calls" />

      <main className="flex-1 overflow-y-auto p-7 space-y-6">
        {/* Page heading */}
        <div>
          <h1 className="text-xl font-bold text-gray-900">Coaching Calls</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Transcribe and analyze coaching sessions to surface member wins, breakthroughs, and blocks.
          </p>
        </div>

        {/* Upload widget — pre-set to Coaching call type */}
        <TranscriptUploadWidget callType="Coaching" onSuccess={handleUploadSuccess} />

        {/* Calls list section */}
        <section aria-label="Analyzed coaching calls">
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
            <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
              <h2 className="text-sm font-bold text-gray-900">Analyzed Coaching Calls</h2>
              <span className="text-xs text-gray-400">
                {isLoading ? "Loading…" : `${total} call${total === 1 ? "" : "s"}`}
              </span>
            </div>

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
                    <Link href={`/coaching-calls/${call.call_id}`} className="flex-1 min-w-0 group">
                      <div className="flex items-center gap-2">
                        <p className="text-sm font-medium text-gray-900 truncate group-hover:text-orange-700">
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
                    </Link>
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        void downloadTranscript(call.call_id);
                      }}
                      className="shrink-0 text-xs font-medium text-orange-600 hover:text-orange-700 underline underline-offset-2"
                    >
                      Download transcript
                    </button>
                  </div>
                ))}
              </div>
            )}

            {!isLoading && total > 0 && (
              <Pagination
                page={page}
                total={total}
                pageSize={pageSize}
                onPageChange={setPage}
                onPageSizeChange={setPageSize}
              />
            )}
          </div>
        </section>
      </main>
    </>
  );
}
