-- 0003_app_role — the least-privilege role the Lambda connects as (Production Readiness).
-- The runtime can read memory, write incidents/working memory, and append to the decision
-- log. It cannot DELETE anything, cannot touch schema (no DDL), and cannot write runbooks —
-- semantic memory changes only through the seed/ops path, never through the agent's runtime.
-- Password/cert is set out-of-band (console or `ALTER ROLE ... WITH PASSWORD` by an admin);
-- secrets never live in migrations.

CREATE ROLE IF NOT EXISTS recall_app WITH LOGIN;

GRANT SELECT, INSERT, UPDATE ON TABLE incidents      TO recall_app;
GRANT SELECT, INSERT, UPDATE ON TABLE working_state  TO recall_app;
GRANT SELECT                 ON TABLE runbooks       TO recall_app;
GRANT SELECT, INSERT         ON TABLE agent_runs     TO recall_app;
