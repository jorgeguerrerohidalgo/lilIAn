-- Migration: 030_feedback_signals
-- Description: User feedback (thumbs up/down, ratings, corrections) on
-- assistant messages. The `extracted_fact` column is filled when the user
-- correction yields a new persistent fact that gets promoted to user_facts.
-- Date: 2026-08-15

CREATE TABLE IF NOT EXISTS feedback_signals (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    chat_message_id BIGINT NOT NULL REFERENCES chat_messages(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    rating SMALLINT NOT NULL CHECK (rating BETWEEN -1 AND 1),
    correction TEXT,
    extracted_fact TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_feedback_signals_org_user_created
    ON feedback_signals(organization_id, user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_feedback_signals_message
    ON feedback_signals(chat_message_id);

COMMENT ON TABLE feedback_signals IS
    'User feedback on assistant messages; -1 thumbs-down, 0 neutral, 1 thumbs-up.';
COMMENT ON COLUMN feedback_signals.extracted_fact IS
    'Optional fact promoted from this feedback into user_facts.';