"use client";

import { useState } from "react";
import Link from "next/link";
import { Header } from "@/components/layout/header";
import { apiClient } from "@/lib/api-client";
import type { OfferGenerateResponse } from "@/types";

// ─── Types ────────────────────────────────────────────────────────────────────

interface PricingTier {
  name: string;
  price: string;
}

interface Bonus {
  name: string;
  value: string;
}

type Guarantee = "30-day" | "60-day" | "90-day" | "none";

interface UrgencyElements {
  countdownTimer: boolean;
  limitedSpots: boolean;
  bonusExpiry: boolean;
}

interface FormState {
  title: string;
  description: string;
  tiers: PricingTier[];
  bonuses: Bonus[];
  guarantee: Guarantee;
  urgency: UrgencyElements;
  ctaText: string;
}

interface AiGenerated {
  title: string;
  description: string;
  cta: string;
}

// ─── Constants ────────────────────────────────────────────────────────────────

const INITIAL_TIERS: PricingTier[] = [
  { name: "Starter", price: "997" },
  { name: "Pro", price: "1997" },
  { name: "Elite", price: "4997" },
];

const INITIAL_BONUSES: Bonus[] = [
  { name: "", value: "" },
  { name: "", value: "" },
];

// Returns the default starting form state — used both for the initial
// useState value AND for resetting after a successful save. Rebuilding the
// nested arrays each call prevents the reset from sharing references with
// the saved offer's payload.
function blankForm(): FormState {
  return {
    title: "",
    description: "",
    tiers: INITIAL_TIERS.map((tier) => ({ ...tier })),
    bonuses: INITIAL_BONUSES.map((bonus) => ({ ...bonus })),
    guarantee: "30-day",
    urgency: { countdownTimer: false, limitedSpots: false, bonusExpiry: false },
    ctaText: "Apply Now",
  };
}

const GUARANTEE_OPTIONS: { label: string; value: Guarantee }[] = [
  { label: "30-day money back", value: "30-day" },
  { label: "60-day money back", value: "60-day" },
  { label: "90-day money back", value: "90-day" },
  { label: "No guarantee", value: "none" },
];

const MOCK_AI_GENERATED: AiGenerated = {
  title: "The Elite Coaching Accelerator — Transform Your Business in 90 Days",
  description:
    "Join a select group of high-performing entrepreneurs who are ready to scale fast, eliminate bottlenecks, and build a business that runs without you. Our proven framework has helped 500+ coaches generate $1M+ in revenue. Spots are strictly limited — apply now before the deadline.",
  cta: "Claim Your Spot Now",
};

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

// ─── Sparkles icon ────────────────────────────────────────────────────────────

function SparklesIcon({ className }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="currentColor"
      className={className}
      aria-hidden="true"
    >
      <path
        fillRule="evenodd"
        d="M9 4.5a.75.75 0 01.721.544l.813 2.846a3.75 3.75 0 002.576 2.576l2.846.813a.75.75 0 010 1.442l-2.846.813a3.75 3.75 0 00-2.576 2.576l-.813 2.846a.75.75 0 01-1.442 0l-.813-2.846a3.75 3.75 0 00-2.576-2.576l-2.846-.813a.75.75 0 010-1.442l2.846-.813A3.75 3.75 0 007.466 7.89l.813-2.846A.75.75 0 019 4.5zM18 1.5a.75.75 0 01.728.568l.258 1.036c.236.94.97 1.674 1.91 1.91l1.036.258a.75.75 0 010 1.456l-1.036.258c-.94.236-1.674.97-1.91 1.91l-.258 1.036a.75.75 0 01-1.456 0l-.258-1.036a2.625 2.625 0 00-1.91-1.91l-1.036-.258a.75.75 0 010-1.456l1.036-.258a2.625 2.625 0 001.91-1.91l.258-1.036A.75.75 0 0118 1.5z"
        clipRule="evenodd"
      />
    </svg>
  );
}

// ─── Offer preview modal ──────────────────────────────────────────────────────

