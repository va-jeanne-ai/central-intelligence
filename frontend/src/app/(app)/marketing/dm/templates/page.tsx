"use client";

import { useState } from "react";
import Link from "next/link";
import { Header } from "@/components/layout/header";
import { apiClient } from "@/lib/api-client";
import { showApiError } from "@/lib/toast";
import { CopyButton, Button } from "@/components/ui/button";
import { SparkleIcon } from "@/components/ui/sparkle-icon";
import { GeneratorHeader, GenerateButton, ResultsPanel } from "@/components/marketing/generator-layout";
import { GeneratedOutput } from "@/components/marketing/generated-output";
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

interface ResultMeta {
  sequenceType: SequenceType;
  icpProfile: IcpProfile;
  tone: Tone;
}

type ResultStatus = "empty" | "loading" | "error" | "content";

// ─── Generated template card ──────────────────────────────────────────────────
// The `/dm` endpoint returns a single `analysis` markdown string (the
// director's targeting rationale + message blocks combined) plus a
// `sequence` field that is currently always [] on the backend (see
// backend/app/routes/dm.py — "Message blocks are inline in `analysis`").
// We render the real analysis text and only render a structured sequence
// list if the API ever starts populating it.

function GeneratedTemplateCard({
  meta,
  result,
  onRegenerate,
}: {
  meta: ResultMeta;
  result: DmAnalyzeResponse;
  onRegenerate: () => void;
}) {
  return (
    <div className="p-5 flex flex-col gap-4">
      <div className="bg-white rounded-xl border border-emerald-200 shadow-sm overflow-hidden">
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

        <GeneratedOutput
          markdown={result.analysis || "No sequence generated."}
          heading={
            <span className="text-[10px] font-bold uppercase tracking-wider text-emerald-600">
              Outreach Plan
            </span>
          }
        />
      </div>

      {/* sequence is a real field but currently always [] on the backend —
          only render structured message blocks when the API populates it. */}
      {result.sequence.length > 0 && (
        <div className="flex flex-col gap-3">
          {result.sequence.map((message, i) => (
            <div
              key={i}
              className="rounded-lg border border-gray-100 bg-gray-50 p-4 flex flex-col gap-2"
            >
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-bold uppercase tracking-wider text-emerald-600">
                  Message {i + 1}
                </span>
                <CopyButton text={message} label="Copy" />
              </div>
              <p className="text-sm text-gray-700 leading-relaxed">{message}</p>
            </div>
          ))}
        </div>
      )}

      {/* recommendations is always [] today — only render when populated. */}
      {result.recommendations.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
          <div className="px-5 py-3 border-b border-gray-100">
            <h3 className="text-sm font-bold text-gray-900">Recommendations</h3>
          </div>
          <ul className="px-5 py-4 flex flex-col gap-2">
            {result.recommendations.map((rec, i) => (
              <li key={i} className="text-sm text-gray-700 flex items-start gap-2">
                <span className="text-emerald-500 flex-shrink-0" aria-hidden="true">
                  →
                </span>
                {rec}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="pt-1">
        <Button variant="ai" size="sm" onClick={onRegenerate}>
          <SparkleIcon />
          Regenerate
        </Button>
      </div>
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
  const [status, setStatus] = useState<ResultStatus>("empty");
  const [resultMeta, setResultMeta] = useState<ResultMeta | null>(null);
  const [result, setResult] = useState<DmAnalyzeResponse | null>(null);

  const isGenerating = status === "loading";

  async function handleGenerate() {
    if (form.context.trim() === "") return;
    setStatus("loading");

    try {
      const response = await apiClient.post<DmAnalyzeResponse>(
        "/dm",
        {
          action: "generate_sequence",
          sequence_type: form.sequenceType.toLowerCase(),
          icp_profile: form.icpProfile,
          tone: form.tone.toLowerCase(),
          context: form.context,
        },
        // Director → specialist agent chains run 30s+; the default 30s
        // timeout aborts right as the script lands (see analyze drawer).
        { silent: true, timeout: 120_000 },
      );

      setResultMeta({
        sequenceType: form.sequenceType,
        icpProfile: form.icpProfile,
        tone: form.tone,
      });
      setResult(response);
      setStatus("content");
    } catch (err) {
      showApiError(err instanceof Error ? err.message : "Failed to generate DM template.");
      setStatus("error");
    }
  }

  return (
    <>
      <Header title="DM" />

      <main className="flex-1 overflow-y-auto p-7 space-y-6">
        {/* Page heading with back link */}
        <div className="flex items-start justify-between">
          <GeneratorHeader
            title="DM Template Builder"
            description="Create personalized DM templates for your outreach sequences."
          />
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

            <GenerateButton
              onClick={handleGenerate}
              disabled={form.context.trim() === ""}
              isGenerating={isGenerating}
              idleLabel="Generate Template"
            />
          </div>
        </section>

        {/* Generated template area */}
        <section aria-label="Generated DM template">
          <ResultsPanel
            title="Generated Template"
            status={status}
            emptyIcon="✍️"
            emptyTitle="No template generated yet."
            emptyDescription="Fill in the form above and click Generate."
            errorDescription="Something went wrong generating the DM template. Try again."
          >
            {resultMeta && result && (
              <GeneratedTemplateCard
                meta={resultMeta}
                result={result}
                onRegenerate={handleGenerate}
              />
            )}
          </ResultsPanel>
        </section>
      </main>
    </>
  );
}
