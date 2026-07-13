"use client";

import { Card, CardHeader, CardBody } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { SparkleIcon } from "@/components/ui/sparkle-icon";
import type { OverallInsight } from "@/types";

// ─── Verdict styling ──────────────────────────────────────────────────────────

const VERDICT_STYLE: Record<
  OverallInsight["health_verdict"],
  { pill: string; dot: string; label: string }
> = {
  healthy: { pill: "bg-emerald-50 text-emerald-700", dot: "bg-emerald-500", label: "Healthy" },
  watch: { pill: "bg-amber-50 text-amber-700", dot: "bg-amber-500", label: "Watch" },
  at_risk: { pill: "bg-red-50 text-red-700", dot: "bg-red-500", label: "At risk" },
};

function VerdictPill({ verdict }: { verdict: OverallInsight["health_verdict"] }) {
  const v = VERDICT_STYLE[verdict] ?? VERDICT_STYLE.watch;
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold ${v.pill}`}
    >
      <span className={`inline-block h-2 w-2 rounded-full ${v.dot}`} aria-hidden="true" />
      {v.label}
    </span>
  );
}

// ─── Card ─────────────────────────────────────────────────────────────────────

/** Hero card atop /insights: the company-level health assessment. Renders the
 * verdict pill, narrative paragraphs, and key-shift bullets — or an empty state
 * prompting generation when none exists yet. */
export function OverallInsightCard({
  insight,
  loading,
  generating,
  onGenerate,
}: {
  insight: OverallInsight | null;
  loading: boolean;
  generating: boolean;
  onGenerate: () => void;
}) {
  const paragraphs = (insight?.narrative ?? "")
    .split(/\n\n+/)
    .map((p) => p.trim())
    .filter(Boolean);

  return (
    <Card>
      <CardHeader
        title="Overall health"
        action={
          <div className="flex items-center gap-3">
            {insight && <VerdictPill verdict={insight.health_verdict} />}
            <Button variant="ai" onClick={onGenerate} disabled={generating || loading}>
              {generating ? (
                "Generating…"
              ) : (
                <>
                  <SparkleIcon />
                  {insight ? "Regenerate" : "Generate"}
                </>
              )}
            </Button>
          </div>
        }
      />
      <CardBody>
        {loading ? (
          <div className="space-y-2">
            <div className="h-4 w-3/4 animate-pulse rounded bg-gray-100" />
            <div className="h-4 w-full animate-pulse rounded bg-gray-100" />
            <div className="h-4 w-5/6 animate-pulse rounded bg-gray-100" />
          </div>
        ) : !insight ? (
          <div className="py-4">
            <p className="text-[13px] text-gray-500">
              No overall assessment yet. Generate one to get a company-level read of the
              business — synthesized from your metric trends and active recommendations.
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            <div className="space-y-3">
              {paragraphs.map((p, i) => (
                <p key={i} className="text-sm leading-relaxed text-gray-700">
                  {p}
                </p>
              ))}
            </div>

            {insight.key_shifts.length > 0 && (
              <div>
                <p className="mb-1.5 text-[10px] font-bold uppercase tracking-wider text-gray-500">
                  Key shifts
                </p>
                <ul className="space-y-1">
                  {insight.key_shifts.map((s, i) => (
                    <li key={i} className="flex gap-2 text-[13px] text-gray-600">
                      <span className="text-accent-500" aria-hidden="true">
                        →
                      </span>
                      <span>{s}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <p className="text-[11px] text-gray-400">
              Assessment for {insight.insight_date}
              {insight.previous_date ? ` · builds on ${insight.previous_date}` : " · genesis"}
              {insight.model !== "mock" ? "" : " · mock"}
            </p>
          </div>
        )}
      </CardBody>
    </Card>
  );
}
