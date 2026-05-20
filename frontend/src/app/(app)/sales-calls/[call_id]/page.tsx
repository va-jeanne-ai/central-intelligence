"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Header } from "@/components/layout/header";
import { apiClient } from "@/lib/api-client";
import { useAuth } from "@/hooks/use-auth";

// ─── Types ────────────────────────────────────────────────────────────────────

interface CallDetail {
  call_id: string;
  date: string | null;
  call_type: string | null;
  call_result: string | null;
  call_owner: string | null;
  transcript_quality: string | null;
  processed_date: string | null;
  transcript: string | null;
  summary: string | null;
  created_at: string | null;
}

interface InsightBrief {
  insight_id: string;
  insight_type: string | null;
  signal_family: string | null;
  signal: string | null;
  raw_quote: string | null;
}

interface ContentIdeaBrief {
  content_id: string;
  content_format: string | null;
  status: string | null;
  priority_level: string | null;
  idea_score: number | null;
}

interface CallDetailResponse {
  call: CallDetail;
  insights: InsightBrief[];
  content_ideas: ContentIdeaBrief[];
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "numeric",
      minute: "2-digit",
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

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function CallDetailPage({ params }: { params: { call_id: string } }) {
  const { isLoading: authLoading } = useAuth();
  const callId = params.call_id;

  const [detail, setDetail] = useState<CallDetailResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isReanalyzing, setIsReanalyzing] = useState(false);

