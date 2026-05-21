"use client";

import { useRef, useState } from "react";
import dynamic from "next/dynamic";
import { useRouter } from "next/navigation";
import { Header } from "@/components/layout/header";
import { Button } from "@/components/ui/button";
import { Card, CardBody } from "@/components/ui/card";
import { FormField, FormInput, FormTextarea } from "@/components/ui/form-field";
import { apiClient } from "@/lib/api-client";
import { showError, showSuccess } from "@/lib/toast";
import { EMAIL_TEMPLATES, getTemplate } from "@/lib/email-templates";
import type { EmailEditorHandle } from "@/components/email/EmailEditor";

// TipTap depends on browser-only APIs. Dynamic import with ssr:false avoids
// hydration mismatches and shrinks the initial bundle for users who never
// reach this page.
const EmailEditor = dynamic(() => import("@/components/email/EmailEditor"), {
  ssr: false,
  loading: () => (
    <div className="border border-gray-200 rounded-lg min-h-[400px] flex items-center justify-center text-sm text-gray-400 bg-white">
      Loading editor…
    </div>
  ),
});

// ─── Types ────────────────────────────────────────────────────────────────────

type CampaignType = "regular" | "plain_text" | "template";
type Step = "type" | "template" | "edit";
type ViewMode = "edit" | "preview";

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

// ─── Helpers ──────────────────────────────────────────────────────────────────

function aiResultToHtml(result: DraftSuggestion): string {
  // Convert the AI's plain-text body (split on double newlines) into <p> tags.
  // The Fill-with-AI button overwrites the editor body, so we want valid HTML
  // that TipTap can parse cleanly.
  const paragraphs = result.body
    .split(/\n{2,}/)
    .map((p) => p.trim())
    .filter(Boolean);
  const ctaHtml = result.cta
    ? `<p><strong>${escapeHtml(result.cta)}</strong></p>`
    : "";
  return paragraphs.map((p) => `<p>${escapeHtml(p)}</p>`).join("") + ctaHtml;
}

