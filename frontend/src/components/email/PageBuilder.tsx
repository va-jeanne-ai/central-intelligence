"use client";

/**
 * Three-column page-builder shell for the email composer.
 *
 * Layout:
 *   [ palette 180px ]  [ canvas 1fr ]  [ edit panel 320px ]
 *
 * The page (compose/page.tsx) owns `blocks`, `selectedBlockIndex`, and the
 * mutation helpers. This component is presentational — it dispatches user
 * intent (click/add/remove/move/update) via props.
 *
 * v2 follow-ups documented in the code:
 *   - Drag-and-drop reordering (v1 = up/down arrows).
 *   - Per-block "Rewrite with AI" button on Paragraph (seeds /email/draft
 *     with the paragraph's current text, replaces the block on response).
 *   - Save/load custom block presets ("Greg's CTA style").
 */

import { Card, CardBody, CardHeader } from "@/components/ui/card";
import {
  BLOCK_DESCRIPTIONS,
  BLOCK_ICONS,
  BLOCK_LABELS,
  PALETTE_ORDER,
  type Block,
  type BlockType,
} from "./blocks/types";
import { HeroBlockCanvas, HeroBlockEditor } from "./blocks/HeroBlock";
import {
  HeadingBlockCanvas,
  HeadingBlockEditor,
} from "./blocks/HeadingBlock";
import {
  ParagraphBlockCanvas,
  ParagraphBlockEditor,
} from "./blocks/ParagraphBlock";
import { ImageBlockCanvas, ImageBlockEditor } from "./blocks/ImageBlock";
import { ButtonBlockCanvas, ButtonBlockEditor } from "./blocks/ButtonBlock";
import {
  DividerBlockCanvas,
  DividerBlockEditor,
} from "./blocks/DividerBlock";

export interface PageBuilderProps {
  blocks: Block[];
  selectedIndex: number | null;
  onSelect: (index: number | null) => void;
  onAdd: (type: BlockType) => void;
  onRemove: (index: number) => void;
  onMove: (index: number, direction: -1 | 1) => void;
  onUpdate: (index: number, patch: Partial<Block>) => void;
  onAiAssist?: () => void;
  aiBusy?: boolean;
}

// ─── Canvas-side dispatch ─────────────────────────────────────────────────────

function BlockCanvas({ block }: { block: Block }) {
  switch (block.type) {
    case "hero":
      return <HeroBlockCanvas block={block} />;
    case "heading":
      return <HeadingBlockCanvas block={block} />;
    case "paragraph":
      return <ParagraphBlockCanvas block={block} />;
    case "image":
      return <ImageBlockCanvas block={block} />;
    case "button":
      return <ButtonBlockCanvas block={block} />;
    case "divider":
      return <DividerBlockCanvas block={block} />;
  }
}

// ─── Editor-side dispatch ─────────────────────────────────────────────────────
// updateBlock receives a `Partial<Block>` but the per-block editors are
// strongly typed to their own variant. We cast at the dispatch boundary —
// the discriminated union's narrowing keeps everything safe inside each
// editor component.

function BlockEditor({
  block,
  onChange,
}: {
  block: Block;
  onChange: (patch: Partial<Block>) => void;
}) {
  switch (block.type) {
    case "hero":
      return (
        <HeroBlockEditor
          block={block}
          onChange={onChange as (p: Partial<typeof block>) => void}
        />
      );
    case "heading":
      return (
        <HeadingBlockEditor
          block={block}
          onChange={onChange as (p: Partial<typeof block>) => void}
        />
      );
    case "paragraph":
      return (
        <ParagraphBlockEditor
          block={block}
          onChange={onChange as (p: Partial<typeof block>) => void}
        />
      );
    case "image":
      return (
        <ImageBlockEditor
          block={block}
          onChange={onChange as (p: Partial<typeof block>) => void}
        />
      );
    case "button":
      return (
        <ButtonBlockEditor
          block={block}
          onChange={onChange as (p: Partial<typeof block>) => void}
        />
      );
    case "divider":
      return (
        <DividerBlockEditor
          block={block}
          onChange={onChange as (p: Partial<typeof block>) => void}
        />
      );
  }
}

// ─── Block-shell wrapper (selection ring + mini toolbar) ──────────────────────

