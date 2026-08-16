-- Migration: 032_agent_steps
-- Description: Per-step trace of an agent run. A "step" is one
-- reasoning/tool/observation cycle in the agent loop. Allows replay and
-- debugging of complex agent runs after the fact.
-- Date: 2026-08-15

CREATE TABLE IF NOT EXISTS agent_steps (
    id BIGSERIAL PRIMARY KEY,
    run_id BIGINT NOT NULL REFERENCES agent_runs(id) ON DELETE CASCADE,
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    step_index INTEGER NOT NULL,
    kind VARCHAR(32) NOT NULL
        CHECK (kind IN ('reasoning', 'tool_call', 'tool_result', 'final_answer')),
    tool_name VARCHAR(64),
    input_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    output_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    reasoning TEXT,
    tokens_used INTEGER NOT NULL DEFAULT 0,
    duration_ms INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (run_id, step_index)
);

CREATE INDEX IF NOT EXISTS idx_agent_steps_run_index
    ON agent_steps(run_id, step_index);

COMMENT ON TABLE agent_steps IS
    'Per-step trace of an agent run: reasoning, tool_call, tool_result, final_answer.';
COMMENT ON COLUMN agent_steps.kind IS
    'Step kind: reasoning (LLM thought), tool_call (action), tool_result (observation), final_answer (synthesis).';