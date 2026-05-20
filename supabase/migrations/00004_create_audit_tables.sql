-- Migration 00004: Audit tables
-- Tables: audit_log, error_log (with Sprint 1B columns), sync_log, idempotency_keys
-- Depends on: 00001 (users)

-- ─── audit_log ──────────────────────────────────────────────────────────────────

CREATE TABLE audit_log (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      UUID REFERENCES users(id) ON DELETE SET NULL,
    action       VARCHAR(50),       -- CREATE, UPDATE, DELETE, EXPORT
    table_name   VARCHAR(100),
    record_id    TEXT,
    before_value JSONB,
    after_value  JSONB,
    ip_address   INET,
    created_at   TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_audit_log_user       ON audit_log(user_id);
CREATE INDEX idx_audit_log_action     ON audit_log(action);
CREATE INDEX idx_audit_log_table      ON audit_log(table_name);
CREATE INDEX idx_audit_log_created_at ON audit_log(created_at);

-- ─── error_log ──────────────────────────────────────────────────────────────────
-- Includes Sprint 1B additions: agent_id, request_id, user_id, stack_trace

CREATE TABLE error_log (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    error_message TEXT,
    error_code    VARCHAR(50),
    context       JSONB,
    severity      VARCHAR(50),      -- ERROR, WARNING, INFO
    agent_id      VARCHAR(128),     -- Sprint 1B: which agent logged this
    request_id    VARCHAR(255),     -- Sprint 1B: correlate with API request
    user_id       UUID REFERENCES users(id) ON DELETE SET NULL,  -- Sprint 1B: user context
    stack_trace   TEXT,             -- Sprint 1B: full stack trace
    created_at    TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_error_log_severity   ON error_log(severity);
CREATE INDEX idx_error_log_error_code ON error_log(error_code);
CREATE INDEX idx_error_log_agent_id   ON error_log(agent_id);
CREATE INDEX idx_error_log_request_id ON error_log(request_id);
CREATE INDEX idx_error_log_user_id    ON error_log(user_id);
CREATE INDEX idx_error_log_created_at ON error_log(created_at);

-- ─── sync_log ───────────────────────────────────────────────────────────────────

CREATE TABLE sync_log (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operation    VARCHAR(50),       -- migrate, import, export
    table_name   VARCHAR(100),
    record_count INTEGER,
    status       VARCHAR(50),       -- success, failed, partial
    details      JSONB,
    created_at   TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_sync_log_operation  ON sync_log(operation);
CREATE INDEX idx_sync_log_status     ON sync_log(status);
CREATE INDEX idx_sync_log_created_at ON sync_log(created_at);

-- ─── idempotency_keys ───────────────────────────────────────────────────────────

CREATE TABLE idempotency_keys (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operation_key VARCHAR(255) UNIQUE NOT NULL,
    result        JSONB,
    created_at    TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_idempotency_keys_created_at ON idempotency_keys(created_at);
