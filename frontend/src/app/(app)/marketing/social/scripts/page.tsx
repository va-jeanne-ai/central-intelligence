"use client";

import { useState } from "react";
import { Header } from "@/components/layout/header";
import { apiClient } from "@/lib/api-client";
import { showApiError } from "@/lib/toast";
import { Button } from "@/components/ui/button";
import { SparkleIcon } from "@/components/ui/sparkle-icon";
import { GeneratorHeader, GenerateButton, ResultsPanel } from "@/components/marketing/generator-layout";
import { GeneratedOutput } from "@/components/marketing/generated-output";
import type { SocialAnalyzeResponse } from "@/types";

// ─── Constants ────────────────────────────────────────────────────────────────

const PLATFORMS = ["Instagram", "TikTok", "YouTube", "LinkedIn"] as const;
type Platform = (typeof PLATFORMS)[number];

const BRAND_VOICES = ["Professional", "Casual", "Energetic", "Inspiring"] as const;
type BrandVoice = (typeof BRAND_VOICES)[number];

// ─── Form state ─────────────────────────────────────────────────────────────

interface FormState {
  platform: Platform;
  brandVoice: BrandVoice;
  topic: string;
}

interface ResultMeta {
  platform: Platform;
  brandVoice: BrandVoice;
  topic: string;
  script: string;
}

type ResultStatus = "empty" | "loading" | "error" | "content";

// ─── Generated script card ────────────────────────────────────────────────────

function GeneratedScriptCard({
  meta,
  onRegenerate,
}: {
  meta: ResultMeta;
  onRegenerate: () => void;
}) {
  return (
    <div className="p-5">
      <div className="bg-white rounded-xl border border-emerald-200 shadow-sm overflow-hidden">
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100 bg-emerald-50">
          <div className="flex items-center gap-2">
            <span className="text-base" aria-hidden="true">
              ✨
            </span>
            <h3 className="text-sm font-bold text-gray-900">Generated Script</h3>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-[11px] font-medium px-2 py-0.5 rounded-full bg-white border border-emerald-200 text-emerald-700">
              {meta.platform}
            </span>
            <span className="text-[11px] font-medium px-2 py-0.5 rounded-full bg-white border border-gray-200 text-gray-600">
              {meta.brandVoice}
            </span>
          </div>
        </div>
        <GeneratedOutput
          markdown={meta.script}
          heading={
            meta.topic !== "" ? (
              <p className="text-xs text-gray-400 truncate">
                Topic: <span className="font-medium text-gray-600">{meta.topic}</span>
              </p>
            ) : undefined
          }
        />
        <div className="px-5 pb-4">
          <Button variant="ai" size="sm" onClick={onRegenerate}>
            <SparkleIcon />
            Regenerate
          </Button>
        </div>
      </div>
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function SocialScriptsPage() {
  const [form, setForm] = useState<FormState>({
    platform: "Instagram",
    brandVoice: "Casual",
    topic: "",
  });
  const [status, setStatus] = useState<ResultStatus>("empty");
  const [resultMeta, setResultMeta] = useState<ResultMeta | null>(null);

  const isGenerating = status === "loading";

  async function handleGenerate() {
    if (form.topic.trim() === "") return;
    setStatus("loading");

    try {
      const result = await apiClient.post<SocialAnalyzeResponse>(
        "/social",
        {
          topic: form.topic,
          platform: form.platform.toLowerCase(),
          brand_voice: form.brandVoice.toLowerCase(),
        },
        // Director → specialist agent chains run 30s+; the default 30s
        // timeout aborts right as the script lands (see analyze drawer).
        { silent: true, timeout: 120_000 },
      );

      // Backend currently echoes the same text into both `analysis` and
      // `script`. Prefer `script`; fall through to `analysis`.
      const script = result.script || result.analysis || "No script generated. Try again.";
      setResultMeta({ ...form, script });
      setStatus("content");
    } catch (err) {
      showApiError(err instanceof Error ? err.message : "Failed to generate script.");
      setStatus("error");
    }
  }

  return (
    <>
      <Header title="Social Media" />

      <main className="flex-1 overflow-y-auto p-7 space-y-6">
        <GeneratorHeader
          title="AI Script Generator"
          description="Generate platform-optimized social media scripts tailored to your brand voice."
        />

        {/* Generator form card */}
        <section aria-label="Script generator form">
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5">
            <h2 className="text-sm font-bold text-gray-900 mb-5">Configure Script</h2>

            <div className="grid grid-cols-2 gap-5 mb-5">
              {/* Platform selector */}
              <div className="flex flex-col gap-1.5">
                <label
                  htmlFor="script-platform"
                  className="text-[10px] font-bold uppercase tracking-wider text-emerald-600"
                >
                  Platform
                </label>
                <select
                  id="script-platform"
                  value={form.platform}
                  onChange={(e) =>
                    setForm((prev) => ({ ...prev, platform: e.target.value as Platform }))
                  }
                  className="text-sm border border-gray-200 rounded-lg px-3 py-2 bg-white text-gray-700 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent"
                >
                  {PLATFORMS.map((p) => (
                    <option key={p} value={p}>
                      {p}
                    </option>
                  ))}
                </select>
              </div>

              {/* Brand voice selector */}
              <div className="flex flex-col gap-1.5">
                <label
                  htmlFor="script-voice"
                  className="text-[10px] font-bold uppercase tracking-wider text-emerald-600"
                >
                  Brand Voice
                </label>
                <select
                  id="script-voice"
                  value={form.brandVoice}
                  onChange={(e) =>
                    setForm((prev) => ({ ...prev, brandVoice: e.target.value as BrandVoice }))
                  }
                  className="text-sm border border-gray-200 rounded-lg px-3 py-2 bg-white text-gray-700 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent"
                >
                  {BRAND_VOICES.map((v) => (
                    <option key={v} value={v}>
                      {v}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* Topic / Goal textarea */}
            <div className="flex flex-col gap-1.5 mb-5">
              <label
                htmlFor="script-topic"
                className="text-[10px] font-bold uppercase tracking-wider text-emerald-600"
              >
                Topic / Goal
              </label>
              <textarea
                id="script-topic"
                value={form.topic}
                onChange={(e) => setForm((prev) => ({ ...prev, topic: e.target.value }))}
                placeholder="Describe what you want this script to achieve — e.g. promote a free challenge, share a transformation story, announce a new offer..."
                rows={4}
                className="text-sm border border-gray-200 rounded-lg px-3 py-2.5 bg-white text-gray-700 placeholder:text-gray-400 resize-none focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent"
              />
            </div>

            <GenerateButton
              onClick={handleGenerate}
              disabled={form.topic.trim() === ""}
              isGenerating={isGenerating}
              idleLabel="Generate Script"
            />
          </div>
        </section>

        {/* Generated scripts area */}
        <section aria-label="Generated scripts">
          <ResultsPanel
            title="Generated Scripts"
            status={status}
            emptyIcon="✍️"
            emptyTitle="No scripts generated yet."
            emptyDescription="Fill in the form above and click Generate."
            errorDescription="Something went wrong generating the script. Try again."
          >
            {resultMeta && (
              <GeneratedScriptCard meta={resultMeta} onRegenerate={handleGenerate} />
            )}
          </ResultsPanel>
        </section>
      </main>
    </>
  );
}
