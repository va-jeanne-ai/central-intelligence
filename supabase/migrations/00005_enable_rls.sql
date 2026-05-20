-- Migration 00005: Enable Row Level Security on all tables
-- Supabase requires RLS to be enabled. These policies start permissive
-- (authenticated users can access everything) and should be tightened
-- per-role as the app matures.

-- ─── Enable RLS on all tables ───────────────────────────────────────────────────

ALTER TABLE users              ENABLE ROW LEVEL SECURITY;
ALTER TABLE teams              ENABLE ROW LEVEL SECURITY;
ALTER TABLE tag_dictionary     ENABLE ROW LEVEL SECURITY;
ALTER TABLE offers             ENABLE ROW LEVEL SECURITY;
ALTER TABLE business_profile   ENABLE ROW LEVEL SECURITY;
ALTER TABLE monthly_preferences ENABLE ROW LEVEL SECURITY;
ALTER TABLE leads              ENABLE ROW LEVEL SECURITY;
ALTER TABLE members            ENABLE ROW LEVEL SECURITY;
ALTER TABLE calls              ENABLE ROW LEVEL SECURITY;
ALTER TABLE insights           ENABLE ROW LEVEL SECURITY;
ALTER TABLE content_ideas      ENABLE ROW LEVEL SECURITY;
ALTER TABLE insight_tags       ENABLE ROW LEVEL SECURITY;
ALTER TABLE market_signals     ENABLE ROW LEVEL SECURITY;
ALTER TABLE goals              ENABLE ROW LEVEL SECURITY;
ALTER TABLE pain_points        ENABLE ROW LEVEL SECURITY;
ALTER TABLE wins               ENABLE ROW LEVEL SECURITY;
ALTER TABLE objections         ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_log          ENABLE ROW LEVEL SECURITY;
ALTER TABLE error_log          ENABLE ROW LEVEL SECURITY;
ALTER TABLE sync_log           ENABLE ROW LEVEL SECURITY;
ALTER TABLE idempotency_keys   ENABLE ROW LEVEL SECURITY;

-- ─── Baseline policies: authenticated users get full access ─────────────────────
-- The backend uses the service_role key (bypasses RLS), so these policies
-- only affect direct client-side queries via Supabase JS SDK.

-- Helper: allow all CRUD for any authenticated user (starter policy)
-- We create one policy per table. Tighten these as roles solidify.

CREATE POLICY "Authenticated full access" ON users
    FOR ALL USING (auth.role() = 'authenticated');

CREATE POLICY "Authenticated full access" ON teams
    FOR ALL USING (auth.role() = 'authenticated');

CREATE POLICY "Authenticated full access" ON tag_dictionary
    FOR ALL USING (auth.role() = 'authenticated');

CREATE POLICY "Authenticated full access" ON offers
    FOR ALL USING (auth.role() = 'authenticated');

CREATE POLICY "Authenticated full access" ON business_profile
    FOR ALL USING (auth.role() = 'authenticated');

CREATE POLICY "Authenticated full access" ON monthly_preferences
    FOR ALL USING (auth.role() = 'authenticated');

CREATE POLICY "Authenticated full access" ON leads
    FOR ALL USING (auth.role() = 'authenticated');

CREATE POLICY "Authenticated full access" ON members
    FOR ALL USING (auth.role() = 'authenticated');

CREATE POLICY "Authenticated full access" ON calls
    FOR ALL USING (auth.role() = 'authenticated');

CREATE POLICY "Authenticated full access" ON insights
    FOR ALL USING (auth.role() = 'authenticated');

CREATE POLICY "Authenticated full access" ON content_ideas
    FOR ALL USING (auth.role() = 'authenticated');

CREATE POLICY "Authenticated full access" ON insight_tags
    FOR ALL USING (auth.role() = 'authenticated');

CREATE POLICY "Authenticated full access" ON market_signals
    FOR ALL USING (auth.role() = 'authenticated');

CREATE POLICY "Authenticated full access" ON goals
    FOR ALL USING (auth.role() = 'authenticated');

CREATE POLICY "Authenticated full access" ON pain_points
    FOR ALL USING (auth.role() = 'authenticated');

CREATE POLICY "Authenticated full access" ON wins
    FOR ALL USING (auth.role() = 'authenticated');

CREATE POLICY "Authenticated full access" ON objections
    FOR ALL USING (auth.role() = 'authenticated');

-- Audit tables: read-only for authenticated, insert via service_role only
CREATE POLICY "Authenticated read audit_log" ON audit_log
    FOR SELECT USING (auth.role() = 'authenticated');

CREATE POLICY "Authenticated read error_log" ON error_log
    FOR SELECT USING (auth.role() = 'authenticated');

CREATE POLICY "Authenticated read sync_log" ON sync_log
    FOR SELECT USING (auth.role() = 'authenticated');

CREATE POLICY "Authenticated read idempotency_keys" ON idempotency_keys
    FOR SELECT USING (auth.role() = 'authenticated');
