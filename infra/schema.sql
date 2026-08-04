-- Canonical DDL — the single source of schema truth (docs/05).
-- Changes land here AND as a numbered file in infra/migrations/ in the same commit.
-- Three memory layers (docs/02): episodic (incidents), semantic (runbooks), working (working_state).

-- Episodic memory: every incident, resolved or in-flight
CREATE TABLE IF NOT EXISTS incidents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    external_id STRING UNIQUE,        -- idempotent ingest: same alert twice = same row
    service STRING NOT NULL,
    title STRING NOT NULL,
    description STRING NOT NULL,
    severity STRING NOT NULL,
    status STRING NOT NULL DEFAULT 'open',
    resolution_summary STRING,
    embedding VECTOR(1024),           -- DECISION PENDING PROBE: confirm dim against
                                      -- the actual Bedrock embedding model output
    blame_scrubbed BOOL NOT NULL DEFAULT true,
    opened_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at TIMESTAMPTZ
);
CREATE VECTOR INDEX IF NOT EXISTS idx_incidents_embedding ON incidents (service, embedding);

-- Semantic memory: runbooks, independent of any one incident
CREATE TABLE IF NOT EXISTS runbooks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    service STRING NOT NULL,
    title STRING NOT NULL,
    content STRING NOT NULL,
    embedding VECTOR(1024),
    source_incident_id UUID REFERENCES incidents(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE VECTOR INDEX IF NOT EXISTS idx_runbooks_embedding ON runbooks (service, embedding);

-- Working memory: what the agent reads/writes mid-incident (AC7's kill test hits this)
CREATE TABLE IF NOT EXISTS working_state (
    incident_id UUID PRIMARY KEY REFERENCES incidents(id),
    retrieved_matches JSONB,
    proposed_diagnosis STRING,
    confidence STRING,                -- 'high' | 'low' | 'none' (AC13)
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Observability, not memory: the replayable decision log (migration 0002). One row per
-- step of an agent run — model turn or tool call — in execution order. working_state
-- says what the agent believed; this says what it did, what it cost, where it failed.
CREATE TABLE IF NOT EXISTS agent_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL,             -- one agent invocation; groups its steps
    incident_id UUID NOT NULL REFERENCES incidents(id),
    seq INT NOT NULL,                 -- step order within the run, 0-based
    step_type STRING NOT NULL,        -- 'model_turn' | 'tool_call'
    name STRING NOT NULL,             -- Bedrock model id, or the tool name
    outcome STRING NOT NULL,          -- 'success' | 'error'
    latency_ms INT NOT NULL,
    input_tokens INT,                 -- model turns only
    output_tokens INT,                -- model turns only
    confidence STRING,                -- set on search_incidents steps (AC13 audit trail)
    detail STRING,                    -- error text, truncated; NULL on success
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (run_id, seq)
);
CREATE INDEX IF NOT EXISTS idx_agent_runs_run ON agent_runs (run_id, seq);
CREATE INDEX IF NOT EXISTS idx_agent_runs_incident ON agent_runs (incident_id, created_at DESC);