function escapeHtml(input: string): string {
  return input
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

// ─── Type picker tile ─────────────────────────────────────────────────────────

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
    description: "Rich-text editor with formatting, colors, links, and images. Start from scratch.",
    icon: "📧",
  },
  {
    id: "plain_text",
    name: "Plain text",
    description: "Simple text-only campaign. No formatting, no images. Best deliverability.",
    icon: "📝",
  },
  {
    id: "template",
    name: "Template",
    description: "Pick a starter design and edit it. Three starters: newsletter, promo, welcome.",
    icon: "🎨",
  },
];

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function EmailComposePage() {
  const router = useRouter();
  const editorRef = useRef<EmailEditorHandle>(null);

  // Flow state
  const [step, setStep] = useState<Step>("type");
  const [campaignType, setCampaignType] = useState<CampaignType | null>(null);
  const [templateId, setTemplateId] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<ViewMode>("edit");

  // Form fields
  const [name, setName] = useState("");
  const [subject, setSubject] = useState("");
  const [segment, setSegment] = useState("");
  const [bodyHtml, setBodyHtml] = useState("");

  // Save / AI state
  const [isSaving, setIsSaving] = useState(false);
  const [isAssisting, setIsAssisting] = useState(false);

  // ── Step transitions ───────────────────────────────────────────────────────

  function pickType(type: CampaignType) {
    setCampaignType(type);
    if (type === "template") {
      setStep("template");
    } else {
      setBodyHtml("");
      setStep("edit");
    }
  }

  function pickTemplate(id: string) {
    const tpl = getTemplate(id);
    if (!tpl) return;
    setTemplateId(id);
    setBodyHtml(tpl.html);
    setStep("edit");
    // The editor mounts after this render; the ref will be ready then. We
    // pass initialHtml=bodyHtml when it mounts, so no setContent call needed
    // here. (setContent is only used for AI overwrites + template re-pick.)
  }

  function backToType() {
    setStep("type");
    setCampaignType(null);
    setTemplateId(null);
    setBodyHtml("");
    setViewMode("edit");
  }

  function backToTemplate() {
    if (campaignType !== "template") return;
    setStep("template");
    setTemplateId(null);
    setBodyHtml("");
    setViewMode("edit");
  }

  // ── AI assist ──────────────────────────────────────────────────────────────

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
      // Apply directly — the old "review and confirm" panel was friction.
      // User can undo via the editor's history if they don't like it.
      if (result.subject) setSubject(result.subject);
      const html = aiResultToHtml(result);
      editorRef.current?.setContent(html);
      setBodyHtml(html);
      showSuccess("AI draft applied. Edit it however you like.");
    } catch (err) {
      showError(err instanceof Error ? err.message : "AI Assist failed.");
    } finally {
      setIsAssisting(false);
    }
  }

  // ── Save draft ─────────────────────────────────────────────────────────────

  async function handleSaveDraft() {
    if (isSaving) return;
    // For plain text, bodyHtml is the raw text — wrap it so the iframe
    // preview and downstream rendering treat it sensibly.
    const finalBody =
      campaignType === "plain_text"
        ? `<pre style="font-family:inherit;white-space:pre-wrap;margin:0;">${escapeHtml(bodyHtml)}</pre>`
        : bodyHtml;

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

      <main className="flex-1 overflow-y-auto p-7 space-y-6 max-w-5xl">
        <div>
          <h1 className="text-xl font-bold text-gray-900">Compose Email</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Pick a campaign type, edit the content, save as a draft. Sending via Mailchimp coming soon.
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
                <button
                  key={opt.id}
                  type="button"
                  onClick={() => pickType(opt.id)}
                  className="text-left"
                >
                  <Card className="h-full hover:shadow-md transition-shadow">
                    <CardBody className="space-y-3">
                      <div className="text-3xl leading-none" aria-hidden>{opt.icon}</div>
                      <h3 className="text-[15px] font-bold text-gray-900">{opt.name}</h3>
                      <p className="text-[13px] text-gray-600 leading-relaxed">{opt.description}</p>
                      <span className="block text-[11px] font-medium text-indigo-600">
                        Continue →
                      </span>
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

            {/* Editor / Preview toggle */}
            {campaignType !== "plain_text" && (
              <div className="flex items-center gap-2 mb-3">
                <button
                  type="button"
                  onClick={() => setViewMode("edit")}
                  className={`text-xs font-semibold px-3 py-1 rounded-md border transition-colors ${
                    viewMode === "edit"
                      ? "bg-indigo-50 border-indigo-200 text-indigo-700"
                      : "bg-white border-gray-200 text-gray-600 hover:bg-gray-50"
                  }`}
                >
                  Edit
                </button>
                <button
                  type="button"
                  onClick={() => setViewMode("preview")}
                  className={`text-xs font-semibold px-3 py-1 rounded-md border transition-colors ${
                    viewMode === "preview"
                      ? "bg-indigo-50 border-indigo-200 text-indigo-700"
                      : "bg-white border-gray-200 text-gray-600 hover:bg-gray-50"
                  }`}
                >
                  Preview
                </button>
              </div>
            )}

            {/* Body editor */}
            {campaignType === "plain_text" ? (
              <FormField label="Body" htmlFor="cmp-body">
                <FormTextarea
                  id="cmp-body"
                  rows={16}
                  value={bodyHtml}
                  placeholder="Write your email. Plain text, no formatting."
                  onChange={(e) => setBodyHtml(e.target.value)}
                />
              </FormField>
            ) : viewMode === "edit" ? (
              <EmailEditor
                ref={editorRef}
                initialHtml={bodyHtml}
                onChange={setBodyHtml}
                onAiAssistClick={handleAiAssist}
                aiBusy={isAssisting}
              />
            ) : (
              // Same sandboxed-iframe pattern as the click-to-expand row on
              // /marketing/email — guarantees email HTML can't touch the host.
              <iframe
                title="Preview"
                sandbox=""
                srcDoc={bodyHtml}
                className="w-full h-[600px] bg-white rounded border border-gray-200"
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
                {bodyHtml.length.toLocaleString()} chars in body
              </span>
            </div>
          </section>
        )}
      </main>
    </>
  );
}
