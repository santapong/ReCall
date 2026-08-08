# status_page — index
The one read-only page (docs/03), built 2026-08-04: static HTML + vanilla JS
polling `GET /status` **and** `GET /runlog` every 3 s. The audience is the camera; the
elapsed clock is the signature element and never stops during the node kill.

| item | what it is | read when |
|---|---|---|
| `index.html` | The whole frontend. `?incident_id=` required, `?api=` Function URL base, `?memory=off` captions the AC12 amnesia arm | Before changing anything on screen — read docs/03 first |

## Invariants
- One file, no framework, no build step. Tokens and layout come from docs/03.
- Read-only. The page never writes; it polls two endpoints, together via `allSettled`, because the
  run log is live well before `working_state` has anything to show.
- The clock, badge, and memory panel are never cut (docs/03 quality floor).
- **The event log is `agent_runs`, not inference.** It renders `GET /runlog` — real per-step latency,
  token counts, and the `error` rows that *are* the refusal proof. It was once built from state
  deltas observed in the browser: it looked like a system log, every line was invented, and it could
  never show an error row. Do not reintroduce that.
- **`?memory=off` is a caption, not a filter.** The arm is chosen at ingest (`POST ?memory=off` runs
  the agent with the memory tools withheld); the page renders whatever the database holds for both
  arms. It used to blank a panel client-side, which would have filmed as an A/B while actually
  comparing the page against itself.
- **Failure must look like failure.** One header indicator (`● live` / `● no data`); a wrong ID, a
  cold Lambda and a CORS-blocked request must not all render as a page that never loaded. Note
  `/runlog` answers 200 with an empty list for an unknown incident, so *empty* is not a live signal.
- Panel edges are carried by `--rule`, not by `--card` against `--ink` (1.15:1). Lifting `--card`
  further drops muted text and the alarm colour below 4.5:1.
