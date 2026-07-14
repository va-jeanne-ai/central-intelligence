// What's-new tour definitions. Data only — rendering lives in
// components/tour/. Bump TOURS_VERSION when shipping a new batch of
// features; the dialog auto-opens once per version.

export const TOURS_VERSION = "2026-07";

export interface TourStep {
  /** Matches a data-tour attribute on the target element. */
  anchor: string;
  title: string;
  body: string;
}

export interface TourDef {
  id: string;
  title: string;
  blurb: string;
  route: string;
  steps: TourStep[];
}

export const TOURS: TourDef[] = [
  {
    id: "analyze-view",
    title: "Analyze any list with AI",
    blurb:
      "One click turns the list you're looking at — filters and all — into a plain-English analysis.",
    route: "/leads",
    steps: [
      {
        anchor: "analyze-button",
        title: "Analyze any list with AI",
        body:
          "This button reads the list exactly as you've filtered it — same rows, same date range — and writes a short analysis.",
      },
      {
        anchor: "analyze-button",
        title: "What you get",
        body:
          "A plain-English summary with key counts, standout patterns, and a \"show the data\" section backing every number. Nothing is saved — it's a fresh read each time.",
      },
      {
        anchor: "analyze-button",
        title: "It's on four pages",
        body:
          "Leads, Appointments, Sales Calls, and Members each have this same button at the end of their filter bar.",
      },
    ],
  },
  {
    id: "copy-actions",
    title: "Formatted content you can copy anywhere",
    blurb:
      "Generated marketing content now renders with real formatting, plus one-click copy buttons. Generate something first to see it live.",
    route: "/marketing/social/scripts",
    steps: [
      {
        anchor: "generated-output",
        title: "Cleaner generated content",
        body:
          "Generated marketing content now shows real formatting — headings, bullets, bold — instead of raw text.",
      },
      {
        anchor: "copy-actions",
        title: "Copy it your way",
        body:
          "\"Copy text\" grabs clean text for emails or DMs. \"Copy Markdown\" keeps the formatting for docs and Notion.",
      },
    ],
  },
  {
    id: "calendar-jump",
    title: "Jump to any date on the calendar",
    blurb:
      "Skip the arrow-clicking — the appointments calendar now has a jump-to-date picker. Switch to calendar view to see it.",
    route: "/appointments",
    steps: [
      {
        anchor: "calendar-jump-date",
        title: "Jump straight to a date",
        body:
          "Pick any date here and the calendar moves right to it — no more paging through weeks with the arrows.",
      },
    ],
  },
  {
    id: "data-freshness",
    title: "Check data freshness & sync on demand",
    blurb:
      "See at a glance whether every data source is up to date, and pull the latest WGR data yourself.",
    route: "/integrations",
    steps: [
      {
        anchor: "freshness-check",
        title: "Is the data current?",
        body:
          "This checks every connected source and tells you which are fresh and which look stale, with how old each one is.",
      },
      {
        anchor: "wgr-sync-now",
        title: "Pull the latest now",
        body:
          "If WGR data looks behind, this pulls the newest rows on demand — it usually takes about a minute.",
      },
    ],
  },
];

export function getTour(id: string): TourDef | undefined {
  return TOURS.find((t) => t.id === id);
}
