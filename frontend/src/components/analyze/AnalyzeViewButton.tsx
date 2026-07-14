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
import { SparkleIcon } from "@/components/ui/sparkle-icon";

interface AnalyzeViewButtonProps {
  onClick: () => void;
}

export function AnalyzeViewButton({ onClick }: AnalyzeViewButtonProps) {
  return (
    <Button
      variant="ai"
      size="sm"
      onClick={onClick}
      data-tour="analyze-button"
      title="AI analysis of the currently filtered list"
    >
      <SparkleIcon />
      Analyze with AI
    </Button>
  );
}
