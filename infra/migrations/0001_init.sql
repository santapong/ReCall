-- 0001_init — mirrors infra/schema.sql at repo setup (Jul 8). Applied by `make migrate`.
-- schema.sql stays the canonical full DDL; this file is the numbered history entry.
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
