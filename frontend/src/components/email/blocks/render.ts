/**
 * Serialise a Block[] to Gmail-safe email HTML.
 *
 * This is the sole source of truth for what gets persisted as
 * `body_html` and (eventually) sent through Mailchimp. The canvas-side
 * preview in each `*BlockCanvas` component renders approximate fidelity
 * using Tailwind, but the buck stops here.
 *
 * Gmail-safe constraints maintained:
 *  - Table-based layout only (no flexbox, no grid).
 *  - Inline styles only — no <style> blocks, no external CSS, no media
 *    queries.
 *  - No JavaScript, no data-* attributes, no comments.
 *  - User-supplied text always passes through `escapeHtml`.
 *
 * Known limitation: `linear-gradient(...)` works in Apple Mail, Gmail
 * web, and iOS Mail but Outlook desktop falls back to the second color
 * stop as a solid background. Acceptable for this project — Greg's
 * audience is consumer-grade, not enterprise Outlook.
 */

import type {
  Block,
  ButtonBlock,
  DividerBlock,
  HeadingBlock,
  HeroBlock,
  ImageBlock,
  ParagraphBlock,
} from "./types";

// ─── Public ───────────────────────────────────────────────────────────────────

export function renderBlocksToHtml(blocks: Block[]): string {
  const body = blocks.map(renderBlock).join("");
  return SCAFFOLD_OPEN + body + SCAFFOLD_CLOSE;
}

