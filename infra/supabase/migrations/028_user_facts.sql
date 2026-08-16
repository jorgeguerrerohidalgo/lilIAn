-- Migration: 028_user_facts
-- Description: Persistent per-user (and per-organization) memory items that the
-- LLM uses as long-term context. Examples: "this firm specializes in labor law",
-- "user prefers Spanish formal register", "user is barred in Santiago".
-- Each fact is tenant-scoped via organization_id. user_id can be NULL when the
-- fact is about the firm rather than the individual user.
-- Date: 2026-08-15

CREATE TABLE IF NOT EXISTS user_facts (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
    kind VARCHAR(64) NOT NULL,
    content TEXT NOT NULL,
    confidence NUMERIC(3, 2) NOT NULL DEFAULT 1.00
        CHECK (confidence >= 0 AND confidence <= 1),
    source VARCHAR(64) NOT NULL DEFAULT 'manual',
    embedding TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT user_facts_user_or_org_only CHECK (
        user_id IS NOT NULL OR kind = 'firm'
    )
);

CREATE INDEX IF NOT EXISTS idx_user_facts_org_user
    ON user_facts(organization_id, user_id);

CREATE INDEX IF NOT EXISTS idx_user_facts_org_kind
    ON user_facts(organization_id, kind);

CREATE INDEX IF NOT EXISTS idx_user_facts_org_updated
    ON user_facts(organization_id, updated_at DESC);

COMMENT ON TABLE user_facts IS
    'Long-term memory items per user (or firm) used to personalize LLM responses.';
COMMENT ON COLUMN user_facts.kind IS
    'Semantic kind: practice_area, jurisdiction, preference, fact, firm_context';
COMMENT ON COLUMN user_facts.source IS
    'How the fact was learned: manual, feedback, observation';
COMMENT ON COLUMN user_facts.embedding IS
    'JSON-stringified float vector (same convention as document_chunks).';