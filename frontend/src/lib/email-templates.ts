/**
 * Starter email templates for the page-builder compose flow.
 *
 * Each template is an ordered `Block[]`. The compose page loads the
 * array as the initial canvas state; users edit each block via the
 * right-panel form. The final HTML is produced by
 * `renderBlocksToHtml` at save time — see
 * `components/email/blocks/render.ts`.
 *
 * Adding a template: append to EMAIL_TEMPLATES. The blocks must use
 * factory defaults overridden with overrides, so the resulting array
 * always passes the Block type checker.
 *
 * v2 follow-ups noted inline as TODO comments — currently the
 * Newsletter's quote callout and the Welcome template's gradient
 * step badges are folded into regular paragraphs because we only
 * have 6 block types in v1.
 */

import {
  createBlock,
  type Block,
} from "@/components/email/blocks/types";

export interface EmailTemplate {
  id: string;
  name: string;
  description: string;
  thumbnail: string; // emoji
  blocks: Block[];
}

function newsletter(): Block[] {
  return [
    createBlock("hero", {
      kicker: "ISSUE 42 · APRIL 2026",
      headline: "This Week in Coaching",
      subheading:
        "Insights, client wins, and the one thing we'd try this week if we were you.",
      gradient_from: "#10b981",
      gradient_to: "#047857",
    }),
    createBlock("heading", {
      text: "The pattern we're seeing across every discovery call this month",
      level: 2,
    }),
    createBlock("paragraph", {
      text: "Open with a short, punchy paragraph that gives the reader a reason to keep reading. Two or three sentences — what's the one thing they'll get out of this issue?\n\nBuild on it. Pose a question, share a specific story from last week, or call out a stat that surprised you.",
    }),
    // TODO(v2): Callout block — for now the quote folds into an italic paragraph.
    createBlock("paragraph", {
      text: '"The quote or stat that anchors this issue. Make it strong enough to stand on its own."\n\n— Source / client name',
    }),
    createBlock("divider", { style: "solid" }),
    createBlock("heading", {
      text: "What's inside",
      level: 3,
    }),
    // TODO(v2): List block with numbered round badges — for now a bulleted paragraph.
    createBlock("paragraph", {
      text: "1. One actionable insight from this week's calls.\n2. A client win worth celebrating.\n3. Something to try before next Monday.",
    }),
    createBlock("button", {
      text: "Read the full breakdown",
      href: "https://",
      color: "#10b981",
    }),
    createBlock("paragraph", {
      text: "Central Intelligence · Coaching insights, every Friday.\n\nYou're getting this because you opted in. Unsubscribe.",
    }),
  ];
}

function promotional(): Block[] {
  return [
    createBlock("hero", {
      kicker: "⏰ LIMITED TIME",
      headline: "Save 30% This Week Only",
      subheading:
        "The one-line promise that makes the offer impossible to scroll past.",
      gradient_from: "#dc2626",
      gradient_to: "#f59e0b",
    }),
    createBlock("heading", {
      text: "Here's what you get",
      level: 2,
      alignment: "center",
    }),
    createBlock("paragraph", {
      text: "One short paragraph explaining what the offer is and why it matters right now. Be specific — what do they get, what does it cost, and why is the deadline real?",
      alignment: "center",
    }),
    // TODO(v2): List block with checkmark badges.
    createBlock("paragraph", {
      text: "✓ Tangible benefit — describe one specific outcome they get.\n\n✓ Another concrete thing — keep these short and specific.\n\n✓ The unexpected bonus — the one that tips them over.",
    }),
    createBlock("button", {
      text: "Claim 30% off",
      href: "https://",
      color: "#dc2626",
    }),
    createBlock("paragraph", {
      text: "⏰ Offer ends Sunday at midnight. No extensions, no exceptions.",
      alignment: "center",
    }),
  ];
}

function welcome(): Block[] {
  return [
    createBlock("hero", {
      kicker: "",
      headline: "👋 Welcome aboard",
      subheading:
        "We're so glad you're here. Let's get you set up in under five minutes.",
      gradient_from: "#6366f1",
      gradient_to: "#ec4899",
    }),
    createBlock("paragraph", {
      text: "Hey — quick personal note before we dive in.\n\nThanks for joining. Here's the very first thing I'd love you to do — it takes about 90 seconds and unlocks the rest of what's coming.\n\nReplace this with the one specific action you want them to take. The clearer the ask, the higher the response rate.",
    }),
    createBlock("button", {
      text: "Do the first thing",
      href: "https://",
      color: "#6366f1",
    }),
    createBlock("divider", { style: "solid" }),
    createBlock("heading", {
      text: "Here's what to expect this week",
      level: 3,
    }),
    // TODO(v2): Numbered list block with gradient step badges.
    createBlock("paragraph", {
      text: "1. Tomorrow: a short note about the most common stuck point.\n\n2. In a few days: the one resource that made the biggest difference for past clients.\n\n3. End of week: an invitation to the next live session.",
    }),
    createBlock("paragraph", {
      text: "Got questions? Just hit reply.\n\nThese go straight to my inbox — I read every one.\n\n— Greg",
    }),
  ];
}

export const EMAIL_TEMPLATES: EmailTemplate[] = [
  {
    id: "newsletter",
    name: "Newsletter",
    description:
      "Recurring update with a hero, lead story, what's-inside list, and CTA.",
    thumbnail: "📰",
    blocks: newsletter(),
  },
  {
    id: "promotional",
    name: "Promotional / Sale",
    description:
      "Time-limited offer with a dramatic hero, benefit list, prominent CTA, and deadline.",
    thumbnail: "🏷️",
    blocks: promotional(),
  },
  {
    id: "welcome",
    name: "Welcome / Re-engagement",
    description:
      "Friendly first-touch with a single clear ask and what-to-expect-next checklist.",
    thumbnail: "👋",
    blocks: welcome(),
  },
];

export function getTemplate(id: string): EmailTemplate | undefined {
  return EMAIL_TEMPLATES.find((t) => t.id === id);
}
