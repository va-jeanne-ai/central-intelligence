-- Migration 00002: Core operational tables
-- Tables: leads, members, calls, insights, content_ideas, insight_tags, market_signals
-- Depends on: 00001 (users, tag_dictionary)

-- ─── leads ──────────────────────────────────────────────────────────────────────

CREATE TABLE leads (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        VARCHAR(255) NOT NULL,
    email       VARCHAR(255) UNIQUE,
    phone       VARCHAR(20),
    status      VARCHAR(50),        -- new, contacted, appointment-set, qualified, sale, lost
    source      VARCHAR(100),
    created_at  TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    deleted_at  TIMESTAMPTZ NULL,
    created_by  UUID REFERENCES users(id) ON DELETE SET NULL
);

CREATE TRIGGER trg_leads_updated_at
    BEFORE UPDATE ON leads
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE INDEX idx_leads_status     ON leads(status);
CREATE INDEX idx_leads_source     ON leads(source);
CREATE INDEX idx_leads_created_at ON leads(created_at);

-- ─── members ────────────────────────────────────────────────────────────────────

CREATE TABLE members (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(255) NOT NULL,
    email           VARCHAR(255) UNIQUE,
    enrollment_date TIMESTAMPTZ,
    coach_id        UUID REFERENCES users(id) ON DELETE SET NULL,
    status          VARCHAR(50) DEFAULT 'active',  -- active, paused, graduated, churned
    created_at      TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    deleted_at      TIMESTAMPTZ NULL
);

CREATE TRIGGER trg_members_updated_at
    BEFORE UPDATE ON members
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE INDEX idx_members_status   ON members(status);
CREATE INDEX idx_members_coach_id ON members(coach_id);

-- ─── calls ──────────────────────────────────────────────────────────────────────

CREATE TABLE calls (
    id                    TEXT PRIMARY KEY,  -- Format: CALL_<TranscriptUID> or CALL_<YYYYMMDD_HHMMSS>
    date                  DATE,
    call_type             VARCHAR(50),       -- Sales, Discovery, Coaching, Accountability, Support
    call_result           VARCHAR(50),       -- Closed, No Decision, Lost, Qualified, N/A
    call_owner            VARCHAR(255),
    member_id             UUID REFERENCES members(id) ON DELETE CASCADE,
    lead_id               UUID REFERENCES leads(id) ON DELETE CASCADE,
    transcript_source     VARCHAR(50),       -- Cockatoo, Otter, Fireflies, Manual
    transcript_uid        VARCHAR(255),
    transcript_quality    VARCHAR(50),       -- Clean, Moderate, Messy
    transcript_link       TEXT,
    processed_date        DATE,
    call_duration_minutes INTEGER,
    notes                 TEXT,
    created_at            TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    deleted_at            TIMESTAMPTZ NULL
);

CREATE INDEX idx_calls_member         ON calls(member_id);
CREATE INDEX idx_calls_lead           ON calls(lead_id);
CREATE INDEX idx_calls_date           ON calls(date);
CREATE INDEX idx_calls_call_type      ON calls(call_type);
CREATE INDEX idx_calls_transcript_uid ON calls(transcript_uid);

-- ─── insights ───────────────────────────────────────────────────────────────────

