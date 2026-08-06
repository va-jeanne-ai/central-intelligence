"use client";

/**
 * Foresight — STATIC PROTOTYPE (P0 of docs/superpowers/plans/
 * 2026-08-06-foresight-layer-prototype.md).
 *
 * Every card pairs a recommendation with the evidence chain that produced it,
 * in three lenses: Hindsight (what the data shows) → Insight (why we think it
 * happens) → Foresight (what to do, with confidence).
 *
 * ⚠️ ALL DATA BELOW IS HARDCODED SAMPLE DATA so the client can feel the format
 * before we build the statistics engine. Headline counts are directionally
 * real (funnel/channel/email figures from the live mirrors as of 2026-08-06);
 * the rates, intervals, and impact estimates are ILLUSTRATIVE. The amber
 * banner must stay until P1 replaces this with GET /foresight/recommendations.
 */

import { Header } from "@/components/layout/header";
import { Card, CardHeader, CardBody } from "@/components/ui/card";
import { KpiCard, KpiRow } from "@/components/ui/kpi-card";
import Link from "next/link";

// ─── Sample data (static — see file banner) ─────────────────────────────────

type Confidence = "High" | "Medium" | "Low";

interface SampleRecommendation {
  id: string;
  title: string;
  department: "sales" | "marketing";
  hindsight: {
    headline: string;
    detail: string;
    evidenceHref: string;
    evidenceLabel: string;
  };
  insight: string;
  foresight: {
    action: string;
    impact: string;
  };
  confidence: Confidence;
  n: string;
  // Illustrative rate comparison for the interval visual (percent points).
  baseline: { label: string; rate: number; low: number; high: number };
  variant: { label: string; rate: number; low: number; high: number };
}

const SAMPLE_RECOMMENDATIONS: SampleRecommendation[] = [
  {
    id: "live-watch-followup",
    title: "Follow up with live webinar watchers within 24 hours",
    department: "sales",
    hindsight: {
      headline: "Live watchers book appointments at ~3.4× the replay rate",
      detail:
        "Of 6,879 webinar watchers, leads who attended live booked at 8.1% vs 2.4% for replay-only watchers (sample rates — illustrative).",
      evidenceHref: "/marketing/funnels",
      evidenceLabel: "Funnel: 11,573 registered → 6,879 watched → 1,290 booked",
    },
    insight:
      "Intent peaks in the hours after live attendance — live watchers chose to show up at a fixed time, and the Q&A creates a personal hook a replay can't.",
    foresight: {
      action:
        "Create a same-day follow-up queue: every live watcher gets a call or DM within 24h of the webinar, before replay-watcher outreach.",
      impact: "Illustrative: ≈ +18 bookings/month at current attendance volume",
    },
    confidence: "High",
    n: "n = 6,879 watchers",
    baseline: { label: "Replay-only", rate: 2.4, low: 1.9, high: 3.0 },
    variant: { label: "Watched live", rate: 8.1, low: 7.2, high: 9.1 },
  },
  {
    id: "meta-paid-scaling",
    title: "Shift Meta budget toward the two proven campaigns",
    department: "marketing",
    hindsight: {
      headline: "meta_paid leads close at ~2.1× the all-channel baseline",
      detail:
        "714 meta_paid leads closed at 1.3% vs the 0.6% all-lead baseline; 83 total sales keep this interval wide (sample rates — illustrative).",
      evidenceHref: "/leads",
      evidenceLabel: "Leads: channel filter → meta_paid (714)",
    },
    insight:
      "Paid traffic arrives pre-qualified by the ad hook — the two top campaigns filter for exactly the ICP the webinar converts.",
    foresight: {
      action:
        "Concentrate spend on the top two campaigns by cost-per-closed-lead (not CPL) and pause the tail — revisit monthly as sales n grows.",
      impact: "Illustrative: same spend, ≈ +2–3 closes/quarter",
    },
    confidence: "Medium",
    n: "n = 714 leads · 83 total sales (wide interval)",
    baseline: { label: "All channels", rate: 0.6, low: 0.5, high: 0.8 },
    variant: { label: "meta_paid", rate: 1.3, low: 0.7, high: 2.4 },
  },
  {
    id: "email-value-prior",
    title: "Send two value emails before every promo push",
    department: "marketing",
    hindsight: {
      headline: "Value/Education campaigns open at 29.4% vs 22.1% for the rest",
      detail:
        "Across 2,426 sent campaigns, the Value/Education type consistently out-opens promotional types (sample rates — illustrative).",
      evidenceHref: "/marketing/email",
      evidenceLabel: "Email: 2,426 campaigns · 12 types",
    },
    insight:
      "Story-led subjects earn the open; promo-led subjects spend the goodwill those opens build. Sequencing value → promo preserves list health.",
    foresight: {
      action:
        "Adopt a 2:1 cadence rule — schedule two Value/Education sends ahead of each promotional campaign, and watch unsubscribes as the guardrail.",
      impact: "Illustrative: ≈ +5–7% opens on the promo that follows",
    },
    confidence: "High",
    n: "n = 2,426 campaigns",
    baseline: { label: "Other types", rate: 22.1, low: 21.4, high: 22.8 },
    variant: { label: "Value/Education", rate: 29.4, low: 28.1, high: 30.7 },
  },
  {
    id: "pain-signal-routing",
    title: "Route time-freedom pain leads to the senior closer",
    department: "sales",
    hindsight: {
      headline: "Discovery calls surfacing time-freedom pain close at ~2.1×",
      detail:
        "Of 184 discovery-held leads, those whose call insights carry the time-freedom signal family close markedly more often (sample rates — illustrative; smallest sample on this page).",
      evidenceHref: "/ci-insights",
      evidenceLabel: "CI Insights: 1,932 insights · source filter → Call · Discovery",
    },
    insight:
      "Time-freedom pain is motivation-qualified — the lead has already articulated the cost of inaction in their own words on the call.",
    foresight: {
      action:
        "Flag these leads at discovery-call analysis time and route them to the senior rep with the matching objection-handling script.",
      impact: "Illustrative: ≈ +1–2 closes/quarter — verify before acting",
    },
    confidence: "Low",
    n: "n = 184 discovery calls (treat as a hypothesis)",
    baseline: { label: "Other discovery", rate: 38.0, low: 30.1, high: 46.4 },
    variant: { label: "Time-freedom pain", rate: 79.0, low: 57.8, high: 91.4 },
  },
];

