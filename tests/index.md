# tests — index
pytest is ground truth (docs/06). Fast structural tests run everywhere; DB-backed tests (P1+) run against a real single-node cockroach — mocked-DB tests are banned (docs/05).

| item | maps to | status |
|---|---|---|
| `test_manifest.py` | **AC4** — exactly 4 tools, exact names | live |
| `test_module_boundaries.py` | hard rules 1–2 — write surface, agent purity | live |
| `test_db_retry.py` | docs/05 retry pattern — silent retries, loud failure | live |
| `retrieval_eval.py` | **AC2** — 20 alerts, ≥18 top-3, prints the hit table | P1 |
| scrub test | hard rule 3 — zero survivors over corpus + adversarial strings | P1 |
| citation validation | **AC3** — fake ID in a diagnosis raises, never persists | P2 |

## Invariants
- Every test file names its AC (or hard rule) in its docstring and in this table.
- Fixtures load the deterministic corpus; the RNG seed never changes after P1.