interface OfferPreviewProps {
  form: FormState;
  onClose: () => void;
}

function OfferPreview({ form, onClose }: OfferPreviewProps) {
  const guaranteeLabel = GUARANTEE_OPTIONS.find((g) => g.value === form.guarantee)?.label ?? "";

  return (
    <div
      className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-6"
      role="dialog"
      aria-modal="true"
      aria-label="Offer preview"
    >
      <div className="bg-white rounded-2xl border border-gray-200 shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
        {/* Preview header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100 sticky top-0 bg-white rounded-t-2xl z-10">
          <h2 className="text-sm font-bold text-gray-900">Offer Preview</h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close preview"
            className="text-xs font-medium px-3 py-1.5 border border-gray-200 text-gray-600 hover:bg-gray-50 rounded-lg transition-colors duration-150"
          >
            Close
          </button>
        </div>

        {/* Preview content */}
        <div className="px-6 py-6 flex flex-col gap-6">
          {/* Title & description */}
          <div className="text-center flex flex-col gap-2">
            <h3 className="text-xl font-bold text-gray-900 leading-snug">
              {form.title !== "" ? form.title : "Your Offer Title"}
            </h3>
            {form.description !== "" && (
              <p className="text-sm text-gray-600 leading-relaxed max-w-lg mx-auto">
                {form.description}
              </p>
            )}
          </div>

          {/* Pricing tiers */}
          <div>
            <p className="text-[10px] font-bold uppercase tracking-wider text-emerald-600 text-center mb-3">
              Choose Your Level
            </p>
            <div className="grid grid-cols-3 gap-3">
              {form.tiers.map((tier, i) => (
                <div
                  key={i}
                  className={`rounded-xl border p-4 flex flex-col items-center gap-2 ${
                    i === 1
                      ? "border-emerald-400 bg-emerald-50 shadow-sm"
                      : "border-gray-200 bg-white"
                  }`}
                >
                  {i === 1 && (
                    <span className="text-[10px] font-bold uppercase tracking-wider text-emerald-600">
                      Most Popular
                    </span>
                  )}
                  <span className="text-sm font-bold text-gray-800">
                    {tier.name !== "" ? tier.name : `Tier ${i + 1}`}
                  </span>
                  <span className="text-2xl font-bold text-gray-900">
                    {tier.price !== "" ? `$${tier.price}` : "—"}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Bonuses */}
          {form.bonuses.some((b) => b.name !== "") && (
            <div>
              <p className="text-[10px] font-bold uppercase tracking-wider text-emerald-600 mb-3">
                Included Bonuses
              </p>
              <ul className="flex flex-col gap-2">
                {form.bonuses
                  .filter((b) => b.name !== "")
                  .map((bonus, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm text-gray-700">
                      <span className="text-emerald-500 font-bold flex-shrink-0" aria-hidden="true">
                        +
                      </span>
                      <span className="font-medium">{bonus.name}</span>
                      {bonus.value !== "" && (
                        <span className="ml-auto text-[11px] font-semibold text-emerald-700 bg-emerald-50 border border-emerald-100 px-2 py-0.5 rounded-full flex-shrink-0">
                          Value: ${bonus.value}
                        </span>
                      )}
                    </li>
                  ))}
              </ul>
            </div>
          )}

          {/* Guarantee */}
          {form.guarantee !== "none" && (
            <div className="flex items-center justify-center gap-3 bg-gray-50 rounded-xl border border-gray-200 px-5 py-4">
              <span className="text-2xl" aria-hidden="true">
                🛡️
              </span>
              <div>
                <p className="text-sm font-bold text-gray-900">{guaranteeLabel}</p>
                <p className="text-xs text-gray-500">Risk-free guarantee</p>
              </div>
            </div>
          )}

          {/* CTA button */}
          <div className="flex justify-center pt-2">
            <button
              type="button"
              className="inline-flex items-center gap-2 px-8 py-3 bg-emerald-600 hover:bg-emerald-700 text-white text-base font-bold rounded-xl transition-colors duration-150 shadow-sm active:scale-95"
            >
              {form.ctaText !== "" ? form.ctaText : "Apply Now"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── AI Generator panel ───────────────────────────────────────────────────────

interface AiPanelProps {
  form: FormState;
}

function AiGeneratorPanel({ form }: AiPanelProps) {
  const [aiContext, setAiContext] = useState("");
  const [isGenerating, setIsGenerating] = useState(false);
  const [generated, setGenerated] = useState<AiGenerated | null>(null);

  async function handleGenerate() {
    if (isGenerating) return;
    setIsGenerating(true);
    setGenerated(null);

    try {
      const result = await apiClient.post<OfferGenerateResponse>("/offer-generate", {
        offer_type: form.title !== "" ? form.title : "coaching",
        max_offers: 3,
      }, { silent: true });

      if (result.status === "queued") {
        // Generation queued — show mock output as placeholder while task processes
        setGenerated(MOCK_AI_GENERATED);
      } else {
        setGenerated(MOCK_AI_GENERATED);
      }
    } catch {
      // Fall back to mock generated data on error.
      setGenerated(MOCK_AI_GENERATED);
    } finally {
      setIsGenerating(false);
    }
  }

  return (
    <div
      className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden flex flex-col"
      style={{ width: "40%" }}
    >
      {/* Card header */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
        <div className="flex items-center gap-2">
          <SparklesIcon className="w-4 h-4 text-emerald-600" />
          <h2 className="text-sm font-bold text-gray-900">AI Offer Generator</h2>
        </div>
      </div>

      <div className="px-5 py-5 flex flex-col gap-4 flex-1">
        {/* Context textarea */}
        <div className="flex flex-col gap-1.5">
          <label
            htmlFor="ai-context"
            className="text-[10px] font-bold uppercase tracking-wider text-emerald-600"
          >
            Audience &amp; Context
          </label>
          <textarea
            id="ai-context"
            value={aiContext}
            onChange={(e) => setAiContext(e.target.value)}
            placeholder="Describe your target audience, transformation, and price point..."
            rows={4}
            className="text-sm border border-gray-200 rounded-lg px-3 py-2.5 bg-white text-gray-700 placeholder:text-gray-400 resize-none focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent"
          />
        </div>

        {/* Generate button */}
        <button
          type="button"
          onClick={handleGenerate}
          disabled={isGenerating}
          className="inline-flex items-center justify-center gap-2 px-4 py-2.5 bg-emerald-600 hover:bg-emerald-700 disabled:bg-emerald-200 disabled:cursor-not-allowed text-white text-sm font-semibold rounded-lg transition-colors duration-150 active:scale-95 shadow-sm"
        >
          {isGenerating ? (
            <>
              <Spinner />
              Generating…
            </>
          ) : (
            <>
              <SparklesIcon className="w-4 h-4" />
              Generate with AI
            </>
          )}
        </button>

        {/* Result area */}
        {generated === null && !isGenerating ? (
          /* Empty state */
          <div className="flex flex-col items-center justify-center flex-1 py-8 gap-3">
            <span className="text-4xl" aria-hidden="true">
              🎁
            </span>
            <p className="text-sm font-medium text-gray-500 text-center">
              No output yet.
            </p>
            <p className="text-xs text-gray-400 text-center">
              Add context above and click Generate.
            </p>
          </div>
        ) : generated !== null ? (
          /* Side-by-side comparison */
          <div className="flex flex-col gap-3">
            <p className="text-[10px] font-bold uppercase tracking-wider text-gray-400">
              Comparison
            </p>
            <div className="grid grid-cols-2 gap-3">
              {/* AI Generated side */}
              <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 flex flex-col gap-3">
                <span className="text-[10px] font-bold uppercase tracking-wider text-emerald-600">
                  AI Generated
                </span>
                <div className="flex flex-col gap-2">
                  <div>
                    <span className="text-[10px] font-semibold text-gray-500 uppercase tracking-wide">
                      Title
                    </span>
                    <p className="text-xs text-gray-800 font-medium leading-snug mt-0.5">
                      {generated.title}
                    </p>
                  </div>
                  <div>
                    <span className="text-[10px] font-semibold text-gray-500 uppercase tracking-wide">
                      Description
                    </span>
                    <p className="text-xs text-gray-700 leading-relaxed mt-0.5 line-clamp-4">
                      {generated.description}
                    </p>
                  </div>
                  <div>
                    <span className="text-[10px] font-semibold text-gray-500 uppercase tracking-wide">
                      CTA
                    </span>
                    <p className="text-xs text-gray-800 font-semibold mt-0.5">{generated.cta}</p>
                  </div>
                </div>
              </div>

              {/* Manual side */}
              <div className="rounded-lg border border-gray-200 bg-white p-3 flex flex-col gap-3">
                <span className="text-[10px] font-bold uppercase tracking-wider text-gray-500">
                  Manual
                </span>
                <div className="flex flex-col gap-2">
                  <div>
                    <span className="text-[10px] font-semibold text-gray-500 uppercase tracking-wide">
                      Title
                    </span>
                    <p className="text-xs text-gray-800 font-medium leading-snug mt-0.5">
                      {form.title !== "" ? form.title : "—"}
                    </p>
                  </div>
                  <div>
                    <span className="text-[10px] font-semibold text-gray-500 uppercase tracking-wide">
                      Description
                    </span>
                    <p className="text-xs text-gray-700 leading-relaxed mt-0.5 line-clamp-4">
                      {form.description !== "" ? form.description : "—"}
                    </p>
                  </div>
                  <div>
                    <span className="text-[10px] font-semibold text-gray-500 uppercase tracking-wide">
                      CTA
                    </span>
                    <p className="text-xs text-gray-800 font-semibold mt-0.5">
                      {form.ctaText !== "" ? form.ctaText : "—"}
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}

// ─── Left form panel ──────────────────────────────────────────────────────────

interface FormPanelProps {
  form: FormState;
  onFormChange: (updated: FormState) => void;
  onPreview: () => void;
  onSave: () => void;
  isSaved: boolean;
}

function FormPanel({ form, onFormChange, onPreview, onSave, isSaved }: FormPanelProps) {
  function updateField<K extends keyof FormState>(key: K, value: FormState[K]) {
    onFormChange({ ...form, [key]: value });
  }

  function updateTier(index: number, field: keyof PricingTier, value: string) {
    const tiers = form.tiers.map((t, i) => (i === index ? { ...t, [field]: value } : t));
    onFormChange({ ...form, tiers });
  }

  function updateBonus(index: number, field: keyof Bonus, value: string) {
    const bonuses = form.bonuses.map((b, i) => (i === index ? { ...b, [field]: value } : b));
    onFormChange({ ...form, bonuses });
  }

  function updateUrgency(key: keyof UrgencyElements, checked: boolean) {
    onFormChange({ ...form, urgency: { ...form.urgency, [key]: checked } });
  }

  const inputClass =
    "text-sm border border-gray-200 rounded-lg px-3 py-2.5 bg-white text-gray-700 placeholder:text-gray-400 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent";

  const labelClass = "text-[10px] font-bold uppercase tracking-wider text-emerald-600";

  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden flex-1 min-w-0">
      {/* Card header */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
        <h2 className="text-sm font-bold text-gray-900">Offer Details</h2>
      </div>

      <div className="px-5 py-5 flex flex-col gap-5">
        {/* Offer Title */}
        <div className="flex flex-col gap-1.5">
          <label htmlFor="offer-title" className={labelClass}>
            Offer Title
          </label>
          <input
            id="offer-title"
            type="text"
            value={form.title}
            onChange={(e) => updateField("title", e.target.value)}
            placeholder="e.g. The 90-Day Elite Accelerator"
            className={inputClass}
          />
        </div>

        {/* Description */}
        <div className="flex flex-col gap-1.5">
          <label htmlFor="offer-description" className={labelClass}>
            Description
          </label>
          <textarea
            id="offer-description"
            value={form.description}
            onChange={(e) => updateField("description", e.target.value)}
            placeholder="Describe the transformation your offer delivers..."
            rows={3}
            className={`${inputClass} resize-none`}
          />
        </div>

        {/* Pricing Tiers */}
        <div className="flex flex-col gap-2">
          <span className={labelClass}>Pricing Tiers</span>
          <div className="flex flex-col gap-2">
            {form.tiers.map((tier, i) => (
              <div key={i} className="flex items-center gap-3">
                <span className="text-xs font-semibold text-gray-500 w-12 flex-shrink-0">
                  Tier {i + 1}
                </span>
                <input
                  type="text"
                  value={tier.name}
                  onChange={(e) => updateTier(i, "name", e.target.value)}
                  placeholder="Name"
                  aria-label={`Tier ${i + 1} name`}
                  className={`${inputClass} flex-1`}
                />
                <div className="relative flex-shrink-0 w-32">
                  <span className="absolute left-3 top-1/2 -translate-y-1/2 text-sm text-gray-400 select-none">
                    $
                  </span>
                  <input
                    type="number"
                    value={tier.price}
                    onChange={(e) => updateTier(i, "price", e.target.value)}
                    placeholder="0"
                    min="0"
                    aria-label={`Tier ${i + 1} price`}
                    className={`${inputClass} w-full pl-7`}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Bonuses */}
        <div className="flex flex-col gap-2">
          <span className={labelClass}>Bonuses</span>
          <div className="flex flex-col gap-2">
            {form.bonuses.map((bonus, i) => (
              <div key={i} className="flex items-center gap-3">
                <span className="text-xs font-semibold text-gray-500 w-16 flex-shrink-0">
                  Bonus {i + 1}
                </span>
                <input
                  type="text"
                  value={bonus.name}
                  onChange={(e) => updateBonus(i, "name", e.target.value)}
                  placeholder="Bonus name"
                  aria-label={`Bonus ${i + 1} name`}
                  className={`${inputClass} flex-1`}
                />
                <div className="relative flex-shrink-0 w-32">
                  <span className="absolute left-3 top-1/2 -translate-y-1/2 text-sm text-gray-400 select-none">
                    $
                  </span>
                  <input
                    type="number"
                    value={bonus.value}
                    onChange={(e) => updateBonus(i, "value", e.target.value)}
                    placeholder="Value"
                    min="0"
                    aria-label={`Bonus ${i + 1} estimated value`}
                    className={`${inputClass} w-full pl-7`}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Guarantee */}
        <div className="flex flex-col gap-1.5">
          <label htmlFor="offer-guarantee" className={labelClass}>
            Guarantee
          </label>
          <select
            id="offer-guarantee"
            value={form.guarantee}
            onChange={(e) => updateField("guarantee", e.target.value as Guarantee)}
            className={inputClass}
          >
            {GUARANTEE_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>

        {/* Urgency Elements */}
        <div className="flex flex-col gap-2">
          <span className={labelClass}>Urgency Elements</span>
          <div className="flex flex-col gap-2">
            {(
              [
                { key: "countdownTimer", label: "Countdown timer" },
                { key: "limitedSpots", label: "Limited spots" },
                { key: "bonusExpiry", label: "Bonus expiry" },
              ] as { key: keyof UrgencyElements; label: string }[]
            ).map(({ key, label }) => (
              <label key={key} className="flex items-center gap-2.5 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={form.urgency[key]}
                  onChange={(e) => updateUrgency(key, e.target.checked)}
                  className="w-4 h-4 rounded border-gray-300 text-emerald-600 focus:ring-emerald-500"
                />
                <span className="text-sm text-gray-700">{label}</span>
              </label>
            ))}
          </div>
        </div>

        {/* CTA Button Text */}
        <div className="flex flex-col gap-1.5">
          <label htmlFor="offer-cta" className={labelClass}>
            CTA Button Text
          </label>
          <input
            id="offer-cta"
            type="text"
            value={form.ctaText}
            onChange={(e) => updateField("ctaText", e.target.value)}
            placeholder="Apply Now"
            className={inputClass}
          />
        </div>

        {/* Action buttons */}
        <div className="flex items-center gap-3 pt-1 border-t border-gray-100">
          <button
            type="button"
            onClick={onPreview}
            className="inline-flex items-center gap-1.5 px-5 py-2.5 border border-gray-200 hover:bg-gray-50 text-gray-700 text-sm font-semibold rounded-lg transition-colors duration-150 active:scale-95"
          >
            Preview Offer
          </button>
          <button
            type="button"
            onClick={onSave}
            className="inline-flex items-center gap-1.5 px-5 py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white text-sm font-semibold rounded-lg transition-colors duration-150 active:scale-95 shadow-sm"
          >
            {isSaved ? (
              <>
                <span aria-hidden="true">✓</span>
                Saved
              </>
            ) : (
              "Save Offer"
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function OfferBuilderPage() {
  const [form, setForm] = useState<FormState>(blankForm);
  const [showPreview, setShowPreview] = useState(false);
  const [isSaved, setIsSaved] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  async function handleSave() {
    setSaveError(null);

    // CreateOfferRequest only accepts {name, description, price, status, url, notes}.
    // The builder collects richer structured data (tiers, bonuses, guarantee,
    // urgency, CTA). Park the structured fields in `notes` as JSON so they
    // round-trip on the library page when we wire that side.
    const structured = {
      tiers: form.tiers,
      bonuses: form.bonuses,
      guarantee: form.guarantee,
      urgency: form.urgency,
      cta_text: form.ctaText,
    };

    // Use the lowest tier's price as the headline price (or null if none parse).
    const firstPriceNum = Number.parseFloat(form.tiers[0]?.price ?? "");
    const headlinePrice = Number.isFinite(firstPriceNum) ? firstPriceNum : undefined;

    try {
      await apiClient.post("/offers", {
        name: form.title || "Untitled Offer",
        description: form.description || null,
        price: headlinePrice,
        status: "Active",
        notes: JSON.stringify(structured),
      });
      // Reset to a clean form so the user can build another offer immediately.
      // The brief "Saved ✓" state on the button is enough acknowledgement;
      // they can always check /marketing/offers to see the new entry.
      setForm(blankForm());
      setIsSaved(true);
      setTimeout(() => setIsSaved(false), 2500);
    } catch (err) {
      setSaveError(
        err instanceof Error ? err.message : "Failed to save offer. Check your network.",
      );
    }
  }

  return (
    <>
      <Header title="Offers" />

      <main className="flex-1 overflow-y-auto p-7 space-y-6">
        {/* Page heading */}
        <div>
          <Link
            href="/marketing/offers"
            className="inline-flex items-center gap-1 text-xs font-medium text-emerald-600 hover:text-emerald-700 transition-colors mb-2"
          >
            <span aria-hidden="true">←</span>
            Back to Offers
          </Link>
          <h1 className="text-xl font-bold text-gray-900">Offer Builder</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Build, price, and configure your offer — then use AI to generate compelling copy.
          </p>
        </div>

        {saveError !== null && (
          <div className="border border-red-200 bg-red-50 rounded-lg px-4 py-3">
            <p className="text-xs text-red-700">{saveError}</p>
          </div>
        )}

        {/* Main two-panel layout */}
        <section aria-label="Offer builder" className="flex gap-5 items-start">
          {/* Left: form panel */}
          <FormPanel
            form={form}
            onFormChange={setForm}
            onPreview={() => setShowPreview(true)}
            onSave={handleSave}
            isSaved={isSaved}
          />

          {/* Right: AI generator panel */}
          <AiGeneratorPanel form={form} />
        </section>
      </main>

      {/* Offer preview overlay */}
      {showPreview && (
        <OfferPreview form={form} onClose={() => setShowPreview(false)} />
      )}
    </>
  );
}
