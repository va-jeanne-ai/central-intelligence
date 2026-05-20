"use client";

import { useState } from "react";
import Link from "next/link";
import { Header } from "@/components/layout/header";
import { apiClient } from "@/lib/api-client";

// ─── AI assist pill ───────────────────────────────────────────────────────────

function Spinner() {
  return (
    <svg
      className="animate-spin w-4 h-4"
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
      aria-hidden="true"
    >
      <circle
        className="opacity-25"
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        strokeWidth="4"
      />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
      />
    </svg>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

interface DraftSuggestion {
  subject: string;
  body: string;
  cta: string | null;
}

export default function EmailComposePage() {
  const [segment, setSegment] = useState("");
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [isAssisting, setIsAssisting] = useState(false);
  const [aiSuggestion, setAiSuggestion] = useState<DraftSuggestion | null>(null);
  const [assistError, setAssistError] = useState<string | null>(null);
  const [savedDraft, setSavedDraft] = useState(false);

  async function handleAiAssist() {
    if (isAssisting) return;
    setIsAssisting(true);
    setAiSuggestion(null);
    setAssistError(null);

    try {
      // /email/draft returns structured { subject, body, cta? } — the right
      // shape for the compose form. /email returns markdown analysis (good for
      // dashboards, wrong shape for a draft form).
      const result = await apiClient.post<DraftSuggestion>(
        "/email/draft",
        {
          // EmailDraftRequest: subject is the *seed* (topic/idea), audience optional.
          subject: subject.trim() || "Write a re-engagement email to past leads",
          audience: segment.trim() || undefined,
          tone: "warm professional",
        },
        {
          silent: true,
          // Director tool-use loop runs longer than the 30s default.
          timeout: 120_000,
        },
      );
      setAiSuggestion(result);
    } catch {
      setAssistError("AI Assist failed. Try again or check your network.");
    } finally {
      setIsAssisting(false);
    }
  }

  function handleApplySuggestion() {
    if (aiSuggestion === null) return;
    // Overwrite the form fields — that's the intent of "Apply to Draft".
    // Earlier guarded behaviour (only fill if empty) was a silent foot-gun.
    setSubject(aiSuggestion.subject);
    let nextBody = aiSuggestion.body;
    if (aiSuggestion.cta) {
      // Append the CTA as a trailing line so the user can see/edit it.
      nextBody = `${nextBody.trimEnd()}\n\n${aiSuggestion.cta}`;
    }
    setBody(nextBody);
    setAiSuggestion(null);
    setAssistError(null);
  }

  function handleSaveDraft() {
    setSavedDraft(true);
    setTimeout(() => setSavedDraft(false), 2500);
  }

  return (
    <>
      <Header title="Email" />

      <main className="flex-1 overflow-y-auto p-7 space-y-6">
        {/* Page heading */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-gray-900">Compose Email</h1>
            <p className="text-sm text-gray-500 mt-0.5">
              Draft a new email campaign for your subscriber list.
            </p>
          </div>
          <Link
            href="/marketing/email"
            className="text-sm font-medium text-gray-500 hover:text-gray-700 transition-colors"
          >
            ← Back to Email
          </Link>
        </div>

        {/* Compose form */}
        <section aria-label="Email compose form">
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5 space-y-5">
            {/* To / Segment */}
            <div className="flex flex-col gap-1.5">
              <label
                htmlFor="email-segment"
                className="text-[10px] font-bold uppercase tracking-wider text-emerald-600"
              >
                To / Segment
              </label>
              <input
                id="email-segment"
                type="text"
                value={segment}
                onChange={(e) => setSegment(e.target.value)}
                placeholder="Segment or email list — e.g. All Subscribers, Active Members"
                className="text-sm border border-gray-200 rounded-lg px-3 py-2.5 bg-white text-gray-700 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent"
              />
            </div>

            {/* Subject line */}
            <div className="flex flex-col gap-1.5">
              <label
                htmlFor="email-subject"
                className="text-[10px] font-bold uppercase tracking-wider text-emerald-600"
              >
                Subject Line
              </label>
              <input
                id="email-subject"
                type="text"
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
                placeholder="Write a compelling subject line…"
                className="text-sm border border-gray-200 rounded-lg px-3 py-2.5 bg-white text-gray-700 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent"
              />
            </div>

            {/* Body */}
            <div className="flex flex-col gap-1.5">
              <div className="flex items-center justify-between">
                <label
                  htmlFor="email-body"
                  className="text-[10px] font-bold uppercase tracking-wider text-emerald-600"
                >
                  Body
                </label>
                <button
                  type="button"
                  onClick={handleAiAssist}
                  disabled={isAssisting}
                  className="inline-flex items-center gap-1.5 text-xs font-medium px-3 py-1 bg-emerald-50 hover:bg-emerald-100 disabled:bg-gray-50 disabled:text-gray-400 text-emerald-700 border border-emerald-200 disabled:border-gray-200 rounded-lg transition-colors duration-150"
                >
                  {isAssisting ? (
                    <>
                      <Spinner />
                      Thinking…
                    </>
                  ) : (
                    <>
                      <span aria-hidden="true">✨</span>
                      AI Assist
                    </>
                  )}
                </button>
              </div>
              <textarea
                id="email-body"
                value={body}
                onChange={(e) => setBody(e.target.value)}
                placeholder="Write your email body here…"
                style={{ minHeight: "200px" }}
                className="text-sm border border-gray-200 rounded-lg px-3 py-2.5 bg-white text-gray-700 placeholder:text-gray-400 resize-y focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent"
              />
            </div>

            {/* AI assist error */}
            {assistError !== null && (
              <div className="border border-red-200 rounded-lg bg-red-50 p-3">
                <p className="text-xs text-red-700">{assistError}</p>
              </div>
            )}

            {/* AI suggestion panel */}
            {aiSuggestion !== null && (
              <div className="border border-emerald-200 rounded-lg bg-emerald-50 p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <p className="text-xs font-bold text-emerald-700 uppercase tracking-wider">
                    AI Suggestion
                  </p>
                  <button
                    type="button"
                    onClick={() => setAiSuggestion(null)}
                    className="text-xs text-gray-400 hover:text-gray-600 transition-colors"
                    aria-label="Dismiss suggestion"
                  >
                    Dismiss
                  </button>
                </div>
                <div className="space-y-2">
                  <div>
                    <p className="text-[10px] font-bold uppercase tracking-wider text-emerald-700 mb-1">
                      Subject
                    </p>
                    <p className="text-sm font-semibold text-gray-900">
                      {aiSuggestion.subject}
                    </p>
                  </div>
                  <div>
                    <p className="text-[10px] font-bold uppercase tracking-wider text-emerald-700 mb-1">
                      Body
                    </p>
                    <pre className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap font-sans">
                      {aiSuggestion.body}
                    </pre>
                  </div>
                  {aiSuggestion.cta && (
                    <div>
                      <p className="text-[10px] font-bold uppercase tracking-wider text-emerald-700 mb-1">
                        CTA
                      </p>
                      <p className="text-sm font-medium text-gray-900">
                        {aiSuggestion.cta}
                      </p>
                    </div>
                  )}
                </div>
                <button
                  type="button"
                  onClick={handleApplySuggestion}
                  className="text-xs font-medium px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg transition-colors duration-150"
                >
                  Apply to Draft
                </button>
              </div>
            )}

            {/* Action buttons */}
            <div className="flex items-center gap-3 pt-1">
              <button
                type="button"
                className="inline-flex items-center gap-1.5 px-5 py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white text-sm font-semibold rounded-lg transition-colors duration-150 active:scale-95 shadow-sm"
              >
                <span aria-hidden="true">📤</span>
                Send
              </button>
              <button
                type="button"
                onClick={handleSaveDraft}
                className="inline-flex items-center gap-1.5 px-5 py-2.5 border border-gray-200 hover:bg-gray-50 text-gray-700 text-sm font-semibold rounded-lg transition-colors duration-150 active:scale-95"
              >
                {savedDraft ? (
                  <>
                    <span aria-hidden="true">✓</span>
                    Saved
                  </>
                ) : (
                  "Save Draft"
                )}
              </button>
            </div>
          </div>
        </section>
      </main>
    </>
  );
}
