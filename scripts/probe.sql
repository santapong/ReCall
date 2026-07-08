-- P0 probe (docs/01): prove DDL + rows + one `<->` vector query on the live cluster.
-- Run: make probe   (needs CRDB_CONN_STRING in the environment)
-- Uses a throwaway 4-dim table so nothing here commits us to an embedding dimension
-- (that is a separate DECISION PENDING PROBE marker — see docs/02).

-- Some mid-2025 builds gate vector indexes behind a cluster setting (docs/02 probe note).
-- If the CREATE VECTOR INDEX below fails, try:
--   SET CLUSTER SETTING feature.vector_index.enabled = true;
-- and record the answer in docs/02.

CREATE TABLE probe_scratch (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    service STRING NOT NULL,
    note STRING NOT NULL,
    embedding VECTOR(4)
);

CREATE VECTOR INDEX idx_probe_embedding ON probe_scratch (service, embedding);

INSERT INTO probe_scratch (service, note, embedding) VALUES
    ('billing', 'payment webhooks timing out',      '[0.9, 0.1, 0.0, 0.0]'),
    ('billing', 'invoice job stuck',                '[0.7, 0.3, 0.0, 0.0]'),
    ('billing', 'card declines spiking',            '[0.1, 0.9, 0.0, 0.0]'),
    ('auth',    'login latency p99 breach',         '[0.0, 0.0, 0.9, 0.1]'),
    ('auth',    'token refresh loop',               '[0.0, 0.0, 0.1, 0.9]');

-- The shape of the real retrieval query (docs/02): service-scoped, ordered by L2 distance.
SELECT note,
       embedding <-> '[1.0, 0.0, 0.0, 0.0]' AS distance
FROM probe_scratch
WHERE service = 'billing'
ORDER BY embedding <-> '[1.0, 0.0, 0.0, 0.0]'
LIMIT 3;

DROP TABLE probe_scratch;

-- Probe passes when: the CREATE VECTOR INDEX succeeded (flag or no flag — record which),
-- and the SELECT returned 'payment webhooks timing out' first.
