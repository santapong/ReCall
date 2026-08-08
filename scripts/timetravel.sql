-- AC11 — "what did memory believe at 02:14?", via AS OF SYSTEM TIME.
--
-- Run against the cluster with an incident id:
--     psql -v ON_ERROR_STOP=1 "$CRDB_CONN_STRING" \
--          -v id="'INC-2094'" -f scripts/timetravel.sql
--
-- Why this file exists: AS OF SYSTEM TIME appeared in seven markdown files and two
-- code comments and in no SQL anywhere, so the shot had no mechanism. Worse, the
-- scripted `AS OF SYSTEM TIME '-10m'` against an incident two minutes old returns
-- zero rows, live, on camera — the incident did not exist ten minutes ago.
--
-- So the timestamp is captured, not guessed. Step 1 records "now" before the agent
-- runs; steps 3 and 4 read the same rows at that captured moment and in the present,
-- and the difference between them is the demo.
--
-- Before filming, check the retention window — a read older than the GC TTL fails
-- with "batch timestamp must be after replica GC threshold":
--     SHOW ZONE CONFIGURATION FOR TABLE working_state;   -- look at gc.ttlseconds
-- The default is 4h+ on a local node, but managed tiers can be much shorter.

-- 1 ── Capture the moment. Run this BEFORE the alert, and keep the value on screen.
SELECT cluster_logical_timestamp() AS capture_this_value;

-- 2 ── (fire the alert, let the agent run)

-- 3 ── What memory believed at the captured moment.
--      Paste the value from step 1 in place of :ts and uncomment.
--      Note the confidence and retrieved_matches are the *old* ones — this is the
--      point of the shot: memory is versioned, not overwritten.
-- SELECT i.external_id, ws.confidence, ws.proposed_diagnosis,
--        jsonb_array_length(COALESCE(ws.retrieved_matches->'matches', '[]')) AS matches,
--        ws.updated_at
-- FROM working_state ws JOIN incidents i ON i.id = ws.incident_id
-- AS OF SYSTEM TIME :ts
-- WHERE i.id::STRING = :id OR i.external_id = :id;

-- 4 ── What it believes now. Same query, no AS OF SYSTEM TIME.
SELECT i.external_id, ws.confidence, ws.proposed_diagnosis,
       jsonb_array_length(COALESCE(ws.retrieved_matches->'matches', '[]')) AS matches,
       ws.updated_at
FROM working_state ws JOIN incidents i ON i.id = ws.incident_id
WHERE i.id::STRING = :id OR i.external_id = :id;

-- 5 ── The decision log at the captured moment: how many steps had run by then.
--      Pairs with the page's run-log panel — working_state says what it believed,
--      agent_runs says what it had done to get there.
-- SELECT count(*) AS steps_so_far
-- FROM agent_runs ar JOIN incidents i ON i.id = ar.incident_id
-- AS OF SYSTEM TIME :ts
-- WHERE i.id::STRING = :id OR i.external_id = :id;

SELECT count(*) AS steps_now
FROM agent_runs ar JOIN incidents i ON i.id = ar.incident_id
WHERE i.id::STRING = :id OR i.external_id = :id;
