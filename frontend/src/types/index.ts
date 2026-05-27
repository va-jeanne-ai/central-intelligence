// ─── Chat ──────────────────────────────────────────────────────────────────────

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
  isStreaming?: boolean;
}

export interface ChatChunk {
  chunk?: string;
  done?: boolean;
  session_id: string;
  full_response?: string;
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
  signal_strength: "Strong" | "Moderate" | "Weak";
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
