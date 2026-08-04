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

// ─── Follow-up chat (deliverable 8) ─────────────────────────────────────────

export interface AnalyzeChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface AnalyzeChatResponse {
  reply: string;
  model: string | null;
  generated_at: string;
}

/**
 * Ask a follow-up question about the same filtered view the drawer already
 * analyzed. `params` must be the SAME filter params passed to `analyzeView`
 * so the backend recomputes aggregates from identical filters. `messages` is
 * the full local running history (including the new user turn) — the
 * backend has no server-side session for this, ephemeral by design.
 */
export function analyzeViewChat(
  surface: string,
  params: URLSearchParams,
  messages: AnalyzeChatMessage[],
): Promise<AnalyzeChatResponse> {
  const qs = params.toString();
  return apiClient.post<AnalyzeChatResponse>(
    `/analyze/${surface}/chat${qs ? `?${qs}` : ""}`,
    { messages },
    { silent: true, timeout: 60_000 },
  );
}
