# status_page — index
The one read-only page (docs/03), built 2026-08-04: static HTML + vanilla JS
polling `GET /status` every 3 s. The audience is the camera; the elapsed clock is
the signature element and never stops during the node kill.

| item | what it is | read when |
|---|---|---|
| `index.html` | The whole frontend. `?incident_id=` required, `?api=` Function URL base, `?memory=off` = AC12 amnesia view | Before changing anything on screen — read docs/03 first |

## Invariants
- One file, no framework, no build step. Tokens and layout come from docs/03.
- One page, read-only, polls one endpoint. `?memory=off` is the amnesia A/B (AC12).
- The clock, badge, and memory panel are never cut (docs/03 quality floor).