  const load = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await apiClient.get<CallDetailResponse>(`/ci/calls/${callId}`, {
        silent: true,
      });
      setDetail(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load call.");
    } finally {
      setIsLoading(false);
    }
  }, [callId]);

  useEffect(() => {
    if (authLoading) return;
    void load();
  }, [authLoading, load]);

  async function handleReanalyze() {
    setIsReanalyzing(true);
    try {
      await apiClient.post(`/ci/calls/${callId}/analyze`, {}, { silent: true });
      // Re-poll a few times so the page reflects the new run when Celery finishes.
      // Conservative: 5 attempts, 6s apart.
      for (let i = 0; i < 5; i += 1) {
        await new Promise((r) => setTimeout(r, 6000));
        await load();
      }
    } catch (err) {
      alert(err instanceof Error ? err.message : "Re-analyze failed.");
    } finally {
      setIsReanalyzing(false);
    }
  }

  if (isLoading) {
    return (
      <>
        <Header title="Call detail" />
        <main className="flex-1 overflow-y-auto p-7">
          <p className="text-sm text-gray-400">Loading…</p>
        </main>
      </>
    );
  }

  if (error || detail === null) {
    return (
      <>
        <Header title="Call detail" />
        <main className="flex-1 overflow-y-auto p-7 space-y-4">
          <Link href="/sales-calls" className="text-sm text-indigo-600 hover:text-indigo-700 underline underline-offset-2">
            ← Back to calls
          </Link>
          <p className="text-sm text-red-700">{error ?? "Call not found."}</p>
        </main>
      </>
    );
  }

  const { call, insights, content_ideas } = detail;

  return (
    <>
      <Header title="Call detail" />

      <main className="flex-1 overflow-y-auto p-7 space-y-6">
        {/* Back link */}
        <Link
          href="/sales-calls"
          className="inline-block text-xs font-medium text-indigo-600 hover:text-indigo-700 underline underline-offset-2"
        >
          ← Back to calls
        </Link>

        {/* Header */}
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <h1 className="text-xl font-bold text-gray-900 truncate">
              {call.call_type ?? "Call"} — {formatDate(call.created_at)}
            </h1>
            <p className="text-xs text-gray-500 mt-0.5 font-mono">{call.call_id}</p>
            <p className="text-xs text-gray-500 mt-1">
              {call.call_owner ?? "Unknown owner"}
              {call.processed_date && (
                <span className="ml-2 text-[10px] font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded bg-emerald-50 text-emerald-700 border border-emerald-200">
                  Processed
                </span>
              )}
            </p>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <button
              type="button"
              onClick={() => void downloadTranscript(call.call_id)}
              className="text-xs font-medium text-indigo-600 hover:text-indigo-700 underline underline-offset-2"
            >
              Download transcript
            </button>
            <button
              type="button"
              onClick={() => void handleReanalyze()}
              disabled={isReanalyzing}
              className="text-xs font-medium px-3 py-1.5 rounded-lg bg-indigo-500 hover:bg-indigo-600 disabled:bg-indigo-200 disabled:cursor-not-allowed text-white transition-colors"
            >
              {isReanalyzing ? "Re-analyzing…" : "Re-analyze"}
            </button>
          </div>
        </div>

        {/* Summary */}
        <section className="bg-white rounded-xl border border-gray-200 shadow-sm p-5">
          <h2 className="text-sm font-bold text-gray-900">Summary</h2>
          {call.summary ? (
            <p className="mt-2 text-sm text-gray-700 whitespace-pre-wrap leading-relaxed">{call.summary}</p>
          ) : (
            <p className="mt-2 text-xs text-gray-400 italic">
              No summary yet. The analyzer writes one alongside insights — if this call shows 0 insights too, the analyzer
              probably hasn't run. Make sure the Celery worker is up, then click Re-analyze.
            </p>
          )}
        </section>

        {/* Insights */}
        <section className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
          <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
            <h2 className="text-sm font-bold text-gray-900">Insights</h2>
            <span className="text-xs text-gray-400">{insights.length}</span>
          </div>
          {insights.length === 0 ? (
            <div className="px-5 py-6 text-xs text-gray-400 italic">No insights extracted yet.</div>
          ) : (
            <div className="divide-y divide-gray-100">
              {insights.map((ins) => (
                <div key={ins.insight_id} className="px-5 py-3">
                  <div className="flex items-center gap-2 flex-wrap">
                    {ins.insight_type && (
                      <span className="text-[10px] font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded bg-indigo-50 text-indigo-700 border border-indigo-200">
                        {ins.insight_type}
                      </span>
                    )}
                    {ins.signal_family && (
                      <span className="text-[10px] text-gray-500">{ins.signal_family}</span>
                    )}
                  </div>
                  {ins.signal && (
                    <p className="text-sm font-medium text-gray-900 mt-1">{ins.signal}</p>
                  )}
                  {ins.raw_quote && (
                    <p className="text-xs text-gray-600 italic mt-1">&ldquo;{ins.raw_quote}&rdquo;</p>
                  )}
                </div>
              ))}
            </div>
          )}
        </section>

        {/* Content ideas */}
        {content_ideas.length > 0 && (
          <section className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
            <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
              <h2 className="text-sm font-bold text-gray-900">Content ideas</h2>
              <span className="text-xs text-gray-400">{content_ideas.length}</span>
            </div>
            <div className="divide-y divide-gray-100">
              {content_ideas.map((idea) => (
                <div key={idea.content_id} className="px-5 py-3 text-sm text-gray-700 flex items-center justify-between">
                  <span>
                    {idea.content_format ?? "Idea"}
                    {idea.priority_level ? ` · ${idea.priority_level}` : ""}
                  </span>
                  {idea.status && <span className="text-xs text-gray-400">{idea.status}</span>}
                </div>
              ))}
            </div>
          </section>
        )}

        {/* Transcript */}
        <section className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
          <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
            <h2 className="text-sm font-bold text-gray-900">Transcript</h2>
            <span className="text-xs text-gray-400">
              {call.transcript ? `${call.transcript.length.toLocaleString()} chars` : "—"}
            </span>
          </div>
          {call.transcript ? (
            <pre className="px-5 py-4 text-xs text-gray-700 whitespace-pre-wrap font-sans leading-relaxed max-h-96 overflow-y-auto">
              {call.transcript}
            </pre>
          ) : (
            <div className="px-5 py-6 text-xs text-gray-400 italic">No transcript on file.</div>
          )}
        </section>
      </main>
    </>
  );
}
