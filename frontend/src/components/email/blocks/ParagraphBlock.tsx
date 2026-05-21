"use client";

import { FormField, FormSelect, FormTextarea } from "@/components/ui/form-field";
import type { ParagraphBlock, Alignment } from "./types";

export function ParagraphBlockCanvas({ block }: { block: ParagraphBlock }) {
  // Split on double-newline like the renderer does, preserve single newlines
  // as <br/> equivalents so the preview matches the email.
  const paragraphs = block.text.split(/\n{2,}/);
  return (
    <div className="px-10 py-2">
      {paragraphs.map((para, i) => (
        <p
          key={i}
          style={{
            margin: "0 0 14px 0",
            fontSize: 16,
            lineHeight: "26px",
            color: "#374151",
            textAlign: block.alignment,
            whiteSpace: "pre-line",
          }}
        >
          {para}
        </p>
      ))}
    </div>
  );
}

export function ParagraphBlockEditor({
  block,
  onChange,
}: {
  block: ParagraphBlock;
  onChange: (patch: Partial<ParagraphBlock>) => void;
}) {
  return (
    <div className="space-y-4">
      <FormField label="Text">
        <FormTextarea
          rows={8}
          value={block.text}
          onChange={(e) => onChange({ text: e.target.value })}
        />
      </FormField>
      <FormField label="Alignment">
        <FormSelect
          value={block.alignment}
          onChange={(e) => onChange({ alignment: e.target.value as Alignment })}
        >
          <option value="left">Left</option>
          <option value="center">Center</option>
          <option value="right">Right</option>
        </FormSelect>
      </FormField>
      <p className="text-[11px] text-gray-400 leading-relaxed">
        Tip: leave a blank line between paragraphs. Single line breaks stay
        as soft breaks inside the same paragraph.
      </p>
    </div>
  );
}
