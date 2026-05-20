"use client";

import { useState } from "react";
import Link from "next/link";
import { Header } from "@/components/layout/header";
import { apiClient } from "@/lib/api-client";
import type { DmAnalyzeResponse } from "@/types";

// ─── Constants ────────────────────────────────────────────────────────────────

const SEQUENCE_TYPES = ["Outreach", "Follow-up", "Re-engagement"] as const;
type SequenceType = (typeof SEQUENCE_TYPES)[number];

const ICP_PROFILES = [
  "Fitness Coach",
  "Business Coach",
  "Life Coach",
  "Marketing Agency",
] as const;
type IcpProfile = (typeof ICP_PROFILES)[number];

const TONES = ["Warm", "Direct", "Conversational", "Professional"] as const;
type Tone = (typeof TONES)[number];

// ─── Form state ───────────────────────────────────────────────────────────────

interface FormState {
  sequenceType: SequenceType;
  icpProfile: IcpProfile;
  tone: Tone;
  context: string;
}

// ─── Mock template messages ───────────────────────────────────────────────────

interface TemplateMessage {
  label: string;
  body: string;
}

function buildMockMessages(icpProfile: IcpProfile): TemplateMessage[] {
  return [
    {
      label: "Message 1 — Outreach",
      body: `Hey [First Name]! I came across your profile and loved what you're building. I work with ${icpProfile} coaches to [outcome]. Would you be open to a quick 15-min call to see if there's a fit? No pitch — just a conversation.`,
    },
    {
      label: "Message 2 — Follow-up (Day 3)",
      body: `Hey [First Name], just circling back on my last message! I know things get busy. I've got one spot opening up this week for ${icpProfile} coaches ready to scale. Would love to see if I can help. Worth a chat?`,
    },
    {
      label: "Message 3 — Re-engagement (Day 7)",
      body: `[First Name]! Totally understand if the timing wasn't right. I'm closing out my roster for this month and wanted to give you a last chance to connect. No pressure at all — just reply 'yes' if you'd like to hop on a call.`,
    },
  ];
}

// ─── Spinner ──────────────────────────────────────────────────────────────────

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

// ─── Generated template card ──────────────────────────────────────────────────

interface ResultMeta {
  sequenceType: SequenceType;
  icpProfile: IcpProfile;
  tone: Tone;
}

