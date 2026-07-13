"use client";

import { useState } from "react";
import { Header } from "@/components/layout/header";
import { apiClient } from "@/lib/api-client";
import { showApiError } from "@/lib/toast";
import { CopyButton, Button } from "@/components/ui/button";
import { SparkleIcon } from "@/components/ui/sparkle-icon";
import { GeneratorHeader, GenerateButton, ResultsPanel } from "@/components/marketing/generator-layout";
import type { AdsAnalyzeResponse } from "@/types";

// ─── Constants ────────────────────────────────────────────────────────────────

const AD_PLATFORMS = ["Google", "Facebook", "Instagram", "TikTok", "LinkedIn"] as const;
type AdPlatform = (typeof AD_PLATFORMS)[number];

const CAMPAIGN_GOALS = ["Awareness", "Traffic", "Conversions", "Retargeting"] as const;
type CampaignGoal = (typeof CAMPAIGN_GOALS)[number];

const BRAND_VOICES = ["Professional", "Casual", "Energetic", "Bold"] as const;
type BrandVoice = (typeof BRAND_VOICES)[number];

// ─── Form state ───────────────────────────────────────────────────────────────

interface FormState {
  platform: AdPlatform;
  goal: CampaignGoal;
  brandVoice: BrandVoice;
  context: string;
}

type ResultStatus = "empty" | "loading" | "error" | "content";

// ─── Analysis result card ─────────────────────────────────────────────────────
// The `/ads` endpoint returns a single markdown-ish `analysis` string (the
// director's copy + reasoning combined) plus `ad_copy` and `recommendations`
// fields that are currently always empty on the backend (see
// backend/app/routes/ads.py). We render exactly what the API gives us and
// omit the sections it doesn't populate — no invented variant cards.

