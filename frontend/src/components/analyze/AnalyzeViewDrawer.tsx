"use client";

/**
 * AnalyzeViewDrawer — right-side drawer showing a grounded LLM analysis of the
 * current filtered list view. Ephemeral: fetches on open, discards on close.
 * Every number in the narrative is verifiable against the "Data this is based
 * on" section (the raw aggregates the backend computed and prompted with).
 */

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { analyzeView, type AnalyzeViewResponse } from "@/lib/analyze-client";
import { SparkleIcon } from "@/components/analyze/AnalyzeViewButton";

interface AnalyzeViewDrawerProps {
  surface: string;
  /** Snapshot of the page's current filter params; null = drawer closed. */
  params: URLSearchParams | null;
  open: boolean;
  onClose: () => void;
}

export function AnalyzeViewDrawer({ surface, params, open, onClose }: AnalyzeViewDrawerProps) {
  const [result, setResult] = useState<AnalyzeViewResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showData, setShowData] = useState(false);
  const [runKey, setRunKey] = useState(0);

  useEffect(() => {
    if (!open || !params) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    setResult(null);
    analyzeView(surface, params)
      .then((r) => { if (!cancelled) setResult(r); })
      .catch((e: unknown) => {
        if (!cancelled) setError(e instanceof Error ? e.message : "Analysis failed.");
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [open, params, surface, runKey]);

  useEffect(() => {
    if (!open) { setResult(null); setError(null); setShowData(false); }
  }, [open]);

  if (!open) return null;

  return (
    <>
      <div className="fixed inset-0 bg-black/30 z-40" onClick={onClose} aria-hidden />
      <aside
        className="fixed inset-y-0 right-0 w-full max-w-[460px] bg-white shadow-xl z-50 flex flex-col"
        role="dialog"
        aria-label="View analysis"
      >
        <div className="flex items-center justify-between border-b border-gray-200 px-5 py-4">
          <h2 className="flex items-center gap-1.5 text-sm font-semibold text-gray-900">
            <SparkleIcon className="h-3.5 w-3.5 text-accent-500" />
            AI analysis
          </h2>
          <div className="flex gap-2">
            <Button variant="ghost" size="sm" onClick={() => setRunKey((k) => k + 1)} disabled={loading}>
              Re-run
            </Button>
            <Button variant="ghost" size="sm" onClick={onClose}>Close</Button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-5">
          {result && (
            <p className="text-xs text-gray-500">
              Analyzing {result.row_count.toLocaleString()} {result.label} · {result.filters_echo}
            </p>
          )}

          {loading && (
            <div className="space-y-3">
              <Skeleton className="h-4 w-3/4" />
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-5/6" />
              <p className="text-xs text-gray-400">Computing aggregates and writing the analysis…</p>
            </div>
          )}

          {error && (
            <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {error}
              <div className="mt-2">
                <Button variant="ghost" size="sm" onClick={() => setRunKey((k) => k + 1)}>Retry</Button>
              </div>
            </div>
          )}

          {result?.empty && (
            <p className="text-sm text-gray-500">
              No data in this view — adjust the filters and try again. (No analysis was run.)
            </p>
          )}

          {result && !result.empty && (
            <>
              <section className="space-y-3">
                {result.narrative.split("\n\n").map((para, i) => (
                  <p key={i} className="text-sm leading-6 text-gray-800">{para}</p>
                ))}
              </section>

              {result.highlights.length > 0 && (
                <section>
                  <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">
                    Highlights
                  </h3>
                  <ul className="list-disc space-y-1 pl-5 text-sm text-gray-800">
                    {result.highlights.map((h, i) => <li key={i}>{h}</li>)}
                  </ul>
                </section>
              )}

              {result.hypotheses.length > 0 && (
                <section className="rounded-md border border-amber-200 bg-amber-50 px-4 py-3">
                  <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-amber-700">
                    Hypotheses — speculative, verify before acting
                  </h3>
                  <ul className="list-disc space-y-1 pl-5 text-sm text-amber-900">
                    {result.hypotheses.map((h, i) => <li key={i}>{h}</li>)}
                  </ul>
                </section>
              )}

              <section>
                <button
                  type="button"
                  className="text-xs font-medium text-gray-600 underline"
                  onClick={() => setShowData((s) => !s)}
                >
                  {showData ? "Hide" : "Show"} the data this is based on
                </button>
                {showData && (
                  <div className="mt-3 space-y-4">
                    {Object.entries(result.stats.breakdowns).map(([name, items]) => (
                      <div key={name}>
                        <h4 className="mb-1 text-xs font-semibold capitalize text-gray-600">
                          By {name.replace(/_/g, " ")}
                        </h4>
                        <table className="w-full text-xs text-gray-700">
                          <tbody>
                            {items.map((it) => (
                              <tr key={it.label} className="border-b border-gray-100">
                                <td className="py-1 pr-2">{it.label}</td>
                                <td className="py-1 pr-2 text-right tabular-nums">{it.count}</td>
                                <td className="py-1 text-right tabular-nums text-gray-400">{it.pct}%</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    ))}
                    {result.stats.series && result.stats.series.points.length > 0 && (
                      <div>
                        <h4 className="mb-1 text-xs font-semibold text-gray-600">By week</h4>
                        <table className="w-full text-xs text-gray-700">
                          <tbody>
                            {result.stats.series.points.map((p) => (
                              <tr key={p.week_start} className="border-b border-gray-100">
                                <td className="py-1 pr-2">{p.week_start}</td>
                                <td className="py-1 text-right tabular-nums">{p.count}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                    {Object.keys(result.stats.extras).length > 0 && (
                      <div>
                        <h4 className="mb-1 text-xs font-semibold text-gray-600">Extras</h4>
                        <pre className="overflow-x-auto rounded bg-gray-50 p-2 text-[11px] text-gray-600">
                          {JSON.stringify(result.stats.extras, null, 2)}
                        </pre>
                      </div>
                    )}
                  </div>
                )}
              </section>

              <p className="text-[11px] text-gray-400">
                Generated {result.generated_at}{result.model ? ` · ${result.model}` : ""} · not saved
              </p>
            </>
          )}
        </div>
      </aside>
    </>
  );
}
