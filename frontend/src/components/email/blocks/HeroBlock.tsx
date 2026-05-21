"use client";

import { FormField, FormInput, FormTextarea } from "@/components/ui/form-field";
import type { HeroBlock } from "./types";

export function HeroBlockCanvas({ block }: { block: HeroBlock }) {
  return (
    <div
      className="w-full"
      style={{
        background: `linear-gradient(135deg, ${block.gradient_from} 0%, ${block.gradient_to} 100%)`,
        color: block.text_color,
        padding: "56px 40px 48px 40px",
      }}
    >
      {block.kicker && (
        <p
          className="m-0 text-[11px] font-bold uppercase tracking-[3px] opacity-85"
          style={{ color: block.text_color, marginBottom: 12 }}
        >
          {block.kicker}
        </p>
      )}
      <h1
        className="m-0 font-extrabold tracking-tight"
        style={{
          color: block.text_color,
          fontSize: 38,
          lineHeight: "46px",
          letterSpacing: "-0.5px",
        }}
      >
        {block.headline}
      </h1>
      {block.subheading && (
        <p
          className="opacity-95"
          style={{
            color: block.text_color,
            margin: "14px 0 0 0",
            fontSize: 17,
            lineHeight: "26px",
            maxWidth: 480,
          }}
        >
          {block.subheading}
        </p>
      )}
    </div>
  );
}

export function HeroBlockEditor({
  block,
  onChange,
}: {
  block: HeroBlock;
  onChange: (patch: Partial<HeroBlock>) => void;
}) {
  return (
    <div className="space-y-4">
      <FormField label="Kicker (small caps label)">
        <FormInput
          type="text"
          value={block.kicker}
          onChange={(e) => onChange({ kicker: e.target.value })}
        />
      </FormField>
      <FormField label="Headline">
        <FormTextarea
          rows={2}
          value={block.headline}
          onChange={(e) => onChange({ headline: e.target.value })}
        />
      </FormField>
      <FormField label="Subheading">
        <FormTextarea
          rows={3}
          value={block.subheading}
          onChange={(e) => onChange({ subheading: e.target.value })}
        />
      </FormField>
      <div className="grid grid-cols-3 gap-3">
        <FormField label="Gradient start">
          <input
            type="color"
            value={block.gradient_from}
            onChange={(e) => onChange({ gradient_from: e.target.value })}
            className="h-10 w-full rounded-md border border-gray-200 cursor-pointer"
          />
        </FormField>
        <FormField label="Gradient end">
          <input
            type="color"
            value={block.gradient_to}
            onChange={(e) => onChange({ gradient_to: e.target.value })}
            className="h-10 w-full rounded-md border border-gray-200 cursor-pointer"
          />
        </FormField>
        <FormField label="Text color">
          <input
            type="color"
            value={block.text_color}
            onChange={(e) => onChange({ text_color: e.target.value })}
            className="h-10 w-full rounded-md border border-gray-200 cursor-pointer"
          />
        </FormField>
      </div>
    </div>
  );
}
