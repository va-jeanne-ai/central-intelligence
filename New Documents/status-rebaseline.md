# Central Intelligence — Status Re-baseline

> **As of 2026-06-29.** An engineering-facing snapshot of *what's actually built* vs.
> the original 8-sprint plan, why the work has drifted, the real gaps, and the
> recommended next steps. Complements (does not replace) `sprint-plan-enhanced.md`
> (the original plan) and `greg-progress-walkthrough.md` (the client demo guide).
>
> Evidence-based: every status below was checked against the code, not memory.

---

## 1. TL;DR

- The 8-sprint plan is **~82% built**. Foundations are unusually complete:
  **3 Directors, 11 specialists, 4+ operators, ~60 DB models, ~30 backend route
  modules, ~43 frontend pages.** Sprints 1a–6 are essentially done.
- **The work has drifted — healthily.** A large share of what actually shipped was
  *not* in the original plan: the **WGR sync** (upstream-mirror data pipeline) is now
  the backbone, plus Google Workspace, embeddings, stats updaters, GHL push, promo
  calendar, integrations catalog.
- The plan document **no longer reflects how work is sequenced.** The pivot was from
  "build the agentic org chart" → "make every surface real against the mockup + wire
  the WGR data." This doc re-baselines to that reality.

---

## 2. Plan vs. built — per sprint

| Sprint | Focus | Status | Evidence |
|--------|-------|--------|----------|
| 1a | Foundation (FastAPI, Supabase, ORM, CI skeleton, Chat, Dashboard) | ✅ done | `app/main.py`, `app/models/` (~60), `app/agents/base.py`, `app/(app)/dashboard`, `/chat` |
| 1b | Auth + error handling + toasts | ✅ done | `app/routes/auth.py`, `app/middleware/auth.py`, `lib/toast.ts`, error boundaries |
| 2 | Marketing Director + Transcriber + ICP + CI webhooks + market signals | ✅ done | `agents/directors/marketing.py`, `tasks/transcriber.py`, `routes/ci.py`, `routes/icp.py` |
| 3 | Marketing specialists batch 1 (social/email/funnels) + stats updaters | ✅ done | `agents/specialists/{social_media,email,funnels}.py`, `tasks/*_stats.py` |
| 4 | Marketing specialists batch 2 (ads/DM/offers) + offer generator | ✅ done | `agents/specialists/{ads,dm,offers}.py`, `tasks/offer_generator.py` |
| 5 | Sales (Director, Leads, Appointments, Call Analyzer) | ✅ done | `agents/directors/sales.py`, `routes/{leads,appointments,sales}.py`, `/sales-calls/*` |
| 6 | Fulfillment (Director, Members, Coaching, Accountability, Tech SOS) | 🟡 mostly | routes + pages all present; **ActiveCampaign + Fireflies integrations not wired** |
| 7 | Data migration (batch import + GHL sync) | 🟡 partial | GHL/WGR sync live; **no batch-import path or `/data-import` page** |
| 8 | CI intelligence + polish (weekly digest, Redis memory, exec dashboard, notifications) | 🟡 partial | CI agent exists; **digest task, Redis memory, notifications absent** |

**Architectural note:** Accountability and Tech SOS shipped as *routes + models* rather
than as *specialist agents* (the plan called for agents). Functionally complete,
architecturally simpler — fine, just worth recording.

---

## 3. Drift — built but not in the original plan

These are the backbone of the current product and explain the recurring "edit vs.
sync" / "empty table" issues:

1. **WGR sync** — the upstream-mirror ingestion pipeline (`services/wgr_sync/`). Now
   the primary data source. This is why several tables are read-only mirrors and why
   editing them needs an overrides layer (see `rep_overrides`).
