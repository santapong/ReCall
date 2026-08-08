-- 0004_cited_runbooks — AC3's other half, made structural.
--
-- docs/01:48 defines AC3 as "every diagnosis cites >=1 real incident ID **+ >=1 runbook
-- step**". Only the incident half was ever enforced: propose_diagnosis took no runbook
-- parameter at all, so the runbook requirement lived exclusively in prompts/system.md
-- rule 4 — an instruction, not a mechanism, and therefore not something the invariant
-- table could honestly claim.
--
-- Storing the cited runbook IDs is what lets the tool validate them the same way it
-- validates incident IDs: against the runbook_ids this run actually retrieved, which
-- record_retrieval already persists inside working_state.retrieved_matches. So the
-- claim becomes "the agent could only cite a runbook it actually pulled", not "a
-- runbook exists somewhere in the table".
--
-- Idempotent like every migration here: CI and dev share one entry point and re-run it.

ALTER TABLE working_state ADD COLUMN IF NOT EXISTS cited_runbook_ids JSONB;

-- The runtime role writes working_state already (0003), and column-level grants are
-- inherited from the table grant, so no additional GRANT is needed here.
