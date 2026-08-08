-- 0003_app_role — the least-privilege role the Lambda connects as (Production Readiness).
-- The runtime can read memory, write incidents/working memory, and append to the decision
-- log. It cannot DELETE anything, cannot touch schema (no DDL), and cannot write runbooks —
-- semantic memory changes only through the seed/ops path, never through the agent's runtime.
-- Password/cert is set out-of-band (console or `ALTER ROLE ... WITH PASSWORD` by an admin);
-- secrets never live in migrations.

CREATE ROLE IF NOT EXISTS recall_app WITH LOGIN;

-- Without these two the role cannot open a session at all, so the table grants below
-- were unreachable and the "the Lambda connects as recall_app" claim could not have
-- been true. Found by actually connecting as the role (tests/test_app_role.py).
GRANT CONNECT ON DATABASE defaultdb TO recall_app;
GRANT USAGE ON SCHEMA public TO recall_app;

-- "No DDL" was not true until this line. CockroachDB, like Postgres, grants CREATE on
-- schema public to the `public` pseudo-role, which every user inherits — so recall_app
-- could create tables despite owning no CREATE grant of its own. Verified by having
-- the role actually do it (tests/test_app_role.py::test_role_cannot_run_ddl).
-- admin and root keep ALL, so migrations and ops are unaffected.
REVOKE CREATE ON SCHEMA public FROM public;

GRANT SELECT, INSERT, UPDATE ON TABLE incidents      TO recall_app;
GRANT SELECT, INSERT, UPDATE ON TABLE working_state  TO recall_app;
GRANT SELECT                 ON TABLE runbooks       TO recall_app;
GRANT SELECT, INSERT         ON TABLE agent_runs     TO recall_app;
