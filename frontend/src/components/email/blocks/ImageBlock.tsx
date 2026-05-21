"use client";

import { FormField, FormInput, FormSelect } from "@/components/ui/form-field";
import type { ImageBlock, Alignment } from "./types";

export function ImageBlockCanvas({ block }: { block: ImageBlock }) {
  return (
    <div className="px-10 py-4" style={{ textAlign: block.alignment }}>
      {block.src ? (
        // Plain <img> rather than next/image — the canvas needs to match
        // what we emit in the saved HTML, which is an unprocessed <img>.
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={block.src}
          alt={block.alt}
          style={{
            display: "inline-block",
            maxWidth: "100%",
            height: "auto",
            border: 0,
          }}
        />
      ) : (
        <div className="inline-block w-32 h-20 bg-gray-100 border border-dashed border-gray-300 text-gray-400 text-[11px] leading-[80px] text-center">
          No image
        </div>
      )}
    </div>
  );
}

export function ImageBlockEditor({
  block,
  onChange,
}: {
  block: ImageBlock;
  onChange: (patch: Partial<ImageBlock>) => void;
}) {
  return (
    <div className="space-y-4">
      <FormField label="Image URL">
        <FormInput
          type="url"
          placeholder="https://..."
          value={block.src}
          onChange={(e) => onChange({ src: e.target.value })}
        />
      </FormField>
      <FormField label="Alt text (for accessibility / fallback)">
        <FormInput
          type="text"
          value={block.alt}
          onChange={(e) => onChange({ alt: e.target.value })}
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
    </div>
  );
}
