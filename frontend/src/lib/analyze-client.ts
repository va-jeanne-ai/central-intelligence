import { apiClient } from "@/lib/api-client";

export interface BreakdownItem {
  label: string;
  count: number;
  pct: number;
}

export interface AnalyzeStats {
  row_count: number;
  breakdowns: Record<string, BreakdownItem[]>;
  series: { bucket: string; points: { week_start: string; count: number }[] } | null;
  extras: Record<string, unknown>;
}

export interface AnalyzeViewResponse {
  surface: string;
  label: string;
  filters_echo: string;
  row_count: number;
  empty: boolean;
  stats: AnalyzeStats;
  narrative: string;
  highlights: string[];
  hypotheses: string[];
  generated_at: string;
  model: string | null;
}

/**
 * Run a grounded analysis of the current filtered view. `params` must be the
 * same filter params the page's list fetch uses (minus pagination/sort).
 * One real LLM call per invocation — only call on explicit user action.
 */
export function analyzeView(
  surface: string,
  params: URLSearchParams,
): Promise<AnalyzeViewResponse> {
  const qs = params.toString();
  return apiClient.post<AnalyzeViewResponse>(
    `/analyze/${surface}${qs ? `?${qs}` : ""}`,
    {},
    { silent: true, timeout: 90_000 },
  );
}
