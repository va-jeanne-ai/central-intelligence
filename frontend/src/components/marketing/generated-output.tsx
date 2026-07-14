"use client";

/**
 * GeneratedOutput — shared display for AI-generated marketing content.
 *
 * Renders the LLM's markdown properly (headings, tables, bold) instead of raw
 * source, with two copy actions:
 *  - "Copy text" — the rendered plain text (formatting stripped), for pasting
 *    into ad platforms, DMs, captions.
 *  - "Copy Markdown" — the raw source, for docs/Notion/anywhere that renders md.
 */

import { useRef, useState } from "react";
import { MarkdownContent } from "@/components/ui/markdown-content";

function CopyActionButton({
  label,
  getText,
}: {
  label: string;
  getText: () => string;
}) {
  const [copied, setCopied] = useState(false);

  function handleCopy() {
    void navigator.clipboard.writeText(getText());
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  return (
    <button
      type="button"
      onClick={handleCopy}
      className="px-2.5 py-1 text-[11px] font-semibold rounded bg-accent-500 text-white hover:bg-accent-600 transition-colors"
    >
      {copied ? "Copied ✓" : label}
    </button>
  );
}

interface GeneratedOutputProps {
  markdown: string;
  /** Optional left-side label rendered in the action row (e.g. "Outreach Plan"). */
  heading?: React.ReactNode;
}

export function GeneratedOutput({ markdown, heading }: GeneratedOutputProps) {
  const contentRef = useRef<HTMLDivElement>(null);

  return (
    <div data-tour="generated-output">
      <div className="flex items-center justify-between gap-2 px-5 py-3 border-b border-gray-100 bg-gray-50/60">
        <div className="min-w-0">{heading}</div>
        <div className="flex gap-1.5 flex-shrink-0" data-tour="copy-actions">
          <CopyActionButton
            label="Copy text"
            getText={() => contentRef.current?.innerText ?? markdown}
          />
          <CopyActionButton label="Copy Markdown" getText={() => markdown} />
        </div>
      </div>
      <div ref={contentRef} className="px-5 py-4">
        <MarkdownContent markdown={markdown} />
      </div>
    </div>
  );
}
