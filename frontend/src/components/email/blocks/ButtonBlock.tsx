"use client";

import { FormField, FormInput } from "@/components/ui/form-field";
import type { ButtonBlock } from "./types";

export function ButtonBlockCanvas({ block }: { block: ButtonBlock }) {
  return (
    <div className="px-10 py-6 text-center">
      <span
        className="inline-block"
        style={{
          background: `linear-gradient(135deg, ${block.color} 0%, ${darken(block.color)} 100%)`,
          color: "#ffffff",
          padding: "16px 36px",
          borderRadius: 8,
          fontWeight: 700,
          fontSize: 16,
          letterSpacing: "0.3px",
          boxShadow: "0 4px 14px rgba(0,0,0,0.15)",
        }}
      >
        {block.text} →
      </span>
    </div>
  );
}

export function ButtonBlockEditor({
  block,
  onChange,
}: {
  block: ButtonBlock;
  onChange: (patch: Partial<ButtonBlock>) => void;
}) {
  return (
    <div className="space-y-4">
      <FormField label="Button text">
        <FormInput
          type="text"
          value={block.text}
          onChange={(e) => onChange({ text: e.target.value })}
        />
      </FormField>
      <FormField label="Link (URL)">
        <FormInput
          type="url"
          placeholder="https://..."
          value={block.href}
          onChange={(e) => onChange({ href: e.target.value })}
        />
      </FormField>
      <FormField label="Color">
        <input
          type="color"
          value={block.color}
          onChange={(e) => onChange({ color: e.target.value })}
          className="h-10 w-full rounded-md border border-gray-200 cursor-pointer"
        />
      </FormField>
    </div>
  );
}

// Local mirror of the darken helper in render.ts — kept duplicated rather
// than imported because the canvas + the saved HTML must look the same.
function darken(hex: string): string {
  const match = /^#?([0-9a-f]{6})$/i.exec(hex);
  if (!match) return hex;
  const n = parseInt(match[1], 16);
  const r = Math.max(0, ((n >> 16) & 0xff) - 30);
  const g = Math.max(0, ((n >> 8) & 0xff) - 30);
  const b = Math.max(0, (n & 0xff) - 30);
  return `#${((r << 16) | (g << 8) | b).toString(16).padStart(6, "0")}`;
}
