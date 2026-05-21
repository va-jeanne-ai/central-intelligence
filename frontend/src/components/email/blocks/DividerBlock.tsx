"use client";

import { FormField, FormSelect } from "@/components/ui/form-field";
import type { DividerBlock, DividerStyle } from "./types";

export function DividerBlockCanvas({ block }: { block: DividerBlock }) {
  if (block.style === "space") {
    return <div className="h-8" aria-hidden />;
  }
  const borderStyle = block.style === "dashed" ? "dashed" : "solid";
  return (
    <div className="px-10 py-4">
      <hr
        style={{
          border: 0,
          borderTop: `1px ${borderStyle} #e5e7eb`,
          margin: 0,
        }}
      />
    </div>
  );
}

export function DividerBlockEditor({
  block,
  onChange,
}: {
  block: DividerBlock;
  onChange: (patch: Partial<DividerBlock>) => void;
}) {
  return (
    <FormField label="Style">
      <FormSelect
        value={block.style}
        onChange={(e) => onChange({ style: e.target.value as DividerStyle })}
      >
        <option value="solid">Solid line</option>
        <option value="dashed">Dashed line</option>
        <option value="space">Just vertical space</option>
      </FormSelect>
    </FormField>
  );
}
