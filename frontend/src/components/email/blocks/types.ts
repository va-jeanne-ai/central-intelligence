/**
 * Block type system for the email page builder.
 *
 * Every editable unit of an email is a Block. The compose page maintains
 * a `Block[]` in state; `renderBlocksToHtml(blocks)` serialises that array
 * to the Gmail-safe HTML we persist as body_html and (eventually) send.
 *
 * Why this exists vs. WYSIWYG: a discriminated union with explicit fields
 * separates the editing model (typed objects) from the rendering model
 * (a deterministic emitter), so the canvas can show a clean preview
 * while the editor side lives in a structured right-panel form.
 *
 * Adding a block type: append to the union, add a factory case in
 * `createBlock`, add a renderer in `render.ts`, build a `XBlockCanvas` +
 * `XBlockEditor` pair in `XBlock.tsx`, and wire the PageBuilder palette.
 */

export type Alignment = "left" | "center" | "right";
export type DividerStyle = "solid" | "dashed" | "space";
export type HeadingLevel = 1 | 2 | 3;

export type BlockType =
  | "hero"
  | "heading"
  | "paragraph"
  | "image"
  | "button"
  | "divider";

interface BaseBlock {
  id: string;
}

export interface HeroBlock extends BaseBlock {
  type: "hero";
  kicker: string;
  headline: string;
  subheading: string;
  gradient_from: string;
  gradient_to: string;
  text_color: string;
}

export interface HeadingBlock extends BaseBlock {
  type: "heading";
  text: string;
  level: HeadingLevel;
  alignment: Alignment;
  color: string;
}

export interface ParagraphBlock extends BaseBlock {
  type: "paragraph";
  text: string;
  alignment: Alignment;
}

export interface ImageBlock extends BaseBlock {
  type: "image";
  src: string;
  alt: string;
  alignment: Alignment;
}

export interface ButtonBlock extends BaseBlock {
  type: "button";
  text: string;
  href: string;
  color: string;
}

export interface DividerBlock extends BaseBlock {
  type: "divider";
  style: DividerStyle;
}

export type Block =
  | HeroBlock
  | HeadingBlock
  | ParagraphBlock
  | ImageBlock
  | ButtonBlock
  | DividerBlock;

// ─── Factory ──────────────────────────────────────────────────────────────────

function newId(): string {
  // crypto.randomUUID is on every modern browser + Node 19+. Fall back
  // to a timestamp-based id for ancient runtimes (tests, old Safari).
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `b_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`;
}

/**
 * Build a new block of the given type with sensible defaults. Pass `overrides`
 * to pre-populate fields — used by templates and by the AI Fill flow.
 */
export function createBlock<T extends BlockType>(
  type: T,
  overrides: Partial<Extract<Block, { type: T }>> = {},
): Extract<Block, { type: T }> {
  const id = newId();
  let block: Block;
  switch (type) {
    case "hero":
      block = {
        id,
        type: "hero",
        kicker: "ISSUE 42",
        headline: "Your headline here",
        subheading: "One short subheading that sets up the email.",
        gradient_from: "#10b981",
        gradient_to: "#047857",
        text_color: "#ffffff",
      };
      break;
    case "heading":
      block = {
        id,
        type: "heading",
        text: "New heading",
        level: 2,
        alignment: "left",
        color: "#111827",
      };
      break;
    case "paragraph":
      block = {
        id,
        type: "paragraph",
        text: "Click to edit this paragraph. Write whatever fits.",
        alignment: "left",
      };
      break;
    case "image":
      block = {
        id,
        type: "image",
        src: "",
        alt: "",
        alignment: "center",
      };
      break;
    case "button":
      block = {
        id,
        type: "button",
        text: "Call to action",
        href: "https://",
        color: "#6366f1",
      };
      break;
    case "divider":
      block = { id, type: "divider", style: "solid" };
      break;
    default:
      throw new Error(`Unknown block type: ${type as string}`);
  }
  return { ...(block as Extract<Block, { type: T }>), ...overrides };
}

// ─── Display metadata for the palette ─────────────────────────────────────────

export const BLOCK_LABELS: Record<BlockType, string> = {
  hero: "Hero",
  heading: "Heading",
  paragraph: "Paragraph",
  image: "Image",
  button: "Button",
  divider: "Divider",
};

export const BLOCK_ICONS: Record<BlockType, string> = {
  hero: "🌅",
  heading: "🅷",
  paragraph: "¶",
  image: "🖼",
  button: "🔘",
  divider: "—",
};

export const BLOCK_DESCRIPTIONS: Record<BlockType, string> = {
  hero: "Gradient banner with kicker, headline, subheading",
  heading: "H1 / H2 / H3 with alignment + color",
  paragraph: "Body text with alignment",
  image: "Image by URL with alt text",
  button: "Call-to-action button with link",
  divider: "Horizontal rule or vertical space",
};

/** Display order in the side palette. */
export const PALETTE_ORDER: BlockType[] = [
  "hero",
  "heading",
  "paragraph",
  "image",
  "button",
  "divider",
];
