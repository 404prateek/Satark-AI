-- =============================================================================
-- Satark AI — PostgreSQL 15 Schema
-- Run with: psql -U postgres -d satark_ai -f database/init.sql
-- =============================================================================

-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- =============================================================================
-- ENUMS
-- =============================================================================
DO $$ BEGIN
    CREATE TYPE user_role        AS ENUM ('admin', 'analyst', 'viewer');
    EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE verdict          AS ENUM ('SAFE', 'SUSPICIOUS', 'PHISHING');
    EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE scan_input_type  AS ENUM ('message', 'url', 'image');
    EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE armoriq_outcome  AS ENUM ('ALLOWED', 'BLOCKED', 'FLAGGED');
    EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE threat_severity  AS ENUM ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL');
    EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE threat_category  AS ENUM (
        'phishing', 'smishing', 'vishing',
        'brand_impersonation', 'malware_url',
        'credential_harvest', 'financial_fraud', 'other'
    );
    EXCEPTION WHEN duplicate_object THEN NULL;
END $$;


-- =============================================================================
-- TABLES
-- =============================================================================

-- ── users ─────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           VARCHAR(255) NOT NULL,
    username        VARCHAR(100) NOT NULL,
    password_hash   VARCHAR(255),                        -- NULL for OAuth-only users
    google_id       VARCHAR(128),
    google_picture  VARCHAR(512),
    role            user_role    NOT NULL DEFAULT 'viewer',
    is_active       BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    last_login_at   TIMESTAMPTZ,
    CONSTRAINT uq_users_email      UNIQUE (email),
    CONSTRAINT uq_users_username   UNIQUE (username),
    CONSTRAINT uq_users_google_id  UNIQUE (google_id)
);

CREATE INDEX IF NOT EXISTS ix_users_email     ON users (email);
CREATE INDEX IF NOT EXISTS ix_users_google_id ON users (google_id);

-- Auto-update updated_at on row modification
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

DO $$ BEGIN
    CREATE TRIGGER trg_users_updated_at
        BEFORE UPDATE ON users
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    EXCEPTION WHEN duplicate_object THEN NULL;
END $$;


-- ── scans ─────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS scans (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID         NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    input_type      scan_input_type NOT NULL,
    raw_input       TEXT,
    language        VARCHAR(20),
    verdict         verdict      NOT NULL,
    risk_score      FLOAT        NOT NULL,
    confidence      FLOAT        NOT NULL,
    model_version   VARCHAR(64)  NOT NULL DEFAULT 'v1.0',
    shap_features   JSONB,                               -- [{feature, value}, …]
    explanation     TEXT,
    groq_model      VARCHAR(128),
    url_analysis    JSONB,                               -- redirect chain, whois, …
    ocr_text        TEXT,
    ocr_confidence  FLOAT,
    ocr_word_count  INTEGER,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_risk_score_range  CHECK (risk_score  >= 0 AND risk_score  <= 100),
    CONSTRAINT chk_confidence_range  CHECK (confidence  >= 0 AND confidence  <= 1)
);

CREATE INDEX IF NOT EXISTS ix_scans_user_id    ON scans (user_id);
CREATE INDEX IF NOT EXISTS ix_scans_verdict    ON scans (verdict);
CREATE INDEX IF NOT EXISTS ix_scans_created_at ON scans (created_at DESC);
-- GIN index for JSONB containment queries: WHERE shap_features @> '[{"feature":"url"}]'
CREATE INDEX IF NOT EXISTS ix_scans_shap_gin   ON scans USING GIN (shap_features);

DO $$ BEGIN
    CREATE TRIGGER trg_scans_updated_at
        BEFORE UPDATE ON scans
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    EXCEPTION WHEN duplicate_object THEN NULL;
END $$;


-- ── audit_logs ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS audit_logs (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      UUID         REFERENCES users(id) ON DELETE SET NULL,
    event_type   VARCHAR(64)  NOT NULL,
    description  TEXT         NOT NULL,
    resource_id  VARCHAR(128),
    ip_address   VARCHAR(64),
    user_agent   VARCHAR(512),
    request_id   VARCHAR(64),
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_audit_logs_user_created ON audit_logs (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_audit_logs_event_type   ON audit_logs (event_type);


-- ── armoriq_logs ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS armoriq_logs (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id   VARCHAR(64)      NOT NULL,
    route        VARCHAR(256)     NOT NULL,
    outcome      armoriq_outcome  NOT NULL,
    input_hash   CHAR(64)         NOT NULL,    -- SHA-256 hex of sanitised input
    output_hash  CHAR(64),                     -- SHA-256 hex of LLM output; NULL if BLOCKED
    block_reason TEXT,
    ip_address   VARCHAR(64),
    user_agent   VARCHAR(256),
    created_at   TIMESTAMPTZ      NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_armoriq_request_id ON armoriq_logs (request_id);
CREATE INDEX IF NOT EXISTS ix_armoriq_outcome     ON armoriq_logs (outcome);
CREATE INDEX IF NOT EXISTS ix_armoriq_created     ON armoriq_logs (created_at DESC);


-- ── threat_reports ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS threat_reports (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scan_id          UUID              NOT NULL REFERENCES scans(id) ON DELETE CASCADE,
    user_id          UUID              NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    severity         threat_severity   NOT NULL,
    category         threat_category   NOT NULL,
    title            VARCHAR(255)      NOT NULL,
    description      TEXT,
    affected_brand   VARCHAR(128),
    malicious_url    VARCHAR(2048),
    confidence       FLOAT,
    is_verified      BOOLEAN           NOT NULL DEFAULT FALSE,
    is_public        BOOLEAN           NOT NULL DEFAULT TRUE,
    auto_generated   BOOLEAN           NOT NULL DEFAULT FALSE,
    created_at       TIMESTAMPTZ       NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ       NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_threat_reports_scan_id  ON threat_reports (scan_id);
CREATE INDEX IF NOT EXISTS ix_threat_reports_user_id  ON threat_reports (user_id);
CREATE INDEX IF NOT EXISTS ix_threat_reports_severity ON threat_reports (severity);
CREATE INDEX IF NOT EXISTS ix_threat_reports_created  ON threat_reports (created_at DESC);

DO $$ BEGIN
    CREATE TRIGGER trg_threat_reports_updated_at
        BEFORE UPDATE ON threat_reports
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    EXCEPTION WHEN duplicate_object THEN NULL;
END $$;
