/**
 * Molecule: GeneratorLayout
 *
 * Shared shell for the marketing "AI generator" pages (ad copy, social
 * scripts, DM templates, offer copy). All four pages share the same
 * structure: a back-link + heading, a "Configure X" form card, and a
 * "Generated X" results card that cycles through empty / loading / error /
 * content states. The actual form fields and result rendering stay
 * page-specific (they diverge too much to generalize), but the shell,
 * loading skeleton, empty state, and error state are unified here so all
 * four pages behave consistently.
 */

import Link from "next/link";
import { Card, CardHeader, CardBody } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { SparkleIcon } from "@/components/ui/sparkle-icon";

// ─── Page header ────────────────────────────────────────────────────────────

interface GeneratorHeaderProps {
  title: string;
  description: string;
  backHref?: string;
  backLabel?: string;
}

export function GeneratorHeader({
  title,
  description,
  backHref,
  backLabel = "Back",
}: GeneratorHeaderProps) {
  return (
    <div>
      {backHref && (
        <Link
          href={backHref}
          className="inline-flex items-center gap-1 text-xs font-medium text-emerald-600 hover:text-emerald-700 transition-colors mb-2"
        >
          <span aria-hidden="true">←</span>
          {backLabel}
        </Link>
      )}
      <h1 className="text-xl font-bold text-gray-900">{title}</h1>
      <p className="text-sm text-gray-500 mt-0.5">{description}</p>
    </div>
  );
}

// ─── Generate button ────────────────────────────────────────────────────────
// Renders the shared Button `ai` variant (gold gradient + glow) so every
// marketing generator page reads as an AI-triggering action, per the app's
// AI-action design convention. Molecule's props/API are unchanged — this is
// an internal restyle only.

function Spinner() {
  return (
    <svg
      className="animate-spin w-4 h-4"
      xmlns="http://www.w3.org/2000/svg"
      fill="none"
      viewBox="0 0 24 24"
      aria-hidden="true"
    >
      <circle
        className="opacity-25"
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        strokeWidth="4"
      />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
      />
    </svg>
  );
}

interface GenerateButtonProps {
  onClick: () => void;
  disabled?: boolean;
  isGenerating: boolean;
  idleLabel?: string;
  busyLabel?: string;
}

export function GenerateButton({
  onClick,
  disabled = false,
  isGenerating,
  idleLabel = "Generate",
  busyLabel = "Generating…",
}: GenerateButtonProps) {
  return (
    <Button variant="ai" onClick={onClick} disabled={disabled || isGenerating}>
      {isGenerating ? (
        <>
          <Spinner />
          {busyLabel}
        </>
      ) : (
        <>
          <SparkleIcon />
          {idleLabel}
        </>
      )}
    </Button>
  );
}

// ─── Results panel ──────────────────────────────────────────────────────────

interface ResultsPanelProps {
  title: string;
  status: "empty" | "loading" | "error" | "content";
  emptyIcon?: string;
  emptyTitle: string;
  emptyDescription: string;
  errorTitle?: string;
  errorDescription: string;
  headerAction?: React.ReactNode;
  children?: React.ReactNode;
}

/**
 * Results card with unified empty / loading / error / content states.
 * `status` drives which body renders; `children` is only rendered when
 * `status === "content"`.
 */
export function ResultsPanel({
  title,
  status,
  emptyIcon = "✨",
  emptyTitle,
  emptyDescription,
  errorTitle = "Generation failed",
  errorDescription,
  headerAction,
  children,
}: ResultsPanelProps) {
  return (
    <Card>
      <CardHeader title={title} action={status === "content" ? headerAction : undefined} />
      {status === "loading" && (
        <CardBody>
          <div className="flex flex-col gap-3" role="status" aria-label="Generating">
            <Skeleton className="h-4 w-1/3" />
            <Skeleton className="h-20 w-full rounded-lg" />
            <Skeleton className="h-20 w-full rounded-lg" />
          </div>
        </CardBody>
      )}
      {status === "error" && (
        <CardBody>
          <EmptyState icon="⚠️" title={errorTitle} description={errorDescription} />
        </CardBody>
      )}
      {status === "empty" && (
        <CardBody>
          <EmptyState icon={emptyIcon} title={emptyTitle} description={emptyDescription} />
        </CardBody>
      )}
      {status === "content" && <CardBody noPadding>{children}</CardBody>}
    </Card>
  );
}
