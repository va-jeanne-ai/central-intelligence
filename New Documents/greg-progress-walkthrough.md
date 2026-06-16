# Central Intelligence — Progress Walkthrough (for Greg)

> A guide for **presenting** the build to Greg. Talk in terms of *what it does for the business*, not the tech. Demo live where you can. Suggested length: 20–30 min + questions.

---

## 0. Before the meeting (5-min prep)

- [ ] Backend running (`uvicorn` :8000), Celery worker running, Next dev on **:3000**.
- [ ] Log in once so you're not fumbling with auth on screen-share.
- [ ] Have these tabs open in order: **Dashboard → CI Chat → Marketing → Sales → Fulfillment → Integrations**.
- [ ] One-line framing to open with: *"The system is feature-complete across all three departments and the AI coordinator. Today I'll show you what works, what's live with real data, and what's next before launch."*

---

## 1. The big picture (2 min — set the frame)

Explain the shape of the product in one breath:

- **Central Intelligence** is the "CEO" AI you chat with. It coordinates **three departments** — Marketing, Sales, Fulfillment — each run by its own AI "Director" with specialists underneath.
- You ask CI one question ("what should we focus on this week?") and it pulls from all three departments and answers as one voice.
- Everything is backed by a real database + dashboards, not mockups.

**Say this:** "Think of it as your operations team in software — a chief of staff that can see across the whole business, with department heads it can delegate to."

---

## 2. The Dashboard (3 min — the home base)

Open `/dashboard`. Walk top to bottom:

- **Department snapshot cards** — live counts across Sales / Marketing / Fulfillment.
- **This Week's Focus** — the AI coordinator's synthesized cross-department priorities. *Call out:* "This is CI actually consulting all three departments and writing one prioritized list."
- **Today's Schedule** — pulls your connected Google Calendar for today, in your timezone.
- **Recommendations** — AI-generated next actions from live business metrics.

**Talking point:** "The dashboard isn't static — these numbers come from the live database and refresh as data flows in."

---

## 3. Central Intelligence Chat (4 min — the headline feature)

Open the CI chat. Do a **live demo**:

- Ask: **"What should we focus on this week?"** → it delegates to all three Directors and synthesizes one answer.
- Ask a scoped question: **"How's our sales pipeline looking?"** → it routes just to Sales.
- Point out the **history sidebar** — past conversations are saved; you can reopen any of them.
- Mention: **reload the page and it drops you back into your last conversation** (just shipped).

**Talking points:**
- "It remembers context within a conversation and across sessions."
- "It never exposes the 'plumbing' — you talk to one assistant, even though three departments are working behind it."
- *Strict rule worth stating:* "Only Central Intelligence sees across departments. The department Directors stay in their lane — that keeps answers focused and the data boundaries clean."

---

## 4. The three departments (6 min — breadth)

Click through one representative page per department so Greg sees the depth. Don't dwell — this is "look how much is here."

**Marketing** (`/marketing`)
- Overview + a Marketing Director chat.
- Specialist surfaces: Social, Email (with a compose builder), Funnels, Ads, DM, Offers, Promo Calendar.
- CI surfaces: Insights, **Market Signals** (trends mined from call transcripts), Content Ideas, Transcript upload.

**Sales** (`/sales`)
- Leads directory (full CRUD) + lead detail.
- Sales-calls list + per-call analysis.
- Appointments (synced from GHL).
- Sales Director chat.

**Fulfillment** (`/fulfillment`)
- Members directory + detail.
- Coaching Calls.
- **Accountability** — goals with a drag-and-drop kanban board.
- **Tech SOS** — member support tickets (members submit, staff resolve).

**Talking point:** "Every department has its data pages, its AI Director, and feeds insights back up to Central Intelligence."

---

## 5. Integrations — what's connected to the real world (4 min)

Open `/integrations`. This is where "real data" lives. Be honest about live vs. pending.

**Live and working:**
- **Go High Level (GHL)** — two-way contact sync (inbound webhook + nightly pull).
- **Google Workspace** — Gmail, Drive, Calendar (each staffer connects their own).
- **Mailchimp** — email campaign metrics.
- **Facebook** — Page metrics via the Meta Graph API (just wired; pulling live follower data).
- **Instagram** — connector built (manual token); needs a linked Instagram Business account to pull data.

**Demo:** click a connector → show the **"Sync now"** button and the setup steps.

**Be straight with Greg about Instagram:** "Facebook is live. Instagram is built and ready, but it requires the Instagram account to be a Business/Creator account linked to a Facebook Page — that's an account-setup step on the Instagram side, not a code gap."

**Coming soon (visible in the UI, honestly labeled):** TikTok, LinkedIn.

---

## 6. What's next — the roadmap (3 min — end on direction)

Frame this as "feature-complete, now hardening for launch." Lead with the one that matters most.

1. **Data Migration (the launch blocker).** "The app runs on sample data today. The biggest remaining piece is importing your real historical data — leads, members, calls — from your existing tools. That's the gate before going live for real."
2. **Notifications & alerts** — proactive nudges for hot leads / risks, instead of having to go look.
3. **Email send** — the compose tool currently saves drafts; wiring it to actually send.
4. **Security hardening** — production-readiness (resilience, credential rotation) before launch.
5. **Later/roadmap:** one-click "Connect with Meta," TikTok/LinkedIn, automatic transcript ingestion.

**Closing line:** "Everything the system *does* is built and working. The remaining work is getting your real data in and the production polish to launch safely."

---

## 7. Likely questions from Greg — quick answers

- **"Is this using real data yet?"** → "Integrations like GHL, Google, Mailchimp, and Facebook are live. The full historical migration is the next big task."
- **"Can I use it now?"** → "You can use every feature today with current/sample data; we hold the real launch until the data migration and security hardening are done."
- **"What about Instagram?"** → "Built and ready — it just needs the IG account switched to Business and linked to a Facebook Page on your side."
- **"How much is left?"** → "The features are done across all three departments and the AI coordinator. What's left is data migration, alerts, email-send, and launch hardening."
- **"Does the AI make things up?"** → "No — it answers from the live database and connected tools, and says when it doesn't have a number rather than inventing one."

---

## Quick-reference: shipped vs. remaining

**Shipped & working:** Auth · CI chat (with delegation + memory + history) · Dashboard (focus, schedule, recommendations) · Marketing dept (6 specialists + pages) · Sales dept (leads, calls, appointments) · Fulfillment dept (members, coaching, goals board, Tech SOS) · Market Signals · Integrations: GHL, Google Workspace, Mailchimp, Facebook (live), Instagram (built).

**Remaining:** Data Migration (launch blocker) · Notifications/alerts · Email send · Security hardening · (roadmap) Meta OAuth, TikTok/LinkedIn, transcript auto-ingest.
