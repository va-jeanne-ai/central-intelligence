-- Migration 00001: Foundation tables (no foreign key dependencies)
-- Tables: users, teams, tag_dictionary, offers, business_profile, monthly_preferences
-- Run this FIRST before any other migration.

-- ─── Enable extensions ─────────────────────────────────────────────────────────

CREATE EXTENSION IF NOT EXISTS "pgcrypto";  -- gen_random_uuid()

-- ─── updated_at trigger function ────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ─── users ──────────────────────────────────────────────────────────────────────

CREATE TABLE users (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email       VARCHAR(255) UNIQUE NOT NULL,
    name        VARCHAR(255),
    role        VARCHAR(50),        -- admin, coach, agent, viewer
    is_active   BOOLEAN DEFAULT true,
    created_at  TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TRIGGER trg_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ─── teams ──────────────────────────────────────────────────────────────────────

CREATE TABLE teams (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        VARCHAR(255) NOT NULL,
    description TEXT,
    created_at  TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- ─── tag_dictionary ─────────────────────────────────────────────────────────────

CREATE TABLE tag_dictionary (
    tag         VARCHAR(100) PRIMARY KEY,
    tag_type    VARCHAR(50),        -- Theme, Pain, Goal, Objection, Identity, Other
    synonyms    TEXT,               -- Comma-separated
    notes       TEXT,
    created_at  TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- ─── offers ─────────────────────────────────────────────────────────────────────

CREATE TABLE offers (
    offer_id    TEXT PRIMARY KEY,   -- OFFER_001, OFFER_MENTORSHIP_10K
    name        VARCHAR(255) NOT NULL,
    offer_type  VARCHAR(50),        -- Product, Service, Webinar, VSL, Course, Coaching
    description TEXT,
    price       NUMERIC(10, 2),
    status      VARCHAR(50) DEFAULT 'Active',  -- Active, Inactive, Coming Soon
    url         TEXT,
    notes       TEXT,
    created_at  TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- ─── business_profile ───────────────────────────────────────────────────────────

CREATE TABLE business_profile (
    id                  SERIAL PRIMARY KEY,
    business_name       VARCHAR(255),
    mission             TEXT,
    target_audience     TEXT,
    brand_voice         TEXT,
    core_values         TEXT,
    key_differentiators TEXT,
    primary_market      VARCHAR(255),
    notes               TEXT,
    updated_at          TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TRIGGER trg_business_profile_updated_at
    BEFORE UPDATE ON business_profile
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ─── monthly_preferences ────────────────────────────────────────────────────────

CREATE TABLE monthly_preferences (
    id              SERIAL PRIMARY KEY,
    month           INTEGER,
    year            INTEGER,
    sending_days    TEXT[],
    emails_per_week INTEGER,
    email_types     TEXT[],
    primary_goal    TEXT,
    secondary_goal  TEXT,
    active_offers   TEXT[],         -- Array of offer_ids
    notes           TEXT,
    created_at      TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(month, year)
);
