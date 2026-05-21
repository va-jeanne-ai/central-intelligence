"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Header } from "@/components/layout/header";
import { Button } from "@/components/ui/button";
import { Card, CardBody } from "@/components/ui/card";
import { FormField, FormInput, FormTextarea } from "@/components/ui/form-field";
import PageBuilder from "@/components/email/PageBuilder";
import {
  createBlock,
  type Block,
  type BlockType,
} from "@/components/email/blocks/types";
import {
  escapeHtml,
  renderBlocksToHtml,
} from "@/components/email/blocks/render";
import { apiClient } from "@/lib/api-client";
import { showError, showSuccess } from "@/lib/toast";
import { EMAIL_TEMPLATES, getTemplate } from "@/lib/email-templates";

// ─── Types ────────────────────────────────────────────────────────────────────

type CampaignType = "regular" | "plain_text" | "template";
type Step = "type" | "template" | "edit";

interface DraftSuggestion {
  subject: string;
  body: string;
  cta: string | null;
}

interface CreateCampaignDraftResponse {
  id: string;
  status: string;
  source: string;
}

// ─── Type-picker tiles ────────────────────────────────────────────────────────

interface TypeOption {
  id: CampaignType;
  name: string;
  description: string;
  icon: string;
}

const TYPE_OPTIONS: TypeOption[] = [
  {
    id: "regular",
    name: "Regular (HTML)",
    description:
      "Start from a blank canvas. Add blocks one at a time: hero, headings, paragraphs, images, buttons.",
    icon: "📧",
  },
  {
    id: "plain_text",
    name: "Plain text",
    description:
      "Simple text-only campaign. No formatting, no images. Best deliverability.",
    icon: "📝",
  },
  {
    id: "template",
    name: "Template",
    description:
      "Pick a starter design and edit each block. Three starters: newsletter, promo, welcome.",
    icon: "🎨",
  },
];

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function EmailComposePage() {
  const router = useRouter();

  // Flow
  const [step, setStep] = useState<Step>("type");
  const [campaignType, setCampaignType] = useState<CampaignType | null>(null);
  const [templateId, setTemplateId] = useState<string | null>(null);

  // Metadata
  const [name, setName] = useState("");
  const [subject, setSubject] = useState("");
  const [segment, setSegment] = useState("");

  // Page-builder state (HTML campaigns)
  const [blocks, setBlocks] = useState<Block[]>([]);
  const [selectedBlockIndex, setSelectedBlockIndex] = useState<number | null>(
    null,
  );

  // Plain-text state (separate from block list)
  const [plainText, setPlainText] = useState("");

  // I/O
  const [isSaving, setIsSaving] = useState(false);
  const [isAssisting, setIsAssisting] = useState(false);

  // ── Step transitions ───────────────────────────────────────────────────────

  function pickType(type: CampaignType) {
    setCampaignType(type);
    if (type === "template") {
      setStep("template");
    } else {
      setBlocks([]);
      setSelectedBlockIndex(null);
      setPlainText("");
      setStep("edit");
    }
  }

  function pickTemplate(id: string) {
    const tpl = getTemplate(id);
    if (!tpl) return;
    setTemplateId(id);
    setBlocks(tpl.blocks);
    setSelectedBlockIndex(null);
    setStep("edit");
  }

  function backToType() {
    setStep("type");
    setCampaignType(null);
    setTemplateId(null);
    setBlocks([]);
    setSelectedBlockIndex(null);
    setPlainText("");
  }

  function backToTemplate() {
    if (campaignType !== "template") return;
    setStep("template");
    setTemplateId(null);
    setBlocks([]);
    setSelectedBlockIndex(null);
  }

  // ── Block mutations ────────────────────────────────────────────────────────

  function addBlock(type: BlockType) {
    const next = createBlock(type);
    setBlocks((prev) => {
      const idx = prev.length;
      setSelectedBlockIndex(idx);
      return [...prev, next];
    });
  }

  function removeBlock(index: number) {
    setBlocks((prev) => prev.filter((_, i) => i !== index));
    setSelectedBlockIndex((curr) => (curr === index ? null : curr));
  }

  function moveBlock(index: number, direction: -1 | 1) {
    const target = index + direction;
    setBlocks((prev) => {
      if (target < 0 || target >= prev.length) return prev;
      const next = prev.slice();
      [next[index], next[target]] = [next[target], next[index]];
      return next;
    });
    // Keep the same block selected after move so the user can keep editing it.
    setSelectedBlockIndex((curr) => {
      if (curr === null) return curr;
      if (curr === index) return target;
      if (curr === target) return index;
      return curr;
    });
  }

  function updateBlock(index: number, patch: Partial<Block>) {
    setBlocks((prev) =>
      prev.map((b, i) =>
        i === index ? ({ ...b, ...patch } as Block) : b,
      ),
    );
  }

  // ── AI Fill ────────────────────────────────────────────────────────────────

  async function handleAiAssist() {
    if (isAssisting) return;
    setIsAssisting(true);
    try {
      const result = await apiClient.post<DraftSuggestion>(
        "/email/draft",
        {
          subject: subject.trim() || "Write a re-engagement email to past leads",
          audience: segment.trim() || undefined,
          tone: "warm professional",
        },
        { silent: true, timeout: 120_000 },
      );

      if (result.subject) setSubject(result.subject);

      // Build a block list from the AI's plain-text body. One Heading,
      // N Paragraphs (split on \n\n), one Button if a CTA came back.
      const paragraphs = result.body
        .split(/\n{2,}/)
        .map((s) => s.trim())
        .filter(Boolean);
      const next: Block[] = [
        createBlock("heading", {
          text: result.subject || "New email",
          level: 1,
          alignment: "center",
        }),
        ...paragraphs.map((p) => createBlock("paragraph", { text: p })),
        ...(result.cta
          ? [createBlock("button", { text: result.cta, href: "https://" })]
          : []),
      ];
      setBlocks(next);
      setSelectedBlockIndex(null);
      showSuccess("AI draft applied. Edit any block from the right panel.");
    } catch (err) {
      showError(err instanceof Error ? err.message : "AI Assist failed.");
    } finally {
      setIsAssisting(false);
    }
  }

  // ── Save draft ─────────────────────────────────────────────────────────────

  async function handleSaveDraft() {
    if (isSaving) return;

    const finalBody =
      campaignType === "plain_text"
        ? `<pre style="font-family:inherit;white-space:pre-wrap;margin:0;">${escapeHtml(plainText)}</pre>`
        : renderBlocksToHtml(blocks);

    setIsSaving(true);
    try {
      await apiClient.post<CreateCampaignDraftResponse>(
        "/email/campaigns",
        {
          name: name.trim() || subject.trim() || "Untitled draft",
          subject: subject.trim() || null,
          body_html: finalBody,
          audience_name: segment.trim() || null,
          campaign_type: campaignType,
        },
        { silent: true },
      );
      showSuccess("Draft saved.");
      router.push("/marketing/email");
    } catch (err) {
      showError(err instanceof Error ? err.message : "Save failed.");
    } finally {
      setIsSaving(false);
    }
  }

  // ── Render ─────────────────────────────────────────────────────────────────

  return (
    <>
      <Header title="Compose Email" />

      <main className="flex-1 overflow-y-auto p-7 space-y-6">
        <div>
          <h1 className="text-xl font-bold text-gray-900">Compose Email</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Pick a campaign type, edit the content block-by-block, save as a draft. Sending via Mailchimp coming soon.
          </p>
        </div>

        {/* ── Step 1: Type picker ──────────────────────────────────────────── */}
        {step === "type" && (
          <section aria-label="Choose campaign type">
            <h2 className="text-[11px] font-bold tracking-widest uppercase text-emerald-600 mb-3">
              Step 1 — Choose campaign type
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {TYPE_OPTIONS.map((opt) => (
                <button key={opt.id} type="button" onClick={() => pickType(opt.id)} className="text-left">
                  <Card className="h-full hover:shadow-md transition-shadow">
                    <CardBody className="space-y-3">
                      <div className="text-3xl leading-none" aria-hidden>{opt.icon}</div>
                      <h3 className="text-[15px] font-bold text-gray-900">{opt.name}</h3>
                      <p className="text-[13px] text-gray-600 leading-relaxed">{opt.description}</p>
                      <span className="block text-[11px] font-medium text-indigo-600">Continue →</span>
                    </CardBody>
                  </Card>
                </button>
              ))}
            </div>
          </section>
        )}

        {/* ── Step 2: Template picker ──────────────────────────────────────── */}
        {step === "template" && (
          <section aria-label="Choose a template">
            <button
              type="button"
              onClick={backToType}
              className="text-xs font-medium text-indigo-600 hover:text-indigo-700 underline underline-offset-2 mb-3"
            >
              ← Change campaign type
            </button>
            <h2 className="text-[11px] font-bold tracking-widest uppercase text-emerald-600 mb-3">
              Step 2 — Choose a template
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {EMAIL_TEMPLATES.map((tpl) => (
                <button key={tpl.id} type="button" onClick={() => pickTemplate(tpl.id)} className="text-left">
                  <Card className="h-full hover:shadow-md transition-shadow">
                    <CardBody className="space-y-3">
                      <div className="text-3xl leading-none" aria-hidden>{tpl.thumbnail}</div>
                      <h3 className="text-[15px] font-bold text-gray-900">{tpl.name}</h3>
                      <p className="text-[13px] text-gray-600 leading-relaxed">{tpl.description}</p>
                      <span className="block text-[11px] font-medium text-indigo-600">Use this template →</span>
                    </CardBody>
                  </Card>
                </button>
              ))}
            </div>
          </section>
        )}

        {/* ── Step 3: Edit ─────────────────────────────────────────────────── */}
        {step === "edit" && campaignType && (
          <section aria-label="Edit campaign">
            <div className="flex items-center gap-3 mb-3">
              <button
                type="button"
                onClick={backToType}
                className="text-xs font-medium text-indigo-600 hover:text-indigo-700 underline underline-offset-2"
              >
                ← Change campaign type
              </button>
              {campaignType === "template" && templateId && (
                <>
                  <span className="text-xs text-gray-300">·</span>
                  <button
                    type="button"
                    onClick={backToTemplate}
                    className="text-xs font-medium text-indigo-600 hover:text-indigo-700 underline underline-offset-2"
                  >
                    ← Change template
                  </button>
                </>
              )}
            </div>

            {/* Metadata */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-5">
              <FormField label="Internal name" htmlFor="cmp-name">
                <FormInput
                  id="cmp-name"
                  type="text"
                  value={name}
                  placeholder="e.g. Spring sale — Tier B"
                  onChange={(e) => setName(e.target.value)}
                />
              </FormField>
              <FormField label="To / Segment" htmlFor="cmp-segment">
                <FormInput
                  id="cmp-segment"
                  type="text"
                  value={segment}
                  placeholder="e.g. All subscribers, or 'opened last 30d'"
                  onChange={(e) => setSegment(e.target.value)}
                />
              </FormField>
              <div className="md:col-span-2">
                <FormField label="Subject line" htmlFor="cmp-subject">
                  <FormInput
                    id="cmp-subject"
                    type="text"
                    value={subject}
                    placeholder="The line that decides if they open it"
                    onChange={(e) => setSubject(e.target.value)}
                  />
                </FormField>
              </div>
            </div>

            {/* Body editor — page builder for HTML, textarea for plain text */}
            {campaignType === "plain_text" ? (
              <FormField label="Body" htmlFor="cmp-body">
                <FormTextarea
                  id="cmp-body"
                  rows={16}
                  value={plainText}
                  placeholder="Write your email. Plain text, no formatting."
                  onChange={(e) => setPlainText(e.target.value)}
                />
              </FormField>
            ) : (
              <PageBuilder
                blocks={blocks}
                selectedIndex={selectedBlockIndex}
                onSelect={setSelectedBlockIndex}
                onAdd={addBlock}
                onRemove={removeBlock}
                onMove={moveBlock}
                onUpdate={updateBlock}
                onAiAssist={handleAiAssist}
                aiBusy={isAssisting}
              />
            )}

            {/* Actions */}
            <div className="flex items-center gap-2 mt-5">
              <Button onClick={handleSaveDraft} disabled={isSaving}>
                {isSaving ? "Saving…" : "Save Draft"}
              </Button>
              <Button
                variant="primary"
                disabled
                title="Sending via Mailchimp coming soon"
                className="opacity-50 cursor-not-allowed"
              >
                Send
              </Button>
              <span className="ml-auto text-[11px] text-gray-400">
                {campaignType === "plain_text"
                  ? `${plainText.length.toLocaleString()} chars`
                  : `${blocks.length} block${blocks.length === 1 ? "" : "s"}`}
              </span>
            </div>
          </section>
        )}
      </main>
    </>
  );
}