function BlockShell({
  block,
  index,
  isSelected,
  isFirst,
  isLast,
  onSelect,
  onMove,
  onRemove,
}: {
  block: Block;
  index: number;
  isSelected: boolean;
  isFirst: boolean;
  isLast: boolean;
  onSelect: () => void;
  onMove: (direction: -1 | 1) => void;
  onRemove: () => void;
}) {
  return (
    <div
      className={`group relative transition-shadow ${
        isSelected
          ? "outline outline-2 outline-accent-500 outline-offset-[-2px]"
          : "outline outline-1 outline-transparent hover:outline-accent-200 outline-offset-[-1px]"
      }`}
      onClick={(e) => {
        e.stopPropagation();
        onSelect();
      }}
      role="button"
      tabIndex={0}
      aria-label={`${BLOCK_LABELS[block.type]} block`}
    >
      <BlockCanvas block={block} />

      {/* Mini toolbar — visible on hover or when selected */}
      <div
        className={`absolute top-2 right-2 flex items-center gap-1 transition-opacity ${
          isSelected ? "opacity-100" : "opacity-0 group-hover:opacity-100"
        }`}
      >
        <ToolbarBtn
          onClick={(e) => {
            e.stopPropagation();
            onMove(-1);
          }}
          disabled={isFirst}
          title="Move up"
        >
          ↑
        </ToolbarBtn>
        <ToolbarBtn
          onClick={(e) => {
            e.stopPropagation();
            onMove(1);
          }}
          disabled={isLast}
          title="Move down"
        >
          ↓
        </ToolbarBtn>
        <ToolbarBtn
          onClick={(e) => {
            e.stopPropagation();
            onRemove();
          }}
          title="Delete"
          danger
        >
          ✕
        </ToolbarBtn>
      </div>

      {/* Type label — top-left, only when selected */}
      {isSelected && (
        <div className="absolute top-2 left-2 text-[10px] font-bold uppercase tracking-wider bg-accent-500 text-white px-2 py-0.5 rounded">
          {BLOCK_LABELS[block.type]} · {index + 1}
        </div>
      )}
    </div>
  );
}

function ToolbarBtn({
  onClick,
  disabled,
  title,
  danger,
  children,
}: {
  onClick: (e: React.MouseEvent) => void;
  disabled?: boolean;
  title: string;
  danger?: boolean;
  children: React.ReactNode;
}) {
  const base =
    "w-7 h-7 flex items-center justify-center rounded-md text-sm font-bold shadow-sm transition-colors disabled:opacity-40 disabled:cursor-not-allowed";
  const tone = danger
    ? "bg-white text-red-600 hover:bg-red-50 border border-red-200"
    : "bg-white text-gray-700 hover:bg-gray-100 border border-gray-200";
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      title={title}
      aria-label={title}
      className={`${base} ${tone}`}
    >
      {children}
    </button>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────

export default function PageBuilder({
  blocks,
  selectedIndex,
  onSelect,
  onAdd,
  onRemove,
  onMove,
  onUpdate,
  onAiAssist,
  aiBusy,
}: PageBuilderProps) {
  const selectedBlock =
    selectedIndex !== null ? blocks[selectedIndex] : null;

  return (
    <div className="grid grid-cols-[180px_1fr_320px] gap-4">
      {/* ── Palette ───────────────────────────────────────────────────────── */}
      <Card>
        <CardHeader title="Add block" />
        <CardBody className="space-y-1.5 !px-2 !py-2">
          {PALETTE_ORDER.map((t) => (
            <button
              key={t}
              type="button"
              onClick={() => onAdd(t)}
              title={BLOCK_DESCRIPTIONS[t]}
              className="w-full flex items-center gap-2 px-2 py-2 rounded-md border border-gray-200 bg-white hover:bg-accent-50 hover:border-accent-300 text-left transition-colors"
            >
              <span className="text-base leading-none" aria-hidden>
                {BLOCK_ICONS[t]}
              </span>
              <span className="text-[13px] font-medium text-gray-700">
                {BLOCK_LABELS[t]}
              </span>
            </button>
          ))}
          {onAiAssist && (
            <button
              type="button"
              onClick={onAiAssist}
              disabled={aiBusy}
              className="mt-3 w-full inline-flex items-center justify-center gap-1.5 px-3 py-2 rounded-md bg-amber-50 border border-amber-200 text-amber-800 text-[12px] font-semibold hover:bg-amber-100 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {aiBusy ? "Generating…" : "✨ Fill with AI"}
            </button>
          )}
        </CardBody>
      </Card>

      {/* ── Canvas ────────────────────────────────────────────────────────── */}
      <div
        className="bg-gray-100 rounded-xl border border-gray-200 overflow-hidden"
        onClick={() => onSelect(null)}
      >
        <div className="py-10 px-8 flex justify-center">
          <div
            className="w-full max-w-[620px] bg-white rounded-xl shadow-md overflow-hidden"
            onClick={(e) => e.stopPropagation()}
          >
            {blocks.length === 0 ? (
              <div className="py-20 text-center text-sm text-gray-400">
                Add blocks from the left to start building your email.
              </div>
            ) : (
              blocks.map((block, i) => (
                <BlockShell
                  key={block.id}
                  block={block}
                  index={i}
                  isSelected={selectedIndex === i}
                  isFirst={i === 0}
                  isLast={i === blocks.length - 1}
                  onSelect={() => onSelect(i)}
                  onMove={(dir) => onMove(i, dir)}
                  onRemove={() => onRemove(i)}
                />
              ))
            )}
          </div>
        </div>
      </div>

      {/* ── Edit panel ────────────────────────────────────────────────────── */}
      <Card>
        <CardHeader
          title={
            selectedBlock
              ? `Edit ${BLOCK_LABELS[selectedBlock.type]}`
              : "Edit"
          }
        />
        <CardBody>
          {selectedBlock && selectedIndex !== null ? (
            <BlockEditor
              block={selectedBlock}
              onChange={(patch) => onUpdate(selectedIndex, patch)}
            />
          ) : (
            <p className="text-[13px] text-gray-400 italic leading-relaxed">
              Click a block in the canvas to edit it. Or pick a block type
              from the left to add a new one.
            </p>
          )}
        </CardBody>
      </Card>
    </div>
  );
}
