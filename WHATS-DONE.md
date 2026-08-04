# Central Intelligence — What's Been Done So Far

> Reconstructed from git history (172 commits, 2026-05-20 → 2026-06-30). ✅ = shipped.
> Snapshot generated 2026-06-30. Revisit / extend as work continues.

**Arc:** Started as a CRM/analytics base (mid-May) → became a multi-department platform with live integrations → most recently pivoted toward the statistical **data-intelligence engine** (metric registry, trends, LLM health insights).

---

## Foundation & Infrastructure
- ✅ Initialize repo + project structure *(5/20)*
- ✅ Call analyzer pipeline — process transcripts, extract insights, editable summaries *(5/21)*
- ✅ Session-based auth — cache identity, refresh expired tokens *(5/21)*
- ✅ Self-serve Integrations page — encrypt/store third-party creds (Mailchimp, GHL, Google, Meta) *(5/21)*

## Data Integration & Sync (WorkerBee / WGR mirror)
- ✅ WGR database foundation — models + migration for synced call-intelligence tables *(6/18)*
- ✅ WGR → CI incremental hourly sync — ~56k rows of marketing/sales/social, watermark in sync_log *(6/18–6/20)*
- ✅ RAG ingestion of WGR data into vector store *(6/18–6/20)*
- ✅ Marketing/social table mirroring (posts, comments, conversations) *(6/22)*
- ✅ Lead entry-date backfill from WGR + null-crash fixes *(6/22)*
- ✅ On-demand "data freshness" sync button + last-synced timestamp *(6/28)*
- ✅ GHL webhook capture + reverse-sync (push CI edits back to GHL) *(5/21, 5/25)*
- ✅ GHL nightly + on-demand contacts pull *(5/25)*

## Leads & Sales Pipeline
- ✅ Leads page + detail view — funnel status timeline, conversation threads, notes/tags, history *(5/24)*
- ✅ Sales Funnel visualization (inverted triangle, clickable stages filter table) *(6/28)*
- ✅ Lead Volume chart with date-range selector *(6/28)*
- ✅ Lead KPI cards — Total / This Week / Avg Deal Value *(6/28)*
- ✅ Lead-to-call association + Lead column on calls *(6/29)*
- ✅ Conversation labeling (CSR vs Lead) *(6/28)*

## Call Analytics
- ✅ All Calls page — sortable/filterable table (Type/Result/Lead) *(6/23)*
- ✅ Call detail page — transcript, metadata, provenance, edit + re-analysis on save *(5/21, 6/23)*
- ✅ Call search (lead/rep/ID) + bulk-analyze *(6/29)*
- ✅ Multi-select Type/Result filters (data-derived, not hardcoded) *(6/26, 6/29)*
- ✅ Normalize 240 sprawled `best_use_case` values → 17 disciplined enums *(6/24)*
- ✅ Analyzed Calls dashboard rebuild — KPI cards, expandable list, pagination *(6/29)*

## Team & Member Management
- ✅ Team roster page rebuilt from sales_reps (WGR-sourced) *(6/29)*
- ✅ Member detail page + editable overrides that survive sync *(6/29)*
- ✅ Consolidate /fulfillment into unified /members with department tabs *(6/29)*

## Analytics & Insights Engine (data-intelligence pivot)
- ✅ Metric registry + daily snapshot store *(6/29)*
- ✅ Trends (period-over-period) + actionable recommendations *(6/29)*
- ✅ Insights dashboard — metrics, trends, recommendations, snapshots *(6/29)*
- ✅ Overall Insight hero card — LLM daily health verdict (healthy/watch/at_risk), compounding narrative *(6/30)*
- ✅ Daily Overall Insight Celery task @ 04:05 UTC *(6/30)*
- ✅ Metrics-by-area sparklines + verdict pills *(6/29)*
- ✅ Content ideas generator from insights *(6/23)*

## Social Media (Meta Graph API)
- ✅ Instagram integration — live stats, OAuth connector + setup panel *(6/10–6/11)*
- ✅ Facebook integration — live Page stats, manual token, graceful metric degradation *(6/11)*
- ✅ Social breakdown page + recent posts + comments card (feeds RAG) *(6/12, 6/22)*

## Chat & Knowledge (RAG)
- ✅ Persistent chat sessions + resume-on-reload *(5/28, 6/16)*
- ✅ Google Drive sync → pgvector RAG, with filename retrieval *(5/26, 5/27)*
- ✅ Gmail per-user OAuth — lead-related threads on detail pages *(5/25)*

## Calendar
- ✅ Google Calendar per-user OAuth + Today's Schedule brief *(6/2, 6/11)*

## Multi-Department Workflow
- ✅ Sprint 5a Sales Director dashboard *(6/8)*
- ✅ Sprint 6a Fulfillment Director — members/coaching + CRUD *(6/8)*
- ✅ Appointments + Coaching Calls, Goals Kanban, Tech SOS tickets, cross-dept delegation *(6/10)*

## UI / Dashboard
- ✅ Mockup-fidelity redesign — gold theme, dark sidebar, dept-colored KPI grid *(6/28)*
- ✅ Weekly Snapshot sparkline, date-range selector, pagination UI *(6/28)*
- ✅ Toasts + ConfirmDialog replacing native alert/confirm *(5/21)*
