// ─── Chat ──────────────────────────────────────────────────────────────────────

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
  isStreaming?: boolean;
  // Set when the model stopped before finishing (e.g. ran out of tokens). The
  // content is partial and must be shown as incomplete with a reload prompt.
  incomplete?: boolean;
  finishReason?: string;
  notice?: string;
}

export interface ChatChunk {
  chunk?: string;
  done?: boolean;
  session_id: string;
  full_response?: string;
  // Final-frame only. "complete" = finished; "incomplete" = stopped early.
  status?: "complete" | "incomplete";
  finish_reason?: string;
  notice?: string;
}

// ─── WebSocket ─────────────────────────────────────────────────────────────────

export interface WebSocketMessage {
  channel: string;
  data: {
    sessionId: string;
    chunk: string;
    tokenIndex: number;
    isComplete: boolean;
    fullResponse?: string;
    // Final-frame only. "incomplete" means the streamed text was cut off.
    status?: "complete" | "incomplete";
    finishReason?: string;
    notice?: string;
  };
}

// ─── API Responses ─────────────────────────────────────────────────────────────

export interface HealthResponse {
  status: string;
  database: string;
  version: string;
  timestamp: string;
}

// ─── Leads ──────────────────────────────────────────────────────────────────

export type LeadStatus =
  | "new"
  | "contacted"
  | "qualified"
  | "appointment_set"
  | "closed_won"
  | "closed_lost"
  | "stale";

export type LeadSource =
  | "webinar"
  | "vsl"
  | "opt-in"
  | "ads"
  | "referral"
  | "other";

export interface Lead {
  id: string;
  name: string;
  email: string;
  phone: string;
  status: LeadStatus;
  source: LeadSource;
  notes: string;
  createdAt: string;
  /** Lead quality score 0–100 */
  score?: number;
}

// ─── API Error ──────────────────────────────────────────────────────────────

export interface ApiErrorResponse {
  error: {
    code: string;
    message: string;
    field?: string;
    timestamp?: string;
    requestId?: string;
  };
}

export interface RequestOptions {
  timeout?: number;
  retries?: number;
  silent?: boolean;
}

// ─── Dashboard ─────────────────────────────────────────────────────────────────

export interface DepartmentStats {
  name: string;
  icon: string;
  color: "marketing" | "sales" | "fulfillment";
  stats: { label: string; value: string; sub?: string }[];
}

export interface DepartmentStat {
  label: string;
  value: string;
  sub?: string;
}

export interface DashboardStats {
  departments: {
    sales: { stats: DepartmentStat[] };
    fulfillment: { stats: DepartmentStat[] };
    marketing: { stats: DepartmentStat[] };
  };
  kpis: {
    total_leads: number;
    leads_this_week: number;
    calls_this_week: number;
    active_members: number;
  };
  lead_volume: { label: string; value: number }[];
}

// ─── Transcripts ───────────────────────────────────────────────────────────────

export type TranscriptCallType = "Sales" | "Discovery" | "Coaching" | "Accountability" | "Support";

export type TranscriptFileType = "txt" | "pdf" | "docx";

export interface TranscriptUploadRequest {
  file_content: string; // base64
  file_name: string;
  file_type: TranscriptFileType;
  call_owner?: string;
  call_type?: TranscriptCallType;
  lead_id?: string;
  member_id?: string;
}

export interface TranscriptUploadResponse {
  call_id: string;
  status: string;
  message: string;
}

export interface TranscribeJobResponse {
  jobId: string;
  status: string;
  queuePosition?: number;
  estimatedWaitMinutes?: number;
}

// Response shape returned by POST /api/v1/transcribe/upload (multipart audio
// uploads). The backend returns snake_case: see TranscribeResponse in
// backend/app/schemas/transcribe.py and the /transcribe/upload route's return.
export interface TranscribeUploadResponse {
  call_id: string;
  job_id: string;
  status: string; // "completed" | "duplicate"
  transcript?: string;
  message?: string;
}

// ─── CI Insights ────────────────────────────────────────────────────────────

