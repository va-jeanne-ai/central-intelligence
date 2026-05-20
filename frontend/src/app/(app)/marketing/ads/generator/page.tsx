"use client";

import { useState } from "react";
import Link from "next/link";
import { Header } from "@/components/layout/header";
import { apiClient } from "@/lib/api-client";
import type { AdsAnalyzeResponse } from "@/types";

// ─── Constants ────────────────────────────────────────────────────────────────

const AD_PLATFORMS = ["Google", "Facebook", "Instagram", "TikTok", "LinkedIn"] as const;
type AdPlatform = (typeof AD_PLATFORMS)[number];

const CAMPAIGN_GOALS = ["Awareness", "Traffic", "Conversions", "Retargeting"] as const;
type CampaignGoal = (typeof CAMPAIGN_GOALS)[number];

const BRAND_VOICES = ["Professional", "Casual", "Energetic", "Bold"] as const;
type BrandVoice = (typeof BRAND_VOICES)[number];

// ─── Mock variant data ─────────────────────────────────────────────────────────

interface AdVariant {
  label: string;
  angle: string;
  headline: string;
  body: string;
  cta: string;
}

const MOCK_VARIANTS: AdVariant[] = [
  {
    label: "Variant A",
    angle: "Awareness",
    headline: "Transform Your Business in 90 Days",
    body: "Join 500+ coaches who scaled with our proven system. Results guaranteed or your money back.",
    cta: "Learn More",
  },
  {
    label: "Variant B",
    angle: "Conversions",
    headline: "Limited Spots — Apply Now",
    body: "Only 5 clients accepted this month. Discover how our clients 3x their revenue without burnout.",
    cta: "Apply Today",
  },
  {
    label: "Variant C",
    angle: "Retargeting",
    headline: "Still Thinking About It?",
    body: "You've seen what's possible. Take the first step — book a free strategy call and get your custom roadmap.",
    cta: "Book My Call",
  },
];

// ─── Form state ───────────────────────────────────────────────────────────────

interface FormState {
  platform: AdPlatform;
  goal: CampaignGoal;
  brandVoice: BrandVoice;
  context: string;
}

// ─── Ad variant card ──────────────────────────────────────────────────────────

function AdVariantCard({ variant }: { variant: AdVariant }) {
  return (
    <div className="bg-white rounded-xl border border-emerald-200 shadow-sm overflow-hidden">
      <div className="flex items-center justify-between px-5 py-3 border-b border-gray-100 bg-emerald-50">
        <div className="flex items-center gap-2">
          <span className="text-base" aria-hidden="true">
            ✨
          </span>
          <h3 className="text-sm font-bold text-gray-900">{variant.label}</h3>
        </div>
        <span className="text-[11px] font-medium px-2 py-0.5 rounded-full bg-white border border-emerald-200 text-emerald-700">
          {variant.angle}
        </span>
      </div>
      <div className="px-5 py-4 flex flex-col gap-3">
        <div className="flex flex-col gap-0.5">
          <span className="text-[10px] font-bold uppercase tracking-wider text-emerald-600">
            Headline
          </span>
          <p className="text-sm font-semibold text-gray-900">{variant.headline}</p>
        </div>
        <div className="flex flex-col gap-0.5">
          <span className="text-[10px] font-bold uppercase tracking-wider text-emerald-600">
            Body
          </span>
          <p className="text-sm text-gray-700 leading-relaxed">{variant.body}</p>
        </div>
        <div className="flex flex-col gap-0.5">
          <span className="text-[10px] font-bold uppercase tracking-wider text-emerald-600">
            CTA
          </span>
          <p className="text-sm font-semibold text-gray-900">{variant.cta}</p>
        </div>
        <div className="pt-1">
          <button
            type="button"
            onClick={() => {
              const text = `${variant.headline}\n\n${variant.body}\n\n${variant.cta}`;
              void navigator.clipboard.writeText(text);
            }}
            className="text-xs font-medium px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg transition-colors duration-150"
          >
            Copy
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Variants empty state ─────────────────────────────────────────────────────

function VariantsEmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-16 gap-3">
      <span className="text-4xl" aria-hidden="true">
        📢
      </span>
      <p className="text-sm font-medium text-gray-500">No variants generated yet.</p>
      <p className="text-xs text-gray-400">
        Fill in the form above and click Generate Variants.
      </p>
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
  const [isGenerating, setIsGenerating] = useState(false);
  const [hasResult, setHasResult] = useState(false);

  async function handleGenerate() {
    if (form.context.trim() === "") return;
    setIsGenerating(true);
    setHasResult(false);

    try {
      await apiClient.post<AdsAnalyzeResponse>("/ads", {
        action: "generate_copy",
        platform: form.platform,
        goal: form.goal,
        context: form.context,
      }, { silent: true });

      // API succeeded — show mock variants (real API returns analysis, not structured variants yet)
      setIsGenerating(false);
      setHasResult(true);
    } catch {
      // Fall back to mock variants on error.
      setIsGenerating(false);
      setHasResult(true);
    }
  }

  async function handleRegenerate() {
    setIsGenerating(true);
    setHasResult(false);

    try {
      await apiClient.post<AdsAnalyzeResponse>("/ads", {
        action: "generate_copy",
        platform: form.platform,
        goal: form.goal,
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
      <Header title="Ads" />

      <main className="flex-1 overflow-y-auto p-7 space-y-6">
        {/* Page heading */}
        <div>
          <Link
            href="/marketing/ads"
            className="inline-flex items-center gap-1 text-xs font-medium text-emerald-600 hover:text-emerald-700 transition-colors mb-2"
          >
            <span aria-hidden="true">←</span>
            Back to Ads
          </Link>
          <h1 className="text-xl font-bold text-gray-900">AI Ad Copy Generator</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Generate compelling ad variants tailored to your platform and campaign goals.
          </p>
        </div>

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

            {/* Generate button */}
            <button
              type="button"
              onClick={handleGenerate}
              disabled={form.context.trim() === "" || isGenerating}
              className="inline-flex items-center gap-2 px-5 py-2.5 bg-emerald-600 hover:bg-emerald-700 disabled:bg-emerald-200 disabled:cursor-not-allowed text-white text-sm font-semibold rounded-lg transition-colors duration-150 active:scale-95 shadow-sm"
            >
              {isGenerating ? (
                <>
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
                  Generating…
                </>
              ) : (
                <>
                  <span aria-hidden="true">✨</span>
                  Generate Variants
                </>
              )}
            </button>
          </div>
        </section>

        {/* Generated variants area */}
        <section aria-label="Generated ad variants">
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
            <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
              <h2 className="text-sm font-bold text-gray-900">Generated Variants</h2>
              {hasResult && (
                <span className="text-xs text-gray-400">3 variants</span>
              )}
            </div>

            {hasResult ? (
              <div className="p-5 flex flex-col gap-4">
                {MOCK_VARIANTS.map((variant) => (
                  <AdVariantCard key={variant.label} variant={variant} />
                ))}
                <div className="pt-1">
                  <button
                    type="button"
                    onClick={handleRegenerate}
                    disabled={isGenerating}
                    className="text-xs font-medium px-3 py-1.5 border border-gray-200 text-gray-600 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg transition-colors duration-150"
                  >
                    Regenerate
                  </button>
                </div>
              </div>
            ) : (
              <VariantsEmptyState />
            )}
          </div>
        </section>
      </main>
    </>
  );
}
