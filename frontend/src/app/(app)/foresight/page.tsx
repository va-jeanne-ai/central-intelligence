"use client";

/**
 * Foresight — P1 statistics engine (real data).
 *
 * Every card pairs a recommendation with the evidence chain that produced
 * it, in three lenses: Hindsight (what the data shows) → Insight (why we
 * think it happens) → Foresight (what to do, with confidence). Numbers come
 * straight from GET /foresight/recommendations, which reads a table
 * computed nightly by a Celery task from pure SQL cohort counts — no ML, no
 * heuristics. A card only publishes (as a lift or a warning) when its
 * confidence interval clears the baseline; anything with overlapping
 * intervals renders collapsed as a gated ("held by the gate") example.
 *
 * See docs/superpowers/plans/2026-08-06-foresight-layer-prototype.md for
 * the full P1 architecture and the validation numbers this page's data is
 * checked against.
 */

import { useEffect, useState } from "react";
import { Header } from "@/components/layout/header";
import { Card, CardHeader, CardBody } from "@/components/ui/card";
import { KpiCard, KpiRow } from "@/components/ui/kpi-card";
import { Skeleton } from "@/components/ui/skeleton";
import { apiClient } from "@/lib/api-client";
import { useAuth } from "@/hooks/use-auth";
import Link from "next/link";

// ─── API response types (GET /foresight/recommendations) ───────────────────

type Status = "published_lift" | "published_warning" | "gated";
type Confidence = "High" | "Medium" | null;

interface ForesightCard {
  id: string;
  status: Status;
  confidence: Confidence;
  title: string;
  department: string;
  hindsight_headline: string;
  hindsight_detail: string;
  evidence_href: string;
  evidence_label: string;
  insight_text: string;
  action_text: string;
  lift_text: string;
  hold_reason: string | null;
  baseline_label: string;
  baseline_rate: number;
  baseline_low: number;
  baseline_high: number;
  variant_label: string;
  variant_rate: number;
  variant_low: number;
  variant_high: number;
  n_label: string;
  computed_at: string;
}

interface ForesightRecommendationsResponse {
  published: ForesightCard[];
  gated: ForesightCard[];
  computed_at: string | null;
}

// ─── Presentation helpers ────────────────────────────────────────────────────

const CONFIDENCE_STYLES: Record<string, string> = {
  High: "bg-green-50 text-green-700 ring-1 ring-inset ring-green-200",
  Medium: "bg-amber-50 text-amber-700 ring-1 ring-inset ring-amber-200",
};

const DEPT_STYLES: Record<string, string> = {
  sales: "bg-blue-50 text-blue-700",
  marketing: "bg-emerald-50 text-emerald-700",
};