function GeneratedTemplateCard({
  meta,
  onRegenerate,
}: {
  meta: ResultMeta;
  onRegenerate: () => void;
}) {
  const messages = buildMockMessages(meta.icpProfile);

  function copyToClipboard(text: string) {
    void navigator.clipboard.writeText(text);
  }

  return (
    <div className="bg-white rounded-xl border border-emerald-200 shadow-sm overflow-hidden">
      {/* Card header */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100 bg-emerald-50">
        <div className="flex items-center gap-2">
          <span className="text-base" aria-hidden="true">
            ✨
          </span>
          <h3 className="text-sm font-bold text-gray-900">Generated Template</h3>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[11px] font-medium px-2 py-0.5 rounded-full bg-white border border-emerald-200 text-emerald-700">
            {meta.sequenceType}
          </span>
          <span className="text-[11px] font-medium px-2 py-0.5 rounded-full bg-white border border-gray-200 text-gray-600">
            {meta.icpProfile}
          </span>
          <span className="text-[11px] font-medium px-2 py-0.5 rounded-full bg-white border border-gray-200 text-gray-600">
            {meta.tone}
          </span>
        </div>
      </div>

      {/* Message blocks */}
      <div className="px-5 py-4 flex flex-col gap-4">
        {messages.map((msg) => (
          <div
            key={msg.label}
            className="rounded-lg border border-gray-100 bg-gray-50 p-4 flex flex-col gap-2"
          >
            <div className="flex items-center justify-between">
              <span className="text-[10px] font-bold uppercase tracking-wider text-emerald-600">
                {msg.label}
              </span>
              <button
                type="button"
                onClick={() => copyToClipboard(msg.body)}
                className="text-xs font-medium px-2.5 py-1 border border-gray-200 text-gray-600 hover:bg-white rounded-lg transition-colors duration-150"
              >
                Copy
              </button>
            </div>
            <p className="text-sm text-gray-700 leading-relaxed">{msg.body}</p>
          </div>
        ))}

        {/* Regenerate */}
        <div className="pt-1">
          <button
            type="button"
            onClick={onRegenerate}
            className="text-xs font-medium px-3 py-1.5 border border-gray-200 text-gray-600 hover:bg-gray-50 rounded-lg transition-colors duration-150"
          >
            Regenerate
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Template empty state ─────────────────────────────────────────────────────

function TemplateEmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-16 gap-3">
      <span className="text-4xl" aria-hidden="true">
        ✍️
      </span>
      <p className="text-sm font-medium text-gray-500">No template generated yet.</p>
      <p className="text-xs text-gray-400">Fill in the form above and click Generate.</p>
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function DmTemplatesPage() {
  const [form, setForm] = useState<FormState>({
    sequenceType: "Outreach",
    icpProfile: "Fitness Coach",
    tone: "Warm",
    context: "",
  });
  const [isGenerating, setIsGenerating] = useState(false);
  const [hasResult, setHasResult] = useState(false);
  const [resultMeta, setResultMeta] = useState<ResultMeta | null>(null);

  async function handleGenerate() {
    if (form.context.trim() === "") return;
    setIsGenerating(true);
    setHasResult(false);

    try {
      await apiClient.post<DmAnalyzeResponse>("/dm", {
        action: "generate_sequence",
        sequence_type: form.sequenceType.toLowerCase(),
        icp_profile: form.icpProfile,
        tone: form.tone.toLowerCase(),
        context: form.context,
      }, { silent: true });

      // API succeeded — show result with form meta
      setResultMeta({
        sequenceType: form.sequenceType,
        icpProfile: form.icpProfile,
        tone: form.tone,
      });
      setIsGenerating(false);
      setHasResult(true);
    } catch {
      // Fall back to mock template on error.
      setResultMeta({
        sequenceType: form.sequenceType,
        icpProfile: form.icpProfile,
        tone: form.tone,
      });
      setIsGenerating(false);
      setHasResult(true);
    }
  }

  async function handleRegenerate() {
    if (resultMeta === null) return;
    setIsGenerating(true);
    setHasResult(false);

    try {
      await apiClient.post<DmAnalyzeResponse>("/dm", {
        action: "generate_sequence",
        sequence_type: resultMeta.sequenceType.toLowerCase(),
        icp_profile: resultMeta.icpProfile,
        tone: resultMeta.tone.toLowerCase(),
        context: form.context,
      }, { silent: true });

      setIsGenerating(false);
      setHasResult(true);
    } catch {
      setIsGenerating(false);
      setHasResult(true);
    }
  }

  return (
    <>
      <Header title="DM" />

      <main className="flex-1 overflow-y-auto p-7 space-y-6">
        {/* Page heading with back link */}
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-xl font-bold text-gray-900">DM Template Builder</h1>
            <p className="text-sm text-gray-500 mt-0.5">
              Create personalized DM templates for your outreach sequences.
            </p>
          </div>
          <Link
            href="/marketing/dm"
            className="text-xs font-medium text-emerald-600 hover:text-emerald-700 transition-colors flex-shrink-0 mt-1"
          >
            ← Back to DM
          </Link>
        </div>

        {/* Generator form card */}
        <section aria-label="DM template generator form">
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5">
            <h2 className="text-sm font-bold text-gray-900 mb-5">Configure Template</h2>

            <div className="grid grid-cols-3 gap-5 mb-5">
              {/* Sequence type selector */}
              <div className="flex flex-col gap-1.5">
                <label
                  htmlFor="dm-sequence-type"
                  className="text-[10px] font-bold uppercase tracking-wider text-emerald-600"
                >
                  Sequence Type
                </label>
                <select
                  id="dm-sequence-type"
                  value={form.sequenceType}
                  onChange={(e) =>
                    setForm((prev) => ({
                      ...prev,
                      sequenceType: e.target.value as SequenceType,
                    }))
                  }
                  className="text-sm border border-gray-200 rounded-lg px-3 py-2 bg-white text-gray-700 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent"
                >
                  {SEQUENCE_TYPES.map((s) => (
                    <option key={s} value={s}>
                      {s}
                    </option>
                  ))}
                </select>
              </div>

              {/* ICP profile selector */}
              <div className="flex flex-col gap-1.5">
                <label
                  htmlFor="dm-icp-profile"
                  className="text-[10px] font-bold uppercase tracking-wider text-emerald-600"
                >
                  ICP Profile
                </label>
                <select
                  id="dm-icp-profile"
                  value={form.icpProfile}
                  onChange={(e) =>
                    setForm((prev) => ({
                      ...prev,
                      icpProfile: e.target.value as IcpProfile,
                    }))
                  }
                  className="text-sm border border-gray-200 rounded-lg px-3 py-2 bg-white text-gray-700 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent"
                >
                  {ICP_PROFILES.map((p) => (
                    <option key={p} value={p}>
                      {p}
                    </option>
                  ))}
                </select>
              </div>

              {/* Tone selector */}
              <div className="flex flex-col gap-1.5">
                <label
                  htmlFor="dm-tone"
                  className="text-[10px] font-bold uppercase tracking-wider text-emerald-600"
                >
                  Tone
                </label>
                <select
                  id="dm-tone"
                  value={form.tone}
                  onChange={(e) =>
                    setForm((prev) => ({ ...prev, tone: e.target.value as Tone }))
                  }
                  className="text-sm border border-gray-200 rounded-lg px-3 py-2 bg-white text-gray-700 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent"
                >
                  {TONES.map((t) => (
                    <option key={t} value={t}>
                      {t}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* Campaign context textarea */}
            <div className="flex flex-col gap-1.5 mb-5">
              <label
                htmlFor="dm-context"
                className="text-[10px] font-bold uppercase tracking-wider text-emerald-600"
              >
                Campaign Context
              </label>
              <textarea
                id="dm-context"
                value={form.context}
                onChange={(e) => setForm((prev) => ({ ...prev, context: e.target.value }))}
                placeholder="Describe what you're inviting them to — e.g. free strategy call, limited spots in program, webinar this Thursday..."
                rows={4}
                className="text-sm border border-gray-200 rounded-lg px-3 py-2.5 bg-white text-gray-700 placeholder:text-gray-400 resize-none focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent"
              />
            </div>

            {/* Generate button */}
            <button
              type="button"
              onClick={handleGenerate}
              disabled={form.context.trim() === "" || isGenerating}
              className="inline-flex items-center gap-2 px-5 py-2.5 bg-emerald-600 hover:bg-emerald-700 disabled:bg-emerald-200 disabled:cursor-not-allowed text-white text-sm font-semibold rounded-lg transition-colors duration-150 active:scale-95 shadow-sm"
            >
              {isGenerating ? (
                <>
                  <Spinner />
                  Generating…
                </>
              ) : (
                <>
                  <span aria-hidden="true">✨</span>
                  Generate Template
                </>
              )}
            </button>
          </div>
        </section>

        {/* Generated template area */}
        <section aria-label="Generated DM template">
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
            <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
              <h2 className="text-sm font-bold text-gray-900">Generated Template</h2>
            </div>

            {hasResult && resultMeta !== null ? (
              <div className="p-5">
                <GeneratedTemplateCard meta={resultMeta} onRegenerate={handleRegenerate} />
              </div>
            ) : (
              <TemplateEmptyState />
            )}
          </div>
        </section>
      </main>
    </>
  );
}
