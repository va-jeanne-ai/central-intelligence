-- Migration 00003: Support tables
-- Tables: goals, pain_points, wins, objections
-- Depends on: 00002 (leads, members)

-- ─── goals ──────────────────────────────────────────────────────────────────────

CREATE TABLE goals (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    member_id   UUID REFERENCES members(id) ON DELETE CASCADE,
    lead_id     UUID REFERENCES leads(id) ON DELETE CASCADE,
    goal_text   TEXT NOT NULL,
    target_date DATE,
    status      VARCHAR(50) DEFAULT 'active',
    created_at  TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    deleted_at  TIMESTAMPTZ NULL
);

CREATE INDEX idx_goals_member ON goals(member_id);
CREATE INDEX idx_goals_lead   ON goals(lead_id);
CREATE INDEX idx_goals_status ON goals(status);

-- ─── pain_points ────────────────────────────────────────────────────────────────

CREATE TABLE pain_points (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    member_id       UUID REFERENCES members(id) ON DELETE CASCADE,
    lead_id         UUID REFERENCES leads(id) ON DELETE CASCADE,
    text            TEXT NOT NULL,
    category        VARCHAR(100),
    frequency_count INTEGER DEFAULT 1,
    created_at      TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    deleted_at      TIMESTAMPTZ NULL
);

CREATE INDEX idx_pain_points_member   ON pain_points(member_id);
CREATE INDEX idx_pain_points_lead     ON pain_points(lead_id);
CREATE INDEX idx_pain_points_category ON pain_points(category);

-- ─── wins ───────────────────────────────────────────────────────────────────────

CREATE TABLE wins (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    member_id   UUID REFERENCES members(id) ON DELETE CASCADE,
    win_text    TEXT NOT NULL,
    win_date    DATE,
    impact_area VARCHAR(100),
    created_at  TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    deleted_at  TIMESTAMPTZ NULL
);

CREATE INDEX idx_wins_member ON wins(member_id);

-- ─── objections ─────────────────────────────────────────────────────────────────

CREATE TABLE objections (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id           UUID REFERENCES leads(id) ON DELETE CASCADE,
    objection_text    TEXT NOT NULL,
    context           VARCHAR(255),
    resolution_offered TEXT,
    created_at        TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    deleted_at        TIMESTAMPTZ NULL
);

CREATE INDEX idx_objections_lead ON objections(lead_id);