function formatComputedAt(iso: string | null): string {
  if (!iso) return "not yet computed";
  try {
    return new Date(iso).toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

/** Confidence-interval bar: baseline vs variant rate, drawn on a shared
 * 0→(max high) scale so the separation (or overlap) of the intervals is the
 * visual message. */
function IntervalBar({
  label,
  rate,
  low,
  high,
  scaleMax,
  tone,
}: {
  label: string;
  rate: number;
  low: number;
  high: number;
  scaleMax: number;
  tone: "baseline" | "variant" | "warning";
}) {
  const pct = (v: number) => `${Math.min((v / scaleMax) * 100, 100)}%`;
  const intervalClass =
    tone === "warning"
      ? "bg-red-200"
      : tone === "variant"
        ? "bg-emerald-200"
        : "bg-gray-300";
  const pointClass =
    tone === "warning"
      ? "bg-red-600"
      : tone === "variant"
        ? "bg-emerald-600"
        : "bg-gray-500";
  return (
    <div className="flex items-center gap-2">
      <span className="w-28 flex-shrink-0 text-[10px] font-semibold uppercase tracking-wider text-gray-500 text-right">
        {label}
      </span>
      <div className="relative flex-1 h-4">
        <div className="absolute inset-y-1.5 left-0 right-0 rounded-full bg-gray-100" />
        <div
          className={`absolute inset-y-1.5 rounded-full ${intervalClass}`}
          style={{ left: pct(low), width: `calc(${pct(high)} - ${pct(low)})` }}
        />
        <div
          className={`absolute top-0 h-4 w-1 rounded-full ${pointClass}`}
          style={{ left: pct(rate) }}
        />
      </div>
      <span className="w-12 flex-shrink-0 text-xs font-bold tabular-nums text-gray-700 text-right">
        {rate.toFixed(1)}%
      </span>
    </div>
  );
}

function LensBlock({
  lens,
  accent,
  children,
}: {
  lens: string;
  accent: string;
  children: React.ReactNode;
}) {
  return (
    <div className={`rounded-lg border-l-2 ${accent} bg-gray-50/60 px-4 py-3`}>
      <p className="text-[10px] font-bold uppercase tracking-widest text-gray-400 mb-1.5">
        {lens}
      </p>
      {children}
    </div>
  );
}

function RecommendationCard({ card }: { card: ForesightCard }) {
  const isWarning = card.status === "published_warning";
  const scaleMax =
    Math.max(card.baseline_high, card.variant_high) * 1.15 || 1;

  return (
    <Card>
      <CardHeader
        title={card.title}
        action={
          <div className="flex items-center gap-2">
            <span
              className={`inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold capitalize ${DEPT_STYLES[card.department] ?? "bg-gray-100 text-gray-600"}`}
            >
              {card.department}
            </span>
            {isWarning && (
              <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold bg-red-50 text-red-700 ring-1 ring-inset ring-red-200">
                Warning
              </span>
            )}
            {card.confidence && (
              <span
                className={`inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold ${CONFIDENCE_STYLES[card.confidence]}`}
              >
                {card.confidence} confidence
              </span>
            )}
          </div>
        }
      />
      <CardBody>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
          <LensBlock
            lens="Hindsight — what the data shows"
            accent={isWarning ? "border-red-400" : "border-gray-400"}
          >
            <p className="text-sm font-semibold text-gray-800">
              {card.hindsight_headline}
            </p>
            <p className="text-xs text-gray-500 mt-1">{card.hindsight_detail}</p>
            <Link
              href={card.evidence_href}
              className="inline-block mt-2 text-xs font-medium text-blue-600 hover:text-blue-700 hover:underline"
            >
              {card.evidence_label} →
            </Link>
          </LensBlock>
          <LensBlock lens="Insight — why we think it happens" accent="border-blue-400">
            <p className="text-sm text-gray-700">{card.insight_text}</p>
          </LensBlock>
          <LensBlock
            lens="Foresight — what to do"
            accent={isWarning ? "border-red-400" : "border-amber-400"}
          >
            <p className="text-sm font-semibold text-gray-800">{card.action_text}</p>
            <p
              className={`text-xs font-medium mt-2 ${isWarning ? "text-red-700" : "text-emerald-700"}`}
            >
              {card.lift_text}
            </p>
          </LensBlock>
        </div>

        <div
          className={`mt-4 rounded-lg border px-4 py-3 ${isWarning ? "border-red-100" : "border-gray-100"}`}
        >
          <div className="flex items-center justify-between mb-2">
            <p className="text-[10px] font-bold uppercase tracking-widest text-gray-400">
              Rate comparison (95% CI)
            </p>
            <span className="text-[11px] font-medium text-gray-400">{card.n_label}</span>
          </div>
          <div className="space-y-1.5">
            <IntervalBar
              label={card.baseline_label}
              rate={card.baseline_rate}
              low={card.baseline_low}
              high={card.baseline_high}
              scaleMax={scaleMax}
              tone="baseline"
            />
            <IntervalBar
              label={card.variant_label}
              rate={card.variant_rate}
              low={card.variant_low}
              high={card.variant_high}
              scaleMax={scaleMax}
              tone={isWarning ? "warning" : "variant"}
            />
          </div>
        </div>
      </CardBody>
    </Card>
  );
}

/** Gated cards render collapsed — the mockup's "Held by the gate" treatment.
 * No confidence badge, no interval bars: the hold_reason IS the content. */
function GatedCard({ card }: { card: ForesightCard }) {
  return (
    <Card>
      <CardHeader
        title={card.title}
        action={
          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold bg-gray-100 text-gray-600 ring-1 ring-inset ring-gray-200">
            Held by the gate
          </span>
        }
      />
      <CardBody>
        <p className="text-sm text-gray-600">
          {card.hold_reason ?? card.insight_text}
        </p>
        <Link
          href={card.evidence_href}
          className="inline-block mt-2 text-xs font-medium text-blue-600 hover:text-blue-700 hover:underline"
        >
          {card.evidence_label} →
        </Link>
      </CardBody>
    </Card>
  );
}

// ─── Loading skeleton ────────────────────────────────────────────────────────

function ForesightPageSkeleton() {
  return (
    <main className="p-6 space-y-5 max-w-6xl">
      <Skeleton className="h-10 w-full rounded-xl" />
      <div>
        <Skeleton className="h-5 w-64" />
        <Skeleton className="h-4 w-96 mt-2" />
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {[1, 2, 3, 4].map((i) => (
          <Skeleton key={i} className="h-20 rounded-xl" />
        ))}
      </div>
      <div className="space-y-4">
        {[1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-48 rounded-xl" />
        ))}
      </div>
    </main>
  );
}

// ─── Page ────────────────────────────────────────────────────────────────────

export default function ForesightPage() {
  const { isLoading: authLoading } = useAuth();
  const [data, setData] = useState<ForesightRecommendationsResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [hasError, setHasError] = useState(false);

  useEffect(() => {
    if (authLoading) return;

    let cancelled = false;

    async function fetchData(): Promise<void> {
      setIsLoading(true);
      try {
        const result = await apiClient.get<ForesightRecommendationsResponse>(
          "/foresight/recommendations",
          { silent: true },
        );
        if (!cancelled) {
          setData(result);
          setHasError(false);
        }
      } catch {
        if (!cancelled) setHasError(true);
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    }

    void fetchData();
    return () => {
      cancelled = true;
    };
  }, [authLoading]);

  if (isLoading && !data) {
    return (
      <>
        <Header title="Foresight" />
        <ForesightPageSkeleton />
      </>
    );
  }

  const published = data?.published ?? [];
  const gated = data?.gated ?? [];

  return (
    <>
      <Header title="Foresight" />
      <main className="p-6 space-y-5 max-w-6xl">
        {/* Replaces the P0 amber PROTOTYPE banner — computed nightly, real data */}
        <div className="rounded-xl border border-gray-200 bg-gray-50 px-4 py-2.5">
          <p className="text-xs text-gray-500">
            Computed nightly from the synced mirrors · last refresh{" "}
            <span className="font-medium text-gray-700">
              {formatComputedAt(data?.computed_at ?? null)}
            </span>{" "}
            · every number is a reproducible SQL count
          </p>
        </div>

        {hasError && (
          <div className="rounded-xl border border-gray-200 bg-white px-4 py-3">
            <p className="text-sm text-gray-500">
              Couldn&apos;t load Foresight recommendations right now. Try refreshing.
            </p>
          </div>
        )}

        <div>
          <h1 className="text-lg font-bold text-gray-900">
            Recommendations with receipts
          </h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Every card shows its full evidence chain: what the data shows
            (hindsight), why we think it happens (insight), and what to do about
            it (foresight) — with the sample size and confidence stated, never
            hidden.
          </p>
        </div>

        <KpiRow>
          <KpiCard label="Published" value={String(published.length)} borderColor="#F59E0B" />
          <KpiCard
            label="Tracked"
            value="0"
            sub="outcome tracking — P2"
            borderColor="#10B981"
          />
          <KpiCard label="Held by the Gate" value={String(gated.length)} borderColor="#3B82F6" />
          <KpiCard
            label="Computed At"
            value={formatComputedAt(data?.computed_at ?? null)}
            sub="nightly, ~1h after WGR sync"
            borderColor="#F97316"
            className="text-lg"
          />
        </KpiRow>

        {published.length === 0 && gated.length === 0 && !hasError ? (
          <p className="text-sm text-gray-400 text-center py-12">
            No recommendations computed yet.
          </p>
        ) : (
          <div className="space-y-4">
            {published.map((card) => (
              <RecommendationCard key={card.id} card={card} />
            ))}
            {gated.map((card) => (
              <GatedCard key={card.id} card={card} />
            ))}
          </div>
        )}

        <p className="text-xs text-gray-400 pb-6">
          Production rules: recommendations are pure counting over the mirrors
          with Wilson score intervals (and a mean-of-campaigns interval for
          the email candidate) — no ML, no heuristics. A card only publishes
          when its interval clears the baseline; overlapping intervals render
          collapsed as &ldquo;held by the gate&rdquo;. Full plan:
          docs/superpowers/plans/2026-08-06-foresight-layer-prototype.md
        </p>
      </main>
    </>
  );
}
