# status_page — index
The whole frontend: one static HTML file, built at **P3 (Jul 27+)** per docs/03. Do not build early; do not add a framework.

| item | what it is | read when |
|---|---|---|
| `index.html` | The page (elapsed clock, memory panel, confidence badge, event log) | P3 — read docs/03 first |

## Invariants
- One page, read-only, polls one endpoint. `?memory=off` is the amnesia A/B (AC12).
- The clock, badge, and memory panel are never cut (docs/03 quality floor).
