# New Client Discovery Checklist

What we need from a new company before their Central Intelligence instance can be
built. Send this to the client contact; items are grouped by who typically answers
them. Nothing here requires write access to any client system — CI only ever
**reads** from the client's database.

## 1. Database access (technical contact)

- [ ] **Read-only Postgres role** on their Supabase project (or other Postgres),
      and its connection string (host, port, database, user, password).
      A dedicated role limited to `SELECT` is strongly preferred — CI additionally
      forces `READ ONLY` at the session level, but least-privilege is the rule.
- [ ] Permission to **dump the schema** (tables, columns, PK/FK, row counts) and
      to sample a small number of rows per table for mapping purposes.
- [ ] Confirmation of **which tables are actively synced/populated** — is
      everything in the business really landing in this database, or are some
      systems not wired in yet? (List anything missing.)
- [ ] Any tables we must **exclude** (PII beyond what CI needs, HR, payroll,
      anything contractually off-limits).

## 2. Business semantics (owner / ops lead)

Plain-English answers — no technical knowledge needed:

- [ ] What is a **customer** in your business, and where does one live in your data?
- [ ] What is a **revenue event** (a sale, an invoice, a subscription payment, a
      placement…)? What amount/date fields define it?
- [ ] Who counts as a **team member** whose performance CI should track?
- [ ] What are your **interactions** (calls, meetings, tickets, messages, visits)?
- [ ] What does your **pipeline** look like — the stages a customer moves through,
      in order, with the exact labels your data uses.
- [ ] The **KPIs you actually run the business on** — ideally the spreadsheet or
      dashboard you look at weekly. For each: how it's computed and what "good"
      looks like.

## 3. Departments & modules (owner)

- [ ] What **departments** should CI have directors for? (Default: Marketing,
      Sales, Fulfillment — rename, remove, or add.)
- [ ] Which CI modules apply: sales calls / appointments / email marketing /
      social media / coaching-style QA & scorecards / webinars? (Anything not
      applicable is simply disabled.)

## 4. Integrations (technical or ops contact)

- [ ] Which of these do you use and want connected: Mailchimp, GoHighLevel,
      Google Workspace (Gmail/Drive/Calendar), Meta Ads, Google Ads,
      Instagram/Facebook pages?
- [ ] For each: who owns the account and can approve the OAuth/API connection?

## 5. Branding & setup (owner)

- [ ] Product name to display (white-label name), logo file, primary brand colors.
- [ ] **Currency** and **timezone** for reporting.
- [ ] Domain or subdomain for the app (e.g. `ci.yourcompany.com`) and who manages
      DNS.
- [ ] **Admin users**: names + emails of the people who should have admin access.
- [ ] Preferred terminology if different from defaults (e.g. you say "clients"
      not "leads", "placements" not "sales").

## 6. Commercial/ops (us)

- [ ] Anthropic/Voyage API budget expectations set with the client.
- [ ] Hosting: new DigitalOcean droplet + Supabase project + Vercel project per
      client (never shared with any other client).
- [ ] Signed authorization for read-only access to their database.

---

**What happens next once this is complete:** we introspect the schema, propose a
data mapping (which of their tables feed which CI concepts), review it with them,
run a historical backfill, and turn on hourly sync. Then directors, metrics, and
branding are configured to match the answers above.