// ─── Presentation helpers ────────────────────────────────────────────────────

const CONFIDENCE_STYLES: Record<Confidence, string> = {
  High: "bg-green-50 text-green-700 ring-1 ring-inset ring-green-200",
  Medium: "bg-amber-50 text-amber-700 ring-1 ring-inset ring-amber-200",
  Low: "bg-gray-100 text-gray-600 ring-1 ring-inset ring-gray-200",
};

const DEPT_STYLES: Record<SampleRecommendation["department"], string> = {
  sales: "bg-blue-50 text-blue-700",
  marketing: "bg-emerald-50 text-emerald-700",
};

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
  tone: "baseline" | "variant";
}) {
  const pct = (v: number) => `${Math.min((v / scaleMax) * 100, 100)}%`;
  return (
    <div className="flex items-center gap-2">
      <span className="w-28 flex-shrink-0 text-[10px] font-semibold uppercase tracking-wider text-gray-500 text-right">
        {label}
      </span>
      <div className="relative flex-1 h-4">
        <div className="absolute inset-y-1.5 left-0 right-0 rounded-full bg-gray-100" />
        {/* interval */}
        <div
          className={`absolute inset-y-1.5 rounded-full ${
            tone === "variant" ? "bg-emerald-200" : "bg-gray-300"
          }`}
          style={{ left: pct(low), width: `calc(${pct(high)} - ${pct(low)})` }}
        />
        {/* point estimate */}
        <div
          className={`absolute top-0 h-4 w-1 rounded-full ${
            tone === "variant" ? "bg-emerald-600" : "bg-gray-500"
          }`}
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

// ─── Page ────────────────────────────────────────────────────────────────────

export default function ForesightPage() {
  return (
    <>
      <Header title="Foresight" />
      <main className="p-6 space-y-5 max-w-6xl">
        {/* Prototype banner — stays until P1 replaces the static data */}
        <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3">
          <p className="text-sm font-semibold text-amber-800">
            Prototype — static sample data
          </p>
          <p className="text-xs text-amber-700 mt-0.5">
            The format is real; the statistics are illustrative. Headline counts
            match the live mirrors, but rates, intervals, and impact estimates
            are hardcoded samples. The production version computes these nightly
            from lead_journey, closed_sales, email_campaigns, and call insights
            — and only publishes a recommendation when its confidence interval
            clears the baseline.
          </p>
        </div>

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
          <KpiCard label="Active Recommendations" value="4" borderColor="#F59E0B" />
          <KpiCard label="High Confidence" value="2" sub="interval clear of baseline" borderColor="#10B981" />
          <KpiCard label="Evidence Rows Analyzed" value="35,714" sub="journey · sales · email · insights" borderColor="#3B82F6" />
          <KpiCard label="Refresh Cadence" value="Nightly" sub="with the WGR sync" borderColor="#F97316" />
        </KpiRow>

        <div className="space-y-4">
          {SAMPLE_RECOMMENDATIONS.map((rec) => {
            const scaleMax =
              Math.max(rec.baseline.high, rec.variant.high) * 1.15;
            return (
              <Card key={rec.id}>
                <CardHeader
                  title={rec.title}
                  action={
                    <div className="flex items-center gap-2">
                      <span
                        className={`inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold capitalize ${DEPT_STYLES[rec.department]}`}
                      >
                        {rec.department}
                      </span>
                      <span
                        className={`inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold ${CONFIDENCE_STYLES[rec.confidence]}`}
                      >
                        {rec.confidence} confidence
                      </span>
                    </div>
                  }
                />
                <CardBody>
                  <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
                    <LensBlock lens="Hindsight — what the data shows" accent="border-gray-400">
                      <p className="text-sm font-semibold text-gray-800">
                        {rec.hindsight.headline}
                      </p>
                      <p className="text-xs text-gray-500 mt-1">{rec.hindsight.detail}</p>
                      <Link
                        href={rec.hindsight.evidenceHref}
                        className="inline-block mt-2 text-xs font-medium text-blue-600 hover:text-blue-700 hover:underline"
                      >
                        {rec.hindsight.evidenceLabel} →
                      </Link>
                    </LensBlock>
                    <LensBlock lens="Insight — why we think it happens" accent="border-blue-400">
                      <p className="text-sm text-gray-700">{rec.insight}</p>
                      <p className="text-[11px] text-gray-400 mt-2 italic">
                        Hypothesis — stated, not proven. The numbers live in the
                        hindsight column.
                      </p>
                    </LensBlock>
                    <LensBlock lens="Foresight — what to do" accent="border-amber-400">
                      <p className="text-sm font-semibold text-gray-800">
                        {rec.foresight.action}
                      </p>
                      <p className="text-xs text-emerald-700 font-medium mt-2">
                        {rec.foresight.impact}
                      </p>
                    </LensBlock>
                  </div>

                  <div className="mt-4 rounded-lg border border-gray-100 px-4 py-3">
                    <div className="flex items-center justify-between mb-2">
                      <p className="text-[10px] font-bold uppercase tracking-widest text-gray-400">
                        Rate comparison (illustrative interval)
                      </p>
                      <span className="text-[11px] font-medium text-gray-400">{rec.n}</span>
                    </div>
                    <div className="space-y-1.5">
                      <IntervalBar {...rec.baseline} scaleMax={scaleMax} tone="baseline" />
                      <IntervalBar {...rec.variant} scaleMax={scaleMax} tone="variant" />
                    </div>
                  </div>
                </CardBody>
              </Card>
            );
          })}
        </div>

        <p className="text-xs text-gray-400 pb-6">
          Production rules (P1): recommendations are pure counting over the
          mirrors with Wilson score intervals — no ML, no heuristics. A card
          only publishes when its interval clears the baseline; anything at
          &ldquo;Low&rdquo; renders as a hypothesis to verify, never an
          instruction. Full plan: docs/superpowers/plans/2026-08-06-foresight-layer-prototype.md
        </p>
      </main>
    </>
  );
}