2. **Google Workspace** — Calendar / Drive / Gmail sync + OAuth.
3. **Embedding infrastructure** — `tasks/embed_*`, `Embedding`/`EmbedPending`/`EmbeddingBudget` models.
4. **Stats updaters** — email / social / funnel / comments collectors (Celery).
5. **GHL bidirectional push** — plan had ingestion only; push is extra.
6. **Integrations catalog** — Mailchimp, Meta Ads, Google Ads, Google Calendar/Workspace
   registered in `integrations_registry.py` (governance doc: `INTEGRATIONS.md`).
7. **Promo calendar**, **call-type classifier**, **faceted market-signals**.

---

## 4. Real gaps (plan items with no evidence in code)

| Gap | Sprint | Severity | Note |
|-----|--------|----------|------|
| ActiveCampaign + Fireflies integrations | 6 | 🔴 | Only a passing mention in `routes/ci.py`; not in the registry, not wired |
| Batch data import / `/data-import` page | 7 | 🔴 | Sidebar links to it but **page + route don't exist → 404** |
| Weekly digest task | 8 | 🟡 | No `tasks/*digest*`; high value for the CI "chief of staff" pitch |
| Redis conversation memory | 8 | 🟡 | Not evident; improves CI chat continuity |
| Executive cross-dept dashboard | 8 | 🟡 | Current `/dashboard` is a KPI view, not a cross-department synthesis |
| Notification system | 8 | 🟢 | Post-launch candidate |

---

## 5. Roadmap — what's next (by impact)

> **⚠️ Superseded (2026-06-29):** the project goal has shifted. We are **not** building
> more operational features. The new direction is a data-analysis + recommendation
> engine — see **[north-star-data-intelligence.md](./north-star-data-intelligence.md)**.
> The list below is retained only as a record of feature-completeness gaps; the Login
> page and the Insights dashboard (the engine's surface) are the only items still
> clearly in scope.


1. **Login page** — mockup exists, page not built. **Blocks production launch.**
2. **The 3 Director pages** (`/sales-director`, `/marketing-director`,
   `/fulfillment-director`) — all ~22-LOC stubs delegating to chat views. Core product
   surfaces, currently the thinnest. Needs backend orchestration endpoints too.
3. **`/calls`** — thin stub (~26 LOC); lacks the search/filters the Sales Calls page
   has. Small, quick win.
4. **Chat & Calendar polish** — functional but lean; validate against the mockup.
5. **Decide `/data-import`** — build it or remove the nav entry (see §6).

---

## 6. Loose ends / debt to clean up

**🔴 Worth fixing**
- **`/data-import` nav 404** — `components/layout/sidebar.tsx:126` links to a page that
  doesn't exist. Cheapest fix in the review: build the page, or drop the nav entry.
- **Silent FK-orphan nulling** in WGR sync — `services/wgr_sync/upsert.py` NULLs FKs when
  a parent row is missing, with no per-run metric/log. This is the root of the recurring
  "empty/broken join" surprises (members empty, `calls.lead_id` NULL). Add a count + log.

**🟡 Worth noting**
- Disabled GHL inbound webhooks still present (`routes/webhooks.py`, return 410) — decide
  legacy-and-delete vs. document.
- Several `react-hooks/exhaustive-deps` eslint-disables without justification (appointments,
  leads, accountability, sales-calls, tech-sos pages; calls-table).
- Mock auth tokens live in the prod code path (`routes/auth.py`), gated only by an unset
  `supabase_url`.
- `rep_overrides` migration is hand-written (autogenerate drift on this DB) — document the
  pattern so future model changes don't silently miss a migration.
- Email-template "v2" TODOs in `lib/email-templates.ts` (callouts, numbered/checkmark lists).

**🟢 Clean**
- Page redirects, route registration, and integration-credential encryption all check out.

---

## 7. Recommended sequence before launch

1. Resolve `/data-import` (build or remove) — kills a guaranteed user-facing 404.
2. Build the **Login page** (launch blocker).
3. Flesh out the **3 Director pages** + their backend orchestration.
4. Add **WGR sync observability** (orphan-null counts) so data drift stops being invisible.
5. Then revisit Sprint-8 intelligence (weekly digest first — highest narrative value).
