-- 0002_agent_runs — the replayable decision log (2026-08-04).
--
-- WHY: the three memory layers say what the agent *knows*. Nothing said what the agent
-- *did*. "Secure, observable, and scalable" is a first-class judging criterion and the
-- honest answer was "we have tests." This table is the observability surface: one row
-- per step of an agent run, in order, so any diagnosis can be replayed after the fact —
-- which tool was called, what it cost, how long it took, and whether it failed.
--
-- Grain is the STEP, not the run: a step is either a model turn or a tool call. Keeping
-- both in one ordered table is what makes it replayable — `ORDER BY run_id, seq` returns
-- the exact interleaving the loop executed. Token counts belong to model turns (Bedrock
-- reports them per Converse response); latency and outcome apply to both.
--
-- Pairs with AS OF SYSTEM TIME: working_state answers "what did memory believe at 02:14",
-- agent_runs answers "and what did it do to get there, at what cost".

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

    UNIQUE (run_id, seq)              -- a step number is written once, never twice
);

-- The two reads that matter: replay one run in order, and pull an incident's full history.
CREATE INDEX IF NOT EXISTS idx_agent_runs_run ON agent_runs (run_id, seq);
CREATE INDEX IF NOT EXISTS idx_agent_runs_incident ON agent_runs (incident_id, created_at DESC);