export interface CIInsight {
  insight_id: string;
  call_id: string;
  speaker_name: string;
  insight_type: string;
  signal_family: string;
  signal: string;
  signal_strength: string;
  raw_quote: string;
  marketing_translation: string;
  hook_angle_example: string;
  best_use_case: string;
  quote_confidence: string;
  frequency_score: number;
}

export interface CIInsightsResponse {
  data: CIInsight[];
  pagination: {
    page: number;
    limit: number;
    total: number;
    totalPages: number;
    hasNextPage: boolean;
    hasPreviousPage: boolean;
  };
}

/** Distinct filterable values present in the insights table — drives the
 * insights-page filter dropdowns so options can't drift from the data. */
export interface CIInsightFacets {
  insight_type: string[];
  signal_family: string[];
  signal_strength: string[];
}

/** The company-level health assessment shown atop /insights. Synthesized daily by
 * the analytics engine (GET /analytics/overall-insight). */
export interface OverallInsight {
  insight_date: string;
  health_verdict: "healthy" | "watch" | "at_risk";
  narrative: string;
  key_shifts: string[];
  previous_date: string | null;
  model: string;
  generated_at: string;
}

/** One (label, count) bucket in a distribution chart. `mentions` sums
 * frequency_score across the bucket; `count` is the raw row count. */
export interface CIInsightCount {
  label: string;
  count: number;
  mentions: number;
}

/** A high-frequency signal for the "top signals" chart. */
export interface CIInsightTopSignal {
  signal: string;
  signal_family: string | null;
  insight_type: string | null;
  mentions: number;
}

/** Pre-aggregated distributions powering the CI Insights charts. Computed
 * server-side over the full (filtered) dataset — see GET /ci/insights/summary. */
export interface CIInsightDistribution {
  total: number;
  by_insight_type: CIInsightCount[];
  by_signal_family: CIInsightCount[];
  by_signal_strength: CIInsightCount[];
  top_signals: CIInsightTopSignal[];
}

// ─── CI Market Signals ───────────────────────────────────────────────────────

export interface CIMarketSignal {
  signal_family: string;
  signal: string;
  insight_type: string;
  total_mentions: number;
  last_30_days: number;
  last_7_days: number;
  example_quote: string;
  best_marketing_angle: string;
}

export interface CIMarketSignalsResponse {
  data: CIMarketSignal[];
}

/** Distinct filterable values present in the market_signals table — drives
 * the market-signals page filter dropdowns so options can't drift. */
export interface CIMarketSignalFacets {
  insight_type: string[];
  signal_family: string[];
}

/** Distinct filterable values present in the calls table — drives the
 * calls-table filter dropdowns so options can't drift. `source` is a fixed
 * provenance set and is not derived. */
export interface CICallFacets {
  call_type: string[];
  call_result: string[];
}

// ─── Ads ─────────────────────────────────────────────────────────────────────

export interface AdsData {
  campaigns: number;
  avg_roas: number;
  total_spend: number;
  top_ads: { campaign_name: string; platform: string; roas: number; spend: number }[];
  generated_at: string;
}

export interface AdsAnalyzeResponse {
  analysis: string;
  ad_copy: string;
  recommendations: string[];
  data_used: Record<string, unknown>;
}

// ─── DM ──────────────────────────────────────────────────────────────────────

export interface DmData {
  outreach_sent: number;
  response_rate: number;
  meetings_booked: number;
  top_sequences: { name: string; response_rate: number; meetings: number }[];
  generated_at: string;
}

export interface DmAnalyzeResponse {
  analysis: string;
  sequence: { step: number; message: string; delay_hours: number }[];
  recommendations: string[];
  data_used: Record<string, unknown>;
}

// ─── Offers ──────────────────────────────────────────────────────────────────

export interface OfferItem {
  id: string;
  name: string;
  offer_type: string;
  description: string | null;
  price: number;
  status: string;
  url: string | null;
  notes: string | null;
}

