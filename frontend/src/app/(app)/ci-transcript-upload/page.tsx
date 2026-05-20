"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
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

interface CallDetail {
  call: {
    call_id: string;
    processed_date: string | null;
  };
  insights: unknown[];
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

// ─── Processing status card ───────────────────────────────────────────────────
//
// Lives below the upload widget after a successful upload. Polls the call
// detail every 5s until processed_date lands, then flips to a "ready" state
// linking to /sales-calls/[call_id]. The user can dismiss it manually or
// trigger a new upload (which replaces the card).

interface PendingCall {
  call_id: string;
  // Snapshot of the previous processed_date — null for a fresh upload, set
  // only if we somehow attached this card to an already-processed call.
  baseline: string | null;
}

interface StatusCardProps {
  pending: PendingCall;
  onReady: (insightsCount: number) => void;
  onDismiss: () => void;
}

function StatusCard({ pending, onReady, onDismiss }: StatusCardProps) {
  const [processedDate, setProcessedDate] = useState<string | null>(null);
  const [insightsCount, setInsightsCount] = useState<number>(0);
  const [timedOut, setTimedOut] = useState(false);

  // Keep callback in a ref so changes to it don't restart the poll loop.
  // Without this, every parent re-render would create a new onReady identity,
  // cancel the in-flight poller, and start a fresh one — which (combined with
  // the parent reloading the list inside the same callback) caused the card
  // to never flip to its 'ready' state.
  const onReadyRef = useRef(onReady);
  useEffect(() => {
    onReadyRef.current = onReady;
  }, [onReady]);

  useEffect(() => {
    let cancelled = false;
    const maxAttempts = 36; // ~3 minutes at 5s
    let attempts = 0;

    async function poll() {
      while (!cancelled && attempts < maxAttempts) {
        attempts += 1;
        try {
          const data = await apiClient.get<CallDetail>(
            `/ci/calls/${pending.call_id}`,
            { silent: true },
          );
          if (cancelled) return;
          const pd = data.call.processed_date;
          if (pd && pd !== pending.baseline) {
            setProcessedDate(pd);
            setInsightsCount(data.insights.length);
            onReadyRef.current(data.insights.length);
            return;
          }
        } catch {
          // Swallow — the call might not be visible yet on first poll
        }
        await new Promise((r) => setTimeout(r, 5000));
      }
      if (!cancelled) setTimedOut(true);
    }

    void poll();
    return () => {
      cancelled = true;
    };
  }, [pending.call_id, pending.baseline]);

  const isReady = processedDate !== null;

  return (
    <div
      className={`rounded-xl border p-4 flex items-start gap-3 ${
        isReady
          ? "bg-emerald-50 border-emerald-200"
          : timedOut
            ? "bg-gray-50 border-gray-200"
            : "bg-amber-50 border-amber-200"
      }`}
    >
      {isReady ? (
        <span
          className="w-6 h-6 rounded-full bg-emerald-100 flex items-center justify-center text-emerald-700 shrink-0"
          aria-hidden="true"
        >
          ✓
        </span>
      ) : timedOut ? (
        <span className="text-gray-500 shrink-0">⏱</span>
      ) : (
        <svg
          className="animate-spin w-5 h-5 text-amber-600 shrink-0 mt-0.5"
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 24 24"
          aria-hidden="true"
        >
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
        </svg>
      )}

      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold">
          {isReady
            ? `${pending.call_id} analyzed`
            : timedOut
              ? `${pending.call_id} still processing`
              : `Processing ${pending.call_id}…`}
        </p>
        <p className="text-xs text-gray-600 mt-0.5">
          {isReady ? (
            <>
              {insightsCount} insight{insightsCount === 1 ? "" : "s"} extracted.{" "}
              <Link
                href={`/sales-calls/${pending.call_id}`}
                className="font-medium text-indigo-600 hover:text-indigo-700 underline underline-offset-2"
              >
                View call detail →
              </Link>
            </>
          ) : timedOut ? (
            <>
              The analyzer is taking longer than usual. The Celery worker may be down, or this is a long call.{" "}
              <Link
                href={`/sales-calls/${pending.call_id}`}
                className="font-medium text-indigo-600 hover:text-indigo-700 underline underline-offset-2"
              >
                Open the call detail
              </Link>{" "}
              to check.
            </>
          ) : (
            <>Whisper finished. The analyzer is extracting insights — usually 30–60 seconds.</>
          )}
        </p>
      </div>

      <button
        type="button"
        onClick={onDismiss}
        className="text-xs text-gray-400 hover:text-gray-600 shrink-0"
        aria-label="Dismiss"
      >
        ✕
      </button>
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function CiTranscriptUploadPage() {
  const { isLoading: authLoading } = useAuth();
  const [recentCalls, setRecentCalls] = useState<CallSummary[]>([]);
  const [isLoadingList, setIsLoadingList] = useState(true);
  const [pending, setPending] = useState<PendingCall | null>(null);

  const loadRecent = useCallback(async () => {
    try {
      const result = await apiClient.get<CallsResponse>(
        "/ci/calls?limit=20",
        { silent: true },
      );
      setRecentCalls(result.data);
    } catch {
      setRecentCalls([]);
    } finally {
      setIsLoadingList(false);
    }
  }, []);

  useEffect(() => {
    if (authLoading) return;
    void loadRecent();
  }, [authLoading, loadRecent]);

  function handleUploadSuccess(result: TranscriptUploadResult) {
    if (!result.callId) {
      // No call_id surfaced — likely a URL-based async path that returns a
      // jobId only. Just refresh the list so the call appears once persisted.
      void loadRecent();
      return;
    }
    // Find the previous processed_date for this call (if it already existed,
    // e.g. via the upload widget's dedup-by-hash path returning "duplicate").
    const existing = recentCalls.find((c) => c.call_id === result.callId);
    setPending({
      call_id: result.callId,
      baseline: existing?.processed_date ?? null,
    });
    void loadRecent();
  }

  const handleReady = useCallback(() => {
    // When the analyzer finishes, refresh the recent list so the call's
    // insights_count and Processed badge reflect reality.
    void loadRecent();
  }, [loadRecent]);

  return (
    <>
      <Header title="CI Transcript Upload" />

      <main className="flex-1 overflow-y-auto p-7 space-y-6">
        {/* Page heading */}
        <div>
          <h1 className="text-xl font-bold text-gray-900">CI Transcript Upload</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Upload coaching, discovery, and client call transcripts. The analyzer extracts insights
            automatically and surfaces them on the call detail page.
          </p>
        </div>

        {/* Upload widget */}
        <TranscriptUploadWidget
          callType="Coaching"
          onSuccess={handleUploadSuccess}
        />

        {/* Status card — only when there's a pending upload */}
        {pending && (
          <StatusCard
            key={pending.call_id}
            pending={pending}
            onReady={handleReady}
            onDismiss={() => setPending(null)}
          />
        )}

        {/* Recent uploads section */}
        <section aria-label="Recent uploads">
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
            <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
              <h2 className="text-sm font-bold text-gray-900">Recent Uploads</h2>
              <span className="text-xs text-gray-400">
                {isLoadingList ? "Loading…" : `${recentCalls.length} call${recentCalls.length === 1 ? "" : "s"}`}
              </span>
            </div>

            {isLoadingList ? (
              <div className="px-5 py-8 text-xs text-gray-400">Loading calls…</div>
            ) : recentCalls.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-16 gap-3">
                <span className="text-4xl" aria-hidden="true">
                  📋
                </span>
                <p className="text-sm font-medium text-gray-500">No uploads yet.</p>
                <p className="text-xs text-gray-400">
                  Submit your first transcript above to get started.
                </p>
              </div>
            ) : (
              <div className="divide-y divide-gray-100">
                {recentCalls.map((call) => (
                  <Link
                    key={call.call_id}
                    href={`/sales-calls/${call.call_id}`}
                    className="block px-5 py-3 hover:bg-gray-50 transition-colors"
                  >
                    <div className="flex items-center gap-2">
                      <p className="text-sm font-medium text-gray-900 truncate">
                        {call.call_type ?? "Call"} — {formatDate(call.date ?? call.processed_date)}
                      </p>
                      {call.processed_date && (
                        <span className="text-[10px] font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded bg-emerald-50 text-emerald-700 border border-emerald-200">
                          Processed
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-gray-500 mt-0.5">
                      <span className="font-mono">{call.call_id}</span>
                      {call.call_owner ? ` · ${call.call_owner}` : ""}
                      {` · ${call.insights_count} insight${call.insights_count === 1 ? "" : "s"}`}
                    </p>
                  </Link>
                ))}
              </div>
            )}
          </div>
        </section>
      </main>
    </>
  );
}
