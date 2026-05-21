"use client";

import { FormField, FormInput, FormSelect } from "@/components/ui/form-field";
import type { HeadingBlock, HeadingLevel, Alignment } from "./types";

const LEVEL_STYLE: Record<HeadingLevel, { size: number; line: number; weight: number }> = {
  1: { size: 30, line: 38, weight: 800 },
  2: { size: 22, line: 30, weight: 700 },
  3: { size: 17, line: 24, weight: 700 },
};

export function HeadingBlockCanvas({ block }: { block: HeadingBlock }) {
  const Tag = `h${block.level}` as "h1" | "h2" | "h3";
  const s = LEVEL_STYLE[block.level];
  return (
    <div className="px-10 pt-6 pb-2">
      <Tag
        className="m-0"
        style={{
          fontSize: s.size,
          lineHeight: `${s.line}px`,
          fontWeight: s.weight,
          color: block.color,
          textAlign: block.alignment,
          letterSpacing: "-0.3px",
        }}
      >
        {block.text}
      </Tag>
    </div>
  );
}

export function HeadingBlockEditor({
  block,
  onChange,
}: {
  block: HeadingBlock;
  onChange: (patch: Partial<HeadingBlock>) => void;
}) {
  return (
    <div className="space-y-4">
      <FormField label="Text">
        <FormInput
          type="text"
          value={block.text}
          onChange={(e) => onChange({ text: e.target.value })}
        />
      </FormField>
      <div className="grid grid-cols-2 gap-3">
        <FormField label="Level">
          <FormSelect
            value={block.level}
            onChange={(e) =>
              onChange({ level: Number(e.target.value) as HeadingLevel })
            }
          >
            <option value={1}>H1 (largest)</option>
            <option value={2}>H2</option>
            <option value={3}>H3</option>
          </FormSelect>
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
