"use client";

/**
 * AnalyzeViewButton — the shared "Analyze with AI" trigger for list pages.
 *
 * One component so the label, sparkle mark, and AI styling stay identical on
 * every surface. Uses the Button `ai` variant (accent gradient + glow) so the
 * control visibly reads as an AI-powered action, per the app's convention
 * that gold/amber marks AI (SuggestionPanel, hypotheses box).
 */

import { Button } from "@/components/ui/button";

/** Four-point sparkle — the AI mark. Inherits currentColor. */
function SparkleIcon({ className = "h-3.5 w-3.5" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden className={className}>
      <path d="M12 2c.6 4.8 2.9 7.7 8 8-5.1.3-7.4 3.2-8 8-.6-4.8-2.9-7.7-8-8 5.1-.3 7.4-3.2 8-8z" />
      <path d="M19 14c.3 2.1 1.3 3.4 3.5 3.5-2.2.1-3.2 1.4-3.5 3.5-.3-2.1-1.3-3.4-3.5-3.5 2.2-.1 3.2-1.4 3.5-3.5z" opacity="0.7" />
    </svg>
  );
}

interface AnalyzeViewButtonProps {
  onClick: () => void;
}

export function AnalyzeViewButton({ onClick }: AnalyzeViewButtonProps) {
  return (
    <Button variant="ai" size="sm" onClick={onClick} title="AI analysis of the currently filtered list">
      <SparkleIcon />
      Analyze with AI
    </Button>
  );
}

export { SparkleIcon };