CREATE TABLE insights (
    id                    TEXT PRIMARY KEY,  -- Format: INS_<CallID>_01
    call_id               TEXT NOT NULL REFERENCES calls(id) ON DELETE CASCADE,
    speaker_name          VARCHAR(255),
    insight_type          VARCHAR(50),       -- Pain, Goal, Objection, False Belief, Win, Breakthrough, Product Issue, Feature Request
    signal_family         VARCHAR(255),
    signal                TEXT,
    signal_strength       VARCHAR(50),       -- Strong, Moderate, Weak
    pain_layer            VARCHAR(50),       -- Surface, Emotional, Existential (Pains only)
    raw_quote             TEXT,
    what_they_say         TEXT,
    the_real_problem      TEXT,
    emotional_driver      TEXT,
    core_fear_revealed    TEXT,
    false_belief_revealed TEXT,
    structural_obstacle   TEXT,
    identity_signal       TEXT,
    buying_trigger        TEXT,
    objection_created     TEXT,
    marketing_translation TEXT,
    hook_angle_example    TEXT,
    best_use_case         VARCHAR(100),      -- Email, Webinar, VSL, Ads, Social
    quote_confidence      VARCHAR(50),       -- High, Medium, Low
    frequency_score       INTEGER DEFAULT 1,
    created_at            TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_insights_call         ON insights(call_id);
CREATE INDEX idx_insights_family       ON insights(signal_family);
CREATE INDEX idx_insights_signal       ON insights(signal);
CREATE INDEX idx_insights_insight_type ON insights(insight_type);
CREATE INDEX idx_insights_strength     ON insights(signal_strength);
CREATE INDEX idx_insights_created_at   ON insights(created_at);

-- ─── content_ideas ──────────────────────────────────────────────────────────────

CREATE TABLE content_ideas (
    id                     TEXT PRIMARY KEY,  -- Format: CONT_<CallID>_01
    insight_id             TEXT REFERENCES insights(id) ON DELETE SET NULL,
    call_id                TEXT REFERENCES calls(id) ON DELETE SET NULL,
    source                 VARCHAR(100),      -- AI Extraction, Manual Entry, Brainstorm
    market_audience        VARCHAR(255),
    content_format         VARCHAR(100),      -- Email, Reel, YouTube, Webinar, Ad, VSL, Post
    content_angle          TEXT,
    trigger_insight        TEXT,
    raw_quote              TEXT,
    content_premise        TEXT,
    hook_opening_line      TEXT,
    teaching_point         TEXT,
    cta_idea               TEXT,
    priority_level         VARCHAR(50),       -- High, Medium, Low
    best_platform          VARCHAR(100),      -- Email, LinkedIn, YouTube, etc.
    repurpose_opportunities TEXT,
    idea_score             INTEGER CHECK (idea_score >= 0 AND idea_score <= 10),
    status                 VARCHAR(50) DEFAULT 'Idea',  -- Idea, Scheduled, Written, Sent, Archived
    created_at             TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    deleted_at             TIMESTAMPTZ NULL
);

CREATE INDEX idx_content_ideas_insight_id ON content_ideas(insight_id);
CREATE INDEX idx_content_ideas_status     ON content_ideas(status);
CREATE INDEX idx_content_ideas_format     ON content_ideas(content_format);

-- ─── insight_tags ───────────────────────────────────────────────────────────────

CREATE TABLE insight_tags (
    id         SERIAL PRIMARY KEY,
    insight_id TEXT NOT NULL REFERENCES insights(id) ON DELETE CASCADE,
    tag        VARCHAR(100) NOT NULL REFERENCES tag_dictionary(tag) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_insight_tags_insight ON insight_tags(insight_id);
CREATE INDEX idx_insight_tags_tag     ON insight_tags(tag);

-- ─── market_signals ─────────────────────────────────────────────────────────────

CREATE TABLE market_signals (
    id                  SERIAL PRIMARY KEY,
    signal_family       VARCHAR(255),
    signal              TEXT,
    insight_type        VARCHAR(50),
    total_mentions      INTEGER DEFAULT 0,
    last_30_days        INTEGER DEFAULT 0,
    last_7_days         INTEGER DEFAULT 0,
    example_quote       TEXT,
    example_call_id     TEXT REFERENCES calls(id) ON DELETE SET NULL,
    best_marketing_angle TEXT,
    notes               TEXT,
    updated_at          TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_market_signals_family ON market_signals(signal_family);

CREATE TRIGGER trg_market_signals_updated_at
    BEFORE UPDATE ON market_signals
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