function AnalysisResultCard({ result }: { result: AdsAnalyzeResponse }) {
  return (
    <div className="flex flex-col gap-4 p-5">
      <div className="bg-white rounded-xl border border-emerald-200 shadow-sm overflow-hidden">
        <div className="flex items-center justify-between px-5 py-3 border-b border-gray-100 bg-emerald-50">
          <div className="flex items-center gap-2">
            <span className="text-base" aria-hidden="true">
              ✨
            </span>
            <h3 className="text-sm font-bold text-gray-900">Ad Copy Analysis</h3>
          </div>
          <CopyButton text={result.analysis} label="Copy" />
        </div>
        <div className="px-5 py-4">
          <pre className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap font-sans">
            {result.analysis || "No analysis returned."}
          </pre>
        </div>
      </div>

      {/* ad_copy is a real field but currently always "" on the backend —
          only render it when the API actually populates it. */}
      {result.ad_copy !== "" && (
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
          <div className="px-5 py-3 border-b border-gray-100">
            <h3 className="text-sm font-bold text-gray-900">Ad Copy</h3>
          </div>
          <div className="px-5 py-4">
            <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap">
              {result.ad_copy}
            </p>
          </div>
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
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function AdCopyGeneratorPage() {
  const [form, setForm] = useState<FormState>({
    platform: "Google",
    goal: "Conversions",
    brandVoice: "Professional",
    context: "",
  });
  const [status, setStatus] = useState<ResultStatus>("empty");
  const [result, setResult] = useState<AdsAnalyzeResponse | null>(null);

  const isGenerating = status === "loading";

  async function handleGenerate() {
    if (form.context.trim() === "") return;
    setStatus("loading");

    try {
      const response = await apiClient.post<AdsAnalyzeResponse>(
        "/ads",
        {
          action: "generate_copy",
          platform: form.platform,
          goal: form.goal,
          context: form.context,
        },
        { silent: true },
      );
      setResult(response);
      setStatus("content");
    } catch (err) {
      showApiError(err instanceof Error ? err.message : "Failed to generate ad copy.");
      setStatus("error");
    }
  }

  return (
    <>
      <Header title="Ads" />

      <main className="flex-1 overflow-y-auto p-7 space-y-6">
        <GeneratorHeader
          title="AI Ad Copy Generator"
          description="Generate compelling ad variants tailored to your platform and campaign goals."
          backHref="/marketing/ads"
          backLabel="Back to Ads"
        />

        {/* Generator form card */}
        <section aria-label="Ad copy generator form">
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5">
            <h2 className="text-sm font-bold text-gray-900 mb-5">Configure Ad Copy</h2>

            <div className="grid grid-cols-3 gap-5 mb-5">
              {/* Platform selector */}
              <div className="flex flex-col gap-1.5">
                <label
                  htmlFor="ads-platform"
                  className="text-[10px] font-bold uppercase tracking-wider text-emerald-600"
                >
                  Platform
                </label>
                <select
                  id="ads-platform"
                  value={form.platform}
                  onChange={(e) =>
                    setForm((prev) => ({ ...prev, platform: e.target.value as AdPlatform }))
                  }
                  className="text-sm border border-gray-200 rounded-lg px-3 py-2 bg-white text-gray-700 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent"
                >
                  {AD_PLATFORMS.map((p) => (
                    <option key={p} value={p}>
                      {p}
                    </option>
                  ))}
                </select>
              </div>

              {/* Campaign goal selector */}
              <div className="flex flex-col gap-1.5">
                <label
                  htmlFor="ads-goal"
                  className="text-[10px] font-bold uppercase tracking-wider text-emerald-600"
                >
                  Campaign Goal
                </label>
                <select
                  id="ads-goal"
                  value={form.goal}
                  onChange={(e) =>
                    setForm((prev) => ({ ...prev, goal: e.target.value as CampaignGoal }))
                  }
                  className="text-sm border border-gray-200 rounded-lg px-3 py-2 bg-white text-gray-700 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent"
                >
                  {CAMPAIGN_GOALS.map((g) => (
                    <option key={g} value={g}>
                      {g}
                    </option>
                  ))}
                </select>
              </div>

              {/* Brand voice selector */}
              <div className="flex flex-col gap-1.5">
                <label
                  htmlFor="ads-voice"
                  className="text-[10px] font-bold uppercase tracking-wider text-emerald-600"
                >
                  Brand Voice
                </label>
                <select
                  id="ads-voice"
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

            {/* Campaign context textarea */}
            <div className="flex flex-col gap-1.5 mb-5">
              <label
                htmlFor="ads-context"
                className="text-[10px] font-bold uppercase tracking-wider text-emerald-600"
              >
                Campaign Context
              </label>
              <textarea
                id="ads-context"
                value={form.context}
                onChange={(e) => setForm((prev) => ({ ...prev, context: e.target.value }))}
                placeholder="Describe your product, offer, or campaign — e.g. 30% off summer sale, free discovery call, new coaching program launch..."
                rows={4}
                className="text-sm border border-gray-200 rounded-lg px-3 py-2.5 bg-white text-gray-700 placeholder:text-gray-400 resize-none focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent"
              />
            </div>

            <GenerateButton
              onClick={handleGenerate}
              disabled={form.context.trim() === ""}
              isGenerating={isGenerating}
              idleLabel="Generate Variants"
            />
          </div>
        </section>

        {/* Generated variants area */}
        <section aria-label="Generated ad variants">
          <ResultsPanel
            title="Generated Variants"
            status={status}
            emptyIcon="📢"
            emptyTitle="No variants generated yet."
            emptyDescription="Fill in the form above and click Generate Variants."
            errorDescription="Something went wrong generating ad copy. Try again."
            headerAction={
              <Button variant="ai" size="sm" onClick={handleGenerate} disabled={isGenerating}>
                <SparkleIcon />
                Regenerate
              </Button>
            }
          >
            {result && <AnalysisResultCard result={result} />}
          </ResultsPanel>
        </section>
      </main>
    </>
  );
}
