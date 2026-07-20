# Discovery prompt — send this file to the client

Instructions for the client: open Claude (Claude Code in VS Code) in the project
that has access to your Supabase/database, paste everything below the line into
the chat, and follow along. At the end you'll have one report file to send back
to us.

---

I'm preparing to onboard our company onto **Central Intelligence**, an AI
business-intelligence platform. It will connect to our database **read-only**,
sync our data into its own system, and let us ask questions about our business.
The vendor needs a discovery report from us. Your job is to build that report —
part by inspecting our database yourself, part by interviewing me.

## Ground rules

- **Read-only, always.** Never create, modify, or delete anything in the
  database. SELECT and introspection queries only.
- **No secrets in the report.** Never include passwords, API keys, tokens, or
  connection strings in the report file. If you find columns that look like
  credentials or tokens, note the column NAME only and flag it.
- **No bulk personal data.** When sampling rows, look at a handful to
  understand shape and meaning — put column names, types, and *descriptions*
  in the report, not dumps of customer emails/phones. A single realistic but
  masked example value per column is fine (e.g. `j***@gmail.com`).
- If you can't connect to the database from this environment, skip Part 1,
  tell me what you'd need, and continue with the interview parts.

## Part 1 — Database inventory (do this yourself)

Connect to our Supabase/Postgres (use the connection details already available
in this project's environment — ask me if you can't find them; I'll run the
queries for you if needed) and produce:

1. **Table inventory**: every table in the `public` schema with its row count,
   sorted by row count descending. Mark which tables look actively used
   (recent `created_at`/`updated_at` values) vs stale or empty.
2. **Schema detail** for each non-empty table: columns (name, type, nullable),
   primary key, and foreign keys to other tables.
3. **Your read of the data model**: in plain English, what does each major
   table represent in our business? Which tables look like they hold:
   - customers/contacts/end-users
   - money events (sales, orders, invoices, payments, subscriptions)
   - our team members / staff
   - interactions (calls, meetings, messages, tickets, appointments, visits)
   - anything else load-bearing
4. **Pipeline/status vocabularies**: for any column that looks like a status
   or stage (e.g. `status`, `stage`, `state`), list its distinct values and
   how many rows hold each value.
5. **Freshness check**: for the 10 biggest tables, the most recent
   `created_at`/`updated_at` — is data actually landing here today, or does
   the sync from our other systems look broken/stale?
6. **Sensitive-table flags**: anything that looks like HR, payroll,
   credentials, or otherwise not for a vendor's eyes — list it under
   "suggest excluding".

## Part 2 — Interview me (one question at a time)

Ask me these, one at a time, and refine my answers with follow-ups until
they'd be clear to someone who has never seen our business. Where Part 1
already suggests an answer, propose it and let me confirm or correct:

1. What is a **customer** for us, and which table(s) hold them?
2. What is a **revenue event** — the moment money is won? Which table/columns
   define it (amount, date, who)?
3. Who are the **team members** whose performance should be tracked?
4. What are our **interactions** with customers (calls, meetings, messages…)?
5. What does our **pipeline** look like — the stages in order, using the exact
   labels from our data (cross-check against the status vocabularies you found)?
6. The **KPIs we actually run the business on** — for each: name, how it's
   computed (in terms of our tables/columns if possible), and what "good"
   looks like.
7. What **departments** should the platform have AI directors for? (Default:
   Marketing, Sales, Fulfillment — rename/remove/add.)
8. Which modules apply to us: sales calls / appointments / email marketing /
   social media / QA scorecards / webinars?

## Part 3 — Logistics (quick-fire, I answer directly)

1. Which of these do we use and want connected: Mailchimp, GoHighLevel,
   Google Workspace (Gmail/Drive/Calendar), Meta Ads, Google Ads,
   Instagram/Facebook pages? Who owns each account?
2. Branding: display name for the platform, logo file, primary brand colors.
3. Currency and timezone for reporting.
4. Domain/subdomain for the app (e.g. `ci.ourcompany.com`) and who manages DNS.
5. Admin users: names + emails of people who should have admin access.
6. Terminology: words we use instead of the defaults (e.g. we say "clients"
   not "leads").

## Part 4 — Produce the deliverables

1. Write everything to a single file, **`ci-discovery-report.md`**, structured
   as: Database Inventory → Data Model Reading → Business Semantics →
   KPIs → Departments & Modules → Integrations → Branding & Setup →
   Suggested Exclusions → Open Questions. Include the masked samples, not raw
   personal data. State clearly at the top which parts came from database
   inspection vs my answers.
2. Separately, **propose (do not run)** the SQL to create a dedicated
   **read-only Postgres role** for the vendor on our Supabase project —
   `CREATE ROLE` + `GRANT SELECT` on the tables NOT in the exclusion list,
   with a note on where we'd run it (Supabase SQL editor) and that we hand
   over only that role's connection string, never our `postgres` credentials.
3. Remind me at the end: send `ci-discovery-report.md` back to the vendor
   through a private channel, and send the read-only connection string
   separately through a password manager or other secure channel — never
   email both together.
