"use client";

import { useState } from "react";
import { Header } from "@/components/layout/header";
import { apiClient } from "@/lib/api-client";

// ─── Constants ────────────────────────────────────────────────────────────────

const PLATFORMS = ["Instagram", "TikTok", "YouTube", "LinkedIn"] as const;
type Platform = (typeof PLATFORMS)[number];

const BRAND_VOICES = ["Professional", "Casual", "Energetic", "Inspiring"] as const;
type BrandVoice = (typeof BRAND_VOICES)[number];

// ─── Mock script result ───────────────────────────────────────────────────────

const MOCK_SCRIPT = `Hook: "Stop scrolling — this changed everything for me."

[0:00–0:05] Open with your bold result or transformation statement.

[0:05–0:20] Quickly establish the problem your audience faces and why they haven't solved it yet.

[0:20–0:40] Share your unique insight or method in plain, conversational language. Use one concrete example.

[0:40–0:55] Reinforce with a quick social proof moment — a client result, a number, or a vivid before/after.

[0:55–1:00] CTA: "Follow for more" or "Drop a comment below with your biggest challenge."

Caption: Share your [topic] journey using #YourBrand. Tag someone who needs to hear this today.`;

// ─── Form section ─────────────────────────────────────────────────────────────

interface FormState {
  platform: Platform;
  brandVoice: BrandVoice;
  topic: string;
}

// ─── Generated script card ────────────────────────────────────────────────────

function GeneratedScriptCard({
  platform,
  brandVoice,
  topic,
  script,
  onRegenerate,
}: {
  platform: Platform;
  brandVoice: BrandVoice;
  topic: string;
  script: string;
  onRegenerate: () => void;
}) {
  return (
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
            {platform}
          </span>
          <span className="text-[11px] font-medium px-2 py-0.5 rounded-full bg-white border border-gray-200 text-gray-600">
            {brandVoice}
          </span>
        </div>
      </div>
      <div className="px-5 py-4">
        {topic !== "" && (
          <p className="text-xs text-gray-400 mb-3">
            Topic: <span className="font-medium text-gray-600">{topic}</span>
          </p>
        )}
        <pre className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap font-sans">
          {script}
        </pre>
        <div className="mt-4 flex gap-2">
          <button
            type="button"
            onClick={() => void navigator.clipboard.writeText(script)}
            className="text-xs font-medium px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg transition-colors duration-150"
          >
            Copy Script
          </button>
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

// ─── Scripts empty state ──────────────────────────────────────────────────────

function ScriptsEmptyState() {
  return (
    <div className="flex flex-col items-center justify-center py-16 gap-3">
      <span className="text-4xl" aria-hidden="true">
        ✍️
      </span>
      <p className="text-sm font-medium text-gray-500">No scripts generated yet.</p>
      <p className="text-xs text-gray-400">
        Fill in the form above and click Generate.
      </p>
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
  const [isGenerating, setIsGenerating] = useState(false);
  const [hasResult, setHasResult] = useState(false);
  const [resultMeta, setResultMeta] = useState<FormState | null>(null);
  const [generatedScript, setGeneratedScript] = useState<string>(MOCK_SCRIPT);

  async function handleGenerate() {
    if (form.topic.trim() === "") return;
    setIsGenerating(true);
    setHasResult(false);

    try {
      const result = await apiClient.post<{
        analysis: string;
        script: string;
        recommendations: string[];
        data_used: Record<string, unknown>;
      }>("/social", {
        topic: form.topic,
        platform: form.platform.toLowerCase(),
        brand_voice: form.brandVoice.toLowerCase(),
      }, { silent: true });

      // Backend currently echoes the same text into both `analysis` and
      // `script`. Prefer `script`; fall through to `analysis`. The old
      // MOCK_SCRIPT fallback masked real Claude responses — drop it.
      setGeneratedScript(
        result.script || result.analysis || "No script generated. Try again."
      );
      setResultMeta({ ...form });
      setHasResult(true);
    } catch {
      setGeneratedScript("Script generation failed. Try again or check your network.");
      setResultMeta({ ...form });
      setHasResult(true);
    } finally {
      setIsGenerating(false);
    }
  }

  return (
    <>
      <Header title="Social Media" />

      <main className="flex-1 overflow-y-auto p-7 space-y-6">
        {/* Page heading */}
        <div>
          <h1 className="text-xl font-bold text-gray-900">AI Script Generator</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Generate platform-optimized social media scripts tailored to your brand voice.
          </p>
        </div>

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

            {/* Generate button */}
            <button
              type="button"
              onClick={handleGenerate}
              disabled={form.topic.trim() === "" || isGenerating}
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
                  Generate Script
                </>
              )}
            </button>
          </div>
        </section>

        {/* Generated scripts area */}
        <section aria-label="Generated scripts">
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
            <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
              <h2 className="text-sm font-bold text-gray-900">Generated Scripts</h2>
            </div>

            {hasResult && resultMeta !== null ? (
              <div className="p-5">
                <GeneratedScriptCard
                  platform={resultMeta.platform}
                  brandVoice={resultMeta.brandVoice}
                  topic={resultMeta.topic}
                  script={generatedScript}
                  onRegenerate={handleGenerate}
                />
              </div>
            ) : (
              <ScriptsEmptyState />
            )}
          </div>
        </section>
      </main>
    </>
  );
}
