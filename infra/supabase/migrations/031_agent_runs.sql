-- Migration: 031_agent_runs
-- Description: One row per agent execution. The `agent_kind` is the agent
-- identifier (case_researcher, drafting_assistant, compliance_checker).
-- `output_artifact_id` points to a Document or AnalysisReport that the agent
-- produced when relevant (drafts land in Document; analyses land in
-- AnalysisReport). `input_json` and `output_json` are agent-specific blobs.
-- Date: 2026-08-15

CREATE TABLE IF NOT EXISTS agent_runs (
    id BIGSERIAL PRIMARY KEY,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    matter_id BIGINT REFERENCES matters(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    agent_kind VARCHAR(64) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'running'
        CHECK (status IN ('running', 'succeeded', 'failed', 'cancelled')),
    input_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    output_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    output_artifact_id BIGINT,
    output_artifact_kind VARCHAR(32)
        CHECK (output_artifact_kind IS NULL OR output_artifact_kind IN ('document', 'analysis_report')),
    total_tokens INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_agent_runs_org_user_started
    ON agent_runs(organization_id, user_id, started_at DESC);

CREATE INDEX IF NOT EXISTS idx_agent_runs_matter
    ON agent_runs(matter_id);

CREATE INDEX IF NOT EXISTS idx_agent_runs_kind_status
    ON agent_runs(agent_kind, status);

COMMENT ON TABLE agent_runs IS
    'One row per execution of an agent. Audit + replay source.';
COMMENT ON COLUMN agent_runs.output_artifact_id IS
    'FK to documents(id) or analysis_reports(id) depending on output_artifact_kind.';