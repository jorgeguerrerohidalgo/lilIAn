-- Migration: 029_case_context_snapshots
-- Description: Rolling LLM-generated summary of a matter that gets injected
-- into every new chat session, so users do not have to re-explain the case.
-- One snapshot per matter, updated as the conversation progresses.
-- Date: 2026-08-15

CREATE TABLE IF NOT EXISTS case_context_snapshots (
    id BIGSERIAL PRIMARY KEY,
    matter_id BIGINT NOT NULL UNIQUE REFERENCES matters(id) ON DELETE CASCADE,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    summary TEXT NOT NULL,
    key_entities JSONB NOT NULL DEFAULT '{}'::jsonb,
    open_questions JSONB NOT NULL DEFAULT '[]'::jsonb,
    last_chat_message_id BIGINT REFERENCES chat_messages(id) ON DELETE SET NULL,
    version INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_case_context_snapshots_org_matter
    ON case_context_snapshots(organization_id, matter_id);

COMMENT ON TABLE case_context_snapshots IS
    'Rolling summary of a matter used as context in new chat sessions.';
COMMENT ON COLUMN case_context_snapshots.key_entities IS
    'JSON: {"parties": [...], "amounts": [...], "dates": [...]}';
COMMENT ON COLUMN case_context_snapshots.open_questions IS
    'JSON array of unresolved questions from past conversations.';