export function escapeHtml(input: string): string {
  return input
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

// ─── Scaffold ─────────────────────────────────────────────────────────────────
// Outer grey body → centred 620px white card with rounded corners + shadow.
// Same shape every email has — block list slots into the inner <table>.

const SCAFFOLD_OPEN = `
<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="background-color:#f3f4f6;padding:40px 0;font-family:'Helvetica Neue',Helvetica,Arial,sans-serif;">
  <tr><td align="center">
    <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="620" style="background-color:#ffffff;border-radius:14px;overflow:hidden;box-shadow:0 4px 20px rgba(0,0,0,0.08);">
`.trim();

const SCAFFOLD_CLOSE = `
    </table>
  </td></tr>
</table>
`.trim();

// ─── Dispatch ─────────────────────────────────────────────────────────────────

function renderBlock(block: Block): string {
  switch (block.type) {
    case "hero":
      return renderHero(block);
    case "heading":
      return renderHeading(block);
    case "paragraph":
      return renderParagraph(block);
    case "image":
      return renderImage(block);
    case "button":
      return renderButton(block);
    case "divider":
      return renderDivider(block);
  }
}

// ─── Per-block renderers ──────────────────────────────────────────────────────

function renderHero(b: HeroBlock): string {
  // linear-gradient in Apple Mail / Gmail web / iOS Mail; Outlook desktop
  // falls back to the gradient_to color as a solid. Documented in the
  // module header.
  return `
<tr><td style="padding:0;">
  <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="background:linear-gradient(135deg,${b.gradient_from} 0%,${b.gradient_to} 100%);background-color:${b.gradient_to};">
    <tr><td style="padding:56px 40px 48px 40px;color:${b.text_color};">
      ${b.kicker ? `<p style="margin:0 0 12px 0;font-size:11px;letter-spacing:3px;text-transform:uppercase;color:${b.text_color};opacity:0.85;font-weight:700;">${escapeHtml(b.kicker)}</p>` : ""}
      <h1 style="margin:0;font-size:38px;line-height:46px;color:${b.text_color};font-weight:800;letter-spacing:-0.5px;">${escapeHtml(b.headline)}</h1>
      ${b.subheading ? `<p style="margin:14px 0 0 0;font-size:17px;line-height:26px;color:${b.text_color};opacity:0.94;max-width:480px;">${escapeHtml(b.subheading)}</p>` : ""}
    </td></tr>
  </table>
</td></tr>`.trim();
}

function renderHeading(b: HeadingBlock): string {
  const sizes: Record<1 | 2 | 3, { size: number; line: number; weight: number }> = {
    1: { size: 30, line: 38, weight: 800 },
    2: { size: 22, line: 30, weight: 700 },
    3: { size: 17, line: 24, weight: 700 },
  };
  const s = sizes[b.level];
  const tag = `h${b.level}`;
  return `
<tr><td style="padding:24px 40px 8px 40px;">
  <${tag} style="margin:0;font-size:${s.size}px;line-height:${s.line}px;color:${b.color};font-weight:${s.weight};text-align:${b.alignment};letter-spacing:-0.3px;">${escapeHtml(b.text)}</${tag}>
</td></tr>`.trim();
}

function renderParagraph(b: ParagraphBlock): string {
  // Preserve user-entered line breaks (single \n → <br>) but not double
  // newlines — those become block-level paragraph breaks via inline margin.
  const escaped = escapeHtml(b.text);
  const withBreaks = escaped
    .split(/\n{2,}/)
    .map((para) => para.replace(/\n/g, "<br/>"))
    .map(
      (para) =>
        `<p style="margin:0 0 14px 0;font-size:16px;line-height:26px;color:#374151;text-align:${b.alignment};">${para}</p>`,
    )
    .join("");
  return `
<tr><td style="padding:8px 40px;">
  ${withBreaks}
</td></tr>`.trim();
}

function renderImage(b: ImageBlock): string {
  if (!b.src) {
    // Empty image block: render a small grey placeholder so the saved
    // HTML still has a visible artifact (better than silently missing).
    return `
<tr><td style="padding:16px 40px;text-align:${b.alignment};">
  <div style="display:inline-block;width:120px;height:80px;background-color:#f3f4f6;border:1px dashed #d1d5db;color:#9ca3af;font-size:11px;line-height:80px;text-align:center;">No image</div>
</td></tr>`.trim();
  }
  return `
<tr><td style="padding:16px 40px;text-align:${b.alignment};">
  <img src="${escapeHtml(b.src)}" alt="${escapeHtml(b.alt)}" style="display:inline-block;max-width:100%;height:auto;border:0;outline:none;text-decoration:none;" />
</td></tr>`.trim();
}

function renderButton(b: ButtonBlock): string {
  // Slightly darker shade for the gradient end so the button reads as
  // a button regardless of its base color choice.
  const darker = darkenHex(b.color);
  return `
<tr><td align="center" style="padding:24px 40px 32px 40px;">
  <a href="${escapeHtml(b.href)}" style="display:inline-block;background:linear-gradient(135deg,${b.color} 0%,${darker} 100%);background-color:${b.color};color:#ffffff;text-decoration:none;padding:16px 36px;border-radius:8px;font-weight:700;font-size:16px;letter-spacing:0.3px;box-shadow:0 4px 14px rgba(0,0,0,0.15);">${escapeHtml(b.text)} →</a>
</td></tr>`.trim();
}

function renderDivider(b: DividerBlock): string {
  if (b.style === "space") {
    return `<tr><td style="height:32px;line-height:32px;font-size:0;">&nbsp;</td></tr>`;
  }
  const borderStyle = b.style === "dashed" ? "dashed" : "solid";
  return `
<tr><td style="padding:16px 40px;">
  <hr style="border:0;border-top:1px ${borderStyle} #e5e7eb;margin:0;" />
</td></tr>`.trim();
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

/**
 * Darken a #rrggbb hex string by ~15% for the button gradient's end stop.
 * Lossy fallback — returns the input unchanged on parse failure rather
 * than throwing inside a render call.
 */
function darkenHex(hex: string): string {
  const match = /^#?([0-9a-f]{6})$/i.exec(hex);
  if (!match) return hex;
  const n = parseInt(match[1], 16);
  const r = Math.max(0, ((n >> 16) & 0xff) - 30);
  const g = Math.max(0, ((n >> 8) & 0xff) - 30);
  const b = Math.max(0, (n & 0xff) - 30);
  return `#${((r << 16) | (g << 8) | b).toString(16).padStart(6, "0")}`;
}