export interface OfferListResponse {
  offers: OfferItem[];
  total: number;
}

export interface OfferGenerateResponse {
  task_id: string;
  status: string;
  message: string;
}

// ─── Promo Calendar ──────────────────────────────────────────────────────────

export interface Promotion {
  id: string;
  name: string;
  description: string | null;
  promo_type: string;
  start_date: string;
  end_date: string;
  status: string;
  department: string | null;
  color: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

// ─── Integrations ────────────────────────────────────────────────────────────

export interface ProviderFieldSchema {
  key: string;
  label: string;
  type: string; // "text" | "password" | "select"
  secret: boolean;
  required: boolean;
  placeholder: string;
  help: string;
}

export interface IntegrationSummary {
  slug: string;
  name: string;
  icon: string;
  category: string;
  status: "available" | "coming_soon";
  description: string;
  connected: boolean;
  last_synced_at: string | null;
  last_sync_status: string | null;
  oauth_pending: boolean;
  // True for providers like GHL where there's no credentials form —
  // the integration row holds a server-generated webhook token and the
  // detail page renders a Copy-URL + Rotate Secret UI instead.
  webhook_only: boolean;
  // True for providers that use per-user OAuth (Google Workspace today).
  // The detail page renders a "Connect Gmail" button instead of the
  // credentials form.
  oauth_per_user: boolean;
}

export interface IntegrationDetail extends IntegrationSummary {
  fields: ProviderFieldSchema[];
  values: Record<string, string>;
  last_sync_error: string | null;
}

export interface TestIntegrationResponse {
  ok: boolean;
  message: string;
  details?: Record<string, unknown> | null;
}

// ─── Data freshness ───────────────────────────────────────────────────────

export type FreshnessVerdict = "fresh" | "stale" | "unknown";

export interface FreshnessSourceResult {
  key: string;
  label: string;
  description: string;
  interval_minutes: number;
  last_run_at: string | null;
  last_status: string | null;
  age_minutes: number | null;
  verdict: FreshnessVerdict;
  detail: string;
}

export interface FreshnessResponse {
  overall: FreshnessVerdict;
  checked_at: string;
  sources: FreshnessSourceResult[];
}

export interface SyncTriggerResponse {
  queued: boolean;
  task_id: string | null;
  message: string;
}

export interface SyncStatusResponse {
  task_id: string;
  state: string; // PENDING | STARTED | SUCCESS | FAILURE | RETRY
  running: boolean;
  detail: string | null;
}

// ─── Calendar ─────────────────────────────────────────────────────────────

export interface CalendarAttendee {
  email: string;
  displayName?: string | null;
  responseStatus?: string | null;
}

export interface CalendarEventRow {
  id: string;
  title: string | null;
  description: string | null;
  calendar_name: string | null;
  start_time: string | null;
  end_time: string | null;
  is_all_day: boolean;
  organizer_email: string | null;
  attendees: CalendarAttendee[];
  event_link: string | null;
  location: string | null;
  status: string | null;
}

export interface CalendarEventsResponse {
  events: CalendarEventRow[];
  total: number;
}

export interface CalendarSummary {
  calendar_id: string;
  calendar_name: string | null;
}

export interface CalendarListResponse {
  calendars: CalendarSummary[];
}

// ─── Chat history (persisted) ─────────────────────────────────────────────

export interface ChatSessionRow {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  last_message_at: string | null;
  message_count: number;
}

export interface ChatSessionListResponse {
  sessions: ChatSessionRow[];
}

export interface ChatMessageRow {
  id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
}

export interface ChatSessionDetailResponse {
  session: ChatSessionRow;
  messages: ChatMessageRow[];
}

// ─── Lead Documents (Google Drive) ────────────────────────────────────────

export interface DocumentRow {
  id: string;
  name: string | null;
  mime_type: string | null;
  owner_email: string | null;
  modified_time: string | null;
  web_view_link: string | null;
  parent_folder_name: string | null;
  size_bytes: number | null;
}

export interface DocumentsResponse {
  files: DocumentRow[];
}
