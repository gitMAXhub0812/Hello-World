-- ReviewGuard Database Schema
-- PostgreSQL 16

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ── Reviews ──────────────────────────────────────────────────────────────────
-- Raw review data as ingested from any platform
CREATE TABLE reviews (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    platform        VARCHAR(50) NOT NULL,          -- 'google', 'jameda', 'manual'
    external_id     VARCHAR(255),                  -- platform-side review ID if known
    reviewer_name   VARCHAR(255),
    rating          SMALLINT CHECK (rating BETWEEN 1 AND 5),
    content         TEXT NOT NULL,
    review_date     TIMESTAMPTZ,
    ingested_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    url             TEXT,
    raw_data        JSONB,
    is_processed    BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE (platform, external_id)
);

CREATE INDEX idx_reviews_platform       ON reviews (platform);
CREATE INDEX idx_reviews_ingested_at    ON reviews (ingested_at DESC);
CREATE INDEX idx_reviews_is_processed   ON reviews (is_processed);
CREATE INDEX idx_reviews_rating         ON reviews (rating);

-- ── Classifications ───────────────────────────────────────────────────────────
-- AI analysis result for each review
CREATE TABLE classifications (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    review_id               UUID NOT NULL REFERENCES reviews(id) ON DELETE CASCADE,
    classified_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    model_used              VARCHAR(100) NOT NULL,
    overall_risk_score      NUMERIC(4,3) NOT NULL CHECK (overall_risk_score BETWEEN 0 AND 1),

    -- Category flags + confidence (0.0–1.0)
    is_insult               BOOLEAN NOT NULL DEFAULT FALSE,
    insult_confidence       NUMERIC(4,3),
    is_spam                 BOOLEAN NOT NULL DEFAULT FALSE,
    spam_confidence         NUMERIC(4,3),
    is_fake                 BOOLEAN NOT NULL DEFAULT FALSE,
    fake_confidence         NUMERIC(4,3),
    has_false_claims        BOOLEAN NOT NULL DEFAULT FALSE,
    false_claims_confidence NUMERIC(4,3),
    is_toxic                BOOLEAN NOT NULL DEFAULT FALSE,
    toxic_confidence        NUMERIC(4,3),

    reasoning               TEXT,
    flagged_phrases         TEXT[],
    raw_ai_response         JSONB,

    UNIQUE (review_id)  -- one classification per review (overwritten on re-classify)
);

CREATE INDEX idx_classifications_risk   ON classifications (overall_risk_score DESC);
CREATE INDEX idx_classifications_review ON classifications (review_id);

-- ── Moderation Drafts ─────────────────────────────────────────────────────────
-- AI-generated draft texts for platform reports / legal notices / responses
CREATE TABLE moderation_drafts (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    review_id   UUID NOT NULL REFERENCES reviews(id) ON DELETE CASCADE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    draft_type  VARCHAR(50) NOT NULL,   -- 'platform_report' | 'owner_response' | 'legal_notice'
    platform    VARCHAR(50),
    content     TEXT NOT NULL,
    status      VARCHAR(30) NOT NULL DEFAULT 'draft',  -- 'draft' | 'sent' | 'resolved'
    notes       TEXT
);

CREATE INDEX idx_drafts_review_id ON moderation_drafts (review_id);
CREATE INDEX idx_drafts_status    ON moderation_drafts (status);

-- ── Reports ───────────────────────────────────────────────────────────────────
-- Generated export reports (PDF / CSV / JSON)
CREATE TABLE reports (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    report_type VARCHAR(50) NOT NULL,   -- 'summary' | 'detailed' | 'moderation_bundle'
    review_ids  UUID[],
    format      VARCHAR(10) NOT NULL,   -- 'pdf' | 'csv' | 'json'
    file_path   TEXT,
    meta        JSONB
);

-- ── Notification Settings ─────────────────────────────────────────────────────
CREATE TABLE notification_settings (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           VARCHAR(255) NOT NULL UNIQUE,
    risk_threshold  NUMERIC(4,3) NOT NULL DEFAULT 0.65,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Trigger: auto-update updated_at
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN NEW.updated_at = NOW(); RETURN NEW; END;
$$;

CREATE TRIGGER trg_notification_settings_updated_at
    BEFORE UPDATE ON notification_settings
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
